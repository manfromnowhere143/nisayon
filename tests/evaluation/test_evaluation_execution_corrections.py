"""The five evaluator corrections the execution lane named at ``93a5b0a``.

Each test works on a copy of a committed record written to a temporary directory.
Prefix-index and cost-parent checks use the D05 diagnostic bundle from
``development-baseline-qualification-001``; the per-run frozen configuration check
turns the v3 ``lift-freshness-001`` protocol into a v4 one; the scorer checks use
the retained labelled missing-decision ledger and the scoring fixtures.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import producer_digest, read_document, write_document
from nisayon.evaluation.schema import digest_of
from nisayon.evaluation.scoring import score_comparison, score_file
from nisayon.evaluation.scoring_fixtures import fair_ledger, write_ledger

REPO = Path(__file__).resolve().parents[2]
D05 = (
    REPO
    / "docs/experiments/results/development-baseline-qualification-001/D05-recurrent-carry/execution"
)
FRESHNESS = REPO / "docs/experiments/results/lift-freshness-001"
BOUNDARY = REPO / "docs/experiments/results/scoring-boundary-001"

needs_d05 = pytest.mark.skipif(not (D05 / "bundle.json.gz").is_file(), reason="D05 record absent")
needs_freshness = pytest.mark.skipif(
    not (FRESHNESS / "bundle.json.gz").is_file(), reason="lift-freshness-001 record absent"
)
needs_boundary = pytest.mark.skipif(
    not (BOUNDARY / "labelled-ledger.json").is_file(), reason="labelled ledger absent"
)


@pytest.fixture(scope="module")
def d05() -> dict:
    return read_document(D05 / "bundle.json.gz")


@pytest.fixture(scope="module")
def freshness() -> tuple[dict, dict]:
    return read_document(FRESHNESS / "bundle.json.gz"), json.loads(
        (FRESHNESS / "frozen-protocol.json").read_text()
    )


def run_named(document: dict, run_id: str) -> dict:
    return next(r for r in document["runs"] if r["id"] == run_id)


def codes_of(run: dict) -> set[str]:
    return {f["code"] for f in run["findings"]}


def details(run: dict, code: str) -> list[str]:
    return [f["detail"] for f in run["findings"] if f["code"] == code]


def d05_variant(source: dict, folder: Path, mutate=None) -> Path:
    document = copy.deepcopy(source)
    if mutate is not None:
        mutate(document)
    folder.mkdir(parents=True, exist_ok=True)
    return write_document(document, folder / "bundle.json")


# --- 1. prefix index: a count and a zero-based index are different numbers ----------------


@needs_d05
def test_last_row_index_of_a_21_row_prefix_is_20_not_a_mismatch(d05, tmp_path):
    regression = run_named(d05, "regression-0")
    assert regression["policy_state_reset"]["source_step"] == 20
    assert regression["prefix_run"]["steps"] == 21
    assert len(run_named(d05, "regression-0-prefix")["trace"]) == 21
    decision = evaluate_bundle(d05_variant(d05, tmp_path))
    run = decision["runs"]["regression-0"]
    assert run["measurement"] == "valid" and run["outcome"]["observed"] == "failed"
    assert "reset_carried_state" in codes_of(run), "carried state on the regression is measured"
    assert "reset_evidence_incomplete" not in codes_of(run)
    assert "trace_chain_broken" not in codes_of(run)
    assert decision["premises"] == {"reference_established": True, "regression_reproduced": True}
    assert decision["runs"]["regression-0-prefix"]["role"] == "probe"


@needs_d05
def test_declared_prefix_length_is_checked_against_the_row_count(d05, tmp_path):
    def shorten(document):
        run_named(document, "regression-0")["prefix_run"]["steps"] = 20

    run = evaluate_bundle(d05_variant(d05, tmp_path, shorten))["runs"]["regression-0"]
    assert run["measurement"] == "unresolved"
    assert any(
        "prefix_run.steps declares 20" in d for d in details(run, "reset_evidence_incomplete")
    )


@needs_d05
def test_source_index_that_is_not_the_last_row_is_incomplete(d05, tmp_path):
    def earlier(document):
        run_named(document, "regression-0")["policy_state_reset"]["source_step"] = 19

    run = evaluate_bundle(d05_variant(d05, tmp_path, earlier))["runs"]["regression-0"]
    assert any("not the last row (20)" in d for d in details(run, "reset_evidence_incomplete"))
    # The state carried is row 20's, not row 19's: the declared chain is broken as well.
    assert run["measurement"] == "invalid" and "trace_chain_broken" in codes_of(run)


@pytest.mark.parametrize("bad", [21, -1, "20", 20.0, True])
@needs_d05
def test_source_index_outside_the_prefix_is_incomplete(d05, tmp_path, bad):
    def out_of_range(document):
        run_named(document, "regression-0")["policy_state_reset"]["source_step"] = bad

    run = evaluate_bundle(d05_variant(d05, tmp_path, out_of_range))["runs"]["regression-0"]
    assert run["measurement"] == "unresolved"
    assert any("is not a row of prefix run" in d for d in details(run, "reset_evidence_incomplete"))


@needs_d05
def test_carried_state_that_is_not_the_source_row_state_breaks_the_chain(d05, tmp_path):
    def tamper(document):
        prefix = run_named(document, "regression-0-prefix")
        prefix["trace"][-1]["policy_state_after_sha256"] = "ab" * 32

    run = evaluate_bundle(d05_variant(d05, tmp_path, tamper))["runs"]["regression-0"]
    assert run["measurement"] == "invalid"
    assert "trace_chain_broken" in codes_of(run)


@needs_d05
def test_prefix_without_an_inline_trace_cannot_evidence_the_carry(d05, tmp_path):
    def strip(document):
        run_named(document, "regression-0-prefix")["trace"] = []

    run = evaluate_bundle(d05_variant(d05, tmp_path, strip))["runs"]["regression-0"]
    assert run["measurement"] == "unresolved"
    assert any(
        "has 0 rows; prefix_run.steps declares 21" in d
        for d in details(run, "reset_evidence_incomplete")
    )


@needs_d05
def test_undeclared_source_index_is_derived_from_the_last_executed_row(d05, tmp_path):
    def undeclared(document):
        run_named(document, "regression-0")["policy_state_reset"]["source_step"] = None

    decision = evaluate_bundle(d05_variant(d05, tmp_path, undeclared))
    run = decision["runs"]["regression-0"]
    assert run["measurement"] == "valid"
    assert any("step 20" in d for d in details(run, "reset_carried_state"))


# --- 4. cost parents: an executed prefix is inside its main run's wall ---------------------


@needs_d05
def test_prefix_costs_are_listed_under_their_parents_not_added(d05, tmp_path):
    costs = evaluate_bundle(d05_variant(d05, tmp_path))["costs"]
    item = costs["per_item"]["reset_rollout_trace_write"]
    assert item["known_runs"] == 3 and item["known_total"] == pytest.approx(10.630919, abs=1e-6)
    assert item["nested_runs"] == 3 and item["nested_known_total"] == pytest.approx(2.150025, 1e-5)
    assert costs["runs_nested_in_parent"] == {
        "reference-0-prefix": "reference-0",
        "regression-0-prefix": "regression-0",
        "correction-exploration-0-prefix": "correction-exploration-0",
    }
    assert costs["cost_parent_missing"] == {}


@needs_d05
def test_undeclared_cost_parent_is_inferred_from_the_main_run_prefix_reference(d05, tmp_path):
    def undeclared(document):
        del run_named(document, "reference-0-prefix")["cost_parent_run_id"]

    costs = evaluate_bundle(d05_variant(d05, tmp_path, undeclared))["costs"]
    assert costs["runs_nested_in_parent"]["reference-0-prefix"] == "reference-0"
    assert costs["per_item"]["reset_rollout_trace_write"]["known_total"] == pytest.approx(
        10.630919, abs=1e-6
    )


@needs_d05
def test_cost_parent_absent_from_the_bundle_counts_the_run_on_its_own(d05, tmp_path):
    def orphan(document):
        run_named(document, "reference-0-prefix")["cost_parent_run_id"] = "ghost-run"

    costs = evaluate_bundle(d05_variant(d05, tmp_path, orphan))["costs"]
    assert costs["cost_parent_missing"] == {"reference-0-prefix": "ghost-run"}
    item = costs["per_item"]["reset_rollout_trace_write"]
    assert item["known_runs"] == 4 and item["known_total"] == pytest.approx(11.340823, abs=1e-6)
    assert item["nested_runs"] == 2


# --- 3. protocol v4: per-run frozen configuration digests ---------------------------------


def freshness_variant(
    source: tuple[dict, dict], folder: Path, mutate_bundle=None, mutate_frozen=None
) -> Path:
    document, frozen = copy.deepcopy(source[0]), copy.deepcopy(source[1])
    runs = {r["id"]: r for r in document["runs"]}
    frozen["schema"] = "nisayon.lift.protocol.v4"
    frozen["configuration_sha256_by_run_id"] = {
        a["run_id"]: runs[a["run_id"]]["configuration_sha256"] for a in frozen["assignments"]
    }
    if mutate_frozen is not None:
        mutate_frozen(frozen)
    document["confirmation"]["protocol_sha256"] = producer_digest(frozen)
    if mutate_bundle is not None:
        mutate_bundle(document)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "frozen-protocol.json").write_text(json.dumps(frozen, indent=2) + "\n")
    shutil.copy(FRESHNESS / "artifact-manifest.json", folder / "artifact-manifest.json")
    return write_document(document, folder / "bundle.json")


def note_details(decision: dict, code: str) -> list[str]:
    return [n["detail"] for n in decision["notes"] if n["code"] == code]


def reason_details(decision: dict, code: str) -> list[str]:
    return [r["detail"] for r in decision["reasons"] if r["code"] == code]


@needs_freshness
def test_v4_per_run_configurations_are_verified(freshness, tmp_path):
    decision = evaluate_bundle(freshness_variant(freshness, tmp_path))
    verified = note_details(decision, "protocol_verified")
    assert verified and "per-run configuration digests" in verified[0]
    assert not reason_details(decision, "protocol_mismatch")
    assert decision["obligation"]["version"] == "first-case-obligation-v0.2"


@needs_freshness
def test_run_whose_configuration_differs_from_its_frozen_entry_is_a_protocol_mismatch(
    freshness, tmp_path
):
    def swap(frozen):
        frozen["configuration_sha256_by_run_id"]["confirmation-correction-4000"] = "00" * 32

    decision = evaluate_bundle(freshness_variant(freshness, tmp_path, mutate_frozen=swap))
    assert decision["decision"] != "accepted"
    assert any(
        "confirmation-correction-4000" in d and "configuration_sha256_by_run_id" in d
        for d in reason_details(decision, "protocol_mismatch")
    )


@needs_freshness
def test_frozen_map_that_omits_an_assigned_run_is_a_protocol_mismatch(freshness, tmp_path):
    def omit(frozen):
        del frozen["configuration_sha256_by_run_id"]["confirmation-reference-4000"]

    decision = evaluate_bundle(freshness_variant(freshness, tmp_path, mutate_frozen=omit))
    assert any(
        "omits assigned runs" in d and "confirmation-reference-4000" in d
        for d in reason_details(decision, "protocol_mismatch")
    )


@needs_freshness
def test_shorter_rollout_hidden_behind_the_same_deployment_is_caught(freshness, tmp_path):
    """A run re-executed with a different horizon keeps its deployment digest but not its
    frozen configuration digest."""

    def rehorizon(document):
        run = run_named(document, "confirmation-correction-4001")
        run["configuration"]["horizon"] = 21
        run["configuration_sha256"] = producer_digest(run["configuration"])

    decision = evaluate_bundle(freshness_variant(freshness, tmp_path, mutate_bundle=rehorizon))
    assert any(
        "confirmation-correction-4001" in d for d in reason_details(decision, "protocol_mismatch")
    )


# --- 2. the scorer: only verified decision bytes support a confirmation -------------------


def trial_of(ledger: dict, arm: str, case_id: str) -> dict:
    return next(t for t in ledger["trials"] if t["arm"] == arm and t["case_id"] == case_id)


def rewrite_record(folder: Path, ledger_path: Path, arm: str, case_id: str, mutate) -> None:
    """Change a written decision record and rebind the ledger's digest to the new bytes."""
    ledger = json.loads(ledger_path.read_text())
    trial = trial_of(ledger, arm, case_id)
    target = folder / trial["decision"]["path"]
    record = json.loads(target.read_text())
    mutate(record)
    raw = (json.dumps(record, indent=2) + "\n").encode()
    target.write_bytes(raw)
    trial["decision"]["sha256"] = hashlib.sha256(raw).hexdigest()
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")


