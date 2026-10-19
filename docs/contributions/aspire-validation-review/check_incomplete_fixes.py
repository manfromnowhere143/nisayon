"""Run the same controls against two deliberately incomplete freshness fixes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    test = Path(__file__).with_name("test_validation_attempts.py")
    report = {}
    for name in ("exit_code_only", "new_outcome_paths_only"):
        root = output / name
        shutil.copytree(source / "src", root / "src")
        path = root / "src/cap_harness/validation/runner.py"
        original = path.read_text(encoding="utf-8")
        discovery = "        run_dir = _find_run_dir(seed_root)\n"
        assert original.count(discovery) == 1
        if name == "exit_code_only":
            changed = original.replace(
                discovery, "        run_dir = _find_run_dir(seed_root) if code == 0 else None\n"
            )
        else:
            invoke = "        code = run_command(argv, env)\n"
            assert original.count(invoke) == 1
            changed = original.replace(
                invoke,
                '        previous = set(seed_root.rglob("outcome.json"))\n' + invoke,
            ).replace(
                discovery,
                '        current = sorted(set(seed_root.rglob("outcome.json")) - previous)\n'
                "        run_dir = current[-1].parent if current else None\n",
            )
        path.write_text(changed, encoding="utf-8")
        xml = root / "results.xml"
        argv = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-c",
            "/dev/null",
            str(test),
            f"--junitxml={xml}",
        ]
        result = subprocess.run(
            argv,
            cwd=root,
            env=dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        (root / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (root / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        assert result.returncode == 1
        cases = list(ET.parse(xml).iter("testcase"))
        assert not any(case.find("error") is not None for case in cases)
        assert not any(case.find("skipped") is not None for case in cases)
        report[name] = {
            "tests": len(cases),
            "failed": [case.attrib["name"] for case in cases if case.find("failure") is not None],
        }
    (output / "readback.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
