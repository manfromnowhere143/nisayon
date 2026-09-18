"""Calibration probes: the observation-age and reset families on real and synthetic records."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import read_document, write_document

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "docs/experiments/results/family-calibration-001"
STORE = Path("/Users/danielwahnich/workspace/nisayon-codex/artifacts/family-calibration-001")

real_record = pytest.mark.skipif(
    not (RESULTS / "bundle.json.gz").is_file(), reason="the committed calibration record is absent"
)


def reasons(decision: dict) -> set[str]:
    return {r["code"] for r in decision["reasons"]}


def codes_of(run: dict) -> set[str]:
    return {f["code"] for f in run["findings"]}


@pytest.fixture(scope="module")
def calibration() -> dict:
    return read_document(RESULTS / "bundle.json.gz")


def write(document: dict, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = write_document(document, folder / "bundle.json")
    (folder / "artifact-manifest.json").write_bytes(
        (RESULTS / "artifact-manifest.json").read_bytes()
    )
    return path


@real_record
def test_real_calibration_is_probed_not_scored(calibration, tmp_path):
    root = STORE if STORE.is_dir() else None
    decision = evaluate_bundle(write(calibration, tmp_path), artifact_root=root)
    assert decision["decision"] == "unresolved"
    assert "calibration_only" in reasons(decision)
    assert "policy_reset_state_differs" not in reasons(decision)
    assert "repeat_runs_differ" not in reasons(decision)
    assert decision["candidates"] == {}
    assert decision["premises"] == {"reference_established": None, "regression_reproduced": None}
    runs = decision["runs"]
    assert len(runs) == 20 and all(r["role"] == "probe" for r in runs.values())
    ages = {rid: r["metrics"].get("max_observation_age_s") for rid, r in runs.items()}
    assert ages["delay-1"] == pytest.approx(0.05) and runs["delay-1"]["timing"] == "violated"
    assert (
        ages["delay-3"] == pytest.approx(0.15)
        and runs["delay-3"]["outcome"]["observed"] == "completed"
    )
    assert ages["delay-6"] == pytest.approx(0.30)
    assert ages["stride-5"] == pytest.approx(0.20)
    assert ages["reference"] == 0 and runs["reference"]["timing"] == "satisfied"
    carried = runs["prefix-21-carried"]
    assert carried["outcome"]["observed"] == "failed" and carried["progress"] == "lost"
    assert "reset_carried_state" in codes_of(carried)
    assert "reset_obligation_violated" not in codes_of(carried), "a probe is not a candidate"
    assert "trace_chain_broken" not in codes_of(carried), (
        "the carried state is the prefix's final state"
    )
    assert runs["prefix-21-clean"]["outcome"]["observed"] == "completed"
    assert runs["reset-every-action"]["outcome"]["observed"] == "completed"
    assert "trace_chain_broken" not in codes_of(runs["reset-every-action"])
    assert runs["sign-delay-sign-only"]["timing"] == "violated"
    assert runs["sign-delay-timing-only"]["outcome"]["observed"] == "failed"
    assert runs["sign-delay-both"]["outcome"]["observed"] == "completed"
    # The producer's calibration bundle omits its qualification; the queue component is a named gap.
    assert any(
        f["code"] == "reset_evidence_incomplete" and "action_queue" in f["detail"]
        for f in runs["reference"]["findings"]
    )
    if root is not None:
        assert all("raw_trace_consistent" in codes_of(r) for r in runs.values())
        assert "artifact_manifest_verified" in {n["code"] for n in decision["notes"]}


@real_record
def test_carried_state_that_is_not_the_prefix_final_state_breaks_the_chain(calibration, tmp_path):
    document = copy.deepcopy(calibration)
    run = next(r for r in document["runs"] if r["id"] == "prefix-21-carried")
    run["trace"][0]["policy_state_sha256"] = "00" * 32
    decision = evaluate_bundle(write(document, tmp_path))
    result = decision["runs"]["prefix-21-carried"]
    assert result["measurement"] == "invalid"
    assert any(
        f["code"] == "trace_chain_broken" and "executed prefix" in f["detail"]
        for f in result["findings"]
    )


@real_record
def test_carried_state_naming_an_absent_prefix_is_incomplete(calibration, tmp_path):
    document = copy.deepcopy(calibration)
    document["runs"] = [r for r in document["runs"] if r["id"] != "prefix-21-carried-prefix"]
    decision = evaluate_bundle(write(document, tmp_path))
    result = decision["runs"]["prefix-21-carried"]
    assert any(
        f["code"] == "reset_evidence_incomplete" and "not in the bundle" in f["detail"]
        for f in result["findings"]
    )


@real_record
def test_recurrent_state_that_changes_without_a_reset_breaks_the_chain(calibration, tmp_path):
    document = copy.deepcopy(calibration)
    run = next(r for r in document["runs"] if r["id"] == "reference")
    run["trace"][3]["policy_state_sha256"] = "11" * 32
    decision = evaluate_bundle(write(document, tmp_path))
    result = decision["runs"]["reference"]
    assert result["measurement"] == "invalid"
    assert any(
        f["code"] == "trace_chain_broken" and "without a recorded reset" in f["detail"]
        for f in result["findings"]
    )


@real_record
def test_current_acquisition_must_be_the_previous_next_packet(calibration, tmp_path):
    document = copy.deepcopy(calibration)
    run = next(r for r in document["runs"] if r["id"] == "delay-3")
    run["trace"][4]["captured_observation_step"] = 9
    decision = evaluate_bundle(write(document, tmp_path))
    result = decision["runs"]["delay-3"]
    assert result["measurement"] == "invalid"
    assert any(
        f["code"] == "trace_chain_broken" and "captured_observation_step" in f["detail"]
        for f in result["findings"]
    )


@real_record
def test_deployment_digest_must_match_configuration(calibration, tmp_path):
    document = copy.deepcopy(calibration)
    run = next(r for r in document["runs"] if r["id"] == "axis-xz-corrected")
    run["configuration"]["deployment"]["repair_translation_order"] = [0, 1, 2]
    decision = evaluate_bundle(write(document, tmp_path))
    result = decision["runs"]["axis-xz-corrected"]
    assert any(
        f["code"] == "identity_mismatch" and "configuration.deployment" in f["detail"]
        for f in result["findings"]
    )


@real_record
def test_calibration_table_is_reproducible_from_the_decision(calibration, tmp_path):
    """The producer's table in FAMILY_CALIBRATION.md, recomputed from the record."""
    decision = evaluate_bundle(write(calibration, tmp_path))
    expected = {
        "reference": ("completed", 44),
        "delay-1": ("completed", 48),
        "delay-3": ("completed", 51),
        "delay-6": ("completed", 128),
        "stride-5": ("completed", 49),
        "reset-every-action": ("completed", 46),
        "prefix-21-clean": ("completed", 44),
        "prefix-21-carried": ("failed", 400),
        "prefix-39-clean": ("completed", 44),
        "prefix-39-carried": ("completed", 46),
        "axis-xz-changed": ("failed", 400),
        "axis-xz-corrected": ("completed", 44),
        "sign-delay-changed": ("failed", 400),
        "sign-delay-sign-only": ("completed", 51),
        "sign-delay-timing-only": ("failed", 400),
        "sign-delay-both": ("completed", 44),
    }
    steps = {r["id"]: len(r["trace"]) for r in calibration["runs"]}
    for run_id, (outcome, count) in expected.items():
        assert decision["runs"][run_id]["outcome"]["observed"] == outcome, run_id
        assert steps[run_id] == count, run_id
    json.dumps(decision)  # the decision is plain JSON