def finding_codes(score: dict) -> set[str]:
    return {f["code"] for f in score["findings"]}


@needs_boundary
def test_retained_missing_decision_ledger_fails_closed():
    score = score_file(BOUNDARY / "labelled-ledger.json", BOUNDARY)
    assert score["fair"] is False
    assert {"decision_unverifiable", "confirmation_unsupported", "false_acceptance"} <= (
        finding_codes(score)
    )
    arm = score["arms"]["A"]
    assert arm["outcomes"]["confirmed"] == 0 and arm["false_acceptances"] == 1
    assert arm["outcomes"]["unresolved"] == 1
    assert any("not found under the root" in f["detail"] for f in score["findings"])


def test_ledger_directory_is_the_default_root(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)
    assert score_file(path)["fair"] is True
    assert score_file(path)["arms"]["A"]["outcomes"]["confirmed"] == 2


def test_without_a_root_no_declaration_confirms_anything(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)
    score = score_comparison(json.loads(path.read_text()))
    assert score["fair"] is False
    assert "decision_unverifiable" in finding_codes(score)
    assert all(arm["outcomes"]["confirmed"] == 0 for arm in score["arms"].values())
    assert any("no root given" in f["detail"] for f in score["findings"])


def test_omitted_digest_does_not_bind_the_decision_bytes(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)
    ledger = json.loads(path.read_text())
    trial_of(ledger, "A", "D01-gripper-sign")["decision"]["sha256"] = None
    path.write_text(json.dumps(ledger))
    score = score_file(path, tmp_path)
    assert score["fair"] is False
    assert any("digest not declared" in f["detail"] for f in score["findings"])
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 1
    assert score["arms"]["A"]["false_acceptances"] == 1


