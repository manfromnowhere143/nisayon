"""Export the six admitted recorded cases; no new simulation or evaluation."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nisayon.ui_export.bytes import canonical  # noqa: E402
from nisayon.ui_export.contract import DOCUMENT  # noqa: E402
from nisayon.ui_export.library import CASES, export_case  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument(
        "--compact-root",
        type=Path,
        default=ROOT / "docs/experiments/results/development-ablation-001",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path(
            "/Users/danielwahnich/workspace/nisayon-codex/artifacts/development-ablation-001"
        ),
    )
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures/ui/recorded")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    reports = []
    for case_id in args.case or CASES:
        started = time.monotonic()
        report = export_case(
            args.compact_root,
            args.raw_root,
            args.output / case_id,
            ROOT / "docs/ui/qualification/retained-state.json",
            case_id,
        )
        report["export_wall_s"] = time.monotonic() - started
        reports.append(report)
        print(
            json.dumps({key: value for key, value in report.items() if key != "runs"}), flush=True
        )
    index = {
        "schema": "nisayon.ui-library.v1",
        "default_case_key": reports[0]["case_key"],
        "cases": [
            {
                "case_key": report["case_key"],
                "case_id": report["case_key"].split("/")[1],
                "directory": report["case_key"].split("/")[1],
                "manifest": report["manifest"],
            }
            for report in reports
        ],
    }
    DOCUMENT.validate_python(index, strict=True)
    temporary = args.output / "library.json.tmp"
    temporary.write_bytes(canonical(index) + b"\n")
    temporary.replace(args.output / "library.json")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps({"schema": "nisayon.ui-library-export.v1", "cases": reports}, indent=2)
            + "\n"
        )


if __name__ == "__main__":
    main()
