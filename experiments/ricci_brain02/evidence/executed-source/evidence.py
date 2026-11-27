"""Independent accounting of Brain 01 records, including incomplete prefixes.

Digests establish artifact integrity, not execution authenticity. The inherited
evaluator is recomputed, not treated as an independent physical ground truth.
"""

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def rows_at(episode: Path) -> list[dict]:
    return [json.loads(line) for line in (episode / "policy.jsonl").read_text().splitlines()]


def verify_files(root: Path, expected_manifest: str | None = None) -> dict:
    """Verify the existing format without importing any archived producer code."""
    if root.is_symlink():
        raise ValueError("episode directory is a symlink")
    manifest_path = root / "manifest.json"
    if expected_manifest is not None and sha256(manifest_path) != expected_manifest:
        raise ValueError("manifest differs from retained anchor")
    from ricci_brain.replay import read_json

    manifest = read_json(manifest_path)
    if manifest["schema"] != "ricci-brain01.episode.v2":
        raise ValueError("unsupported episode schema")
    names = set()
    size = 0
    for entry in manifest["files"]:
        name = entry["path"]
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or str(relative) != name
            or name in names
        ):
            raise ValueError("unsafe or duplicate manifest member")
        names.add(name)
        target = root / relative
        if any(
            (root / Path(*relative.parts[:i])).is_symlink()
            for i in range(1, len(relative.parts) + 1)
        ):
            raise ValueError("symlink member")
        if target.stat().st_size != entry["bytes"] or sha256(target) != entry["sha256"]:
            raise ValueError(f"member mismatch: {name}")
        size += entry["bytes"]
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != names | {"manifest.json"}:
        raise ValueError("file closure mismatch")
    return {"manifest_sha256": sha256(manifest_path), "files": len(names), "bytes": size}


def prefix_agreement(reference: list[dict], treatment: list[dict], period: float = 0.02) -> dict:
    """Require complete coverage through the first decision, not zip agreement.

    Only observations and issued/applied commands are compared. Host execution
    time is diagnostic and is not part of the modeled physical input history.
    Both traces must reach the branch point. No-decision traces must end together.
    """
    if not reference or not treatment or not math.isfinite(period) or period <= 0:
        raise ValueError("nonempty traces and positive finite period required")
    for rows in (reference, treatment):
        for i, row in enumerate(rows):
            if row["tick"] != i or not math.isclose(row["t"], i * period, abs_tol=1e-10, rel_tol=0):
                return {"matched": False, "reason": "clock_discontinuity", "tick": i}
    decisions = [
        r["decision_time_s"] for r in reference + treatment if r["decision_time_s"] is not None
    ]
    if decisions:
        cutoff = min(decisions)
        if (
            not math.isfinite(cutoff)
            or cutoff < 0
            or not math.isclose(cutoff / period, round(cutoff / period), abs_tol=1e-8)
        ):
            raise ValueError("invalid decision clock")
        count = round(cutoff / period)
        if min(len(reference), len(treatment)) <= count:
            return {"matched": False, "reason": "incomplete_prefix", "cutoff_s": cutoff}
    else:
        cutoff = None
        count = len(reference)
        if count != len(treatment):
            return {"matched": False, "reason": "unequal_no_decision_horizons"}
    for i in range(count):
        a, b = reference[i], treatment[i]
        if a["observation"] != b["observation"]:
            return {"matched": False, "reason": "observation_divergence", "tick": i}
        for field in ("command", "applied_command"):
            ac, bc = a[field], b[field]
            if ac.keys() != bc.keys() or any(ac[k] != bc[k] for k in ac if k != "torque_nm"):
                return {"matched": False, "reason": f"{field}_metadata_divergence", "tick": i}
            x, y = ac["torque_nm"], bc["torque_nm"]
            if len(x) != len(y) or any(
                not math.isclose(u, v, abs_tol=1e-10, rel_tol=0) for u, v in zip(x, y, strict=True)
            ):
                return {"matched": False, "reason": f"{field}_divergence", "tick": i}
    return {"matched": True, "compared_rows": count, "cutoff_s": cutoff}


