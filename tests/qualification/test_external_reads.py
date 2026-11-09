"""Observed external inputs cannot silently inherit a native software verdict."""

import json
import os
from pathlib import Path

import pytest

from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    assess_reuse,
    evidence_at,
    export_run,
    inspect_bundle,
    inspect_run,
    plan_change,
)

from .test_native_qualification import execute
from .test_owner_reads import add_candidate_read


@pytest.mark.parametrize("kind", ["direct", "missing", "import", "alias"])
def test_unbound_external_reads_prevent_acceptance_and_reuse(native, tmp_path, kind):
    external = tmp_path / "external-calibration.json"
    external.write_text("0")
    path = external
    if kind == "alias":
        path = tmp_path / "external-alias.json"
        path.symlink_to(external)
    body = f"Path({str(path)!r}).read_text()"
    if kind == "missing":
        external.unlink()
        body = f"try:\n    {body}\nexcept FileNotFoundError:\n    pass"
    _, context = add_candidate_read(native, "pass" if kind == "import" else body)
    if kind == "import":
        source = context.project / "policy.py"
        source.write_text(source.read_text() + f"\nEXTERNAL = {body}\n")
    case, _, evidence, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert "unbound_external_read:candidate-offset" in result["obligations"]
    witness = json.loads((evidence.root / "candidate-offset/observation.json").read_text())[
        "read_witness"
    ]
    assert witness["outside_owner_reads"] >= 1
    assert str(path) not in json.dumps(witness)
    external.write_text("5")
    proposed = plan_change(
        case, context=ExecutionContext.from_project(context.project, output_dir=tmp_path / "next")
    )
    assert assess_reuse(evidence, proposed)["verdict_applicability"] == "unresolved"
    bundle = tmp_path / "external.zip"
    export_run(evidence.root, bundle)
    portable = inspect_bundle(bundle)
    assert portable["review_status"] == "verified"
    assert portable["software_decision"] == "unresolved"


def test_standard_library_imports_remain_supported(native):
    add_candidate_read(
        native,
        "import fractions\nassert fractions.Fraction(1, 2) * 2 == 1\n"
        "Path(fractions.__file__).read_bytes()",
    )
    _, _, evidence, result = execute(native)
    assert result["software_decision"] == "adopt"
    witness = json.loads((evidence.root / "candidate-offset/observation.json").read_text())[
        "read_witness"
    ]
    assert witness["environment_reads"] > 0
    assert witness["outside_owner_reads"] == 0


def test_materialized_worker_cache_is_not_an_unbound_input_exemption(native):
    add_candidate_read(
        native,
        "import sys\ncache = Path(sys.pycache_prefix)\ncache.mkdir(parents=True)\n"
        "data = cache / 'calibration.pyc'\ndata.write_text('0')\ndata.read_text()",
    )
    _, _, _, result = execute(native)
    assert result["software_decision"] == "unresolved"


def test_legacy_external_read_evidence_keeps_its_original_scope(native, tmp_path):
    from nisayon.qualification.models import LEGACY_READ_POLICY, READ_POLICY

    legacy = Path(__file__).parent / "fixtures/external-reads-v1"
    result = inspect_run(legacy).record()
    assert result["software_decision"] == "adopt"
    assert result["read_policy"] == LEGACY_READ_POLICY
    proposed = plan_change(CaseSpec.from_dict(native[0]), context=native[1])
    assert proposed.record()["read_policy"] == READ_POLICY
    reuse = assess_reuse(evidence_at(legacy), proposed)
    assert reuse["verdict_applicability"] == "inapplicable"
    assert "read_policy" in reuse["changed_dependencies"]
    bundle = tmp_path / "legacy.zip"
    export_run(legacy, bundle)
    portable = inspect_bundle(bundle)
    assert portable["review_status"] == "verified"
    assert portable["assessment"]["read_policy"] == LEGACY_READ_POLICY


def test_legacy_witness_cannot_be_promoted_to_the_stricter_policy():
    from nisayon.qualification.reads import READ_SCHEMA, check_read_witness

    legacy = Path(__file__).parent / "fixtures/external-reads-v1"
    witness = json.loads((legacy / "candidate-offset/observation.json").read_text())["read_witness"]
    sources = json.loads((legacy / "plan.json").read_text())["sources"]
    with pytest.raises(ValueError):
        check_read_witness(witness, sources, "policy.py")
    witness.update(schema=READ_SCHEMA, bytecode_cache_misses=0)
    assert check_read_witness(witness, sources, "policy.py") == ["unbound_external_read"]


@pytest.mark.parametrize("location", ["outside", "inside", "ancestor", "declared", "escape"])
def test_library_exemption_does_not_hide_owner_data_or_escaping_aliases(tmp_path, location):
    from nisayon.qualification.reads import OwnerReadWitness

    owner = tmp_path / "owner"
    owner.mkdir()
    library = owner / "venv" if location in {"inside", "declared"} else tmp_path / "library"
    if location == "ancestor":
        library = tmp_path
    library.mkdir(exist_ok=True)
    path = owner / "data.json" if location == "ancestor" else library / "data.json"
    path.write_text("0")
    if location == "escape":
        outside = tmp_path / "unbound.json"
        outside.write_text("0")
        path.unlink()
        path.symlink_to(outside)
    declared = {path.relative_to(owner).as_posix(): "0" * 64} if location == "declared" else {}
    witness = OwnerReadWitness(owner, declared, [str(library)])
    witness.active = True
    witness._audit("open", (str(path), "r", os.O_RDONLY))
    witness.active = False
    assert witness.counts["environment_reads"] == (1 if location in {"inside", "outside"} else 0)
    assert witness.counts["outside_owner_reads"] == (1 if location == "escape" else 0)
    assert bool(witness.reads) == (location in {"ancestor", "declared"})


@pytest.mark.parametrize("alias", [False, True])
def test_preexisting_bytecode_cache_cannot_supply_undeclared_state(tmp_path, alias):
    from nisayon.qualification.reads import OwnerReadWitness

    cache = tmp_path / "cache"
    cache.mkdir()
    if alias:
        linked = tmp_path / "alias"
        linked.symlink_to(cache, target_is_directory=True)
        cache = linked
    with pytest.raises(ValueError, match="cache must be absent"):
        with OwnerReadWitness(tmp_path, {}, [], bytecode_cache=cache):
            pytest.fail("Existing cache must fail before executing owner code")


def test_same_claim_and_fresh_confirmation_keep_their_existing_contract(native):
    from nisayon.qualification import inspect_change, qualify_change

    declaration, context = native
    confirmation = json.loads(json.dumps(declaration))
    confirmation["id"] = "confirmation"
    confirmation["probes"] = [
        {"id": "fresh", "input": {"position": [15]}, "expected": {"action": [0.5]}}
    ]
    result = qualify_change(
        CaseSpec.from_dict(declaration),
        CaseSpec.from_dict(confirmation),
        project=context.project,
        output=context.output_dir,
        condition_store=context.output_dir.parent / "conditions",
    )
    assert result["software_decision"] == "adopt"
    assert result["deployment_decision"] == "unresolved"
    assert inspect_change(context.output_dir)["new_native_attempts"] == 6
