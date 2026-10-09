"""The processor reference: arithmetic, container, contract and the eight controls.

Every test here demonstrates a distinct decision or failure the reference must make. The
statistics are synthetic or, where marked, the reporter's transcription from issue 4415;
none is a measured deployment.
"""

from __future__ import annotations

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from nisayon.evaluation import processor_reference as ref
from nisayon.evaluation.processor_controls import (
    ACTION_WITNESS,
    ALPHA,
    CONTROLS,
    build_explicit_override_complete,
    run_processor_controls,
    write_control,
)
from nisayon.evaluation.schema import Malformed

# The reporter's transcription of the pre-migration so100 observation.state statistics
# from the 11 August comment on issue 4415 (two decimals; the checkpoint is out of scope).
# Used here as arithmetic input of a realistic magnitude, not as a verified deployment value.
SO100_STATE_TRANSCRIBED = {
    "mean": [1.56, 118.65, 110.85, 56.63, -27.28, 13.95],
    "std": [26.15, 52.65, 49.38, 36.57, 58.90, 17.99],
}
EPS = Fraction(1e-8)


def _fr(values: list[float]) -> list[Fraction]:
    return [Fraction(ref.f32(v)) for v in values]


def test_every_control_reaches_its_expected_decision(tmp_path: Path) -> None:
    summary = run_processor_controls(tmp_path)
    failures = {row["name"]: row["failures"] for row in summary["controls"] if row["failures"]}
    assert failures == {}
    assert summary["all_ok"]
    outcomes = {row["name"]: row["reference_overall"] for row in summary["controls"]}
    assert outcomes == {
        "identity_mode_visual": "rejected_candidate",
        "fixed_point_witness": "unresolved",
        "prefixed_keys_exact_lookup": "rejected_candidate",
        "suffix_match_ambiguous": "rejected_candidate",
        "suffix_match_partial": "rejected_candidate",
        "explicit_override_complete": "supported_software_correction",
        "round_trip_cancels_wrong_stats": "rejected_candidate",
        "missing_std_error": "invalid_input",
        "label_only_promotion": "supported_software_correction",
        "artifact_label_without_bytes": "supported_software_correction",
        "artifact_label_with_matching_bytes": "supported_software_correction",
        "artifact_carries_complete_statistics": "supported_software_correction",
    }
    assert len(CONTROLS) == 12


def test_reporter_witness_discriminates_but_a_fixed_point_does_not() -> None:
    mean, std = _fr(SO100_STATE_TRANSCRIBED["mean"]), _fr(SO100_STATE_TRANSCRIBED["std"])
    witness = ref.mean_std_values(_fr([0.5] * 6), mean, std, EPS, "inverse")
    assert not witness.vacuous
    # The issue's printed ``torch.equal(fake_action, result) == True`` is what a skipped
    # transform gives; an inverse transform with statistics of this magnitude moves 0.5 on
    # channel 0 to 0.5 * 26.15 + 1.56.
    assert abs(float(witness.exact[0]) - (0.5 * 26.15 + 1.56)) < 1e-3
    points = ref.fixed_point(mean, std, EPS, "inverse")
    at_point = ref.mean_std_values(
        [Fraction(ref.f32(float(p))) for p in points], mean, std, EPS, "inverse"
    )
    assert at_point.vacuous


def test_tolerance_propagates_intermediate_rounding_near_a_fixed_point() -> None:
    mean, std = _fr(SO100_STATE_TRANSCRIBED["mean"]), _fr(SO100_STATE_TRANSCRIBED["std"])
    x = Fraction(ref.f32(float(mean[1] / (1 - std[1]))))
    propagated = ref.tolerance("inverse", x, mean[1], std[1], EPS)
    output_only = ref.ULP_TOLERANCE * ref.ulp32(float(x * std[1] + mean[1])) + ref.ABSOLUTE_FLOOR
    # The rounded product x·std (about 122) contributes far more than the output's ulp.
    assert propagated > 10 * output_only
    emulated = ref.f32(ref.f32(float(x) * float(std[1])) + float(mean[1]))
    exact = x * std[1] + mean[1]
    assert abs(Fraction(emulated) - exact) <= propagated
    assert abs(Fraction(emulated) - exact) > output_only


