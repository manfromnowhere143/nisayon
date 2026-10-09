"""Two narrow integration questions about the newly supplied cancellation fields.

Uses the evaluator owner's labelled synthetic fixture and public evaluator.
This is not robot evidence or a demonstration of false repair acceptance.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

from nisayon.engine.io import file_digest, write_json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/evaluation"))

from test_evaluation_cancellation import STOP, decide, document  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    for name in (
        "valid_stop",
        "violation_names_nonviolating_reference",
        "empty_explicit_membership",
    ):
        cancellation = copy.deepcopy(STOP)
        if name == "violation_names_nonviolating_reference":
            cancellation["violation"] = {
                "condition_id": "seed-1001",
                "run_id": "confirmation-reference-1001",
                "code": "regression_on_fresh_condition",
            }
        if name == "empty_explicit_membership":
            doc, protocol = document()
            doc["confirmation"]["assignments"] = []
        else:
            doc, protocol = document(
                candidate_fails={"seed-1001"},
                drop={"seed-1002", "seed-1003"},
                cancellation=cancellation,
            )
        decision = decide(doc, protocol, args.out / name)
        write_json(args.out / name / "decision.json", decision)
        rows.append(
            {
                "case": name,
                "decision": decision["decision"],
                "reason_codes": sorted({r["code"] for r in decision["reasons"]}),
                "confirmation": decision.get("confirmation"),
                "input_sha256": file_digest(args.out / name / "bundle.json"),
            }
        )
    report = {
        "schema": "nisayon.temporal-cancellation-integration.v1",
        "source": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "evaluator_source": {
            name: file_digest(ROOT / name)
            for name in (
                "src/nisayon/evaluation/confirmation.py",
                "src/nisayon/evaluation/first_case.py",
                "tests/evaluation/test_evaluation_cancellation.py",
            )
        },
        "kind": "labelled synthetic metadata-conformance probes; no robot result or false bad-repair acceptance claim",
        "questions": [
            "Must a supplied violating run ID identify the run to which the claimed violation is attributed, beyond pair membership?",
            "Can a present empty explicit assignment list be treated as absent when the frozen membership is nonempty?",
        ],
        "rows": rows,
    }
    write_json(args.out / "probes.json", report)
    print(json.dumps([{k: row[k] for k in ("case", "decision", "reason_codes")} for row in rows]))


if __name__ == "__main__":
    main()
