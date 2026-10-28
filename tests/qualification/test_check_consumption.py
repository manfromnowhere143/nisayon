"""A verified check readback must consume exactly its receipt-bound result."""

import json
from pathlib import Path

import pytest

from nisayon.engine.io import canonical_bytes, file_digest, write_json
from nisayon.qualification import (
    CheckImplementation,
    DependencyModel,
    EvidenceState,
    checks,
    execute_checks,
    export_checks,
    inspect_check_bundle,
    inspect_checks,
)


def confirm(ctx):
    return {"holds": ctx.input("data")["value"] <= ctx.input("scoring")["limit"]}


def review(ctx):
    holds = ctx.input("data")["value"] <= ctx.input("scoring")["limit"]
    return {"decision": "supported" if holds else "rejected"}


@pytest.fixture(params=["conservative", "scoped"])
def case(tmp_path, request):
    root = tmp_path / "evidence"
    root.mkdir()
    kinds = {
        "procedure": "protocol",
        "code": "code",
        "data": "data",
        "scoring": "scoring",
        "runtime": "runtime",
        "population": "population",
    }
    definition = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "result-consumption-control",
        "scope": "Two independent software checks, not physical confirmation",
        "inputs": {key: {"kind": kind, "description": key} for key, kind in kinds.items()},
        "checks": {
            "confirm": {
                "kind": "confirmation",
                "depends_on": list(kinds),
                "refresh": "always",
            },
            "review": {
                "kind": "review",
                "depends_on": list(kinds),
                "refresh": "on_change",
            },
        },
        "decisions": {
            "relation": {
                "depends_on": ["confirm", "review"],
                "description": "Both declared checks are required",
            }
        },
        "review": None,
    }
    model = DependencyModel.from_dict(definition)
    witness = root / "review.json"
    write_json(
        witness,
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": model.definition_sha256,
            "reviewer": "constructed-control",
            "coverage": "reviewed_for_declared_scope",
            "statement": "Authored software control, not independent adjudication",
        },
    )
    definition["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": "constructed-control",
        "artifact": {"path": "review.json", "sha256": file_digest(witness)},
    }
    scoped = request.param == "scoped"
    inputs = {}
    for key in kinds.keys() - {"procedure", *(["code"] if scoped else [])}:
        inputs[key] = root / f"{key}.json"
        write_json(inputs[key], {"value": 10, "limit": 9})
    return {
        "model": DependencyModel.from_dict(definition),
        "inputs": inputs,
        "handlers": {"confirm": confirm, "review": review},
        "implementation_files": [Path(__file__)],
        "check_implementations": (
            {name: CheckImplementation(input_key="code") for name in ("confirm", "review")}
            if scoped
            else None
        ),
        "evidence_root": root,
    }


def produce(case, reused=False):
    root = case["evidence_root"]
    first = execute_checks(**case, output=root / "first")
    if not reused:
        return root / "first", first
    report = execute_checks(
        **case, output=root / "second", previous=EvidenceState.from_dict(first["state"])
    )
    assert {row["check"]: row["action"] for row in report["attempts"]} == {
        "confirm": "run",
        "review": "reuse",
    }
    return root / "second", report


def replace_after_receipt(monkeypatch, target, after_read=False):
    original = checks.record_check
    original_read = checks._artifact_bytes
    replacement = {"holds": True} if target == "confirm" else {"decision": "supported"}
    armed = {}
    mutations = []

    def mutate(path):
        path.write_bytes(canonical_bytes(replacement) + b"\n")
        mutations.append(path)

    def bind(model, state, key, **kwargs):
        result = original(model, state, key, **kwargs)
        if key == target:
            path = kwargs["evidence_root"] / kwargs["artifact"]
            if after_read:
                armed["path"] = path
            else:
                mutate(path)
        return result

    def read(root, name):
        raw = original_read(root, name)
        if root / name == armed.pop("path", None):
            mutate(root / name)
        return raw

    monkeypatch.setattr(checks, "record_check", bind)
    if after_read:
        monkeypatch.setattr(checks, "_artifact_bytes", read)
    return mutations


@pytest.mark.parametrize("reused", [False, True])
@pytest.mark.parametrize("target", ["confirm", "review"])
def test_replacement_after_receipt_cannot_return_verified_claim(case, monkeypatch, reused, target):
    output, report = produce(case, reused)
    mutations = replace_after_receipt(monkeypatch, target)
    with pytest.raises(ValueError, match="Check result changed before consumption"):
        inspect_checks(evidence_root=case["evidence_root"], output=output)
    assert mutations
    assert file_digest(mutations[0]) != report["state"]["checks"][target]["artifact"]["sha256"]


@pytest.mark.parametrize("reused", [False, True])
@pytest.mark.parametrize("supported", [False, True])
def test_valid_positive_and_negative_claims_survive_local_and_portable_readback(
    case, reused, supported
):
    case["inputs"]["scoring"].write_text(json.dumps({"limit": 11 if supported else 9}))
    output, _ = produce(case, reused)
    local = inspect_checks(evidence_root=case["evidence_root"], output=output)
    assert local["status"] == "verified_execution_records"
    assert local["artifacts"]["confirm"]["holds"] is supported
    assert local["artifacts"]["review"]["decision"] == ("supported" if supported else "rejected")
    assert local["deployment_decision"] == "unresolved"
    root = case["evidence_root"]
    bundle = root.parent / (root.name + ".zip")
    export_checks(evidence_root=root, execution=output, output=bundle)
    portable = inspect_check_bundle(bundle)
    assert portable["review_status"] == "verified"
    assert portable["assessment"]["review"] == local


@pytest.mark.parametrize("reused", [False, True])
def test_result_is_decoded_from_the_same_bytes_that_were_checked(case, monkeypatch, reused):
    output, _ = produce(case, reused)
    mutations = replace_after_receipt(monkeypatch, "review", after_read=True)
    result = inspect_checks(evidence_root=case["evidence_root"], output=output)
    assert mutations
    assert result["status"] == "verified_execution_records"
    assert result["artifacts"]["review"]["decision"] == "rejected"
    assert json.loads(mutations[0].read_text()) == {"decision": "supported"}


def test_export_refuses_changed_result_in_its_staged_readback(case, monkeypatch):
    output, _ = produce(case)
    root = case["evidence_root"]
    mutations = replace_after_receipt(monkeypatch, "review")
    bundle = root.parent / (root.name + ".zip")
    with pytest.raises(ValueError, match="Check result changed before consumption"):
        export_checks(evidence_root=root, execution=output, output=bundle)
    assert mutations
    assert not bundle.exists()
    assert json.loads((output / "checks/review/result.json").read_text()) == {
        "decision": "rejected"
    }
