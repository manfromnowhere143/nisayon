"""Constructed controls for the processor reference.

Eight labelled synthetic records, one question each, from the challenge set frozen in
``docs/evaluation/results/external-decision-001/QUALIFICATION.md``. They are not
incidents and enter no incident count. Each control writes a saved-pipeline layout
(configuration JSON and safetensors state files) with round synthetic statistics that
carry no deployment meaning, produces observations with a stand-in transcribed from the
pinned ``_apply_transform`` and the reporter's suffix candidate, and states what the
reference must conclude. Some records deliberately claim a wrong output or a wrong
decision so the rejection paths are exercised, not only the positive one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .processor_reference import (
    NORMALIZER_STEPS,
    OBSERVATION_SCHEMA,
    assess,
    f32,
    write_safetensors,
)

FEATURES = {
    "observation.state": {"type": "STATE", "shape": [6]},
    "observation.images.top": {"type": "VISUAL", "shape": [3, 2, 2]},
    "action": {"type": "ACTION", "shape": [6]},
}
NORM_MAP = {"VISUAL": "IDENTITY", "STATE": "MEAN_STD", "ACTION": "MEAN_STD"}
EPS = 1e-8
# Round synthetic statistics: no dataset, robot or deployment meaning.
ALPHA = {"mean": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "std": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]}
BETA = {"mean": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0], "std": [3.0] * 6}
GAMMA = {"mean": [-1.0, -2.0, -3.0, -4.0, -5.0, -6.0], "std": [0.5] * 6}
STATE_REF = {"mean": [0.5, 1.0, -1.0, 2.0, 0.25, 4.0], "std": [1.5, 2.0, 0.5, 4.0, 1.0, 2.5]}
STATE_WRONG = {"mean": [0.0] * 6, "std": [1.0] * 6}
ACTION_WITNESS = [0.5, -1.0, 2.0, 0.25, -0.75, 1.5]
STATE_WITNESS = [3.0, 7.0, -2.0, 11.0, 0.5, 4.0]
IMAGE_WITNESS = [0.0, 0.25, 0.5, 0.75, 1.0, 0.125, 0.375, 0.625, 0.875, 0.2, 0.4, 0.6]


def prefixed(datasets: dict[str, dict], key: str = "action") -> dict[str, list[float]]:
    """Flat ``<dataset>.<key>.<stat>`` tensors in the migrated layout, in the given order."""
    flat: dict[str, list[float]] = {}
    for prefix, stats in datasets.items():
        for name, values in stats.items():
            flat[f"{prefix}.{key}.{name}"] = list(values)
    return flat


def processor_config(role: str, state_file: str | None, features: dict = FEATURES) -> dict:
    """A saved ``PolicyProcessorPipeline`` layout with the (un)normalizer at a fixed index."""
    filler = {"registry_name": "rename_observations_processor", "config": {"rename_map": {}}}
    step = {
        "registry_name": NORMALIZER_STEPS[role],
        "config": {"eps": EPS, "features": features, "norm_map": NORM_MAP},
    }
    if state_file is not None:
        step["state_file"] = state_file
    steps = [dict(filler) for _ in range(5)] + [step] if role == "preprocessor" else [step]
    return {"name": f"policy_{role}", "steps": steps}


# --- producer stand-in --------------------------------------------------------------------


def _resolve_stats_key(key: str, stats: dict) -> str | None:
    """The reporter's candidate, transcribed from issue 4415 (first match on ambiguity)."""
    if key in stats:
        return key
    suffix = f".{key}"
    matches = [k for k in stats if k.endswith(suffix) or k.endswith(f"_{key}")]
    if matches:
        return matches[0]
    return None


