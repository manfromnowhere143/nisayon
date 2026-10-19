"""Check this retained qualification packet without CUDA, models, or Nisayon.

This is a consistency readback of recorded execution, not an independent model
run, signature, physical result, or general-purpose acceptance mechanism.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_NAMES = {
    "test_full_weight_streaming_vae_matches_window",
    "test_full_weight_async_pending_transition[late_handoff]",
    "test_full_weight_async_pending_transition[reset_pending]",
}
EXTRA_NAME = "test_full_weight_async_pending_transition[reset_pending_changed_observation]"
CELLS = {(family, phase) for family in ("idm", "cod") for phase in ("original", "candidate")}
FIXTURES = {
    ("direct", "original"): (
        "native.py.txt",
        "cc6d4d6c5e09b67a46d347d4624f89a654b263e8fbf238a62b4890aba1675b02",
    ),
    ("direct", "candidate"): (
        "candidate.py.txt",
        "82554ad393fff14ea3842f3d82c347a7c8d9240216a4988b04fbcf2b34772398",
    ),
    ("cpu-stage", "original"): (
        "native-cpu-stage.py.txt",
        "fe5ea25dd337f377da7d3a0ef27f2af8ab7bfa5956da3c1f7ee92755df9f5f34",
    ),
    ("cpu-stage", "candidate"): (
        "candidate-cpu-stage.py.txt",
        "a0d994a5ca8127ed73ce49485ef8e73f632845068b29ce7969103ba6dca4d854",
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def verify(root: Path) -> dict:
    root = root.resolve()
    manifest = read_json(root / "manifest.json")
    present = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.name != "manifest.json"
    }
    require(set(manifest["files"]) == present, "Incomplete file manifest")
    for relative, expected in manifest["files"].items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root), f"Outside packet: {relative}")
        require(digest(path) == expected, f"File identity mismatch: {relative}")
    for name, expected in FIXTURES.values():
        require(digest(root / "fixtures" / name) == expected, f"Unqualified fixture: {name}")

    counts = {"cpu_stage_passed": 0, "direct_setup_errors": 0}
    for loading in ("direct", "cpu-stage"):
        summary = read_json(root / "results" / f"{loading}-summary.json")
        rows = summary["outcomes"]
        require(len(rows) == 4, f"Incomplete {loading} matrix")
        require({(r["family"], r["phase"]) for r in rows} == CELLS, f"Wrong {loading} cells")
        adapted = loading == "cpu-stage"
        require(summary["qualification_complete"] is adapted, f"Wrong {loading} verdict")
        for row in rows:
            family, phase = row["family"], row["phase"]
            names = BASE_NAMES | ({EXTRA_NAME} if phase == "candidate" else set())
            label = f"{loading}-{family}-{phase}"
            require(row["test_sha256"] == FIXTURES[loading, phase][1], f"Wrong source: {label}")
            require(row["qualified"] is adapted, f"Wrong row verdict: {label}")
            require(row["returncode"] == (0 if adapted else 1), f"Wrong exit: {label}")
            require(sorted(row["names"]) == sorted(names), f"Wrong recorded nodes: {label}")
            require(sorted(row["expected_names"]) == sorted(names), f"Wrong allocation: {label}")
            require(
                sorted(row["problems"]) == ([] if adapted else sorted(names)),
                f"Wrong problems: {label}",
            )
            tree = ET.parse(root / "results" / f"{label}.xml")
            suites = tree.findall(".//testsuite")
            require(len(suites) == 1, f"Wrong suite count: {label}")
            suite = suites[0]
            cases = suite.findall("testcase")
            require(
                sorted(c.get("name") for c in cases) == sorted(names), f"Wrong JUnit nodes: {label}"
            )
            for field, expected in {
                "tests": len(names),
                "errors": 0 if adapted else len(names),
                "failures": 0,
                "skipped": 0,
            }.items():
                require(int(suite.get(field, "-1")) == expected, f"Wrong JUnit {field}: {label}")
            for case in cases:
                require(
                    case.get("classname") == "tests.policies.longwam.test_longwam_gpu",
                    f"Wrong class: {label}",
                )
                require(
                    case.find("skipped") is None and case.find("failure") is None,
                    f"Skipped or failed: {label}",
                )
                errors = case.findall("error")
                require(len(errors) == (0 if adapted else 1), f"Wrong case error: {label}")
                if not adapted:
                    message = errors[0].get("message", "")
                    require(
                        message.startswith("failed on setup")
                        and "torch.OutOfMemoryError" in message,
                        f"Wrong setup error: {label}",
                    )
            counts["cpu_stage_passed" if adapted else "direct_setup_errors"] += len(cases)
            if adapted:
                weights = read_json(root / "results" / f"{family}-{phase}.weights.json")
                require(weights == row["weights"], f"Inconsistent weight record: {label}")
                for key, expected in {
                    "strict": True,
                    "all_parameters_cuda": True,
                    "all_serialized_values_exact": True,
                    "serialized_tensors_compared": 2089,
                    "shared_aliases_checked": 3298,
                    "config_device": "cuda",
                    "core_device": "cuda:0",
                    "core_dtype": "torch.bfloat16",
                }.items():
                    require(
                        type(weights[key]) is type(expected) and weights[key] == expected,
                        f"Wrong weight evidence {key}: {label}",
                    )
                log = (root / "results" / f"{family}-{phase}.log").read_text()
                values = re.findall(r"FULL_VAE_MAX_ABS_ERROR=([^\s]+)", log)
                require(
                    len(values) == 1 and float(values[0]) == 0.0, f"Wrong VAE observation: {label}"
                )
    require(counts == {"cpu_stage_passed": 14, "direct_setup_errors": 14}, "Wrong total allocation")
    return {
        "status": "recorded_results_consistent",
        **counts,
        "direct_test_bodies_executed": 0,
        "fresh_model_execution": False,
        "physical_task_confirmation": "not_assessed",
        "owner_savings": "not_assessed",
        "separate_reuse": "not_assessed",
    }


def main() -> int:
    try:
        print(json.dumps(verify(Path(__file__).parent), indent=2))
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as exc:
        print(f"Unqualified retained packet: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
