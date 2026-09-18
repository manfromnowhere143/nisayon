"""Adapter for execution-lane bundles (``nisayon.first_case.v1``).

Codex's runner writes one JSON document, optionally gzip-compressed, holding
the case, qualification, plans, every run with an inline compact trace and an
optional confirmation. This module translates that document into the
evaluator's records without changing its meaning, verifies what the document
lets us verify (observation and state chains, acquisition stamps, raw artifact
digests and manifests, the frozen protocol, repeated runs) and derives the
invalid-replay control from a retained run. Translation choices are recorded in
the decision's ``producer`` section so a reader can check them.

The obligation version is read from the frozen protocol (``protocol_id``) or
the producer's predicates. Version 0.1 records are evaluated against what they
declared; the stricter version 0.2 requirements are reported as limitations,
never applied retroactively.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import codes
from .bundle import Bundle
from .case import OBLIGATION_V01, OBLIGATION_V02
from .checks import Finding
from .decision import (
    PROTOCOL_ID,
    evaluate_loaded,
    history_consumption,
    inline_trace_digests,
    retained_protocols,
    unreadable_history,
)
from .schema import Malformed, digest_of, finite, mapping, require, sequence, string

FIRST_CASE_SCHEMA = "nisayon.first_case.v1"
CALIBRATION_SCHEMA = "nisayon.family_calibration.v1"
PROBE_ROLES = {"calibration", "executed_prefix_context", "probe"}
PLAN_ROLES = {"reference", "regression", "candidate", "probe", "executed_prefix_context"}
DEPLOYMENT_FIELDS = (
    "transport_gripper_sign",
    "repair_gripper_sign",
    "transport_translation_order",
    "repair_translation_order",
    "observation_delay_steps",
    "observation_stride_steps",
    "policy_reset",
    "suppress_actions",
)
FAILURE_OBLIGATIONS = {"task", "timing", "progress", "reset", "constraints"}
DEPLOYMENT_DEFAULTS = {
    "transport_gripper_sign": 1,
    "repair_gripper_sign": 1,
    "transport_translation_order": [0, 1, 2],
    "repair_translation_order": [0, 1, 2],
    "observation_delay_steps": 0,
    "observation_stride_steps": 1,
    "policy_reset": "episode",
    "suppress_actions": False,
}
MANIFEST_SCHEMA = "nisayon.artifact_manifest.v1"
PRODUCER_MANIFEST_SCHEMA = "nisayon.execution.artifacts.v1"
V2_RECORD_CONTRACT = "nisayon.execution.v2"
V2_PROTOCOL_SCHEMAS = {
    "nisayon.lift.protocol.v2",
    "nisayon.lift.protocol.v3",
    "nisayon.lift.protocol.v4",
}
MODES = ("reference", "regression", "correction", "suppression")
REPLAY_PLAN_ID = "replay_correction"
LEGACY_PROGRESS_MINIMUM_GAIN_M = 0.01
LEGACY_PROGRESS_ACTIVATION_TOLERANCE_M = 0.005
STATE_COMPONENTS = ["sim_state", "controller_state", "policy_state", "action_queue", "rng"]
COMPONENTS = {
    "correction": [
        {
            "kind": "config_edit",
            "path": "repair_gripper_sign",
            "role": "deployable_edit",
            "summary": "invert the gripper command before the changed transport",
        }
    ],
    "suppression": [
        {
            "kind": "config_edit",
            "path": "suppress_actions",
            "role": "deployable_edit",
            "summary": "zero every executed action",
        }
    ],
}
UNITS = {
    "cube_height_m": "m",
    "task_success": "bool",
    "executed_action_max_abs": "normalized",
    "action_dimension": "count",
    "step_period_s": "s",
    "step_index": "count",
    "inference_wall_s": "s",
}
REPEAT_FIELDS = (
    "state_before_sha256",
    "state_after_sha256",
    "observation_sha256",
    "next_observation_sha256",
    "policy_state_sha256",
    "executed_action",
)
PROCESS = {"completed": "completed", "failed": "nonzero", "interrupted": "interrupted"}
VALIDITY = {"observed": "valid", "invalid": "invalid", "missing": "unknown"}
IDENTITY_KEYS = (
    "invocation_id",
    "execution_identity_sha256",
    "configuration_sha256",
    "code_git_head",
    "sources_sha256",
    "dependencies_sha256",
    "policy_sha256",
)


def producer_digest(value: object) -> str:
    """The execution lane's digest: SHA-256 hex of compact, key-sorted JSON, no prefix."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def deployment(mode: str, policy_sha256: str) -> dict:
    """Mirror of ``nisayon.engine.lift.candidate``; the digest of this dict identifies a run."""
    if mode not in MODES:
        raise ValueError(f"unknown deployment mode {mode!r}")
    return {
        "mode": mode,
        "transport_gripper_sign": 1 if mode == "reference" else -1,
        "repair_gripper_sign": -1 if mode == "correction" else 1,
        "suppress_actions": mode == "suppression",
        "policy_sha256": policy_sha256,
    }


def known_deployments(policy_sha256: str) -> dict[str, str]:
    return {producer_digest(deployment(mode, policy_sha256)): mode for mode in MODES}


def execute_action(intended: list[float], dep: dict) -> list[float]:
    """Mirror of ``nisayon.engine.lift.execute_action`` without NumPy."""
    action = [float(a) for a in intended]
    if len(action) != 7 or not all(math.isfinite(a) for a in action):
        raise ValueError("expected seven finite action components")
    action[-1] *= dep["repair_gripper_sign"]
    action[-1] *= dep["transport_gripper_sign"]
    if dep["suppress_actions"]:
        action = [0.0] * 7
    return [min(1.0, max(-1.0, a)) for a in action]


def _reject_constant(name: str) -> None:
    raise Malformed("$", f"non-finite JSON constant {name}")