def test_tampered_record_is_a_digest_mismatch(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)
    record = tmp_path / "decisions/A-D01-gripper-sign.json"
    tampered = json.loads(record.read_text())
    tampered["decision"] = "rejected"
    record.write_text(json.dumps(tampered))
    score = score_file(path, tmp_path)
    assert score["fair"] is False
    assert any("record digest mismatch" in f["detail"] for f in score["findings"])
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 1


def test_record_that_names_no_confirmed_candidate_does_not_support_a_confirmation(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)

    def drop(record):
        record["confirmation"]["candidate"]["digest"] = None

    rewrite_record(tmp_path, path, "A", "D01-gripper-sign", drop)
    score = score_file(path, tmp_path)
    assert "decision_unverifiable" not in finding_codes(score), "the bytes verify"
    assert any("names no confirmed candidate" in f["detail"] for f in score["findings"])
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 1
    assert score["arms"]["A"]["false_acceptances"] == 1


def test_record_for_a_candidate_the_arm_never_proposed_is_unsupported(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)

    def other(record):
        record["confirmation"]["candidate"]["digest"] = "sha256:" + "cd" * 32

    rewrite_record(tmp_path, path, "A", "D01-gripper-sign", other)
    score = score_file(path, tmp_path)
    assert any("not among the arm's proposals" in f["detail"] for f in score["findings"])
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 1


