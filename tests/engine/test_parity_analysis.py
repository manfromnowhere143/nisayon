import copy
import importlib
from pathlib import Path

import pytest

from nisayon.engine.io import digest, file_digest, write_json


@pytest.fixture
def parity(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/experiments"
    monkeypatch.syspath_prepend(str(scripts))
    return importlib.import_module("explain_development_parity")


def test_binding_catches_changed_bytes_even_when_outcome_is_unchanged(parity, tmp_path):
    path = tmp_path / "decision.json"
    write_json(path, {"decision": "unresolved"})
    reference = {"path": path.name, "sha256": file_digest(path)}
    assert parity.bound(tmp_path, reference)[1]["decision"] == "unresolved"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="Changed bound record"):
        parity.bound(tmp_path, reference)


def test_fable_source_binds_document_while_producer_binds_file_bytes(parity, tmp_path):
    document = {"runs": [], "case": "development"}
    path = tmp_path / "snapshot.json"
    write_json(path, document)
    assessment = {"bundle_sha256": "sha256:" + digest(document)}
    assert file_digest(path) != digest(document)
    parity.require_decision_source(document, assessment)
    with pytest.raises(ValueError, match="another snapshot"):
        parity.require_decision_source({**document, "case": "other"}, assessment)


def test_same_final_answer_does_not_hide_changed_observation_order(parity):
    keys = (
        "information_sha256",
        "selection",
        "proposals",
        "candidate",
        "diagnostic_stop",
        "trial_status",
        "accepted",
        "confirmation_pairs",
    )
    left = dict.fromkeys(keys, "same")
    left["ordered_evidence"] = {"diagnostic": ["reference", "regression", "probe"]}
    right = copy.deepcopy(left)
    right["ordered_evidence"]["diagnostic"].reverse()
    result = parity.compare_arms(left, right)
    assert result["candidate"] and result["trial_status"]
    assert not result["ordered_evidence"]
    right["candidate"] = "different"
    assert not parity.compare_arms(left, right)["candidate"]


def test_disjoint_costs_reconcile_without_adding_simulator_twice(parity):
    diagnostic = {
        "phase_wall_s": 10,
        "diagnostic_final_check_wall_s": 1,
        "preflight_checks": [{"wall_s": 2}],
        "costs": {"known_run_wall_s": 6},
    }
    confirmation = {
        "phase_wall_s": 20,
        "preparation_wall_s": 2,
        "execution_and_integrity_wall_s": 18,
        "final_evaluation_wall_s": 2,
        "costs": {"known_run_wall_s": 15},
    }
    trial = {"costs": {"own_trial_wall": {"value": 32}, "simulator_wall": {"value": 21}}}
    costs = parity.cost_parts(diagnostic, confirmation, trial)
    assert sum(costs.values()) == 32
    assert costs["diagnostic_unpartitioned_s"] == 1
    trial["costs"]["own_trial_wall"]["value"] += 21
    with pytest.raises(ValueError, match="do not reconcile"):
        parity.cost_parts(diagnostic, confirmation, trial)


def test_negative_partition_does_not_become_a_saving(parity):
    diagnostic = {
        "phase_wall_s": 4,
        "diagnostic_final_check_wall_s": 1,
        "preflight_checks": [{"wall_s": 2}],
        "costs": {"known_run_wall_s": 6},
    }
    with pytest.raises(ValueError, match="negative cost"):
        parity.cost_parts(diagnostic, None, {})
