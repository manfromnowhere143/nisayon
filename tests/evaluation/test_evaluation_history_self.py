"""A record's own retained decision in the history is not a prior use of its conditions.

The execution lane copies every retained decision into the history it passes to the
evaluator. Re-evaluating an already-decided confirmation under that history must reach
the same decision; only another execution that spends the same conditions is reuse.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import read_document, write_document
from nisayon.evaluation.fixtures import scenario, write_scenario

REPO = Path(__file__).resolve().parents[2]
FRESHNESS = REPO / "docs/experiments/results/lift-freshness-001"
needs_freshness = pytest.mark.skipif(
    not (FRESHNESS / "bundle.json.gz").is_file(), reason="lift-freshness-001 record absent"
)


def reasons(decision: dict) -> set[str]:
    return {r["code"] for r in decision["reasons"]}


def notes(decision: dict) -> set[str]:
    return {n["code"] for n in decision["notes"]}


def place(folder: Path, mutate=None) -> Path:
    document = read_document(FRESHNESS / "bundle.json.gz")
    if mutate is not None:
        mutate(document)
    folder.mkdir(parents=True, exist_ok=True)
    path = write_document(document, folder / "bundle.json")
    shutil.copy(FRESHNESS / "frozen-protocol.json", folder / "frozen-protocol.json")
    shutil.copy(FRESHNESS / "artifact-manifest.json", folder / "artifact-manifest.json")
    return path


def retain(decision: dict, folder: Path, name: str = "first") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.decision.json"
    path.write_text(json.dumps(decision, indent=2))
    return path


@needs_freshness
def test_own_decision_in_history_is_not_reuse(tmp_path):
    path = place(tmp_path / "record")
    first = evaluate_bundle(path)
    assert first["bundle_sha256"].startswith("sha256:")
    assert "confirmation_condition_reused" not in reasons(first)
    retain(first, tmp_path / "history")
    second = evaluate_bundle(path, history=[tmp_path / "history"])
    assert reasons(second) == reasons(first)
    assert second["decision"] == first["decision"]
    assert "history_contains_this_record" in notes(second)
    assert "history_absent" not in notes(second)
    assert second["bundle_sha256"] == first["bundle_sha256"]


@needs_freshness
def test_reexecution_under_the_same_frozen_protocol_reuses_its_conditions(tmp_path):
    first = evaluate_bundle(place(tmp_path / "record"))
    retain(first, tmp_path / "history")

    def rerun(document):
        # Another execution of the same frozen protocol: same runs, different measurements.
        for run in document["runs"]:
            for cost in run.get("costs") or []:
                if cost.get("value") is not None:
                    cost["value"] = round(cost["value"] * 1.01, 9)

    again = evaluate_bundle(place(tmp_path / "again", rerun), history=[tmp_path / "history"])
    assert again["decision"] == "invalid"
    assert "confirmation_condition_reused" in reasons(again)
    assert "history_contains_this_record" not in notes(again)


@needs_freshness
def test_decision_without_bundle_digest_matches_by_path_or_protocol(tmp_path):
    path = place(tmp_path / "record")
    first = evaluate_bundle(path)
    del first["bundle_sha256"]  # a decision retained before bundle digests existed
    retain(first, tmp_path / "history")
    second = evaluate_bundle(path, history=[tmp_path / "history"])
    assert "confirmation_condition_reused" not in reasons(second)
    assert "history_contains_this_record" in notes(second)
    # A digest-less decision also covers the same frozen protocol evaluated elsewhere; it
    # cannot tell a re-execution under the same freeze apart, which is why digests exist.
    first["bundle"] = "/nowhere/bundle.json"
    retain(first, tmp_path / "history")
    copied = evaluate_bundle(place(tmp_path / "copy"), history=[tmp_path / "history"])
    assert "confirmation_condition_reused" not in reasons(copied)
    assert "history_contains_this_record" in notes(copied)


@needs_freshness
def test_a_confirmation_decided_later_is_not_prior_consumption(tmp_path):
    path = place(tmp_path / "record")
    first = evaluate_bundle(path)
    retain(first, tmp_path / "history")
    other = json.loads(json.dumps(first))
    other["bundle_sha256"] = "sha256:" + "ee" * 32
    other["bundle"] = "/elsewhere/bundle.json"
    other["confirmation"]["protocol"]["producer_protocol_sha256"] = "ff" * 32
    other["decided_at"] = "2026-09-19T00:00:00+00:00"  # after this record's decision
    retain(other, tmp_path / "history", "other")
    decision = evaluate_bundle(path, history=[tmp_path / "history"])
    assert "confirmation_condition_reused" not in reasons(decision)
    assert "protocol_mismatch" not in reasons(decision)
    assert "history_later_records" in notes(decision)
    assert "history_absent" not in notes(decision)
    other["decided_at"] = "2026-09-01T00:00:00+00:00"  # before this record's decision
    retain(other, tmp_path / "history", "other")
    decision = evaluate_bundle(path, history=[tmp_path / "history"])
    assert decision["decision"] == "invalid"
    assert "confirmation_condition_reused" in reasons(decision)


@needs_freshness
def test_declared_freeze_times_order_only_decisions_that_predate_decision_stamps(tmp_path):
    path = place(tmp_path / "record")
    first = evaluate_bundle(path)
    del first["decided_at"]
    retain(first, tmp_path / "history")
    other = json.loads(json.dumps(first))
    other["bundle_sha256"] = "sha256:" + "ee" * 32
    other["bundle"] = "/elsewhere/bundle.json"
    other["confirmation"]["protocol"]["producer_protocol_sha256"] = "ff" * 32
    other["confirmation"]["frozen_at"] = "2026-09-19T00:00:00+00:00"
    retain(other, tmp_path / "history", "other")
    decision = evaluate_bundle(path, history=[tmp_path / "history"])
    assert "confirmation_condition_reused" not in reasons(decision)
    assert "history_later_records" in notes(decision)
    other["confirmation"]["frozen_at"] = "2026-09-01T00:00:00+00:00"
    retain(other, tmp_path / "history", "other")
    decision = evaluate_bundle(path, history=[tmp_path / "history"])
    assert "confirmation_condition_reused" in reasons(decision)


@needs_freshness
def test_a_first_evaluation_counts_every_entry_whatever_its_declared_freeze(tmp_path):
    """A backdated re-execution: its freeze is declared earlier than the original's, but
    the original was decided first and this record has no decision of its own yet."""
    original = evaluate_bundle(place(tmp_path / "original"))
    retain(original, tmp_path / "history")

    def backdate(document):
        document["confirmation"]["frozen_at"] = "2026-09-01T00:00:00+00:00"

    folder = tmp_path / "backdated"
    path = place(folder, backdate)
    frozen = json.loads((folder / "frozen-protocol.json").read_text())
    frozen["frozen_at"] = "2026-09-01T00:00:00+00:00"
    (folder / "frozen-protocol.json").write_text(json.dumps(frozen))
    from nisayon.evaluation.first_case import producer_digest

    document = read_document(path)
    document["confirmation"]["protocol_sha256"] = producer_digest(frozen)
    write_document(document, path)
    decision = evaluate_bundle(path, history=[tmp_path / "history"])
    assert decision["decision"] == "invalid"
    assert "confirmation_condition_reused" in reasons(decision)
    assert "history_later_records" not in notes(decision)
    # Retaining that invalid decision and evaluating again does not launder it.
    retain(decision, tmp_path / "history", "backdated")
    again = evaluate_bundle(path, history=[tmp_path / "history"])
    assert again["decision"] == "invalid"
    # The original, re-evaluated with the backdated record's later decision in history,
    # is unchanged.
    original_again = evaluate_bundle(
        tmp_path / "original/bundle.json", history=[tmp_path / "history"]
    )
    assert reasons(original_again) == reasons(original)
    assert "history_later_records" in notes(original_again)


@needs_freshness
def test_the_bundle_file_itself_as_history_is_not_reuse(tmp_path):
    path = place(tmp_path / "record")
    decision = evaluate_bundle(path, history=[path])
    assert "confirmation_condition_reused" not in reasons(decision)
    assert "history_contains_this_record" in notes(decision)


def test_native_positive_control_stays_accepted_under_its_own_decision(tmp_path):
    root = write_scenario(scenario("strict_positive_control"), tmp_path / "fixtures")
    first = evaluate_bundle(root)
    assert first["decision"] == "accepted"
    retain(first, tmp_path / "history")
    second = evaluate_bundle(root, history=[tmp_path / "history"])
    assert second["decision"] == "accepted"
    assert "history_contains_this_record" in notes(second)


@needs_freshness
def test_renaming_the_case_does_not_free_its_conditions(tmp_path):
    original = evaluate_bundle(place(tmp_path / "original"))
    assert original["task"]["policy_sha256"]
    retain(original, tmp_path / "history")

    def rename(document):
        document["case"]["id"] = "lift-gripper-sign-v9"
        for item in [*document["runs"], *document["plans"]]:
            item["case_id"] = "lift-gripper-sign-v9"

    renamed = evaluate_bundle(place(tmp_path / "renamed", rename), history=[tmp_path / "history"])
    assert renamed["case_id"] == "lift-gripper-sign-v9"
    assert "confirmation_condition_reused" in reasons(renamed)


@needs_freshness
def test_every_executed_run_in_the_history_spent_its_condition(tmp_path):
    """A history bundle whose declared condition list omits what its runs actually ran."""

    def misdeclare(document):
        document["confirmation"]["condition_ids"] = ["seed-9000"]

    misdeclared = place(tmp_path / "misdeclared", misdeclare)
    decision = evaluate_bundle(place(tmp_path / "record"), history=[misdeclared])
    assert decision["decision"] == "invalid"
    assert "confirmation_condition_reused" in reasons(decision)


@needs_freshness
def test_a_stamped_re_evaluation_beside_a_legacy_decision_keeps_legacy_order(tmp_path):
    """v3's situation once its re-evaluation is retained: the original decision predates
    the stamps, a later legacy reuse is ordered by freeze time, and any stamped entry was
    decided after the original."""
    path = place(tmp_path / "record")
    stamped = evaluate_bundle(path)
    legacy = json.loads(json.dumps(stamped))
    del legacy["decided_at"]
    retain(legacy, tmp_path / "history", "legacy-self")
    retain(stamped, tmp_path / "history", "stamped-self")
    reuse = json.loads(json.dumps(legacy))
    reuse["bundle_sha256"] = "sha256:" + "ee" * 32
    reuse["bundle"] = "/elsewhere/bundle.json"
    reuse["confirmation"]["protocol"]["producer_protocol_sha256"] = "ff" * 32
    reuse["confirmation"]["frozen_at"] = "2026-09-19T00:00:00+00:00"
    retain(reuse, tmp_path / "history", "legacy-reuse")
    stamped_reuse = json.loads(json.dumps(reuse))
    stamped_reuse["bundle_sha256"] = "sha256:" + "dd" * 32
    stamped_reuse["decided_at"] = "2026-09-01T00:00:00+00:00"
    retain(stamped_reuse, tmp_path / "history", "stamped-reuse")
    decision = evaluate_bundle(path, history=[tmp_path / "history"])
    assert "confirmation_condition_reused" not in reasons(decision)
    assert "history_contains_this_record" in notes(decision)
    assert any(
        "2 history entries were decided after" in n["detail"]
        for n in decision["notes"]
        if n["code"] == "history_later_records"
    )


@needs_freshness
def test_decision_records_the_history_it_was_made_under(tmp_path):
    path = place(tmp_path / "record")
    first = evaluate_bundle(path)
    assert first["history"] == {
        "paths": [],
        "consumed_condition_count": 0,
        "own_entries": [],
        "later_entries": [],
        "unreadable": [],
    }
    retain(first, tmp_path / "history")
    second = evaluate_bundle(path, history=[tmp_path / "history", tmp_path / "missing.json"])
    assert second["history"]["paths"] == [str(tmp_path / "history"), str(tmp_path / "missing.json")]
    assert second["history"]["own_entries"] == [str(tmp_path / "history/first.decision.json")]
    assert second["history"]["unreadable"] == [f"{tmp_path / 'missing.json'}: missing"]
    assert second["history"]["consumed_condition_count"] == 0


@needs_freshness
def test_a_history_directory_expands_to_its_bundles_as_well_as_its_decisions(tmp_path):
    """The execution lane binds its history as a directory of copied decisions and
    compressed bundles; a bundle's consumed conditions must not be dropped."""
    history = tmp_path / "history"
    history.mkdir()
    shutil.copy(FRESHNESS / "bundle.json.gz", history / "03-bundle.json.gz")

    def rerun_measurements(document):
        # The same frozen protocol executed again: same runs, different measurements.
        for run in document["runs"]:
            for cost in run.get("costs") or []:
                if cost.get("value") is not None:
                    cost["value"] = round(cost["value"] * 1.01, 9)

    rerun = place(tmp_path / "rerun", rerun_measurements)
    decision = evaluate_bundle(rerun, history=[history])
    assert decision["decision"] == "invalid"
    assert "confirmation_condition_reused" in reasons(decision)
    assert decision["history"]["consumed_condition_count"] >= 32
