"""Per-run assessment: process, measurement validity, task outcome and cost.

The four layers stay separate. A run can complete as a process and still be an
invalid experiment; a valid experiment can show a failed task; neither is an
acceptance. Producer claims are retained for comparison and never used as
evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import codes
from .case import EVIDENCE_ORIGINS, Case, Threshold
from .schema import (
    Malformed,
    Quantity,
    canonical_json,
    finite,
    integer,
    load_json,
    mapping,
    number_list,
    optional_string,
    parse_quantity,
    parse_sim_time,
    parse_wall_time,
    require,
    sequence,
    sha256_bytes,
    string,
)

RUN_SCHEMA = "nisayon.run.v1"
TRACE_SCHEMA = "nisayon.trace.v1"
PROCESS_STATUSES = {"completed", "nonzero", "timeout", "interrupted", "spawn_error", "running"}
CONTINUATIONS = {"full_rerun", "partial_reuse"}
PROVENANCE_KINDS = {"closed_loop", "recorded"}
RESET_STATUSES = {"restored", "cleared", "seeded", "not_applicable", "unknown", "carried"}
RESET_COMPLETE = {"restored", "cleared", "seeded", "not_applicable"}
OUTCOMES = {"completed", "failed", "unknown"}
VALIDITY_CLAIMS = {"valid", "invalid", "unknown"}
COMPONENT_ROLES = {"deployable_edit", "diagnostic_oracle"}
ORACLE_SOURCE = "oracle"

MEASUREMENT_CODES = {
    codes.MALFORMED_RECORD,
    codes.ARTIFACT_MISSING,
    codes.ARTIFACT_DIGEST_MISMATCH,
    codes.IDENTITY_MISMATCH,
    codes.SYNTHETIC_PRESENTED_AS_MEASUREMENT,
    codes.PROCESS_INCOMPLETE,
    codes.RECORDED_OBSERVATION_IN_FULL_RERUN,
    codes.AFFECTED_FUTURE_OBSERVATION_REUSED,
    codes.RECORDED_OBSERVATION_FROM_UNDECLARED_SOURCE,
    codes.DIVERGENCE_PRECEDES_ACTIVATION,
    codes.SOURCE_RUN_MISSING,
    codes.PREFIX_REUSE_CONDITION_MISMATCH,
    codes.OBSERVATION_AFTER_ACTION,
    codes.UNKNOWN_OBSERVATION_REFERENCE,
    codes.NON_MONOTONE_CLOCK,
    codes.CHUNK_SCHEDULE_INCONSISTENT,
    codes.RESET_EVIDENCE_INCOMPLETE,
    codes.RESET_CONDITION_MISMATCH,
    codes.CANDIDATE_NOT_ON_CHANGED_REVISION,
    codes.MEASUREMENT_UNIT_UNDECLARED,
    codes.PREDICATE_UNMEASURABLE,
    codes.TRACE_CHAIN_BROKEN,
    codes.RAW_TRACE_MISMATCH,
    codes.MEASUREMENT_INCONSISTENT,
    codes.CAPTURE_STAMPS_INCONSISTENT,
}


@dataclass(frozen=True)
class Finding:
    code: str
    detail: str
    run_id: str | None = None
    step: int | None = None
    path: str | None = None

    @property
    def severity(self) -> str:
        return codes.SEVERITY[self.code]

    def to_dict(self) -> dict:
        data = {"code": self.code, "severity": self.severity, "detail": self.detail}
        for key in ("run_id", "step", "path"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data


@dataclass(frozen=True)
class Step:
    index: int
    obs_id: str
    obs_t: float
    obs_source: str
    provenance: str
    source_run_id: str | None
    source_step: int | None
    computed_from: str
    t_executed: float
    chunk: tuple[str, int, int] | None
    intended: tuple[float, ...]
    executed: tuple[float, ...]
    measurements: dict[str, float | None]
    missing: dict[str, str]
    capture: dict | None = None
    host: dict | None = None


@dataclass(frozen=True)
class Trace:
    run_id: str
    digest: str
    units: dict[str, str]
    steps: tuple[Step, ...]


class ArtifactMissing(Exception):
    pass


class DigestMismatch(Exception):
    pass


def _parse_step(obj: object, position: int, clock: str) -> Step:
    path = f"trace.steps[{position}]"
    data = mapping(obj, path)
    index = integer(require(data, "step", path), f"{path}.step", minimum=0)
    if index != position:
        raise Malformed(f"{path}.step", f"expected {position}, found {index}")
    obs = mapping(require(data, "observation", path), f"{path}.observation")
    opath = f"{path}.observation"
    provenance = mapping(require(obs, "provenance", opath), f"{opath}.provenance")
    kind = string(provenance, "kind", f"{opath}.provenance", allowed=PROVENANCE_KINDS)
    source_run_id = source_step = None
    if kind == "recorded":
        source_run_id = string(provenance, "source_run_id", f"{opath}.provenance")
        source_step = integer(
            require(provenance, "source_step", f"{opath}.provenance"),
            f"{opath}.provenance.source_step",
            minimum=0,
        )
    action = mapping(require(data, "action", path), f"{path}.action")
    apath = f"{path}.action"
    chunk = None
    if action.get("chunk") is not None:
        cdata = mapping(action["chunk"], f"{apath}.chunk")
        chunk = (
            string(cdata, "id", f"{apath}.chunk"),
            integer(require(cdata, "index", f"{apath}.chunk"), f"{apath}.chunk.index", minimum=0),
            integer(require(cdata, "length", f"{apath}.chunk"), f"{apath}.chunk.length", minimum=1),
        )
    intended = tuple(number_list(require(action, "intended", apath), f"{apath}.intended"))
    executed = tuple(number_list(require(action, "executed", apath), f"{apath}.executed"))
    if len(intended) != len(executed):
        raise Malformed(f"{apath}.executed", "intended and executed actions differ in length")
    measurements: dict[str, float | None] = {}
    missing: dict[str, str] = {}
    mdata = mapping(require(data, "measurements", path), f"{path}.measurements")
    for name, value in mdata.items():
        mpath = f"{path}.measurements.{name}"
        if isinstance(value, dict):
            quantity = parse_quantity(value, mpath) if "unit" in value else _missing(value, mpath)
            measurements[name] = quantity.value
            if quantity.missing is not None:
                missing[name] = quantity.missing
        else:
            measurements[name] = finite(value, mpath)
    capture = None
    if obs.get("capture") is not None:
        capture = _parse_capture(obs["capture"], f"{opath}.capture")
    host = None
    if action.get("host") is not None:
        hdata = mapping(action["host"], f"{apath}.host")
        host = {
            key: finite(hdata[key], f"{apath}.host.{key}")
            for key in hdata
            if hdata[key] is not None
        }
    return Step(
        index=index,
        obs_id=string(obs, "id", opath),
        obs_t=parse_sim_time(require(obs, "t", opath), f"{opath}.t", clock),
        obs_source=string(obs, "source", opath),
        provenance=kind,
        source_run_id=source_run_id,
        source_step=source_step,
        computed_from=string(action, "computed_from", apath),
        t_executed=parse_sim_time(
            require(action, "t_executed", apath), f"{apath}.t_executed", clock
        ),
        chunk=chunk,
        intended=intended,
        executed=executed,
        measurements=measurements,
        missing=missing,
        capture=capture,
        host=host,
    )


def _parse_capture(obj: object, path: str) -> dict:
    """Acquisition stamps of the sensor components that make up one observation."""
    data = mapping(obj, path)
    components = {}
    for name, item in mapping(require(data, "components", path), f"{path}.components").items():
        cpath = f"{path}.components.{name}"
        cdata = mapping(item, cpath)
        components[name] = {
            "sequence": integer(require(cdata, "sequence", cpath), f"{cpath}.sequence", minimum=0),
            "simulation_s": finite(require(cdata, "simulation_s", cpath), f"{cpath}.simulation_s"),
            "host_started_s": finite(
                require(cdata, "host_started_s", cpath), f"{cpath}.host_started_s"
            ),
            "host_finished_s": finite(
                require(cdata, "host_finished_s", cpath), f"{cpath}.host_finished_s"
            ),
        }
    if not components:
        raise Malformed(
            f"{path}.components", "an observation needs at least one acquired component"
        )
    received = data.get("received_host_s")
    return {
        "components": components,
        "received_host_s": finite(received, f"{path}.received_host_s")
        if received is not None
        else None,
    }


def _missing(value: dict, path: str) -> Quantity:
    if value.get("value") is not None:
        raise Malformed(path, "a measurement object needs a unit or an explicit missing value")
    reason = value.get("missing")
    if not isinstance(reason, str) or not reason.strip():
        raise Malformed(f"{path}.missing", "a null measurement needs a missingness reason")
    return Quantity(None, "undeclared", reason)


def parse_trace(obj: object, run_id: str, digest: str, clock: str) -> Trace:
    data = mapping(obj, "trace")
    schema = string(data, "schema", "trace")
    if schema != TRACE_SCHEMA:
        raise Malformed("trace.schema", f"expected {TRACE_SCHEMA}, found {schema!r}")
    if string(data, "run_id", "trace") != run_id:
        raise Malformed("trace.run_id", f"trace belongs to {data['run_id']!r}, not {run_id!r}")
    units_data = mapping(data.get("measurement_units", {}), "trace.measurement_units")
    units = {}
    for name, unit in units_data.items():
        if not isinstance(unit, str) or not unit.strip():
            raise Malformed(f"trace.measurement_units.{name}", "expected a unit string")
        units[name] = unit
    steps = sequence(require(data, "steps", "trace"), "trace.steps")
    if not steps:
        raise Malformed("trace.steps", "empty trace")
    return Trace(
        run_id=run_id,
        digest=digest,
        units=units,
        steps=tuple(_parse_step(step, position, clock) for position, step in enumerate(steps)),
    )


class TraceStore:
    """Resolve, verify and cache trace artifacts against an explicit artifact root."""

    def __init__(self, artifact_root: Path, runs: dict[str, dict], clock: str) -> None:
        self.root = artifact_root.resolve()
        self.runs = runs
        self.clock = clock
        self._cache: dict[str, Trace] = {}

    def get(self, run_id: str) -> Trace:
        if run_id in self._cache:
            return self._cache[run_id]
        run = self.runs[run_id]
        inline = run.get("trace")
        if inline is not None:
            raw = (canonical_json(inline) + "\n").encode()
            trace = parse_trace(inline, run_id, sha256_bytes(raw), self.clock)
            self._cache[run_id] = trace
            return trace
        ref = mapping(require(run, "trace_ref", "run"), "run.trace_ref")
        relative = string(ref, "path", "run.trace_ref")
        expected = string(ref, "sha256", "run.trace_ref")
        if Path(relative).is_absolute():
            raise Malformed(
                "run.trace_ref.path", "artifact paths are relative to the artifact root"
            )
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise Malformed("run.trace_ref.path", "artifact path escapes the artifact root")
        if not target.is_file():
            raise ArtifactMissing(relative)
        data = target.read_bytes()
        digest = sha256_bytes(data)
        if digest != expected:
            raise DigestMismatch(f"{relative}: declared {expected}, actual {digest}")
        trace = parse_trace(load_json(target), run_id, digest, self.clock)
        self._cache[run_id] = trace
        return trace


@dataclass
class RunAssessment:
    run_id: str
    role: str = "unknown"
    revision_role: str | None = None
    condition_id: str | None = None
    candidate: dict | None = None
    evidence_origin: str | None = None
    started_at: datetime | None = None
    process: str | None = None
    measurement: str = "unresolved"
    outcome_claimed: str | None = None
    validity_claimed: str | None = None
    outcome: str = "unknown"
    progress: str = "unknown"
    constraints: str = "unknown"
    timing: str = "unknown"
    findings: list[Finding] = field(default_factory=list)
    costs: dict[str, Quantity] = field(default_factory=dict)
    trace_digest: str | None = None
    initial_state_digest: str | None = None
    activation_step: int | None = None
    metrics: dict = field(default_factory=dict)
    identity: dict | None = None
    reset_evidence: dict = field(default_factory=dict)
    continuation: str = "full_rerun"
    cost_parent: str | None = None

    def add(
        self, code: str, detail: str, *, step: int | None = None, path: str | None = None
    ) -> None:
        self.findings.append(Finding(code, detail, run_id=self.run_id, step=step, path=path))

    def obligation_failures(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == codes.REJECTED]

    def unmeasured_obligations(self) -> list[Finding]:
        """Declared obligations this run cannot evidence; they block acceptance, not validity."""
        gaps = {codes.TIMING_UNMEASURED, codes.CANDIDATE_DEPLOYABILITY_UNDECLARED}
        return [f for f in self.findings if f.code in gaps]

    def finalize(self) -> RunAssessment:
        severities = [f.severity for f in self.findings if f.code in MEASUREMENT_CODES]
        strongest = codes.strongest(severities)
        self.measurement = {
            codes.INVALID: "invalid",
            codes.UNRESOLVED: "unresolved",
        }.get(strongest, "valid")
        return self

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "role": self.role,
            "revision": self.revision_role,
            "condition_id": self.condition_id,
            "candidate": (
                {"id": self.candidate["id"], "digest": self.candidate["digest"]}
                if self.candidate
                else None
            ),
            "evidence_origin": self.evidence_origin,
            "process": self.process,
            "measurement": self.measurement,
            "outcome": {"observed": self.outcome, "claimed": self.outcome_claimed},
            "progress": self.progress,
            "constraints": self.constraints,
            "timing": self.timing,
            "metrics": self.metrics,
            "findings": [f.to_dict() for f in self.findings],
            "costs": {name: q.to_dict() for name, q in self.costs.items()},
            "cost_parent_run_id": self.cost_parent,
            "trace_digest": self.trace_digest,
            "identity": self.identity,
        }


def _identity_matches(declared: dict, found: dict) -> bool:
    return all(found.get(key) == value for key, value in declared.items())


def _parse_header(run: dict, case: Case, a: RunAssessment) -> dict:
    path = "run"
    schema = string(run, "schema", path)
    if schema != RUN_SCHEMA:
        raise Malformed(f"{path}.schema", f"expected {RUN_SCHEMA}, found {schema!r}")
    case_id = string(run, "case_id", path)
    if case_id != case.id:
        a.add(codes.IDENTITY_MISMATCH, f"run belongs to case {case_id!r}, not {case.id!r}")
    a.evidence_origin = string(run, "evidence_origin", path, allowed=EVIDENCE_ORIGINS)
    a.started_at = parse_wall_time(require(run, "started_at", path), f"{path}.started_at")
    revision = mapping(require(run, "revision", path), f"{path}.revision")
    a.revision_role = string(
        revision, "role", f"{path}.revision", allowed={"working", "changed", "probe"}
    )
    revision_id = string(revision, "id", f"{path}.revision")
    if a.revision_role != "probe":
        expected_id = (
            case.working_revision if a.revision_role == "working" else case.changed_revision
        )
        if revision_id != expected_id:
            a.add(
                codes.IDENTITY_MISMATCH,
                f"{a.revision_role} revision is {revision_id!r}; the case declares {expected_id!r}",
            )
    task = mapping(require(run, "task", path), f"{path}.task")
    for name, declared in (("policy", case.policy), ("backend", case.backend)):
        found = mapping(require(task, name, f"{path}.task"), f"{path}.task.{name}")
        if not _identity_matches(declared, found):
            a.add(codes.IDENTITY_MISMATCH, f"{name} identity {found} differs from case {declared}")
    a.condition_id = string(run, "condition_id", path)
    process = mapping(require(run, "process", path), f"{path}.process")
    a.process = string(process, "status", f"{path}.process", allowed=PROCESS_STATUSES)
    candidate = run.get("candidate")
    if candidate is not None:
        cdata = mapping(candidate, f"{path}.candidate")
        components = []
        for index, item in enumerate(
            sequence(cdata.get("components", []), f"{path}.candidate.components")
        ):
            cpath = f"{path}.candidate.components[{index}]"
            comp = mapping(item, cpath)
            components.append(
                {
                    "kind": string(comp, "kind", cpath),
                    "role": string(comp, "role", cpath, allowed=COMPONENT_ROLES),
                    "path": optional_string(comp, "path", cpath),
                }
            )
        deployable = cdata.get("deployable")
        if deployable is not None and not isinstance(deployable, bool):
            raise Malformed(f"{path}.candidate.deployable", "expected true, false or null")
        a.candidate = {
            "id": string(cdata, "id", f"{path}.candidate"),
            "digest": string(cdata, "digest", f"{path}.candidate"),
            "deployable": deployable,
            "components": components,
        }
        a.role = "candidate"
    else:
        a.role = "reference" if a.revision_role == "working" else "regression"
    if a.revision_role == "probe":
        # A calibration probe: assessed for validity and predicates, never a candidate verdict.
        a.role = "probe"
    plan = mapping(run.get("plan") or {}, f"{path}.plan")
    continuation = optional_string(plan, "continuation", f"{path}.plan", allowed=CONTINUATIONS)
    intervention = plan.get("intervention")
    parsed_plan = {"continuation": continuation or "full_rerun", "source_run_id": None}
    a.continuation = parsed_plan["continuation"]
    if intervention is not None:
        idata = mapping(intervention, f"{path}.plan.intervention")
        parsed_plan["mechanism"] = string(idata, "mechanism", f"{path}.plan.intervention")
        a.activation_step = integer(
            require(idata, "activation_step", f"{path}.plan.intervention"),
            f"{path}.plan.intervention.activation_step",
            minimum=0,
        )
        a.add(
            codes.INTERVENTION_DECLARED,
            f"{parsed_plan['mechanism']} from step {a.activation_step}, {parsed_plan['continuation']}",
        )
    if parsed_plan["continuation"] == "partial_reuse":
        parsed_plan["source_run_id"] = string(plan, "source_run_id", f"{path}.plan")
        if intervention is None:
            raise Malformed(
                f"{path}.plan.intervention", "partial reuse without an intervention is a replay"
            )
    reset = mapping(require(run, "reset", path), f"{path}.reset")
    string(reset, "procedure_id", f"{path}.reset")
    initial = string(reset, "initial_condition_id", f"{path}.reset")
    if initial != a.condition_id:
        a.add(
            codes.RESET_CONDITION_MISMATCH,
            f"reset restored condition {initial!r} but the run is assigned to {a.condition_id!r}",
        )
    evidence = mapping(require(reset, "evidence", f"{path}.reset"), f"{path}.reset.evidence")
    for component in case.state_components:
        item = evidence.get(component)
        if item is None:
            a.add(codes.RESET_EVIDENCE_INCOMPLETE, f"no reset evidence for {component!r}")
            continue
        edata = mapping(item, f"{path}.reset.evidence.{component}")
        status = string(
            edata, "status", f"{path}.reset.evidence.{component}", allowed=RESET_STATUSES
        )
        a.reset_evidence[component] = status
        if status == "carried":
            source = optional_string(edata, "source_run_id", f"{path}.reset.evidence.{component}")
            step = edata.get("source_step")
            if source is None or not isinstance(step, int) or isinstance(step, bool):
                raise Malformed(
                    f"{path}.reset.evidence.{component}",
                    "a carried state must name its source run and step",
                )
            detail = f"{component!r} carried from run {source!r} step {step}; not cleared at reset"
            if candidate is not None and a.revision_role != "probe":
                a.add(codes.RESET_OBLIGATION_VIOLATED, detail)
            else:
                a.add(codes.RESET_CARRIED_STATE, detail)
        elif status not in RESET_COMPLETE:
            a.add(codes.RESET_EVIDENCE_INCOMPLETE, f"{component!r} reset status is {status!r}")
        elif status == "not_applicable" and not optional_string(
            edata, "reason", f"{path}.reset.evidence.{component}"
        ):
            a.add(
                codes.RESET_EVIDENCE_INCOMPLETE,
                f"{component!r} marked not applicable without a reason",
            )
    sim_state = evidence.get("sim_state")
    if isinstance(sim_state, dict):
        a.initial_state_digest = optional_string(
            sim_state, "digest", f"{path}.reset.evidence.sim_state"
        )
    outcome = mapping(run.get("task_outcome") or {}, f"{path}.task_outcome")
    a.outcome_claimed = optional_string(
        outcome, "claimed", f"{path}.task_outcome", allowed=OUTCOMES
    )
    validity = mapping(run.get("validity") or {}, f"{path}.validity")
    a.validity_claimed = optional_string(
        validity, "claimed", f"{path}.validity", allowed=VALIDITY_CLAIMS
    )
    for name, item in mapping(run.get("costs", {}), f"{path}.costs").items():
        a.costs[name] = parse_quantity(item, f"{path}.costs.{name}")
    a.cost_parent = optional_string(run, "cost_parent_run_id", path)
    if run.get("identity") is not None:
        identity = mapping(run["identity"], f"{path}.identity")
        a.identity = {
            key: value
            for key, value in identity.items()
            if isinstance(value, str) and value.strip()
        }
    return parsed_plan


def _check_structure(trace: Trace, a: RunAssessment) -> None:
    seen: dict[str, int] = {}
    previous_t: float | None = None
    for step in trace.steps:
        if step.obs_id in seen:
            a.add(
                codes.MALFORMED_RECORD, f"duplicate observation id {step.obs_id!r}", step=step.index
            )
        seen[step.obs_id] = step.index
        if previous_t is not None and step.obs_t <= previous_t:
            a.add(
                codes.NON_MONOTONE_CLOCK,
                f"observation time {step.obs_t} s does not advance past {previous_t} s",
                step=step.index,
            )
        previous_t = step.obs_t
        source_index = seen.get(step.computed_from)
        if source_index is None:
            a.add(
                codes.UNKNOWN_OBSERVATION_REFERENCE,
                f"action computed from unknown or later observation {step.computed_from!r}",
                step=step.index,
            )
            continue
        source_t = trace.steps[source_index].obs_t
        if step.t_executed < source_t:
            a.add(
                codes.OBSERVATION_AFTER_ACTION,
                f"action executed at {step.t_executed} s used observation {step.computed_from!r} "
                f"stamped {source_t} s",
                step=step.index,
            )
    _check_chunks(trace, a)


def _check_chunks(trace: Trace, a: RunAssessment) -> None:
    groups: list[list[Step]] = []
    for step in trace.steps:
        if step.chunk is None:
            groups.append([step])
        elif groups and groups[-1][0].chunk is not None and groups[-1][0].chunk[0] == step.chunk[0]:
            groups[-1].append(step)
        else:
            groups.append([step])
    seen_ids: set[str] = set()
    for group in groups:
        first = group[0]
        if first.chunk is None:
            continue
        chunk_id, _, length = first.chunk
        if chunk_id in seen_ids:
            a.add(
                codes.CHUNK_SCHEDULE_INCONSISTENT,
                f"chunk {chunk_id!r} resumes after another chunk",
                step=first.index,
            )
        seen_ids.add(chunk_id)
        indices = [s.chunk[1] for s in group if s.chunk is not None]
        lengths = {s.chunk[2] for s in group if s.chunk is not None}
        sources = {s.computed_from for s in group}
        if indices != list(range(len(group))) or lengths != {length} or len(group) != length:
            a.add(
                codes.CHUNK_SCHEDULE_INCONSISTENT,
                f"chunk {chunk_id!r} declares length {sorted(lengths)} with indices {indices}",
                step=first.index,
            )
        if len(sources) != 1:
            a.add(
                codes.CHUNK_SCHEDULE_INCONSISTENT,
                f"chunk {chunk_id!r} actions were computed from several observations {sorted(sources)}",
                step=first.index,
            )


def _check_continuation(
    trace: Trace,
    plan: dict,
    a: RunAssessment,
    store: TraceStore,
    assessments: dict[str, RunAssessment],
) -> None:
    recorded = [s for s in trace.steps if s.provenance == "recorded"]
    if plan["continuation"] == "full_rerun":
        if recorded:
            a.add(
                codes.RECORDED_OBSERVATION_IN_FULL_RERUN,
                f"{len(recorded)} observations were reused from run {recorded[0].source_run_id!r} "
                "although the plan declares a full closed-loop rerun",
                step=recorded[0].index,
            )
        return
    source_id = plan["source_run_id"]
    activation = a.activation_step or 0
    foreign = [s for s in recorded if s.source_run_id != source_id]
    if foreign:
        a.add(
            codes.RECORDED_OBSERVATION_FROM_UNDECLARED_SOURCE,
            f"observation reused from {foreign[0].source_run_id!r}; the plan declares {source_id!r}",
            step=foreign[0].index,
        )
    affected = [s for s in recorded if s.index > activation]
    if affected:
        a.add(
            codes.AFFECTED_FUTURE_OBSERVATION_REUSED,
            f"{len(affected)} observations after the intervention at step {activation} were "
            f"reused from run {source_id!r}; the changed action must produce new future observations",
            step=affected[0].index,
        )
    if source_id not in store.runs:
        a.add(codes.SOURCE_RUN_MISSING, f"source run {source_id!r} is not in the bundle")
        return
    try:
        source = store.get(source_id)
    except (ArtifactMissing, DigestMismatch, Malformed) as error:
        a.add(codes.SOURCE_RUN_MISSING, f"source run {source_id!r} trace unavailable: {error}")
        return
    source_assessment = assessments.get(source_id)
    if source_assessment is not None:
        if source_assessment.condition_id != a.condition_id:
            a.add(
                codes.PREFIX_REUSE_CONDITION_MISMATCH,
                f"source run condition {source_assessment.condition_id!r} differs from {a.condition_id!r}",
            )
        elif (
            source_assessment.initial_state_digest
            and a.initial_state_digest
            and source_assessment.initial_state_digest != a.initial_state_digest
        ):
            a.add(
                codes.PREFIX_REUSE_CONDITION_MISMATCH,
                "reset state digests differ from the source run",
            )
    for step in trace.steps[: min(activation, len(source.steps))]:
        if step.executed != source.steps[step.index].executed:
            a.add(
                codes.DIVERGENCE_PRECEDES_ACTIVATION,
                f"executed action differs from the source run before the declared activation {activation}",
                step=step.index,
            )
            break
    for step in recorded:
        if step.source_step is None or step.source_step >= len(source.steps):
            a.add(
                codes.RECORDED_OBSERVATION_FROM_UNDECLARED_SOURCE,
                "source step out of range",
                step=step.index,
            )
        elif source.steps[step.source_step].obs_id != step.obs_id:
            a.add(
                codes.RECORDED_OBSERVATION_FROM_UNDECLARED_SOURCE,
                f"observation {step.obs_id!r} is not the source run's observation at step {step.source_step}",
                step=step.index,
            )


def _check_candidate(trace: Trace, case: Case, a: RunAssessment) -> None:
    candidate = a.candidate
    if candidate is None or a.role == "probe":
        return
    if a.revision_role != "changed":
        a.add(
            codes.CANDIDATE_NOT_ON_CHANGED_REVISION, "a repair is tested on the changed deployment"
        )
    if candidate["deployable"] is False:
        a.add(codes.CANDIDATE_OUTSIDE_REPAIR_SCOPE, "candidate is declared not deployable")
    elif candidate["deployable"] is None:
        if case.strict:
            a.add(
                codes.CANDIDATE_DEPLOYABILITY_UNDECLARED,
                "the producer did not declare whether this candidate is deployable",
            )
        else:
            a.add(
                codes.CANDIDATE_DEPLOYABILITY_ASSUMED,
                "deployability is not declared by the producer; assumed for this legacy record",
            )
    for component in candidate["components"]:
        label = f"{component['kind']} {component['path'] or ''}".strip()
        if component["role"] == "diagnostic_oracle":
            a.add(
                codes.DIAGNOSTIC_ORACLE_IN_CANDIDATE, f"component {label!r} is a diagnostic oracle"
            )
        if case.allowed_component_kinds and component["kind"] not in case.allowed_component_kinds:
            a.add(
                codes.CANDIDATE_OUTSIDE_REPAIR_SCOPE,
                f"component kind {component['kind']!r} is not allowed",
            )
        if case.allowed_paths and component["path"] is not None:
            if not any(component["path"].startswith(prefix) for prefix in case.allowed_paths):
                a.add(
                    codes.CANDIDATE_OUTSIDE_REPAIR_SCOPE,
                    f"path {component['path']!r} is outside the scope",
                )
    oracle_steps = [s.index for s in trace.steps if s.obs_source == ORACLE_SOURCE]
    if oracle_steps:
        a.add(
            codes.DIAGNOSTIC_ORACLE_IN_CANDIDATE,
            f"{len(oracle_steps)} observations came from an oracle source",
            step=oracle_steps[0],
        )


def _series(trace: Trace, measure: str, unit: str, a: RunAssessment) -> list[float] | None:
    declared = trace.units.get(measure)
    if declared is None:
        a.add(codes.MEASUREMENT_UNIT_UNDECLARED, f"trace declares no unit for {measure!r}")
        return None
    if declared != unit:
        a.add(
            codes.MALFORMED_RECORD,
            f"measurement {measure!r} is recorded in {declared!r}; the predicate needs {unit!r}",
            path=f"trace.measurement_units.{measure}",
        )
        return None
    values = []
    for step in trace.steps:
        if measure not in step.measurements:
            a.add(codes.PREDICATE_UNMEASURABLE, f"{measure!r} is not measured", step=step.index)
            return None
        value = step.measurements[measure]
        if value is None:
            a.add(
                codes.PREDICATE_UNMEASURABLE,
                f"{measure!r} missing: {step.missing.get(measure)}",
                step=step.index,
            )
            return None
        values.append(value)
    return values


def _threshold_status(pred: Threshold, values: list[float]) -> tuple[bool, int | None]:
    checks = [pred.holds(v) for v in values]
    match pred.when:
        case "final":
            return checks[-1], (None if checks[-1] else len(values) - 1)
        case "any":
            return any(checks), None
        case _:
            first_bad = next((i for i, ok in enumerate(checks) if not ok), None)
            return first_bad is None, first_bad


def _check_predicates(trace: Trace, case: Case, a: RunAssessment) -> None:
    values = _series(trace, case.outcome.measure, case.outcome.unit, a)
    if values is not None:
        ok, step = _threshold_status(case.outcome, values)
        a.outcome = "completed" if ok else "failed"
        a.metrics["outcome_final_value"] = values[-1]
        if not ok:
            a.add(
                codes.OUTCOME_FAILED,
                f"{case.outcome.id}: {case.outcome.measure} {case.outcome.op} "
                f"{case.outcome.threshold} {case.outcome.unit} does not hold ({values[-1]} at end)",
                step=step,
            )
    progress = case.progress
    values = _series(trace, progress.measure, progress.unit, a)
    if values is not None:
        gain = values[-1] - values[0]
        a.metrics["progress_gain"] = round(gain, 9)
        a.metrics["progress_peak_gain"] = round(max(values) - values[0], 9)
        lost = []
        if gain < progress.minimum_gain:
            lost.append(
                f"gain {gain:.4g} {progress.unit} is below the minimum {progress.minimum_gain}"
            )
        activation = a.activation_step
        if activation is not None and 0 < activation < len(values):
            if values[-1] < values[activation] - progress.activation_tolerance:
                lost.append(
                    f"{progress.measure} fell from {values[activation]} at activation step {activation} "
                    f"to {values[-1]} at the end"
                )
        a.progress = "lost" if lost else "preserved"
        for detail in lost:
            a.add(codes.PROGRESS_LOST, f"{progress.id}: {detail}")
    statuses = []
    for constraint in case.constraints:
        values = _series(trace, constraint.measure, constraint.unit, a)
        if values is None:
            statuses.append("unknown")
            continue
        ok, step = _threshold_status(constraint, values)
        statuses.append("satisfied" if ok else "violated")
        if not ok:
            a.add(
                codes.CONSTRAINT_VIOLATED,
                f"{constraint.id}: {constraint.measure} {constraint.op} {constraint.threshold} "
                f"{constraint.unit} violated ({values[step]})",
                step=step,
            )
    if "violated" in statuses:
        a.constraints = "violated"
    elif "unknown" in statuses:
        a.constraints = "unknown"
    else:
        a.constraints = "satisfied"
    _check_timing(trace, case, a)


def _check_timing(trace: Trace, case: Case, a: RunAssessment) -> None:
    by_id = {s.obs_id: s for s in trace.steps}
    periods = [
        (trace.steps[i + 1].obs_t - trace.steps[i].obs_t, i + 1)
        for i in range(len(trace.steps) - 1)
    ]
    violations = []
    if periods:
        max_period, period_step = max(periods)
        a.metrics["max_step_period_s"] = round(max_period, 9)
        if max_period > case.timing.max_step_period_s:
            violations.append(
                (
                    f"step period {max_period:.4g} s exceeds {case.timing.max_step_period_s} s",
                    period_step,
                )
            )
    ages: list[tuple[float, int]] = []
    unmeasured = 0
    # Acquisition sequence numbers must advance along the acquired stream, in step order.
    # A consumer may legitimately read an older packet later; that is measured as age.
    last_sequence: dict[str, int] = {}
    if case.timing.evidence == "acquisition_stamps":
        for step in trace.steps:
            if step.capture is None:
                continue
            for name, component in step.capture["components"].items():
                previous = last_sequence.get(name)
                if previous is not None and component["sequence"] < previous:
                    a.add(
                        codes.CAPTURE_STAMPS_INCONSISTENT,
                        f"component {name!r} acquisition sequence went backwards in the acquired stream",
                        step=step.index,
                    )
                last_sequence[name] = component["sequence"]
    for step in trace.steps:
        source = by_id.get(step.computed_from)
        if source is None:
            continue
        if case.timing.evidence == "acquisition_stamps":
            if source.capture is None:
                unmeasured += 1
                continue
            components = source.capture["components"]
            oldest = min(c["simulation_s"] for c in components.values())
            if abs(oldest - source.obs_t) > 1e-9:
                a.add(
                    codes.CAPTURE_STAMPS_INCONSISTENT,
                    f"observation {source.obs_id!r} is stamped {source.obs_t} s but its oldest "
                    f"component was acquired at {oldest} s",
                    step=step.index,
                )
            for name, component in components.items():
                if component["simulation_s"] > step.t_executed + 1e-12:
                    a.add(
                        codes.OBSERVATION_AFTER_ACTION,
                        f"component {name!r} was acquired at {component['simulation_s']} s, after the "
                        f"action executed at {step.t_executed} s",
                        step=step.index,
                    )
                if component["host_finished_s"] < component["host_started_s"]:
                    a.add(
                        codes.CAPTURE_STAMPS_INCONSISTENT,
                        f"component {name!r} finished acquisition before it started",
                        step=step.index,
                    )
            received = source.capture.get("received_host_s")
            if received is not None:
                latest_finish = max(c["host_finished_s"] for c in components.values())
                if received < latest_finish:
                    a.add(
                        codes.CAPTURE_STAMPS_INCONSISTENT,
                        "observation was received before its last component finished acquisition",
                        step=step.index,
                    )
                if step.host is not None:
                    order = [received] + [
                        step.host[key]
                        for key in ("inference_started_s", "inference_finished_s", "executed_s")
                        if key in step.host
                    ]
                    if any(
                        later < earlier for earlier, later in zip(order, order[1:], strict=False)
                    ):
                        a.add(
                            codes.CAPTURE_STAMPS_INCONSISTENT,
                            "host stamps for receipt, inference and execution are out of order",
                            step=step.index,
                        )
            if step.t_executed >= oldest:
                ages.append((step.t_executed - oldest, step.index))
        elif step.t_executed >= source.obs_t:
            ages.append((step.t_executed - source.obs_t, step.index))
    if unmeasured:
        a.add(
            codes.TIMING_UNMEASURED,
            f"{unmeasured} of {len(trace.steps)} consumed observations carry no acquisition stamps; "
            "observation age cannot be measured from assigned step times",
        )
    if ages:
        max_age, age_step = max(ages)
        a.metrics["max_observation_age_s"] = round(max_age, 9)
        if max_age > case.timing.max_observation_age_s:
            violations.append(
                (
                    f"observation age {max_age:.4g} s exceeds {case.timing.max_observation_age_s} s",
                    age_step,
                )
            )
    if violations:
        a.timing = "violated"
    elif unmeasured:
        a.timing = "unmeasured"
    elif ages or periods:
        a.timing = "satisfied"
    for detail, step in violations:
        a.add(codes.TIMING_OBLIGATION_VIOLATED, f"{case.timing.id}: {detail}", step=step)


def assess_run(
    run: dict,
    case: Case,
    store: TraceStore,
    assessments: dict[str, RunAssessment],
    known_synthetic_digests: frozenset[str] = frozenset(),
) -> RunAssessment:
    run_id = run.get("id") if isinstance(run.get("id"), str) else "<unidentified>"
    a = RunAssessment(run_id=run_id)
    try:
        plan = _parse_header(run, case, a)
    except Malformed as error:
        a.add(codes.MALFORMED_RECORD, error.detail, path=error.path)
        return a.finalize()
    for item in run.get("_adapter_findings") or []:
        a.findings.append(
            Finding(
                item["code"],
                item["detail"],
                run_id=run_id,
                step=item.get("step"),
                path=item.get("path"),
            )
        )
    if a.process != "completed":
        a.add(codes.PROCESS_INCOMPLETE, f"process status {a.process!r}; the trace may be partial")
    try:
        trace = store.get(run_id)
    except ArtifactMissing as error:
        a.add(codes.ARTIFACT_MISSING, f"trace artifact {error} is absent from the artifact root")
        return a.finalize()
    except DigestMismatch as error:
        a.add(codes.ARTIFACT_DIGEST_MISMATCH, str(error))
        return a.finalize()
    except Malformed as error:
        a.add(codes.MALFORMED_RECORD, error.detail, path=error.path)
        return a.finalize()
    a.trace_digest = trace.digest
    if a.evidence_origin in {"simulator", "hardware"} and trace.digest in known_synthetic_digests:
        a.add(
            codes.SYNTHETIC_PRESENTED_AS_MEASUREMENT,
            f"trace bytes match a synthetic development fixture but the run claims {a.evidence_origin!r}",
        )
    _check_structure(trace, a)
    _check_continuation(trace, plan, a, store, assessments)
    _check_candidate(trace, case, a)
    _check_predicates(trace, case, a)
    if a.process != "completed":
        a.outcome = "unknown"
        a.progress = "unknown"
        if a.constraints == "satisfied":
            a.constraints = "unknown"
    if a.outcome_claimed and a.outcome != "unknown" and a.outcome_claimed != a.outcome:
        a.add(
            codes.PRODUCER_CLAIM_DISAGREES,
            f"producer claimed {a.outcome_claimed!r}; measurements show {a.outcome!r}",
        )
    a.finalize()
    if a.validity_claimed == "valid" and a.measurement != "valid":
        a.add(
            codes.PRODUCER_VALIDITY_CLAIM_IGNORED,
            f"producer claimed a valid experiment; the record supports {a.measurement!r}",
        )
    return a
