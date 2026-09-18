"""The finite confirmation obligation for the first case.

A frozen candidate, the case's declared predicates, fresh conditions, paired
reference and candidate runs, and every assigned outcome. Dropping a failure,
reusing a condition, or changing the candidate after the freeze voids the
confirmation; a valid failure rejects the candidate; a gap leaves it unresolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from . import codes
from .case import Case
from .checks import Finding, RunAssessment
from .schema import (
    Malformed,
    mapping,
    optional_string,
    parse_wall_time,
    require,
    sequence,
    string,
    string_list,
)

CONFIRMATION_SCHEMA = "nisayon.confirmation.v1"
CONDITION_ROLES = {"reproduction", "fresh"}
# Keys that must agree across every assigned run and with the frozen protocol.
BOUND_IDENTITY_KEYS = (
    "execution_identity_sha256",
    "code_git_head",
    "code_sha256",
    "lock_sha256",
    "sources_sha256",
    "dependencies_sha256",
    "policy_sha256",
)


@dataclass
class Pair:
    condition_id: str
    role: str
    reference_run_id: str
    candidate_run_id: str
    reference_outcome: str = "unknown"
    candidate_outcome: str = "unknown"
    reference_measurement: str = "unknown"
    candidate_measurement: str = "unknown"
    verdict: str = "gap"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ConfirmationAssessment:
    id: str | None = None
    protocol_id: str | None = None
    candidate_id: str | None = None
    candidate_digest: str | None = None
    frozen_at: datetime | None = None
    fresh_condition_ids: list[str] = field(default_factory=list)
    reproduction_condition_ids: list[str] = field(default_factory=list)
    consumed_condition_ids: list[str] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    assigned_candidate_run_ids: list[str] = field(default_factory=list)
    frozen_identity: dict = field(default_factory=dict)
    producer_protocol_digest: str | None = None

    def add(
        self, code: str, detail: str, *, run_id: str | None = None, path: str | None = None
    ) -> None:
        self.findings.append(Finding(code, detail, run_id=run_id, path=path))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "protocol_id": self.protocol_id,
            "protocol": {
                "id": self.protocol_id,
                "producer_protocol_sha256": self.producer_protocol_digest,
            },
            "candidate": {"id": self.candidate_id, "digest": self.candidate_digest},
            "frozen_at": self.frozen_at.isoformat() if self.frozen_at else None,
            "fresh_condition_ids": self.fresh_condition_ids,
            "reproduction_condition_ids": self.reproduction_condition_ids,
            "consumed_condition_ids": self.consumed_condition_ids,
            "pairs": [pair.to_dict() for pair in self.pairs],
            "findings": [f.to_dict() for f in self.findings],
        }


def _violates(a: RunAssessment, case: Case) -> bool:
    match case.failure_obligation:
        case "timing":
            return a.timing == "violated"
        case "progress":
            return a.progress == "lost"
        case "constraints":
            return a.constraints == "violated"
        case "reset":
            return a.reset_evidence.get("policy_state") == "carried"
        case _:
            return a.outcome == "failed"


def _prior_conditions(prior: list[object], case_id: str) -> set[str]:
    consumed: set[str] = set()
    for index, item in enumerate(prior):
        path = f"prior[{index}]"
        try:
            data = mapping(item, path)
            if string(data, "case_id", path) != case_id:
                continue
            for cindex, condition in enumerate(
                sequence(data.get("conditions", []), f"{path}.conditions")
            ):
                consumed.add(string(mapping(condition, f"{path}.conditions[{cindex}]"), "id", path))
        except Malformed:
            continue
    return consumed


def assess_confirmation(
    obj: object,
    case: Case,
    assessments: dict[str, RunAssessment],
    prior: list[object],
    extra_consumed: set[str] | frozenset[str] = frozenset(),
) -> ConfirmationAssessment:
    c = ConfirmationAssessment()
    path = "confirmation"
    try:
        data = mapping(obj, path)
        schema = string(data, "schema", path)
        if schema != CONFIRMATION_SCHEMA:
            raise Malformed(f"{path}.schema", f"expected {CONFIRMATION_SCHEMA}, found {schema!r}")
        c.id = string(data, "id", path)
        if string(data, "case_id", path) != case.id:
            c.add(codes.IDENTITY_MISMATCH, f"confirmation belongs to case {data['case_id']!r}")
        protocol = mapping(require(data, "protocol", path), f"{path}.protocol")
        c.protocol_id = string(protocol, "id", f"{path}.protocol")
        c.producer_protocol_digest = optional_string(
            protocol, "producer_protocol_sha256", f"{path}.protocol"
        )
        declared_digest = string(protocol, "predicates_digest", f"{path}.protocol")
        if declared_digest != case.predicates_digest:
            c.add(
                codes.PROTOCOL_MISMATCH,
                f"confirmation binds predicates {declared_digest}; the case declares {case.predicates_digest}",
            )
        candidate = mapping(require(data, "candidate", path), f"{path}.candidate")
        c.candidate_id = string(candidate, "id", f"{path}.candidate")
        c.candidate_digest = string(candidate, "digest", f"{path}.candidate")
        c.frozen_at = parse_wall_time(
            require(candidate, "frozen_at", f"{path}.candidate"), f"{path}.candidate.frozen_at"
        )
        roles: dict[str, str] = {}
        for index, item in enumerate(
            sequence(require(data, "conditions", path), f"{path}.conditions")
        ):
            cpath = f"{path}.conditions[{index}]"
            cdata = mapping(item, cpath)
            condition_id = string(cdata, "id", cpath)
            if condition_id in roles:
                raise Malformed(f"{cpath}.id", f"duplicate condition {condition_id!r}")
            roles[condition_id] = string(cdata, "role", cpath, allowed=CONDITION_ROLES)
        c.fresh_condition_ids = [cid for cid, role in roles.items() if role == "fresh"]
        c.reproduction_condition_ids = [
            cid for cid, role in roles.items() if role == "reproduction"
        ]
        if not c.fresh_condition_ids:
            raise Malformed(f"{path}.conditions", "declare at least one fresh condition")
        exploration = set(string_list(data, "exploration_condition_ids", path))
        if data.get("identity") is not None:
            c.frozen_identity = {
                key: value
                for key, value in mapping(data["identity"], f"{path}.identity").items()
                if isinstance(value, str) and value.strip()
            }
        contamination = mapping(data.get("contamination") or {}, f"{path}.contamination")
        declared = optional_string(contamination, "declared", f"{path}.contamination")
        if declared is not None and declared != "none":
            c.add(codes.CONTAMINATION_DECLARED, f"producer declared contamination: {declared}")
        assignments = []
        for index, item in enumerate(
            sequence(require(data, "assignments", path), f"{path}.assignments")
        ):
            apath = f"{path}.assignments[{index}]"
            adata = mapping(item, apath)
            assignments.append(
                (
                    string(adata, "condition_id", apath),
                    string(adata, "reference_run_id", apath),
                    string(adata, "candidate_run_id", apath),
                )
            )
    except Malformed as error:
        c.add(codes.MALFORMED_RECORD, error.detail, path=error.path)
        return c

    # Freshness: declared exploration, exploration runs in the bundle, and prior confirmations.
    assigned_candidate_ids = {a[2] for a in assignments}
    assigned_reference_ids = {a[1] for a in assignments}
    derived_exploration = {
        a.condition_id
        for a in assessments.values()
        if a.role == "candidate"
        and a.run_id not in assigned_candidate_ids
        and a.started_at is not None
        and a.started_at < c.frozen_at
        and a.condition_id
    }
    consumed = _prior_conditions(prior, case.id)
    history = set(extra_consumed)
    c.consumed_condition_ids = sorted(exploration | derived_exploration | consumed | history)
    for condition_id in c.fresh_condition_ids:
        origins = []
        if condition_id in exploration:
            origins.append("declared exploration set")
        if condition_id in derived_exploration:
            origins.append("a candidate run before the freeze")
        if condition_id in consumed:
            origins.append("a prior confirmation of this case")
        if condition_id in history:
            origins.append("retained history supplied to the evaluator")
        if origins:
            c.add(
                codes.CONFIRMATION_CONDITION_REUSED,
                f"fresh condition {condition_id!r} was already used in {', '.join(origins)}",
            )
    if case.reproduction_condition_id not in c.reproduction_condition_ids:
        c.add(
            codes.REPRODUCTION_NOT_CONFIRMED,
            f"the failing condition {case.reproduction_condition_id!r} is not assigned for reproduction",
        )

    # Every declared condition has exactly one assignment; every assignment has both outcomes.
    by_condition: dict[str, list[tuple[str, str, str]]] = {}
    for assignment in assignments:
        by_condition.setdefault(assignment[0], []).append(assignment)
    for condition_id, role in roles.items():
        entries = by_condition.get(condition_id, [])
        if not entries:
            c.add(
                codes.CONDITION_UNASSIGNED,
                f"condition {condition_id!r} ({role}) has no assigned runs",
            )
        elif len(entries) > 1:
            c.add(
                codes.MULTIPLE_RUNS_PER_CONDITION_ROLE,
                f"condition {condition_id!r} is assigned {len(entries)} times",
            )
    for condition_id in by_condition:
        if condition_id not in roles:
            c.add(
                codes.MALFORMED_RECORD,
                f"assignment for undeclared condition {condition_id!r}",
                path=f"{path}.assignments",
            )

    # Extra runs on confirmation conditions would allow selecting the best of several attempts.
    for a in assessments.values():
        if (
            a.condition_id not in roles
            or a.run_id in assigned_candidate_ids | assigned_reference_ids
        ):
            continue
        if a.evidence_origin == "invalid_replay_control" or a.continuation != "full_rerun":
            # A labelled derived control or a partial reuse is not a spare closed-loop attempt;
            # it cannot count for the obligation, so it cannot have been selected against.
            c.add(
                codes.INTERVENTION_DECLARED,
                f"derived or partial-reuse run {a.run_id!r} on {a.condition_id!r} is excluded from "
                "the spare-attempt rule; it is assessed on its own provenance",
                run_id=a.run_id,
            )
            continue
        if a.role == "candidate" and a.candidate and a.candidate["digest"] == c.candidate_digest:
            if a.started_at is not None and a.started_at >= c.frozen_at:
                c.add(
                    codes.MULTIPLE_RUNS_PER_CONDITION_ROLE,
                    f"unassigned run {a.run_id!r} also executes the frozen candidate on {a.condition_id!r}",
                    run_id=a.run_id,
                )
        elif a.role == "reference" and a.condition_id in c.fresh_condition_ids:
            c.add(
                codes.MULTIPLE_RUNS_PER_CONDITION_ROLE,
                f"unassigned reference run {a.run_id!r} also covers fresh condition {a.condition_id!r}",
                run_id=a.run_id,
            )

    informative = 0
    for condition_id, reference_id, candidate_id in assignments:
        role = roles.get(condition_id, "fresh")
        pair = Pair(condition_id, role, reference_id, candidate_id)
        c.pairs.append(pair)
        first_finding = len(c.findings)
        c.assigned_candidate_run_ids.append(candidate_id)
        missing = [rid for rid in (reference_id, candidate_id) if rid not in assessments]
        if missing:
            c.add(
                codes.ASSIGNED_OUTCOME_MISSING,
                f"condition {condition_id!r}: assigned run(s) {missing} are not in the bundle",
            )
            continue
        reference, candidate = assessments[reference_id], assessments[candidate_id]
        pair.reference_measurement, pair.candidate_measurement = (
            reference.measurement,
            candidate.measurement,
        )
        pair.reference_outcome, pair.candidate_outcome = reference.outcome, candidate.outcome
        problems = False
        for label, run in (("reference", reference), ("candidate", candidate)):
            expected_role = "reference" if label == "reference" else "candidate"
            if run.role != expected_role:
                c.add(
                    codes.ASSIGNMENT_ROLE_MISMATCH,
                    f"{run.run_id!r} is a {run.role} run, assigned as {label}",
                    run_id=run.run_id,
                )
                problems = True
            if run.condition_id != condition_id:
                c.add(
                    codes.ASSIGNMENT_ROLE_MISMATCH,
                    f"{run.run_id!r} ran condition {run.condition_id!r}, assigned to {condition_id!r}",
                    run_id=run.run_id,
                )
                problems = True
            if run.measurement == "invalid":
                c.add(
                    codes.ASSIGNED_RUN_INVALID,
                    f"{label} run {run.run_id!r} is an invalid experiment",
                    run_id=run.run_id,
                )
                problems = True
            elif run.measurement == "unresolved":
                c.add(
                    codes.ASSIGNED_RUN_UNRESOLVED,
                    f"{label} run {run.run_id!r} cannot be assessed",
                    run_id=run.run_id,
                )
                problems = True
        if candidate.candidate and candidate.candidate["digest"] != c.candidate_digest:
            c.add(
                codes.CANDIDATE_NOT_FROZEN,
                f"run {candidate_id!r} executed candidate {candidate.candidate['digest']}, not the frozen {c.candidate_digest}",
                run_id=candidate_id,
            )
            problems = True
        if candidate.started_at is not None and candidate.started_at <= c.frozen_at:
            if (
                role == "reproduction"
                and candidate.candidate
                and candidate.candidate["digest"] == c.candidate_digest
            ):
                if case.strict:
                    c.add(
                        codes.REPRODUCTION_NOT_POST_FREEZE,
                        f"the reproduction run {candidate_id!r} started before the freeze; the "
                        "strict obligation requires a post-freeze rerun of the failing condition",
                        run_id=candidate_id,
                    )
                    problems = True
                else:
                    c.add(
                        codes.REPRODUCTION_EVIDENCE_PRECEDES_FREEZE,
                        f"the reproduction fix is evidenced by run {candidate_id!r}, executed before "
                        "the freeze with the identical candidate digest; a post-freeze rerun would be "
                        "stronger",
                        run_id=candidate_id,
                    )
            else:
                c.add(
                    codes.RUN_PRECEDES_FREEZE,
                    f"run {candidate_id!r} started at {candidate.started_at.isoformat()} before the "
                    f"freeze at {c.frozen_at.isoformat()}",
                    run_id=candidate_id,
                )
                problems = True
        if (
            reference.initial_state_digest
            and candidate.initial_state_digest
            and reference.initial_state_digest != candidate.initial_state_digest
        ):
            c.add(
                codes.PAIRED_INITIAL_STATE_MISMATCH,
                f"condition {condition_id!r}: reference and candidate reset to different recorded states",
                run_id=candidate_id,
            )
            problems = True
        if problems:
            worst = codes.strongest([f.severity for f in c.findings[first_finding:]])
            pair.verdict = "invalid" if worst == codes.INVALID else "gap"
            continue
        if role == "reproduction":
            still_failing = _violates(candidate, case)
            if candidate.outcome == "completed" and not still_failing:
                pair.verdict = "fixed"
            elif still_failing:
                pair.verdict = "not_fixed"
                c.add(
                    codes.REPRODUCTION_NOT_FIXED,
                    f"the frozen candidate still violates the {case.failure_obligation} obligation "
                    f"on the failing condition {condition_id!r}",
                    run_id=candidate_id,
                )
            else:
                pair.verdict = "not_fixed"
                c.add(
                    codes.REPRODUCTION_NOT_FIXED,
                    f"the frozen candidate does not complete the failing condition {condition_id!r}",
                    run_id=candidate_id,
                )
            continue
        if reference.outcome == "completed":
            informative += 1
            if candidate.outcome == "completed":
                pair.verdict = "pass"
            else:
                pair.verdict = "regression"
                c.add(
                    codes.REGRESSION_ON_FRESH_CONDITION,
                    f"condition {condition_id!r}: the reference completes and the candidate fails",
                    run_id=candidate_id,
                )
        elif candidate.outcome == "completed":
            pair.verdict = "improved"
            c.add(
                codes.CANDIDATE_IMPROVED_CONDITION,
                f"condition {condition_id!r}: the reference fails and the candidate completes",
                run_id=candidate_id,
            )
        else:
            pair.verdict = "both_failed"
            c.add(
                codes.REFERENCE_FAILED_CONDITION,
                f"condition {condition_id!r}: reference and candidate both fail; retained, not a regression",
                run_id=candidate_id,
            )
    _check_identity_binding(c, case, assessments)
    if (
        c.pairs
        and informative == 0
        and not any(f.code == codes.ASSIGNED_OUTCOME_MISSING for f in c.findings)
    ):
        c.add(
            codes.CONFIRMATION_UNINFORMATIVE,
            "the reference completes none of the fresh conditions; they do not exercise the task",
        )
    return c


def _check_identity_binding(
    c: ConfirmationAssessment, case: Case, assessments: dict[str, RunAssessment]
) -> None:
    """Every assigned run must name the same execution, configuration, code and policy identity."""
    assigned = []
    for pair in c.pairs:
        for run_id in (pair.reference_run_id, pair.candidate_run_id):
            if run_id in assessments and run_id not in assigned:
                assigned.append(run_id)
    if not assigned:
        return
    identities = {run_id: assessments[run_id].identity or {} for run_id in assigned}
    required = ("execution_identity_sha256", "policy_sha256", "configuration_sha256")

    def lacking(identity: dict) -> list[str]:
        gaps = [key for key in required if not identity.get(key)]
        if not identity.get("code_sha256") and not identity.get("code_git_head"):
            gaps.append("code_sha256 or code_git_head")
        return gaps

    incomplete = {
        run_id: lacking(identity)
        for run_id, identity in identities.items()
        if identity and lacking(identity)
    }
    if incomplete and case.strict:
        sample = next(iter(incomplete.items()))
        c.add(
            codes.IDENTITY_UNBOUND,
            f"{len(incomplete)} assigned runs carry a partial identity; for example "
            f"{sample[0]!r} lacks {sample[1]}",
        )
    missing = [run_id for run_id, identity in identities.items() if not identity]
    if missing:
        detail = (
            f"{len(missing)} of {len(assigned)} assigned runs carry no per-run identity "
            f"(invocation, execution, configuration, code, dependency and policy digests): "
            f"{missing[:4]}"
        )
        if case.strict:
            c.add(codes.IDENTITY_UNBOUND, detail)
        else:
            c.add(
                codes.IDENTITY_INHERITED,
                detail + "; identity is inherited from the bundle-level case",
            )
    present = {run_id: identity for run_id, identity in identities.items() if identity}
    if not present:
        return
    mismatched = False
    checked = []
    for key in BOUND_IDENTITY_KEYS:
        values = {identity[key] for identity in present.values() if identity.get(key)}
        if not values:
            continue
        checked.append(key)
        if len(values) > 1:
            mismatched = True
            c.add(codes.IDENTITY_MISMATCH, f"assigned runs disagree on {key}: {sorted(values)[:3]}")
        frozen = c.frozen_identity.get(key)
        if frozen and values != {frozen}:
            mismatched = True
            c.add(
                codes.IDENTITY_MISMATCH,
                f"{key} of the assigned runs ({sorted(values)[:2]}) differs from the frozen "
                f"protocol's {frozen}",
            )
    # The deployment configuration differs between reference and candidate runs by design;
    # it must agree within each role and, for candidates, with the frozen candidate.
    for role in ("reference", "candidate"):
        values = {
            identity["configuration_sha256"]
            for run_id, identity in present.items()
            if identity.get("configuration_sha256") and assessments[run_id].role == role
        }
        if values:
            checked.append(f"configuration_sha256[{role}]")
        if len(values) > 1:
            mismatched = True
            c.add(
                codes.IDENTITY_MISMATCH,
                f"assigned {role} runs disagree on configuration_sha256: {sorted(values)[:3]}",
            )
    invocations = {identity.get("invocation_id") for identity in present.values()}
    invocations.discard(None)
    if len(invocations) > 1:
        c.add(
            codes.QUALIFICATION_REPEAT,
            f"assigned runs come from {len(invocations)} invocations; execution identity still agrees"
            if not mismatched
            else f"assigned runs come from {len(invocations)} invocations",
        )
    if not missing and not mismatched:
        c.add(
            codes.IDENTITY_VERIFIED,
            f"all {len(assigned)} assigned runs carry matching identity for {checked}"
            + (" and agree with the frozen protocol" if c.frozen_identity else ""),
        )
