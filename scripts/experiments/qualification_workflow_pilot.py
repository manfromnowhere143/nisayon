"""Exercise an installed CLI outside Git on five exposed software controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


def save(path: Path, value: object) -> None:
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.absolute()
    root.mkdir(parents=True, exist_ok=False)
    cli = str(args.cli.absolute())
    review_cli = str(args.cli.absolute().with_name("nisayon-qualify"))
    started = time.perf_counter()
    commands = []

    def command(argv: list[str]) -> subprocess.CompletedProcess:
        remaining = 120 - (time.perf_counter() - started)
        if remaining <= 0:
            raise TimeoutError("Pilot budget exhausted; retain the prefix")
        index = len(commands)
        before = time.perf_counter()
        process = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, timeout=remaining, check=False
        )
        (root / f"{index:02d}-stdout.txt").write_text(process.stdout)
        (root / f"{index:02d}-stderr.txt").write_text(process.stderr)
        commands.append(
            {
                "argv": argv,
                "returncode": process.returncode,
                "wall_seconds": time.perf_counter() - before,
            }
        )
        save(root / f"{index:02d}-command.json", commands[-1])
        return process

    rows = []
    for name, expected, code in [
        ("good", "adopt", 0),
        ("bad", "reject", 1),
        ("unknown", "unresolved", 3),
        ("crash", "unresolved", 3),
        ("timeout", "unresolved", 3),
    ]:
        owner = root / (name + "-owner")
        created = command([review_cli, "example", str(owner)])
        if created.returncode:
            raise RuntimeError("Example creation failed; inspect retained command")
        case_path = owner / "case.json"
        case = json.loads(case_path.read_text())
        if name == "bad":
            case["targets"]["candidate"]["callable"] = "wrong_sign"
        elif name == "unknown":
            case["premises"]["environment"] = None
        elif name in {"crash", "timeout"}:
            case["targets"]["candidate"]["callable"] = "adverse"
            source = owner / "policy.py"
            behavior = (
                '    raise RuntimeError("exposed native failure")\n'
                if name == "crash"
                else "    import time\n    time.sleep(30)\n    return result\n"
            )
            source.write_text(
                source.read_text()
                + "\ndef adverse(value):\n"
                + "    result = normalize(value)\n"
                + behavior
            )
        case_path.write_text(json.dumps(case, indent=2) + "\n")
        output = root / name
        process = command(
            [
                cli,
                "qualify",
                str(case_path),
                "--project",
                str(owner),
                "--out",
                str(output),
                "--timeout",
                "2",
                "--total-seconds",
                "15",
            ]
        )
        result = json.loads(process.stdout)
        inspected = command([review_cli, "inspect", str(output / "run")])
        reviewed = command([review_cli, "review", str(output / "review.nisayon.zip")])
        assessment = json.loads(inspected.stdout)
        review = json.loads(reviewed.stdout)
        records = [
            json.loads(p.read_text()) for p in sorted((output / "run").glob("*/record.json"))
        ]
        passed = (
            process.returncode == inspected.returncode == reviewed.returncode == code
            and result["software_decision"]
            == assessment["software_decision"]
            == review["software_decision"]
            == expected
            and result["deployment_decision"] == "unresolved"
            and review["review_status"] == "verified"
            and len(records) == (0 if name == "unknown" else 5 if name == "timeout" else 6)
            and (
                name != "timeout"
                or (
                    sum(r["status"] == "completed" for r in records) == 4
                    and sum(r["error"] == "timeout" for r in records) == 1
                    and not (output / "run/candidate-fractional/intent.json").exists()
                )
            )
        )
        rows.append(
            {
                "case": name,
                "expected": expected,
                "observed": result["software_decision"],
                "deployment_decision": result["deployment_decision"],
                "passed": passed,
                "attempts": len(records),
                "statuses": [r["status"] for r in records],
                "costs": result["costs"],
                "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
                "plan_sha256": result["plan_sha256"],
                "bundle_sha256": result["bundle_sha256"],
            }
        )
        save(root / (name + "-result.json"), rows[-1])
        if not passed:
            raise RuntimeError("Frozen engineering outcome failed; stop without retry")
    save(
        root / "pilot.json",
        {
            "cases": rows,
            "commands": commands,
            "wall_seconds": time.perf_counter() - started,
            "scientific_result": "INCONCLUSIVE",
            "scope": "Exposed software controls; no independent incident, robot, economic advantage or deployment acceptance.",
        },
    )
    print(
        json.dumps(
            {
                "output": str(root),
                "cases_passed": sum(r["passed"] for r in rows),
                "cases": len(rows),
                "attempts": sum(r["attempts"] for r in rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