def stand_in_transform(
    store: dict[str, dict[str, list[float]]],
    key: str,
    values: list[float],
    direction: str,
    candidate: str,
) -> tuple[list[float] | None, str | None]:
    """Transcription of ``_apply_transform`` for MEAN_STD (lines 329–362) in float32.

    Returns ``(output, error)``. Used only to produce control observations; the reference
    never calls it.
    """
    bound = (
        _resolve_stats_key(key, store)
        if candidate == "suffix_match"
        else (key if key in store else None)
    )
    if bound is None:
        return list(values), None
    stats = store[bound]
    mean = stats.get("mean")
    std = stats.get("std")
    if mean is None or std is None:
        return None, "MEAN_STD normalization mode requires mean and std stats"
    out = []
    for x, m, s in zip(values, mean, std, strict=True):
        if direction == "inverse":
            out.append(f32(f32(x * s) + m))
        else:
            out.append(f32(f32(x - m) / f32(s + f32(EPS))))
    return out, None


# --- records -------------------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _execution(
    identifier: str,
    candidate: str,
    processor: str,
    feature: str,
    direction: str,
    values: list[float],
    store: dict,
    *,
    override: dict | None = None,
    provenance: str = "artifact",
    stats_order: list[str] | None = None,
    output: list[float] | None = None,
    status: str | None = None,
) -> dict:
    lookup = "action" if feature == "action" else feature
    ordered = store if not stats_order else {k: store[k] for k in stats_order}
    if feature == "observation.images.top":
        produced, error = list(values), None
    else:
        produced, error = stand_in_transform(
            override if override is not None else ordered, lookup, values, direction, candidate
        )
    row = {
        "id": identifier,
        "candidate": candidate,
        "processor": processor,
        "feature": feature,
        "direction": direction,
        "input": list(values),
        "status": status or ("error" if error else "completed"),
        "stats_provenance": provenance,
    }
    if row["status"] == "completed":
        row["output"] = output if output is not None else produced
    if error:
        row["error"] = error
    if override is not None:
        row["override_stats"] = override
    if stats_order:
        row["stats_order"] = stats_order
    return row


def _store(flat: dict[str, list[float]]) -> dict[str, dict[str, list[float]]]:
    grouped: dict[str, dict[str, list[float]]] = {}
    for name, values in flat.items():
        key, stat = name.rsplit(".", 1)
        grouped.setdefault(key, {})[stat] = values
    return grouped


@dataclass(frozen=True)
class Control:
    name: str
    question: str
    build: Callable[[], tuple[dict, dict[str, bytes]]]
    check: Callable[[dict], list[str]]


def _files(pre_flat: dict, post_flat: dict) -> dict[str, bytes]:
    pre_state = write_safetensors(pre_flat)
    post_state = write_safetensors(post_flat)
    return {
        "preprocessor.json": json.dumps(
            processor_config("preprocessor", "preprocessor.safetensors"), indent=1
        ).encode(),
        "postprocessor.json": json.dumps(
            processor_config("postprocessor", "postprocessor.safetensors"), indent=1
        ).encode(),
        "preprocessor.safetensors": pre_state,
        "postprocessor.safetensors": post_state,
    }


def _record(arm: str, files: dict[str, bytes], executions: list[dict], **extra: object) -> dict:
    inputs = {
        "preprocessor_config": "preprocessor.json",
        "postprocessor_config": "postprocessor.json",
        "preprocessor_stats": "preprocessor.safetensors",
        "postprocessor_stats": "postprocessor.safetensors",
    }
    record = {
        "schema": OBSERVATION_SCHEMA,
        "arm": arm,
        "incident": {
            "id": "synthetic-control",
            "provenance": "constructed control; not an incident",
        },
        "inputs": {
            role: {"path": name, "bytes": len(files[name]), "sha256": _sha256(files[name])}
            for role, name in inputs.items()
        },
        "executions": executions,
    }
    record.update(extra)
    return record


def _outcome(assessment: dict, candidate: str) -> str:
    return assessment["reference_decision"]["per_candidate"][candidate]["outcome"]


def _row(assessment: dict, identifier: str) -> dict:
    return next(r for r in assessment["executions"] if r["id"] == identifier)


INCIDENT_LAYOUT = prefixed({"alpha.buffer": ALPHA, "beta.buffer": BETA, "gamma.buffer": GAMMA})


