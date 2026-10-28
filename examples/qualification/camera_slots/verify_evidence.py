"""Recompute the retained finite decisions without LeRobot or its environment."""

import hashlib
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from nisayon.qualification import inspect_bundle


def main():
    packet = Path(sys.argv[1])
    manifest = json.loads((packet / "evidence-manifest.json").read_text())
    data = (packet / "evidence.tar.gz").read_bytes()
    assert hashlib.sha256(data).hexdigest() == manifest["archive_sha256"]
    assert len(data) == manifest["archive_bytes"]
    assert manifest["payload_bytes"] <= 64 * 1024 * 1024
    members = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            name = member.name
            relative = PurePosixPath(name)
            assert not relative.is_absolute() and ".." not in relative.parts
            assert name in manifest["members"] and name not in members and member.isfile()
            record = manifest["members"][name]
            assert member.size == record["bytes"] <= 16 * 1024 * 1024
            source = archive.extractfile(member)
            assert source is not None
            content = source.read(member.size + 1)
            assert len(content) == member.size
            assert hashlib.sha256(content).hexdigest() == record["sha256"]
            members[name] = content
    assert set(members) == set(manifest["members"])
    assert sum(map(len, members.values())) == manifest["payload_bytes"]
    native_runs = []
    for name, content in members.items():
        if not name.startswith("native/") or not name.endswith("/report.json"):
            continue
        prefix = name.removesuffix("report.json")
        report = json.loads(content)
        actual = json.loads(members[prefix + "actual.json"])["conditions"]
        assert len(actual) == report["rows"]
        assert len({r["id"] for r in actual}) == len(actual)
        for mode, groups in report["comparisons"].items():
            expected_rows = json.loads(members[prefix + f"expected-{mode}.json"])["conditions"]
            expected = {row["id"]: row for row in expected_rows}
            assert set(expected) == {row["id"] for row in actual}
            for policy, counts in groups.items():
                rows = [r for r in actual if r["id"].split("-", 1)[0] == policy]
                mismatches = [r["id"] for r in rows if r != expected[r["id"]]]
                assert counts == {
                    "assigned": len(rows),
                    "matched": len(rows) - len(mismatches),
                    "mismatches": mismatches,
                }
        native_runs.append(name)
    assert len(native_runs) == 8
    declared = json.loads(members["portable-readback.json"])["readbacks"]
    summaries = []
    with tempfile.TemporaryDirectory(prefix="nisayon-camera-readback-") as temporary:
        for row in declared:
            name = f"portable/{row['id']}.zip"
            bundle = Path(temporary) / f"{row['id']}.zip"
            bundle.write_bytes(members[name])
            assert hashlib.sha256(members[name]).hexdigest() == row["bundle_sha256"]
            review = inspect_bundle(bundle)
            assert review["review_status"] == "verified"
            assert review["assessment"]["execution_validity"] == "valid"
            assert review["software_decision"] == row["sdk_decision"] == row["native_decision"]
            assert review["deployment_decision"] == "unresolved"
            # Recompute the native gate from raw records, independent of saved counts.
            arm, mode, scope = row["id"].split("-", 2)
            comparisons = []
            for seed in (17, 67):
                prefix = f"native/{arm}-{seed}/"
                actual = json.loads(members[prefix + "actual.json"])["conditions"]
                expected = json.loads(members[prefix + f"expected-{mode}.json"])["conditions"]
                if scope == "changed_three":
                    selected = {"pi0", "pi05", "smolvla"}
                    actual = [r for r in actual if r["id"].split("-", 1)[0] in selected]
                    expected = [r for r in expected if r["id"].split("-", 1)[0] in selected]
                comparisons += [a == b for a, b in zip(actual, expected, strict=True)]
            assert len(comparisons) == row["assigned"]
            assert sum(comparisons) == row["matched"]
            assert ("adopt" if all(comparisons) else "reject") == row["sdk_decision"]
            summaries.append({"id": row["id"], "decision": row["sdk_decision"]})
    print(
        json.dumps(
            {
                "native_reports_verified": len(native_runs),
                "portable_reviews_verified": len(summaries),
                "decisions": summaries,
                "new_native_execution": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
