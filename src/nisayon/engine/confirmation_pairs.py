"""Complete producer-assigned pairs, including unusable and unmatched evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator

from .diagnostics import ordinary_checks
from .io import digest


def run_observation(run: dict, predicates: dict) -> dict:
    """Original units and descriptive checks; no normalization or acceptance."""
    try:
        checks = ordinary_checks(run, predicates)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
        checks = {"invalid_reasons": [f"unreadable_measurements: {error}"], "evidence_gaps": []}
    configuration = run.get("configuration", {})
    deployment = configuration.get("deployment", {})
    try:
        content_hash = digest(run)
    except (ValueError, TypeError):
        content_hash = None
        checks.setdefault("invalid_reasons", []).append("non_finite_or_unserializable_record")
    return {
        "run_id": run.get("id"),
        "condition_id": run.get("condition_id"),
        "seed": run.get("seed"),
        "role": run.get("assignment_role"),
        "case_id": run.get("case_id"),
        "candidate_sha256": run.get("candidate_sha256"),
        "configuration_sha256": run.get("configuration_sha256"),
        "deployment": deployment,
        "controller": configuration.get("environment", {})
        .get("kwargs", {})
        .get("controller_configs"),
        "controller_target_convention": {
            "producer_field": "controller_target",
            "recorded": deployment.get("controller_target"),
            "omission": "legacy default; no explicit convention field"
            if "controller_target" not in deployment
            else None,
        },
        "policy_sha256": run.get("policy_sha256"),
        "code_sha256": run.get("code_sha256"),
        "code_git_head": run.get("code", {}).get("git_head"),
        "dependencies_sha256": run.get("dependencies_sha256"),
        "execution_identity_sha256": run.get("execution_identity_sha256"),
        "process_status": run.get("process_status"),
        "measurement_status": run.get("measurement_status"),
        "recorded_task_outcome": run.get("task_outcome", "unknown"),
        "measured_task_outcome": checks.get("task", "unmeasured"),
        "progress": {
            "value": checks.get("progress_gain_m"),
            "unit": "m",
            "boundary": "last minus first recorded post-action cube height",
            "status": checks.get("progress", "unmeasured"),
            "normalization": None,
        },
        "timing": checks.get("timing", "unmeasured"),
        "maximum_observation_age_s": checks.get("maximum_observation_age_s"),
        "executed_action_bounds": checks.get("executed_action_bounds", "unmeasured"),
        "recorded_constraint_violations": run.get("constraint_violations"),
        "ordinary_checks": checks,
        "reset": {
            "reset_id": run.get("reset_id"),
            "initial_state_sha256": run.get("initial_state_sha256"),
            "policy_reset": run.get("policy_reset"),
            "policy_state_reset": run.get("policy_state_reset"),
            "prefix_run": run.get("prefix_run"),
            "claim_limit": "Recorded state and reset evidence do not establish complete hidden-state equality.",
        },
        "started_at": run.get("started_at"),
        "ended_at": run.get("ended_at"),
        "costs": run.get("costs"),
        "cost_parent_run_id": run.get("cost_parent_run_id"),
        "artifacts": run.get("artifacts", []),
        "record_path": f"{run.get('id')}.run.json",
        "record_content_sha256": content_hash,
    }


def assigned_pairs(
    bundle: dict, protocol: dict, identity: dict, *, binding_issues: list[str]
) -> dict:
    """Use declared ordered membership, never incidental run-file order."""
    assignments = protocol.get("assignments", [])
    counts = Counter(a.get("run_id") for a in assignments)
    assigned = defaultdict(list)
    for index, assignment in enumerate(assignments):
        assigned[assignment.get("run_id")].append(index)
    by_id = defaultdict(list)
    observations = []
    for index, run in enumerate(bundle.get("runs", [])):
        by_id[run.get("id")].append(index)
        observations.append(run_observation(run, protocol["predicates"]))
    confirmation = bundle.get("confirmation") or {}
    conditions = protocol.get("condition_ids", [])
    refs, candidates = (
        confirmation.get("reference_run_ids", []),
        confirmation.get("candidate_run_ids", []),
    )
    global_issues = list(binding_issues)
    if len(set(conditions)) != len(conditions):
        global_issues.append("duplicate_frozen_conditions")
    if confirmation.get("condition_ids") != conditions:
        global_issues.append("confirmation_condition_order_differs_from_protocol")
    if len(refs) != len(conditions) or len(candidates) != len(conditions):
        global_issues.append("incomplete_or_extra_declared_pair_membership")
    if bundle.get("assignments") != assignments:
        global_issues.append("bundle_assignments_differ_from_protocol")
    if bundle.get("arm") != identity["arm"]:
        global_issues.append("wrong_bundle_arm")
    if confirmation.get("candidate_sha256") != identity["candidate_sha256"]:
        global_issues.append("wrong_confirmation_candidate")
    reproduction = confirmation.get("reproduction") or {}
    specs = [
        (
            "reproduction",
            c,
            reproduction.get("reference_run_id"),
            reproduction.get("candidate_run_id"),
        )
        for c in protocol.get("reproduction_condition_ids", [])
    ] + [
        (
            "fresh_development_confirmation",
            condition,
            refs[index] if index < len(refs) else None,
            candidates[index] if index < len(candidates) else None,
        )
        for index, condition in enumerate(conditions)
    ]
    used = Counter(run_id for _, _, ref, cand in specs for run_id in (ref, cand) if run_id)
    pairs = []
    for index, (role, condition, reference_id, candidate_id) in enumerate(specs):
        issues = list(global_issues)
        if role == "reproduction" and reproduction.get("condition_id") != condition:
            issues.append("wrong_reproduction_condition")
        members = {}
        for side, run_id, mode in (
            ("reference", reference_id, "reference"),
            ("candidate", candidate_id, "correction"),
        ):
            assignment_indices = assigned[run_id]
            record_indices = by_id[run_id]
            members[side] = {
                "run_id": run_id,
                "assignment_indices": assignment_indices,
                "record_indices": record_indices,
            }
            if counts[run_id] != 1:
                issues.append(f"{side}_assignment_count_{counts[run_id]}")
            if len(record_indices) != 1:
                issues.append(f"{side}_record_count_{len(record_indices)}")
            if used[run_id] != 1:
                issues.append(f"{side}_member_reused_across_pairs")
            for assignment_index in assignment_indices:
                assignment = assignments[assignment_index]
                if assignment.get("role") != role or assignment.get("mode") != mode:
                    issues.append(f"{side}_wrong_assignment_role_or_mode")
                for record_index in record_indices:
                    run = bundle["runs"][record_index]
                    observation = observations[record_index]
                    if any(
                        run.get(field) != expected
                        for field, expected in {
                            "condition_id": condition,
                            "case_id": f"{identity['case_id']}-{identity['arm']}",
                            "candidate_sha256": assignment.get("candidate_sha256"),
                            "seed": assignment.get("seed"),
                            "assignment_role": role,
                            "plan_id": mode,
                        }.items()
                    ):
                        issues.append(f"{side}_run_identity_mismatch")
                    checks = observation["ordinary_checks"]
                    if checks.get("invalid_reasons") or checks.get("evidence_gaps"):
                        issues.append(f"{side}_invalid_or_incomplete_measurements")
                    if observation["recorded_task_outcome"] != observation["measured_task_outcome"]:
                        issues.append(f"{side}_outcome_disagrees_with_measurement")
        pair_identity = {**identity, "condition_id": condition, "role": role, "ordinal": index}
        pairs.append(
            {
                "identity": pair_identity,
                "id": digest(pair_identity),
                **members,
                "state": "complete" if not issues else "incomplete_or_invalid",
                "issues": sorted(set(issues)),
            }
        )
    return {
        "assignments": assignments,
        "observations": observations,
        "pairs": pairs,
        "unpaired_assignment_indices": [
            i for i, a in enumerate(assignments) if a.get("run_id") not in used
        ],
        "unexpected_record_indices": [
            i for i, r in enumerate(bundle.get("runs", [])) if r.get("id") not in assigned
        ],
        "duplicate_assignment_ids": [key for key, count in counts.items() if count > 1],
        "unmatched_declared_members": refs[len(conditions) :] + candidates[len(conditions) :],
    }


def iter_pairs(view: dict) -> Iterator[dict]:
    """Yield every assigned pair, including invalid ones, in frozen order."""
    for trial in view["trials"]:
        confirmation = trial.get("confirmation")
        if not confirmation:
            continue
        for pair in confirmation["pairs"]:
            yield {
                **pair,
                "source_state": trial["state"],
                "reference_observations": [
                    confirmation["observations"][i] for i in pair["reference"]["record_indices"]
                ],
                "candidate_observations": [
                    confirmation["observations"][i] for i in pair["candidate"]["record_indices"]
                ],
            }
