"""Applicability controls: stale evidence cannot remove a required check."""

import copy
import json

import pytest

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.qualification import DependencyModel, EvidenceState, plan_applicability, record_check
from nisayon.qualification.applicability import MODEL_SCHEMA, STATE_SCHEMA


@pytest.fixture
def graph(tmp_path):
    definition = {
        "schema": MODEL_SCHEMA,
        "id": "normalization",
        "scope": "Declared software relation, trusted stateless native loader",
        "inputs": {
            key: {"kind": key if key != "documentation" else "other", "description": key}
            for key in (
                "code",
                "data",
                "runtime",
                "state",
                "scoring",
                "population",
                "documentation",
            )
        },
        "checks": {
            "observe": {
                "kind": "observation",
                "depends_on": ["code", "data", "runtime", "state"],
                "refresh": "on_change",
            },
            "score": {
                "kind": "analysis",
                "depends_on": ["observe", "scoring"],
                "refresh": "on_change",
            },
            "confirm": {
                "kind": "confirmation",
                "depends_on": ["code", "data", "runtime", "state", "scoring", "population"],
                "refresh": "always",
            },
            "review": {
                "kind": "review",
                "depends_on": ["score", "confirm"],
                "refresh": "on_change",
            },
        },
        "decisions": {"adoption": {"depends_on": ["review"], "description": "Software only"}},
        "review": None,
    }
    model = DependencyModel.from_dict(definition)
    write_json(
        tmp_path / "review.txt",
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": model.definition_sha256,
            "reviewer": "synthetic-control",
            "coverage": "reviewed_for_declared_scope",
            "statement": "Developer-reviewed synthetic control; not human approval",
        },
    )
    definition["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": "synthetic-control",
        "artifact": {"path": "review.txt", "sha256": file_digest(tmp_path / "review.txt")},
    }
    model = DependencyModel.from_dict(definition)
    inputs = {key: digest(key) for key in definition["inputs"]}
    state = EvidenceState.from_dict(
        {"schema": STATE_SCHEMA, "model_sha256": model.sha256, "inputs": inputs, "checks": {}}
    )
    for key in ("observe", "score", "confirm", "review"):
        write_json(tmp_path / f"{key}.json", {"check": key, "decision": "reject"})
        state = record_check(model, state, key, evidence_root=tmp_path, artifact=f"{key}.json")
    return model, state, inputs, tmp_path


def plan(graph, **changes):
    model, state, inputs, root = graph
    return plan_applicability(model, state, inputs | changes, evidence_root=root)


def actions(result):
    return {key: item["action"] for key, item in result["checks"].items()}


def test_unchanged_rejected_observations_are_reusable_but_not_acceptance(graph):
    result = plan(graph)
    assert actions(result) == {
        "observe": "reuse",
        "score": "reuse",
        "confirm": "run",
        "review": "run",
    }
    assert result["automatic_acceptance"] is False
    assert result["decisions"]["adoption"]["applicability"] == "requires_checks"
    assert "fresh_check_required" in result["checks"]["confirm"]["reasons"]


def test_rescoring_does_not_relabel_old_observations(graph):
    result = plan(graph, scoring=digest("strict"))
    assert actions(result) == {
        "observe": "reuse",
        "score": "run",
        "confirm": "run",
        "review": "run",
    }
    assert {"input": "scoring", "reason": "changed", "via": "scoring"} in result["checks"]["score"][
        "affected_inputs"
    ]


@pytest.mark.parametrize("key", ["code", "data", "runtime", "state"])
def test_execution_dependencies_propagate_transitively(graph, key):
    result = plan(graph, **{key: digest("changed")})
    assert set(actions(result).values()) == {"run"}
    assert {"input": key, "reason": "changed", "via": "observe"} in result["checks"]["score"][
        "affected_inputs"
    ]


def test_population_change_requires_confirmation_without_erasing_history(graph):
    result = plan(graph, population=digest("new population"))
    assert result["checks"]["observe"]["action"] == "reuse"
    assert result["checks"]["confirm"]["affected_inputs"][0]["input"] == "population"