def test_torch_float32_path_matches_the_emulation_bit_for_bit() -> None:
    torch = pytest.importorskip("torch")
    mean, std = _fr(SO100_STATE_TRANSCRIBED["mean"]), _fr(SO100_STATE_TRANSCRIBED["std"])
    t_mean = torch.tensor(SO100_STATE_TRANSCRIBED["mean"], dtype=torch.float32)
    t_std = torch.tensor(SO100_STATE_TRANSCRIBED["std"], dtype=torch.float32)
    raw = [10.0, 100.0, 90.0, 40.0, -30.0, 20.0]
    points = [ref.f32(float(p)) for p in ref.fixed_point(mean, std, EPS, "inverse")]
    cases = [
        ("inverse", [0.5] * 6),
        ("inverse", points),
        ("forward", raw),
    ]
    for direction, values in cases:
        expected = ref.mean_std_values(_fr(values), mean, std, EPS, direction)
        tensor = torch.tensor(values, dtype=torch.float32)
        # Lines 357–362 of the pinned normalize_processor.py, transcribed.
        if direction == "inverse":
            observed = tensor * t_std + t_mean
        else:
            observed = (tensor - t_mean) / (t_std + 1e-8)
        result = ref.compare(expected, [Fraction(v) for v in observed.tolist()])
        assert result["within_tolerance"], (direction, values, result)
        assert result["bit_exact_float32"], (direction, values, result)


def test_safetensors_container_round_trip_and_malformed_forms() -> None:
    data = ref.write_safetensors({"so100.buffer.action.mean": [1.5, -2.0], "x.std": [0.25]})
    tensors = ref.read_safetensors(data)
    assert tensors["so100.buffer.action.mean"] == {
        "dtype": "F32",
        "shape": [2],
        "values": [1.5, -2.0],
    }
    grouped = ref.flat_statistics(tensors)
    assert list(grouped) == ["so100.buffer.action", "x"]
    assert grouped["so100.buffer.action"]["mean"] == [Fraction(3, 2), Fraction(-2)]
    with pytest.raises(Malformed) as short:
        ref.read_safetensors(data[:5])
    assert "shorter" in short.value.detail
    with pytest.raises(Malformed) as header:
        ref.read_safetensors(b"\xff" * 8 + data[8:])
    assert header.value.path == "safetensors"
    corrupt = bytearray(data)
    corrupt[8:9] = b"x"  # invalid JSON header
    with pytest.raises(Malformed) as bad_json:
        ref.read_safetensors(bytes(corrupt))
    assert bad_json.value.path == "safetensors.header"
    header_bytes = b'{"a.mean":{"dtype":"BF16","shape":[1],"data_offsets":[0,2]}}'
    unsupported = ref.read_safetensors(
        len(header_bytes).to_bytes(8, "little") + header_bytes + b"\x00\x00"
    )
    assert unsupported["a.mean"]["dtype"] == "BF16" and unsupported["a.mean"]["values"] is None
    with pytest.raises(Malformed):
        ref.flat_statistics({"nodot": {"dtype": "F32", "shape": [1], "values": [0.0]}})


def test_key_resolution_per_candidate() -> None:
    keys = ["so100.buffer.action", "so100-blue.buffer.action", "old_action", "observation.state"]
    assert ref.resolve_key("action", keys, "as_is") == (None, [])
    assert ref.resolve_key("observation.state", keys, "as_is") == (
        "observation.state",
        ["observation.state"],
    )
    bound, matches = ref.resolve_key("action", keys, "suffix_match")
    assert bound == "so100.buffer.action"
    assert matches == ["so100.buffer.action", "so100-blue.buffer.action", "old_action"]
    assert ref.resolve_key("action", list(reversed(keys)), "suffix_match")[0] == "old_action"
    assert ref.resolve_key("observation.state", keys, "explicit_override")[0] == "observation.state"
    with pytest.raises(Malformed):
        ref.resolve_key("action", keys, "guess")


