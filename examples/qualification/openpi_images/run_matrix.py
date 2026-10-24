"""Run frozen CPU image checks and retain every arm, including failures."""

import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
ARMS = ROOT / "artifacts/openpi/arms"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(manifests):
    for arm, files in manifests.items():
        for name, expected in files.items():
            assert sha256(ARMS / arm / name) == expected, f"Source changed: {arm}/{name}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--shape-only", action="store_true")
    args = parser.parse_args()
    destination = PACKET / (f"seed-{args.seed}" + ("-shape-only" if args.shape_only else ""))
    destination.mkdir(exist_ok=False)
    source = json.loads((PACKET / "source-identities.json").read_text())
    frozen = json.loads((PACKET / "probe-freeze.json").read_text())
    for name, expected in frozen["files"].items():
        assert sha256(PACKET / name) == expected, f"Frozen probe changed: {name}"
    verify(source["source_files_sha256"])
    environment = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
    }
    (destination / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    arms = (
        ["bad_reshape"]
        if args.shape_only
        else ["base", "pr1016", "pr1050", "combined", "bad_reshape"]
    )
    results = []
    for arm in arms:
        directory = destination / arm
        directory.mkdir()
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            str(PACKET / "test_image_contract.py"),
            str(ARMS / arm / "src/openpi/shared/image_tools_test.py"),
            "--junitxml",
            str(directory / "tests.xml"),
        ]
        env = dict(
            os.environ,
            PYTHONPATH=str(ARMS / arm / "src"),
            PYTHONDONTWRITEBYTECODE="1",
            NISAYON_INPUT_SEED=str(args.seed),
            NISAYON_SHAPE_ONLY="1" if args.shape_only else "0",
            JAX_PLATFORMS="cpu",
            CUDA_VISIBLE_DEVICES="",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
        )
        record = {
            "arm": arm,
            "seed": args.seed,
            "shape_only": args.shape_only,
            "command": command,
            "cwd": str(ARMS / arm),
            "started_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "status": "running",
        }
        (directory / "command.json").write_text(json.dumps(record, indent=2) + "\n")
        started = time.monotonic()
        with (
            (directory / "stdout.log").open("w") as out,
            (directory / "stderr.log").open("w") as err,
        ):
            result = subprocess.run(
                command, cwd=ARMS / arm, env=env, stdout=out, stderr=err, timeout=180
            )
        record.update(
            returncode=result.returncode,
            wall_seconds=time.monotonic() - started,
            ended_at=datetime.datetime.now(datetime.UTC).isoformat(),
            status="completed",
        )
        xml_path = directory / "tests.xml"
        if xml_path.exists():
            cases = ET.parse(xml_path).findall(".//testcase")
            record["counts"] = {
                "tests": len(cases),
                "failed": sum(c.find("failure") is not None for c in cases),
                "errors": sum(c.find("error") is not None for c in cases),
                "skipped": sum(c.find("skipped") is not None for c in cases),
            }
        (directory / "command.json").write_text(json.dumps(record, indent=2) + "\n")
        results.append(record)
        print(
            json.dumps(
                {
                    k: record.get(k)
                    for k in ("arm", "seed", "shape_only", "returncode", "wall_seconds", "counts")
                }
            ),
            flush=True,
        )
        if result.returncode not in (0, 1):
            raise SystemExit(f"Harness/collection error in {arm}; preserve results and investigate")
    verify(source["source_files_sha256"])
    (destination / "summary.json").write_text(
        json.dumps({"source_unchanged": True, "results": results}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