def test_decision_from_a_different_case_is_unverifiable(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)

    def relabel(record):
        record["case_id"] = "D02-cartesian-axis"

    rewrite_record(tmp_path, path, "A", "D01-gripper-sign", relabel)
    score = score_file(path, tmp_path)
    assert score["fair"] is False
    assert any("belongs to case 'D02-cartesian-axis'" in f["detail"] for f in score["findings"])
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 1


def test_arm_specific_execution_of_the_case_binds(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)

    def suffix(record):
        record["case_id"] = "D01-gripper-sign-A"

    rewrite_record(tmp_path, path, "A", "D01-gripper-sign", suffix)
    score = score_file(path, tmp_path)
    assert score["fair"] is True and score["arms"]["A"]["outcomes"]["confirmed"] == 2


def test_candidate_digest_prefix_does_not_matter(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)

    def bare(record):
        digest = record["confirmation"]["candidate"]["digest"]
        record["confirmation"]["candidate"]["digest"] = (
            digest.removeprefix("sha256:") if digest.startswith("sha256:") else "sha256:" + digest
        )

    rewrite_record(tmp_path, path, "A", "D01-gripper-sign", bare)
    score = score_file(path, tmp_path)
    assert score["fair"] is True and score["arms"]["A"]["outcomes"]["confirmed"] == 2


