"""Fill plan.v2.json's bindings and freeze time from the files as they are now."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(commit: str, path: str) -> str:
    data = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str]) -> int:
    plan_path = HERE / "plan.v2.json"
    plan = json.loads(plan_path.read_text())
    execution_commit = argv[1] if len(argv) > 1 else "62bb2dab174b737a6d02573b131b2c59f1d88812"
    site = (
        Path(sys.prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    plan["bindings"] = {
        "evaluation_commit_at_start": "e93cdc59e71e5de835aedbfbb0fd8c587bfe4571",
        "scorer": {
            "path": "docs/evaluation/results/decision-case-001/score_probe_pairs.py",
            "sha256": sha(HERE / "score_probe_pairs.py"),
        },
        "controls_generator": {
            "path": "docs/evaluation/results/decision-case-001/probe_pair_controls.py",
            "sha256": sha(HERE / "probe_pair_controls.py"),
        },
        "original_plan": {
            "path": "docs/evaluation/results/decision-case-001/plan.json",
            "sha256": sha(HERE / "plan.json"),
        },
        "execution_commit_bound": execution_commit,
        "execution_lane_files_at_bound_commit": {
            path: git_blob(execution_commit, path)
            for path in (
                "docs/experiments/results/decision-case-001/allocation.json",
                "src/nisayon/engine/lift.py",
                "src/nisayon/engine/configuration.py",
                "src/nisayon/engine/diagnostics.py",
                "src/nisayon/engine/records.py",
                "scripts/experiments/controller_target_probe.py",
            )
        },
        "installed_sources": {
            "robosuite/models/robots/manipulators/panda_robot.py": sha(
                site / "robosuite/models/robots/manipulators/panda_robot.py"
            ),
            "robosuite/controllers/osc.py": sha(site / "robosuite/controllers/osc.py"),
        },
        "evaluation_machinery": {
            "src/nisayon/evaluation/first_case.py": sha(
                ROOT / "src/nisayon/evaluation/first_case.py"
            ),
        },
    }
    plan["frozen_at"] = datetime.now(UTC).isoformat()
    plan_path.write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "frozen_at": plan["frozen_at"],
                "scorer_sha256": plan["bindings"]["scorer"]["sha256"],
                "plan_sha256": sha(plan_path),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
