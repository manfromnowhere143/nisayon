"""Adversarial and metamorphic tests on derived copies of the real Lift v2 record.

The source is the execution lane's committed record at ``docs/experiments/results/lift-v2``.
Every test works on an in-memory copy written to a temporary directory; the committed
files and the producer's raw store are never modified. Tests that need the raw store
are skipped where it is absent.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import (
    deployment,
    producer_digest,
    read_document,
    replay_control,
    write_document,
)

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "docs/experiments/results/lift-v2"
STORE = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/lift-v2-confirmation-001/execution"
)
HISTORY = [
    REPO / "docs/evaluation/results/audit-2026-09-18/lift-confirmation-with-replay.decision.json",
    REPO / "docs/evaluation/results/audit-2026-09-18/lift-exploration.decision.json",
]
DEPLOYABILITY_GAP = "candidate_deployability_undeclared"

pytestmark = pytest.mark.skipif(
    not (RESULTS / "bundle.json.gz").is_file(), reason="the committed v2 record is absent"
)
needs_store = pytest.mark.skipif(not STORE.is_dir(), reason="the producer's raw store is not here")


@pytest.fixture(scope="module")
def source() -> dict:
    return read_document(RESULTS / "bundle.json.gz")


def variant(source: dict, folder: Path, mutate=None, *, protocol=True, manifest=True) -> Path:
    document = copy.deepcopy(source)
    if mutate is not None:
        mutate(document)
    folder.mkdir(parents=True, exist_ok=True)
    path = write_document(document, folder / "bundle.json")
    if protocol:
        shutil.copy(RESULTS / "frozen-protocol.json", folder / "frozen-protocol.json")
    if manifest:
        shutil.copy(RESULTS / "artifact-manifest.json", folder / "artifact-manifest.json")
    return path


def run_named(document: dict, run_id: str) -> dict:
    return next(r for r in document["runs"] if r["id"] == run_id)


def reasons(decision: dict) -> set[str]:
    return {r["code"] for r in decision["reasons"]}


def notes(decision: dict) -> set[str]:
    return {n["code"] for n in decision["notes"]}


def declare_deployable(document: dict) -> None:
    for plan in document["plans"]:
        plan["deployable"] = plan["id"] == "correction"


# --- baseline ---------------------------------------------------------------------------


def test_portable_baseline_decides_on_inline_traces_and_names_the_store_gap(source, tmp_path):
    decision = evaluate_bundle(variant(source, tmp_path), history=HISTORY)
    assert decision["decision"] == "unresolved"
    assert reasons(decision) == {"artifact_store_unverified", DEPLOYABILITY_GAP}
    assert {"protocol_verified"} <= notes(decision)
    assert decision["evidence"]["timing"] == "measured_from_acquisition_stamps"
    assert decision["evidence"]["identity"] == "verified_per_run"
    assert decision["confirmation"]["summary"]["fresh_pass"] == 32


@needs_store
def test_with_the_store_only_the_declaration_is_missing(source, tmp_path):
    decision = evaluate_bundle(variant(source, tmp_path), artifact_root=STORE, history=HISTORY)
    assert reasons(decision) == {DEPLOYABILITY_GAP}
    assert {"protocol_verified", "artifact_manifest_verified"} <= notes(decision)
    consistent = [
        run_id
        for run_id, run in decision["runs"].items()
        if any(f["code"] == "raw_trace_consistent" for f in run["findings"])
    ]
    assert len(consistent) == 69


@needs_store
def test_declaring_deployability_is_the_only_missing_piece(source, tmp_path):
    """A derived edit of the producer's record, labelled as such; not a producer result."""
    decision = evaluate_bundle(
        variant(source, tmp_path, declare_deployable), artifact_root=STORE, history=HISTORY
    )
    assert decision["decision"] == "accepted", decision["reasons"]
    assert decision["evidence"]["deployability"] == "declared"
    statuses = {e["id"]: e["status"] for e in decision["candidates"].values()}
    assert statuses == {"correction": "accepted", "suppression": "rejected"}


# --- attacks on the protocol --------------------------------------------------------------


def test_threshold_relaxed_after_freeze_is_a_protocol_mismatch(source, tmp_path):
    def relax(document):
        document["case"]["predicates"]["min_cube_height_m"] = 0.82

    decision = evaluate_bundle(variant(source, tmp_path, relax), history=HISTORY)
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "protocol_mismatch" and "predicates" in r["detail"]
        for r in decision["reasons"]
    )