def test_gzipped_decision_record_is_verified(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)
    ledger = json.loads(path.read_text())
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    plain = tmp_path / trial["decision"]["path"]
    packed = plain.with_suffix(".json.gz")
    with gzip.open(packed, "wb") as stream:
        stream.write(plain.read_bytes())
    plain.unlink()
    trial["decision"]["path"] = str(packed.relative_to(tmp_path))
    trial["decision"]["sha256"] = hashlib.sha256(packed.read_bytes()).hexdigest()
    path.write_text(json.dumps(ledger))
    score = score_file(path, tmp_path)
    assert score["fair"] is True and score["arms"]["A"]["outcomes"]["confirmed"] == 2


def test_misdeclared_decision_is_named_but_the_record_decides(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)
    ledger = json.loads(path.read_text())
    trial_of(ledger, "A", "D01-gripper-sign")["decision"]["decision"] = "rejected"
    path.write_text(json.dumps(ledger))
    score = score_file(path, tmp_path)
    assert score["fair"] is True
    assert "decision_misdeclared" in finding_codes(score)
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 2


def test_decision_path_escaping_the_root_is_unverifiable(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path / "inner")
    ledger = json.loads(path.read_text())
    trial_of(ledger, "A", "D01-gripper-sign")["decision"]["path"] = "../outside.json"
    path.write_text(json.dumps(ledger))
    (tmp_path / "outside.json").write_text("{}")
    score = score_file(path, tmp_path / "inner")
    assert any("escapes the root" in f["detail"] for f in score["findings"])


# --- 5. diagnostic versus complete trial timelines ----------------------------------------


def test_full_trial_timeline_extends_the_reported_elapsed_wall(tmp_path):
    ledger = fair_ledger()
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    started, ended = trial["timeline"]["started_at"], trial["timeline"]["ended_at"]
    trial["full_trial_timeline"] = {
        "started_at": started,
        "ended_at": ended.replace("T02:", "T04:"),
    }
    trial["confirmation_timeline"] = {
        "started_at": ended,
        "ended_at": ended.replace("T02:", "T04:"),
    }
    trial["time_to_confirmed_correction_s"] = 7500.0
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    arm = score["arms"]["A"]
    assert score["fair"] is True
    assert arm["diagnostic_elapsed_wall_s"] == pytest.approx(55 * 60)
    assert arm["elapsed_wall_s"] > arm["diagnostic_elapsed_wall_s"]
    assert arm["elapsed_wall_scope"] == "mixed"
    assert arm["time_to_confirmed_correction_s"] == {
        "known_total": 7500.0,
        "confirmed_trials_with_time": 1,
        "mean": 7500.0,
    }
    assert score["arms"]["B"]["elapsed_wall_scope"] == "diagnostic_only"
    assert score["arms"]["B"]["time_to_confirmed_correction_s"] is None