def test_unrelated_documentation_cannot_skip_fresh_confirmation(graph):
    assert actions(plan(graph, documentation=digest("new docs"))) == actions(plan(graph))


@pytest.mark.parametrize("key", ["code", "data", "runtime", "scoring", "population", "state"])
def test_unknown_is_not_unchanged(graph, key):
    result = plan(graph, **{key: None})
    assert result["status"] == "unresolved"
    assert result["decisions"]["adoption"]["applicability"] == "unresolved"
    assert f"unknown_input:{key}" in result["obligations"]


@pytest.mark.parametrize("key", ["observe", "score", "confirm"])
def test_altered_evidence_requires_recomputation(graph, key):
    (graph[3] / f"{key}.json").write_text("tampered")
    result = plan(graph)
    assert result["checks"][key]["action"] == "run"
    assert "artifact_bytes_changed" in result["checks"][key]["reasons"]
    assert result["checks"]["review"]["action"] == "run"


def test_relabeling_inputs_without_new_execution_does_not_rebind_receipts(graph):
    model, state, inputs, root = graph
    record = state.record()
    record["inputs"]["data"] = digest("new data")
    result = plan_applicability(
        model, EvidenceState.from_dict(record), record["inputs"], evidence_root=root
    )
    assert result["checks"]["observe"]["reasons"] == ["receipt_dependency_mismatch"]
    assert result["checks"]["score"]["action"] == "run"


def test_review_is_bound_to_the_exact_graph_and_retained_bytes(graph):
    model, state, inputs, root = graph
    value = model.record()
    value["checks"]["observe"]["depends_on"].remove("data")
    with pytest.raises(ValueError, match="Review does not bind"):
        DependencyModel.from_dict(value)
    (root / "review.txt").write_text("changed review")
    result = plan(graph)
    assert result["status"] == "unresolved"
    assert set(actions(result).values()) == {"run"}


def test_changed_model_requires_new_evidence_even_when_outputs_match(graph):
    model, state, inputs, root = graph
    value = model.record()
    value["scope"] = "Expanded declared scope"
    value["review"] = None
    new_model = DependencyModel.from_dict(value)
    value["review"] = model.record()["review"] | {"definition_sha256": new_model.definition_sha256}
    result = plan_applicability(DependencyModel.from_dict(value), state, inputs, evidence_root=root)
    assert result["status"] == "unresolved"
    assert "dependency_model_review_identity_mismatch" in result["obligations"]
    assert set(actions(result).values()) == {"run"}
    assert all("dependency_model_changed" in row["reasons"] for row in result["checks"].values())


def test_missing_population_edge_is_unresolved_even_with_a_declared_review(graph):
    model, state, inputs, root = graph
    value = model.record()
    value["checks"]["confirm"]["depends_on"].remove("population")
    value["review"] = None
    updated = DependencyModel.from_dict(value)
    value["review"] = model.record()["review"] | {"definition_sha256": updated.definition_sha256}
    result = plan_applicability(DependencyModel.from_dict(value), state, inputs, evidence_root=root)
    assert result["status"] == "unresolved"
    assert "uncovered_dependency_kind:population" in result["decisions"]["adoption"]["obligations"]


def test_no_confirmation_is_unresolved_and_confirmation_cannot_be_cached(graph):
    model, state, inputs, root = graph
    value = model.record()
    value["checks"]["confirm"]["refresh"] = "on_change"
    with pytest.raises(ValueError, match="Confirmation cannot be cached"):
        DependencyModel.from_dict(value)
    value["checks"]["confirm"]["kind"] = "analysis"
    value["review"] = None
    result = plan_applicability(DependencyModel.from_dict(value), state, inputs, evidence_root=root)
    assert "fresh_confirmation_not_declared" in result["decisions"]["adoption"]["obligations"]