def build_identity_mode_visual() -> tuple[dict, dict[str, bytes]]:
    files = _files(INCIDENT_LAYOUT, INCIDENT_LAYOUT)
    store = _store(INCIDENT_LAYOUT)
    unchanged = _execution(
        "I1", "as_is", "preprocessor", "observation.images.top", "forward", IMAGE_WITNESS, store
    )
    altered = _execution(
        "I2",
        "explicit_override",
        "preprocessor",
        "observation.images.top",
        "forward",
        IMAGE_WITNESS,
        store,
        override={"action": ALPHA, "observation.state": STATE_REF},
        provenance="synthetic_control",
        output=[v * 2 for v in IMAGE_WITNESS],
    )
    return _record("B", files, [unchanged, altered]), files


def check_identity_mode_visual(a: dict) -> list[str]:
    failures = []
    if (
        _row(a, "I1")["expected"]["class"] != "identity_mode"
        or _row(a, "I1")["agreement"] != "agrees"
    ):
        failures.append("unchanged IDENTITY visual output must agree with the reference")
    if _row(a, "I2")["agreement"] != "disagrees":
        failures.append("a changed IDENTITY visual output must disagree")
    override = a["reference_decision"]["per_candidate"]["explicit_override"]
    if override["outcome"] != "rejected_candidate" or not override["legitimacy_violations"]:
        failures.append("changing an IDENTITY feature must reject the candidate")
    return failures


def build_fixed_point_witness() -> tuple[dict, dict[str, bytes]]:
    files = _files(INCIDENT_LAYOUT, INCIDENT_LAYOUT)
    store = _store(INCIDENT_LAYOUT)
    override = {"action": ALPHA, "observation.state": STATE_REF}
    # Elementwise fixed points of the inverse transform: x = mean / (1 - std).
    point = [f32(m / (1 - s)) for m, s in zip(ALPHA["mean"], ALPHA["std"], strict=True)]
    fixed = _execution(
        "F1",
        "explicit_override",
        "postprocessor",
        "action",
        "inverse",
        point,
        store,
        override=override,
        provenance="synthetic_control",
    )
    state = _execution(
        "F2",
        "explicit_override",
        "preprocessor",
        "observation.state",
        "forward",
        STATE_WITNESS,
        store,
        override=override,
        provenance="synthetic_control",
    )
    decision = {"candidates": {"explicit_override": {"outcome": "supported_software_correction"}}}
    return _record("B", files, [fixed, state], decision=decision), files


def check_fixed_point_witness(a: dict) -> list[str]:
    failures = []
    row = _row(a, "F1")
    if (
        row["expected"]["class"] != "transformed"
        or not row["vacuous"]
        or row["agreement"] != "agrees"
    ):
        failures.append("a fixed-point input must be a vacuous but agreeing transformed witness")
    if _outcome(a, "explicit_override") != "unresolved":
        failures.append("a vacuous action witness cannot support the candidate")
    if a["decision_agreement"]["false_acceptance"] != ["explicit_override"]:
        failures.append("the producer's acceptance on a vacuous witness is a false acceptance")
    return failures


def build_prefixed_keys_exact_lookup() -> tuple[dict, dict[str, bytes]]:
    files = _files(INCIDENT_LAYOUT, INCIDENT_LAYOUT)
    store = _store(INCIDENT_LAYOUT)
    action = _execution("P1", "as_is", "postprocessor", "action", "inverse", ACTION_WITNESS, store)
    state = _execution(
        "P2", "as_is", "preprocessor", "observation.state", "forward", STATE_WITNESS, store
    )
    interrupted = _execution(
        "P3",
        "as_is",
        "postprocessor",
        "action",
        "inverse",
        ACTION_WITNESS,
        store,
        status="interrupted",
    )
    decision = {"candidates": {"as_is": {"outcome": "supported_software_correction"}}}
    return _record("B", files, [action, state, interrupted], decision=decision), files


