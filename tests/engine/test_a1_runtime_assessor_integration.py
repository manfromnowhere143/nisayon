"""Execution-owned regressions for the A1 runtime-assessor v1.3 corrections."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from nisayon.evaluation import a1_runtime_assessor as assessor

FIXTURE_SOURCE = Path("tests/evaluation/test_evaluation_a1_runtime_assessor.py")
SPEC = importlib.util.spec_from_file_location("a1_runtime_assessor_fixtures", FIXTURE_SOURCE)
fixtures = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fixtures
SPEC.loader.exec_module(fixtures)


def _assess(case: dict) -> dict:
    return assessor.assess_packet(
        case["store"],
        contract_paths=case["contracts"],
        dataset=case["dataset"],
        pilot_stats=case["pilot_stats"],
        checkpoint=case["checkpoint"],
        wheel=case["wheel"],
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_checkpoint_list_restoration_requires_opt_in_and_exact_values(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    stats = {
        key: {
            "mean": np.full((1, dim), 0.25, dtype=np.float32),
            "std": np.full((1, dim), 0.3, dtype=np.float64),
        }
        for key, dim in assessor.EXPECTED_DIMS.items()
    }
    serialized = {k: {p: v.tolist() for p, v in parts.items()} for k, parts in stats.items()}
    path = tmp_path / "checkpoint.pth"
    torch.save({"obs_normalization_stats": serialized}, path)

    legacy = assessor.checkpoint_statistics(path)
    decoded = assessor.checkpoint_statistics(path, restore_list_dtypes=True)
    assert legacy["object"]["mean"].dtype == np.float64
    assert assessor._stats_equal(decoded, stats, strict_dtype=True)

    serialized["object"]["mean"][0][0] = np.nextafter(0.25, np.inf)
    torch.save({"obs_normalization_stats": serialized}, path)
    assert assessor.checkpoint_statistics(path, restore_list_dtypes=True) is None

    stats["object"]["mean"] = stats["object"]["mean"].astype(np.float64)
    torch.save({"obs_normalization_stats": stats}, path)
    decoded = assessor.checkpoint_statistics(path, restore_list_dtypes=True)
    assert decoded["object"]["mean"].dtype == np.float64


def test_probe_rejects_inference_statistics_with_a_checkpoint_dtype_mismatch(
    tmp_path: Path,
) -> None:
    case = fixtures.build_packet(tmp_path)
    inference_path = case["store"] / "inference-stats.npz"
    with np.load(inference_path, allow_pickle=False) as archive:
        inference = {key: archive[key] for key in archive.files}
    assert inference["object__mean"].dtype == np.float32
    inference["object__mean"] = inference["object__mean"].astype(np.float64)
    np.savez(inference_path, **inference)
    fixtures._seal(case["store"])

    report = _assess(case)

    assert report["bindings"]["pilot_stats"]["bound"] is True
    c9 = report["compatibility_checks"]["C9"]
    assert c9["statistics_equality"] == {"pilot_packet": False, "checkpoint": False}
    assert c9["status"] == "fail"
    assert report["verdicts"]["Q-C_compatibility"] == "incompatible"
    assert report["disposition"] == "D1_runtime_incompatible"


def test_probe_rejects_a_policy_record_bound_to_the_wrong_checkpoint(tmp_path: Path) -> None:
    case = fixtures.build_packet(tmp_path)
    policy = case["store"] / "policy-identity.json"
    fixtures._edit_json(policy, lambda doc: doc.update({"checkpoint_sha256": "0" * 64}))
    fixtures._seal(case["store"])

    report = _assess(case)

    assert report["bindings"]["checkpoint"]["bound"] is True
    assert _read_json(policy)["checkpoint_sha256"] != report["bindings"]["checkpoint"]["sha256"]
    assert report["verdicts"]["Q-C_compatibility"] == "compatible"
    assert (
        report["competence"]["preconditions"]["policy_identity_names_the_effective_checkpoint"]
        is False
    )
    assert report["competence"]["verdict"] == "invalid_evidence"
    assert report["disposition"] != "D3_qualified_and_competent"


def test_probe_rejects_unverifiable_package_license_and_ledger_digests(tmp_path: Path) -> None:
    case = fixtures.build_packet(tmp_path)
    store = case["store"]
    identity = _read_json(store / "runtime-identity.json")
    receipt = _read_json(store / "acquisition-receipt-001.json")
    gate = _read_json(store / "dependency-gate-001.json")

    next(iter(identity["packages"].values()))["sha256"] = "p" * 64
    receipt["license"]["sha256"] = "m" * 64
    gate["ledger"]["sha256"] = "l" * 64
    (store / "runtime-identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    (store / "acquisition-receipt-001.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (store / "dependency-gate-001.json").write_text(json.dumps(gate, indent=2) + "\n")
    fixtures._seal(store)

    report = _assess(case)

    assert any(set(package["sha256"]) == {"p"} for package in identity["packages"].values())
    assert set(receipt["license"]["sha256"]) == {"m"}
    assert set(gate["ledger"]["sha256"]) == {"l"}
    assert (store / gate["ledger"]["path"]).exists()
    assert report["permission_and_custody"]["status"] == "fail"
    assert report["compatibility_checks"]["C1"]["status"] == "fail"
    assert report["gate"]["ledger_member_verified"] is False
    assert report["gate"]["status"] == "differs"
    assert report["disposition"] == "P0_not_qualified_permission_or_gate"


def test_probe_rejects_a_stopped_gate_with_the_wrong_wheel_pin(tmp_path: Path) -> None:
    case = fixtures.build_packet(tmp_path)
    gate_path = case["store"] / "dependency-gate-001.json"

    def corrupt_gate(doc: dict) -> None:
        doc.update(
            {
                "wheel_url": "https://invalid.example/not-the-wheel.whl",
                "wheel_sha256_expected": "0" * 64,
                "wheel_bytes_expected": 1,
                "wheel_downloaded_bytes": 0,
                "downloaded_bytes": 0,
                "stopped": True,
                "stop_mechanism": "storage_floor",
                "stop_reason": "synthetic stop with the wrong identity",
            }
        )

    fixtures._edit_json(gate_path, corrupt_gate)
    fixtures._seal(case["store"])

    report = _assess(case)

    assert report["gate"]["pin_matches_effective_contract"] is False
    assert report["gate"]["status"] == "unresolved"
    assert report["disposition"] == "D1_materially_unresolved"


def test_probe_rejects_an_unbound_mutated_intermediate_amendment(tmp_path: Path) -> None:
    case = fixtures.build_packet(tmp_path)
    _, v11, _, v13 = case["contracts"]
    fixtures._edit_json(v11, lambda doc: doc.update({"unbound_mutation": True}))

    def omit_v11_binding(doc: dict) -> None:
        doc["amends"] = [item for item in doc["amends"] if "v1.1" not in item["path"]]

    fixtures._edit_json(v13, omit_v11_binding)

    report = _assess(case)

    assert report["bindings"]["contract_chain_verified"] is False
    assert report["verdicts"]["Q-C_compatibility"] == "invalid"
    assert report["disposition"] == "invalid_contract_chain"
