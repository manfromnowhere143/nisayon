"""Executable dependency controls, including changed bytes and failed prefixes."""

import json
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import DependencyModel, EvidenceState, execute_checks, inspect_checks


def observe(ctx):
    return ctx.input("data")


def score(ctx):
    return {"holds": ctx.upstream("observe")["value"] <= ctx.input("scoring")["limit"]}


def confirm(ctx):
    return {
        "holds": ctx.input("data")["value"] <= ctx.input("scoring")["limit"],
        "origin": "exposed_control",
    }


def review(ctx):
    return {
        "decision": "supported"
        if ctx.upstream("score")["holds"] and ctx.upstream("confirm")["holds"]
        else "rejected"
    }


@pytest.fixture
def case(tmp_path):
    kinds = {
        "data": "data",
        "scoring": "scoring",
        "code": "code",
        "runtime": "runtime",
        "population": "population",
        "procedure": "protocol",
    }
    value = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "executable-controls",
        "scope": "Exposed data controls, no fresh physical confirmation",
        "inputs": {key: {"kind": kind, "description": key} for key, kind in kinds.items()},
        "checks": {
            "observe": {
                "kind": "observation",
                "depends_on": ["data", "code", "runtime", "procedure"],
                "refresh": "on_change",
            },
            "score": {
                "kind": "analysis",
                "depends_on": ["observe", "scoring"],
                "refresh": "on_change",
            },
            "confirm": {"kind": "confirmation", "depends_on": list(kinds), "refresh": "always"},
            "review": {
                "kind": "review",
                "depends_on": ["score", "confirm"],
                "refresh": "on_change",
            },
        },
        "decisions": {
            "relation": {"description": "Declared scalar relation", "depends_on": ["review"]}
        },
        "review": None,
    }
    model = DependencyModel.from_dict(value)
    write_json(
        tmp_path / "review.json",
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": model.definition_sha256,
            "reviewer": "exposed-control",
            "coverage": "reviewed_for_declared_scope",
            "statement": "Authored test declaration; not independent review",
        },
    )
    value["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": "exposed-control",
        "artifact": {"path": "review.json", "sha256": file_digest(tmp_path / "review.json")},
    }
    model = DependencyModel.from_dict(value)
    inputs = {}
    for key in kinds.keys() - {"procedure"}:
        path = tmp_path / f"{key}.json"
        write_json(path, {"value": 10, "limit": 11, "identity": key})
        inputs[key] = path
    return {
        "model": model,
        "inputs": inputs,
        "handlers": {"observe": observe, "score": score, "confirm": confirm, "review": review},
        "implementation_files": [Path(__file__)],
        "evidence_root": tmp_path,
    }


def run(case, name="run", previous=None):
    return execute_checks(**case, output=case["evidence_root"] / name, previous=previous)


def replay(case, name="run"):
    return inspect_checks(evidence_root=case["evidence_root"], output=case["evidence_root"] / name)


def change(case, key, value):
    case["inputs"][key].write_text(json.dumps(value))


def test_complete_is_not_automatic_acceptance_and_replays(case):
    result = run(case)
    assert result["status"] == "completed"
    assert result["automatic_acceptance"] is False
    assert result["costs"]["complete_cost"] is None
    assert replay(case)["artifacts"]["review"]["decision"] == "supported"


@pytest.mark.parametrize("incomplete", [False, True])
@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "future_execution"),
        ("status", "adopted"),
        ("automatic_acceptance", True),
        ("deployment_decision", "adopt"),
        ("errors", {"message": "not a list"}),
    ],
)
def test_execution_header_cannot_change_authority_or_hide_invalidity(
    case, incomplete, field, value
):
    if incomplete:
        case["inputs"]["population"] = None
    report = run(case)
    report[field] = value
    (case["evidence_root"] / "run/execution.json").write_text(json.dumps(report))
    with pytest.raises(ValueError):
        replay(case)