def check_prefixed_keys_exact_lookup(a: dict) -> list[str]:
    failures = []
    for identifier in ("P1", "P2"):
        row = _row(a, identifier)
        if row["expected"]["class"] != "skipped_no_stats" or row["agreement"] != "agrees":
            failures.append(f"{identifier}: prefixed keys must leave the plain key skipped")
    if _row(a, "P3")["agreement"] != "unresolved":
        failures.append("an interrupted execution is unresolved, not a skip")
    verdict = a["reference_decision"]["per_candidate"]["as_is"]
    if verdict["outcome"] != "rejected_candidate" or len(verdict["unmet"]) != 2:
        failures.append("as-is must be rejected on both the state and the action obligation")
    if a["decision_agreement"]["false_acceptance"] != ["as_is"]:
        failures.append("accepting as-is is a false acceptance")
    if a["reference_decision"]["overall"] != "rejected_candidate":
        failures.append("overall must be rejected when no candidate is supported")
    return failures


def build_suffix_match_ambiguous() -> tuple[dict, dict[str, bytes]]:
    files = _files(INCIDENT_LAYOUT, INCIDENT_LAYOUT)
    store = _store(INCIDENT_LAYOUT)
    keys = list(store)
    first = _execution(
        "S1",
        "suffix_match",
        "postprocessor",
        "action",
        "inverse",
        ACTION_WITNESS,
        store,
        stats_order=keys,
    )
    reversed_order = _execution(
        "S2",
        "suffix_match",
        "postprocessor",
        "action",
        "inverse",
        ACTION_WITNESS,
        store,
        stats_order=list(reversed(keys)),
    )
    state = _execution(
        "S3", "suffix_match", "preprocessor", "observation.state", "forward", STATE_WITNESS, store
    )
    return _record("B", files, [first, reversed_order, state]), files


def check_suffix_match_ambiguous(a: dict) -> list[str]:
    failures = []
    one, two = _row(a, "S1"), _row(a, "S2")
    for row in (one, two):
        if row["expected"]["class"] != "ambiguous" or row["agreement"] != "agrees":
            failures.append(f"{row['id']}: three prefixed datasets must be ambiguous yet agree")
        if not row.get("order_dependent"):
            failures.append(f"{row['id']}: different keys must give different outputs")
    if one["expected"]["bound_key"] == two["expected"]["bound_key"]:
        failures.append("reversing the store order must change the bound key")
    if one["expected_output"]["float32_emulation"] == two["expected_output"]["float32_emulation"]:
        failures.append("reversing the store order must change the expected output")
    if _row(a, "S3")["expected"]["class"] != "skipped_no_stats":
        failures.append("no state statistics exist for the suffix candidate to match")
    if _outcome(a, "suffix_match") != "rejected_candidate":
        failures.append("the suffix candidate must be rejected")
    return failures


SINGLE_LAYOUT = prefixed({"alpha.buffer": ALPHA})


def build_suffix_match_partial() -> tuple[dict, dict[str, bytes]]:
    files = _files(SINGLE_LAYOUT, SINGLE_LAYOUT)
    store = _store(SINGLE_LAYOUT)
    action = _execution(
        "U1", "suffix_match", "postprocessor", "action", "inverse", ACTION_WITNESS, store
    )
    state = _execution(
        "U2", "suffix_match", "preprocessor", "observation.state", "forward", STATE_WITNESS, store
    )
    decision = {"candidates": {"suffix_match": {"outcome": "supported_software_correction"}}}
    return _record("B", files, [action, state], decision=decision), files


def check_suffix_match_partial(a: dict) -> list[str]:
    failures = []
    action = _row(a, "U1")
    if (
        action["expected"]["class"] != "transformed"
        or action["agreement"] != "agrees"
        or action["vacuous"]
    ):
        failures.append("a unique prefixed dataset repairs the action direction")
    if _row(a, "U2")["expected"]["class"] != "skipped_no_stats":
        failures.append("the state direction stays skipped")
    verdict = a["reference_decision"]["per_candidate"]["suffix_match"]
    if verdict["outcome"] != "rejected_candidate" or verdict["unmet"] != [
        "preprocessor:observation.state:forward: skipped_no_stats"
    ]:
        failures.append("the partial candidate must be rejected on the state obligation alone")
    if a["decision_agreement"]["false_acceptance"] != ["suffix_match"]:
        failures.append("accepting the partial candidate is a false acceptance")
    return failures


