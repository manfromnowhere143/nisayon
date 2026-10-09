"""Replay the coordinator's six cancellation probes through the public evaluator.

The variants are the coordinator's (nisayon-opus-reuse-evaluation-2026-09-19-8tvvohgc):
a valid stop, a violation run id that names no assigned run, a cancellation recorded
before the freeze, an unknown cancelled condition, a duplicate cancelled condition, and a
present non-object cancellation. Each is a labelled synthetic strict bundle built from the
test suite's own fixture; none is a robot trial. Outputs are retained beside this script.

Usage: probe_cancellation.py OUT_DIR
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / "tests" / "evaluation"))

from test_evaluation_cancellation import STOP, decide, document  # noqa: E402


def variants() -> dict:
    return {
        "valid_stop_control": copy.deepcopy(STOP),
        "wrong_violation_run_id": {
            **copy.deepcopy(STOP),
            "violation": {**STOP["violation"], "run_id": "not-an-assigned-run"},
        },
        "cancellation_before_freeze": {
            **copy.deepcopy(STOP),
            "recorded_at": "2026-09-16T00:00:00+00:00",
        },
        "unknown_cancelled_condition": {
            **copy.deepcopy(STOP),
            "cancelled_condition_ids": [*STOP["cancelled_condition_ids"], "not-assigned"],
        },
        "duplicate_cancelled_condition": {
            **copy.deepcopy(STOP),
            "cancelled_condition_ids": [
                *STOP["cancelled_condition_ids"],
                STOP["cancelled_condition_ids"][0],
            ],
        },
        "malformed_present_cancellation": "not-an-object",
    }


def main(argv: list[str]) -> int:
    out = Path(argv[1])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    started = time.perf_counter()
    rows = []
    for name, cancellation in variants().items():
        doc, protocol = document(
            candidate_fails={"seed-1001"},
            drop={"seed-1002", "seed-1003"},
            cancellation=cancellation,
        )
        decision = decide(doc, protocol, out / "inputs" / name)
        confirmation = decision.get("confirmation") or {}
        rows.append(
            {
                "variant": name,
                "decision": decision["decision"],
                "codes": sorted({r["code"] for r in decision["reasons"]}),
                "reason_details": sorted(
                    {f"{r['code']}: {r['detail'][:160]}" for r in decision["reasons"]}
                ),
                "confirmation_findings": sorted(
                    {f["code"] for f in confirmation.get("findings") or []}
                ),
                "cancellation": confirmation.get("cancellation"),
                "summary": confirmation.get("summary"),
            }
        )
    result = {
        "schema": "nisayon.cancellation-probes.v1",
        "source": head,
        "kind": "labelled synthetic metadata-conformance probes on the test fixture; not robot trials, not false-repair-acceptance evidence",
        "command_wall_s": round(time.perf_counter() - started, 6),
        "rows": rows,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "probes.json").write_text(json.dumps(result, indent=2) + "\n")
    for row in rows:
        print(
            f"{row['variant']}: {row['decision']} {row['codes']} findings {row['confirmation_findings']} "
            f"cancelled {row['summary']['fresh_cancelled'] if row['summary'] else None}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
