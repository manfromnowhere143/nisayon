"""Two labelled synthetic controls through the public scorer; no robot or real trial."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from nisayon.evaluation.prospective_fixtures import required_field_omission_control


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    summaries = []
    for variant in ("positive", "start_observed_absent"):
        folder = args.out / variant
        ledger = required_field_omission_control(folder, variant=variant)
        command = [sys.executable, "-m", "nisayon.evaluation", "prospective", str(ledger), "--json"]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        (folder / "stdout.json").write_text(result.stdout)
        (folder / "stderr.txt").write_text(result.stderr)
        report = json.loads(result.stdout)
        trial = next(
            t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01")
        )
        positive = variant == "positive"
        assert result.returncode == (0 if positive else 1)
        assert report["fair"] is positive
        assert len(report["trials"]) == 8
        assert trial["reference"]["decision"] == "accepted"
        assert trial["prospective"] is positive
        summaries.append(
            {
                "fixture": variant,
                "synthetic": True,
                "exit": result.returncode,
                "study_usable": report["eligibility"]["usable_as_study_result"],
                "assignments_retained": len(report["trials"]),
                "reference_decision": trial["reference"]["decision"],
                "findings": sorted({f["code"] for f in report["findings"]}),
            }
        )
    (args.out / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