def build_explicit_override_complete() -> tuple[dict, dict[str, bytes]]:
    files = _files(INCIDENT_LAYOUT, INCIDENT_LAYOUT)
    store = _store(INCIDENT_LAYOUT)
    override = {"action": ALPHA, "observation.state": STATE_REF}
    action = _execution(
        "C1",
        "explicit_override",
        "postprocessor",
        "action",
        "inverse",
        ACTION_WITNESS,
        store,
        override=override,
        provenance="synthetic_control",
    )
    state = _execution(
        "C2",
        "explicit_override",
        "preprocessor",
        "observation.state",
        "forward",
        STATE_WITNESS,
        store,
        override=override,
        provenance="synthetic_control",
    )
    image = _execution(
        "C3",
        "explicit_override",
        "preprocessor",
        "observation.images.top",
        "forward",
        IMAGE_WITNESS,
        store,
        override=override,
        provenance="synthetic_control",
    )
    decision = {
        "candidates": {
            "as_is": {"outcome": "rejected_candidate"},
            "suffix_match": {"outcome": "rejected_candidate"},
            "explicit_override": {"outcome": "supported_software_correction"},
        }
    }
    return _record("B", files, [action, state, image], decision=decision), files


def check_explicit_override_complete(a: dict) -> list[str]:
    failures = []
    for identifier in ("C1", "C2"):
        row = _row(a, identifier)
        if (
            row["expected"]["class"] != "transformed"
            or row["agreement"] != "agrees"
            or row["vacuous"]
        ):
            failures.append(f"{identifier}: complete explicit statistics transform the feature")
        if not row["comparison"]["bit_exact_float32"]:
            failures.append(
                f"{identifier}: the stand-in float32 path must match the emulation bit for bit"
            )
    verdict = a["reference_decision"]["per_candidate"]["explicit_override"]
    if verdict["outcome"] != "supported_software_correction":
        failures.append("complete explicit override is the supported software correction")
    if verdict["deployment_binding"] != "unresolved":
        failures.append("synthetic statistics leave the deployment binding unresolved")
    if a["reference_decision"]["overall"] != "supported_software_correction":
        failures.append("overall follows the supported candidate")
    if not a["decision_agreement"]["all_agree"] or a["decision_agreement"]["false_refusal"]:
        failures.append("the producer decision agrees on every candidate with no false refusal")
    return failures


def build_round_trip_cancels_wrong_stats() -> tuple[dict, dict[str, bytes]]:
    files = _files(INCIDENT_LAYOUT, INCIDENT_LAYOUT)
    store = _store(INCIDENT_LAYOUT)
    wrong = {"action": BETA, "observation.state": STATE_WRONG}
    forward = _execution(
        "R1",
        "explicit_override",
        "preprocessor",
        "action",
        "forward",
        ACTION_WITNESS,
        store,
        override=wrong,
        provenance="synthetic_control",
    )
    back = _execution(
        "R2",
        "explicit_override",
        "postprocessor",
        "action",
        "inverse",
        forward["output"],
        store,
        override=wrong,
        provenance="synthetic_control",
    )
    state = _execution(
        "R3",
        "explicit_override",
        "preprocessor",
        "observation.state",
        "forward",
        STATE_WITNESS,
        store,
        override=wrong,
        provenance="synthetic_control",
    )
    reference = {
        "provenance": "synthetic_control",
        "values": {"action": ALPHA, "observation.state": STATE_REF},
    }
    decision = {"candidates": {"explicit_override": {"outcome": "supported_software_correction"}}}
    return _record(
        "B", files, [forward, back, state], reference_statistics=reference, decision=decision
    ), files


def check_round_trip_cancels_wrong_stats(a: dict) -> list[str]:
    failures = []
    back = _row(a, "R2")
    if back["agreement"] != "agrees":
        failures.append("the inverse of the forward output is what the wrong statistics produce")
    round_trip = [round(v, 5) for v in back["expected_output"]["float32_emulation"]]
    if round_trip != [round(v, 5) for v in ACTION_WITNESS]:
        failures.append("forward then inverse with the same statistics returns the input")
    verdict = a["reference_decision"]["per_candidate"]["explicit_override"]
    if verdict["outcome"] != "rejected_candidate" or not verdict["reference_mismatches"]:
        failures.append("a round trip cannot vouch for statistics that differ from the reference")
    if a["decision_agreement"]["false_acceptance"] != ["explicit_override"]:
        failures.append("accepting on the round trip is a false acceptance")
    return failures


