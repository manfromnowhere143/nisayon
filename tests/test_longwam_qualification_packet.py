"""Meaningful failure controls for the retained full-weight report reader."""

import copy
import hashlib
import importlib.util
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/contributions/longwam-cuda-qualification"
SPEC = importlib.util.spec_from_file_location("longwam_packet_reader", PACKET / "verify_results.py")
assert SPEC is not None and SPEC.loader is not None
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)


def refresh_manifest(root: Path) -> None:
    path = root / "manifest.json"
    manifest = json.loads(path.read_text())
    for relative in manifest["files"]:
        manifest["files"][relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))


def test_retained_packet() -> None:
    result = READER.verify(PACKET)
    assert result["cpu_stage_passed"] == result["direct_setup_errors"] == 14
    assert result["direct_test_bodies_executed"] == 0
    assert result["fresh_model_execution"] is False
    assert result["physical_task_confirmation"] == "not_assessed"


@pytest.mark.parametrize(
    "fault", ["skip", "duplicate", "omission", "wrong_node", "failure", "setup_error"]
)
def test_false_green_junit(tmp_path: Path, fault: str) -> None:
    root = tmp_path / "packet"
    shutil.copytree(PACKET, root, ignore=shutil.ignore_patterns("__pycache__"))
    path = root / "results/cpu-stage-idm-candidate.xml"
    tree = ET.parse(path)
    suite = tree.find("testsuite")
    assert suite is not None
    cases = suite.findall("testcase")
    if fault == "skip":
        ET.SubElement(cases[0], "skipped", message="CUDA unavailable")
    elif fault == "duplicate":
        suite.append(copy.deepcopy(cases[0]))
    elif fault == "omission":
        suite.remove(cases[0])
    elif fault == "wrong_node":
        cases[0].set("name", "unrelated_test")
    elif fault == "failure":
        ET.SubElement(cases[0], "failure", message="wrong action")
    else:
        ET.SubElement(cases[0], "error", message="failed on setup")
    tree.write(path)
    # Rebind file hashes to test semantic rejection rather than digest mismatch.
    refresh_manifest(root)
    with pytest.raises(ValueError, match="Wrong JUnit nodes|Skipped or failed|Wrong case error"):
        READER.verify(root)


@pytest.mark.parametrize("fault", ["matrix", "exit", "source", "weights", "direct_verdict", "vae"])
def test_false_summary(tmp_path: Path, fault: str) -> None:
    root = tmp_path / "packet"
    shutil.copytree(PACKET, root, ignore=shutil.ignore_patterns("__pycache__"))
    path = root / "results/cpu-stage-summary.json"
    summary = json.loads(path.read_text())
    if fault == "matrix":
        summary["outcomes"][1] = copy.deepcopy(summary["outcomes"][0])
    elif fault == "exit":
        summary["outcomes"][0]["returncode"] = 1
    elif fault == "source":
        summary["outcomes"][0]["test_sha256"] = "0" * 64
    elif fault == "weights":
        summary["outcomes"][0]["weights"]["all_serialized_values_exact"] = False
    elif fault == "direct_verdict":
        path = root / "results/direct-summary.json"
        summary = json.loads(path.read_text())
        summary["qualification_complete"] = True
    else:
        (root / "results/idm-original.log").write_text("FULL_VAE_MAX_ABS_ERROR=0.01\n")
    path.write_text(json.dumps(summary))
    refresh_manifest(root)
    with pytest.raises(
        ValueError,
        match="Wrong .*cells|Wrong exit|Wrong source|Inconsistent weight|Wrong direct verdict|Wrong VAE",
    ):
        READER.verify(root)