def test_processor_config_layout_problems_are_named() -> None:
    step = {
        "registry_name": "normalizer_processor",
        "config": {
            "eps": 1e-8,
            "features": {"action": {"type": "ACTION", "shape": [6]}},
            "norm_map": {"ACTION": "MEAN_STD"},
        },
        "state_file": "s.safetensors",
    }
    spec = ref.parse_processor_config({"steps": [{}, step]}, "preprocessor")
    assert (spec.step_index, spec.state_file, spec.eps) == (1, "s.safetensors", Fraction(1e-8))
    with pytest.raises(Malformed) as twice:
        ref.parse_processor_config({"steps": [step, step]}, "preprocessor")
    assert "exactly one normalizer_processor" in twice.value.detail
    with pytest.raises(Malformed) as wrong_role:
        ref.parse_processor_config({"steps": [step]}, "postprocessor")
    assert "unnormalizer_processor" in wrong_role.value.detail
    broken = json.loads(json.dumps(step))
    broken["config"]["eps"] = "1e-8"
    with pytest.raises(Malformed) as eps:
        ref.parse_processor_config({"steps": [broken]}, "preprocessor")
    assert eps.value.path.endswith(".eps")
    no_features = json.loads(json.dumps(step))
    no_features["config"]["features"] = {}
    with pytest.raises(Malformed) as features:
        ref.parse_processor_config({"steps": [no_features]}, "preprocessor")
    assert features.value.path.endswith(".features")


def test_expectation_classes_from_contract_and_bytes() -> None:
    spec = ref.ProcessorSpec(
        "postprocessor",
        0,
        "unnormalizer_processor",
        {
            "action": ref.Feature("action", "ACTION", (6,)),
            "observation.state": ref.Feature("observation.state", "STATE", (6,)),
            "observation.images.top": ref.Feature("observation.images.top", "VISUAL", (3, 2, 2)),
        },
        {"ACTION": "MEAN_STD", "STATE": "MEAN_STD", "VISUAL": "IDENTITY"},
        Fraction(1e-8),
        None,
        None,
    )
    stats = {"so100.buffer.action": {"mean": _fr(ALPHA["mean"]), "std": _fr(ALPHA["std"])}}
    assert ref.expectation(spec, stats, "action", "inverse", "as_is").klass == "skipped_no_stats"
    unique = ref.expectation(spec, stats, "action", "inverse", "suffix_match")
    assert (unique.klass, unique.bound_key) == ("transformed", "so100.buffer.action")
    # The postprocessor does not unnormalize observations at inference.
    state = ref.expectation(spec, stats, "observation.state", "inverse", "as_is")
    assert state.klass == "not_applicable"
    assert ref.expectation(spec, stats, "action", "forward", "as_is").klass == "not_applicable"
    plain = {"action": {"mean": _fr(ALPHA["mean"]), "std": None}}
    assert ref.expectation(spec, plain, "action", "inverse", "as_is").klass == "error"
    unknown = ref.expectation(spec, stats, "observation.language", "inverse", "as_is")
    assert unknown.klass == "not_applicable"


def test_digest_mismatch_makes_the_record_invalid(tmp_path: Path) -> None:
    record, files = build_explicit_override_complete()
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    (tmp_path / "preprocessor.safetensors").write_bytes(
        ref.write_safetensors({"other.action.mean": [0.0] * 6, "other.action.std": [1.0] * 6})
    )
    assessment = ref.assess(record, tmp_path)
    assert assessment["reference_decision"]["overall"] == "invalid_input"
    assert not assessment["inputs"]["preprocessor_stats"]["digest_matches"]
    assert [f["code"] for f in assessment["findings"] if f["severity"] == "invalid"] == [
        "artifact_digest_mismatch"
    ]
    # The same record with intact bytes is the supported positive path.
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    intact = ref.assess(record, tmp_path)
    assert intact["reference_decision"]["overall"] == "supported_software_correction"
    assert intact["decision_agreement"]["all_agree"]


