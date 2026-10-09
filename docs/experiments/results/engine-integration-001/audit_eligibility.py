"""Run labelled evaluation fixtures through the public CLI, retaining full reports."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.evaluation.prospective_fixtures import (
    PROSPECTIVE_SCENARIOS,
    prospective_ledger,
    write_prospective_ledger,
)

SCENARIOS = (
    "prospective_fair",
    "all_abstain",
    "missing_assigned_case",
    "terminal_binding_broken",
    "reference_missing",
    "reference_corrupt",
    "unsupported_acceptance_invalid",
    "partial_costs",
)


def audit(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    controls = []
    for name in (*SCENARIOS, "over_budget_supported"):
        folder = out / name
        if name == "over_budget_supported":
            ledger = prospective_ledger()
            trial = next(
                t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D07")
            )
            trial["diagnostic_rollouts"] = 99
            ledger_path = write_prospective_ledger(ledger, folder)
        else:
            scenario = next(s for s in PROSPECTIVE_SCENARIOS if s.name == name)
            ledger_path = write_prospective_ledger(scenario.build(), folder)
            if scenario.after_write is not None:
                scenario.after_write(folder)
        report_path = folder / "report.json"
        command = [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "prospective",
            str(ledger_path),
            "--root",
            str(folder),
            "--out",
            str(report_path),
        ]
        process = subprocess.run(command, capture_output=True, check=False, timeout=30)
        (folder / "stdout.log").write_bytes(process.stdout)
        (folder / "stderr.log").write_bytes(process.stderr)
        assert process.returncode in (0, 1), (name, process.stderr.decode())
        report = json.loads(report_path.read_text())
        assert len(report["trials"]) == 8, name
        assert all(arm["assigned_cases"] == 4 for arm in report["arms"].values()), name
        controls.append(
            {
                "name": name,
                "command": command,
                "returncode": process.returncode,
                "report_sha256": file_digest(report_path),
                "fair": report["fair"],
                "report_eligibility": {
                    k: v for k, v in report.items() if "eligib" in k or "validity" in k
                },
                "arms": report["arms"],
                "declarations": report["declarations"],
                "findings": report["findings"],
            }
        )
    result = {
        "schema": "nisayon.integration-eligibility-readback.v1",
        "scope": (
            "Labelled synthetic development controls from the evaluation owner's fixtures, "
            "consumed through the public CLI. No physics or model calls; not effectiveness "
            "evidence. Reference correctness, study validity and product eligibility are "
            "inspected separately; every assigned case must remain visible."
        ),
        "controls": controls,
    }
    write_json(out / "summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.out)
    print(
        json.dumps(
            [
                {
                    "name": c["name"],
                    "fair": c["fair"],
                    "report_eligibility": c["report_eligibility"],
                    "product_accepted": {
                        arm: d["product_accepted"] for arm, d in c["arms"].items()
                    },
                }
                for c in result["controls"]
            ],
            indent=2,
        )
    )
