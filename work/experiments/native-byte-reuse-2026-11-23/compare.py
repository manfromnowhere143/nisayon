"""Matched exposed scalar controls; existing native selection and portable review.

No external code, hardware or network execution. The native arm receives the
same initial observation (no cached score), inputs and fresh confirmation scope.
Timers include setup, validation and review; human effort remains unmeasured.
"""

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

PACKET = Path(__file__).resolve().parent
REPO = PACKET.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


case = load("byte_case", REPO / "tests/qualification/test_reused_native_bytes.py")
native = load(
    "native_comparator",
    REPO / "work/experiments/native-comparator-review-2026-11-09/native_calibration.py",
)
selector = load("native_selector", REPO / "examples/qualification/applicability/native_selector.py")


def sdk_cell(root, variant):
    start = time.perf_counter()
    shared, inputs, prior, raw = case.prepare(root / "evidence")
    evidence = shared["evidence_root"]
    current = case.next_inputs(
        evidence,
        inputs,
        tolerance=0.001 if variant == "scoring" else 0.01,
        center=11 if variant == "calibration" else None,
    )
    setup = time.perf_counter() - start
    execution_start = time.perf_counter()
    result = case.execute_checks(**shared, inputs=current, previous=prior, output=evidence / "next")
    execution = time.perf_counter() - execution_start
    review_start = time.perf_counter()
    decision, review_status, error = "unresolved", "not_completed", None
    try:
        reviewed = case.inspect_checks(evidence_root=evidence, output=evidence / "next")
        case.export_checks(
            evidence_root=evidence, execution=evidence / "next", output=root / "review.zip"
        )
        portable = case.inspect_check_bundle(root / "review.zip")
        assert portable["review_status"] == "verified"
        decision = reviewed["artifacts"]["review"]["software_decision"]
        assert reviewed["artifacts"]["confirm"]["observation"]["position"] == 26
        review_status = "verified"
    except ValueError as exc:
        error = str(exc)
    return {
        "execution": result["status"],
        "decision": decision,
        "review": review_status,
        "error": error,
        "actions": {r["check"]: r["action"] for r in result["attempts"]},
        "producer_bytes_preserved": (evidence / "next/checks/observe/result.json").read_bytes()
        == raw,
        "input_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in current.items()},
        "setup_seconds": setup,
        "execute_seconds": execution,
        "review_seconds": time.perf_counter() - review_start,
        "total_seconds": time.perf_counter() - start,
        "initial_executed_checks": 4,
        "new_executed_checks": sum(r["action"] == "run" for r in result["attempts"]),
        "human_review_seconds": None,
    }


def native_cell(root, variant):
    start = time.perf_counter()
    source = root / "inputs"
    source.mkdir(parents=True)
    # Same source writer/bytes as the SDK fixture; no SDK planner in selection.
    calibration = source / "calibration.json"
    admission = source / "admission.json"
    case.write_json(calibration, {"center": 10})
    case.write_json(
        admission,
        {
            "schema": "nisayon.example.calibration_admission.v1",
            "resource": "calibration",
            "sha256": case.file_digest(calibration),
            "provenance": "authored scalar regression; no physical measurement",
            "permitted_use": case.calibration.PURPOSE,
            "consumption": "check_context_snapshot",
            "export_contents": True,
        },
    )
    inputs = case.calibration.bindings(source, "initial", calibration, admission)
    history = []
    kwargs = {
        "policy": case.calibration.calibration_policy,
        "runtime": case.calibration.runtime_identity(),
        "selector": selector,
        "history": history,
        "reuse": True,
    }
    initial = native.run(inputs, root / "initial", **kwargs)
    raw = json.dumps(initial["observations"]["observe"], separators=(",", ":")).encode()
    path = root / "native-observation.json"
    path.write_bytes(raw)
    # Restrict availability to the same observation offered to the SDK.
    kwargs["history"] = [
        {
            "identity": initial["identity"],
            "receipts": {"observe": {"path": str(path), "sha256": native.sha(raw)}},
        }
    ]
    current = case.next_inputs(
        source,
        inputs,
        tolerance=0.001 if variant == "scoring" else 0.01,
        center=11 if variant == "calibration" else None,
    )
    setup = time.perf_counter() - start
    execution_start = time.perf_counter()
    result = native.run(current, root / "next", **kwargs)
    execution = time.perf_counter() - execution_start
    review_start = time.perf_counter()
    reviewed = native.export_and_review(root / "next", root / "review.zip")
    assert native.review_bundle(root / "review.zip") == reviewed
    assert result["observations"]["confirm"]["observation"]["position"] == 26
    return {
        "execution": result["execution"],
        "decision": reviewed["software_decision"],
        "review": "verified",
        "error": None,
        "actions": result["actions"],
        "input_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in current.items()},
        "setup_seconds": setup,
        "execute_seconds": execution,
        "review_seconds": time.perf_counter() - review_start,
        "total_seconds": time.perf_counter() - start,
        "initial_executed_checks": 4,
        "new_executed_checks": sum(v == "run" for v in result["actions"].values()),
        "human_review_seconds": None,
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    results = []
    for variant in ("unchanged", "calibration", "scoring"):
        sdk = sdk_cell(args.out / variant / "sdk", variant)
        conventional = native_cell(args.out / variant / "native", variant)
        assert sdk["input_sha256"] == conventional["input_sha256"]
        expected = "reject" if variant == "calibration" else "adopt"
        assert conventional["decision"] == expected
        results.append(
            {
                "variant": variant,
                "sdk": sdk,
                "native": conventional,
                "equal_inputs": True,
                "expected_decision": expected,
                "decision_equivalent": sdk["decision"] == conventional["decision"],
                "actions_equivalent": sdk["actions"] == conventional["actions"],
            }
        )
    report = {
        "cells": results,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": {
            str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path(__file__),
                REPO / "src/nisayon/qualification/checks.py",
                Path(native.__file__),
                Path(selector.__file__),
            )
        },
        "scope": "Three exposed scalar cases; no production, human-effort or statistical savings claim. Native and SDK portable formats differ; neither authenticates execution.",
        "complete_cost": None,
    }
    (args.out / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            [
                {k: r[k] for k in ("variant", "decision_equivalent", "actions_equivalent")}
                for r in results
            ]
        )
    )


if __name__ == "__main__":
    main()
