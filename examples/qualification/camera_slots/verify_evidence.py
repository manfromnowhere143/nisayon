"""Recompute the complete frozen camera study without native execution.

Checks remain active under optimized Python. Hashes establish consistency, not
authenticity; retained references do not independently establish physical truth.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json
from nisayon.qualification import inspect_bundle

ARMS = ("base", "pr5129", "pr5120", "pr5120_base")
SEEDS = (17, 67)
MODES = ("configured_budget", "all_configured_slots")
CASES = (
    "base-configured_budget-all",
    "pr5129-configured_budget-all",
    "pr5120-configured_budget-changed_three",
    "pr5120-all_configured_slots-changed_three",
    "pr5129-all_configured_slots-all",
)
# The frozen 352-row assignment, independent of the counts claimed by a packet.
LAYOUTS = {
    "pi0": ("bchw", "bhwc"),
    "pi05": ("bchw", "bhwc", "btchw", "bthwc"),
    "pi0_fast": ("bchw", "bhwc"),
    "smolvla": ("bchw", "btchw"),
    "xvla": ("bchw", "btchw"),
    "evo1": ("bchw", "btchw"),
}
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(f"Invalid camera evidence: {message}")


def same(left, right):
    # Python's ordinary equality silently equates True, 1 and 1.0.
    return canonical_bytes(left) == canonical_bytes(right)


def condition_ids(scope="all"):
    return [
        f"{policy}-{layout}-b{budget}-s{subset}-r{reverse}"
        for policy, layouts in LAYOUTS.items()
        if scope == "all" or policy in ("pi0", "pi05", "smolvla")
        for layout in layouts
        for budget in ((0, 1, 3) if policy in ("smolvla", "evo1") else (3,))
        for subset in range(8)
        for reverse in (0, 1)
    ]


def bounded_read(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, f"file exceeds limit: {path.name}")
    return data


def count(value, limit, context):
    require(type(value) is int and 0 <= value <= limit, f"invalid count: {context}")
    return value


def read_members(packet):
    manifest = decode_json(bounded_read(packet / "evidence-manifest.json", 64 * 1024))
    require(isinstance(manifest, dict), "manifest must be an object")
    expected_names = {
        f"native/{arm}-{seed}/{name}"
        for arm in ARMS
        for seed in SEEDS
        for name in ("actual.json", "report.json", *(f"expected-{mode}.json" for mode in MODES))
    } | {"portable-readback.json", *(f"portable/{case}.zip" for case in CASES)}
    records = manifest.get("members")
    require(isinstance(records, dict) and set(records) == expected_names, "archive coverage")
    total = count(manifest.get("payload_bytes"), MAX_PAYLOAD_BYTES, "payload")
    for name, record in records.items():
        require(isinstance(record, dict), f"member metadata: {name}")
        count(record.get("bytes"), MAX_MEMBER_BYTES, name)
    require(sum(r["bytes"] for r in records.values()) == total, "declared payload total")
    size = count(manifest.get("archive_bytes"), MAX_PAYLOAD_BYTES, "archive")
    data = bounded_read(packet / "evidence.tar.gz", MAX_PAYLOAD_BYTES)
    require(len(data) == size, "archive size")
    require(hashlib.sha256(data).hexdigest() == manifest.get("archive_sha256"), "archive digest")
    # Bound decompression before tar parsing, including extended-header overhead.
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        unpacked = stream.read(MAX_PAYLOAD_BYTES + 1024 * 1024 + 1)
    require(len(unpacked) <= MAX_PAYLOAD_BYTES + 1024 * 1024, "expanded archive limit")
    members = {}
    with tarfile.open(fileobj=io.BytesIO(unpacked), mode="r:") as archive:
        for member in archive:
            name = member.name
            require(name in records and name not in members, "unexpected or duplicate member")
            require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE), "nonregular member")
            record = records[name]
            require(member.size == record["bytes"], f"member size: {name}")
            source = archive.extractfile(member)
            require(source is not None, f"unreadable member: {name}")
            content = source.read(member.size + 1)
            require(len(content) == member.size, f"short member: {name}")
            require(
                hashlib.sha256(content).hexdigest() == record.get("sha256"),
                f"member digest: {name}",
            )
            members[name] = content
    require(set(members) == expected_names, "missing archive member")
    require(sum(map(len, members.values())) == total, "payload total")
    return members


def rows_by_id(value, expected_ids, context):
    expected_ids = set(expected_ids)
    require(isinstance(value, dict) and set(value) == {"conditions"}, f"row container: {context}")
    rows = value["conditions"]
    require(isinstance(rows, list), f"row list: {context}")
    indexed = {}
    for row in rows:
        require(isinstance(row, dict) and type(row.get("id")) is str, f"row identity: {context}")
        identifier = row["id"]
        require(
            identifier in expected_ids and identifier not in indexed,
            f"unexpected or duplicate row: {context}",
        )
        fields = (
            {"id", "input_unchanged", "error"}
            if "error" in row
            else {"id", "input_unchanged", "images", "masks"}
        )
        require(
            set(row) == fields and type(row["input_unchanged"]) is bool, f"row schema: {context}"
        )
        if "error" in row:
            require(row["error"] == "ValueError", f"unknown native error: {context}")
        else:
            require(
                isinstance(row["images"], list) and isinstance(row["masks"], list),
                f"tensor lists: {context}",
            )
        indexed[identifier] = row
    require(set(indexed) == set(expected_ids), f"condition coverage: {context}")
    return indexed


def verify(packet):
    members = read_members(Path(packet))
    ids = condition_ids()
    native = {}
    for arm in ARMS:
        for seed in SEEDS:
            prefix = f"native/{arm}-{seed}/"
            report = decode_json(members[prefix + "report.json"])
            require(isinstance(report, dict), f"report: {prefix}")
            require(same(report.get("seed"), seed), f"seed binding: {prefix}")
            require(same(report.get("rows"), len(ids)), f"assigned rows: {prefix}")
            actual = rows_by_id(decode_json(members[prefix + "actual.json"]), ids, prefix)
            comparisons = report.get("comparisons")
            require(
                isinstance(comparisons, dict) and set(comparisons) == set(MODES),
                f"contract coverage: {prefix}",
            )
            for mode in MODES:
                expected = rows_by_id(
                    decode_json(members[prefix + f"expected-{mode}.json"]), ids, prefix + mode
                )
                groups = comparisons[mode]
                require(
                    isinstance(groups, dict) and set(groups) == set(LAYOUTS),
                    f"policy coverage: {prefix}",
                )
                for policy, declared in groups.items():
                    assigned = [
                        identifier for identifier in ids if identifier.split("-", 1)[0] == policy
                    ]
                    mismatches = [
                        identifier
                        for identifier in assigned
                        if not same(actual[identifier], expected[identifier])
                    ]
                    counts = {
                        "assigned": len(assigned),
                        "matched": len(assigned) - len(mismatches),
                        "mismatches": mismatches,
                    }
                    require(same(declared, counts), f"native counts: {prefix}{mode}/{policy}")
                native[arm, seed, mode] = (actual, expected)
    readback = decode_json(members["portable-readback.json"])
    require(isinstance(readback, dict), "portable readback object")
    declared = readback.get("readbacks")
    require(isinstance(declared, list) and len(declared) == len(CASES), "portable review coverage")
    indexed = {}
    for row in declared:
        require(isinstance(row, dict) and type(row.get("id")) is str, "portable review identity")
        identifier = row["id"]
        require(
            identifier in CASES and identifier not in indexed,
            "unexpected or duplicate portable review",
        )
        indexed[identifier] = row
    summaries = []
    with tempfile.TemporaryDirectory(prefix="nisayon-camera-readback-") as temporary:
        for identifier in CASES:
            row = indexed[identifier]
            bundle = Path(temporary) / f"{identifier}.zip"
            content = members[f"portable/{identifier}.zip"]
            require(
                hashlib.sha256(content).hexdigest() == row.get("bundle_sha256"),
                "portable bundle digest",
            )
            bundle.write_bytes(content)
            review = inspect_bundle(bundle, include_plan=True)
            require(
                review["review_status"] == row.get("review_status") == "verified",
                "portable review status",
            )
            require(
                review["assessment"]["execution_validity"] == "valid", "portable execution invalid"
            )
            require(
                review["software_decision"]
                == row.get("sdk_decision")
                == row.get("native_decision"),
                "portable decision disagreement",
            )
            require(
                review["deployment_decision"] == row.get("deployment_decision") == "unresolved",
                "deployment decision",
            )
            case = review["plan"]["case"]
            require(
                case["id"] == identifier and case["contract"] == {"kind": "exact"},
                "portable case binding",
            )
            arm, mode, scope = identifier.split("-", 2)
            assigned_ids = condition_ids(scope)
            probes = case["probes"]
            require(
                [p["id"] for p in probes] == [f"seed-{seed}" for seed in SEEDS],
                "portable seed coverage",
            )
            comparisons = []
            for seed, probe in zip(SEEDS, probes, strict=True):
                require(
                    same(probe["input"], {"seed": seed, "mode": mode, "scope": scope}),
                    "portable input binding",
                )
                actual, expected = native[arm, seed, mode]
                reference = rows_by_id(probe["expected"], assigned_ids, identifier)
                require(
                    all(same(reference[key], expected[key]) for key in assigned_ids),
                    "portable reference binding",
                )
                comparisons.extend(same(actual[key], expected[key]) for key in assigned_ids)
            require(same(len(comparisons), row.get("assigned")), "portable assigned count")
            require(same(sum(comparisons), row.get("matched")), "portable matched count")
            decision = "adopt" if all(comparisons) else "reject"
            require(decision == review["software_decision"], "native/SDK decision disagreement")
            summaries.append({"id": identifier, "decision": decision})
    return {
        "native_reports_verified": len(ARMS) * len(SEEDS),
        "portable_reviews_verified": len(summaries),
        "decisions": summaries,
        "new_native_execution": False,
    }


def main():
    print(json.dumps(verify(Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    main()