def test_time_to_correction_counts_only_confirmed_trials(tmp_path):
    ledger = fair_ledger()
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    trial["time_to_confirmed_correction_s"] = 300.0
    trial["decision"]["decision"] = "unresolved"
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert score["arms"]["A"]["time_to_confirmed_correction_s"] is None


def test_full_trial_that_does_not_contain_its_diagnosis_is_malformed(tmp_path):
    ledger = fair_ledger()
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    trial["full_trial_timeline"] = {
        "started_at": trial["timeline"]["started_at"].replace("T02:", "T03:"),
        "ended_at": trial["timeline"]["ended_at"].replace("T02:", "T03:"),
    }
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert score["fair"] is False
    assert any(
        f["code"] == "malformed_ledger" and "full_trial_timeline" in f["detail"]
        for f in score["findings"]
    )


# --- trial record bindings: what a trial names by path and digest must verify ---------------


def bind_diagnosis(tmp_path: Path, digest: str | None = None, present: bool = True) -> Path:
    """A trial that names a complete diagnosis record: the record names the trial's decision
    and the bundle the decision was made on, and the decision carries that bundle's digest."""
    ledger = fair_ledger()
    path = write_ledger(ledger, tmp_path)
    ledger = json.loads(path.read_text())
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    bundle_doc = {"schema": "nisayon.first_case.v1", "case": {"id": "D01-gripper-sign-A"}}
    bundle = tmp_path / "A/D01/execution/bundle.json"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_text(json.dumps(bundle_doc))
    decision_file = tmp_path / trial["decision"]["path"]
    record = json.loads(decision_file.read_text())
    record["bundle_sha256"] = digest_of(bundle_doc)
    decision_raw = (json.dumps(record, indent=2) + "\n").encode()
    decision_file.write_bytes(decision_raw)
    trial["decision"]["sha256"] = hashlib.sha256(decision_raw).hexdigest()
    diagnosis = {
        "schema": "nisayon.development-diagnosis.v1",
        "case_id": "D01-gripper-sign",
        "bundle_path": "execution/bundle.json",
        "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "decision": {"path": "decision.json", "sha256": trial["decision"]["sha256"]},
    }
    raw = (json.dumps(diagnosis, indent=2) + "\n").encode()
    record_path = tmp_path / "A/D01/diagnosis.json"
    if present:
        record_path.write_bytes(raw)
    trial["diagnosis"] = {
        "path": "A/D01/diagnosis.json",
        "sha256": hashlib.sha256(raw).hexdigest() if digest is None else digest,
    }
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    return path


def test_bound_diagnosis_record_verifies(tmp_path):
    score = score_file(bind_diagnosis(tmp_path), tmp_path)
    assert score["fair"] is True
    assert "trial_record_unverifiable" not in finding_codes(score)


def test_bound_diagnosis_record_with_wrong_digest_blocks(tmp_path):
    score = score_file(bind_diagnosis(tmp_path, digest="00" * 32), tmp_path)
    assert score["fair"] is False
    assert any(
        f["code"] == "trial_record_unverifiable" and "digest mismatch" in f["detail"]
        for f in score["findings"]
    )


def test_bound_diagnosis_record_that_is_missing_blocks(tmp_path):
    score = score_file(bind_diagnosis(tmp_path, present=False), tmp_path)
    assert score["fair"] is False
    assert any(
        f["code"] == "trial_record_unverifiable" and "not found under the root" in f["detail"]
        for f in score["findings"]
    )


# --- the execution lane's real trial shape parses and scores -------------------------------