def read_document(path: Path) -> dict:
    path = Path(path)
    try:
        raw = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    except OSError as error:
        raise Malformed(str(path), f"unreadable: {error.strerror}") from error
    try:
        data = json.loads(raw.decode(), parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Malformed(str(path), f"invalid JSON: {error}") from error
    return mapping(data, "bundle")


def write_document(document: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, allow_nan=False) + "\n"
    if path.suffix == ".gz":
        with gzip.open(path, "wt") as stream:
            stream.write(text)
    else:
        path.write_text(text)
    return path


def is_first_case(path: Path) -> bool:
    path = Path(path)
    if not path.is_file():
        return False
    try:
        return read_document(path).get("schema") == FIRST_CASE_SCHEMA
    except Malformed:
        return False


def sim(seconds: float) -> dict:
    return {"value": seconds, "unit": "s", "clock": "sim"}


def wall(stamp: str) -> dict:
    return {"value": stamp, "clock": "wall_utc"}


def _finding(code: str, detail: str, **extra: object) -> dict:
    return {"code": code, "detail": detail, **extra}


def deployment_components(dep: dict, changed: dict | None = None) -> list[dict]:
    """The repair a candidate deployment carries: every field where it differs from the changed
    deployment. Without a changed deployment, non-default repair fields and suppression."""
    components = []
    if changed is not None:
        for key in DEPLOYMENT_FIELDS:
            if key in dep and dep.get(key) != changed.get(key):
                components.append(
                    {
                        "kind": "config_edit",
                        "path": key,
                        "role": "deployable_edit",
                        "summary": f"{key}: {changed.get(key)} -> {dep.get(key)}",
                    }
                )
        return components
    for key in ("repair_gripper_sign", "repair_translation_order"):
        value = dep.get(key)
        if value is not None and value != DEPLOYMENT_DEFAULTS[key]:
            components.append(
                {
                    "kind": "config_edit",
                    "path": key,
                    "role": "deployable_edit",
                    "summary": f"{key} = {value}",
                }
            )
    if dep.get("suppress_actions"):
        components.append(
            {
                "kind": "config_edit",
                "path": "suppress_actions",
                "role": "deployable_edit",
                "summary": "zero every executed action",
            }
        )
    return components


def deployment_label(dep: dict) -> str:
    changed = [
        f"{key}={dep[key]}"
        for key, default in DEPLOYMENT_DEFAULTS.items()
        if key in dep and dep[key] != default
    ]
    return ", ".join(changed) or "default deployment"


def obligation_version(document: dict, frozen: dict | None) -> str:
    """Version 0.2 only when the producer says so: a v2 record contract, a v2 protocol schema,
    or an explicit ``protocol_id`` in the frozen protocol or predicates."""
    predicates = (document.get("case") or {}).get("predicates") or {}
    declared = (frozen or {}).get("protocol_id") or predicates.get("protocol_id")
    if declared == OBLIGATION_V02:
        return OBLIGATION_V02
    if document.get("record_contract") == V2_RECORD_CONTRACT:
        return OBLIGATION_V02
    if (frozen or {}).get("schema") in V2_PROTOCOL_SCHEMAS:
        return OBLIGATION_V02
    return OBLIGATION_V01


def translate_predicates(pred: object) -> dict:
    """The producer's predicates in the evaluator's form.

    ``evaluator_added_ids`` lists the predicates the evaluator had to supply itself; they
    are never preregistered. The execution lane imports this function for its probes.
    """
    path = "bundle.case.predicates"
    p = mapping(pred, path)
    minimum = finite(require(p, "min_cube_height_m", path), f"{path}.min_cube_height_m")
    period = finite(require(p, "control_period_s", path), f"{path}.control_period_s")
    tolerance = finite(
        p.get("control_period_tolerance_s", 0.0), f"{path}.control_period_tolerance_s"
    )
    added: list[str] = []
    if p.get("progress_minimum_gain_m") is not None:
        progress = {
            "id": "lift.cube_raised",
            "measure": "cube_height_m",
            "unit": "m",
            "minimum_gain": finite(p["progress_minimum_gain_m"], f"{path}.progress_minimum_gain_m"),
            "activation_tolerance": finite(
                p.get("progress_activation_tolerance_m", 0.0),
                f"{path}.progress_activation_tolerance_m",
            ),
            "declared_by": "producer",
            "preregistered": True,
        }
    else:
        progress = {
            "id": "lift.cube_raised",
            "measure": "cube_height_m",
            "unit": "m",
            "minimum_gain": LEGACY_PROGRESS_MINIMUM_GAIN_M,
            "activation_tolerance": LEGACY_PROGRESS_ACTIVATION_TOLERANCE_M,
            "declared_by": "evaluation lane; legacy fallback for records without a producer "
            "progress declaration",
            "preregistered": False,
        }
        added.append("lift.cube_raised")
    predicates = {
        "outcome": {
            "id": "lift.cube_above_table",
            "measure": "cube_height_m",
            "unit": "m",
            "op": ">",
            "threshold": minimum,
            "when": "final",
        },
        "progress": progress,
        "constraints": [
            {
                "id": "action.executed_bounded",
                "measure": "executed_action_max_abs",
                "unit": "normalized",
                "op": "<=",
                "threshold": finite(
                    require(p, "max_abs_executed_action", path), f"{path}.max_abs_executed_action"
                ),
            },
            {
                "id": "action.dimension",
                "measure": "action_dimension",
                "unit": "count",
                "op": "==",
                "threshold": finite(
                    require(p, "action_dimension", path), f"{path}.action_dimension"
                ),
            },
            {
                "id": "control.period_upper",
                "measure": "step_period_s",
                "unit": "s",
                "op": "<=",
                "threshold": period + tolerance,
            },
            {
                "id": "control.period_lower",
                "measure": "step_period_s",
                "unit": "s",
                "op": ">=",
                "threshold": period - tolerance,
            },
            {
                "id": "episode.max_steps",
                "measure": "step_index",
                "unit": "count",
                "op": "<",
                "threshold": finite(require(p, "max_steps", path), f"{path}.max_steps"),
            },
        ],
        "timing": {
            "id": "control.fresh_observation",
            "clock": "sim",
            "evidence": "acquisition_stamps",
            "max_observation_age": {
                "value": finite(
                    require(p, "max_observation_age_s", path), f"{path}.max_observation_age_s"
                ),
                "unit": "s",
            },
            "max_step_period": {"value": period + tolerance, "unit": "s"},
        },
        "evaluator_added_ids": added,
        "producer_predicates": p,
        "producer_predicates_digest": producer_digest(p),
    }
    return predicates


def _repair_paths(declared: object) -> list[str]:
    """Deployment field names from the declared repair scope; the legacy text scope maps to
    the gripper-sign inverse."""
    names = [
        item for item in (declared or []) if isinstance(item, str) and item in DEPLOYMENT_FIELDS
    ]
    if names:
        return names
    text = " ".join(str(item) for item in (declared or []))
    return ["repair_gripper_sign"] if "gripper" in text else []


def _failure_obligation(case: dict) -> str:
    """Which declared obligation the registered failure violates; task unless the case says so."""
    declared = case.get("failure_obligation")
    if isinstance(declared, str) and declared in FAILURE_OBLIGATIONS:
        return declared
    failure = case.get("failure") if isinstance(case.get("failure"), dict) else {}
    declared = failure.get("obligation")
    return declared if isinstance(declared, str) and declared in FAILURE_OBLIGATIONS else "task"


def _cost(item: object, path: str) -> dict:
    data = mapping(item, path)
    cost = {"value": data.get("value"), "unit": data.get("unit")}
    if data.get("value") is None:
        cost["missing"] = data.get("missing_reason") or "no reason recorded"
    return cost


def translate_case(
    case: dict,
    qualification: dict,
    bundle_costs: list,
    failure_condition: str,
    origin: str,
    obligation: str,
    calibration: bool = False,
) -> dict:
    path = "bundle.case"
    if calibration:
        case = {
            "task": case.get("task", "calibration"),
            "backend": case.get("backend") or {},
            "working_revision": case.get("working_revision", "undeclared-working"),
            "changed_revision": case.get("changed_revision", "undeclared-changed"),
            **{k: v for k, v in case.items() if k not in ("task", "backend")},
        }
    policy = mapping(require(case, "policy", path), f"{path}.policy")
    backend = mapping(require(case, "backend", path), f"{path}.backend")
    versions = mapping(backend.get("versions", {}), f"{path}.backend.versions")
    version = ", ".join(f"{name} {value}" for name, value in versions.items())
    if backend.get("platform"):
        version = f"{version}; {backend['platform']}" if version else str(backend["platform"])
    url = policy.get("url") if isinstance(policy.get("url"), str) else ""
    predicates = translate_predicates(require(case, "predicates", path))
    return {
        "schema": "nisayon.case.v1",
        "id": string(case, "id", path),
        "evidence_origin": origin,
        "obligation": obligation,
        "calibration": calibration,
        "task": {
            "id": string(case, "task", path),
            "policy": {
                "id": Path(url).name or "policy",
                "digest": string(policy, "sha256", f"{path}.policy"),
            },
            "backend": {"id": "robosuite-mujoco-cpu", "version": version or "undeclared"},
        },
        "revisions": {
            "working": string(case, "working_revision", path),
            "changed": string(case, "changed_revision", path),
        },
        "failure": {
            "condition_id": failure_condition,
            "description": "the changed deployment fails the declared task",
        },
        "predicates": predicates,
        "qualification": {
            "state_components": list(STATE_COMPONENTS),
            "omitted_state": [str(item) for item in qualification.get("omitted_state", [])],
            "captured_state": [str(item) for item in qualification.get("captured_state", [])],
        },
        "repair_scope": {
            "allowed_component_kinds": ["config_edit"],
            "allowed_paths": _repair_paths(case.get("allowed_repair_scope")),
            "declared": case.get("allowed_repair_scope"),
        },
        "failure_obligation": _failure_obligation(case),
        "preparation_costs": {
            mapping(item, f"bundle.costs[{index}]").get("category", f"cost-{index}"): _cost(
                item, f"bundle.costs[{index}]"
            )
            for index, item in enumerate(bundle_costs)
        },
    }


def _translate_capture(meta: object) -> dict | None:
    """Codex's ``CapturedObservation.metadata()`` in the evaluator's capture form."""
    if not isinstance(meta, dict) or not isinstance(meta.get("components"), dict):
        return None
    components = {}
    for name, stamp in meta["components"].items():
        if not isinstance(stamp, dict):
            return None
        components[name] = {
            "sequence": stamp.get("sequence"),
            "simulation_s": stamp.get("simulation_s"),
            "host_started_s": stamp.get("host_started_s"),
            "host_finished_s": stamp.get("host_finished_s"),
        }
    return {"received_host_s": meta.get("received_host_s"), "components": components}


def translate_steps(rows: list[dict], run_id: str, findings: list[dict]) -> list[dict]:
    """One evaluator step per producer row.

    The observation defined at row ``k`` is the newest one available there: the reset
    observation for row 0, otherwise the observation acquired after row ``k - 1``. The
    action names the observation it consumed (``observation_step``), which is older when
    the delivery was stale. Acquisition stamps travel with the observation they belong to.
    """
    defined: dict[int, dict | None] = {}
    if rows:
        first = rows[0]
        defined[0] = (
            _translate_capture(first.get("observation_capture"))
            if int(first.get("observation_step", 0)) == 0
            else None
        )
        for row in rows:
            defined[int(row["step"]) + 1] = _translate_capture(row.get("next_observation_capture"))
    steps = []
    for row in rows:
        index = int(row["step"])
        consumed_index = int(row["observation_step"])
        executed = list(row["executed_action"])
        capture = defined.get(index)
        if capture is not None:
            observation_t = min(c["simulation_s"] for c in capture["components"].values())
        elif consumed_index == index:
            observation_t = row["observation_sim_time_s"]
        else:
            observation_t = None
        if observation_t is None:
            # The newest observation at this row is not stamped; its time is unknown.
            observation_t = row["observation_sim_time_s"]
            findings.append(
                _finding(
                    codes.TRACE_CHAIN_BROKEN,
                    "the observation available at this row has no acquisition record and the "
                    "consumed observation is older; its time cannot be established",
                    step=index,
                )
            )
        captured_step = row.get("captured_observation_step")
        if captured_step is not None and int(captured_step) != index:
            findings.append(
                _finding(
                    codes.TRACE_CHAIN_BROKEN,
                    f"captured_observation_step {captured_step} is not this row's step {index}",
                    step=index,
                )
            )
        current_capture = _translate_capture(row.get("captured_observation_capture"))
        if current_capture is not None and capture is not None and current_capture != capture:
            findings.append(
                _finding(
                    codes.CAPTURE_STAMPS_INCONSISTENT,
                    "the current acquisition's stamps differ from the packet acquired at the "
                    "previous row",
                    step=index,
                )
            )
        consumed_capture = _translate_capture(row.get("observation_capture"))
        recorded = defined.get(consumed_index)
        if consumed_capture is not None and recorded is not None and consumed_capture != recorded:
            findings.append(
                _finding(
                    codes.CAPTURE_STAMPS_INCONSISTENT,
                    f"the consumed observation's stamps differ from those recorded when observation "
                    f"{consumed_index} was acquired",
                    step=index,
                )
            )
        if consumed_capture is not None:
            oldest = min(c["simulation_s"] for c in consumed_capture["components"].values())
            if abs(oldest - float(row["observation_sim_time_s"])) > 1e-9:
                findings.append(
                    _finding(
                        codes.CAPTURE_STAMPS_INCONSISTENT,
                        f"observation_sim_time_s {row['observation_sim_time_s']} differs from the "
                        f"oldest consumed component acquisition {oldest}",
                        step=index,
                    )
                )
        source = row["observation_source_run_id"]
        provenance = (
            {"kind": "closed_loop"}
            if source == run_id
            else {"kind": "recorded", "source_run_id": source, "source_step": consumed_index}
        )
        observation = {
            "id": f"obs-{index:04d}",
            "t": sim(observation_t),
            "source": "sensor",
            "provenance": provenance,
        }
        if capture is not None:
            observation["capture"] = capture
        host = {
            key: row[field]
            for key, field in (
                ("inference_started_s", "inference_started_host_s"),
                ("inference_finished_s", "inference_finished_host_s"),
                ("executed_s", "action_host_s"),
            )
            if row.get(field) is not None
        }
        action = {
            "computed_from": f"obs-{consumed_index:04d}",
            "t_executed": sim(row["action_sim_time_s"]),
            "intended": list(row["intended_action"]),
            "executed": executed,
        }
        if host:
            action["host"] = host
        steps.append(
            {
                "step": index,
                "observation": observation,
                "action": action,
                "measurements": {
                    "cube_height_m": row["cube_height_m"],
                    "task_success": 1 if row["task_success"] else 0,
                    "executed_action_max_abs": max((abs(float(a)) for a in executed), default=0.0),
                    "action_dimension": len(executed),
                    "step_period_s": row["next_sim_time_s"] - row["action_sim_time_s"],
                    "step_index": index,
                    "inference_wall_s": row["inference_wall_s"],
                },
            }
        )
    return steps


def translate_step(row: dict, run_id: str) -> dict:
    """One row on its own; the execution lane's interface probe uses this form."""
    return translate_steps([mapping(row, "row")], run_id, [])[0]


def _verify_raw_artifacts(
    run: dict, root: Path, findings: list[dict], manifest: dict | None, strict: bool
) -> None:
    artifacts = run.get("artifacts") or []
    verified, missing = 0, []
    if strict and not artifacts and run.get("execution_mode") == "full_closed_loop":
        findings.append(
            _finding(
                codes.ARTIFACT_STORE_UNVERIFIED,
                "the run declares no raw artifacts; under the strict obligation an execution "
                "without a digest-bound raw record cannot be verified",
            )
        )
    for item in artifacts:
        relative = item.get("path")
        expected = item.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            findings.append(
                _finding(
                    codes.MALFORMED_RECORD,
                    "artifact entry needs path and sha256",
                    path="run.artifacts",
                )
            )
            continue
        if manifest is not None and manifest.get(relative) not in (None, expected):
            findings.append(
                _finding(
                    codes.ARTIFACT_DIGEST_MISMATCH,
                    f"raw artifact {relative}: run declares {expected}, manifest {manifest[relative]}",
                )
            )
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            findings.append(
                _finding(codes.MALFORMED_RECORD, f"artifact path escapes the root: {relative}")
            )
            continue
        if not target.is_file():
            missing.append(relative)
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            findings.append(
                _finding(
                    codes.ARTIFACT_DIGEST_MISMATCH,
                    f"raw artifact {relative}: declared {expected}, actual {actual}",
                )
            )
        else:
            verified += 1
    if verified:
        findings.append(
            _finding(
                codes.RAW_ARTIFACT_VERIFIED,
                f"{verified} of {len(artifacts)} raw artifacts verified under {root}",
            )
        )
    if missing:
        code = codes.ARTIFACT_STORE_UNVERIFIED if strict else codes.RAW_ARTIFACT_UNVERIFIED
        findings.append(
            _finding(
                code, f"{len(missing)} raw artifacts not accessible under {root}: {missing[:3]}"
            )
        )


RAW_ROW_DIGESTS = (
    ("observation", "observation_sha256"),
    ("next_observation", "next_observation_sha256"),
    ("state_before", "state_before_sha256"),
    ("state_after", "state_after_sha256"),
    ("policy_state_before", "policy_state_sha256"),
    ("policy_state_after", "policy_state_after_sha256"),
    ("captured_observation", "captured_observation_sha256"),
)
RAW_ROW_EQUAL = (
    ("intended_action", "intended_action"),
    ("executed_action", "executed_action"),
    ("observation_capture", "observation_capture"),
    ("next_observation_capture", "next_observation_capture"),
    ("captured_observation_capture", "captured_observation_capture"),
)


def _verify_raw_trace(run: dict, rows: list[dict], root: Path, findings: list[dict]) -> None:
    """Compare the compact rows with the raw per-step record when the store is available.

    Every digest the compact row carries must be the digest of the raw value, and the
    actions and stamps must be equal. A forged compact trace then needs a matching forged
    raw file; that raises the cost of an offline forgery, it does not make one impossible.
    """
    raw_name = next(
        (
            item.get("path")
            for item in run.get("artifacts") or []
            if isinstance(item, dict) and str(item.get("path", "")).endswith(".jsonl.gz")
        ),
        None,
    )
    if raw_name is None:
        return
    target = (root / raw_name).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        return
    try:
        with gzip.open(target, "rt") as stream:
            lines = [
                json.loads(line, parse_constant=_reject_constant) for line in stream if line.strip()
            ]
    except (OSError, ValueError, Malformed) as error:
        findings.append(
            _finding(codes.RAW_TRACE_MISMATCH, f"raw trace {raw_name} unreadable: {error}")
        )
        return
    if not lines:
        findings.append(_finding(codes.RAW_TRACE_MISMATCH, f"raw trace {raw_name} is empty"))
        return
    reset, raw_rows = lines[0], lines[1:]
    initial = run.get("initial_state_sha256")
    if initial and isinstance(reset, dict) and "reset" in reset:
        if producer_digest(reset["reset"]) != initial:
            findings.append(
                _finding(
                    codes.RAW_TRACE_MISMATCH, "raw reset state does not match initial_state_sha256"
                )
            )
            return
    if len(raw_rows) != len(rows):
        findings.append(
            _finding(
                codes.RAW_TRACE_MISMATCH,
                f"raw trace has {len(raw_rows)} rows; the compact trace has {len(rows)}",
            )
        )
        return
    for index, (raw, row) in enumerate(zip(raw_rows, rows, strict=True)):
        if not isinstance(raw, dict) or raw.get("step") != row.get("step"):
            findings.append(
                _finding(codes.RAW_TRACE_MISMATCH, "raw and compact steps disagree", step=index)
            )
            return
        for raw_key, digest_key in RAW_ROW_DIGESTS:
            if row.get(digest_key) is None:
                # An explicitly missing digest is a declared gap, not a mismatch, as long as
                # the raw record declares the same gap; a value on one side only is a mismatch.
                if raw_key in raw and raw.get(raw_key) is not None:
                    findings.append(
                        _finding(
                            codes.RAW_TRACE_MISMATCH,
                            f"{digest_key} is declared unavailable but the raw record carries "
                            f"{raw_key}",
                            step=index,
                        )
                    )
                    return
                continue
            if (
                digest_key in row
                and raw_key in raw
                and producer_digest(raw[raw_key]) != row[digest_key]
            ):
                findings.append(
                    _finding(
                        codes.RAW_TRACE_MISMATCH,
                        f"{digest_key} is not the digest of the raw {raw_key}",
                        step=index,
                    )
                )
                return
        for raw_key, row_key in RAW_ROW_EQUAL:
            if row_key in row and raw_key in raw and raw[raw_key] != row[row_key]:
                findings.append(
                    _finding(
                        codes.RAW_TRACE_MISMATCH,
                        f"{row_key} differs from the raw record",
                        step=index,
                    )
                )
                return
    findings.append(
        _finding(
            codes.RAW_TRACE_CONSISTENT,
            f"{len(rows)} compact rows agree with the raw record {raw_name}: digests of observations, "
            "states and recurrent state, actions and acquisition stamps",
        )
    )


def _index(value: object) -> int | None:
    """An integer row index or count; booleans and floats are neither."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _check_carried_prefix(
    source: object,
    source_step: object,
    declared_steps: object,
    prefix_rows: list,
    rows: list,
    findings: list[dict],
) -> None:
    """Carried recurrent state must be the executed prefix's state after its declared source row.

    ``prefix_run.steps`` is a row count and ``policy_state_reset.source_step`` is the zero-based
    index of the row whose post-step state was carried: a 21-row prefix carries row 20. Each is
    checked against the retained prefix on its own; the count is never compared to the index.
    """
    if declared_steps is not None and _index(declared_steps) != len(prefix_rows):
        findings.append(
            _finding(
                codes.RESET_EVIDENCE_INCOMPLETE,
                f"prefix run {source!r} has {len(prefix_rows)} rows; prefix_run.steps declares "
                f"{declared_steps!r}",
            )
        )
    index = _index(source_step)
    source_row = None
    if source_step is None:
        source_row = prefix_rows[-1] if prefix_rows else None
    elif index is None or not 0 <= index < len(prefix_rows):
        findings.append(
            _finding(
                codes.RESET_EVIDENCE_INCOMPLETE,
                f"source_step {source_step!r} is not a row of prefix run {source!r} "
                f"({len(prefix_rows)} rows; the last index is {len(prefix_rows) - 1})",
            )
        )
    else:
        source_row = prefix_rows[index]
        if index != len(prefix_rows) - 1:
            findings.append(
                _finding(
                    codes.RESET_EVIDENCE_INCOMPLETE,
                    f"source_step {index} is not the last row ({len(prefix_rows) - 1}) of prefix "
                    f"run {source!r}; the rows after it were executed but not carried",
                )
            )
    if source_row is None:
        return
    final = source_row.get("policy_state_after_sha256")
    entering = rows[0].get("policy_state_sha256") if rows else None
    if final and entering and final != entering:
        findings.append(
            _finding(
                codes.TRACE_CHAIN_BROKEN,
                "the carried recurrent state is not the executed prefix's state after its "
                "declared source row",
                step=0,
            )
        )


def _run_identity(run: dict) -> dict | None:
    identity: dict[str, str] = {}
    declared = run.get("identity")
    if isinstance(declared, dict):
        identity.update({k: v for k, v in declared.items() if isinstance(v, str) and v.strip()})
    for key in (
        "invocation_id",
        "execution_identity_sha256",
        "configuration_sha256",
        "code_sha256",
        "dependencies_sha256",
        "policy_sha256",
    ):
        value = run.get(key)
        if isinstance(value, str) and value.strip():
            identity.setdefault(key, value)
    code = run.get("code")
    if isinstance(code, dict):
        if isinstance(code.get("git_head"), str):
            identity.setdefault("code_git_head", code["git_head"])
        if isinstance(code.get("lock_sha256"), str):
            identity.setdefault("lock_sha256", code["lock_sha256"])
        if isinstance(code.get("sources"), dict):
            identity.setdefault("sources_sha256", producer_digest(code["sources"]))
        identity.setdefault("code_sha256", producer_digest(code))
    value = run.get("policy_sha256")
    if isinstance(value, str) and value.strip():
        identity.setdefault("policy_sha256", value)
    return identity or None


def translate_run(
    run: dict,
    known: dict[str, str],
    case: dict,
    qualification: dict,
    root: Path,
    min_height: float,
    plans: dict[str, dict],
    manifest: dict | None,
    roles: dict[str, str] | None = None,
    raw_runs: dict[str, dict] | None = None,
) -> dict:
    path = "run"
    run_id = string(run, "id", path)
    digest = string(run, "candidate_sha256", path)
    strict = case["obligation"] == OBLIGATION_V02
    findings: list[dict] = []
    roles = roles or {}
    raw_runs = raw_runs or {}
    plan_id = string(run, "plan_id", path)
    plan = plans.get(plan_id, {})
    configuration = run.get("configuration") if isinstance(run.get("configuration"), dict) else {}
    dep = (
        configuration.get("deployment")
        if isinstance(configuration.get("deployment"), dict)
        else None
    )
    if dep is not None and producer_digest(dep) != digest:
        findings.append(
            _finding(
                codes.IDENTITY_MISMATCH,
                "candidate_sha256 is not the digest of configuration.deployment",
            )
        )
        dep = None
    plan_by_digest = {
        str(p.get("candidate_sha256")): pid
        for pid, p in plans.items()
        if isinstance(p, dict) and p.get("candidate_sha256")
    }
    mode = known.get(digest) or plan_by_digest.get(digest)
    if mode is None and dep is not None:
        mode = plan_id
    if mode is None:
        findings.append(
            _finding(
                codes.IDENTITY_MISMATCH,
                f"candidate digest {digest} matches no known deployment of the case policy",
            )
        )
    # An explicit plan role wins over digest equality: a rollback candidate can share the
    # working deployment's digest and still be a candidate under test.
    plan_role = plan.get("role") if plan.get("role") in PLAN_ROLES else None
    if plan_role is not None and plan.get("candidate_sha256") not in (None, digest):
        findings.append(
            _finding(
                codes.IDENTITY_MISMATCH,
                f"plan {plan_id!r} declares candidate {str(plan.get('candidate_sha256'))[:12]}, the "
                f"run carries {digest[:12]}",
            )
        )
    # An executed prefix context is a probe in any bundle. The producer's "calibration"
    # assignment role marks a probe only in a calibration bundle; in a case with declared
    # revisions, explore-only runs are the case's own reference, regression and candidates.
    assignment_role = roles.get(run_id)
    probe = (
        case.get("calibration", False)
        or assignment_role in ("executed_prefix_context", "probe")
        or plan_role in ("probe", "executed_prefix_context")
    )
    if plan_role == "reference" or (
        plan_role is None and (digest == case["revisions"]["working"] or mode == "reference")
    ):
        revision_role = "working"
    else:
        revision_role = "changed"
    candidate = None
    if plan_role is not None:
        is_plain_deployment = plan_role in ("reference", "regression")
    else:
        is_plain_deployment = mode in ("reference", "regression") or digest in (
            case["revisions"]["working"],
            case["revisions"]["changed"],
        )
    changed_dep = None
    for other in plans.values():
        if isinstance(other, dict) and other.get("role") == "regression":
            if isinstance(other.get("deployment"), dict):
                changed_dep = other["deployment"]
    if changed_dep is None:
        for other in raw_runs.values():
            conf = (
                other.get("configuration") if isinstance(other.get("configuration"), dict) else {}
            )
            if other.get("candidate_sha256") == case["revisions"]["changed"] and isinstance(
                conf.get("deployment"), dict
            ):
                changed_dep = conf["deployment"]
                break
    if not is_plain_deployment:
        deployable = plan.get("deployable", run.get("deployable"))
        candidate = {
            "id": mode or plan_id or "unknown-deployment",
            "digest": digest,
            "deployable": deployable if isinstance(deployable, bool) else None,
            "components": deployment_components(dep, changed_dep)
            if dep is not None
            else COMPONENTS.get(mode or "", []),
        }
        if dep is not None:
            candidate["deployment"] = deployment_label(dep)
    if probe:
        revision_role = "probe"
    rows = [
        mapping(item, f"{path}.trace[{i}]")
        for i, item in enumerate(sequence(require(run, "trace", path), f"{path}.trace"))
    ]
    foreign = Counter(
        row.get("observation_source_run_id")
        for row in rows
        if row.get("observation_source_run_id") != run_id
    )
    execution_mode = string(run, "execution_mode", path)
    intervention = {"mechanism": plan_id, "activation_step": 0} if candidate else None
    if execution_mode == "full_closed_loop":
        translated_plan = {"continuation": "full_rerun", "intervention": intervention}
    else:
        translated_plan = {
            "continuation": "partial_reuse",
            "source_run_id": foreign.most_common(1)[0][0] if foreign else None,
            "intervention": intervention,
        }
    initial = run.get("initial_state_sha256") or ""
    policy_reset = run.get("policy_state_reset")
    proposed_reset = run.get("policy_reset") if isinstance(run.get("policy_reset"), dict) else {}
    prefix_run = run.get("prefix_run") if isinstance(run.get("prefix_run"), dict) else {}
    carried = (isinstance(policy_reset, dict) and policy_reset.get("status") == "carried") or (
        proposed_reset.get("mode") == "carry_prefix"
    )
    if carried:
        source = policy_reset.get("source_run_id") if isinstance(policy_reset, dict) else None
        source_step = policy_reset.get("source_step") if isinstance(policy_reset, dict) else None
        if source is None:
            source = (
                proposed_reset.get("prefix_run_id")
                or prefix_run.get("id")
                or prefix_run.get("run_id")
            )
        declared_steps = prefix_run.get("steps")
        # The evaluator's record names the carried row as an index. An undeclared index is
        # derived from the retained prefix's last executed row, or from the declared length
        # when the prefix is absent; the derivation is recorded and checked below.
        prefix_record = raw_runs.get(str(source)) if source is not None else None
        retained_rows = prefix_record.get("trace") if prefix_record is not None else None
        derived_step = None
        if isinstance(retained_rows, list) and retained_rows:
            derived_step = len(retained_rows) - 1
        elif _index(declared_steps) is not None and declared_steps > 0:
            derived_step = declared_steps - 1
        policy_evidence = {
            "status": "carried",
            "source_run_id": source,
            "source_step": _index(source_step) if _index(source_step) is not None else derived_step,
            "source_step_declared": source_step is not None,
            "declared_prefix_steps": declared_steps,
            "digest": rows[0].get("policy_state_sha256") if rows else None,
        }
        if prefix_record is None:
            findings.append(
                _finding(
                    codes.RESET_EVIDENCE_INCOMPLETE,
                    f"carried recurrent state names prefix run {source!r}, which is not in the bundle",
                )
            )
        elif not isinstance(prefix_record.get("trace"), list):
            findings.append(
                _finding(
                    codes.RESET_EVIDENCE_INCOMPLETE,
                    f"prefix run {source!r} carries no inline trace; the carried state cannot be "
                    "checked against an executed row",
                )
            )
        else:
            prefix_rows = prefix_record["trace"]
            policy_evidence["prefix_rows"] = len(prefix_rows)
            _check_carried_prefix(source, source_step, declared_steps, prefix_rows, rows, findings)
    elif proposed_reset.get("episode_reset_applied") is True and proposed_reset.get("after_sha256"):
        policy_evidence = {
            "status": "cleared",
            "digest": proposed_reset["after_sha256"],
            "derivation": "recorded episode reset event with its resulting recurrent-state digest",
        }
    elif rows and rows[0].get("policy_state_sha256"):
        policy_evidence = {
            "status": "cleared",
            "digest": rows[0].get("policy_state_sha256"),
            "derivation": "recurrent state digest recorded before step 0; equality across runs "
            "is checked at bundle level",
        }
    else:
        policy_evidence = {"status": "unknown"}
    evidence = {
        "sim_state": {"status": "restored", "digest": initial}
        if initial
        else {"status": "unknown"},
        "controller_state": (
            {
                "status": "restored",
                "digest": initial,
                "derivation": "controller goals and gains are part of the captured initial state",
            }
            if initial
            else {"status": "unknown"}
        ),
        "policy_state": policy_evidence,
        "action_queue": (
            {"status": "not_applicable", "reason": str(qualification["queue"])}
            if qualification.get("queue")
            else {"status": "unknown"}
        ),
        "rng": {"status": "seeded", "seed": run.get("seed")},
    }
    steps = translate_steps(rows, run_id, findings)
    after_reset = proposed_reset.get("after_sha256")
    if rows and after_reset and rows[0].get("policy_state_sha256") not in (None, after_reset):
        findings.append(
            _finding(
                codes.TRACE_CHAIN_BROKEN,
                "the recorded reset outcome is not the recurrent state entering inference at step 0",
                step=0,
            )
        )
    for index in range(1, len(rows)):
        before = rows[index].get("policy_state_sha256")
        after_previous = rows[index - 1].get("policy_state_after_sha256")
        if not before or not after_previous:
            continue
        if rows[index].get("policy_reset_before_inference"):
            if after_reset and before != after_reset:
                findings.append(
                    _finding(
                        codes.TRACE_CHAIN_BROKEN,
                        "a recorded per-action reset did not restore the fresh recurrent state",
                        step=index,
                    )
                )
                break
        elif before != after_previous:
            findings.append(
                _finding(
                    codes.TRACE_CHAIN_BROKEN,
                    "the recurrent state changed between steps without a recorded reset",
                    step=index,
                )
            )
            break
    # The observation a row consumed must be the packet recorded when it was acquired:
    # the reset packet for index 0, otherwise the previous rows' next observation. A stale
    # delivery consumes an older packet; that is a measured timing failure, not a broken chain.
    acquired: dict[int, str | None] = {}
    if rows and int(rows[0].get("observation_step", 0)) == 0:
        acquired[0] = rows[0].get("observation_sha256")
    for row in rows:
        acquired[int(row["step"]) + 1] = row.get("next_observation_sha256")
    for index, current in enumerate(rows):
        consumed = int(current.get("observation_step", index))
        expected = acquired.get(consumed)
        if expected is None:
            findings.append(
                _finding(
                    codes.TRACE_CHAIN_BROKEN,
                    f"the consumed observation {consumed} was never recorded as acquired",
                    step=index,
                )
            )
            break
        if current.get("observation_sha256") != expected:
            findings.append(
                _finding(
                    codes.TRACE_CHAIN_BROKEN,
                    "the observation fed to this step is not the packet recorded when observation "
                    f"{consumed} was acquired",
                    step=index,
                )
            )
            break
    for index in range(1, len(rows)):
        previous, current = rows[index - 1], rows[index]
        if current.get("state_before_sha256") != previous.get("state_after_sha256"):
            findings.append(
                _finding(
                    codes.TRACE_CHAIN_BROKEN,
                    "the state before this step is not the state after the previous step",
                    step=index,
                )
            )
            break
        if current.get("observation_source_run_id") != previous.get(
            "next_observation_source_run_id"
        ):
            findings.append(
                _finding(
                    codes.TRACE_CHAIN_BROKEN,
                    "observation source identity disagrees with the previous step's next-observation source",
                    step=index,
                )
            )
            break
    if rows and initial and rows[0].get("state_before_sha256") != initial:
        findings.append(
            _finding(
                codes.TRACE_CHAIN_BROKEN,
                "the state before step 0 is not the recorded initial state",
                step=0,
            )
        )
    inconsistent = [
        i
        for i, row in enumerate(rows)
        if isinstance(row.get("cube_height_m"), int | float)
        and not isinstance(row.get("cube_height_m"), bool)
        and bool(row.get("task_success")) != (float(row["cube_height_m"]) > min_height)
    ]
    if inconsistent:
        findings.append(
            _finding(
                codes.MEASUREMENT_INCONSISTENT,
                f"task_success disagrees with cube_height_m > {min_height} at {len(inconsistent)} steps",
                step=inconsistent[0],
            )
        )
    out_of_bounds = [
        i for i, row in enumerate(rows) if any(abs(float(a)) > 1.0 for a in row["intended_action"])
    ]
    if out_of_bounds:
        peak = max(abs(float(a)) for row in rows for a in row["intended_action"])
        findings.append(
            _finding(
                codes.INTENDED_ACTION_OUT_OF_BOUNDS,
                f"the policy's intended action exceeds the normalized bound at {len(out_of_bounds)} of "
                f"{len(rows)} steps (peak |a| = {peak:.6g}); the adapter clips before execution",
                step=out_of_bounds[0],
            )
        )
    _verify_raw_artifacts(run, root, findings, manifest, strict)
    _verify_raw_trace(run, rows, root, findings)
    costs = {}
    for index, item in enumerate(run.get("costs") or []):
        data = mapping(item, f"{path}.costs[{index}]")
        costs[str(data.get("category", f"cost-{index}"))] = _cost(item, f"{path}.costs[{index}]")
    # An executed prefix's wall is inside its main run's measured wall. The producer names
    # the parent explicitly; an older record implies it through the main run's prefix_run.
    cost_parent = run.get("cost_parent_run_id")
    if cost_parent is None:
        cost_parent = next(
            (
                other_id
                for other_id, other in raw_runs.items()
                if isinstance(other.get("prefix_run"), dict)
                and run_id in (other["prefix_run"].get("id"), other["prefix_run"].get("run_id"))
            ),
            None,
        )
    return {
        "schema": "nisayon.run.v1",
        "id": run_id,
        "case_id": string(run, "case_id", path),
        "evidence_origin": string(run, "evidence_origin", path),
        "started_at": wall(string(run, "started_at", path)),
        "revision": {
            "role": revision_role,
            "id": case["revisions"]["working"]
            if revision_role == "working"
            else case["revisions"]["changed"],
        },
        "task": {"policy": dict(case["task"]["policy"]), "backend": dict(case["task"]["backend"])},
        "condition_id": string(run, "condition_id", path),
        "candidate": candidate,
        "plan": translated_plan,
        "process": {
            "status": PROCESS.get(run.get("process_status"), "nonzero"),
            "returncode": None,
            "error": run.get("error"),
        },
        "reset": {
            "procedure_id": string(run, "reset_id", path),
            "initial_condition_id": string(run, "condition_id", path),
            "evidence": evidence,
        },
        "trace": {
            "schema": "nisayon.trace.v1",
            "run_id": run_id,
            "measurement_units": dict(UNITS),
            "steps": steps,
        },
        "task_outcome": {"claimed": run.get("task_outcome") or "unknown"},
        "validity": {"claimed": VALIDITY.get(run.get("measurement_status"), "unknown")},
        "costs": costs,
        "cost_parent_run_id": str(cost_parent) if cost_parent is not None else None,
        "identity": _run_identity(run),
        "artifacts": run.get("artifacts") or [],
        "derived_from": run.get("derived_from"),
        "_adapter_findings": findings,
    }


def _parse_wall(value: object) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def _frozen_identity(frozen: dict | None) -> dict:
    if not frozen:
        return {}
    identity: dict[str, str] = {}
    code = frozen.get("code") or {}
    if isinstance(code, dict):
        if isinstance(code.get("git_head"), str):
            identity["code_git_head"] = code["git_head"]
        if isinstance(code.get("lock_sha256"), str):
            identity["lock_sha256"] = code["lock_sha256"]
        if isinstance(code.get("sources"), dict):
            identity["sources_sha256"] = producer_digest(code["sources"])
        # Runs carry code_sha256 = digest of the whole code identity block.
        identity["code_sha256"] = producer_digest(code)
    candidate = frozen.get("candidate") or {}
    if isinstance(candidate, dict) and isinstance(candidate.get("policy_sha256"), str):
        identity["policy_sha256"] = candidate["policy_sha256"]
    for key in ("execution_identity_sha256", "configuration_sha256"):
        if isinstance(frozen.get(key), str):
            identity[key] = frozen[key]
    return identity


def translate_confirmation(
    conf: dict,
    runs: dict[str, dict],
    case: dict,
    known: dict[str, str],
    frozen: dict | None,
    roles: dict[str, str] | None = None,
) -> dict:
    path = "bundle.confirmation"
    frozen_digest = string(conf, "candidate_sha256", path)
    frozen_at = string(conf, "frozen_at", path)
    freeze = _parse_wall(frozen_at)
    references = [
        str(item)
        for item in sequence(require(conf, "reference_run_ids", path), f"{path}.reference_run_ids")
    ]
    candidates = [
        str(item)
        for item in sequence(require(conf, "candidate_run_ids", path), f"{path}.candidate_run_ids")
    ]
    if len(references) != len(candidates):
        raise Malformed(
            f"{path}.candidate_run_ids", "reference and candidate run lists differ in length"
        )
    assignments = []
    for reference_id, candidate_id in zip(references, candidates, strict=True):
        condition = None
        for run_id in (reference_id, candidate_id):
            if run_id in runs:
                condition = runs[run_id]["condition_id"]
                break
        assignments.append(
            {
                "condition_id": condition or f"unknown-condition-of-{reference_id}",
                "reference_run_id": reference_id,
                "candidate_run_id": candidate_id,
            }
        )
    failure = case["failure"]["condition_id"]
    conditions = []
    roles = roles or {}

    def closed_loop_first(run: dict) -> tuple[int, str]:
        # Full closed-loop executions are reproduction evidence; a replay or prefix reuse is not.
        return (0 if run["plan"]["continuation"] == "full_rerun" else 1, run["started_at"]["value"])

    declared_reproduction = conf.get("reproduction")
    reproduction_assignment = None
    if not isinstance(declared_reproduction, dict) and roles:
        # The execution lane marks reproduction runs by role in the bundle's assignments.
        reproduction_refs = [
            r
            for r in runs.values()
            if roles.get(r["id"]) == "reproduction"
            and r["candidate"] is None
            and r["revision"]["role"] == "working"
            and r["condition_id"] == failure
        ]
        reproduction_cands = [
            r
            for r in runs.values()
            if roles.get(r["id"]) == "reproduction"
            and r["candidate"]
            and r["candidate"]["digest"] == frozen_digest
            and r["condition_id"] == failure
        ]
        if reproduction_refs and reproduction_cands:

            def post_freeze_first(run: dict) -> tuple[int, str]:
                started = _parse_wall(run["started_at"]["value"])
                after = freeze is not None and started is not None and started > freeze
                return (0 if after else 1, run["started_at"]["value"])

            declared_reproduction = {
                "condition_id": failure,
                "reference_run_id": sorted(reproduction_refs, key=post_freeze_first)[0]["id"],
                "candidate_run_id": sorted(reproduction_cands, key=post_freeze_first)[0]["id"],
            }
    if isinstance(declared_reproduction, dict):
        reproduction_assignment = {
            "condition_id": str(declared_reproduction.get("condition_id") or failure),
            "reference_run_id": str(declared_reproduction.get("reference_run_id")),
            "candidate_run_id": str(declared_reproduction.get("candidate_run_id")),
        }
    else:
        reference_runs = sorted(
            (
                r
                for r in runs.values()
                if r["candidate"] is None
                and r["revision"]["role"] == "working"
                and r["condition_id"] == failure
            ),
            key=closed_loop_first,
        )
        candidate_runs = sorted(
            (
                r
                for r in runs.values()
                if r["candidate"]
                and r["candidate"]["digest"] == frozen_digest
                and r["condition_id"] == failure
            ),
            key=closed_loop_first,
        )
        # Prefer a post-freeze rerun when one exists; otherwise the earliest closed-loop evidence.
        post_freeze = [
            r
            for r in candidate_runs
            if freeze is not None and (_parse_wall(r["started_at"]["value"]) or freeze) > freeze
        ]
        chosen = post_freeze[0] if post_freeze else (candidate_runs[0] if candidate_runs else None)
        if reference_runs and chosen is not None:
            reproduction_assignment = {
                "condition_id": failure,
                "reference_run_id": reference_runs[0]["id"],
                "candidate_run_id": chosen["id"],
            }
    if reproduction_assignment is not None:
        conditions.append(
            {
                "id": reproduction_assignment["condition_id"],
                "role": "reproduction",
                "generated_by": "the registered failure",
            }
        )
        assignments.insert(0, reproduction_assignment)
    for condition_id in sequence(require(conf, "condition_ids", path), f"{path}.condition_ids"):
        conditions.append(
            {
                "id": str(condition_id),
                "role": "fresh",
                "generated_by": "producer-declared confirmation condition",
            }
        )
    exploration = sorted(
        {
            r["condition_id"]
            for r in runs.values()
            if r["candidate"]
            and freeze is not None
            and (_parse_wall(r["started_at"]["value"]) or freeze) <= freeze
        }
    )
    contamination = [str(item) for item in conf.get("contamination") or []]
    return {
        "schema": "nisayon.confirmation.v1",
        "id": f"confirmation-{frozen_digest[:12]}",
        "case_id": case["id"],
        "protocol": {
            "id": case.get("obligation", PROTOCOL_ID),
            "predicates_digest": digest_of(case["predicates"]),
            "producer_protocol_sha256": conf.get("protocol_sha256"),
            "producer_predicates_digest": case["predicates"]["producer_predicates_digest"],
        },
        "candidate": {
            "id": known.get(frozen_digest, "unknown-deployment"),
            "digest": frozen_digest,
            "frozen_at": wall(frozen_at),
        },
        "identity": _frozen_identity(frozen),
        "conditions": conditions,
        "exploration_condition_ids": exploration,
        "assignments": assignments,
        "contamination": {"declared": "none" if not contamination else "; ".join(contamination)},
    }


def locate_frozen_protocol(root: Path, source: Path) -> Path | None:
    for candidate in (root / "frozen-protocol.json", source.parent / "frozen-protocol.json"):
        if candidate.is_file():
            return candidate
    return None


def verify_frozen_protocol(
    document: dict, conf: dict, frozen: dict | None, found: Path | None, obligation: str
) -> list[Finding]:
    if frozen is None or found is None:
        return [
            Finding(
                codes.PROTOCOL_UNVERIFIED,
                "frozen-protocol.json is not under the artifact root or beside the bundle; "
                "the freeze is asserted by the confirmation record only",
            )
        ]
    findings = []
    if producer_digest(frozen) != conf.get("protocol_sha256"):
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH,
                f"{found.name} digest differs from the confirmation's protocol_sha256",
            )
        )
    if producer_digest(frozen.get("candidate")) != conf.get("candidate_sha256"):
        findings.append(
            Finding(
                codes.CANDIDATE_NOT_FROZEN,
                f"the candidate in {found.name} is not the confirmed candidate",
            )
        )
    if frozen.get("predicates") != document["case"].get("predicates"):
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH, "predicates in the frozen protocol differ from the case"
            )
        )
    if frozen.get("condition_ids") != conf.get("condition_ids"):
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH,
                "condition IDs in the frozen protocol differ from the confirmation",
            )
        )
    frozen_assignments = frozen.get("assignments")
    if frozen_assignments is not None and frozen_assignments != document.get("assignments"):
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH,
                "run assignments in the bundle differ from the frozen protocol's assignments",
            )
        )
    if isinstance(frozen_assignments, list):
        frozen_ids = {
            str(a.get("run_id"))
            for a in frozen_assignments
            if isinstance(a, dict) and a.get("run_id")
        }
        assigned = [
            *conf.get("reference_run_ids", []),
            *conf.get("candidate_run_ids", []),
        ]
        stray = [run_id for run_id in assigned if str(run_id) not in frozen_ids]
        if stray:
            findings.append(
                Finding(
                    codes.PROTOCOL_MISMATCH,
                    f"assigned runs {stray[:3]} are not named in the frozen protocol's assignments",
                )
            )
    by_run = frozen.get("configuration_sha256_by_run_id")
    if isinstance(by_run, dict):
        findings.extend(_check_frozen_run_configurations(document, frozen, by_run))
    if frozen.get("frozen_at") != conf.get("frozen_at"):
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH,
                "freeze timestamps disagree between the protocol and the confirmation",
            )
        )
    frozen_head = (frozen.get("code") or {}).get("git_head")
    bundle_head = (document.get("code") or {}).get("git_head")
    if frozen_head and bundle_head and frozen_head != bundle_head and not conf.get("contamination"):
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH,
                f"execution sources changed after the freeze ({frozen_head} to {bundle_head}) "
                "without a contamination entry",
            )
        )
    if obligation == OBLIGATION_V02:
        predicates = frozen.get("predicates") or {}
        if not isinstance(predicates, dict) or predicates.get("progress_minimum_gain_m") is None:
            findings.append(
                Finding(
                    codes.PREREGISTRATION_MISSING,
                    "the v0.2 frozen protocol does not carry a producer progress declaration",
                )
            )
    if not findings:
        per_run = (
            f" and the {len(by_run)} per-run configuration digests"
            if isinstance(by_run, dict)
            else ""
        )
        findings.append(
            Finding(
                codes.PROTOCOL_VERIFIED,
                f"{found.name} verified: protocol digest, candidate digest, predicates, condition IDs, "
                f"freeze timestamp, execution code identity {frozen_head}{per_run} agree with the "
                "confirmation",
            )
        )
    return findings


def _check_frozen_run_configurations(document: dict, frozen: dict, by_run: dict) -> list[Finding]:
    """Protocol v4 freezes every assigned run's full configuration digest.

    A deployment digest cannot tell a 21-step prefix rollout from the full-horizon run of the
    same deployment; the per-run map can. Every assigned run must be in the map, and each run's
    declared and recomputed configuration digests must equal its frozen entry.
    """
    findings: list[Finding] = []
    assigned = [
        str(a.get("run_id"))
        for a in frozen.get("assignments") or []
        if isinstance(a, dict) and a.get("run_id")
    ]
    omitted = [run_id for run_id in assigned if run_id not in by_run]
    if omitted:
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH,
                f"configuration_sha256_by_run_id omits assigned runs {omitted[:3]}",
            )
        )
    runs = {str(run.get("id")): run for run in document.get("runs") or [] if isinstance(run, dict)}
    mismatched = []
    for run_id, expected in by_run.items():
        run = runs.get(str(run_id))
        if run is None:
            continue  # an absent assigned run is reported by the confirmation checks
        configuration = run.get("configuration")
        recomputed = producer_digest(configuration) if isinstance(configuration, dict) else None
        if run.get("configuration_sha256") != expected or (
            recomputed is not None and recomputed != expected
        ):
            mismatched.append(str(run_id))
    if mismatched:
        findings.append(
            Finding(
                codes.PROTOCOL_MISMATCH,
                f"runs {mismatched[:3]} do not carry the configuration frozen for them in "
                "configuration_sha256_by_run_id",
            )
        )
    return findings


def load_manifest(document: dict, root: Path, source: Path) -> tuple[dict | None, list[Finding]]:
    """A digest-bound relative-path manifest of the raw store, verified fail-closed.

    Accepts the evaluator's ``nisayon.artifact_manifest.v1`` (``files`` as an object) and
    the execution lane's ``nisayon.execution.artifacts.v1`` (``files`` as a list of entries).
    """
    declared = document.get("artifact_manifest")
    candidates: list[Path] = []
    expected_digest = None
    if isinstance(declared, dict) and isinstance(declared.get("path"), str):
        candidates.append(root / declared["path"])
        candidates.append(source.parent / declared["path"])
        expected_digest = (
            declared.get("sha256") if isinstance(declared.get("sha256"), str) else None
        )
    candidates += [root / "manifest.json", source.parent / "manifest.json"]
    found = next((p for p in candidates if p.is_file()), None)
    if found is None:
        return None, []
    raw = found.read_bytes()
    if expected_digest and hashlib.sha256(raw).hexdigest() != expected_digest:
        return None, [
            Finding(
                codes.ARTIFACT_DIGEST_MISMATCH, f"{found.name} does not match its declared digest"
            )
        ]
    try:
        data = json.loads(raw.decode(), parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, Malformed) as error:
        return None, [Finding(codes.MALFORMED_RECORD, f"{found.name}: {error}", path=str(found))]
    if not isinstance(data, dict) or data.get("schema") not in {
        MANIFEST_SCHEMA,
        PRODUCER_MANIFEST_SCHEMA,
    }:
        return None, [
            Finding(
                codes.MALFORMED_RECORD,
                f"{found.name} is not a known artifact manifest",
                path=str(found),
            )
        ]
    entries = data.get("files")
    files: dict[str, str] = {}
    if isinstance(entries, dict):
        files = {str(k): str(v) for k, v in entries.items()}
    elif isinstance(entries, list):
        for item in entries:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                return None, [
                    Finding(
                        codes.MALFORMED_RECORD, f"{found.name}: malformed entry", path=str(found)
                    )
                ]
            files[item["path"]] = str(item.get("sha256"))
    else:
        return None, [
            Finding(
                codes.MALFORMED_RECORD,
                f"{found.name}: files must be a list or object",
                path=str(found),
            )
        ]
    findings: list[Finding] = []
    verified = 0
    missing = []
    for relative, digest in files.items():
        if relative == found.name:
            continue
        target = (root / relative).resolve()
        if Path(relative).is_absolute() or not target.is_relative_to(root.resolve()):
            findings.append(
                Finding(
                    codes.ARTIFACT_DIGEST_MISMATCH, f"manifest path escapes the root: {relative}"
                )
            )
            continue
        if not target.is_file():
            missing.append(relative)
            continue
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            findings.append(
                Finding(
                    codes.ARTIFACT_DIGEST_MISMATCH,
                    f"manifest entry {relative} does not match its bytes",
                )
            )
        else:
            verified += 1
    if missing:
        findings.append(
            Finding(
                codes.ARTIFACT_STORE_UNVERIFIED,
                f"{len(missing)} of {len(files)} manifest entries are absent under {root}: {missing[:3]}",
            )
        )
    if not findings:
        findings.append(
            Finding(
                codes.ARTIFACT_MANIFEST_VERIFIED,
                f"{found.name}: {verified} files verified under {root}",
            )
        )
    return files, findings


def load_cost_ledger(
    document: dict, root: Path, source: Path, manifest: dict | None
) -> tuple[dict | None, list[Finding]]:
    """The producer's command ledger, bound by digest; its known sum and missing categories."""
    reference = document.get("preparation_cost_ledger")
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        return None, []
    found = next(
        (p for p in (root / reference["path"], source.parent / reference["path"]) if p.is_file()),
        None,
    )
    if found is None:
        return None, [
            Finding(
                codes.RAW_ARTIFACT_UNVERIFIED,
                f"cost ledger {reference['path']} is not accessible under the artifact root",
            )
        ]
    raw = found.read_bytes()
    expected = reference.get("sha256")
    if isinstance(expected, str) and hashlib.sha256(raw).hexdigest() != expected:
        return None, [
            Finding(
                codes.ARTIFACT_DIGEST_MISMATCH,
                f"cost ledger {found.name} does not match its declared digest",
            )
        ]
    if manifest is not None and manifest.get(reference["path"]) not in (None, expected):
        return None, [
            Finding(
                codes.ARTIFACT_DIGEST_MISMATCH, "cost ledger digest disagrees with the manifest"
            )
        ]
    try:
        data = json.loads(raw.decode(), parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, Malformed) as error:
        return None, [Finding(codes.MALFORMED_RECORD, f"{found.name}: {error}", path=str(found))]
    if not isinstance(data, dict):
        return None, [
            Finding(codes.MALFORMED_RECORD, f"{found.name} is not an object", path=str(found))
        ]
    return data, []


def _bundle_checks(document: dict, raw_runs: list[dict]) -> list[Finding]:
    findings: list[Finding] = []

    def declares_carried(run: dict) -> bool:
        reset = run.get("policy_reset") if isinstance(run.get("policy_reset"), dict) else {}
        legacy = (
            run.get("policy_state_reset") if isinstance(run.get("policy_state_reset"), dict) else {}
        )
        return reset.get("mode") == "carry_prefix" or legacy.get("status") == "carried"

    # Runs that declare a carried recurrent state are measured as such, not as reset outliers.
    cleared_runs = [run for run in raw_runs if run.get("trace") and not declares_carried(run)]
    first_policy = Counter(run["trace"][0].get("policy_state_sha256") for run in cleared_runs)
    if len(first_policy) > 1:
        majority = first_policy.most_common(1)[0][0]
        outliers = [
            run["id"]
            for run in cleared_runs
            if run["trace"][0].get("policy_state_sha256") != majority
        ]
        findings.append(
            Finding(
                codes.POLICY_RESET_STATE_DIFFERS,
                f"recurrent policy state before step 0 differs across runs; outliers {outliers[:5]}",
            )
        )
    groups: dict[tuple, list[dict]] = {}
    for run in raw_runs:
        if run.get("execution_mode") != "full_closed_loop":
            continue  # a replay or prefix reuse is not a repeated execution
        # Repeats share deployment, condition, assignment role and, for executed prefixes,
        # the declared prefix length; a 21-step and a 39-step prefix are different contexts.
        key = (
            str(run.get("candidate_sha256")),
            str(run.get("condition_id")),
            str(run.get("assignment_role")),
            len(run.get("trace") or [])
            if run.get("assignment_role") == "executed_prefix_context"
            else None,
        )
        groups.setdefault(key, []).append(run)
    for (digest, condition, _role, _prefix_length), members in groups.items():
        if len(members) < 2:
            continue
        first = members[0]
        for other in members[1:]:
            if len(first["trace"]) != len(other["trace"]):
                differing = f"lengths {len(first['trace'])} and {len(other['trace'])}"
                same = False
            else:
                counts = {
                    field: sum(
                        a.get(field) != b.get(field)
                        for a, b in zip(first["trace"], other["trace"], strict=True)
                    )
                    for field in REPEAT_FIELDS
                }
                same = not any(counts.values())
                differing = ", ".join(f"{field} {n}" for field, n in counts.items() if n)
            if same:
                findings.append(
                    Finding(
                        codes.QUALIFICATION_REPEAT,
                        f"runs {first['id']!r} and {other['id']!r} repeat deployment {digest[:12]} on "
                        f"{condition} with identical recorded state, observation, recurrent-state and "
                        f"action sequences over {len(first['trace'])} steps",
                    )
                )
            else:
                findings.append(
                    Finding(
                        codes.REPEAT_RUNS_DIFFER,
                        f"runs {first['id']!r} and {other['id']!r} repeat deployment {digest[:12]} on "
                        f"{condition} but differ: {differing}; a stochastic protocol is needed before pairing",
                    )
                )
    return findings


def translate(
    document: dict, source: Path, artifact_root: Path | None = None
) -> tuple[Bundle, list[Finding], dict]:
    doc = mapping(document, "bundle")
    schema = string(doc, "schema", "bundle")
    if schema not in {FIRST_CASE_SCHEMA, CALIBRATION_SCHEMA}:
        raise Malformed(
            "bundle.schema",
            f"expected {FIRST_CASE_SCHEMA} or {CALIBRATION_SCHEMA}, found {schema!r}",
        )
    calibration = schema == CALIBRATION_SCHEMA or not (
        isinstance(doc.get("case"), dict)
        and doc["case"].get("working_revision")
        and doc["case"].get("changed_revision")
    )
    source = Path(source)
    declared_root = doc.get("artifact_root") or "."
    if artifact_root is not None:
        # A caller-supplied root is relative to the caller's working directory, never joined
        # onto the bundle's location; the bundle's own declared root is relative to the bundle.
        root = Path(artifact_root).resolve()
    else:
        root = Path(str(declared_root))
        if not root.is_absolute():
            root = source.parent / root
    case_doc = mapping(require(doc, "case", "bundle"), "bundle.case")
    qualification = mapping(doc.get("qualification") or {}, "bundle.qualification")
    raw_runs = [
        mapping(item, f"bundle.runs[{i}]")
        for i, item in enumerate(sequence(require(doc, "runs", "bundle"), "bundle.runs"))
    ]
    policy_sha = string(
        mapping(require(case_doc, "policy", "bundle.case"), "bundle.case.policy"),
        "sha256",
        "bundle.case.policy",
    )
    known = known_deployments(policy_sha)
    changed = case_doc.get("changed_revision")
    regression_runs = sorted(
        (run for run in raw_runs if run.get("candidate_sha256") == changed),
        key=lambda run: str(run.get("started_at")),
    )
    failure_condition = str(regression_runs[0]["condition_id"]) if regression_runs else "undeclared"
    origins = {str(run.get("evidence_origin")) for run in raw_runs}
    origin = "synthetic_development" if "synthetic_development" in origins else "simulator"
    frozen_path = locate_frozen_protocol(root, source)
    frozen: dict | None = None
    frozen_error: Finding | None = None
    if frozen_path is not None:
        try:
            frozen = read_document(frozen_path)
        except Malformed as error:
            frozen_error = Finding(codes.MALFORMED_RECORD, error.detail, path=str(frozen_path))
    obligation = obligation_version(doc, frozen)
    case = translate_case(
        case_doc,
        qualification,
        list(doc.get("costs") or []),
        failure_condition,
        origin,
        obligation,
        calibration,
    )
    min_height = case["predicates"]["outcome"]["threshold"]
    plans = {
        str(p.get("id")): p for p in doc.get("plans") or [] if isinstance(p, dict) and p.get("id")
    }
    manifest, extra = load_manifest(doc, root, source)
    if manifest is None and obligation == OBLIGATION_V02 and not extra:
        extra.append(
            Finding(
                codes.ARTIFACT_MANIFEST_MISSING,
                "the strict obligation needs a digest-bound manifest of the raw artifact store",
            )
        )
    ledger, ledger_findings = load_cost_ledger(doc, root, source, manifest)
    extra.extend(ledger_findings)
    if ledger:
        case["preparation_costs"]["recorded_command_wall"] = {
            "value": ledger.get("known_command_wall_sum_s"),
            "unit": "s",
        }
        for item in ledger.get("unmeasured") or []:
            if isinstance(item, dict) and item.get("category"):
                case["preparation_costs"][str(item["category"])] = {
                    "value": None,
                    "unit": str(item.get("unit") or "unknown"),
                    "missing": str(item.get("reason") or "not measured"),
                }
    bundle = Bundle(root=source, artifact_root=root, case=case)
    assignment_roles = {
        str(a.get("run_id")): str(a.get("role"))
        for a in doc.get("assignments") or []
        if isinstance(a, dict) and a.get("run_id")
    }
    raw_by_id = {str(run.get("id")): run for run in raw_runs if run.get("id")}
    for index, run in enumerate(raw_runs):
        try:
            translated = translate_run(
                run,
                known,
                case,
                qualification,
                root,
                min_height,
                plans,
                manifest,
                assignment_roles,
                raw_by_id,
            )
        except (Malformed, KeyError, TypeError, ValueError) as error:
            bundle.unparsed.append(
                {"file": f"bundle.runs[{index}] ({run.get('id')})", "error": str(error)}
            )
            continue
        if translated["id"] in bundle.runs:
            bundle.unparsed.append(
                {"file": f"bundle.runs[{index}]", "error": f"duplicate run id {translated['id']!r}"}
            )
            continue
        bundle.runs[translated["id"]] = translated
    extra.extend(
        _bundle_checks(doc, [run for run in raw_runs if isinstance(run.get("trace"), list)])
    )
    conf = doc.get("confirmation")
    if conf is not None:
        if frozen_error is not None:
            extra.append(frozen_error)
        try:
            roles = {
                str(a.get("run_id")): str(a.get("role"))
                for a in doc.get("assignments") or []
                if isinstance(a, dict) and a.get("run_id")
            }
            bundle.confirmation = translate_confirmation(
                mapping(conf, "bundle.confirmation"), bundle.runs, case, known, frozen, roles
            )
            observed = (frozen or {}).get("previously_observed_seeds")
            if isinstance(observed, list):
                declared = set(bundle.confirmation.get("exploration_condition_ids", []))
                declared.update(f"seed-{seed}" for seed in observed if isinstance(seed, int))
                bundle.confirmation["exploration_condition_ids"] = sorted(declared)
        except Malformed as error:
            bundle.confirmation_error = error
        else:
            extra.extend(verify_frozen_protocol(doc, conf, frozen, frozen_path, obligation))
    producer = {
        "schema": FIRST_CASE_SCHEMA,
        "source": str(source),
        "bundle_sha256": digest_of(document),
        "artifact_root": str(root),
        "obligation": obligation,
        "frozen_protocol": str(frozen_path) if frozen_path else None,
        "manifest": "verified" if manifest is not None else "absent",
        "cost_ledger": {
            "path": (doc.get("preparation_cost_ledger") or {}).get("path")
            if isinstance(doc.get("preparation_cost_ledger"), dict)
            else None,
            "known_command_wall_sum_s": (ledger or {}).get("known_command_wall_sum_s"),
            "unmeasured": [
                item.get("category")
                for item in (ledger or {}).get("unmeasured") or []
                if isinstance(item, dict)
            ],
        },
        "code": doc.get("code"),
        "plans": sorted(plans),
        "known_deployments": known,
        "qualification": {
            key: qualification.get(key)
            for key in (
                "reset",
                "captured_state",
                "omitted_state",
                "continuation_supported",
                "clocks",
                "queue",
                "scope",
            )
        },
        "translation": {
            "revision_role": "reference deployments are the working revision; every other "
            "deployment runs on the changed transport",
            "candidate_components": COMPONENTS,
            "repair_scope": "config_edit of repair_gripper_sign only, from the declared scope "
            + str(case_doc.get("allowed_repair_scope")),
            "progress_predicate": case["predicates"]["progress"]["declared_by"],
            "deployability": "read from the plan or run; undeclared is assumed under v0.1 and "
            "unresolved under v0.2",
            "identity": "per-run identity from `identity`, `invocation_id`, "
            "`execution_identity_sha256`, `configuration_sha256`, `code` and `policy_sha256`; "
            "absent identity is inherited under v0.1 and unbound under v0.2",
            "reset_evidence": "sim_state and controller_state from initial_state_sha256; "
            "policy_state from `policy_state_reset` or the step-0 recurrent digest; action_queue "
            "from the qualification; rng from the seed",
            "timing": "observation age from the consumed observation's acquisition stamps; "
            "unmeasured without them; step period from next_sim_time_s minus action_sim_time_s",
            "outcome": "cube_height_m at the final step > min_cube_height_m, recomputed from the trace",
        },
    }
    return bundle, extra, producer


def _document_policy(document: object) -> str | None:
    case = document.get("case") if isinstance(document, dict) else None
    policy = case.get("policy") if isinstance(case, dict) else None
    digest = policy.get("sha256") if isinstance(policy, dict) else None
    return digest if isinstance(digest, str) else None


def evaluate_first_case(
    path: Path,
    artifact_root: Path | None = None,
    known_synthetic_digests: frozenset[str] = frozenset(),
    history: list[Path] | tuple[Path, ...] = (),
) -> dict:
    document = read_document(Path(path))
    bundle, extra, producer = translate(document, Path(path), artifact_root)
    consumed: set[str] = set()
    protocols: dict = {}
    problems: list[str] = []
    own: list[str] = []
    later: list[str] = []
    if history and isinstance(bundle.case, dict):
        conf = document.get("confirmation") if isinstance(document, dict) else None
        own_protocol = conf.get("protocol_sha256") if isinstance(conf, dict) else None
        identity = {
            "own_digest": producer.get("bundle_sha256"),
            "own_path": Path(path),
            "own_protocol": own_protocol if isinstance(own_protocol, str) else None,
            "own_frozen_at": conf.get("frozen_at") if isinstance(conf, dict) else None,
            "policy_sha256": _document_policy(document),
            "own_traces": inline_trace_digests(bundle.runs),
        }
        consumed, own, later = history_consumption(list(history), bundle.case["id"], **identity)
        protocols = retained_protocols(list(history), bundle.case["id"], **identity)
        problems = unreadable_history(list(history))
    return evaluate_loaded(
        bundle,
        known_synthetic_digests,
        extra,
        producer,
        consumed,
        protocols,
        problems,
        history_self=own,
        history_later=later,
        history_paths=[str(item) for item in history],
    )


def replay_control(
    document: dict,
    *,
    source_run_id: str = "regression-0",
    corrected_mode: str = "correction",
    run_id: str | None = None,
) -> dict:
    """Derive the invalid-replay control from a retained run.

    The corrected executed actions are paired with the source run's recorded
    observations, future state and outcome. Nothing is executed. The record
    claims completion the way a replay tool would; the evaluator must reject it
    on provenance, whatever it claims.
    """
    doc = copy.deepcopy(mapping(document, "bundle"))
    runs = {run["id"]: run for run in doc["runs"]}
    if source_run_id not in runs:
        raise ValueError(f"source run {source_run_id!r} is not in the bundle")
    source = runs[source_run_id]
    policy = doc["case"]["policy"]["sha256"]
    dep = deployment(corrected_mode, policy)
    run_id = run_id or f"replay-{corrected_mode}-of-{source_run_id}"
    if run_id in runs:
        raise ValueError(f"run {run_id!r} already exists")
    rows = []
    for row in source["trace"]:
        new = dict(row)
        new["executed_action"] = execute_action(row["intended_action"], dep)
        new["observation_source_run_id"] = source_run_id
        new["next_observation_source_run_id"] = source_run_id
        rows.append(new)
    doc["runs"].append(
        {
            "id": run_id,
            "case_id": source["case_id"],
            "plan_id": REPLAY_PLAN_ID,
            "condition_id": source["condition_id"],
            "seed": source["seed"],
            "evidence_origin": "invalid_replay_control",
            "candidate_sha256": producer_digest(dep),
            "started_at": source["started_at"],
            "process_status": "completed",
            "execution_mode": "recorded_observation_replay",
            "reset_id": source["reset_id"],
            "initial_state_sha256": source["initial_state_sha256"],
            "trace": rows,
            "artifacts": [],
            "measurement_status": "observed",
            "task_outcome": "completed",
            "constraint_violations": [],
            "costs": [
                {
                    "category": "replay_construction",
                    "value": None,
                    "unit": "s",
                    "missing_reason": "derived from retained rows; no simulator execution",
                }
            ],
            "derived_from": source_run_id,
            "control": "changed executed actions paired with the source run's recorded observations, "
            "future state and outcome; the claimed outcome is the replay's assertion, not a measurement",
        }
    )
    doc.setdefault("plans", []).append(
        {
            "id": REPLAY_PLAN_ID,
            "case_id": source["case_id"],
            "intervention": corrected_mode,
            "candidate_sha256": producer_digest(dep),
            "execution_mode": "recorded_observation_replay",
            "recompute": [],
            "retain": ["recorded observations", "recorded future state", "recorded outcome"],
            "reset": "none; reuses the source run",
        }
    )
    return doc