MISSING_STD = {"action.mean": ALPHA["mean"]}


def build_missing_std_error() -> tuple[dict, dict[str, bytes]]:
    files = _files(MISSING_STD, MISSING_STD)
    store = _store(MISSING_STD)
    silent = _execution(
        "M1",
        "as_is",
        "postprocessor",
        "action",
        "inverse",
        ACTION_WITNESS,
        store,
        output=list(ACTION_WITNESS),
        status="completed",
    )
    raised = _execution("M2", "as_is", "postprocessor", "action", "inverse", ACTION_WITNESS, store)
    return _record("B", files, [silent, raised]), files


def check_missing_std_error(a: dict) -> list[str]:
    failures = []
    silent, raised = _row(a, "M1"), _row(a, "M2")
    if silent["expected"]["class"] != "error" or silent["agreement"] != "disagrees":
        failures.append(
            "a completed unchanged output where the pinned step raises is a disagreement"
        )
    if raised["status"] != "error" or raised["agreement"] != "agrees":
        failures.append("a raised error agrees with the reference")
    if _outcome(a, "as_is") != "invalid_input":
        failures.append("a producer that silently skips a raising path is invalid input")
    if a["reference_decision"]["overall"] != "invalid_input":
        failures.append("an invalid record can neither support nor reject: overall is invalid")
    return failures


# --- provenance controls (added 20 September 2026, 16:20 UTC, after the label-only
# promotion was reproduced at commit c401efa; rule external-decision-001/v2) ---------------

UNMATCHED_ACTION = {"mean": [7.0, 7.0, 7.0, 7.0, 7.0, 7.0], "std": [3.5, 3.5, 3.5, 3.5, 3.5, 3.5]}
COMPLETE_PLAIN_LAYOUT = {
    "action.mean": ALPHA["mean"],
    "action.std": ALPHA["std"],
    "observation.state.mean": STATE_REF["mean"],
    "observation.state.std": STATE_REF["std"],
}


def _override_record(
    labels: dict[str, str], override: dict, decision_outcome: str | None = None
) -> tuple[dict, dict[str, bytes]]:
    files = _files(INCIDENT_LAYOUT, INCIDENT_LAYOUT)
    store = _store(INCIDENT_LAYOUT)
    action = _execution(
        "V1",
        "explicit_override",
        "postprocessor",
        "action",
        "inverse",
        ACTION_WITNESS,
        store,
        override=override,
        provenance=labels["action"],
    )
    state = _execution(
        "V2",
        "explicit_override",
        "preprocessor",
        "observation.state",
        "forward",
        STATE_WITNESS,
        store,
        override=override,
        provenance=labels["observation.state"],
    )
    extra = {}
    if decision_outcome is not None:
        extra["decision"] = {"candidates": {"explicit_override": {"outcome": decision_outcome}}}
    return _record("B", files, [action, state], **extra), files


def _binding(a: dict) -> dict:
    return a["reference_decision"]["per_candidate"]["explicit_override"]


def _declared_findings(a: dict) -> list[str]:
    return [
        f["detail"] for f in a["findings"] if f["code"] == "provenance_declared_not_established"
    ]


def build_label_only_promotion() -> tuple[dict, dict[str, bytes]]:
    labels = {
        "action": "verified_training_statistics",
        "observation.state": "verified_training_statistics",
    }
    return _override_record(labels, {"action": ALPHA, "observation.state": STATE_REF})