def audit_history(root: Path, packet: Path) -> dict:
    started = time.perf_counter()
    index = json.loads((packet / "episode-index.json").read_text())
    anchors = json.loads((packet / "episode-manifests.json").read_text())["episodes"]
    by_path = {item["path"]: item for item in index}
    if (
        len(by_path) != len(index)
        or set(by_path) != {item["episode"] for item in anchors}
        or len(anchors) != len(index)
    ):
        raise ValueError("index/anchor mismatch")
    from ricci_brain.evaluation import evaluate
    from ricci_brain.replay import read_json

    verified = []
    for anchor in anchors:
        name = anchor["episode"]
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe episode path")
        episode = root / relative
        integrity = verify_files(episode, anchor["manifest_sha256"])
        result = read_json(episode / "result.json")
        if result != by_path[name]["result"]:
            raise ValueError(f"index result mismatch: {name}")
        recomputed = evaluate(
            read_json(episode / "truth.json"), read_json(episode / "source/protocol.json")
        )
        if any(result[k] != v for k, v in recomputed.items()):
            raise ValueError(f"evaluator mismatch: {name}")
        verified.append(
            {
                "episode": name,
                **integrity,
                "outcome": result["outcome"],
                "censored": result["censored"],
            }
        )
    heldout = [r for r in index if r["group"] == "heldout"]
    matched = []
    paired = []
    for family, case in sorted({(r["family"], r["case"]) for r in heldout}):
        arms = {r["arm"]: r for r in heldout if (r["family"], r["case"]) == (family, case)}
        reference = rows_at(root / arms["none"]["path"])
        for arm in ("baseline", "candidate", "privileged"):
            matched.append(
                {
                    "family": family,
                    "case": case,
                    "arm": arm,
                    **prefix_agreement(reference, rows_at(root / arms[arm]["path"])),
                }
            )
        b, c = (arms[a]["result"] for a in ("baseline", "candidate"))
        paired.append(
            {
                "family": family,
                "case": case,
                "baseline_completed": b["completed"],
                "candidate_completed": c["completed"],
                "baseline_censored": b["censored"],
                "candidate_censored": c["censored"],
            }
        )
    table = Counter((p["baseline_completed"], p["candidate_completed"]) for p in paired)
    n = len(paired)
    wins, losses = table[False, True], table[True, False]
    # Independent closed form of the retained zero-discordance Bonferroni bound.
    interval = [-1 + 0.0125 ** (1 / n), 1 - 0.0125 ** (1 / n)] if wins == losses == 0 else None
    return {
        "schema": "ricci.rb02.history-audit.v1",
        "root": str(root.resolve()),
        "index_sha256": sha256(packet / "episode-index.json"),
        "anchor_ledger_sha256": sha256(packet / "episode-manifests.json"),
        "verified_episodes": verified,
        "bytes_read": sum(r["bytes"] for r in verified),
        "prefixes": matched,
        "prefixes_matched": sum(r["matched"] for r in matched),
        "pairs": paired,
        "contingency": {
            "both_complete": table[True, True],
            "candidate_only": wins,
            "baseline_only": losses,
            "neither_observed_complete": table[False, False],
        },
        "jointly_censored": sum(p["baseline_censored"] and p["candidate_censored"] for p in paired),
        "zero_discordance_conservative_95_interval": interval,
        "completions_by_arm": {
            a: sum(r["result"]["completed"] for r in heldout if r["arm"] == a)
            for a in ("none", "baseline", "candidate", "privileged")
        },
        "wall_s": time.perf_counter() - started,
        "limitations": [
            "Artifact audit and inherited evaluator recomputation, not full campaign execution.",
            "No execution authenticity or real-world truth guarantee.",
            "Interval concerns observed completion indicators under exchangeable paired trials; fixed grid does not establish population transfer.",
            "Censored records do not establish eventual failure or safe continuation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    result = audit_history(args.root, args.packet)
    write_json(args.out, result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "prefixes_matched",
                    "contingency",
                    "jointly_censored",
                    "completions_by_arm",
                    "wall_s",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
