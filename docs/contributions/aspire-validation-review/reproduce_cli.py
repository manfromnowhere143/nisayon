"""Exercise native ASPIRE CLI preflight failure with and without prior evidence.

The old successful record is a controlled fixture written by RunRecorder.
No simulator, provider, policy task or robot is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(source / "src"))
    from cap_harness.artifacts import RunRecorder

    rows = []
    for prior_success in (False, True):
        root = output / ("prior_success" if prior_success else "empty")
        root.mkdir()
        program = root / "program.py"
        program.write_text("pass\n", encoding="utf-8")
        validation_output = root / "validation"
        prior = None
        if prior_success:
            recorder = RunRecorder(
                output_root=validation_output / "controlled" / "runs" / "1",
                benchmark="robosuite",
                suite="two_arm_lift",
                task_id=0,
                task_name="controlled fixture, no robot execution",
                seed=1,
                max_steps=10,
                flat_layout=True,
                capture_videos=False,
            )
            recorder.save_program(program)
            recorder.finalize(
                program_ok=True,
                task_success=True,
                termination_reason="task_succeeded",
                program_result=None,
            )
            prior = recorder.root
        before = snapshot(prior) if prior is not None else {}
        # A supported input check raises before a new recorder is constructed.
        # The earlier fixture retains the previous, nonempty program bytes.
        program.write_text("", encoding="utf-8")
        plan = root / "plan.json"
        plan.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "current-attempt-control",
                    "benchmark": "robosuite",
                    "sealed": False,
                    "cases": [
                        {
                            "id": "controlled",
                            "kind": "program",
                            "suite": "two_arm_lift",
                            "task_id": 0,
                            "seeds": [1],
                            "program": str(program),
                            "max_steps": 10,
                            "require": {"program_ok": True, "task_success": True},
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        argv = [
            sys.executable,
            "-B",
            "-m",
            "cap_harness.cli",
            "validate",
            "--plan",
            str(plan),
            "--output-dir",
            str(validation_output),
        ]
        env = dict(os.environ, PYTHONPATH=str(source / "src"), PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run(
            argv, cwd=source, env=env, capture_output=True, text=True, timeout=60, check=False
        )
        (root / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (root / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        summary = json.loads((validation_output / "summary.json").read_text())
        detail = summary["cases"][0]["seeds"][0]["detail"]
        assert (
            completed.stderr.strip()
            == "cap-harness run: program file must contain non-empty Python source"
        )
        assert detail["exit_code"] == 1
        outcomes = list(validation_output.rglob("outcome.json"))
        assert len(outcomes) == int(prior_success)
        unchanged = prior is None or before == snapshot(prior)
        assert unchanged
        rows.append(
            {
                "prior_success": prior_success,
                "argv": argv,
                "cli_exit_code": completed.returncode,
                "child_exit_code": detail["exit_code"],
                "native_success": summary["success"],
                "expected_current_confirmation": False,
                "new_outcomes": 0,
                "prior_files_unchanged": unchanged,
                "summary": summary,
            }
        )
    report = {
        "scope": "Unmodified CLI dispatch and child run preflight. Prior success is fabricated with native RunRecorder. No task execution.",
        "source": str(source),
        "rows": rows,
    }
    (output / "readback.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([{k: row[k] for k in row if k not in {"argv", "summary"}} for row in rows]))


if __name__ == "__main__":
    main()