def test_threshold_relaxed_with_rebuilt_protocol_is_caught_by_retained_history(source, tmp_path):
    """An attacker who rewrites the frozen protocol and its digest consistently fools an
    offline check of the bundle alone; the retained decision for the same candidate and
    condition set still carries the original protocol digest."""
    document = copy.deepcopy(source)
    declare_deployable(document)
    document["case"]["predicates"]["min_cube_height_m"] = 0.82
    frozen = json.loads((RESULTS / "frozen-protocol.json").read_text())
    frozen["predicates"] = document["case"]["predicates"]
    document["confirmation"]["protocol_sha256"] = producer_digest(frozen)
    tmp_path.mkdir(exist_ok=True)
    path = write_document(document, tmp_path / "bundle.json")
    (tmp_path / "frozen-protocol.json").write_text(json.dumps(frozen))
    shutil.copy(RESULTS / "artifact-manifest.json", tmp_path / "artifact-manifest.json")
    alone = evaluate_bundle(path)
    assert "protocol_mismatch" not in reasons(alone), "offline, the rebuilt protocol is consistent"
    retained = REPO / "docs/evaluation/results/audit-2026-09-18/lift-v2.decision.json"
    if retained.is_file():
        with_history = evaluate_bundle(path, history=[retained])
        assert any(
            r["code"] == "protocol_mismatch" and "rewritten" in r["detail"]
            for r in with_history["reasons"]
        )


def test_missing_or_conflicting_frozen_protocol(source, tmp_path):
    missing = evaluate_bundle(variant(source, tmp_path / "missing", protocol=False))
    assert "protocol_unverified" in reasons(missing)
    assert missing["decision"] != "accepted"
    path = variant(source, tmp_path / "conflict")
    frozen = json.loads((tmp_path / "conflict/frozen-protocol.json").read_text())
    frozen["frozen_at"] = "2026-09-17T23:59:59+00:00"
    (tmp_path / "conflict/frozen-protocol.json").write_text(json.dumps(frozen))
    conflict = evaluate_bundle(path)
    assert conflict["decision"] == "invalid"
    assert "protocol_mismatch" in reasons(conflict)


def test_post_freeze_source_change_not_represented_in_the_run(source, tmp_path):
    def change_code(document):
        document["code"] = {**document["code"], "git_head": "deadbeef" * 5}

    decision = evaluate_bundle(variant(source, tmp_path, change_code))
    assert decision["decision"] == "invalid"
    assert any("changed after the freeze" in r["detail"] for r in decision["reasons"])


# --- attacks on assignments ---------------------------------------------------------------


def test_dropping_an_assigned_run_leaves_a_named_gap(source, tmp_path):
    def drop(document):
        document["runs"] = [
            r for r in document["runs"] if r["id"] != "confirmation-correction-2005"
        ]

    decision = evaluate_bundle(variant(source, tmp_path, drop))
    assert decision["decision"] != "accepted"
    assert any(
        r["code"] == "assigned_outcome_missing" and "confirmation-correction-2005" in r["detail"]
        for r in decision["reasons"]
    )


def test_replacing_an_assigned_run_by_a_renamed_retry(source, tmp_path):
    def retry(document):
        run = run_named(document, "confirmation-correction-2005")
        run["id"] = "confirmation-correction-2005-retry"
        ids = document["confirmation"]["candidate_run_ids"]
        ids[ids.index("confirmation-correction-2005")] = run["id"]
        for assignment in document["assignments"]:
            if assignment["run_id"] == "confirmation-correction-2005":
                assignment["run_id"] = run["id"]

    decision = evaluate_bundle(variant(source, tmp_path, retry))
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "protocol_mismatch" and "assignments" in r["detail"]
        for r in decision["reasons"]
    )


def test_unassigned_spare_attempt_voids_the_confirmation(source, tmp_path):
    def spare(document):
        spare_run = copy.deepcopy(run_named(document, "confirmation-correction-2004"))
        spare_run["id"] = "confirmation-correction-2004-spare"
        document["runs"].append(spare_run)

    decision = evaluate_bundle(variant(source, tmp_path, spare))
    assert decision["decision"] == "invalid"
    assert "multiple_runs_per_condition_role" in reasons(decision)