@pytest.mark.parametrize("mutation", ["cycle", "unknown", "duplicate", "overlap"])
def test_malformed_graphs_are_rejected(graph, mutation):
    value = graph[0].record()
    if mutation == "overlap":
        value["checks"]["code"] = value["checks"].pop("observe")
    else:
        value["checks"]["observe"]["depends_on"].append(
            {"cycle": "score", "unknown": "absent", "duplicate": "data"}[mutation]
        )
    with pytest.raises(ValueError):
        DependencyModel.from_dict(value)


def test_missing_input_key_is_an_error_not_silently_irrelevant(graph):
    inputs = graph[2].copy()
    del inputs["population"]
    with pytest.raises(ValueError, match="exactly"):
        plan_applicability(graph[0], graph[1], inputs, evidence_root=graph[3])


def test_receipts_cannot_overwrite_or_consume_tampered_dependencies(graph):
    model, state, inputs, root = graph
    with pytest.raises(ValueError, match="overwrite"):
        record_check(model, state, "observe", evidence_root=root, artifact="observe.json")
    value = state.record()
    del value["checks"]["score"]
    (root / "observe.json").write_text("altered")
    with pytest.raises(ValueError, match="upstream"):
        record_check(
            model,
            EvidenceState.from_dict(value),
            "score",
            evidence_root=root,
            artifact="score.json",
        )


def test_symlink_artifacts_do_not_supply_reuse(graph):
    root = graph[3]
    (root / "observe.json").rename(root / "moved.json")
    (root / "observe.json").symlink_to(root / "moved.json")
    assert plan(graph)["checks"]["observe"]["action"] == "run"


def test_records_are_immutable_and_duplicate_json_keys_rejected(graph):
    original = graph[0].sha256
    altered = copy.deepcopy(graph[0].record())
    altered["inputs"].clear()
    assert graph[0].sha256 == original
    with pytest.raises(ValueError, match="Duplicate"):
        EvidenceState(b'{"schema":1,"schema":2}')


def test_changed_sdk_cannot_inherit_old_receipts(graph, monkeypatch):
    monkeypatch.setattr(
        "nisayon.qualification.applicability.tool_identity", lambda: {"changed": True}
    )
    result = plan(graph)
    assert set(actions(result).values()) == {"run"}
    assert "receipt_dependency_mismatch" in result["checks"]["observe"]["reasons"]


def test_missing_receipt_is_explicit(graph):
    model, state, inputs, root = graph
    value = state.record()
    del value["checks"]["observe"]
    result = plan_applicability(model, EvidenceState.from_dict(value), inputs, evidence_root=root)
    assert result["checks"]["observe"]["reasons"] == ["missing_receipt"]
    assert result["checks"]["score"]["action"] == "run"


def test_review_read_is_bound_to_consumed_bytes(graph, monkeypatch):
    from nisayon.qualification import applicability

    original = applicability._artifact_bytes

    def changed(root, name):
        raw = original(root, name)
        if name == "review.txt":
            record = json.loads(raw)
            record["coverage"] = "incomplete"
            return json.dumps(record).encode()
        return raw

    monkeypatch.setattr(applicability, "_artifact_bytes", changed)
    result = plan(graph)
    assert result["status"] == "unresolved"
    assert "dependency_model_review_bytes_changed" in result["obligations"]


def test_cli_matches_sdk_and_unknown_is_nonzero(graph, monkeypatch, capsys):
    from nisayon.qualification.cli import main

    model, state, inputs, root = graph
    write_json(root / "model.json", model.record())
    write_json(root / "state.json", state.record())
    write_json(root / "inputs.json", inputs | {"population": None})
    monkeypatch.setattr(
        "sys.argv",
        [
            "nisayon-qualify",
            "applicability",
            str(root / "model.json"),
            str(root / "state.json"),
            str(root / "inputs.json"),
            "--evidence-root",
            str(root),
        ],
    )
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code == 3
    assert json.loads(capsys.readouterr().out) == plan(graph, population=None)
