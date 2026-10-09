"""Labelled partial-input and repeated-read recovery; never resumes physics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nisayon.engine.confirmation_pairs import iter_pairs
from nisayon.engine.confirmation_view import INPUTS, build_view, validate_view
from nisayon.engine.io import digest, file_digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    spec = json.loads(Path(INPUTS).read_text())
    selection = [["development-ablation-001", "D01-gripper-sign", "A"]]
    partial_root = args.out / "labelled-header-only-reference"
    tail = Path("development-ablation-001/D01-gripper-sign/A/confirmation/execution")
    header = Path("artifacts") / tail / "bundle-header.json"
    target = partial_root / tail / "bundle-header.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(header.read_bytes())
    partial, partial_timing = build_view(
        Path.cwd(), spec, raw_base=partial_root, selection=selection
    )
    again, _ = build_view(Path.cwd(), spec, raw_base=partial_root, selection=selection)
    assert digest(partial) == digest(again)
    recovered, recovery_timing = build_view(Path.cwd(), spec, selection=selection)
    reread, reread_timing = build_view(Path.cwd(), spec, selection=selection)
    partial_pairs, recovered_pairs = list(iter_pairs(partial)), list(iter_pairs(recovered))
    assert len(partial_pairs) == len(recovered_pairs) == 33
    assert all(p["state"] == "incomplete_or_invalid" for p in partial_pairs)
    assert all(p["state"] == "complete" for p in recovered_pairs)
    assert [p["id"] for p in partial_pairs] == [p["id"] for p in recovered_pairs]
    assert digest(recovered) == digest(reread)
    assert recovered["trials"][0]["costs"] == reread["trials"][0]["costs"]
    check = validate_view(recovered, Path.cwd(), expected_content_sha256=digest(recovered))
    assert check["status"] == "current"
    report = {
        "schema": "nisayon.confirmation-read-recovery.v1",
        "recovery_driver_source_sha256": file_digest(Path(__file__)),
        "scope": "A labelled header-only copy omits raw records; recovery changes the read locator back to the original retained store. No original store is modified or copied.",
        "header_copy": {
            "path": str(target),
            "sha256": file_digest(target),
            "bytes": target.stat().st_size,
        },
        "partial_sha256": digest(partial),
        "recovered_sha256": digest(recovered),
        "partial_recovery": partial["trials"][0]["confirmation"]["raw_source"]["recovery"],
        "partial_pair_count": len(partial_pairs),
        "recovered_pair_count": len(recovered_pairs),
        "same_pair_identities": True,
        "repeated_partial_read_identical": True,
        "repeated_complete_read_identical": True,
        "historical_costs_counted_once_per_view": recovered["trials"][0]["costs"],
        "validation": check,
        "processing_timings": {
            "partial": partial_timing,
            "recovery": recovery_timing,
            "reread": reread_timing,
        },
        "scientific_acceptance": "none",
        "physical_execution_guarantee": "none; this is a read-only recovery exercise",
    }
    write_json(args.out / "recovery.json", report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "partial_pair_count",
                    "recovered_pair_count",
                    "same_pair_identities",
                    "validation",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