def test_assigned_failure_cannot_be_relabelled_as_a_negative_control(source, tmp_path):
    def relabel(document):
        run = run_named(document, "confirmation-correction-2005")
        run["evidence_origin"] = "invalid_replay_control"
        run["execution_mode"] = "recorded_observation_replay"

    decision = evaluate_bundle(variant(source, tmp_path, relabel))
    assert decision["decision"] == "invalid"
    assert "assigned_run_invalid" in reasons(decision)


# --- attacks on identity ------------------------------------------------------------------


def test_candidate_identity_swapped_in_one_assigned_run(source, tmp_path):
    def swap(document):
        run = run_named(document, "confirmation-correction-2005")
        run["candidate_sha256"] = producer_digest(
            deployment("suppression", document["case"]["policy"]["sha256"])
        )

    decision = evaluate_bundle(variant(source, tmp_path, swap))
    assert decision["decision"] == "invalid"
    assert "candidate_not_frozen" in reasons(decision)


def test_backend_identity_changed_while_bundle_identity_is_unchanged(source, tmp_path):
    def change(document):
        run = run_named(document, "confirmation-reference-2010")
        run["code_sha256"] = "11" * 32
        run["dependencies_sha256"] = "22" * 32

    decision = evaluate_bundle(variant(source, tmp_path, change))
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "identity_mismatch" and "code_sha256" in r["detail"]
        for r in decision["reasons"]
    )
    assert any(
        r["code"] == "identity_mismatch" and "dependencies_sha256" in r["detail"]
        for r in decision["reasons"]
    )


def test_identity_stripped_from_one_run_is_unbound(source, tmp_path):
    def strip(document):
        run = run_named(document, "confirmation-correction-2011")
        for key in (
            "invocation_id",
            "execution_identity_sha256",
            "code_sha256",
            "dependencies_sha256",
            "policy_sha256",
            "configuration_sha256",
        ):
            run.pop(key, None)

    decision = evaluate_bundle(variant(source, tmp_path, strip))
    assert decision["decision"] != "accepted"
    assert "identity_unbound" in reasons(decision)


# --- attacks on measurements --------------------------------------------------------------


def test_stale_consumption_is_a_measured_timing_failure_not_an_invalid_experiment(source, tmp_path):
    def stale(document):
        run = run_named(document, "confirmation-correction-2000")
        rows = run["trace"]
        row = rows[5]
        older = rows[2]
        row["observation_step"] = 2
        row["observation_sim_time_s"] = older["observation_sim_time_s"]
        row["observation_capture"] = older["observation_capture"]
        row["observation_sha256"] = older["observation_sha256"]

    decision = evaluate_bundle(variant(source, tmp_path, stale))
    run = decision["runs"]["confirmation-correction-2000"]
    assert run["measurement"] == "valid", run["findings"]
    assert run["timing"] == "violated"
    assert run["metrics"]["max_observation_age_s"] == pytest.approx(0.15)
    assert decision["decision"] == "rejected"
    assert "timing_obligation_violated" in reasons(decision)


def test_impossible_host_ordering_is_invalid(source, tmp_path):
    def reorder(document):
        row = run_named(document, "confirmation-correction-2001")["trace"][3]
        row["action_host_s"] = row["observation_capture"]["received_host_s"] - 1.0

    decision = evaluate_bundle(variant(source, tmp_path, reorder))
    assert decision["decision"] == "invalid"
    assert "capture_stamps_inconsistent" in reasons(decision)


def test_unit_mistake_in_observation_time_is_invalid(source, tmp_path):
    def milliseconds(document):
        for row in run_named(document, "confirmation-correction-2002")["trace"]:
            row["observation_sim_time_s"] = row["observation_sim_time_s"] * 1000.0

    decision = evaluate_bundle(variant(source, tmp_path, milliseconds))
    assert decision["decision"] == "invalid"
    assert reasons(decision) & {
        "capture_stamps_inconsistent",
        "observation_after_action",
        "non_monotone_clock",
    }


def test_carried_recurrent_state_on_an_assigned_candidate_is_rejected(source, tmp_path):
    def carry(document):
        run = run_named(document, "confirmation-correction-2003")
        run["policy_reset"] = {"mode": "carry_prefix", "prefix_run_id": "reference-0-b"}
        run["prefix_run"] = {"id": "reference-0-b", "steps": 44}

    decision = evaluate_bundle(variant(source, tmp_path, carry))
    assert decision["decision"] == "rejected"
    assert "reset_obligation_violated" in reasons(decision)


