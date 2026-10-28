"""Recompute this finite camera comparison from portable check bundles only."""

import argparse
import hashlib
import io
import zipfile
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json
from nisayon.qualification import inspect_check_bundle


def camera_score(actual, expected, mode):
    rows, reference = actual["conditions"], expected["conditions"]
    if len(rows) != 352 or [r["id"] for r in rows] != [r["id"] for r in reference]:
        raise ValueError("Incomplete or misaligned native camera rows")
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate camera condition")
    matches = sum(
        canonical_bytes(a) == canonical_bytes(b) for a, b in zip(rows, reference, strict=True)
    )
    return {"mode": mode, "matched": matches, "assigned": len(rows), "holds": matches == len(rows)}


def review_bundle(path, mode):
    review = inspect_check_bundle(path)
    if review["review_status"] != "verified":
        raise ValueError("Portable check review did not verify")
    data = path.read_bytes()
    if len(data) > 16 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != review["bundle_sha256"]:
        raise ValueError("Bundle changed or exceeds the example's resource bound")
    prefix = "evidence/" + review["recorded_assessment"]["execution_path"] + "/"
    artifacts = review["assessment"]["review"]["artifacts"]
    observed = artifacts["observe"]
    diagnostic = camera_score(observed["actual"], observed["expected"][mode], mode)
    if diagnostic != artifacts["score"]:
        raise ValueError("Saved diagnostic score differs from native records")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:

        def read(name):
            return decode_json(archive.read(prefix + name))

        confirmation = camera_score(
            read("checks/confirm/native/actual.json"),
            read(f"checks/confirm/native/expected-{mode}.json"),
            mode,
        )
        execution = read("execution.json")
        process_names = [
            name
            for name in archive.namelist()
            if name.startswith(prefix) and name.endswith("/native-completion.json")
        ]
        for name in process_names:
            if decode_json(archive.read(name))["returncode"] != 0:
                raise ValueError("Native process did not complete successfully")
    expected_decision = "adopt" if diagnostic["holds"] and confirmation["holds"] else "reject"
    if (
        artifacts["confirm"]["diagnostic"] != diagnostic
        or artifacts["confirm"]["confirmation"] != confirmation
        or artifacts["confirm"]["decision"] != expected_decision
    ):
        raise ValueError("Saved confirmation differs from native records")
    if review["deployment_decision"] != "unresolved":
        raise ValueError("Unsupported deployment authority")
    return {
        "mode": mode,
        "diagnostic": diagnostic,
        "confirmation": confirmation,
        "decision": expected_decision,
        "native_processes": len(process_names),
        "actions": {r["check"]: r["action"] for r in execution["attempts"]},
        "bundle_sha256": review["bundle_sha256"],
        "deployment_decision": "unresolved",
    }


def main():
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    rows = []
    for arm in ("conservative", "scoped"):
        for mode in ("configured_budget", "all_configured_slots"):
            rows.append({"arm": arm, **review_bundle(args.directory / f"{arm}-{mode}.zip", mode)})
    if [r["decision"] for r in rows] != ["adopt", "reject", "adopt", "reject"]:
        raise ValueError("Unexpected declared contract decisions")
    if [r["native_processes"] for r in rows] != [2, 2, 2, 1]:
        raise ValueError("Native execution coverage differs")
    if rows[-1]["actions"] != {"observe": "reuse", "score": "run", "confirm": "run"}:
        raise ValueError("Scoring-change obligations differ")
    print(
        json.dumps(
            {
                "records": rows,
                "new_native_execution": False,
                "limit": "Recomputed finite software records; no independent truth or owner savings.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
