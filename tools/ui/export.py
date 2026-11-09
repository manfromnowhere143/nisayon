"""Explicit offline export command; reads the existing simulation environment only."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nisayon.ui_export.exporter import export_d01  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compact",
        type=Path,
        default=ROOT
        / "docs/experiments/results/development-ablation-001/D01-gripper-sign/B/diagnostic/execution/bundle.json.gz",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path(
            "/Users/danielwahnich/workspace/nisayon-codex/artifacts/development-ablation-001/D01-gripper-sign/B/diagnostic/execution"
        ),
    )
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures/ui/d01")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    result = export_d01(
        args.compact, args.raw, args.output, ROOT / "docs/ui/qualification/retained-state.json"
    )
    result["export_wall_s"] = time.monotonic() - started
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
