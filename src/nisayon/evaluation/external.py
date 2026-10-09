"""Field assessment of an execution record against the confirmation obligation.

An inventory (``nisayon.external-record.inventory.v1``) says what a record contains: the
source bytes and their digests, the producer's declarations, each episode's datasets with
shape, dtype, recording hook and role, the consistency checks that passed or failed on the
retained values, and direct measurements computed from those values. The assessment maps
every obligation of ``first-case-obligation-v0.2`` to what the inventory supports:
``measurable``, ``measurable_with_evaluator_predicate``, ``declared_only``, ``absent``,
``ambiguous`` or ``inapplicable``, each with the gap code the native evaluator would emit
and the smallest additional measurement that would close the gap. It never synthesizes a
missing field, never turns a producer declaration into a measurement, and never changes
the native rule: a native record is assessed by the same table and stays positive.

``inspect_robolab_hdf5`` builds the inventory for the pinned RoboLab sample when the
optional ``h5py`` dependency is installed (it is a transitive dependency of the simulation
extra); ``native_inventory`` builds one from a native ``nisayon.first_case.v1`` document.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from . import codes
from .schema import Malformed, load_json

INVENTORY_SCHEMA = "nisayon.external-record.inventory.v1"
ASSESSMENT_SCHEMA = "nisayon.external-record.assessment.v1"
NATIVE_RULE = "first-case-obligation-v0.2"
STATUSES = (
    "measurable",
    "measurable_with_evaluator_predicate",
    "declared_only",
    "absent",
    "ambiguous",
    "inapplicable",
)
# Roles a field can carry. Hooks name when the producer recorded it relative to a step.
ROLES = {
    "action": "the action applied at a step (pre-step)",
    "observation": "the observation the policy consumed at a step (pre-step)",
    "acquisition_stamps": "per-component acquisition clocks of the consumed observation",
    "simulation_clock": "simulation time per row",
    "state": "scene state after a step (post-step)",
    "initial_state": "scene state after reset, before the first step",
    "end_effector": "end-effector pose per step",
    "object_geometry": "object bounding boxes or centroids per step",
    "task_outcome_measurement": "the task predicate measured per row against a frozen threshold",
    "progress_measurement": "the progress quantity measured per row with a frozen minimum",
    "policy_state": "recurrent policy state or its digest per row and at reset",
    "identity_digest": "execution, code, dependency, policy and configuration digests per run",
    "artifact_manifest": "digest-bound manifest of the raw store",
    "frozen_candidate": "a frozen candidate, protocol and assignments for a confirmation",
    "condition": "the condition (seed) of each run and its role",
    "execution_mode": "full closed-loop rerun versus replay per run",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows_agree(fields: list[dict]) -> tuple[bool, str]:
    per_step = [f for f in fields if f.get("hook") in ("pre_step", "post_step") and f.get("shape")]
    rows = {f["shape"][0] for f in per_step}
    if not per_step:
        return False, "no per-step field"
    if len(rows) != 1:
        return False, f"per-step fields disagree on the row count: {sorted(rows)}"
    return True, f"{len(per_step)} per-step fields agree on {rows.pop()} rows"


def assess_inventory(inventory: dict) -> dict:
    """Map every obligation to what the inventory supports; see the module docstring."""
    if not isinstance(inventory, dict) or inventory.get("schema") != INVENTORY_SCHEMA:
        raise Malformed("inventory.schema", f"expected {INVENTORY_SCHEMA}")
    episodes = inventory.get("episodes") or []
    if not episodes:
        raise Malformed("inventory.episodes", "no episode")
    declarations = inventory.get("producer_declarations") or {}
    source = inventory.get("source") or {}
    rejections: list[dict] = []
    findings: list[dict] = []
    if not source.get("sha256"):
        findings.append(
            {"code": "source_unbound", "detail": "the record's bytes are not bound by a digest"}
        )
    episode = episodes[0]
    if len(episodes) > 1:
        findings.append(
            {
                "code": "several_episodes",
                "detail": f"{len(episodes)} episodes; the assessment reads the first, "
                f"{episode.get('id')!r}, and keeps membership explicit",
            }
        )
    fields = episode.get("fields") or []
    roles = {f.get("role") for f in fields}
    by_role = {role: [f for f in fields if f.get("role") == role] for role in roles}
    agree, detail = _rows_agree(fields)
    if not agree and fields:
        rejections.append({"code": "row_count_inconsistent", "detail": detail})
    declared_rows = episode.get("rows")
    if agree and declared_rows is not None:
        observed = next(f["shape"][0] for f in fields if f.get("hook") in ("pre_step", "post_step"))
        if observed != declared_rows:
            rejections.append(
                {
                    "code": "row_count_inconsistent",
                    "detail": f"the episode declares {declared_rows} rows; the fields hold {observed}",
                }
            )
    for check in inventory.get("consistency") or []:
        if check.get("status") == "inconsistent":
            rejections.append({"code": "record_inconsistent", "detail": check.get("detail")})
    initial_rows = [f for f in by_role.get("initial_state", []) if f.get("shape")]
    initial_axis = {f["shape"][0] for f in initial_rows}
    initial_identical = inventory.get("direct_measurements", {}).get("initial_state_rows_identical")
    measured = inventory.get("direct_measurements") or {}
    consistency = inventory.get("consistency") or []

    def row(obligation: str, status: str, evidence: str, gap: str | None, smallest: str) -> dict:
        assert status in STATUSES
        return {
            "obligation": obligation,
            "status": status,
            "evidence": evidence,
            "gap_code": gap,
            "smallest_additional_measurement": smallest,
        }

    table: list[dict] = []
    # Task outcome.
    if "task_outcome_measurement" in roles:
        table.append(
            row(
                "task_outcome",
                "measurable",
                "per-row task measurement against a frozen predicate",
                None,
                "none",
            )
        )
    elif "state" in roles or "object_geometry" in roles:
        success = declarations.get("success")
        table.append(
            row(
                "task_outcome",
                "measurable_with_evaluator_predicate",
                f"producer declares success={success!r}; object and robot states are retained "
                "per step, so an evaluator-added geometric predicate can be computed and is "
                "reported as not preregistered; the producer's own conditional (contact, "
                "gripper detached) is not recomputable from retained fields",
                codes.PREDICATE_NOT_PREREGISTERED,
                "a frozen outcome predicate over retained fields, plus the contact and "
                "gripper-detachment measurements the producer's conditional uses",
            )
        )
    else:
        table.append(
            row(
                "task_outcome",
                "declared_only" if "success" in declarations else "absent",
                f"success declared: {declarations.get('success')!r}; no per-step state",
                codes.PREDICATE_UNMEASURABLE,
                "per-step object and robot states with a frozen predicate",
            )
        )
    # Progress.
    if "progress_measurement" in roles:
        table.append(
            row("progress", "measurable", "frozen progress minimum measured per row", None, "none")
        )
    elif "state" in roles or "object_geometry" in roles:
        table.append(
            row(
                "progress",
                "absent",
                "object trajectories are retained, so a progress quantity could be defined; "
                "no frozen progress minimum or activation tolerance exists",
                codes.PREREGISTRATION_MISSING,
                "a producer-frozen progress quantity and minimum gain",
            )
        )
    else:
        table.append(
            row(
                "progress",
                "absent",
                "no progress quantity",
                codes.PREREGISTRATION_MISSING,
                "a frozen progress quantity",
            )
        )
    # Action constraints.
    actions = by_role.get("action", [])
    if actions:
        declared_limit = declarations.get("action_clip")
        bounds = measured.get("action_bounds")
        table.append(
            row(
                "constraints_action",
                "measurable",
                f"actions {actions[0].get('shape')} {actions[0].get('dtype')}; dimension and "
                f"range measurable ({bounds}); declared limit: {declared_limit!r}",
                None
                if declared_limit
                else codes.CONSTRAINT_VIOLATED.replace("violated", "undeclared"),
                "none" if declared_limit else "a declared action bound to check the range against",
            )
        )
    else:
        table.append(
            row(
                "constraints_action",
                "absent",
                "no action record",
                codes.PREDICATE_UNMEASURABLE,
                "the applied actions per step",
            )
        )
    # Step period.
    if "simulation_clock" in roles:
        table.append(
            row("constraints_step_period", "measurable", "simulation clock per row", None, "none")
        )
    else:
        period = declarations.get("step_period_s")
        table.append(
            row(
                "constraints_step_period",
                "declared_only" if period is not None else "absent",
                f"step period {period!r} s derived from configuration (dt × decimation); no per-row clock",
                codes.PREDICATE_UNMEASURABLE,
                "a simulation clock per row",
            )
        )
    # Observation timing.
    if "acquisition_stamps" in roles:
        table.append(
            row(
                "timing_observation_age",
                "measurable",
                "per-component acquisition stamps on consumed observations",
                None,
                "none",
            )
        )
    else:
        table.append(
            row(
                "timing_observation_age",
                "absent",
                "no acquisition stamps; the age of what the policy consumed is unknown",
                codes.TIMING_UNMEASURED,
                "acquisition and consumption stamps per observation component",
            )
        )
    # Observation record.
    if "observation" in roles:
        table.append(
            row(
                "observation_record",
                "measurable",
                "the consumed observation is retained per row",
                None,
                "none",
            )
        )
    else:
        table.append(
            row(
                "observation_record",
                "absent",
                "the observation the policy consumed is not retained (image observations were "
                "dropped by the producer's export), so the observation-to-action chain cannot be checked",
                None,
                "the consumed observation, or its digest and acquisition stamp, per row",
            )
        )
    # Reset evidence for recurrent policy state.
    if "policy_state" in roles:
        table.append(
            row(
                "reset_evidence",
                "measurable",
                "policy state digests per row and at reset",
                None,
                "none",
            )
        )
    else:
        table.append(
            row(
                "reset_evidence",
                "absent",
                f"no policy state or chunk schedule; policy declared as {declarations.get('policy')!r}",
                codes.RESET_EVIDENCE_INCOMPLETE,
                "a digest of the policy's recurrent state and action-chunk position at reset and per step",
            )
        )
    # Initial state.
    if initial_rows:
        if len(initial_axis) != 1:
            table.append(
                row(
                    "initial_state",
                    "ambiguous",
                    f"leading axes differ: {sorted(initial_axis)}",
                    codes.RESET_CONDITION_MISMATCH,
                    "one initial-state row per reset event, labelled",
                )
            )
            rejections.append(
                {
                    "code": "initial_state_ambiguous",
                    "detail": "initial-state fields disagree on their leading axis",
                }
            )
        elif initial_axis == {1}:
            table.append(
                row("initial_state", "measurable", "one post-reset scene state", None, "none")
            )
        elif initial_identical is True:
            table.append(
                row(
                    "initial_state",
                    "measurable",
                    f"{initial_axis.pop()} identical rows on the leading axis (repeated post-reset "
                    "records concatenated by the writer); the pinned reader restores row 0",
                    None,
                    "none for this record; a reader must reject rows that differ",
                )
            )
        else:
            table.append(
                row(
                    "initial_state",
                    "ambiguous",
                    f"{initial_axis.pop()} rows on the leading axis that are not identical; which "
                    "reset the episode started from is not determined",
                    codes.RESET_CONDITION_MISMATCH,
                    "one labelled initial-state row per reset event",
                )
            )
            rejections.append(
                {"code": "initial_state_ambiguous", "detail": "initial-state rows differ"}
            )
    else:
        table.append(
            row(
                "initial_state",
                "absent",
                "no initial state",
                codes.RESET_CONDITION_MISMATCH,
                "the post-reset scene state",
            )
        )
    # Identity.
    if "identity_digest" in roles:
        table.append(
            row(
                "identity",
                "measurable",
                "per-run execution, code, dependency, policy and configuration digests",
                None,
                "none",
            )
        )
    else:
        named = {
            k: declarations.get(k)
            for k in ("isaaclab_version", "isaacsim_version", "policy")
            if k in declarations
        }
        table.append(
            row(
                "identity",
                "declared_only" if named else "absent",
                f"producer names {named}; no digest binds the policy checkpoint, code or dependencies",
                codes.IDENTITY_UNBOUND,
                "digests of the policy checkpoint, simulator build and configuration bound to each run",
            )
        )
    # Artifact manifest.
    if "artifact_manifest" in roles:
        table.append(
            row(
                "artifact_manifest",
                "measurable",
                "digest-bound manifest of the raw store",
                None,
                "none",
            )
        )
    else:
        table.append(
            row(
                "artifact_manifest",
                "absent",
                "the producer ships no manifest; the source packet binds the file digests externally"
                if source.get("sha256")
                else "no manifest and no digest",
                codes.ARTIFACT_MANIFEST_MISSING,
                "a producer-written manifest of every retained file with digests",
            )
        )
    # Frozen candidate, protocol and confirmation.
    if "frozen_candidate" in roles:
        table.append(
            row(
                "frozen_candidate_and_protocol",
                "measurable",
                "frozen candidate, protocol and assignments retained",
                None,
                "none",
            )
        )
    else:
        table.append(
            row(
                "frozen_candidate_and_protocol",
                "inapplicable",
                "a single episode; no working/changed pair, no candidate, no assignments",
                codes.CONFIRMATION_MISSING,
                "a working and a changed deployment with a frozen candidate and paired fresh conditions",
            )
        )
    # Fresh conditions.
    if "condition" in roles:
        table.append(
            row(
                "fresh_conditions",
                "measurable",
                "conditions and roles per run; history checkable",
                None,
                "none",
            )
        )
    else:
        table.append(
            row(
                "fresh_conditions",
                "inapplicable",
                f"one episode on declared seed {declarations.get('seed')!r}; no assignment of conditions",
                codes.CONFIRMATION_MISSING,
                "assigned fresh conditions with reference and candidate runs",
            )
        )
    # Intervention validity.
    if "execution_mode" in roles:
        table.append(
            row(
                "intervention_validity",
                "measurable",
                "execution mode per run; replay controls checkable",
                None,
                "none",
            )
        )
    else:
        table.append(
            row(
                "intervention_validity",
                "inapplicable",
                "no intervention; the producer documents open-loop replay of recorded actions, "
                "which is legitimate for its purpose and cannot validate a changed action against "
                "the recorded future",
                None,
                "a full closed-loop rerun after any changed action",
            )
        )
    # Internal consistency of retained values.
    if consistency and all(c.get("status") == "consistent" for c in consistency):
        table.append(
            row(
                "raw_trace_consistency",
                "measurable",
                "; ".join(str(c.get("check")) for c in consistency),
                None,
                "none",
            )
        )
    elif consistency:
        table.append(
            row(
                "raw_trace_consistency",
                "measurable",
                "checks ran; see rejections",
                codes.MEASUREMENT_INCONSISTENT,
                "none",
            )
        )
    else:
        table.append(
            row(
                "raw_trace_consistency",
                "absent",
                "no consistency check ran",
                None,
                "row-count and value-range checks",
            )
        )

    counts = {status: sum(1 for r in table if r["status"] == status) for status in STATUSES}
    positive = [r["obligation"] for r in table if r["status"].startswith("measurable")]
    return {
        "schema": ASSESSMENT_SCHEMA,
        "assessed_at": datetime.now(UTC).isoformat(),
        "native_rule": f"{NATIVE_RULE} unchanged; an unsupported foreign field never relaxes or tightens it",
        "producer": inventory.get("producer"),
        "source": source,
        "episode": episode.get("id"),
        "rows": declared_rows,
        "declared_success": declarations.get("success"),
        "rejected": bool(rejections),
        "rejections": rejections,
        "findings": findings,
        "obligations": table,
        "counts": counts,
        "positive_observables": positive,
        "repair_comparison_applicable": "frozen_candidate" in roles and "condition" in roles,
        "reading": (
            "a valid native record: every obligation is measurable"
            if all(r["status"] == "measurable" for r in table)
            else "record portability evidence only: usable measurements are listed per obligation; "
            "an upstream successful episode is not a repair comparison, a backend qualification or "
            "an independently verified success"
        ),
    }


def render_assessment(assessment: dict) -> str:
    lines = [
        f"External record assessment: {'REJECTED' if assessment['rejected'] else 'assessed'} · "
        f"producer {assessment.get('producer')} · episode {assessment.get('episode')} · "
        f"rows {assessment.get('rows')} · declared success {assessment.get('declared_success')!r}",
        f"Rule: {assessment['native_rule']}",
    ]
    for item in assessment["rejections"]:
        lines.append(f"  rejection {item['code']}: {item['detail']}")
    for item in assessment["findings"]:
        lines.append(f"  finding {item['code']}: {item['detail']}")
    lines.append(f"  {'obligation':<32}{'status':<38}gap code / smallest additional measurement")
    for item in assessment["obligations"]:
        lines.append(
            f"  {item['obligation']:<32}{item['status']:<38}{item['gap_code'] or '-'} / "
            f"{item['smallest_additional_measurement']}"
        )
        lines.append(f"      evidence: {item['evidence']}")
    lines.append(f"Counts: {assessment['counts']}")
    lines.append(f"Repair comparison applicable: {assessment['repair_comparison_applicable']}")
    lines.append(f"Reading: {assessment['reading']}")
    return "\n".join(lines)


def native_inventory(document: dict, *, path: str | None = None) -> dict:
    """An inventory of a native ``nisayon.first_case.v1`` document, by the same field roles."""
    runs = document.get("runs") or []
    if not runs:
        raise Malformed("document.runs", "no run")
    first = runs[0]
    trace = first.get("trace") or []
    row0 = trace[0] if trace else {}
    fields: list[dict] = []

    def field(
        name: str, role: str, hook: str, shape: list | None = None, dtype: str = "json"
    ) -> None:
        fields.append({"path": name, "role": role, "hook": hook, "shape": shape, "dtype": dtype})

    rows = len(trace)
    if "executed_action" in row0:
        field(
            "trace[].executed_action",
            "action",
            "pre_step",
            [rows, len(row0["executed_action"])],
            "float",
        )
    if "observation_sha256" in row0:
        field("trace[].observation_sha256", "observation", "pre_step", [rows])
    if isinstance(row0.get("observation_capture"), dict):
        field("trace[].observation_capture.components", "acquisition_stamps", "pre_step", [rows])
    if "action_sim_time_s" in row0 and "next_sim_time_s" in row0:
        field("trace[].action_sim_time_s", "simulation_clock", "pre_step", [rows])
    if "state_after_sha256" in row0:
        field("trace[].state_after_sha256", "state", "post_step", [rows])
    if first.get("initial_state_sha256"):
        field("run.initial_state_sha256", "initial_state", "post_reset", [1])
    if "cube_height_m" in row0 and "task_success" in row0:
        field("trace[].task_success", "task_outcome_measurement", "post_step", [rows])
        field("trace[].cube_height_m", "progress_measurement", "post_step", [rows])
    if "policy_state_sha256" in row0:
        field("trace[].policy_state_sha256", "policy_state", "pre_step", [rows])
    if first.get("execution_identity_sha256") and first.get("policy_sha256"):
        field("run.execution_identity_sha256", "identity_digest", "per_run", [len(runs)])
    if isinstance(document.get("artifact_manifest"), dict | list):
        field("artifact_manifest", "artifact_manifest", "per_record")
    if isinstance(document.get("confirmation"), dict) and document["confirmation"].get(
        "candidate_sha256"
    ):
        field("confirmation", "frozen_candidate", "per_record")
    if first.get("condition_id") is not None and first.get("assignment_role") is not None:
        field("run.condition_id", "condition", "per_run", [len(runs)])
    if first.get("execution_mode"):
        field("run.execution_mode", "execution_mode", "per_run", [len(runs)])
    consistency = [
        {
            "check": "every run's trace has rows",
            "status": "consistent" if all(r.get("trace") for r in runs) else "inconsistent",
            "detail": f"{len(runs)} runs",
        }
    ]
    return {
        "schema": INVENTORY_SCHEMA,
        "producer": "nisayon",
        "source": {
            "path": path,
            "sha256": None,
            "note": "native document; digests are inside the record",
        },
        "producer_declarations": {
            "schema": document.get("schema"),
            "action_clip": "frozen case predicates declare the executed action bound"
            if isinstance((document.get("case") or {}).get("predicates"), dict)
            else None,
        },
        "episodes": [
            {
                "id": first.get("id"),
                "rows": rows,
                "success_declared": None,
                "fields": fields,
                "note": f"first of {len(runs)} runs; the native evaluator reads every run",
            }
        ],
        "consistency": consistency,
        "direct_measurements": {},
        "inspection": {
            "tool": "nisayon.evaluation.external.native_inventory",
            "at": datetime.now(UTC).isoformat(),
            "scope": "field roles read from the document; no evaluation, no physics",
        },
    }


ROBOLAB_ROLES = (
    ("actions", "action", "pre_step"),
    ("states/", "state", "post_step"),
    ("initial_state/", "initial_state", "post_reset"),
    ("ee_pose/", "end_effector", "post_step"),
    ("bbox/", "object_geometry", "post_step"),
    ("obs/", "observation", "pre_step"),
)


def inspect_robolab_hdf5(
    path: Path,
    *,
    env_cfg: Path | None = None,
    manifest: Path | None = None,
    upstream: dict | None = None,
    episode: str = "demo_0",
) -> dict:
    """Build the inventory of a RoboLab recording from its bytes (needs ``h5py``).

    Field roles and hooks follow the pinned recorders (``robolab/core/events/basic_recorders.py``
    and Isaac Lab 2.2.0 ``recorders.py``): actions pre-step, states, end-effector pose and
    bounding boxes post-step, initial state post-reset, concatenated on a leading axis per
    reset event by ``EpisodeData.add``. Nothing is squeezed or reassigned.
    """
    try:
        import h5py
        import numpy as np
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise RuntimeError("h5py and numpy are needed to inspect an HDF5 record") from error
    path = Path(path)
    fields: list[dict] = []
    measured: dict = {}
    consistency: list[dict] = []
    declarations: dict = {}
    with h5py.File(path, "r") as handle:
        data = handle["data"]
        declarations.update(
            {k: (v.item() if hasattr(v, "item") else v) for k, v in data.attrs.items()}
        )
        if episode not in data:
            raise Malformed("episode", f"{episode!r} not in the file")
        demo = data[episode]
        demo_attrs = {k: (v.item() if hasattr(v, "item") else v) for k, v in demo.attrs.items()}
        declarations["success"] = demo_attrs.get("success")
        declarations["num_samples"] = demo_attrs.get("num_samples")
        episodes = sorted(k for k in data.keys())

        def visit(name: str, obj) -> None:
            if not isinstance(obj, h5py.Dataset):
                return
            role, hook = None, None
            for prefix, prefix_role, prefix_hook in ROBOLAB_ROLES:
                if name == prefix or name.startswith(prefix):
                    role, hook = prefix_role, prefix_hook
                    break
            fields.append(
                {
                    "path": name,
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                    "compression": obj.compression,
                    "role": role,
                    "hook": hook,
                    "frame": (
                        "env-local positions, world-frame orientations and velocities"
                        if role in ("state", "initial_state")
                        else "position and orientation in the robot-root frame, linear and "
                        "angular velocities on world axes (pinned PostStepEndEffectorPoseRecorder "
                        "docstring; docs/data.md describes env-local position and world "
                        "orientation, a documentation discrepancy retained as such)"
                        if role == "end_effector"
                        else "millimetres (int16) for corners, metres (float16) for centroids"
                        if role == "object_geometry"
                        else None
                    ),
                }
            )

        demo.visititems(visit)
        actions = demo["actions"][()]
        measured["action_bounds"] = {
            "min": [round(float(v), 6) for v in actions.min(0)],
            "max": [round(float(v), 6) for v in actions.max(0)],
        }
        measured["action_nan"] = bool(np.isnan(actions).any())
        measured["gripper_column_values"] = sorted(float(v) for v in np.unique(actions[:, -1]))
        initial = {}
        states0 = {}
        for name in ("articulation/robot/joint_position", "rigid_object/rubiks_cube/root_pose"):
            key_i, key_s = f"initial_state/{name}", f"states/{name}"
            if key_i in demo and key_s in demo:
                initial[name] = demo[key_i][()]
                states0[name] = demo[key_s][()][0]
        identical = all(
            bool(np.array_equal(value[0], value[i]))
            for value in initial.values()
            for i in range(1, value.shape[0])
        )
        measured["initial_state_rows_identical"] = identical
        measured["initial_state_leading_axis"] = sorted(
            {int(f["shape"][0]) for f in fields if f["role"] == "initial_state"}
        )
        measured["initial_vs_first_post_step_max_abs"] = {
            name: round(float(np.abs(initial[name][0] - states0[name]).max()), 6)
            for name in initial
        }
        objects = [
            f["path"].split("/")[2]
            for f in fields
            if f["path"].startswith("states/rigid_object/") and f["path"].endswith("root_pose")
        ]
        if "bowl" in objects:
            bowl = demo["states/rigid_object/bowl/root_pose"][()]
            distances = {}
            for name in objects:
                if name in ("bowl", "table"):
                    continue
                pose = demo[f"states/rigid_object/{name}/root_pose"][()]
                distances[name] = {
                    "initial_m": round(float(np.linalg.norm(pose[0, :3] - bowl[0, :3])), 6),
                    "final_m": round(float(np.linalg.norm(pose[-1, :3] - bowl[-1, :3])), 6),
                    "final_z_minus_bowl_z_m": round(float(pose[-1, 2] - bowl[-1, 2]), 6),
                }
            measured["object_to_bowl_distance"] = distances
            if "bbox/bbox_mm/bowl" in demo:
                corners = demo["bbox/bbox_mm/bowl"][()][-1].astype(float) / 1000.0
                lo, hi = corners.min(0), corners.max(0)
                inside = {}
                for name in distances:
                    centroid = demo[f"bbox/centroid/{name}"][()][-1].astype(float)
                    inside[name] = bool(
                        lo[0] <= centroid[0] <= hi[0]
                        and lo[1] <= centroid[1] <= hi[1]
                        and lo[2] <= centroid[2] <= hi[2] + 0.05
                    )
                measured["final_centroid_inside_bowl_obb_xy_and_below_rim_plus_5cm"] = inside
                measured["bowl_obb_final_m"] = {
                    "min": [round(float(v), 4) for v in lo],
                    "max": [round(float(v), 4) for v in hi],
                }
        per_step_rows = {f["shape"][0] for f in fields if f["hook"] in ("pre_step", "post_step")}
        consistency.append(
            {
                "check": "per-step datasets agree on the row count",
                "status": "consistent" if len(per_step_rows) == 1 else "inconsistent",
                "detail": f"rows {sorted(per_step_rows)}",
            }
        )
        rows = per_step_rows.pop() if len(per_step_rows) == 1 else None
        consistency.append(
            {
                "check": "num_samples and data.total equal the action rows",
                "status": "consistent"
                if rows is not None
                and declarations.get("num_samples") == rows == declarations.get("total")
                else "inconsistent",
                "detail": f"num_samples {declarations.get('num_samples')}, total {declarations.get('total')}, rows {rows}",
            }
        )
        consistency.append(
            {
                "check": "actions carry no NaN",
                "status": "inconsistent" if measured["action_nan"] else "consistent",
                "detail": "float32 actions",
            }
        )
    sidecars = []
    if env_cfg is not None and Path(env_cfg).is_file():
        cfg = json.loads(Path(env_cfg).read_text())
        sim = cfg.get("sim") or {}
        declarations["seed"] = cfg.get("seed")
        declarations["sim_dt_s"] = sim.get("dt")
        declarations["decimation"] = cfg.get("decimation")
        if isinstance(sim.get("dt"), int | float) and isinstance(cfg.get("decimation"), int):
            declarations["step_period_s"] = round(sim["dt"] * cfg["decimation"], 9)
        declarations["num_envs"] = cfg.get("num_envs")
        declarations["episode_length_s"] = cfg.get("episode_length_s")
        declarations["instruction"] = cfg.get("instruction")
        body = (cfg.get("actions") or {}).get("body") or {}
        declarations["action_clip"] = body.get("clip")
        declarations["action_terms"] = sorted((cfg.get("actions") or {}).keys())
        success = (cfg.get("terminations") or {}).get("success") or {}
        declarations["success_conditional"] = {
            "func": success.get("func"),
            "params": success.get("params"),
        }
        declarations["recorders"] = sorted(
            k
            for k, v in (cfg.get("recorders") or {}).items()
            if isinstance(v, dict) and v.get("class_type")
        )
        sidecars.append(
            {
                "path": Path(env_cfg).name,
                "bytes": Path(env_cfg).stat().st_size,
                "sha256": _sha256(Path(env_cfg)),
                "role": "environment configuration",
            }
        )
    upstream = dict(upstream or {})
    if manifest is not None and Path(manifest).is_file():
        packet = load_json(Path(manifest))
        if isinstance(packet, dict):
            upstream.setdefault("upstream", packet.get("upstream"))
            upstream.setdefault("commit", packet.get("commit"))
            upstream.setdefault("license_observed", packet.get("license_observed"))
            sidecars.append(
                {
                    "path": Path(manifest).name,
                    "bytes": Path(manifest).stat().st_size,
                    "sha256": _sha256(Path(manifest)),
                    "role": "source packet manifest",
                }
            )
    return {
        "schema": INVENTORY_SCHEMA,
        "producer": "robolab",
        "source": {
            **upstream,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "sidecars": sidecars,
        },
        "producer_declarations": declarations,
        "episodes": [
            {
                "id": episode,
                "rows": int(declarations.get("num_samples") or 0),
                "success_declared": declarations.get("success"),
                "fields": fields,
                "all_episodes": episodes,
            }
        ],
        "field_semantics_source": (
            "robolab/core/events/basic_recorders.py and examples/episodes.py at "
            f"{upstream.get('commit')}; Isaac Lab 2.2.0 recorder_manager.py, recorders.py and "
            "episode_data.py"
        ),
        "consistency": consistency,
        "direct_measurements": measured,
        "inspection": {
            "tool": f"h5py {__import__('h5py').__version__}",
            "at": datetime.now(UTC).isoformat(),
            "scope": "read-only inspection of retained values; no simulation, policy inference or evaluation",
        },
    }


EXTERNAL_RECORD_SCHEMA = "nisayon.external-record.v1"
# The execution lane's reader names each field's semantic and alignment; these map onto the
# roles and hooks the assessment reads. Anything else stays unmapped and is listed.
EXTERNAL_SEMANTICS = {
    ("action_manager_input", "pre_step_action_manager_input"): ("action", "pre_step"),
    ("recorded_scene_state", "post_step"): ("state", "post_step"),
    ("recorded_scene_state", "reset_recorder_emission"): ("initial_state", "post_reset"),
    ("recorded_camera_pose", "reset_recorder_emission"): ("initial_state", "post_reset"),
    ("recorded_end_effector_state", "post_step"): ("end_effector", "post_step"),
    ("quantized_bounding_box_corners", "post_step"): ("object_geometry", "post_step"),
    ("bounding_box_centroid", "post_step"): ("object_geometry", "post_step"),
    ("policy_observation", "pre_step"): ("observation", "pre_step"),
}


def inventory_from_external_record(document: dict) -> dict:
    """An inventory from the execution lane's ``nisayon.external-record.v1`` document.

    Works on the full import and on its compact summary (values removed): shapes, dtypes,
    the reader's mapping semantics, producer attributes and the initial-state emission
    analysis are enough for the obligation table. Direct measurements that need values
    are reported only when the values are present.
    """
    if not isinstance(document, dict) or document.get("schema") != EXTERNAL_RECORD_SCHEMA:
        raise Malformed("document.schema", f"expected {EXTERNAL_RECORD_SCHEMA}")
    episodes_in = document.get("episodes") or []
    if not episodes_in:
        raise Malformed("document.episodes", "no episode")
    data_attributes = document.get("data_attributes") or {}
    configuration = document.get("producer_configuration") or {}
    declarations: dict = {
        key: data_attributes.get(key)
        for key in ("isaaclab_version", "isaacsim_version", "policy", "recorded_at", "total")
        if key in data_attributes
    }
    if isinstance(configuration.get("sim_dt"), int | float) and isinstance(
        configuration.get("decimation"), int
    ):
        declarations["sim_dt_s"] = configuration["sim_dt"]
        declarations["decimation"] = configuration["decimation"]
        declarations["step_period_s"] = round(
            configuration["sim_dt"] * configuration["decimation"], 9
        )
    declarations["num_envs"] = configuration.get("num_envs")
    body = (configuration.get("actions") or {}).get("body") or {}
    declarations["action_clip"] = body.get("clip")
    declarations["action_terms"] = sorted((configuration.get("actions") or {}).keys())
    declarations["reader_missing_obligations"] = document.get("missing_obligations")
    episodes = []
    consistency: list[dict] = []
    measured: dict = {}
    unmapped: list[str] = []
    for episode in episodes_in:
        attributes = episode.get("attributes") or {}
        fields_in = episode.get("fields") or {}
        items = fields_in.items() if isinstance(fields_in, dict) else enumerate(fields_in)
        fields = []
        for key, field in items:
            mapping = field.get("mapping") or {}
            role, hook = EXTERNAL_SEMANTICS.get(
                (mapping.get("semantic"), mapping.get("alignment")), (None, None)
            )
            if role is None:
                unmapped.append(str(field.get("source_dataset") or key))
            fields.append(
                {
                    "path": str(field.get("source_dataset") or key)
                    .removeprefix("/data/")
                    .removeprefix(f"{episode.get('id')}/"),
                    "shape": list(field.get("shape") or []),
                    "dtype": field.get("dtype"),
                    "compression": field.get("compression"),
                    "role": role,
                    "hook": hook,
                    "frame": mapping.get("frame"),
                    "reader_semantic": mapping.get("semantic"),
                    "reader_alignment": mapping.get("alignment"),
                    "finite": field.get("finite"),
                }
            )
        per_step_rows = {f["shape"][0] for f in fields if f["hook"] in ("pre_step", "post_step")}
        consistency.append(
            {
                "check": "per-step datasets agree on the row count",
                "status": "consistent" if len(per_step_rows) == 1 else "inconsistent",
                "detail": f"rows {sorted(per_step_rows)}",
            }
        )
        rows = per_step_rows.pop() if len(per_step_rows) == 1 else None
        consistency.append(
            {
                "check": "num_samples and data.total equal the action rows",
                "status": "consistent"
                if rows is not None
                and attributes.get("num_samples") == rows == data_attributes.get("total")
                else "inconsistent",
                "detail": f"num_samples {attributes.get('num_samples')}, "
                f"total {data_attributes.get('total')}, rows {rows}",
            }
        )
        finite = [f for f in fields if f.get("finite") is not None]
        consistency.append(
            {
                "check": "actions carry no NaN",
                "status": "consistent"
                if all(f["finite"] for f in finite if f["role"] == "action")
                else "inconsistent",
                "detail": "reader finite flag on the action field",
            }
        )
        for issue in document.get("mapping_issues") or []:
            consistency.append(
                {"check": "reader mapping issue", "status": "inconsistent", "detail": str(issue)}
            )
        initial = episode.get("initial_state") or {}
        if "rows_identical" in initial:
            measured["initial_state_rows_identical"] = bool(initial["rows_identical"])
        if initial.get("emission_counts"):
            measured["initial_state_leading_axis"] = sorted(
                {int(v) for v in initial["emission_counts"]}
            )
        action_field = next((f for f in fields if f["role"] == "action"), None)
        if action_field is not None and isinstance(fields_in, dict):
            source = next(
                (
                    v
                    for k, v in fields_in.items()
                    if (v.get("mapping") or {}).get("semantic") == "action_manager_input"
                ),
                None,
            )
            if source is not None:
                values = source.get("values")
                if isinstance(values, list) and values and isinstance(values[0], list):
                    width = len(values[0])
                    measured["action_bounds"] = {
                        "min": [round(min(row[i] for row in values), 6) for i in range(width)],
                        "max": [round(max(row[i] for row in values), 6) for i in range(width)],
                    }
                    measured["gripper_column_values"] = sorted({float(row[-1]) for row in values})
                elif source.get("minimum") is not None:
                    measured["action_bounds_overall"] = {
                        "min": source.get("minimum"),
                        "max": source.get("maximum"),
                        "note": "compact record: overall bounds only; per-column bounds need values",
                    }
        episodes.append(
            {
                "id": episode.get("id"),
                "rows": episode.get("action_rows") or attributes.get("num_samples"),
                "success_declared": attributes.get("success"),
                "fields": fields,
                "reader_alignment": episode.get("alignment"),
                "reader_initial_state": initial,
            }
        )
    declarations["success"] = episodes[0]["success_declared"]
    declarations["num_samples"] = (episodes_in[0].get("attributes") or {}).get("num_samples")
    source = document.get("source") or {}
    sources = document.get("mapping_sources") or {}
    return {
        "schema": INVENTORY_SCHEMA,
        "producer": "robolab"
        if str(document.get("format", "")).startswith("robolab")
        else document.get("format"),
        "source": {
            "upstream": "https://github.com/NVlabs/RoboLab"
            if sources.get("robolab_commit")
            else None,
            "commit": sources.get("robolab_commit"),
            "path": source.get("path"),
            "bytes": source.get("bytes"),
            "sha256": source.get("sha256"),
            "reader": document.get("reader"),
            "evidence_origin": document.get("evidence_origin"),
        },
        "producer_declarations": declarations,
        "episodes": episodes,
        "unmapped_fields": unmapped,
        "consistency": consistency,
        "direct_measurements": measured,
        "inspection": {
            "tool": "nisayon.evaluation.external.inventory_from_external_record",
            "at": datetime.now(UTC).isoformat(),
            "scope": "converted from the execution lane's reader output; no bytes re-read",
        },
    }


__all__ = [
    "ASSESSMENT_SCHEMA",
    "EXTERNAL_RECORD_SCHEMA",
    "INVENTORY_SCHEMA",
    "assess_inventory",
    "inspect_robolab_hdf5",
    "inventory_from_external_record",
    "native_inventory",
    "render_assessment",
]