def test_carried_state_without_its_prefix_in_the_bundle_is_unresolved(source, tmp_path):
    def carry(document):
        run = run_named(document, "confirmation-correction-2003")
        run["policy_reset"] = {"mode": "carry_prefix", "prefix_run_id": "prefix-not-retained"}
        run["prefix_run"] = {"id": "prefix-not-retained", "steps": 21}

    decision = evaluate_bundle(variant(source, tmp_path, carry))
    assert decision["decision"] != "accepted"
    run = decision["runs"]["confirmation-correction-2003"]
    assert {"reset_obligation_violated", "reset_evidence_incomplete"} <= {
        f["code"] for f in run["findings"]
    }


def test_missing_reset_component_is_unresolved(source, tmp_path):
    def remove(document):
        run = run_named(document, "confirmation-correction-2004")
        run["initial_state_sha256"] = ""

    decision = evaluate_bundle(variant(source, tmp_path, remove))
    assert decision["decision"] != "accepted"
    assert "reset_evidence_incomplete" in reasons(decision)


def test_missing_measurement_is_not_a_failure(source, tmp_path):
    def blank(document):
        for row in run_named(document, "confirmation-correction-2006")["trace"]:
            row["cube_height_m"] = {"value": None, "missing": "sensor dropout in this derived copy"}

    decision = evaluate_bundle(variant(source, tmp_path, blank))
    run = decision["runs"]["confirmation-correction-2006"]
    assert run["outcome"]["observed"] == "unknown"
    assert decision["decision"] == "unresolved"
    assert "predicate_unmeasurable" in reasons(decision)
    assert "regression_on_fresh_condition" not in reasons(decision)


# --- replay with recomputed validity flags -------------------------------------------------


def test_replay_relabelled_as_closed_loop_becomes_a_spare_attempt(source, tmp_path):
    document = replay_control(
        copy.deepcopy(source), source_run_id="regression-0", run_id="forged-rerun"
    )
    forged = run_named(document, "forged-rerun")
    forged["evidence_origin"] = "simulator"
    forged["execution_mode"] = "full_closed_loop"
    forged["measurement_status"] = "observed"
    for row in forged["trace"]:
        row["observation_source_run_id"] = "forged-rerun"
        row["next_observation_source_run_id"] = "forged-rerun"
    decision = evaluate_bundle(variant(document, tmp_path))
    assert decision["decision"] == "invalid"
    assert "multiple_runs_per_condition_role" in reasons(decision)
    run = decision["runs"]["forged-rerun"]
    assert run["outcome"]["observed"] == "failed", (
        "copied observations still show the cube on the table"
    )


def test_labelled_derived_replay_is_invalid_and_does_not_contaminate(source, tmp_path):
    document = replay_control(copy.deepcopy(source), source_run_id="regression-0")
    decision = evaluate_bundle(variant(document, tmp_path), history=HISTORY)
    run = decision["runs"]["replay-correction-of-regression-0"]
    assert run["measurement"] == "invalid"
    assert "affected_future_observation_reused" in {f["code"] for f in run["findings"]}
    assert reasons(decision) == {"artifact_store_unverified", DEPLOYABILITY_GAP}


# --- the trust boundary --------------------------------------------------------------------


def test_naive_forgery_is_caught_by_copied_source_identity(source, tmp_path):
    """Copying another run's rows without rewriting their source identity is visible."""

    def forge(document):
        victim = run_named(document, "confirmation-correction-2007")
        donor = run_named(document, "confirmation-correction-2004")
        victim["trace"] = copy.deepcopy(donor["trace"])

    decision = evaluate_bundle(variant(source, tmp_path, forge))
    assert decision["decision"] == "invalid"
    assert "recorded_observation_in_full_rerun" in reasons(decision)


