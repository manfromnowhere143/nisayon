"""Tests for the normalizer reference, the conventional diagnostic and the frozen controls."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from nisayon.evaluation import conventional_normalizer as conventional
from nisayon.evaluation import normalizer_reference as ref
from nisayon.evaluation.normalizer_controls import CONTRACT, build_controls, run_normalizer_controls

PACKET = Path(
    "/Users/danielwahnich/.codex/reports/nisayon-next-evidence-decision-2026-09-20-8i17bt5a/sources"
)
FLAGS = dict(ref.FLAG_DEFAULTS)


def _params(**kw):
    base = {"min": [0.0], "max": [2.0], "mean": [1.0], "std": [0.5], "q01": [0.1], "q99": [1.9]}
    base.update(kw)
    return ref.group_parameters(base, use_percentiles=False, path="t")


def test_override_rule_keeps_present_embodiments_and_fills_the_mirror():
    existing = {"e": {"state": {"a": {"min": [0.0]}}}}
    candidate = {"e": {"state": {"a": {"min": [5.0]}}}, "f": {"state": {"a": {"min": [7.0]}}}}
    kept = ref.effective_statistics(existing, candidate, False)
    assert kept["outcome"] == {"e": "kept", "f": "installed"}
    assert kept["nested"]["e"] == existing["e"] and kept["nested"]["f"] == candidate["f"]
    assert kept["mirror"]["e"] == candidate["e"], "the outer mirror takes the candidate silently"
    replaced = ref.effective_statistics(existing, candidate, True)
    assert replaced["outcome"]["e"] == "replaced" and replaced["nested"]["e"] == candidate["e"]


def test_mode_selection_reads_the_modality_configuration_not_the_outer_flag():
    config = {
        "state": {"mean_std_embedding_keys": ["a"], "sin_cos_embedding_keys": ["b"]},
        "action": {"mean_std_embedding_keys": None},
    }
    flags = dict(FLAGS, use_mean_std=True)
    assert ref.select_mode(config, "state", "a", flags) == "meanstd"
    assert ref.select_mode(config, "state", "b", flags) == "minmax"
    assert (
        ref.select_mode(config, "state", "b", dict(flags, apply_sincos_state_encoding=True))
        == "sincos"
    )
    assert ref.select_mode(config, "action", "u", flags) == "minmax"
    assert ref.clip_applies("state", "meanstd", flags) is False
    assert ref.clip_applies("action", "meanstd", flags) is True
    assert ref.clip_applies("state", "minmax", dict(flags, clip_outliers=False)) is False


def test_minmax_emulation_dtype_constants_and_rational_bound():
    params = _params(
        min=[0.0, 1000.0, 5.0],
        max=[2.0, 1000.005, 5.0],
        mean=[1.0, 1000.0, 5.0],
        std=[0.5, 0.001, 0.0],
        q01=[0.1, 1000.0, 5.0],
        q99=[1.9, 1000.005, 5.0],
    )
    x = np.asarray([[0.5, 1000.004, 5.0], [3.0, 1000.0, 5.0]], dtype=np.float32)
    y = ref.emulate_minmax(x, params, True)
    assert y.dtype == np.float32
    assert y[0, 0] == np.float32(-0.5) and y[1, 0] == 1.0  # clipped
    assert y[0, 1] == 0.0 and y[0, 2] == 0.0  # near-constant and constant coordinates map to 0
    exact = ref.exact_transform_value(0.5, params, 0, "minmax", True)
    assert abs(float(exact) - float(y[0, 0])) <= ref.rational_bound(
        "minmax", float(y[0, 0]), y.dtype
    )
    inverse = ref.emulate_inverse_minmax(y, params)
    assert inverse[0, 2] == 5.0 and abs(inverse[0, 1] - 1000.0025) < 1e-9


def test_meanstd_emulation_passthrough_and_overflow():
    params = _params(
        min=[0.0, 0.0],
        max=[2.0, 2.0],
        mean=[1.0, 1.0],
        std=[0.0, 1e-40],
        q01=[0.1, 0.1],
        q99=[1.9, 1.9],
    )
    x = np.asarray([[0.75, 0.75]], dtype=np.float32)
    y = ref.emulate_meanstd(x, params, False)
    assert y[0, 0] == np.float32(0.75), "zero std passes the raw value through"
    assert np.isinf(y[0, 1]), "a tiny std overflows the float32 store"
    y64 = ref.emulate_meanstd(x.astype(np.float64), params, False)
    assert np.isfinite(y64[0, 1])


def _case(**overrides):
    control = next(c for c in build_controls() if c["id"] == "NX1a")
    case = json.loads(json.dumps(control["case"]))
    case.update(overrides)
    return case


def test_decisions_follow_effective_maps_not_labels():
    keep = ref.assess_case(_case())
    assert (keep["decision"]["operation"], keep["decision"]["decision"]) == ("keep", "supported")
    alt = json.loads(json.dumps(CONTRACT))
    alt["state"]["a"]["max"] = [3.0]
    rejected = ref.assess_case(
        _case(candidate_statistics={"grouped": alt}, override=True, declared_operation="replace")
    )
    assert (
        rejected["decision"]["decision"] == "rejected"
        and rejected["decision"]["witness"] is not None
    )
    no_contract = ref.assess_case(_case(contract_statistics=None))
    assert (no_contract["decision"]["operation"], no_contract["decision"]["decision"]) == (
        "abstain",
        "unresolved",
    )
    binding = ref.assess_case(
        _case(
            execution_binding={"claims_selection": True, "calls": [{"function": "set_statistics"}]}
        )
    )
    assert (
        binding["decision"]["decision"] == "unresolved"
        and "call record" in binding["decision"]["reason"]
    )
    missing = json.loads(json.dumps(CONTRACT))
    del missing["state"]["a"]["std"]
    invalid = ref.assess_case(
        _case(existing_statistics={"grouped": missing}, contract_statistics={"grouped": missing})
    )
    assert invalid["decision"]["operation"] == "invalid"
    relabelled = ref.assess_case(_case(declared_role="training_reference", provenance="anything"))
    assert relabelled["decision"] == keep["decision"]


def test_producer_comparison_maps_install_to_replace_and_counts():
    reference = {"decision": {"operation": "replace", "decision": "supported"}}
    agree = ref.assess_producer(
        {"decision": {"selected_operation": "install_when_absent", "status": "supported"}},
        reference,
    )
    assert agree["agrees"] and agree["counts"]["useful_acceptance"]
    reference = {"decision": {"operation": "replace", "decision": "rejected"}}
    bad = ref.assess_producer(
        {"decision": {"selected_operation": "replace_with_candidate", "status": "supported"}},
        reference,
    )
    assert bad["counts"]["false_acceptance"] and bad["counts"]["unjustified_replacement"]
    unknown = ref.assess_producer(
        {"decision": {"selected_operation": "something", "status": "supported"}}, reference
    )
    assert unknown["status"] == "not_compared"


def test_conventional_diagnostic_decides_on_its_own_arithmetic():
    record = conventional.diagnose(_case())
    assert (record["decision"]["selected_operation"], record["decision"]["status"]) == (
        "keep",
        "supported",
    )
    assert "output_sha256" in record["groups"]["state"]["a"]


def test_frozen_controls_pass_and_the_conventional_workflow_misses_only_the_dtype_boundary():
    summary = run_normalizer_controls()
    assert summary["passed"] == summary["cases_evaluated"]
    assert summary["runs"] == 23 and len(summary["families"]) == 8
    assert summary["conventional_disagreements"] == ["NX5d"]
    assert summary["conventional_v2_disagreements"] == []


def test_conventional_v2_sees_the_float32_overflow_and_keeps_every_other_decision():
    controls = {c["id"]: c["case"] for c in build_controls()}
    v2 = conventional.diagnose(controls["NX5d"], arithmetic="input")
    assert (v2["decision"]["selected_operation"], v2["decision"]["status"]) == (
        "invalid",
        "invalid",
    )
    v1 = conventional.diagnose(controls["NX5d"])
    assert v1["decision"]["status"] == "supported"
    with pytest.raises(ValueError):
        conventional.diagnose(controls["NX1a"], arithmetic="float16")


@pytest.mark.skipif(
    not (PACKET / "groot-demo-stats.json").exists(), reason="retained packet not present"
)
def test_real_invocation_keep_supported_replace_rejected_and_no_minmax_clipping():
    controls = {c["id"]: c for c in build_controls()}
    keep = ref.assess_case(controls["NX7d"]["case"])
    assert (keep["decision"]["operation"], keep["decision"]["decision"]) == ("keep", "supported")
    assert all(
        g["rational_check"]["within_bound"] for m in keep["groups"].values() for g in m.values()
    )
    cov = ref.coverage(controls["NX7d"]["case"])
    assert (
        cov["rows"] == 1406
        and cov["total_outside_min_max"] == 0
        and cov["total_outside_q01_q99"] > 0
    )


STORE = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/normalizer-execution-001/producer-004"
)


@pytest.mark.skipif(not (STORE / "seal.json").exists(), reason="sealed execution store not present")
def test_sealed_store_real_runs_match_the_reference_at_zero_ulp():
    from nisayon.evaluation import normalizer_store as store

    assessment = store.assess_store(STORE, packet=PACKET)
    assert assessment["seal_checks"]["manifest_entries_bad"] == []
    for run_id in ("real-keep", "real-replace"):
        run = assessment["runs"][run_id]
        assert run["outputs_all_match"] and run["comparison"]["agrees"]
        assert run["selection"]["nested_matches_rule"] and run["selection"]["outer_matches_mirror"]
    assert assessment["counts"]["false_acceptance"] == 0
    assert assessment["counts"]["false_refusal"] == 0
    assert assessment["row_identity"]["runs"]["real-keep"]["bound"]