def test_completed_execution_cannot_retain_an_error(case):
    report = run(case)
    report["errors"] = ["confirmation failed"]
    (case["evidence_root"] / "run/execution.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="errors"):
        replay(case)


def test_rescore_reuses_observation_and_keeps_new_confirmation(case):
    first = run(case, "first")
    change(case, "scoring", {"limit": 9})
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert {row["check"]: row["action"] for row in second["attempts"]} == {
        "observe": "reuse",
        "score": "run",
        "confirm": "run",
        "review": "run",
    }
    assert replay(case, "second")["artifacts"]["review"]["decision"] == "rejected"


@pytest.mark.parametrize("key", ["data", "code", "runtime"])
def test_silent_file_change_invalidates_execution(case, key):
    first = run(case, "first")
    change(case, key, {"value": 12, "limit": 11, "changed": True})
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert all(row["action"] == "run" for row in second["attempts"])


def test_unchanged_can_reuse_scoring_but_never_confirmation(case):
    first = run(case, "first")
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert {row["check"] for row in second["attempts"] if row["action"] == "reuse"} == {
        "observe",
        "score",
    }
    assert replay(case, "second")["status"] == "verified_execution_records"


def test_unknown_input_runs_nothing(case):
    case["inputs"]["population"] = None
    result = run(case)
    assert result["status"] == "unresolved" and result["attempts"] == []
    assert replay(case)["status"] == "unresolved"


def test_undeclared_direct_input_is_an_error(case):
    def wrong(ctx):
        return ctx.input("scoring")

    case["handlers"]["observe"] = wrong
    result = run(case)
    assert result["status"] == "unresolved"
    assert any("Undeclared direct input" in error for error in result["errors"])


def test_stale_upstream_forces_reexecution(case):
    first = run(case, "first")
    artifact = case["evidence_root"] / first["state"]["checks"]["observe"]["artifact"]["path"]
    artifact.write_text('{"value": 999}')
    result = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert next(row for row in result["attempts"] if row["check"] == "observe")["action"] == "run"
    with pytest.raises(ValueError):
        replay(case, "first")


def test_failed_handler_retains_attempt_and_stops_dependents(case):
    def failure(ctx):
        (ctx.directory / "native-prefix.txt").write_text("failed native attempt")
        raise RuntimeError("native worker failed")

    case["handlers"]["observe"] = failure
    result = run(case)
    assert result["status"] == "unresolved"
    assert (case["evidence_root"] / "run/checks/observe/native-prefix.txt").is_file()
    assert "review" not in result["state"]["checks"]


def test_input_mutation_during_execution_fails_closed(case):
    def mutate(ctx):
        change(case, "data", {"value": 0})
        return {"value": 0}

    case["handlers"]["observe"] = mutate
    result = run(case)
    assert result["status"] == "unresolved"
    assert any("changed during execution" in error for error in result["errors"])


def test_interruption_preserves_incomplete_prefix(case):
    def interrupt(ctx):
        raise KeyboardInterrupt

    case["handlers"]["observe"] = interrupt
    with pytest.raises(KeyboardInterrupt):
        run(case)
    assert replay(case)["status"] == "unresolved"


@pytest.mark.parametrize("kind", ["saved_decision", "frozen_input", "completion", "omit"])
def test_tampering_is_rejected(case, kind):
    run(case)
    root = case["evidence_root"] / "run"
    if kind == "saved_decision":
        (root / "checks/review/result.json").write_text('{"decision":"forged"}')
    elif kind == "frozen_input":
        (root / "inputs/data").write_text("{}")
    elif kind == "completion":
        (root / "checks/review/completion.json").write_text("{}")
    else:
        (root / "checks/observe/result.json").unlink()
    with pytest.raises((ValueError, OSError)):
        replay(case)


def test_output_reuse_is_forbidden(case):
    run(case)
    with pytest.raises(FileExistsError):
        run(case)


def test_implementation_bytes_change_forces_run(case):
    dependency = case["evidence_root"] / "adapter.txt"
    dependency.write_text("version1")
    case["implementation_files"].append(dependency)
    first = run(case, "first")
    dependency.write_text("version2")
    result = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert all(row["action"] == "run" for row in result["attempts"])


def test_cli_review_never_calls_handlers(case, monkeypatch, capsys):
    from nisayon.qualification.cli import main

    run(case)
    monkeypatch.setattr(
        "sys.argv",
        [
            "nisayon-qualify",
            "review-checks",
            str(case["evidence_root"] / "run"),
            "--evidence-root",
            str(case["evidence_root"]),
        ],
    )
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified_execution_records"


def test_system_exit_leaves_unresolved_completion(case):
    def stop(ctx):
        raise SystemExit(9)

    case["handlers"]["observe"] = stop
    with pytest.raises(SystemExit):
        run(case)
    assert replay(case)["status"] == "unresolved"


def test_aggregate_input_limit_is_checked_before_any_execution(case, monkeypatch):
    monkeypatch.setattr("nisayon.qualification.checks.MAX_INPUT_BYTES", 64)
    with pytest.raises(ValueError, match="Aggregate"):
        run(case)
    assert not (case["evidence_root"] / "run").exists()
