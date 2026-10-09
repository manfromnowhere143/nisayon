"""Reproduce discriminating integration controls against the A1 runtime assessor.

The probe creates labelled synthetic packets in a temporary directory by using the
evaluator's own fixture builder. It edits only those copies, performs no network or
simulator operation, and reports current acceptance behavior without changing producer
or evaluator evidence.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

from nisayon.evaluation import a1_runtime_assessor as assessor
from nisayon.evaluation.a1_pilot_assessor import DATASET_SHA256

HELPER_PATH = Path("tests/evaluation/test_evaluation_a1_runtime_assessor.py")
AMENDMENT_PATH = Path("docs/evaluation/results/a1-runtime-001/runtime-contract.v1.1.json")


def _load_helper():
    spec = importlib.util.spec_from_file_location("a1_runtime_assessor_fixture", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the evaluator fixture builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build(helper, root: Path):
    root.mkdir()
    return helper.build_packet(root)


def _assess(store: Path, contract: Path, dataset: Path, pilot_stats: Path) -> dict:
    return assessor.assess_packet(
        store,
        contract_path=contract,
        dataset=dataset,
        pilot_stats=pilot_stats,
        checkpoint=None,
    )


def run_probe(root: Path) -> dict:
    helper = _load_helper()
    findings = {}

    store, contract, dataset, pilot_stats = _build(helper, root / "baseline")
    baseline = _assess(store, contract, dataset, pilot_stats)
    runtime_identity = json.loads((store / "runtime-identity.json").read_text())
    findings["baseline_incomplete_bindings"] = {
        "seal": baseline["seal"]["status"],
        "disposition": baseline["disposition"],
        "dataset_sha256": baseline["bindings"]["dataset_sha256"],
        "expected_dataset_sha256": DATASET_SHA256,
        "dataset_matches_expected": baseline["bindings"]["dataset_sha256"] == DATASET_SHA256,
        "checkpoint_sha256": baseline["bindings"]["checkpoint_sha256"],
        "C1": baseline["compatibility_checks"]["C1"],
        "C4": baseline["compatibility_checks"]["C4"],
        "C9": baseline["compatibility_checks"]["C9"]["status"],
        "runtime_identity_members": runtime_identity["members"],
        "runtime_identity_packages": runtime_identity["packages"],
        "object_state_evidence_present": any(
            "object-state" in name for name in np.load(store / "replay-R-1.npz").files
        ),
    }

    store, contract, dataset, pilot_stats = _build(helper, root / "invalid-seal")
    (store / "costs.json").write_text((store / "costs.json").read_text() + " ")
    invalid_seal = _assess(store, contract, dataset, pilot_stats)
    findings["invalid_seal_still_decides"] = {
        "seal": invalid_seal["seal"]["status"],
        "bad": invalid_seal["seal"]["manifest_entries_bad"],
        "compatibility": invalid_seal["verdicts"]["Q-C_compatibility"],
        "disposition": invalid_seal["disposition"],
    }

    store, contract, dataset, pilot_stats = _build(helper, root / "unsealed-override")
    helper._write(store / "000-runtime-identity.json", {"robosuite_version": "9.9"})
    unsealed = _assess(store, contract, dataset, pilot_stats)
    findings["unsealed_record_changes_decision"] = {
        "seal": unsealed["seal"]["status"],
        "manifest_contains_override": "000-runtime-identity.json"
        in json.loads((store / "artifact-manifest.json").read_text())["files"],
        "C1_record": unsealed["compatibility_checks"]["C1"]["record"],
        "compatibility": unsealed["verdicts"]["Q-C_compatibility"],
        "disposition": unsealed["disposition"],
    }

    store, contract, dataset, pilot_stats = _build(helper, root / "incomplete-replays")
    for attempt in ("R-1", "R-2"):
        record = json.loads((store / f"replay-{attempt}.json").read_text())
        record["completed"] = False
        helper._write(store / f"replay-{attempt}.json", record)
    helper._reseal(store)
    incomplete = _assess(store, contract, dataset, pilot_stats)
    findings["incomplete_replays_pass"] = {
        "completed": incomplete["replay"]["reproducibility"]["completed"],
        "reproducibility": incomplete["replay"]["reproducibility"]["status"],
        "compatibility": incomplete["verdicts"]["Q-C_compatibility"],
        "disposition": incomplete["disposition"],
    }

    store, contract, dataset, pilot_stats = _build(helper, root / "mutated-policy")
    policy_path = store / "policy-identity.json"
    policy = json.loads(policy_path.read_text())
    policy["parameter_sha256_after"] = "changed"
    helper._write(policy_path, policy)
    helper._reseal(store)
    mutated_policy = _assess(store, contract, dataset, pilot_stats)
    findings["mutated_policy_passes_competence"] = {
        "policy_unchanged": mutated_policy["competence"]["policy_unchanged_across_episodes"],
        "competence": mutated_policy["competence"]["verdict"],
        "disposition": mutated_policy["disposition"],
    }

    store, contract, dataset, pilot_stats = _build(helper, root / "invalid-gate-stop")
    helper._write(store / "dependency-gate-001.json", {"stopped": True})
    helper._reseal(store)
    invalid_gate = _assess(store, contract, dataset, pilot_stats)
    findings["bare_gate_stop_yields_G0"] = {
        "gate": invalid_gate["gate"],
        "compatibility": invalid_gate["verdicts"]["Q-C_compatibility"],
        "disposition": invalid_gate["disposition"],
    }

    store, contract, dataset, pilot_stats = _build(helper, root / "invalid-action")
    episode_path = store / "episode-E-200.npz"
    with np.load(episode_path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    arrays["actions"] = arrays["actions"].astype(np.float64)
    arrays["actions"][0, 0] = 2.0
    np.savez(episode_path, **arrays)
    helper._reseal(store)
    invalid_action = _assess(store, contract, dataset, pilot_stats)
    findings["invalid_action_contract_not_scored"] = {
        "episode": invalid_action["competence"]["episodes"]["E-200"],
        "compatibility": invalid_action["verdicts"]["Q-C_compatibility"],
        "competence": invalid_action["competence"]["verdict"],
        "disposition": invalid_action["disposition"],
    }

    store, _contract, dataset, pilot_stats = _build(helper, root / "amendment")
    amendment_error = None
    try:
        _assess(store, AMENDMENT_PATH, dataset, pilot_stats)
    except Exception as error:  # noqa: BLE001 - the exact integration failure is evidence.
        amendment_error = f"{type(error).__name__}: {error}"
    findings["amendment_not_consumable"] = {
        "amendment_sha256": hashlib.sha256(AMENDMENT_PATH.read_bytes()).hexdigest(),
        "error": amendment_error,
    }

    expected = {
        "baseline_d3": findings["baseline_incomplete_bindings"]["disposition"]
        == "D3_qualified_and_competent",
        "invalid_seal_d3": findings["invalid_seal_still_decides"]["disposition"]
        == "D3_qualified_and_competent",
        "unsealed_override_changes": findings["unsealed_record_changes_decision"]["C1_record"]
        == "000-runtime-identity.json",
        "incomplete_replays_compatible": findings["incomplete_replays_pass"]["compatibility"]
        == "compatible",
        "mutated_policy_d3": findings["mutated_policy_passes_competence"]["disposition"]
        == "D3_qualified_and_competent",
        "bare_gate_g0": findings["bare_gate_stop_yields_G0"]["disposition"]
        == "G0_not_qualified_dependency_ceiling",
        "invalid_action_d3": findings["invalid_action_contract_not_scored"]["disposition"]
        == "D3_qualified_and_competent",
        "amendment_raises": findings["amendment_not_consumable"]["error"] is not None,
    }
    if not all(expected.values()):
        raise RuntimeError(f"integration controls did not reproduce current behavior: {expected}")
    return {
        "schema": "nisayon.a1-runtime-assessor-integration-probe.v1",
        "assessor_sha256": hashlib.sha256(Path(assessor.__file__).read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest(),
        "synthetic_only": True,
        "findings": findings,
        "controls_reproduced": expected,
        "operations": {
            "network_requests": 0,
            "package_downloads": 0,
            "environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nisayon-a1-runtime-assessor-probe-") as directory:
        result = run_probe(Path(directory))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
