"""The case record: identities, declared predicates and repair scope."""

from __future__ import annotations

from dataclasses import dataclass, field

from .schema import (
    Malformed,
    digest_of,
    finite,
    mapping,
    optional_string,
    parse_duration,
    require,
    sequence,
    string,
    string_list,
)

CASE_SCHEMA = "nisayon.case.v1"
EVIDENCE_ORIGINS = {"synthetic_development", "simulator", "hardware", "invalid_replay_control"}
OPS = {">=", "<=", ">", "<", "=="}
WHEN = {"final", "any", "all"}
OBLIGATION_V01 = "first-case-obligation-v0.1"
OBLIGATION_V02 = "first-case-obligation-v0.2"
OBLIGATIONS = {OBLIGATION_V01, OBLIGATION_V02}
TIMING_EVIDENCE = {"acquisition_stamps", "none"}
FAILURE_OBLIGATIONS = {"task", "timing", "progress", "reset", "constraints"}


@dataclass(frozen=True)
class Threshold:
    id: str
    measure: str
    unit: str
    op: str
    threshold: float
    when: str = "all"

    def holds(self, value: float) -> bool:
        match self.op:
            case ">=":
                return value >= self.threshold
            case "<=":
                return value <= self.threshold
            case ">":
                return value > self.threshold
            case "<":
                return value < self.threshold
            case _:
                return value == self.threshold


@dataclass(frozen=True)
class Progress:
    id: str
    measure: str
    unit: str
    minimum_gain: float
    activation_tolerance: float


@dataclass(frozen=True)
class Timing:
    id: str
    clock: str
    max_observation_age_s: float
    max_step_period_s: float
    evidence: str = "acquisition_stamps"


@dataclass(frozen=True)
class Case:
    id: str
    evidence_origin: str
    task_id: str
    policy: dict
    backend: dict
    working_revision: str
    changed_revision: str
    reproduction_condition_id: str
    outcome: Threshold
    progress: Progress
    constraints: tuple[Threshold, ...]
    timing: Timing
    predicates_digest: str
    state_components: tuple[str, ...]
    omitted_state: tuple[str, ...]
    allowed_component_kinds: frozenset[str]
    allowed_paths: tuple[str, ...]
    preparation_costs: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    obligation: str = OBLIGATION_V01
    evaluator_added_predicates: tuple[str, ...] = ()
    calibration: bool = False
    failure_obligation: str = "task"

    @property
    def strict(self) -> bool:
        """Version 0.2 requires the evidence that version 0.1 only reports as limitations."""
        return self.obligation == OBLIGATION_V02


def _threshold(obj: object, path: str, *, when_required: bool) -> Threshold:
    data = mapping(obj, path)
    when = string(data, "when", path, allowed=WHEN) if when_required else "all"
    return Threshold(
        id=string(data, "id", path),
        measure=string(data, "measure", path),
        unit=string(data, "unit", path),
        op=string(data, "op", path, allowed=OPS),
        threshold=finite(require(data, "threshold", path), f"{path}.threshold"),
        when=when,
    )


def _identity(obj: object, path: str) -> dict:
    data = mapping(obj, path)
    identity = {"id": string(data, "id", path)}
    for key in ("digest", "version"):
        value = optional_string(data, key, path)
        if value is not None:
            identity[key] = value
    return identity


