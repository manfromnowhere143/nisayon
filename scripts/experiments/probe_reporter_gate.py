"""Exercise a pinned external reporter through its installed CLI on frozen controls.

These LeRobot-format inputs are constructed software fixtures, not robot trials.
The caller supplies the isolated environment and the pre-execution protocol.
Every comparison, gate result and process outcome is retained without retries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_run(directory: Path, labels: list[bool | None]) -> None:
    directory.mkdir()
    write_json(
        directory / "eval_info.json",
        {
            "per_episode": [
                {"episode_ix": i, "seed": 100 + i, "success": value}
                for i, value in enumerate(labels)
            ],
            "aggregated": {"n_episodes": len(labels)},
        },
    )
    write_json(
        directory / "run_meta.json",
        {
            "task": "constructed-label-coverage-control",
            "environment": "software-fixture",
            "environment_version": "1",
            "embodiment": "none",
            "run_kind": "constructed_software_control",
            "source_experiment": "nisayon-reporter-gate-001",
        },
    )


def command(argv: list[str], directory: Path, name: str) -> dict:
    # The released CLI requires explicit consent as well as an environment flag.
    # This experiment uses its local evaluate/gate commands only.
    env = {**os.environ, "ARISOLE_TELEMETRY": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONPATH", None)
    started = datetime.now(UTC).isoformat()
    before = time.perf_counter()
    result = subprocess.run(argv, capture_output=True, timeout=30, cwd=directory, env=env)
    wall = time.perf_counter() - before
    for stream in ("stdout", "stderr"):
        (directory / f"{name}.{stream}.txt").write_bytes(getattr(result, stream))
    return {
        "argv": argv,
        "started_at": started,
        "returncode": result.returncode,
        "wall_seconds": wall,
        "stdout_sha256": sha256(directory / f"{name}.stdout.txt"),
        "stderr_sha256": sha256(directory / f"{name}.stderr.txt"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    # Resolve the venv directory, not its Python symlink, to preserve isolation.
    python = str(args.python.absolute())
    protocol = json.loads(args.protocol.read_bytes())
    out = args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": "nisayon.reporter-gate.probe.v1",
        "started_at": datetime.now(UTC).isoformat(),
        "protocol_sha256": sha256(args.protocol),
        "script_sha256": sha256(Path(__file__)),
        "scope": "Constructed software controls; no robot, model or task execution",
        "cases": [],
    }
    identity_code = (
        "import hashlib,importlib.metadata,json,pathlib,sys; import arisole_eval; "
        "p=pathlib.Path(arisole_eval.__file__).parent; "
        "print(json.dumps({'version':arisole_eval.__version__, 'package_path':str(p), "
        "'python':sys.version, 'executable':sys.executable, "
        "'packages':dict(sorted((d.metadata['Name'],d.version) "
        "for d in importlib.metadata.distributions())), "
        "'source_sha256':{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() "
        "for f in sorted(p.rglob('*.py'))}}))"
    )
    identity = command([python, "-c", identity_code], out, "identity")
    receipt["identity_command"] = identity
    if identity["returncode"]:
        write_json(out / "result.json", receipt)
        return 2
    receipt["runtime"] = json.loads((out / "identity.stdout.txt").read_bytes())
    if receipt["runtime"]["version"] != protocol["version"]:
        raise ValueError("Installed reporter version differs from frozen protocol")
    for case in protocol["cases"]:
        directory = out / case["id"]
        directory.mkdir()
        for arm in ("baseline", "candidate"):
            write_run(directory / arm, case[arm])
        inputs = {
            str(path.relative_to(directory)): sha256(path)
            for arm in ("baseline", "candidate")
            for path in sorted((directory / arm).glob("*.json"))
        }
        comparison = directory / "comparison.json"
        evaluate = command(
            [
                python,
                "-m",
                "arisole_eval",
                "evaluate",
                "--baseline",
                str(directory / "baseline"),
                "--candidate",
                str(directory / "candidate"),
                "--out",
                str(comparison),
            ],
            directory,
            "evaluate",
        )
        row = {"id": case["id"], "input_sha256": inputs, "evaluate": evaluate}
        if evaluate["returncode"] == 0 and comparison.is_file():
            gate = command(
                [
                    python,
                    "-m",
                    "arisole_eval",
                    "gate",
                    str(comparison),
                    "--out-json",
                    str(directory / "gate.json"),
                    "--out-md",
                    str(directory / "gate.md"),
                ],
                directory,
                "gate",
            )
            row["gate_command"] = gate
            if (directory / "gate.json").is_file():
                gate_result = json.loads((directory / "gate.json").read_bytes())["gate"]
                result = json.loads(comparison.read_bytes())
                known_pairs = sum(
                    type(b) is bool and type(c) is bool
                    for b, c in zip(case["baseline"], case["candidate"], strict=True)
                )
                known_regressions = sum(
                    b is True and c is False
                    for b, c in zip(case["baseline"], case["candidate"], strict=True)
                )
                rate = next(
                    (
                        reason["observed"]
                        for reason in gate_result["reasons"]
                        if reason["rule"] == "pass_to_fail_rate"
                    ),
                    None,
                )
                expected_rate = known_regressions / known_pairs if known_pairs else None
                row.update(
                    summary=result.get("summary"),
                    observed_outcome=gate_result["outcome"],
                    expected_outcome=case["expected_outcome"],
                    expected_exit=case["expected_exit"],
                    known_labelled_pairs=known_pairs,
                    missing_label_pairs=len(case["baseline"]) - known_pairs,
                    known_regressions=known_regressions,
                    gate_reported_regression_rate=rate,
                    known_labelled_regression_rate=expected_rate,
                    input_unchanged=all(
                        sha256(directory / path) == value for path, value in inputs.items()
                    ),
                )
                row["contract_passed"] = (
                    gate_result["outcome"] == case["expected_outcome"]
                    and gate["returncode"] == case["expected_exit"]
                    and row["input_unchanged"]
                    and (rate is None or rate == expected_rate)
                )
        receipt["cases"].append(row)
        write_json(out / "result.json", receipt)
    receipt["completed_at"] = datetime.now(UTC).isoformat()
    receipt["passed"] = sum(row.get("contract_passed", False) for row in receipt["cases"])
    receipt["failed_or_invalid"] = len(receipt["cases"]) - receipt["passed"]
    write_json(out / "result.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("passed", "failed_or_invalid")}))
    return 0 if receipt["failed_or_invalid"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