def test_malformed_records_are_named_not_tracebacks(tmp_path: Path) -> None:
    record, files = build_explicit_override_complete()
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    with pytest.raises(Malformed) as schema:
        ref.assess({**record, "schema": "nisayon.other.v1"}, tmp_path)
    assert schema.value.path == "$.schema"
    bad = json.loads(json.dumps(record))
    bad["executions"][0]["output"] = [0.1, float("nan")] if False else [0.1, "x"]
    with pytest.raises(Malformed) as output:
        ref.assess(bad, tmp_path)
    assert output.value.path == "$.executions[0].output[1]"
    missing = json.loads(json.dumps(record))
    missing["inputs"]["postprocessor_stats"]["path"] = "absent.safetensors"
    with pytest.raises(Malformed) as absent:
        ref.assess(missing, tmp_path)
    assert absent.value.path == "$.inputs.postprocessor_stats.path"
    provenance = json.loads(json.dumps(record))
    provenance["executions"][0]["stats_provenance"] = "trust me"
    with pytest.raises(Malformed) as prov:
        ref.assess(provenance, tmp_path)
    assert prov.value.path.endswith(".stats_provenance")


def test_cli_processor_and_controls(tmp_path: Path) -> None:
    out = tmp_path / "controls"
    completed = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "processor-controls", "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().endswith("all ok")
    record = write_control(CONTROLS[5], tmp_path / "one")
    result = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "processor", str(record), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assessment = json.loads(result.stdout)
    assert assessment["schema"] == ref.ASSESSMENT_SCHEMA
    assert assessment["reference_decision"]["overall"] == "supported_software_correction"
    per = assessment["reference_decision"]["per_candidate"]["explicit_override"]
    assert per["deployment_binding"] == "unresolved"
    assert [row["input"] for row in json.loads(record.read_text())["executions"]][
        0
    ] == ACTION_WITNESS
    broken = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "processor", str(tmp_path / "nope.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert broken.returncode == 2 and "error" in broken.stderr


def test_execution_record_adapter_completes_the_counterpart_from_the_manifest(
    tmp_path: Path,
) -> None:
    record, files = build_explicit_override_complete()
    root = tmp_path / "lane"
    capture = root / "artifacts" / "capture"
    capture.mkdir(parents=True)
    names = {
        "preprocessor.json": "policy_preprocessor.json",
        "postprocessor.json": "policy_postprocessor.json",
        "preprocessor.safetensors": "policy_preprocessor_step_5_normalizer_processor.safetensors",
        "postprocessor.safetensors": "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    }
    for local, upstream in names.items():
        (capture / upstream).write_bytes(files[local])
    manifest = {
        "schema": ref.CAPTURE_SCHEMA,
        "retrieved": [
            {
                "path": f"artifacts/capture/{upstream}",
                "bytes": len(files[local]),
                "sha256": ref.hashlib.sha256(files[local]).hexdigest(),
            }
            for local, upstream in names.items()
        ],
    }
    execution = {
        "schema": ref.EXECUTION_SCHEMA,
        "recorded_at": "2026-09-20T13:03:47Z",
        "incident": {"id": "synthetic"},
        "inputs": [
            {
                "role": "pipeline_config",
                "path": "artifacts/capture/policy_postprocessor.json",
                "sha256": manifest["retrieved"][1]["sha256"],
                "bytes": manifest["retrieved"][1]["bytes"],
            },
            {
                "role": "processor_state",
                "path": "artifacts/capture/"
                "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
                "sha256": manifest["retrieved"][3]["sha256"],
                "bytes": manifest["retrieved"][3]["bytes"],
            },
        ],
        "operation": {
            "pipeline": "policy_postprocessor",
            "requested_feature_key": "action",
            "inverse": True,
            "witness": ACTION_WITNESS,
        },
        "execution": {"process_status": "completed"},
        "observation": {"status": "observed", "output": ACTION_WITNESS},
        "cost": {"command_wall_seconds": 1.0},
    }
    adapted = ref.observation_from_execution_record(execution, manifest)
    assert set(adapted["inputs"]) == {
        "preprocessor_config",
        "preprocessor_stats",
        "postprocessor_config",
        "postprocessor_stats",
    }
    assert adapted["executions"][0]["candidate"] == "as_is"
    assessment = ref.assess(adapted, root)
    assert assessment["reference_decision"]["overall"] == "rejected_candidate"
    verdict = assessment["reference_decision"]["per_candidate"]["as_is"]
    assert verdict["unmet"] == [
        "postprocessor:action:inverse: skipped_no_stats",
        "preprocessor:observation.state:forward: skipped_no_stats (no statistics key "
        "resolves 'observation.state': the pinned step returns the input)",
    ]
    # Without the manifest the counterpart pipeline is missing and the record is malformed.
    with pytest.raises(Malformed) as missing:
        ref.assess(ref.observation_from_execution_record(execution, None), root)
    assert missing.value.path == "$.inputs.preprocessor_config"
    interrupted = json.loads(json.dumps(execution))
    interrupted["execution"]["process_status"] = "interrupted"
    interrupted["observation"] = {"status": "unresolved", "reason": "stopped"}
    row = ref.observation_from_execution_record(interrupted, manifest)["executions"][0]
    assert row["status"] == "interrupted" and "output" not in row


def test_merging_single_operation_records_covers_every_candidate(tmp_path: Path) -> None:
    record, files = build_explicit_override_complete()
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    parts = []
    for execution in record["executions"]:
        part = json.loads(json.dumps(record))
        part["executions"] = [execution]
        part.pop("decision")
        parts.append(part)
    parts[-1]["decision"] = record["decision"]
    merged = ref.merge_observations(parts)
    assert [row["id"] for row in merged["executions"]] == ["C1", "C2", "C3"]
    assessment = ref.assess(merged, tmp_path)
    assert assessment["reference_decision"]["overall"] == "supported_software_correction"
    assert assessment["decision_agreement"]["all_agree"]
    # A single part alone leaves the other obligation uncovered: unresolved, not supported.
    alone = ref.assess(parts[0], tmp_path)
    assert alone["reference_decision"]["per_candidate"]["explicit_override"]["outcome"] == (
        "unresolved"
    )
    conflicting = json.loads(json.dumps(parts))
    conflicting[1]["inputs"]["preprocessor_stats"]["sha256"] = "0" * 64
    with pytest.raises(Malformed) as differs:
        ref.merge_observations(conflicting)
    assert differs.value.path == "$[1].inputs.preprocessor_stats"
    other_arm = json.loads(json.dumps(parts))
    other_arm[1]["arm"] = "A"
    with pytest.raises(Malformed):
        ref.merge_observations(other_arm)


def test_case_store_adapter_takes_conditions_from_the_frozen_case(tmp_path: Path) -> None:
    from nisayon.evaluation.processor_controls import ALPHA, BETA, STATE_REF, _store, prefixed

    record, files = build_explicit_override_complete()
    sources = tmp_path / "sources"
    sources.mkdir()
    names = {
        "preprocessor.json": "policy_preprocessor.json",
        "postprocessor.json": "policy_postprocessor.json",
        "preprocessor.safetensors": "policy_preprocessor_step_5_normalizer_processor.safetensors",
        "postprocessor.safetensors": "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    }
    for local, upstream in names.items():
        (sources / upstream).write_bytes(files[local])
    roles = {
        "policy_preprocessor.json": "preprocessor_config",
        "policy_postprocessor.json": "postprocessor_config",
        "policy_preprocessor_step_5_normalizer_processor.safetensors": "preprocessor_state",
        "policy_postprocessor_step_0_unnormalizer_processor.safetensors": "postprocessor_state",
    }
    case = {
        "schema": ref.CASE_SCHEMA,
        "id": "synthetic-case",
        "frozen_at": "2026-09-20T13:21:22Z",
        "incident": {"id": "synthetic"},
        "sources": [
            {
                "role": roles[upstream],
                "path": upstream,
                "sha256": ref.hashlib.sha256(files[local]).hexdigest(),
                "bytes": len(files[local]),
            }
            for local, upstream in names.items()
        ],
        "candidates": [
            {"id": "C0_as_is"},
            {"id": "C1_suffix_match"},
            {
                "id": "C2_explicit_override",
                "stats": {"action": ALPHA, "observation.state": STATE_REF},
            },
        ],
        "suffix_orders": [
            ["alpha.buffer.action", "beta.buffer.action", "gamma.buffer.action"],
            ["gamma.buffer.action", "beta.buffer.action", "alpha.buffer.action"],
        ],
        "assignments": [
            "incident-C1-action-original-order",
            "incident-C1-action-reordered",
            "incident-C2-action",
            "incident-C3-remigration-availability",
            "control-identity-mode-visual",
        ],
    }
    store = tmp_path / "store"
    (store / "executions").mkdir(parents=True)
    layout = _store(prefixed({"alpha.buffer": ALPHA, "beta.buffer": BETA}))

    def execution(assignment: str, candidate: str, output: list[float], **extra: object) -> None:
        body = {
            "schema": ref.STORE_EXECUTION_SCHEMA,
            "assignment_id": assignment,
            "candidate": candidate,
            "processor": "postprocessor",
            "feature": "action",
            "direction": "inverse",
            "process_status": "completed",
            # The producer's own resolution is deliberately wrong here: it must be ignored.
            "statistics_key": "beta.buffer.action",
            "statistics_matches": ["beta.buffer.action"],
            "observation": {"status": "completed", "input": ACTION_WITNESS, "output": output},
        }
        body.update(extra)
        (store / "executions" / f"{assignment}.json").write_text(json.dumps(body))

    from nisayon.evaluation.processor_controls import stand_in_transform

    first, _ = stand_in_transform(
        {"alpha.buffer.action": layout["alpha.buffer.action"]},
        "alpha.buffer.action",
        ACTION_WITNESS,
        "inverse",
        "as_is",
    )
    reordered, _ = stand_in_transform(
        {"gamma.buffer.action": {"mean": [-1.0] * 6, "std": [0.5] * 6}},
        "gamma.buffer.action",
        ACTION_WITNESS,
        "inverse",
        "as_is",
    )
    override, _ = stand_in_transform(
        {"action": ALPHA}, "action", ACTION_WITNESS, "inverse", "as_is"
    )
    execution("incident-C1-action-original-order", "C1_suffix_match", first)
    execution("incident-C1-action-reordered", "C1_suffix_match", reordered)
    execution("incident-C2-action", "C2_explicit_override", override)
    execution(
        "incident-C3-remigration-availability",
        "C3_remigration",
        [],
        observation={"status": "unavailable", "input": None, "output": None},
    )
    (store / "executions" / "control-identity-mode-visual.json").write_text(
        json.dumps({"schema": ref.STORE_EXECUTION_SCHEMA, "candidate": "control"})
    )
    observation = ref.observation_from_case_store(store, case, sources)
    rows = {row["id"]: row for row in observation["executions"]}
    assert set(rows) == {
        "incident-C1-action-original-order",
        "incident-C1-action-reordered",
        "incident-C2-action",
    }
    assert rows["incident-C1-action-original-order"]["stats_order"] == case["suffix_orders"][0]
    assert rows["incident-C1-action-reordered"]["stats_order"] == case["suffix_orders"][1]
    assert rows["incident-C2-action"]["override_stats"] == case["candidates"][2]["stats"]
    assert observation["decision"] is None
    assessment = ref.assess(observation, None)
    by_id = {row["id"]: row for row in assessment["executions"]}
    # Expectations come from the frozen order, not from the producer's declared key.
    assert by_id["incident-C1-action-original-order"]["expected"]["bound_key"] == (
        "alpha.buffer.action"
    )
    assert by_id["incident-C1-action-original-order"]["agreement"] == "agrees"
    assert by_id["incident-C2-action"]["agreement"] == "agrees"
    (store / "summary.json").write_text(
        json.dumps(
            {
                "schema": ref.STORE_SUMMARY_SCHEMA,
                "decisions": {
                    "candidates": [
                        {"candidate": "C0_as_is", "outcome": "rejected_candidate"},
                        {"candidate": "C2_explicit_override", "outcome": "unresolved"},
                    ],
                    "software_decision": "unresolved",
                },
            }
        )
    )
    with_summary = ref.observation_from_case_store(store, case, sources)
    assert with_summary["decision"]["candidates"]["explicit_override"]["outcome"] == "unresolved"


def test_no_declared_label_reaches_a_supported_binding(tmp_path: Path) -> None:
    """The version-1 promotion: only labels change, and the binding must not move."""
    from nisayon.evaluation.processor_controls import build_explicit_override_complete

    record, files = build_explicit_override_complete()
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    baseline = ref.assess(record, tmp_path)
    before = baseline["reference_decision"]["per_candidate"]["explicit_override"]
    assert before["outcome"] == "supported_software_correction"
    assert before["deployment_binding"] == "unresolved"
    for label in sorted(ref.STATS_PROVENANCE):
        relabelled = json.loads(json.dumps(record))
        for row in relabelled["executions"]:
            row["stats_provenance"] = label
        verdict = ref.assess(relabelled, tmp_path)["reference_decision"]["per_candidate"][
            "explicit_override"
        ]
        assert verdict["outcome"] == "supported_software_correction", label
        assert verdict["deployment_binding"] == "unresolved", label
        # Byte provenance is decided from the bytes, whatever the label says.
        per = {
            f["feature"]: f["byte_provenance"] for f in verdict["binding_evidence"]["per_feature"]
        }
        assert per == {
            "action": "matches_artifact_set",
            "observation.state": "not_established",
        }, label
        assert verdict["binding_evidence"]["selection"] == ref.NOT_CARRIED
    assert baseline["schema"] == "nisayon.processor-reference.assessment.v2"
    assert baseline["decision_rule"] == "external-decision-001/v2"
    assert "binding_contract_limit" in baseline


def test_byte_provenance_is_established_only_from_the_verified_artifact() -> None:
    from nisayon.evaluation.processor_controls import ALPHA, BETA, _store, prefixed

    artifact = {
        key: {stat: _fr(values) for stat, values in entry.items()}
        for key, entry in _store(prefixed({"alpha.buffer": ALPHA, "beta.buffer": BETA})).items()
    }
    stats = {"mean": _fr(ALPHA["mean"]), "std": _fr(ALPHA["std"])}
    base = ("action", "ACTION", "postprocessor", "inverse")
    read = ref.Expectation(
        *base,
        "suffix_match",
        "MEAN_STD",
        "transformed",
        "alpha.buffer.action",
        ("alpha.buffer.action",),
        "",
        stats,
    )
    assert ref.byte_provenance(read, artifact, "suffix_match") == {
        "status": "established_from_artifact",
        "artifact_key": "alpha.buffer.action",
    }
    override = ref.Expectation(
        *base, "explicit_override", "MEAN_STD", "transformed", "action", ("action",), "", stats
    )
    assert ref.byte_provenance(override, artifact, "explicit_override") == {
        "status": "matches_artifact_set",
        "artifact_key": "alpha.buffer.action",
    }
    nudged = {"mean": _fr(ALPHA["mean"]), "std": _fr([v + 1e-3 for v in ALPHA["std"]])}
    other = ref.Expectation(
        *base, "explicit_override", "MEAN_STD", "transformed", "action", ("action",), "", nudged
    )
    assert ref.byte_provenance(other, artifact, "explicit_override")["status"] == "not_established"
    skipped = ref.Expectation(*base, "as_is", "MEAN_STD", "skipped_no_stats", None, (), "")
    assert ref.byte_provenance(skipped, artifact, "as_is")["status"] == "not_applicable"


def test_a_declared_supported_binding_is_compared_not_adopted(tmp_path: Path) -> None:
    from nisayon.evaluation.processor_controls import build_explicit_override_complete

    record, files = build_explicit_override_complete()
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    record["decision"]["deployment_applicability"] = "supported"
    for row in record["executions"]:
        row["stats_provenance"] = "verified_training_statistics"
    assessment = ref.assess(record, tmp_path)
    agreement = assessment["decision_agreement"]
    assert agreement["all_agree"]
    assert agreement["declared_deployment_binding"] == "supported"
    assert agreement["false_binding_acceptance"]
    verdict = assessment["reference_decision"]["per_candidate"]["explicit_override"]
    assert verdict["deployment_binding"] == "unresolved"
    details = [
        f["detail"]
        for f in assessment["findings"]
        if f["code"] == "provenance_declared_not_established"
    ]
    assert any(d.startswith("producer declares deployment binding supported") for d in details)
    honest = json.loads(json.dumps(record))
    honest["decision"]["deployment_applicability"] = "unresolved"
    assert not ref.assess(honest, tmp_path)["decision_agreement"]["false_binding_acceptance"]