def test_execution_lane_trial_shape_scores(tmp_path):
    """Every field development.py writes per trial and per ledger is tolerated or read."""
    ledger = fair_ledger()
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    started, ended = trial["timeline"]["started_at"], trial["timeline"]["ended_at"]
    trial.update(
        {
            "diagnostic_records_retained": 3,
            "timeline_scope": "Diagnostic interval required by scoring contract v1",
            "full_trial_timeline": {"started_at": started, "ended_at": ended},
            "confirmation_timeline": None,
            "time_to_confirmed_correction_s": 300.0,
            "time_to_decision_including_other_arm_work_s": 300.0,
            "cost_scope": "Simulator wall is nested within phase walls.",
            "diagnosis": None,
            "confirmation": None,
        }
    )
    trial["costs"].update(
        {
            "diagnostic_wall": {"value": 13.26, "unit": "s"},
            "confirmation_wall": {"value": 0, "unit": "s"},
            "own_trial_wall": {"value": 13.26, "unit": "s"},
            "provider_and_compute_charges": {
                "value": None,
                "unit": "USD",
                "missing": "No invoices or power meter",
            },
        }
    )
    ledger.update(
        {
            "execution_complete": True,
            "started_at": started,
            "ended_at": ended,
            "measured_invocation_wall_s": 1234.5,
            "preparation_cost_ledger": {"path": "preparation-costs.json", "sha256": "ab" * 32},
            "incomplete_trial_policy": "Missing trials remain assigned and unknown.",
            "cost_and_claim_limits": ["No full-cost savings claim."],
        }
    )
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert score["fair"] is True, score["findings"]
    assert score["arms"]["A"]["time_to_confirmed_correction_s"]["known_total"] == 300.0
    assert score["arms"]["A"]["costs"]["own_trial_wall"]["known_trials"] == 1


def test_declared_incomplete_execution_is_reported(tmp_path):
    ledger = fair_ledger()
    ledger["execution_complete"] = False
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert "execution_incomplete" in finding_codes(score)
    assert score["fair"] is True, "incompleteness is reported; the missing trials decide"


# --- an executed prefix under another deployment is an invalid probe ------------------------

BOUNDARY_001_D05 = (
    REPO / "docs/experiments/results/development-boundary-001/D05-recurrent-carry/execution"
)


@pytest.mark.skipif(
    not (BOUNDARY_001_D05 / "bundle.json.gz").is_file(), reason="boundary-001 D05 absent"
)
def test_prefix_executed_under_another_deployment_is_an_invalid_probe(tmp_path):
    """The `11a4a47` record: plan `reference` names the typed deployment, the prefixes ran
    the older record. The producer defect is named on the prefixes; the main runs stand."""
    document = read_document(BOUNDARY_001_D05 / "bundle.json.gz")
    decision = evaluate_bundle(d05_variant(document, tmp_path))
    for prefix in ("reference-0-prefix", "regression-0-prefix"):
        run = decision["runs"][prefix]
        assert run["role"] == "probe" and run["measurement"] == "invalid"
        assert any("declares candidate" in d for d in details(run, "identity_mismatch"))
    assert decision["runs"]["reference-0"]["measurement"] == "valid"
    assert decision["runs"]["regression-0"]["measurement"] == "valid"
    assert decision["premises"] == {"reference_established": True, "regression_reproduced": True}


def test_two_arms_naming_the_same_decision_record_is_not_fair(tmp_path):
    ledger = fair_ledger()
    a = trial_of(ledger, "A", "D01-gripper-sign")
    b = trial_of(ledger, "B", "D01-gripper-sign")
    b["decision"] = dict(a["decision"])
    b["proposals"] = [dict(p) for p in a["proposals"]]
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert score["fair"] is False
    assert any(
        f["code"] == "decision_shared_between_arms" and "D01-gripper-sign" in f["detail"]
        for f in score["findings"]
    )


def test_confirmation_outside_the_full_trial_is_malformed(tmp_path):
    ledger = fair_ledger()
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    started, ended = trial["timeline"]["started_at"], trial["timeline"]["ended_at"]
    trial["full_trial_timeline"] = {"started_at": started, "ended_at": ended}
    trial["confirmation_timeline"] = {
        "started_at": ended,
        "ended_at": ended.replace("T02:", "T05:"),
    }
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert score["fair"] is False
    assert any(
        f["code"] == "malformed_ledger" and "confirmation_timeline" in f["detail"]
        for f in score["findings"]
    )