@needs_store
def test_careful_forgery_passes_without_the_store_and_fails_with_it(source, tmp_path):
    """Replacing an assigned run's compact rows by another passing run's rows, with source
    identities and the initial state rewritten, keeps the compact record internally
    consistent. Offline, the evaluator cannot tell; with the raw store the raw-versus-compact
    check rejects it. A forger who also rewrites the raw file and the manifest consistently
    is not detectable by this evaluator. See docs/evaluation/TRUST_BOUNDARY.md."""

    def forge(document):
        victim = run_named(document, "confirmation-correction-2007")
        donor = run_named(document, "confirmation-correction-2004")
        reference = run_named(document, "confirmation-reference-2007")
        victim["trace"] = copy.deepcopy(donor["trace"])
        for row in victim["trace"]:
            row["observation_source_run_id"] = victim["id"]
            row["next_observation_source_run_id"] = victim["id"]
        victim["trace"][0]["state_before_sha256"] = reference["initial_state_sha256"]
        victim["initial_state_sha256"] = reference["initial_state_sha256"]

    document = copy.deepcopy(source)
    declare_deployable(document)
    offline = evaluate_bundle(variant(document, tmp_path / "offline", forge))
    assert "raw_trace_mismatch" not in reasons(offline)
    assert offline["confirmation"]["summary"]["fresh_pass"] == 32
    assert offline["runs"]["confirmation-correction-2007"]["measurement"] == "valid"
    with_store = evaluate_bundle(variant(document, tmp_path / "store", forge), artifact_root=STORE)
    assert with_store["decision"] == "invalid"
    assert "raw_trace_mismatch" in reasons(with_store)


# --- metamorphic properties ---------------------------------------------------------------


def test_reordering_runs_does_not_change_the_decision(source, tmp_path):
    def reverse(document):
        document["runs"] = list(reversed(document["runs"]))

    straight = evaluate_bundle(variant(source, tmp_path / "a"), history=HISTORY)
    reversed_ = evaluate_bundle(variant(source, tmp_path / "b", reverse), history=HISTORY)
    assert straight["decision"] == reversed_["decision"]
    assert reasons(straight) == reasons(reversed_)
    assert straight["confirmation"]["summary"] == reversed_["confirmation"]["summary"]
    assert {k: v["status"] for k, v in straight["candidates"].items()} == {
        k: v["status"] for k, v in reversed_["candidates"].items()
    }


@needs_store
def test_content_identical_copied_store_verifies_independently_of_its_path(source, tmp_path):
    copied = tmp_path / "copied-store"
    shutil.copytree(STORE, copied)
    original = evaluate_bundle(
        variant(source, tmp_path / "o"), artifact_root=STORE, history=HISTORY
    )
    moved = evaluate_bundle(variant(source, tmp_path / "m"), artifact_root=copied, history=HISTORY)
    assert original["decision"] == moved["decision"]
    assert reasons(original) == reasons(moved)
    assert "artifact_manifest_verified" in notes(moved)
    target = copied / "confirmation-correction-2000.jsonl.gz"
    target.write_bytes(target.read_bytes() + b"\n")
    tampered = evaluate_bundle(
        variant(source, tmp_path / "t"), artifact_root=copied, history=HISTORY
    )
    assert tampered["decision"] == "invalid"
    assert "artifact_digest_mismatch" in reasons(tampered)


def test_removing_required_evidence_never_produces_acceptance(source, tmp_path):
    document = copy.deepcopy(source)
    declare_deployable(document)

    def strip_stamps(doc):
        for row in run_named(doc, "confirmation-correction-2008")["trace"]:
            row.pop("observation_capture", None)
            row.pop("next_observation_capture", None)

    def strip_identity(doc):
        run = run_named(doc, "confirmation-correction-2009")
        for key in ("invocation_id", "execution_identity_sha256", "code_sha256"):
            run.pop(key, None)

    outcomes = {
        "no_protocol": evaluate_bundle(variant(document, tmp_path / "p", protocol=False)),
        "no_manifest": evaluate_bundle(variant(document, tmp_path / "m", manifest=False)),
        "no_stamps": evaluate_bundle(variant(document, tmp_path / "s", strip_stamps)),
        "no_identity": evaluate_bundle(variant(document, tmp_path / "i", strip_identity)),
    }
    for name, decision in outcomes.items():
        assert decision["decision"] != "accepted", name
    assert "protocol_unverified" in reasons(outcomes["no_protocol"])
    assert "artifact_manifest_missing" in reasons(outcomes["no_manifest"])
    assert "timing_unmeasured" in reasons(outcomes["no_stamps"])
    assert "identity_unbound" in reasons(outcomes["no_identity"])


def test_every_frozen_condition_survives_aggregation(source, tmp_path):
    decision = evaluate_bundle(variant(source, tmp_path), history=HISTORY)
    frozen = json.loads((RESULTS / "frozen-protocol.json").read_text())
    paired = {p["condition_id"] for p in decision["confirmation"]["pairs"]}
    assert paired == set(frozen["condition_ids"]) | set(frozen["reproduction_condition_ids"])
    assert decision["confirmation"]["summary"]["fresh_assigned"] == len(frozen["condition_ids"])
