"""Run native checks with explicit implementation and upstream-test source trees."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--upstream-tests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=["upstream", "contract"], required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    upstream = args.upstream_tests.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    record = {
        "started_at": datetime.now(UTC).isoformat(),
        "source": str(source),
        "upstream_tests": str(upstream),
        "group": args.group,
        "python": sys.version,
        "platform": platform.platform(),
        "distributions": sorted(
            (dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions()
        ),
    }

    import gymnasium
    import pytest
    import torch
    from lerobot.envs import configs, utils
    from lerobot.processor import pipeline, relative_action_processor
    from lerobot.scripts import lerobot_eval

    record["cpu"] = str(torch.empty(0).device)
    record["modules"] = {}
    for module in (configs, utils, pipeline, relative_action_processor, lerobot_eval):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(source), (path, source)
        record["modules"][module.__name__] = {
            "path": str(path.relative_to(source)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    record["gymnasium_version"] = gymnasium.__version__
    if args.group == "upstream":
        tests = [
            str(upstream / "tests/scripts/test_lerobot_eval.py"),
            str(upstream / "tests/envs/test_freeze_after_episode_end.py"),
            str(upstream / "tests/envs/test_envs.py")
            + "::test_create_envs_async_registers_env_in_workers",
            str(upstream / "tests/envs/test_envs.py")
            + "::test_sub_env_has_attr_keeps_async_workers_alive",
        ]
    else:
        tests = [str(Path(__file__).with_name("test_episode_contract.py").resolve())]
    record["test_files"] = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in {Path(test.split("::")[0]) for test in tests}
    }
    arguments = [
        "-c",
        str(upstream / "pyproject.toml"),
        "-p",
        "no:cacheprovider",
        "--timeout=40",
        "-q",
        "-ra",
        *tests,
        f"--junitxml={output.with_suffix('.xml')}",
    ]
    record["pytest_arguments"] = arguments
    code = pytest.main(arguments)
    record["exit_code"] = int(code)
    record["wall_seconds"] = time.monotonic() - started
    if output.with_suffix(".xml").exists():
        junit = ET.parse(output.with_suffix(".xml")).getroot()
        record["suites"] = [element.attrib for element in junit.findall("testsuite")]
        record["cases"] = [
            {
                **case.attrib,
                "status": (
                    "failed"
                    if case.find("failure") is not None
                    else "error"
                    if case.find("error") is not None
                    else "skipped"
                    if case.find("skipped") is not None
                    else "passed"
                ),
            }
            for case in junit.iter("testcase")
        ]
    output.write_text(json.dumps(record, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
