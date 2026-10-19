"""Check attempt freshness with ASPIRE's native sealed-run test fixture.

The fixture's three-byte video files are fabricated test data, not robot evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(source / "src"))
    from cap_harness.validation.model import ValidationCase, ValidationPlan
    from cap_harness.validation.runner import _run_program_case

    spec = importlib.util.spec_from_file_location(
        "native_fixture", source / "tests/test_validation_sealing.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    program = output / "program.py"
    program.write_text("pass\n", encoding="utf-8")
    program_sha = hashlib.sha256(program.read_bytes()).hexdigest()

    def write_evidence(root: Path) -> Path:
        run_dir = fixture._good_run(root, max_steps=3000)
        path = run_dir / "source/provenance.json"
        provenance = json.loads(path.read_text())
        provenance["sha256"] = program_sha
        path.write_text(json.dumps(provenance), encoding="utf-8")
        return run_dir

    records = []
    for sealed in (False, True):
        for name, old_evidence, fresh_evidence, exit_code in (
            ("fresh_success", False, True, 0),
            ("fresh_success_teardown", False, True, 139),
            ("empty_zero_exit", False, False, 0),
            ("empty_failure", False, False, 1),
            ("stale_zero_exit", True, False, 0),
            ("stale_failure", True, False, 1),
        ):
            destination = output / ("sealed" if sealed else "unsealed") / name
            case = ValidationCase(
                id="controlled",
                kind="program",
                seeds=(1,),
                suite="two_arm_lift",
                program=str(program),
                max_steps=3000,
                require={"program_ok": True, "task_success": True, "evaluator_success": True},
            )
            plan = ValidationPlan(
                schema_version=1,
                name="current-attempt-control",
                benchmark="robosuite",
                cases=(case,),
                sealed=sealed,
            )
            old = None
            before = {}
            if old_evidence:
                old = write_evidence(destination / case.id / "runs/1")
                before = {str(p): p.read_bytes() for p in old.rglob("*") if p.is_file()}

            def command(argv, env, fresh_evidence=fresh_evidence, exit_code=exit_code):
                if fresh_evidence:
                    write_evidence(Path(argv[argv.index("--output-root") + 1]))
                return subprocess.run(
                    [sys.executable, "-c", f"raise SystemExit({exit_code})"],
                    env=env,
                    check=False,
                ).returncode

            seal = (
                {
                    "commit": fixture.COMMIT,
                    "dependency_lock_sha256": fixture.LOCK_SHA,
                    "environment_sha256": fixture.ENV_SHA,
                }
                if sealed
                else None
            )
            result = _run_program_case(
                plan,
                case,
                destination,
                repo_root=source,
                run_command=command,
                base_env=dict(os.environ),
                seal=seal,
            )
            assert all(Path(path).read_bytes() == data for path, data in before.items())
            records.append(
                {
                    "sealed": sealed,
                    "scenario": name,
                    "expected_pass": fresh_evidence,
                    "observed_pass": result.passed,
                    "exit_code": exit_code,
                    "prior_files_unchanged": True,
                    "result": result.to_dict(),
                }
            )
    (output / "readback.json").write_text(
        json.dumps({"records": records}, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": len(records),
                "agree": sum(r["expected_pass"] == r["observed_pass"] for r in records),
            }
        )
    )


if __name__ == "__main__":
    main()
