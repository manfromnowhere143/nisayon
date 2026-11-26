"""Compare every retained NPZ array with the exposed historical B2 execution."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    current = json.loads((args.current / "result.json").read_text())
    old = json.loads((args.historical / "result.json").read_text())
    prior = {(r["seed"], r["mode"]): r for r in old["episodes"]}
    rows = []
    for row in current["episodes"]:
        key = (row["seed"], row["mode"])
        before = prior[key]
        name = f"{row['seed']}-{row['mode']}.npz"
        with (
            np.load(args.current / name, allow_pickle=False) as new,
            np.load(args.historical / name, allow_pickle=False) as previous,
        ):
            same_keys = set(new.files) == set(previous.files)
            differences = [
                k
                for k in new.files
                if k not in previous.files or not np.array_equal(new[k], previous[k])
            ]
        rows.append(
            {
                "seed": key[0],
                "mode": key[1],
                "same_outcome_and_steps": all(row[k] == before[k] for k in ("outcome", "steps")),
                "same_keys": same_keys,
                "array_differences": differences,
            }
        )
    valid = (
        len(rows) == 20
        and current["weights_unchanged"]
        and all(
            r["same_outcome_and_steps"] and r["same_keys"] and not r["array_differences"]
            for r in rows
        )
    )
    result = {
        "schema": "nisayon.edpi.b2.recheck.v1",
        "verified": valid,
        "fresh_confirmation": False,
        "verdict": current["verdict"],
        "rows": rows,
        "current_manifest": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(args.current.iterdir())
            if p.is_file()
        },
        "historical_result_sha256": hashlib.sha256(
            (args.historical / "result.json").read_bytes()
        ).hexdigest(),
        "scope": "Array/outcome equality on exposed seeds. Runtime/path metadata can differ; no cross-platform bitwise guarantee or independent-human replication.",
    }
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"verified": valid, "episodes": len(rows), "verdict": current["verdict"]}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
