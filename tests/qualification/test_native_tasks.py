"""Native records, adverse semantic controls and portable independent recomputation."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.engine.io import canonical_bytes, decode_json
from nisayon.qualification import (
    EvidenceState,
    NativeTaskProtocol,
    assess_native_task,
    export_checks,
    reassess_native_task_bundle,
    run_native_task,
)
from nisayon.qualification.native_tasks import FILES

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/qualification/native_task_case"


@pytest.fixture
def case():
    protocol = NativeTaskProtocol.from_dict(decode_json((EXAMPLE / "protocol.json").read_bytes()))
    records = {
        role: {key: (EXAMPLE / role / name).read_bytes() for key, name in FILES.items()}
        for role in ("reference", "candidate")
    }
    return protocol, records


def assess(case):
    protocol, records = case
    return assess_native_task(protocol, records["reference"], records["candidate"])


def rows(case, key, role="candidate"):
    return [decode_json(line) for line in case[1][role][key].splitlines()]


def put_rows(case, key, values, role="candidate"):
    case[1][role][key] = b"".join(canonical_bytes(row) + b"\n" for row in values)


def summary_outcome(case, success, episode=2, role="candidate"):
    value = decode_json(case[1][role]["summary"])
    outcomes = value["per_task"][0]["metrics"]["successes"]
    outcomes[episode] = success
    for aggregate in [value["per_task"][0], value["overall"], value["per_group"]["libero_spatial"]]:
        aggregate["n_success"] = sum(outcomes)
        aggregate["pc_success"] = 100 * sum(outcomes) / len(outcomes)
    case[1][role]["summary"] = canonical_bytes(value)


def timeout_failure(case, role="candidate"):
    original = rows(case, "steps", role)
    values = []
    for episode in range(5):
        group = [row for row in original if row["episode"] == episode]
        if episode == 2:
            group = [
                dict(group[0], step=step, success=False, terminated=False, truncated=False)
                for step in range(1, 281)
            ]
        values.extend(group)
    put_rows(case, "steps", values, role)
    put_rows(
        case,
        "history",
        [
            {"observation": i, "history_frames": 1, "queued_actions": 0}
            for i in range(1, len(values) + 1)
        ],
        role,
    )
    summary_outcome(case, False, role=role)


def test_original_five_pairs_reconstruct_without_implying_new_execution(case):
    result = assess(case)
    assert result["status"] == "valid_retained_records"
    assert result["verdict"] == "supported"
    assert result["recorded_outcome"] == "no_regression_observed"
    assert [p["candidate_steps"] for p in result["pairs"]] == [70, 73, 79, 78, 76]
    assert sum(p["reference_steps"] for p in result["pairs"]) == 390
    assert result["measurement_adequacy"] == result["deployment_decision"] == "unresolved"
    assert result["new_native_execution"] is False


def test_native_timeout_is_a_task_regression_not_invalid_evidence(case):
    timeout_failure(case)
    result = assess(case)
    assert result["status"] == "valid_retained_records"
    assert result["verdict"] == "rejected"
    assert result["regressions"] == [2]
    assert result["pairs"][2]["candidate_completion"] == "native_horizon"


def test_useful_improvement_and_shared_failure_are_not_starved(case):
    timeout_failure(case, "reference")
    result = assess(case)
    assert result["verdict"] == "supported"
    assert result["improvements"] == [2]
    timeout_failure(case)
    result = assess(case)
    assert result["verdict"] == "supported"
    assert not result["improvements"] and not result["regressions"]
    assert result["pairs"][2]["candidate_success"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "missing_step",
        "duplicate_step",
        "unknown_episode",
        "reordered_episode",
        "missing_episode",
        "unfinished",
        "after_termination",
        "wrong_action_dimension",
        "nonfinite_qpos",
        "string_success",
        "stale_summary",
        "wrong_task",
        "wrong_episode_count",
        "wrong_reset",
        "already_solved",
        "stale_state_values",
        "wrong_initial_input",
        "missing_input_producer",
        "wrong_history",
        "missing_history",
        "wrong_environment",
        "interrupted_execution",
        "incomplete_weights",
        "duplicate_json_key",
        "boolean_episode",
        "missing_file",
    ],
)
def test_invalid_records_never_become_a_valid_task_result(case, fault):
    steps = rows(case, "steps")
    if fault in {
        "missing_step",
        "duplicate_step",
        "unknown_episode",
        "reordered_episode",
        "missing_episode",
        "unfinished",
        "after_termination",
        "wrong_action_dimension",
        "nonfinite_qpos",
        "string_success",
        "boolean_episode",
    }:
        if fault == "missing_step":
            steps.pop(2)
        elif fault == "duplicate_step":
            steps[2]["step"] = 2
        elif fault == "unknown_episode":
            steps[0]["episode"] = 99
        elif fault == "reordered_episode":
            steps[0]["episode"] = 2
        elif fault == "missing_episode":
            steps = [row for row in steps if row["episode"] != 4]
        elif fault == "unfinished":
            steps = [row for row in steps if row["episode"] != 4 or row["step"] < 10]
        elif fault == "after_termination":
            steps[1]["terminated"] = True
        elif fault == "wrong_action_dimension":
            steps[0]["action"].pop()
        elif fault == "nonfinite_qpos":
            case[1]["candidate"]["steps"] = case[1]["candidate"]["steps"].replace(
                b'"qpos": [', b'"qpos": [1e999,', 1
            )
        elif fault == "string_success":
            steps[0]["success"] = "false"
        elif fault == "boolean_episode":
            steps[0]["episode"] = False
        if fault != "nonfinite_qpos":
            put_rows(case, "steps", steps)
            # Keep history consistent so the step/completion obligation is tested.
            put_rows(
                case,
                "history",
                [
                    {"observation": i, "history_frames": 1, "queued_actions": 0}
                    for i in range(1, len(steps) + 1)
                ],
            )
    elif fault in {"stale_summary", "wrong_task", "wrong_episode_count"}:
        value = decode_json(case[1]["candidate"]["summary"])
        if fault == "stale_summary":
            value["per_task"][0]["metrics"]["successes"][2] = False
        elif fault == "wrong_task":
            value["per_task"][0]["task_id"] = 1
        else:
            value["overall"]["n_episodes"] = 4
        case[1]["candidate"]["summary"] = canonical_bytes(value)
    elif fault in {"wrong_reset", "already_solved", "stale_state_values"}:
        values = rows(case, "resets")
        if fault == "wrong_reset":
            values[0]["initial_state_index"] = 4
        elif fault == "already_solved":
            values[0]["initial_goal"] = True
        else:
            values[0]["settled_state_values"][0] += 1
        put_rows(case, "resets", values)
    elif fault in {"wrong_initial_input", "missing_input_producer"}:
        values = rows(case, "initial_inputs")
        if fault == "wrong_initial_input":
            values[0]["observation.state"]["sha256"] = "0" * 64
        else:
            del values[0]["observation.state"]
        put_rows(case, "initial_inputs", values)
    elif fault in {"wrong_history", "missing_history"}:
        values = rows(case, "history")
        if fault == "wrong_history":
            values[0]["observation"] = 7
        else:
            values.pop()
        put_rows(case, "history", values)
    elif fault == "wrong_environment":
        values = rows(case, "environment")
        values[0]["bddl_sha256"] = "0" * 64
        put_rows(case, "environment", values)
    elif fault in {"interrupted_execution", "incomplete_weights"}:
        key = "execution" if fault == "interrupted_execution" else "weights"
        value = decode_json(case[1]["candidate"][key])
        value["status"] = "incomplete"
        case[1]["candidate"][key] = canonical_bytes(value)
    elif fault == "duplicate_json_key":
        case[1]["candidate"]["steps"] = case[1]["candidate"]["steps"].replace(
            b'"episode": 0', b'"episode": 0, "episode": 0', 1
        )
    else:
        del case[1]["candidate"]["steps"]
    result = assess(case)
    assert result["status"] == "invalid", fault
    assert result["verdict"] == result["recorded_outcome"] == "unresolved"
    assert result["errors"]


def test_consistent_native_flags_do_not_establish_a_qualified_measurement(case):
    # An internally consistent but false producer can evade record checks. Do
    # not turn agreement or the adapter's source identity into physical truth.
    for role in ("reference", "candidate"):
        values = rows(case, "steps", role)
        for row in values:
            row["qpos"] = [0.0] * 48
        put_rows(case, "steps", values, role)
    result = assess(case)
    assert result["verdict"] == "supported"
    assert result["measurement_adequacy"] == result["deployment_decision"] == "unresolved"
    assert result["missing_evidence"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("initial_state_indices", [0, 0]),
        ("action_size", True),
        ("state_encoding", "unknown"),
        ("format", "newer_libero"),
    ],
)
def test_protocol_rejects_ambiguous_or_unsupported_semantics(case, field, value):
    declaration = case[0].record()
    declaration[field] = value
    with pytest.raises(ValueError):
        NativeTaskProtocol.from_dict(declaration)


def test_sdk_export_recompute_and_reuse(tmp_path):
    evidence = tmp_path / "evidence"
    first = evidence / "first"
    report = run_native_task(
        EXAMPLE / "protocol.json",
        reference=EXAMPLE / "reference",
        candidate=EXAMPLE / "candidate",
        evidence_root=evidence,
        output=first,
    )
    assert report["assessment"]["verdict"] == "supported"
    state = EvidenceState.read(first / "execution/state.json")
    second = evidence / "second"
    run_native_task(
        EXAMPLE / "protocol.json",
        reference=EXAMPLE / "reference",
        candidate=EXAMPLE / "candidate",
        evidence_root=evidence,
        output=second,
        previous=state,
    )
    execution = decode_json((second / "execution/execution.json").read_bytes())
    assert execution["attempts"][0]["action"] == "reuse"
    bundle = tmp_path / "review.zip"
    export_checks(evidence_root=evidence, execution=second / "execution", output=bundle)
    reviewed = reassess_native_task_bundle(bundle)
    assert reviewed["assessment_matches"]
    assert reviewed["assessment"]["pairs"] == report["assessment"]["pairs"]
    assert reviewed["assessment"]["measurement_adequacy"] == "unresolved"


def test_cli_outside_git_preserves_scope_and_needs_no_native_imports(tmp_path):
    args = [
        sys.executable,
        "-m",
        "nisayon.qualification",
        "native-task",
        str(EXAMPLE / "protocol.json"),
        "--reference",
        str(EXAMPLE / "reference"),
        "--candidate",
        str(EXAMPLE / "candidate"),
        "--evidence-root",
        str(tmp_path / "evidence"),
        "--out",
        str(tmp_path / "evidence/run"),
    ]
    result = subprocess.run(
        args,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["assessment"]["recorded_outcome"] == "no_regression_observed"
    assert report["deployment_decision"] == "unresolved"


def test_changed_native_bytes_invalidate_reuse(tmp_path):
    case_root = tmp_path / "case"
    shutil.copytree(EXAMPLE, case_root)
    evidence = tmp_path / "evidence"
    arguments = {
        "protocol_path": case_root / "protocol.json",
        "reference": case_root / "reference",
        "candidate": case_root / "candidate",
        "evidence_root": evidence,
    }
    run_native_task(**arguments, output=evidence / "first")
    state = EvidenceState.read(evidence / "first/execution/state.json")
    path = case_root / "candidate/steps.jsonl"
    values = [decode_json(line) for line in path.read_bytes().splitlines()]
    values[0]["qpos"][0] += 0.001
    path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in values))
    run_native_task(**arguments, output=evidence / "changed", previous=state)
    record = decode_json((evidence / "changed/execution/execution.json").read_bytes())
    assert all(attempt["action"] == "run" for attempt in record["attempts"])


def test_domain_reassessment_detects_an_internally_consistent_wrong_saved_claim(
    tmp_path, monkeypatch
):
    from nisayon.qualification import native_task_workflow as workflow

    original = workflow._assess

    def wrong_claim(context):
        result = original(context)
        result["verdict"] = "rejected"
        return result

    evidence = tmp_path / "evidence"
    with monkeypatch.context() as patch:
        patch.setattr(workflow, "_assess", wrong_claim)
        run_native_task(
            EXAMPLE / "protocol.json",
            reference=EXAMPLE / "reference",
            candidate=EXAMPLE / "candidate",
            evidence_root=evidence,
            output=evidence / "wrong",
        )
    bundle = tmp_path / "wrong.zip"
    export_checks(evidence_root=evidence, execution=evidence / "wrong/execution", output=bundle)
    review = reassess_native_task_bundle(bundle)
    assert review["integrity"] == "verified"
    assert review["assessment_matches"] is False
    assert review["assessment"]["verdict"] == "supported"