def parse_case(obj: object) -> Case:
    path = "case"
    data = mapping(obj, path)
    schema = string(data, "schema", path)
    if schema != CASE_SCHEMA:
        raise Malformed(f"{path}.schema", f"expected {CASE_SCHEMA}, found {schema!r}")
    task = mapping(require(data, "task", path), f"{path}.task")
    revisions = mapping(require(data, "revisions", path), f"{path}.revisions")
    failure = mapping(require(data, "failure", path), f"{path}.failure")
    predicates = mapping(require(data, "predicates", path), f"{path}.predicates")
    ppath = f"{path}.predicates"
    progress_data = mapping(require(predicates, "progress", ppath), f"{ppath}.progress")
    timing_data = mapping(require(predicates, "timing", ppath), f"{ppath}.timing")
    qualification = mapping(data.get("qualification", {}), f"{path}.qualification")
    scope = mapping(data.get("repair_scope", {}), f"{path}.repair_scope")
    constraints = tuple(
        _threshold(item, f"{ppath}.constraints[{index}]", when_required=False)
        for index, item in enumerate(
            sequence(predicates.get("constraints", []), f"{ppath}.constraints")
        )
    )
    components = string_list(qualification, "state_components", f"{path}.qualification")
    if not components:
        raise Malformed(
            f"{path}.qualification.state_components",
            "declare the state components a reset must cover",
        )
    return Case(
        id=string(data, "id", path),
        evidence_origin=string(data, "evidence_origin", path, allowed=EVIDENCE_ORIGINS),
        task_id=string(task, "id", f"{path}.task"),
        policy=_identity(require(task, "policy", f"{path}.task"), f"{path}.task.policy"),
        backend=_identity(require(task, "backend", f"{path}.task"), f"{path}.task.backend"),
        working_revision=string(revisions, "working", f"{path}.revisions"),
        changed_revision=string(revisions, "changed", f"{path}.revisions"),
        reproduction_condition_id=string(failure, "condition_id", f"{path}.failure"),
        outcome=_threshold(
            require(predicates, "outcome", ppath), f"{ppath}.outcome", when_required=True
        ),
        progress=Progress(
            id=string(progress_data, "id", f"{ppath}.progress"),
            measure=string(progress_data, "measure", f"{ppath}.progress"),
            unit=string(progress_data, "unit", f"{ppath}.progress"),
            minimum_gain=finite(
                require(progress_data, "minimum_gain", f"{ppath}.progress"),
                f"{ppath}.progress.minimum_gain",
            ),
            activation_tolerance=finite(
                progress_data.get("activation_tolerance", 0.0),
                f"{ppath}.progress.activation_tolerance",
            ),
        ),
        constraints=constraints,
        timing=Timing(
            id=string(timing_data, "id", f"{ppath}.timing"),
            clock=string(timing_data, "clock", f"{ppath}.timing"),
            max_observation_age_s=parse_duration(
                require(timing_data, "max_observation_age", f"{ppath}.timing"),
                f"{ppath}.timing.max_observation_age",
            ),
            max_step_period_s=parse_duration(
                require(timing_data, "max_step_period", f"{ppath}.timing"),
                f"{ppath}.timing.max_step_period",
            ),
            evidence=(
                string(timing_data, "evidence", f"{ppath}.timing", allowed=TIMING_EVIDENCE)
                if timing_data.get("evidence") is not None
                else "acquisition_stamps"
            ),
        ),
        predicates_digest=digest_of(predicates),
        state_components=tuple(components),
        omitted_state=tuple(string_list(qualification, "omitted_state", f"{path}.qualification")),
        allowed_component_kinds=frozenset(
            string_list(scope, "allowed_component_kinds", f"{path}.repair_scope")
        ),
        allowed_paths=tuple(string_list(scope, "allowed_paths", f"{path}.repair_scope")),
        preparation_costs=mapping(data.get("preparation_costs", {}), f"{path}.preparation_costs"),
        raw=data,
        obligation=(
            string(data, "obligation", path, allowed=OBLIGATIONS)
            if data.get("obligation") is not None
            else OBLIGATION_V01
        ),
        evaluator_added_predicates=tuple(string_list(predicates, "evaluator_added_ids", ppath)),
        calibration=bool(data.get("calibration", False)),
        failure_obligation=(
            string(data, "failure_obligation", path, allowed=FAILURE_OBLIGATIONS)
            if data.get("failure_obligation") is not None
            else "task"
        ),
    )