def check_label_only_promotion(a: dict) -> list[str]:
    failures = []
    verdict = _binding(a)
    if verdict["outcome"] != "supported_software_correction":
        failures.append("the transform still runs: the software correction stays supported")
    if verdict["deployment_binding"] != "unresolved":
        failures.append("a verified_training_statistics label must not promote the binding")
    per = {f["feature"]: f for f in verdict["binding_evidence"]["per_feature"]}
    if per["action"]["byte_provenance"] != "matches_artifact_set":
        failures.append(
            "the evaluator establishes on its own that the action values equal an artifact set"
        )
    if per["observation.state"]["byte_provenance"] != "not_established":
        failures.append("state values match no artifact set and are not established")
    if len(_declared_findings(a)) != 2:
        failures.append("both over-claiming labels are named findings")
    if verdict["binding_evidence"]["selection"] != "not_carried_by_contract":
        failures.append("selection is not carried by the contract")
    return failures


def build_artifact_label_without_bytes() -> tuple[dict, dict[str, bytes]]:
    labels = {"action": "artifact", "observation.state": "artifact"}
    return _override_record(labels, {"action": UNMATCHED_ACTION, "observation.state": STATE_REF})


def check_artifact_label_without_bytes(a: dict) -> list[str]:
    failures = []
    verdict = _binding(a)
    if verdict["outcome"] != "supported_software_correction":
        failures.append("supplied statistics that transform correctly remain a software correction")
    if (
        verdict["deployment_binding"] != "unresolved"
        or verdict["binding_evidence"]["byte_provenance"] != "not_established"
    ):
        failures.append("an artifact label without matching bytes establishes no byte provenance")
    if len(_declared_findings(a)) != 2:
        failures.append("both unsupported artifact claims are named findings")
    return failures


def build_artifact_label_with_matching_bytes() -> tuple[dict, dict[str, bytes]]:
    labels = {"action": "artifact", "observation.state": "artifact"}
    return _override_record(labels, {"action": ALPHA, "observation.state": STATE_REF})


def check_artifact_label_with_matching_bytes(a: dict) -> list[str]:
    failures = []
    verdict = _binding(a)
    per = {f["feature"]: f for f in verdict["binding_evidence"]["per_feature"]}
    if (
        per["action"]["byte_provenance"] != "matches_artifact_set"
        or per["action"]["artifact_key"] != "alpha.buffer.action"
    ):
        failures.append("action bytes match alpha.buffer.action in the verified artifact")
    if per["observation.state"]["byte_provenance"] != "not_established":
        failures.append("state bytes match nothing in the artifact")
    if (
        verdict["deployment_binding"] != "unresolved"
        or verdict["binding_evidence"]["byte_provenance"] != "not_established"
    ):
        failures.append("one matched feature does not establish the candidate's byte provenance")
    if _declared_findings(a) != [
        "explicit_override: observation.state: declared 'artifact', established not_established only"
    ]:
        failures.append("only the state label over-claims")
    return failures


def build_artifact_carries_complete_statistics() -> tuple[dict, dict[str, bytes]]:
    files = _files(COMPLETE_PLAIN_LAYOUT, COMPLETE_PLAIN_LAYOUT)
    store = _store(COMPLETE_PLAIN_LAYOUT)
    action = _execution("W1", "as_is", "postprocessor", "action", "inverse", ACTION_WITNESS, store)
    state = _execution(
        "W2", "as_is", "preprocessor", "observation.state", "forward", STATE_WITNESS, store
    )
    image = _execution(
        "W3", "as_is", "preprocessor", "observation.images.top", "forward", IMAGE_WITNESS, store
    )
    decision = {"candidates": {"as_is": {"outcome": "supported_software_correction"}}}
    return _record("B", files, [action, state, image], decision=decision), files


def check_artifact_carries_complete_statistics(a: dict) -> list[str]:
    failures = []
    verdict = a["reference_decision"]["per_candidate"]["as_is"]
    if verdict["outcome"] != "supported_software_correction":
        failures.append("an artifact with complete plain statistics needs no correction")
    if verdict["binding_evidence"]["byte_provenance"] != "established":
        failures.append("both features' statistics were read from the verified artifact")
    if verdict["deployment_binding"] != "unresolved":
        failures.append("byte provenance alone is not a deployment binding")
    if verdict["binding_missing"] != [
        "interpretation: not_carried_by_contract",
        "selection: not_carried_by_contract",
    ]:
        failures.append("only interpretation and selection remain missing")
    if _declared_findings(a):
        failures.append("an artifact label that the evaluator established is not a finding")
    if not a["decision_agreement"]["per_candidate"]["as_is"]["agrees"]:
        failures.append("the producer's supported verdict for as_is agrees")
    return failures