def test_time_to_correction_longer_than_the_trial_is_reported(tmp_path):
    ledger = fair_ledger()
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    started, ended = trial["timeline"]["started_at"], trial["timeline"]["ended_at"]
    trial["full_trial_timeline"] = {"started_at": started, "ended_at": ended}
    trial["time_to_confirmed_correction_s"] = 10 * 3600.0
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert "time_to_correction_exceeds_trial" in finding_codes(score)
    assert score["fair"] is True, "reported, not blocking"


# --- duplicated conditions and assignments in a confirmation -------------------------------


@needs_freshness
def test_duplicated_condition_id_in_a_confirmation_is_malformed(freshness, tmp_path):
    def repeat(frozen):
        frozen["condition_ids"] = [c for c in frozen["condition_ids"] if c != "seed-4031"]
        frozen["condition_ids"].append("seed-4000")

    def repeat_in_bundle(document):
        ids = document["confirmation"]["condition_ids"]
        document["confirmation"]["condition_ids"] = [c for c in ids if c != "seed-4031"]
        document["confirmation"]["condition_ids"].append("seed-4000")

    decision = evaluate_bundle(
        freshness_variant(freshness, tmp_path, mutate_bundle=repeat_in_bundle, mutate_frozen=repeat)
    )
    assert decision["decision"] == "invalid"
    assert reason_details(decision, "malformed_record")
    assert not (decision["confirmation"] or {}).get("pairs")


@needs_freshness
def test_one_run_assigned_to_two_conditions_is_invalid(freshness, tmp_path):
    def reassign(frozen):
        for item in frozen["assignments"]:
            if item["run_id"] == "confirmation-correction-4031":
                item["run_id"] = "confirmation-correction-4000"

    def reassign_in_bundle(document):
        for item in document["assignments"]:
            if item["run_id"] == "confirmation-correction-4031":
                item["run_id"] = "confirmation-correction-4000"
        ids = document["confirmation"].get("candidate_run_ids") or []
        document["confirmation"]["candidate_run_ids"] = [
            "confirmation-correction-4000" if r == "confirmation-correction-4031" else r
            for r in ids
        ]

    decision = evaluate_bundle(
        freshness_variant(
            freshness, tmp_path, mutate_bundle=reassign_in_bundle, mutate_frozen=reassign
        )
    )
    assert decision["decision"] == "invalid"
    codes = {r["code"] for r in decision["reasons"]}
    assert {"multiple_runs_per_condition_role", "paired_initial_state_mismatch"} & codes
    assert decision["confirmation"]["summary"]["fresh_pass"] < 32


def test_decision_made_on_another_bundle_is_not_bound(tmp_path):
    path = bind_diagnosis(tmp_path)
    other = tmp_path / "A/D01/execution/bundle.json"
    other.write_text(json.dumps({"schema": "nisayon.first_case.v1", "case": {"id": "other"}}))
    ledger = json.loads(path.read_text())
    trial = trial_of(ledger, "A", "D01-gripper-sign")
    diagnosis = json.loads((tmp_path / trial["diagnosis"]["path"]).read_text())
    diagnosis["bundle_sha256"] = hashlib.sha256(other.read_bytes()).hexdigest()
    raw = (json.dumps(diagnosis, indent=2) + "\n").encode()
    (tmp_path / trial["diagnosis"]["path"]).write_bytes(raw)
    trial["diagnosis"]["sha256"] = hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(ledger))
    score = score_file(path, tmp_path)
    assert score["fair"] is False
    assert any(
        f["code"] == "decision_not_bound_to_trial" and "different bundle" in f["detail"]
        for f in score["findings"]
    )
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 1


def test_confirmed_trial_without_an_execution_record_is_reported(tmp_path):
    score = score_file(write_ledger(fair_ledger(), tmp_path), tmp_path)
    assert "trial_names_no_execution_record" in finding_codes(score)
    assert score["fair"] is True
