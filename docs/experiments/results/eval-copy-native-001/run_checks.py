"""Run this retained regression against an installed, explicit LeRobot tree."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    tests = Path(__file__).resolve().parent
    started = time.monotonic()

    import pytest
    import torch
    from lerobot.policies import pretrained
    from lerobot.processor import converters, pipeline, relative_action_processor
    from lerobot.scripts import lerobot_eval

    modules = {}
    for module in (pretrained, converters, pipeline, relative_action_processor, lerobot_eval):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(source), (path, source)
        modules[module.__name__] = {
            "path": str(path.relative_to(source)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    record = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "source": str(source),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "torch_default_device": str(torch.empty(0).device),
        "modules": modules,
        "distributions": sorted(
            (dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions()
        ),
        "environment": {
            key: os.environ.get(key)
            for key in ("PYTHONPATH", "HF_HOME", "HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE")
        },
    }
    arguments = [
        "-c",
        str(source / "pyproject.toml"),
        "-p",
        "no:cacheprovider",
        "--timeout=60",
        "-ra",
        str(source / "tests/scripts/test_lerobot_eval.py"),
        str(tests / "test_linked_processors.py"),
        str(tests / "test_native_rollout.py"),
        f"--junitxml={output.with_suffix('.xml')}",
    ]
    record["pytest_arguments"] = arguments
    code = pytest.main(arguments)
    record["exit_code"] = int(code)
    record["wall_seconds"] = time.monotonic() - started
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