CONTROLS: tuple[Control, ...] = (
    Control(
        "identity_mode_visual",
        "Is an unchanged IDENTITY feature correct?",
        build_identity_mode_visual,
        check_identity_mode_visual,
    ),
    Control(
        "fixed_point_witness",
        "Can an input at the fixed point show a transform ran?",
        build_fixed_point_witness,
        check_fixed_point_witness,
    ),
    Control(
        "prefixed_keys_exact_lookup",
        "Are prefixed keys skipped under the exact lookup?",
        build_prefixed_keys_exact_lookup,
        check_prefixed_keys_exact_lookup,
    ),
    Control(
        "suffix_match_ambiguous",
        "Does the suffix candidate depend on store order?",
        build_suffix_match_ambiguous,
        check_suffix_match_ambiguous,
    ),
    Control(
        "suffix_match_partial",
        "Does a unique suffix match repair only one direction?",
        build_suffix_match_partial,
        check_suffix_match_partial,
    ),
    Control(
        "explicit_override_complete",
        "Is the complete explicit override accepted?",
        build_explicit_override_complete,
        check_explicit_override_complete,
    ),
    Control(
        "round_trip_cancels_wrong_stats",
        "Does a round trip vouch for wrong statistics?",
        build_round_trip_cancels_wrong_stats,
        check_round_trip_cancels_wrong_stats,
    ),
    Control(
        "missing_std_error",
        "Is a raising path distinguished from a silent skip?",
        build_missing_std_error,
        check_missing_std_error,
    ),
    Control(
        "label_only_promotion",
        "Can a verified_training_statistics label promote the binding?",
        build_label_only_promotion,
        check_label_only_promotion,
    ),
    Control(
        "artifact_label_without_bytes",
        "Does an artifact label establish bytes the artifact does not hold?",
        build_artifact_label_without_bytes,
        check_artifact_label_without_bytes,
    ),
    Control(
        "artifact_label_with_matching_bytes",
        "Does one matched feature bind the whole candidate?",
        build_artifact_label_with_matching_bytes,
        check_artifact_label_with_matching_bytes,
    ),
    Control(
        "artifact_carries_complete_statistics",
        "Is byte provenance established without a deployment claim?",
        build_artifact_carries_complete_statistics,
        check_artifact_carries_complete_statistics,
    ),
)


def write_control(control: Control, out_dir: Path) -> Path:
    record, files = control.build()
    folder = out_dir / control.name
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    path = folder / "record.json"
    path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    return path


def run_processor_controls(out_dir: Path) -> dict:
    """Write, assess and check every control; ``all_ok`` only when every check passes."""
    results = []
    for control in CONTROLS:
        path = write_control(control, out_dir)
        assessment = assess(json.loads(path.read_text()), path.parent)
        (path.parent / "assessment.json").write_text(
            json.dumps(assessment, indent=2, allow_nan=False) + "\n"
        )
        failures = control.check(assessment)
        results.append(
            {
                "name": control.name,
                "question": control.question,
                "record": str(path),
                "reference_overall": assessment["reference_decision"]["overall"],
                "failures": failures,
                "ok": not failures,
            }
        )
    return {
        "schema": "nisayon.processor-controls.summary.v1",
        "controls": results,
        "all_ok": all(r["ok"] for r in results),
        "note": "constructed controls with synthetic statistics; not incidents",
    }


def render_processor_controls(summary: dict) -> str:
    lines = []
    for row in summary["controls"]:
        mark = "ok  " if row["ok"] else "FAIL"
        lines.append(f"{mark} {row['name']:<38}{row['reference_overall']:<32}{row['question']}")
        for failure in row["failures"]:
            lines.append(f"       {failure}")
    lines.append("all ok" if summary["all_ok"] else "some controls failed")
    return "\n".join(lines)
