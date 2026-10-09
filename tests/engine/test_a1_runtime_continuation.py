"""Keep the prospective A1 continuation within its exact reset and ownership change."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nisayon.evaluation.a1_runtime_assessor import load_effective_contract

CONTRACT_ROOT = Path("docs/evaluation/results/a1-runtime-001")
VERSIONS = ("v1", "v1.1", "v1.2", "v1.3", "v1.4")


def test_continuation_binds_the_chain_without_changing_scientific_terms() -> None:
    paths = [CONTRACT_ROOT / f"runtime-contract.{version}.json" for version in VERSIONS]
    result = load_effective_contract(paths)
    previous = json.loads(paths[-2].read_text())["effective"]
    current = dict(result["effective"])

    assert result["chain_verified"] is True
    assert current.pop("contract_chain") == [
        *previous["contract_chain"],
        "nisayon.a1-runtime-contract-amendment.v1.4",
    ]
    continuation = current.pop("qualification_continuation")
    mode = current.pop("assessment_mode")
    assert current == {key: value for key, value in previous.items() if key != "contract_chain"}
    assert mode["independent"] is False
    assert mode["external_replication"] is False
    assert mode["execution_and_assessment"] == "single_lane"

    failure_path = Path(continuation["prior_failure"]["path"])
    assert (
        hashlib.sha256(failure_path.read_bytes()).hexdigest()
        == continuation["prior_failure"]["sha256"]
    )
    failure = json.loads(failure_path.read_text())
    assert failure["operations"]["explicit_probe_reset_invocations"] == 1
    assert failure["operations"]["control_steps"] == 0
    assert continuation["failed_probe_explicit_resets"] == 1
    assert continuation["replacement_probe_invocations_maximum"] == 1
    assert continuation["qualification_explicit_resets_maximum"] == 4
    assert continuation["phase_explicit_resets_maximum"] == 16
    assert continuation["qualification_control_steps_maximum"] == 20
    assert continuation["phase_control_steps_maximum"] == 4138
    assert continuation["phase_physics_substeps_maximum"] == 103450
    assert continuation["policy_actions_maximum"] == 4000


def test_continuation_rejects_an_omitted_prior_freeze(tmp_path: Path) -> None:
    paths = []
    for version in VERSIONS:
        source = CONTRACT_ROOT / f"runtime-contract.{version}.json"
        target = tmp_path / source.name
        target.write_bytes(source.read_bytes())
        paths.append(target)
    amendment = json.loads(paths[-1].read_text())
    amendment["amends"] = amendment["amends"][:-1]
    paths[-1].write_text(json.dumps(amendment))

    assert load_effective_contract(paths)["chain_verified"] is False


def test_recorder_extension_preserves_criteria_and_counts_consumed_attempts() -> None:
    paths = [CONTRACT_ROOT / f"runtime-contract.{version}.json" for version in (*VERSIONS, "v1.5")]
    result = load_effective_contract(paths)
    previous = json.loads(paths[-2].read_text())["effective"]
    current = dict(result["effective"])

    assert result["chain_verified"] is True
    extension = current.pop("recorder_validation")
    for key in ("contract_chain", "qualification_continuation", "unchanged"):
        current.pop(key)
    assert current == {
        key: value
        for key, value in previous.items()
        if key not in {"contract_chain", "qualification_continuation", "unchanged"}
    }
    assert extension["old_replay_attempts_assigned_started_consumed"] == [2, 2, 2]
    assert extension["additional_replay_attempts"] == 2
    assert extension["global_attempts"] == ["R-3", "R-4"]
    ceilings = extension["cumulative_phase_ceilings"]
    assert ceilings["control_steps"] == 20 + 4 * 59 + 10 * 400 == 4256
    assert ceilings["contract_counted_physics_substeps"] == 4256 * 25
    assert ceilings["explicit_resets"] == 4 + 4 + 10 == 18
    assert ceilings["development_attempts"] == 10
    continuation = result["effective"]["qualification_continuation"]
    assert continuation["phase_control_steps_maximum"] == ceilings["control_steps"]
    assert continuation["phase_explicit_resets_maximum"] == ceilings["explicit_resets"]
    for binding in (extension["proposal"], extension["prior_assessment"]):
        assert hashlib.sha256(Path(binding["path"]).read_bytes()).hexdigest() == binding["sha256"]
    proposal = json.loads(Path(extension["proposal"]["path"]).read_text())
    assert extension["correction"] == proposal["basis"]["correction"]


def test_statistics_startup_correction_adds_no_attempt_or_threshold_allowance() -> None:
    versions = (*VERSIONS, "v1.5", "v1.6")
    paths = [CONTRACT_ROOT / f"runtime-contract.{version}.json" for version in versions]
    result = load_effective_contract(paths)
    previous = json.loads(paths[-2].read_text())["effective"]
    current = dict(result["effective"])
    assert result["chain_verified"] is True
    assert current.pop("checkpoint_statistics_serialization")["restore_lossless_lists"] is True
    continuation = current.pop("development_startup_correction")
    current.pop("contract_chain")
    assert current == {k: v for k, v in previous.items() if k != "contract_chain"}
    failure = json.loads(Path(continuation["prior_failure"]["path"]).read_text())
    assert not any(failure["operations_of_failed_startup"].values())
    assert failure["accounting_before_continuation"][
        "development_attempts_assigned_started_consumed"
    ] == [10, 0, 0]