TELEMETRY = REPO / "docs/experiments/results/policy-telemetry-unavailable-001"
TELEMETRY_STORE = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/policy-telemetry-unavailable-001"
)


@pytest.mark.skipif(
    not (TELEMETRY / "bundle.json.gz").is_file() or not TELEMETRY_STORE.is_dir(),
    reason="the telemetry control record or its store is absent",
)
def test_null_recurrent_state_is_a_gap_on_both_sides_only(tmp_path):
    document = read_document(TELEMETRY / "bundle.json.gz")
    folder = tmp_path / "t"
    folder.mkdir()
    path = write_document(document, folder / "bundle.json")
    (folder / "artifact-manifest.json").write_bytes(
        (TELEMETRY / "artifact-manifest.json").read_bytes()
    )
    decision = evaluate_bundle(path, artifact_root=TELEMETRY_STORE)
    reference = decision["runs"]["reference"]
    assert reference["measurement"] == "unresolved"
    assert any(
        f["code"] == "reset_evidence_incomplete" and "policy_state" in f["detail"]
        for f in reference["findings"]
    )
    assert "raw_trace_mismatch" not in codes_of(reference)
    assert "raw_trace_consistent" in codes_of(reference)
    # A digest declared unavailable while the raw record carries a value is a mismatch.
    tampered = copy.deepcopy(document)
    run = next(r for r in tampered["runs"] if r["id"] == "reference")
    run["trace"][0]["state_before_sha256"] = None
    path = write_document(tampered, folder / "bundle-tampered.json")
    decision = evaluate_bundle(path, artifact_root=TELEMETRY_STORE)
    assert "raw_trace_mismatch" in codes_of(decision["runs"]["reference"])
