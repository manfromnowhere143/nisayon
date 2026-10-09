import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nisayon.engine.configuration import Deployment
from nisayon.engine.confirmation_service import assignments_for, prepare_confirmation
from nisayon.engine.declarations import DeclarationBinding, declare
from nisayon.engine.development_cases import load_suite
from nisayon.engine.development_diagnostics import plans_for
from nisayon.engine.diagnostics import known_correction
from nisayon.engine.io import digest, file_digest, write_json

ROOT = Path(__file__).resolve().parents[2]


def incident(index):
    return load_suite(ROOT / "work/development/incidents-proposed-v1.json")[1][index]


def test_confirmation_counts_all_reproduction_and_physical_prefixes():
    simple, recurrent = incident(0), incident(4)
    for case, expected in [(simple, 67), (recurrent, 134)]:
        assigned = assignments_for(case, known_correction(case.changed), list(range(10000, 10032)))
        assert len(assigned) == len({a["run_id"] for a in assigned}) == expected
        main = [a for a in assigned if a["role"] != "executed_prefix_context"]
        assert len([a for a in main if a["role"] == "reproduction"]) == 3
        assert len([a for a in main if a["role"] == "fresh_development_confirmation"]) == 64
    plans = {p["id"]: p for p in plans_for(recurrent)}
    assert plans["prefix-reference"]["role"] == "executed_prefix_context"
    assert plans["prefix-reference"]["candidate_sha256"] == digest(Deployment().record())


def test_reproduction_and_duplicate_conditions_cannot_be_called_fresh():
    case = incident(0)
    for seeds in [list(range(32)), [10000] * 32, list(range(10000, 10031))]:
        with pytest.raises(ValueError):
            assignments_for(case, known_correction(case.changed), seeds)


@pytest.mark.parametrize("study", [False, True])
def test_freeze_separates_same_deployment_with_different_rollout_configurations(tmp_path, study):
    case = incident(4)
    corrected = known_correction(case.changed)
    code = {"git_head": "synthetic-test", "source_changes": []}
    identity = {
        "code": code,
        "dependencies": {"packages": [], "platform": "synthetic", "python": "synthetic"},
        "environment": {},
        "torch": {},
    }

    def configuration_for(mode, **kwargs):
        return {"deployment": kwargs["deployment"].record(), "horizon": kwargs.get("horizon", 400)}

    executor = SimpleNamespace(
        identity=identity,
        invocation={"id": "synthetic", "execution_identity_sha256": digest(identity)},
        configuration_for=configuration_for,
    )
    seeds = list(range(10000, 10032))
    joint = tmp_path / "joint.json"
    binding = None
    extension = {}
    if study:
        inputs_sha = digest({"labelled_metadata_test": True})
        receipt = declare(
            tmp_path / "declaration",
            {
                "assignment": {
                    "suite_id": "synthetic-suite",
                    "case_id": case.id,
                    "arm": "A",
                    "frozen_inputs_sha256": inputs_sha,
                },
                "candidate": {
                    "configuration": corrected.record(),
                    "configuration_sha256": digest(corrected.record()),
                },
                "disposition": "claim_acceptance",
                "reason": "Labelled preparation boundary test, no physical runs",
                "source": {"synthetic_test": True},
                "settings": {"synthetic_test": True},
                "evidence": [],
                "evidence_scope": "prospective_execution",
            },
            evidence_root=tmp_path,
        )
        binding = DeclarationBinding(tmp_path / "declaration", tmp_path, receipt)
        extension = {"declarations": {"A": receipt}, "frozen_inputs_sha256": inputs_sha}
    write_json(
        joint,
        {
            "case_id": case.id,
            "candidates": {"A": corrected.record(), "B": corrected.record()},
            "suite_sha256": "synthetic-suite",
            "condition_seeds": seeds,
            **extension,
        },
    )
    prepared = prepare_confirmation(
        executor,
        case,
        {},
        "A",
        corrected.record(),
        seeds,
        tmp_path / "arm-A",
        {},
        [],
        joint,
        suite_sha256="synthetic-suite",
        declaration=binding,
    )
    frozen = prepared.frozen
    configs = frozen["configuration_sha256_by_run_id"]
    assert configs["reproduction-reference"] == configs["reproduction-correction"]
    assert configs["reproduction-reference-prefix"] != configs["reproduction-reference"]
    assert not prepared.store.assignments  # Freeze never executes or invents observations.
    assert json.loads((prepared.store.root / "frozen-protocol.json").read_text()) == frozen
    if study:
        retained = prepared.store.root / "arm-declaration.json"
        assert file_digest(retained) == binding.reference["sha256"]
        assert frozen["arm_declaration"] == prepared.store.header["arm_declaration"]
        assert prepared.store.header["confirmation"]["protocol_sha256"] == digest(frozen)
        wrong_joint = tmp_path / "wrong-inputs.json"
        write_json(
            wrong_joint,
            {
                **json.loads(joint.read_text()),
                "frozen_inputs_sha256": "0" * 64,
            },
        )
        with pytest.raises(ValueError, match="joint frozen inputs"):
            prepare_confirmation(
                executor,
                case,
                {},
                "A",
                corrected.record(),
                seeds,
                tmp_path / "wrong-arm",
                {},
                [],
                wrong_joint,
                suite_sha256="synthetic-suite",
                declaration=binding,
            )
        assert not (tmp_path / "wrong-arm").exists()
    altered = Deployment(policy_reset="every_action").record()
    with pytest.raises(ValueError, match="joint pre-confirmation freeze"):
        prepare_confirmation(
            executor,
            case,
            {},
            "B",
            altered,
            seeds,
            tmp_path / "arm-B",
            {},
            [],
            joint,
            suite_sha256="synthetic-suite",
        )
    assert not (tmp_path / "arm-B").exists()
