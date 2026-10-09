"""Coverage failures must not turn omitted or misbound evidence into agreement."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nisayon.engine.io import digest
from nisayon.engine.temporal_audit import CoverageError, declared_pairs, owner_index

ROOT = Path(__file__).resolve().parents[2]
COVERAGE = json.loads(
    (
        ROOT / "docs/experiments/results/temporal-integration-001/frozen-audit-coverage.v1.json"
    ).read_bytes()
)


@pytest.fixture
def delivery():
    source = {"assessment_schema": "test-assessment", "module_sha256": "test-source"}
    manifest = {
        "schema": "nisayon.temporal-followthrough-reassessment.v1",
        "source": copy.deepcopy(source),
        "populations": [],
    }
    full = {}
    for population in [*COVERAGE["populations"], COVERAGE["prefix_population"]]:
        rows, results = [], []
        for member in population["members"]:
            assignment = member["assignment"]
            assessment = {"schema": "test-assessment", "case_id": assignment["case_id"]}
            rows.append(
                {
                    "assignment_id": member["identity"],
                    "case_id": assignment["case_id"],
                    "remedy_id": assignment["remedy_id"],
                    "trace_sha256": member["trace_sha256"],
                    "trace_canonical_sha256": member["trace_sha256"],
                    "assessment_sha256": digest(assessment),
                }
            )
            results.append({"assignment_id": member["identity"], "assessment": assessment})
        name = population["owner_population"]
        manifest["populations"].append(
            {
                "name": name,
                "expected": len(rows),
                "count": len(rows),
                "complete": True,
                "rows": rows,
            }
        )
        full[name] = results
    return manifest, full, source


def test_complete_frozen_membership_and_actual_combined_pair(delivery):
    manifest, full, source = delivery
    indexed = owner_index(COVERAGE, manifest, full, source)
    assert len(indexed) == 233
    assert sum(len(p["members"]) for p in COVERAGE["populations"]) == 230
    assert len(COVERAGE["prefix_population"]["members"]) == 3
    pairs = []
    for population in COVERAGE["populations"]:
        suite = json.loads((ROOT / population["frozen_suite"]["path"]).read_bytes())
        assert declared_pairs(suite) == population["required_pairs"]
        pairs.extend((population["name"], pair) for pair in population["required_pairs"])
    assert len(pairs) == 35
    combined = [p for name, p in pairs if name == "combined_deadline"]
    assert len(combined) == 6
    assert all(p["conventional"].endswith("--conventional_combined_deadline") for p in combined)
    assert all(p["selected"].endswith("--selected_combined_deadline") for p in combined)


@pytest.mark.parametrize("missing", ["population", "file", "member"])
def test_owner_omission_names_the_missing_coverage(delivery, missing):
    manifest, full, source = delivery
    population = next(p for p in manifest["populations"] if p["name"] == "combined_deadline")
    if missing == "population":
        manifest["populations"].remove(population)
    elif missing == "file":
        del full["combined_deadline"]
    else:
        absent = population["rows"].pop()
    with pytest.raises(CoverageError) as caught:
        owner_index(COVERAGE, manifest, full, source)
    detail = caught.value.details
    assert detail["missing"]
    if missing == "member":
        assert detail["missing"] == [absent["assignment_id"]]
    else:
        assert len(detail["missing"]) == 24
        assert all(identity[0] == "combined_deadline" for identity in detail["missing"])


@pytest.mark.parametrize("where", ["metadata", "full", "population"])
def test_duplicate_rows_are_rejected_before_lookup(delivery, where):
    manifest, full, source = delivery
    if where == "metadata":
        rows = manifest["populations"][0]["rows"]
    elif where == "full":
        rows = full["original"]
    else:
        rows = manifest["populations"]
    rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(CoverageError) as caught:
        owner_index(COVERAGE, manifest, full, source)
    assert caught.value.details["duplicates"]


def test_extra_row_is_not_a_new_implicit_assignment(delivery):
    manifest, full, source = delivery
    extra = copy.deepcopy(full["original"][0])
    extra["assignment_id"] = "unassigned"
    full["original"].append(extra)
    with pytest.raises(CoverageError) as caught:
        owner_index(COVERAGE, manifest, full, source)
    assert caught.value.details["extra"] == ["unassigned"]


def test_same_case_name_in_different_population_does_not_alias(delivery):
    manifest, full, source = delivery
    identity = "T14-deadline-equality--conventional"
    original = next(p for p in manifest["populations"] if p["name"] == "original")
    combined = next(p for p in manifest["populations"] if p["name"] == "combined_deadline")
    old = next(r for r in original["rows"] if r["assignment_id"] == identity)
    new = next(r for r in combined["rows"] if r["assignment_id"] == identity)
    assert old["trace_sha256"] != new["trace_sha256"]
    new.update(copy.deepcopy(old))
    with pytest.raises(CoverageError, match="owner_input_or_result_binding"):
        owner_index(COVERAGE, manifest, full, source)


def test_wrong_owner_source_is_not_an_accepted_older_result(delivery):
    manifest, full, source = delivery
    manifest["source"]["module_sha256"] = "older-source"
    with pytest.raises(CoverageError, match="owner_source_mismatch"):
        owner_index(COVERAGE, manifest, full, source)


def test_raw_file_hash_without_verified_content_binding_is_insufficient(delivery):
    manifest, full, source = delivery
    del manifest["populations"][0]["rows"][0]["trace_canonical_sha256"]
    with pytest.raises(CoverageError, match="owner_input_or_result_binding"):
        owner_index(COVERAGE, manifest, full, source)


def test_full_result_case_binding_cannot_be_rewritten(delivery):
    manifest, full, source = delivery
    row = full["original"][0]
    row["assessment"]["case_id"] = "different-case"
    meta = manifest["populations"][0]["rows"][0]
    meta["assessment_sha256"] = digest(row["assessment"])
    with pytest.raises(CoverageError, match="owner_input_or_result_binding"):
        owner_index(COVERAGE, manifest, full, source)
