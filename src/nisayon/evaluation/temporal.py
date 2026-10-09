"""Reference assessment of asynchronous action-chunk traces: a small pure state machine.

A trace records, in producer order, what a controller did while inference and execution
overlapped: observations acquired, requests sent, responses arrived, chunks admitted to a
queue, actions dispatched and acknowledged, resets and configuration changes. This module
replays the events into an inspectable state and reports, per predicate, whether the
temporal contract was satisfied, violated or left unresolved by the evidence. It is written
independently of any executor and shares only the event schema with the execution lane;
the producer's own guard fields (``age_guard``) are never read.

What the model can and cannot say. Identity equality (episode generation, request,
configuration activation) is decided from recorded identities and recorded transitions;
deadline satisfaction is decided from recorded times within one clock or through a
declared mapping with uncertainty, in exact arithmetic; useful execution is a software
dispatch-coverage measure, read both on this lane's frozen tick grid and on the producer's
frozen opportunity contract. None of these is robot task success, which this module never
measures. A dispatched action is a software send attempt; an acknowledgement is what the
producer recorded for that attempt, not physical actuation.

Version 2 (20 September 2026) corrects four readings of the version-1 implementation
against the frozen contracts and adds two separately named retrospective readings.
Version 3 (later the same day) closes the clock-declaration boundary: declarations are
parsed once into a ``ClockModel`` with an explicit supported domain, a clock pair declared
twice with different relations is conflicting evidence whatever the list order, malformed
declarations are named problems that never raise, unsupported or undeclared clocks leave
freshness unresolved, and a queued action keeps the chunk identity it was admitted with.
See ``ASSESSMENT_CHANGES`` and docs/evaluation/results/temporal-integration-001/followthrough/.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction

SCHEMA = "nisayon.temporal-trace.v1"
ASSESSMENT_SCHEMA = "nisayon.temporal-assessment.v3"
ASSESSMENT_CHANGES = (
    "v3: clock declarations are parsed into a model with an explicit supported domain (one "
    "direct unit-rate constant-offset relation per clock pair); a pair declared with "
    "different relations is conflicting evidence in any order and leaves freshness "
    "unresolved unless same-clock chain evidence proves expiry",
    "v3: malformed clock containers and members are named trace problems (invalid, never an "
    "exception); unsupported declaration fields, unit mismatches and undeclared clocks "
    "leave the pair unmapped and freshness unresolved; legacy forms are named rules",
    "v3: a queued action keeps the chunk identity it was admitted with; a different "
    "response under the same chunk id is a conflict resolved by the producer's admission "
    "decision and reported under retrospective chunk_identity",
    "configuration_binding follows the activation context derived from recorded "
    "configuration_changed transitions (a content hash that returns is a new context)",
    "acknowledgement binds to the send attempt (dispatch_id), not to the action id",
    "freshness adjudicates chronology explicitly: a mapped interval admitting negative ages "
    "is unresolved unless same-clock chain evidence bounds the age from below",
    "age and grid arithmetic are exact (no float conversion of stamps)",
    "assigned_usefulness reads the producer's frozen whole-case opportunity contract; "
    "useful_execution keeps the version-1 grid meaning under its original name",
    "retrospective chunk_target_alignment and observation_context are reported outside the "
    "frozen nine-predicate contract",
)
PREDICATES = (
    "generation_fencing",
    "request_binding",
    "configuration_binding",
    "queue_reset",
    "duplicate_dispatch",
    "dispatch_order",
    "freshness",
    "acknowledgement",
    "useful_execution",
)
STATUSES = ("satisfied", "violated", "unresolved")
USEFUL_COVERAGE_MIN = 0.8  # frozen in temporal-integration-001/spec.json; the evaluator's threshold
EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "episode_start": ("generation",),
    "reset_requested": ("generation_from", "generation_to"),
    "reset_completed": ("generation",),
    "observation_acquired": ("obs_id", "generation", "step"),
    "request_sent": ("req_id", "obs_id", "generation", "config_sha256"),
    "inference_started": ("req_id",),
    "inference_ended": ("req_id",),
    "response_arrived": ("resp_id", "chunk_id", "first_step", "ordinals"),
    "queue_admitted": ("chunk_id", "admitted"),
    "action_dispatched": ("action_id", "chunk_id", "ordinal", "step", "generation"),
    "dispatch_acknowledged": ("action_id",),
    "dispatch_failed": ("action_id",),
    "cancellation_requested": ("target",),
    "dispatch_refused": ("reason",),
    "configuration_changed": ("from_sha256", "to_sha256"),
    "evidence_gap": ("what",),
}
ATTEMPT_OUTCOMES = (
    "acknowledged",
    "failed",
    "unacknowledged",
    "conflicting",
    "ambiguous_legacy",
)


@dataclass
class Finding:
    predicate: str
    status: str
    detail: str
    seq: int | None = None
    witness: dict | None = None

    def to_dict(self) -> dict:
        data = {"predicate": self.predicate, "status": self.status, "detail": self.detail}
        if self.seq is not None:
            data["seq"] = self.seq
        if self.witness is not None:
            data["witness"] = self.witness
        return data


@dataclass
class Chunk:
    chunk_id: str
    req_id: str | None
    generation: int | None
    generation_source: str
    config_sha256: str | None
    acquired_at: dict | None
    arrived_at: dict | None
    first_step: int | None
    ordinals: int
    activation: int | None = None
    obs_activation: int | None = None
    obs_step: int | None = None
    held_at: Fraction | None = None  # earliest controller-clock evidence the observation existed
    asserted_config_sha256: str | None = None
    assertion_conflict: bool = False  # the response's own assertions contradict its request
    delivery_id: str | None = None
    seq: int | None = None

    def identity(self) -> tuple:
        """What a repeated delivery must repeat: the bound request, generation, configuration
        and shape. A delivery with the same chunk id and a different identity is a conflict."""
        return (
            self.req_id,
            self.generation,
            self.config_sha256,
            self.asserted_config_sha256,
            self.first_step,
            self.ordinals,
        )

    @property
    def bound(self) -> bool:
        """True when the response named a recorded request; a named but unrecorded request
        leaves the chunk unbound, as does a missing request id."""
        return self.generation_source == "request"


@dataclass
class Attempt:
    """One software send attempt: an action_dispatched event and what answered it."""

    key: str
    dispatch_id: str | None
    action_id: str
    chunk_id: str
    input_id: str | None
    seq: int
    at: dict | None
    generation: int | None
    step: int | None
    acknowledgements: int = 0
    failures: int = 0
    ambiguous: bool = False
    validity: dict = field(default_factory=dict)

    @property
    def outcome(self) -> str:
        if self.ambiguous:
            return "ambiguous_legacy"
        if self.failures and self.acknowledgements:
            return "conflicting"
        if self.failures:
            return "failed"
        if self.acknowledgements:
            return "acknowledged"
        return "unacknowledged"

    def to_dict(self) -> dict:
        return {
            "attempt": self.key,
            "dispatch_id": self.dispatch_id,
            "action_id": self.action_id,
            "input_id": self.input_id,
            "seq": self.seq,
            "outcome": self.outcome,
            "acknowledgements": self.acknowledgements,
            "failures": self.failures,
            "validity": dict(self.validity),
        }


# --- exact numbers -------------------------------------------------------------------------


def exact(value: object) -> Fraction | None:
    """The exact value of a numeric field: integers exactly, floats at their binary value.

    Booleans, non-finite floats and non-numbers are None. Nothing is rounded; a float input
    is supported at the value it actually holds and is flagged by the caller.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, Fraction)):
        return Fraction(value)
    if isinstance(value, float) and math.isfinite(value):
        return Fraction(value)
    return None


def number(value: Fraction | int | float | None) -> int | float | str | None:
    """JSON form of an exact number: an int when integral, else the exact fraction text."""
    if value is None:
        return None
    if isinstance(value, float):
        return value
    frac = Fraction(value)
    return int(frac) if frac.denominator == 1 else f"{frac.numerator}/{frac.denominator}"


def _stamp_value(stamp: object) -> Fraction | None:
    if not isinstance(stamp, dict):
        return None
    if not isinstance(stamp.get("clock"), str) or not isinstance(stamp.get("unit"), str):
        return None
    return exact(stamp.get("value"))


# --- clocks ------------------------------------------------------------------------------

DECLARATION_FIELDS = ("from", "to", "offset", "uncertainty", "unit")
CLOCK_CATEGORIES = (
    "same_clock",
    "mapped",
    "unmapped",
    "malformed_declarations",
    "conflicting_declarations",
    "unsupported_declaration",
    "unit_mismatch",
    "undeclared_clock",
    "absent_acquisition",
    "unstamped",
    "mapping_contradicts_chain",
)


@dataclass
class Relation:
    """One supported clock relation over the case horizon.

    ``t_b`` lies in ``[t_a + offset - uncertainty, t_a + offset + uncertainty]`` with ``a < b``
    in name order; a declaration written in the other direction is stored negated. Unit rate
    and constant offset are the only supported model.
    """

    a: str
    b: str
    offset: Fraction
    uncertainty: Fraction
    unit: str
    declarations: list[int] = field(default_factory=list)

    def same(self, other: Relation) -> bool:
        return (
            self.offset == other.offset
            and self.uncertainty == other.uncertainty
            and self.unit == other.unit
        )


@dataclass
class ClockModel:
    """The declared clocks of a trace, parsed once, with every defect named.

    Supported domain. ``clocks`` is an object with ``names`` (a non-empty list of distinct
    strings whose first member is the controller clock) and ``declared_mappings`` (a list,
    possibly empty). Each declaration is an object with exactly the fields ``from``, ``to``,
    ``offset``, ``uncertainty`` and ``unit``: two distinct declared clock names, a finite
    non-Boolean offset, a finite non-Boolean uncertainty that is not negative, and a unit
    string. At most one relation per unordered clock pair is supported; an exact repeat of
    a relation counts once, and any other second declaration for the pair makes the pair
    ``conflicting``: the record grants no priority, so neither a jointly consistent
    calibration (their exact intervals differ) nor a fresh verdict over alternatives (both
    ages would have to lie within the limit) can be established. Only direct relations
    are used; no composition through a third clock, no rate, drift, validity interval or
    selection field.

    Legacy forms, named. ``clocks`` absent, or ``names`` absent: the controller clock is the
    clock literally named ``controller`` and no other clock is declared, so a stamp on any
    other clock is ``undeclared``. Malformed containers and members are trace problems;
    unsupported declarations are diagnostics that leave their pair unmapped.
    """

    controller: str = "controller"
    names: list[str] | None = None
    relations: dict[tuple[str, str], Relation] = field(default_factory=dict)
    conflicting: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    unsupported_pairs: set[tuple[str, str]] = field(default_factory=set)
    diagnostics: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    legacy: str | None = None
    undeclared: list[str] = field(default_factory=list)
    declare_all: bool = False  # ad hoc API use without a names list: any clock name is fine
    malformed: bool = False  # a malformed member disabled every relation of the list

    @property
    def status(self) -> str:
        if self.problems:
            return "malformed"
        if self.conflicting:
            return "conflicting"
        if self.unsupported_pairs or self.undeclared:
            return "unsupported"
        if self.legacy:
            return "legacy"
        return "supported"

    def declared(self, clock: str) -> bool:
        if self.declare_all:
            return True
        if self.names is None:
            return clock == self.controller
        return clock in self.names

    def note_clock(self, clock: object) -> None:
        """Record a stamp on a clock the trace never declared (once per clock name)."""
        if isinstance(clock, str) and not self.declared(clock) and clock not in self.undeclared:
            self.undeclared.append(clock)
            self.diagnostics.append(
                {
                    "category": "undeclared_clock",
                    "detail": f"stamps name clock {clock!r}, which clocks.names does not declare",
                }
            )

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "controller": self.controller,
            "names": self.names,
            "legacy_rule": self.legacy,
            "relations": [
                {
                    "a": r.a,
                    "b": r.b,
                    "offset": number(r.offset),
                    "uncertainty": number(r.uncertainty),
                    "unit": r.unit,
                    "declarations": list(r.declarations),
                }
                for r in self.relations.values()
            ],
            "conflicting_pairs": [list(pair) for pair in self.conflicting],
            "unsupported_pairs": [list(pair) for pair in sorted(self.unsupported_pairs)],
            "undeclared_clocks": list(self.undeclared),
            "diagnostics": list(self.diagnostics),
            "problems": list(self.problems),
            "supported_domain": "one direct unit-rate constant-offset relation per clock pair "
            "with exact offset and nonnegative uncertainty in the stamps' unit; no priority, "
            "validity interval, rate, drift, selection or composition",
        }


def _pair(x: str, y: str) -> tuple[str, str]:
    return (x, y) if x <= y else (y, x)


def parse_declaration(index: int, item: object, model: ClockModel) -> Relation | None:
    """Validate one declared mapping; a defect is named on the model and yields None."""
    where = f"clocks.declared_mappings[{index}]"
    if not isinstance(item, dict):
        model.problems.append(f"{where} is not an object")
        return None
    keys = set(item)
    missing = [f for f in DECLARATION_FIELDS if f not in keys]
    if missing:
        model.problems.append(f"{where} lacks {missing}")
        return None
    extra = sorted(keys - set(DECLARATION_FIELDS))
    src, dst, unit = item["from"], item["to"], item["unit"]
    if not isinstance(src, str) or not isinstance(dst, str) or not isinstance(unit, str):
        model.problems.append(f"{where} from, to and unit must be strings")
        return None
    if src == dst:
        model.problems.append(f"{where} relates clock {src!r} to itself")
        return None
    offset, uncertainty = exact(item["offset"]), exact(item["uncertainty"])
    if offset is None or uncertainty is None:
        model.problems.append(f"{where} offset and uncertainty must be finite non-Boolean numbers")
        return None
    if uncertainty < 0:
        model.problems.append(f"{where} uncertainty {number(uncertainty)} is negative")
        return None
    pair = _pair(src, dst)
    if extra:
        model.unsupported_pairs.add(pair)
        model.diagnostics.append(
            {
                "category": "unsupported_declaration",
                "index": index,
                "detail": f"{where} carries unsupported field(s) {extra}; the relation is not "
                "used because its premise cannot be verified",
            }
        )
        return None
    undeclared = [c for c in (src, dst) if not model.declared(c)]
    if undeclared:
        model.unsupported_pairs.add(pair)
        model.diagnostics.append(
            {
                "category": "unsupported_declaration",
                "index": index,
                "detail": f"{where} names undeclared clock(s) {undeclared}",
            }
        )
        return None
    if src <= dst:
        return Relation(src, dst, offset, uncertainty, unit, [index])
    return Relation(dst, src, -offset, uncertainty, unit, [index])


def parse_clocks(trace: dict) -> ClockModel:
    """Parse ``trace["clocks"]`` into a ClockModel without raising on any shape."""
    model = ClockModel()
    clocks = trace.get("clocks")
    if clocks is None:
        model.legacy = "clocks_absent: the controller clock is the clock named 'controller'"
        return model
    if not isinstance(clocks, dict):
        model.problems.append("clocks is not an object")
        model.legacy = "clocks_malformed: the controller clock is the clock named 'controller'"
        return model
    names = clocks.get("names")
    if names is None:
        model.legacy = "names_absent: the controller clock is the clock named 'controller'"
    elif (
        not isinstance(names, list)
        or not names
        or not all(isinstance(n, str) for n in names)
        or len(set(names)) != len(names)
    ):
        model.problems.append("clocks.names is not a non-empty list of distinct strings")
        model.legacy = "names_malformed: the controller clock is the clock named 'controller'"
    else:
        model.names = list(names)
        model.controller = names[0]
    declared = clocks.get("declared_mappings")
    if declared is None:
        declared = []
    if not isinstance(declared, list):
        model.problems.append(
            f"clocks.declared_mappings is {type(declared).__name__}, not a list; no relation is used"
        )
        return model
    member_problems = len(model.problems)
    for index, item in enumerate(declared):
        relation = parse_declaration(index, item, model)
        if relation is None:
            continue
        pair = (relation.a, relation.b)
        if pair in model.conflicting:
            model.conflicting[pair].append({"index": index, "offset": number(relation.offset)})
            continue
        held = model.relations.get(pair)
        if held is None:
            model.relations[pair] = relation
        elif held.same(relation):
            held.declarations.append(index)
            model.diagnostics.append(
                {
                    "category": "duplicate_declaration",
                    "index": index,
                    "detail": f"clocks.declared_mappings[{index}] repeats the relation of "
                    f"[{held.declarations[0]}] exactly; counted once",
                }
            )
        else:
            model.conflicting[pair] = [
                {"index": i, "offset": number(held.offset)} for i in held.declarations
            ] + [{"index": index, "offset": number(relation.offset)}]
            del model.relations[pair]
            model.diagnostics.append(
                {
                    "category": "conflicting_declarations",
                    "index": index,
                    "detail": f"clocks.declared_mappings[{index}] declares {pair[0]}/{pair[1]} "
                    f"with offset {number(relation.offset)} ± {number(relation.uncertainty)} "
                    f"{relation.unit} while [{held.declarations[0]}] declares offset "
                    f"{number(held.offset)} ± {number(held.uncertainty)} {held.unit}; no "
                    "priority is declared, so the pair has no usable relation",
                }
            )
    if len(model.problems) > member_problems:
        # A malformed member may be the unreadable half of a conflict; no relation from a
        # malformed list is used, and the malformation is a trace problem.
        model.relations.clear()
        model.malformed = True
    return model


def _model_from(mappings: object) -> ClockModel:
    if isinstance(mappings, ClockModel):
        return mappings
    model = ClockModel(legacy="ad hoc: declarations given without a names list", declare_all=True)
    if isinstance(mappings, list):
        for index, item in enumerate(mappings):
            relation = parse_declaration(index, item, model)
            if relation is None:
                continue
            pair = (relation.a, relation.b)
            held = model.relations.get(pair)
            if held is None:
                model.relations[pair] = relation
            elif not held.same(relation):
                model.conflicting[pair] = [{"index": index}]
                del model.relations[pair]
    return model


def age_reading(
    later: dict | None, earlier: dict | None, model: ClockModel
) -> tuple[tuple[Fraction, Fraction] | None, str]:
    """The elapsed time from ``earlier`` to ``later`` as an exact interval and its category.

    Same clock and unit: the exact difference. Different clocks: only through the one
    supported relation for the pair, ``t_b = t_a + offset ± uncertainty`` in the stamps'
    unit. Anything else is named and unknown, never guessed: a conflicting pair, an
    unsupported declaration, a unit mismatch, an undeclared clock, or no relation at all.
    """
    if earlier is None:
        return None, "absent_acquisition"
    later_value, earlier_value = _stamp_value(later), _stamp_value(earlier)
    if later_value is None or earlier_value is None:
        return None, "unstamped"
    assert isinstance(later, dict) and isinstance(earlier, dict)
    if later["unit"] != earlier["unit"]:
        return None, "unit_mismatch"
    if later["clock"] == earlier["clock"]:
        delta = later_value - earlier_value
        return (delta, delta), "same_clock"
    for clock in (later["clock"], earlier["clock"]):
        if not model.declared(clock):
            return None, "undeclared_clock"
    if model.malformed:
        return None, "malformed_declarations"
    pair = _pair(later["clock"], earlier["clock"])
    if pair in model.conflicting:
        return None, "conflicting_declarations"
    relation = model.relations.get(pair)
    if relation is None:
        if pair in model.unsupported_pairs:
            return None, "unsupported_declaration"
        return None, "unmapped"
    if relation.unit != later["unit"]:
        return None, "unit_mismatch"
    # t_b = t_a + offset ± u with a = pair[0]; express later - earlier through it.
    if earlier["clock"] == relation.a:
        delta = later_value - (earlier_value + relation.offset)
    else:
        delta = (later_value + relation.offset) - earlier_value
    return (delta - relation.uncertainty, delta + relation.uncertainty), "mapped"


def age_interval(
    later: dict | None, earlier: dict | None, mappings: object
) -> tuple[Fraction, Fraction] | None:
    """The elapsed time from ``earlier`` to ``later`` as an exact interval, or None.

    ``mappings`` is a parsed ClockModel or a raw list of declarations. The category behind a
    None is available from ``age_reading``. No value is converted to float; a one-unit
    excess at any epoch survives the subtraction.
    """
    interval, _ = age_reading(later, earlier, _model_from(mappings))
    return interval


@dataclass
class State:
    generation: int | None = None
    config_sha256: str | None = None
    activation: int = 0  # derived: one per recorded configuration_changed event
    transitions: list[dict] = field(default_factory=list)
    activation_contradictions: list[dict] = field(default_factory=list)
    observations: dict[str, dict] = field(default_factory=dict)
    requests: dict[str, dict] = field(default_factory=dict)
    chunks: dict[str, Chunk] = field(default_factory=dict)
    queued: dict[str, dict] = field(default_factory=dict)
    dispatched: dict[str, dict] = field(default_factory=dict)
    attempts: list[Attempt] = field(default_factory=list)
    attempts_by_dispatch_id: dict[str, Attempt] = field(default_factory=dict)
    unmatched_outcomes: list[dict] = field(default_factory=list)
    steps_dispatched: dict[int, set[int]] = field(default_factory=dict)
    dispatch_ticks: dict[int, set[Fraction]] = field(default_factory=dict)
    last_step: dict[int, int] = field(default_factory=dict)
    generations_seen: list[int] = field(default_factory=list)
    generation_start: dict[int, Fraction] = field(default_factory=dict)
    generation_end: dict[int, Fraction] = field(default_factory=dict)
    first_arrival: dict[int, Fraction] = field(default_factory=dict)
    controller_clock: str = "controller"
    clocks: ClockModel = field(default_factory=ClockModel)
    pending_deliveries: dict[str, list[Chunk]] = field(default_factory=dict)
    identity_conflicts: list[dict] = field(default_factory=list)
    refusals: list[dict] = field(default_factory=list)
    opportunities: dict[int, dict[str, int]] = field(default_factory=dict)
    opportunity_events: list[dict] = field(default_factory=list)
    repeated_deliveries: list[dict] = field(default_factory=list)
    stale_overwrites: list[dict] = field(default_factory=list)
    strict_admissions: list[dict] = field(default_factory=list)
    request_order: dict[str, int] = field(default_factory=dict)
    survivors_at_reset: dict[int, list[str]] = field(default_factory=dict)
    survivors_at_first_dispatch: dict[int, list[str]] = field(default_factory=dict)
    last_time: Fraction | None = None
    age_readings: list[dict] = field(default_factory=list)
    alignment: list[Finding] = field(default_factory=list)
    observation_context: list[Finding] = field(default_factory=list)
    non_integer_stamps: bool = False
    unknowns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generation": self.generation,
            "config_sha256": self.config_sha256,
            "activation": self.activation,
            "queued_action_ids": sorted(self.queued),
            "dispatched_action_ids": sorted(self.dispatched),
            "chunks": {
                cid: {
                    "req_id": c.req_id,
                    "generation": c.generation,
                    "generation_source": c.generation_source,
                    "config_sha256": c.config_sha256,
                    "activation": c.activation,
                }
                for cid, c in self.chunks.items()
            },
            "steps_dispatched": {str(g): sorted(s) for g, s in self.steps_dispatched.items()},
            "unknowns": list(self.unknowns),
        }


def classify_age(interval: tuple | None, max_age: object) -> str:
    """Frozen boundary rule: an age equal to the limit is within it.

    ``inconsistent``: the whole interval is negative, so the acquisition lies after the
    dispatch under the declared relation, which no consistent clock relation permits.
    ``chronology_unresolved``: the interval admits negative and nonnegative ages, so the
    declared relation alone does not order acquisition before dispatch; the age is not
    clamped to zero. Callers narrow such an interval with same-clock chain evidence first.
    """
    limit = exact(max_age)
    if interval is None or limit is None:
        return "unknown"
    low, high = interval
    if high < 0:
        return "inconsistent"
    if low < 0:
        return "chronology_unresolved"
    if high <= limit:
        return "within"
    if low > limit:
        return "beyond"
    return "overlapping"


# --- replay ------------------------------------------------------------------------------


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def assess(trace: dict) -> dict:
    """Replay a trace and assess every predicate; never raises on a malformed trace."""
    findings: list[Finding] = []
    state = State()
    problems: list[str] = []
    if not isinstance(trace, dict) or trace.get("schema") != SCHEMA:
        problems.append(f"schema is not {SCHEMA}")
        return _assessment(trace if isinstance(trace, dict) else {}, state, findings, problems)
    # The first declared clock is the controller's; generation windows and dispatch ticks
    # are measured in it. Every defect of the clock declarations is named on the model.
    state.clocks = parse_clocks(trace)
    state.controller_clock = state.clocks.controller
    problems.extend(state.clocks.problems)
    mappings = state.clocks
    configuration = (
        trace.get("configuration") if isinstance(trace.get("configuration"), dict) else {}
    )
    max_age = exact(configuration.get("max_age"))
    control_period = exact(configuration.get("control_period"))
    coverage_min = configuration.get("useful_coverage_min", USEFUL_COVERAGE_MIN)
    state.config_sha256 = (
        configuration.get("config_sha256")
        if isinstance(configuration.get("config_sha256"), str)
        else None
    )
    events = trace.get("events")
    if not isinstance(events, list):
        problems.append("events is not a list")
        return _assessment(trace, state, findings, problems)
    last_seq = None
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            problems.append(f"events[{index}] is not an object")
            continue
        seq, kind = _int(event.get("seq")), event.get("kind")
        if seq is None or (last_seq is not None and seq <= last_seq):
            problems.append(f"events[{index}] seq {event.get('seq')!r} is not increasing")
        last_seq = seq if seq is not None else last_seq
        if kind not in EVENT_FIELDS:
            problems.append(f"events[{index}] kind {kind!r} is unknown")
            continue
        missing = [f for f in EVENT_FIELDS[kind] if f not in event]
        if missing:
            problems.append(f"events[{index}] {kind} lacks {missing}")
            continue
        _apply(event, state, findings, mappings, max_age)
    _close(state, findings, control_period, coverage_min)
    return _assessment(trace, state, findings, problems, control_period)


def _controller_time(at: object, controller_clock: str = "controller") -> Fraction | None:
    if isinstance(at, dict) and at.get("clock") == controller_clock:
        return exact(at.get("value"))
    return None


def _check_activation(event: dict, state: State) -> None:
    """Validate an asserted activation counter against the transitions actually recorded."""
    asserted = event.get("activation")
    if "activation" in event and _int(asserted) is not None and asserted != state.activation:
        state.activation_contradictions.append(
            {
                "seq": event["seq"],
                "kind": event["kind"],
                "asserted": asserted,
                "derived": state.activation,
            }
        )


def _apply(
    event: dict,
    state: State,
    findings: list[Finding],
    mappings: list[dict],
    max_age: Fraction | None,
) -> None:
    kind, seq, at = event["kind"], event["seq"], event.get("at")
    if isinstance(at, dict) and isinstance(at.get("value"), float):
        state.non_integer_stamps = True
    for stamp in (at, event.get("observed_by_driver_at")):
        if isinstance(stamp, dict):
            state.clocks.note_clock(stamp.get("clock"))
    now = _controller_time(at, state.controller_clock)
    if now is not None:
        state.last_time = now
    if kind == "episode_start":
        _check_activation(event, state)
        generation = _int(event["generation"])
        state.generation = generation
        if generation is not None and generation not in state.generations_seen:
            state.generations_seen.append(generation)
        if generation is not None and now is not None:
            state.generation_start.setdefault(generation, now)
    elif kind == "reset_requested":
        pass  # a request is not a completion; the queue is judged at reset_completed
    elif kind == "reset_completed":
        generation = _int(event["generation"])
        survivors = sorted(state.queued)
        declared = event.get("queued_at_reset")
        if isinstance(declared, list) and sorted(str(x) for x in declared) != survivors:
            findings.append(
                Finding(
                    "queue_reset",
                    "unresolved",
                    f"producer declares queued_at_reset {declared} but the replay holds {survivors}",
                    seq,
                )
            )
        # Actions queued before the reset that survive into the new generation are judged
        # when dispatched; their presence alone is recorded here.
        previous = state.generation
        if previous is not None and now is not None:
            state.generation_end.setdefault(previous, now)
        state.generation = generation
        if generation is not None and generation not in state.generations_seen:
            state.generations_seen.append(generation)
        if generation is not None and now is not None:
            state.generation_start.setdefault(generation, now)
        if generation is not None:
            state.survivors_at_reset[generation] = list(survivors)
        if survivors:
            findings.append(
                Finding(
                    "queue_reset",
                    "violated",
                    f"{len(survivors)} queued action(s) from before the reset remain queued after generation {generation} began: {survivors[:4]}",
                    seq,
                )
            )
    elif kind == "observation_acquired":
        _check_activation(event, state)
        state.observations[str(event["obs_id"])] = {
            "generation": _int(event["generation"]),
            "step": _int(event["step"]),
            "at": at,
            "activation": state.activation,
            # Arrival at the driver is evidence the observation already existed; it is never
            # substituted for the acquisition time itself.
            "held_at": _controller_time(event.get("observed_by_driver_at"), state.controller_clock),
        }
    elif kind == "request_sent":
        _check_activation(event, state)
        obs = state.observations.get(str(event["obs_id"]))
        state.request_order[str(event["req_id"])] = len(state.request_order)
        held = obs["held_at"] if obs else None
        if held is None or (now is not None and now < held):
            held = now
        state.requests[str(event["req_id"])] = {
            "obs_id": str(event["obs_id"]),
            "generation": _int(event["generation"]),
            "config_sha256": event["config_sha256"]
            if isinstance(event["config_sha256"], str)
            else None,
            "acquired_at": obs["at"] if obs else None,
            "obs_activation": obs["activation"] if obs else None,
            "obs_step": obs["step"] if obs else None,
            "activation": state.activation,
            "held_at": held,
            "at": at,
        }
        if obs is None:
            state.unknowns.append(f"request {event['req_id']} names an unrecorded observation")
    elif kind in ("inference_started", "inference_ended"):
        pass
    elif kind == "response_arrived":
        _on_response(event, state, findings)
    elif kind == "queue_admitted":
        _on_admission(event, state, findings)
    elif kind == "action_dispatched":
        _on_dispatch(event, state, findings, mappings, max_age)
    elif kind in ("dispatch_acknowledged", "dispatch_failed"):
        _on_outcome(event, state, findings)
    elif kind == "cancellation_requested":
        pass  # requested, not completed: the queue and dispatches decide
    elif kind == "dispatch_refused":
        # A control opportunity at which the producer refused to dispatch (a stale or
        # unbound chunk, an age gate, a stop policy): not a dispatch, not a failure. It is
        # visible through coverage and through the queue decisions it followed.
        state.refusals.append({"seq": seq, "at": at, "reason": event.get("reason")})
        state.opportunity_events.append(
            {
                "seq": seq,
                "kind": "refusal",
                "input_id": event.get("input_id"),
                "at": at,
                "attempt": None,
                "action_id": event.get("action_id"),
                "reason": event.get("reason"),
            }
        )
        if state.generation is not None:
            counts = state.opportunities.setdefault(
                state.generation, {"dispatched": 0, "refused": 0}
            )
            counts["refused"] += 1
    elif kind == "configuration_changed":
        _check_activation_transition(event, state)
        state.config_sha256 = event["to_sha256"] if isinstance(event["to_sha256"], str) else None
    elif kind == "evidence_gap":
        state.unknowns.append(f"declared gap: {event['what']} ({event.get('reason')})")


def _check_activation_transition(event: dict, state: State) -> None:
    """A configuration change opens a new activation context, whatever the content hash."""
    previous = state.config_sha256
    if (
        isinstance(event["from_sha256"], str)
        and previous is not None
        and event["from_sha256"] != previous
    ):
        state.unknowns.append(
            f"configuration_changed at seq {event['seq']} claims from {event['from_sha256'][:12]} "
            f"but the replay holds {previous[:12]}"
        )
    state.activation += 1
    _check_activation(event, state)
    state.transitions.append(
        {
            "seq": event["seq"],
            "activation": state.activation,
            "from_sha256": event["from_sha256"],
            "to_sha256": event["to_sha256"],
        }
    )


def _on_response(event: dict, state: State, findings: list[Finding]) -> None:
    seq, at = event["seq"], event.get("at")
    now = _controller_time(at, state.controller_clock)
    req_id = event.get("req_id")
    request = state.requests.get(str(req_id)) if isinstance(req_id, str) else None
    claimed_generation = _int(event.get("generation"))
    activation = obs_activation = obs_step = None
    held = None
    conflict = False
    if request is not None:
        generation, source = request["generation"], "request"
        config = request["config_sha256"]
        acquired = request["acquired_at"]
        activation, obs_activation = request["activation"], request["obs_activation"]
        obs_step, held = request["obs_step"], request["held_at"]
        asserted_config = event.get("config_sha256")
        if isinstance(asserted_config, str) and config is not None and asserted_config != config:
            conflict = True
            findings.append(
                Finding(
                    "request_binding",
                    "violated",
                    f"response {event['resp_id']} asserts configuration "
                    f"{asserted_config[:12]} but its request {req_id} was sent under "
                    f"{config[:12]}",
                    seq,
                )
            )
        if (
            claimed_generation is not None
            and generation is not None
            and claimed_generation != generation
        ):
            conflict = True
            findings.append(
                Finding(
                    "request_binding",
                    "violated",
                    f"response {event['resp_id']} claims generation {claimed_generation} but "
                    f"its request {req_id} was sent in generation {generation}",
                    seq,
                )
            )
    else:
        generation, source = (
            claimed_generation,
            "claimed" if claimed_generation is not None else "unknown",
        )
        config = event.get("config_sha256") if isinstance(event.get("config_sha256"), str) else None
        acquired = None
    chunk = Chunk(
        str(event["chunk_id"]),
        str(req_id) if isinstance(req_id, str) else None,
        generation,
        source,
        config,
        acquired,
        at,
        _int(event["first_step"]),
        _int(event["ordinals"]) or 0,
        activation,
        obs_activation,
        obs_step,
        held,
        event.get("config_sha256") if isinstance(event.get("config_sha256"), str) else None,
        conflict,
        event.get("delivery_id") if isinstance(event.get("delivery_id"), str) else None,
        seq,
    )
    if state.generation is not None and now is not None:
        state.first_arrival.setdefault(state.generation, now)
    held_chunk = state.chunks.get(chunk.chunk_id)
    if held_chunk is None:
        state.chunks[chunk.chunk_id] = chunk
    elif held_chunk.identity() == chunk.identity():
        # A repeated delivery of a known chunk is recorded; only a second admission
        # after dispatch or a second dispatch violates the predicate.
        state.repeated_deliveries.append(
            {"seq": seq, "chunk_id": chunk.chunk_id, "delivery_id": chunk.delivery_id}
        )
        state.chunks[chunk.chunk_id] = chunk
    else:
        # A different response claims a known chunk id. The bound version stays the one
        # the queue holds; the admission decision that follows says whether the producer
        # accepted the new identity. Until then the delivery is pending, not bound.
        state.pending_deliveries.setdefault(chunk.chunk_id, []).append(chunk)
        state.identity_conflicts.append(
            {
                "seq": seq,
                "chunk_id": chunk.chunk_id,
                "delivery_id": chunk.delivery_id,
                "bound_req_id": held_chunk.req_id,
                "claimed_req_id": chunk.req_id,
                "disposition": "pending",
            }
        )
    if request is None:
        witness = {
            "history_a": f"the response belongs to a request of the current generation {state.generation}",
            "history_b": "the response belongs to a request of an earlier generation",
            "smallest_observation": "req_id on the response, or generation and config_sha256 carried by the response",
        }
        findings.append(
            Finding(
                "request_binding",
                "unresolved",
                f"response {event['resp_id']} carries no request binding (generation {source})",
                seq,
                witness if source == "unknown" else None,
            )
        )


def _on_admission(event: dict, state: State, findings: list[Finding]) -> None:
    seq = event["seq"]
    chunk_id = str(event["chunk_id"])
    accepted = bool(event.get("admitted")) or bool(event.get("replaced"))
    pending = state.pending_deliveries.get(chunk_id) or []
    delivery_id = event.get("delivery_id") if isinstance(event.get("delivery_id"), str) else None
    decided = None
    for candidate in pending:
        if delivery_id is None or candidate.delivery_id == delivery_id:
            decided = candidate
    if decided is not None:
        pending.remove(decided)
        for conflict in state.identity_conflicts:
            if conflict["seq"] == decided.seq:
                conflict["disposition"] = "admitted" if accepted else "rejected"
                conflict["decided_at_seq"] = seq
        if accepted:
            # The producer accepted a different identity under the same chunk id: from
            # here on the queued actions of this chunk belong to the admitted version.
            state.chunks[chunk_id] = decided
    chunk = state.chunks.get(chunk_id)
    if chunk is None:
        state.unknowns.append(f"admission of unrecorded chunk {event['chunk_id']}")
        return
    for action_id in event.get("replaced") or []:
        replaced = state.queued.pop(str(action_id), None)
        if replaced is not None:
            older = state.chunks.get(replaced["chunk_id"])
            if (
                older is not None
                and older.req_id is not None
                and chunk.req_id is not None
                and state.request_order.get(chunk.req_id, -1)
                < state.request_order.get(older.req_id, -1)
            ):
                # Exploratory reading: a chunk from an older request replaced a queued
                # action of a newer request; the frozen contract does not score this.
                state.stale_overwrites.append(
                    {"seq": seq, "replaced": str(action_id), "by_chunk": chunk.chunk_id}
                )
    for decision in event.get("decisions") or []:
        # Retrospective reading: a configuration fence applied to a chunk whose request
        # belongs to the current activation context is stricter than the frozen rule,
        # which fences prior requests only. Reported, not scored.
        if (
            isinstance(decision, dict)
            and decision.get("disposition") == "skipped"
            and decision.get("reason") == "configuration_fence"
            and chunk.bound
            and chunk.activation == state.activation
            and chunk.config_sha256 == state.config_sha256
            and chunk.asserted_config_sha256 in (None, state.config_sha256)
        ):
            state.strict_admissions.append(
                {
                    "seq": seq,
                    "chunk_id": chunk.chunk_id,
                    "ordinal": decision.get("ordinal"),
                    "request_activation": chunk.activation,
                    "observation_activation": chunk.obs_activation,
                }
            )
    for ordinal in event.get("admitted") or []:
        o = _int(ordinal)
        if o is None:
            continue
        action_id = f"{chunk.chunk_id}:{o}"
        if action_id in state.dispatched:
            findings.append(
                Finding(
                    "duplicate_dispatch",
                    "violated",
                    f"action {action_id} admitted again after it was dispatched",
                    seq,
                )
            )
        state.queued[action_id] = {
            "chunk_id": chunk.chunk_id,
            "ordinal": o,
            "step": (chunk.first_step or 0) + o,
            # The binding at admission: a later delivery under the same chunk id, whether
            # rejected or admitted afterwards, does not change what this queued action is.
            "chunk": chunk,
        }


def _on_dispatch(
    event: dict,
    state: State,
    findings: list[Finding],
    mappings: list[dict],
    max_age: Fraction | None,
) -> None:
    seq, at = event["seq"], event.get("at")
    now = _controller_time(at, state.controller_clock)
    _check_activation(event, state)
    action_id, chunk_id = str(event["action_id"]), str(event["chunk_id"])
    generation, step = _int(event["generation"]), _int(event["step"])
    queued_entry = state.queued.get(action_id)
    chunk = queued_entry["chunk"] if queued_entry is not None else state.chunks.get(chunk_id)
    dispatch_id = event.get("dispatch_id") if isinstance(event.get("dispatch_id"), str) else None
    key = dispatch_id or f"{action_id}#{sum(1 for a in state.attempts if a.action_id == action_id)}"
    attempt = Attempt(
        key,
        dispatch_id,
        action_id,
        chunk_id,
        event.get("input_id") if isinstance(event.get("input_id"), str) else None,
        seq,
        at,
        generation,
        step,
    )
    validity = attempt.validity
    validity["first_attempt_of_action"] = action_id not in state.dispatched
    if dispatch_id is not None and dispatch_id in state.attempts_by_dispatch_id:
        state.unknowns.append(f"dispatch_id {dispatch_id} is reused by a second send attempt")
    state.attempts.append(attempt)
    if dispatch_id is not None:
        state.attempts_by_dispatch_id.setdefault(dispatch_id, attempt)
    state.opportunity_events.append(
        {
            "seq": seq,
            "kind": "dispatch",
            "input_id": attempt.input_id,
            "at": at,
            "attempt": key,
            "action_id": action_id,
        }
    )
    if generation is not None and generation not in state.survivors_at_first_dispatch:
        # Exploratory reading, added after the frozen cases ran: which pre-reset actions
        # are still queued when the new generation dispatches for the first time.
        carried = state.survivors_at_reset.get(generation, [])
        state.survivors_at_first_dispatch[generation] = sorted(
            a for a in carried if a in state.queued or a == action_id
        )
    if action_id in state.dispatched:
        findings.append(
            Finding("duplicate_dispatch", "violated", f"action {action_id} dispatched twice", seq)
        )
    if action_id not in state.queued:
        state.unknowns.append(f"dispatch of {action_id} without a recorded admission")
    state.queued.pop(action_id, None)
    state.dispatched[action_id] = {
        "chunk_id": chunk_id,
        "step": step,
        "generation": generation,
        "at": at,
        "seq": seq,
        "attempts": state.dispatched.get(action_id, {}).get("attempts", 0) + 1,
    }
    if generation is not None and now is not None:
        state.dispatch_ticks.setdefault(generation, set()).add(now)
    if generation is not None:
        counts = state.opportunities.setdefault(generation, {"dispatched": 0, "refused": 0})
        counts["dispatched"] += 1
    if generation is not None and step is not None:
        state.steps_dispatched.setdefault(generation, set()).add(step)
        last = state.last_step.get(generation)
        if last is not None and step <= last:
            findings.append(
                Finding(
                    "dispatch_order",
                    "violated",
                    f"step {step} dispatched after step {last} in generation {generation}",
                    seq,
                )
            )
        state.last_step[generation] = max(step, last if last is not None else step)
    if chunk is None:
        validity.update(
            {"bound": False, "generation": None, "configuration": None, "freshness": None}
        )
        findings.append(
            Finding(
                "generation_fencing",
                "unresolved",
                f"action {action_id} belongs to an unrecorded chunk {chunk_id}",
                seq,
            )
        )
        state.alignment.append(
            Finding(
                "chunk_target_alignment",
                "unresolved",
                f"action {action_id}: target unknown, the chunk {chunk_id} is unrecorded",
                seq,
            )
        )
        return
    # A dispatch is bound when its chunk names a recorded request whose assertions agree
    # with that request; a response that contradicts its request is not a valid binding.
    validity["bound"] = chunk.bound and not chunk.assertion_conflict
    _check_generation(attempt, chunk, findings)
    _check_configuration(attempt, chunk, state, findings)
    _check_freshness(attempt, chunk, state, findings, mappings, max_age)
    _check_alignment(event, attempt, chunk, state)
    _check_observation_context(attempt, chunk, state)


def _check_generation(attempt: Attempt, chunk: Chunk, findings: list[Finding]) -> None:
    generation, action_id, seq = attempt.generation, attempt.action_id, attempt.seq
    if chunk.generation is None:
        attempt.validity["generation"] = None
        findings.append(
            Finding(
                "generation_fencing",
                "unresolved",
                f"action {action_id} dispatched in generation {generation} from chunk {chunk.chunk_id} of unknown generation",
                seq,
                {
                    "history_a": "the chunk was computed in this generation",
                    "history_b": "the chunk was computed before the last reset",
                    "smallest_observation": "req_id or generation on the response",
                },
            )
        )
    elif generation is not None and chunk.generation != generation:
        attempt.validity["generation"] = False
        findings.append(
            Finding(
                "generation_fencing",
                "violated",
                f"action {action_id} from generation {chunk.generation} dispatched in generation {generation} ({chunk.generation_source} binding)",
                seq,
            )
        )
    else:
        attempt.validity["generation"] = True


def _check_configuration(
    attempt: Attempt, chunk: Chunk, state: State, findings: list[Finding]
) -> None:
    """Configuration binding on the activation chain.

    The frozen rule (suite v2, shared interface): every configuration change opens a new
    local activation context and fences prior requests even if the content hash later
    returns. The replay derives the context from recorded ``configuration_changed`` events;
    a chunk inherits its request's context. Content equality is checked as well: a content
    mismatch is a violation on its own. When the chunk has no request the context is
    unknown; if the record holds no transition at all, content is the whole context.
    """
    action_id, seq = attempt.action_id, attempt.seq
    if chunk.config_sha256 is None:
        attempt.validity["configuration"] = None
        findings.append(
            Finding(
                "configuration_binding",
                "unresolved",
                f"action {action_id}: the chunk carries no configuration identity",
                seq,
            )
        )
        return
    content_equal = state.config_sha256 is None or chunk.config_sha256 == state.config_sha256
    if not content_equal:
        attempt.validity["configuration"] = False
        findings.append(
            Finding(
                "configuration_binding",
                "violated",
                f"action {action_id} computed under configuration {chunk.config_sha256[:12]} dispatched under {state.config_sha256[:12]}",
                seq,
            )
        )
    if chunk.activation is None:
        if state.transitions:
            attempt.validity["configuration"] = None
            findings.append(
                Finding(
                    "configuration_binding",
                    "unresolved",
                    f"action {action_id}: the record holds {len(state.transitions)} configuration "
                    "transition(s) and the chunk's request is unknown, so its activation "
                    "context cannot be established",
                    seq,
                )
            )
        elif content_equal:
            attempt.validity["configuration"] = True
        return
    if chunk.activation != state.activation:
        crossed = [t for t in state.transitions if t["activation"] > chunk.activation]
        attempt.validity["configuration"] = False
        findings.append(
            Finding(
                "configuration_binding",
                "violated",
                f"action {action_id} was requested in activation {chunk.activation} and "
                f"dispatched in activation {state.activation}, after {len(crossed)} "
                f"configuration change(s) at seq {[t['seq'] for t in crossed]}"
                + ("; the content hash returned to the same value" if content_equal else ""),
                seq,
            )
        )
    elif content_equal:
        attempt.validity["configuration"] = True


def _check_freshness(
    attempt: Attempt,
    chunk: Chunk,
    state: State,
    findings: list[Finding],
    mappings: list[dict],
    max_age: Fraction | None,
) -> None:
    """Age at dispatch against the inclusive limit, with explicit chronology.

    The mapped interval comes from the stamps and the declared clock relation. Same-clock
    chain evidence gives a lower bound on the age: the observation already existed when
    the driver recorded its arrival or when a controller-stamped request carried it, so
    ``age >= dispatch - held_at`` under the premise that acquisition precedes possession.
    The interval is intersected with that bound; it is never clamped to zero.
    """
    action_id, seq, at = attempt.action_id, attempt.seq, attempt.at
    now = _controller_time(at, state.controller_clock)
    mapped, chronology = age_reading(at, chunk.acquired_at, state.clocks)
    chain_low = now - chunk.held_at if now is not None and chunk.held_at is not None else None
    used = mapped
    premise = None
    if mapped is not None and chain_low is not None:
        low, high = mapped
        if chain_low > high:
            used = None
            chronology = "mapping_contradicts_chain"
        elif chain_low > low:
            used = (chain_low, high)
            premise = (
                f"lower bound {number(chain_low)} from same-clock evidence that the observation "
                f"was held at {number(chunk.held_at)} (acquisition precedes possession)"
            )
    classification = classify_age(used, max_age)
    if chronology == "mapping_contradicts_chain":
        classification = "inconsistent"
    if (
        classification == "unknown"
        and chain_low is not None
        and max_age is not None
        and chain_low > max_age
    ):
        classification = "beyond"
        premise = (
            f"age at least {number(chain_low)} by same-clock chain evidence alone (held at "
            f"{number(chunk.held_at)}); no acquisition stamp or mapping was needed"
        )
    reading = {
        "attempt": attempt.key,
        "action_id": action_id,
        "chronology": chronology,
        "mapped_interval": [number(mapped[0]), number(mapped[1])] if mapped else None,
        "chain_lower_bound": number(chain_low),
        "interval_used": [number(used[0]), number(used[1])] if used else None,
        "max_age": number(max_age),
        "classification": classification,
        "premise": premise,
        "non_integer_inputs": state.non_integer_stamps,
    }
    state.age_readings.append(reading)
    attempt.validity["freshness"] = {
        "within": True,
        "beyond": False,
    }.get(classification)
    if classification == "within":
        if premise is not None:
            findings.append(
                Finding(
                    "freshness",
                    "satisfied",
                    f"action {action_id} age {reading['interval_used']} within the limit "
                    f"{number(max_age)} under the chain premise: {premise}",
                    seq,
                )
            )
        return
    if classification == "beyond":
        findings.append(
            Finding(
                "freshness",
                "violated",
                f"action {action_id} age {reading['interval_used'] or reading['chain_lower_bound']} "
                f"exceeds the limit {number(max_age)}" + (f" ({premise})" if premise else ""),
                seq,
            )
        )
    elif classification == "overlapping":
        findings.append(
            Finding(
                "freshness",
                "unresolved",
                f"action {action_id} age interval {reading['interval_used']} straddles the limit "
                f"{number(max_age)} under the declared clock mapping",
                seq,
            )
        )
    elif classification == "inconsistent":
        findings.append(
            Finding(
                "freshness",
                "unresolved",
                f"action {action_id} has an inconsistent age: mapped interval "
                f"{reading['mapped_interval']}, chain lower bound {reading['chain_lower_bound']}; "
                "the declared clock relation places the acquisition after the dispatch or after "
                "evidence that the observation was already held; the relation or a stamp is wrong",
                seq,
            )
        )
    elif classification == "chronology_unresolved":
        findings.append(
            Finding(
                "freshness",
                "unresolved",
                f"action {action_id} age interval {reading['mapped_interval']} admits negative "
                "ages: the declared clock relation does not order acquisition before dispatch "
                "and no same-clock chain evidence bounds the age; not clamped to zero",
                seq,
                {
                    "history_a": "the observation was acquired just before the dispatch",
                    "history_b": "the declared offset or uncertainty is wrong",
                    "smallest_observation": "a controller-clock stamp of the observation's "
                    "arrival, or a tighter declared mapping",
                },
            )
        )
    else:
        witness = {
            "history_a": "the observation was acquired just before the request",
            "history_b": "the observation was acquired long before the request",
            "smallest_observation": "acquisition time in the controller clock, or a declared clock mapping with uncertainty",
        }
        explanation = {
            "conflicting_declarations": "the clock pair is declared with different offsets and "
            "no priority: jointly they have no consistent calibration, and as alternatives the "
            "admissible ages are not all within the limit",
            "unsupported_declaration": "the only declarations for the clock pair are outside "
            "the supported domain",
            "undeclared_clock": "a stamp names a clock the trace does not declare",
            "unit_mismatch": "the stamps and the declared relation use different units",
            "unmapped": "no relation is declared for the clock pair",
            "malformed_declarations": "a malformed member disables every declared relation",
            "absent_acquisition": "the acquisition time is missing",
            "unstamped": "a stamp is malformed",
        }.get(chronology, chronology)
        findings.append(
            Finding(
                "freshness",
                "unresolved",
                f"action {action_id} has no computable age ({chronology}: {explanation})"
                + (
                    f"; same-clock chain evidence gives age at least {reading['chain_lower_bound']}"
                    if chain_low is not None
                    else ""
                ),
                seq,
                witness,
            )
        )


def _check_alignment(event: dict, attempt: Attempt, chunk: Chunk, state: State) -> None:
    """Retrospective: the dispatched step equals the chunk target ``first_step + ordinal``.

    Premises, declared: the chunk's ``first_step`` is the step its policy targeted (frozen
    suite v2: it equals the bound observation's step); the dispatch ``step`` is the executed
    local consumption counter; alignment means the action ran at the step it targeted. An
    unbound chunk has no established target and stays unresolved.
    """
    action_id, seq, step = attempt.action_id, attempt.seq, attempt.step
    ordinal = _int(event.get("ordinal"))
    if not chunk.bound or chunk.first_step is None or ordinal is None:
        state.alignment.append(
            Finding(
                "chunk_target_alignment",
                "unresolved",
                f"action {action_id}: target semantics not established (unbound chunk or "
                "missing first_step/ordinal)",
                seq,
            )
        )
        return
    target = chunk.first_step + ordinal
    declared = _int(event.get("target_step"))
    if declared is not None and declared != target:
        state.alignment.append(
            Finding(
                "chunk_target_alignment",
                "unresolved",
                f"action {action_id}: producer target_step {declared} disagrees with "
                f"first_step + ordinal = {target}",
                seq,
            )
        )
    if chunk.obs_step is not None and chunk.first_step != chunk.obs_step:
        state.alignment.append(
            Finding(
                "chunk_target_alignment",
                "unresolved",
                f"action {action_id}: chunk first_step {chunk.first_step} differs from its bound "
                f"observation's step {chunk.obs_step}; the target is not established",
                seq,
            )
        )
        return
    if step is None:
        state.alignment.append(
            Finding("chunk_target_alignment", "unresolved", f"action {action_id}: no step", seq)
        )
    elif step != target:
        state.alignment.append(
            Finding(
                "chunk_target_alignment",
                "violated",
                f"action {action_id} dispatched at step {step} but targeted step {target} "
                f"(first_step {chunk.first_step} + ordinal {ordinal})",
                seq,
                {"dispatched_step": step, "target_step": target, "generation": attempt.generation},
            )
        )


def _check_observation_context(attempt: Attempt, chunk: Chunk, state: State) -> None:
    """Retrospective: the chunk's observation was acquired in its request's activation.

    The frozen rule fences prior requests, not prior observations. A request sent in a
    later activation that carries an observation from an earlier one is reported here with
    the premise stated; whether such an observation is unusable is a policy-side premise
    the record does not establish.
    """
    if not chunk.bound:
        return
    if chunk.obs_activation is None or chunk.activation is None:
        state.observation_context.append(
            Finding(
                "observation_context",
                "unresolved",
                f"action {attempt.action_id}: the observation's activation is unrecorded",
                attempt.seq,
            )
        )
    elif chunk.obs_activation != chunk.activation:
        state.observation_context.append(
            Finding(
                "observation_context",
                "violated",
                f"action {attempt.action_id}: request {chunk.req_id} was sent in activation "
                f"{chunk.activation} with an observation acquired in activation "
                f"{chunk.obs_activation}",
                attempt.seq,
            )
        )


def _on_outcome(event: dict, state: State, findings: list[Finding]) -> None:
    """Bind an acknowledgement or failure to one send attempt."""
    kind, seq = event["kind"], event["seq"]
    action_id = str(event["action_id"])
    dispatch_id = event.get("dispatch_id") if isinstance(event.get("dispatch_id"), str) else None
    attempt = None
    if dispatch_id is not None:
        attempt = state.attempts_by_dispatch_id.get(dispatch_id)
        if attempt is None:
            state.unmatched_outcomes.append(
                {"seq": seq, "kind": kind, "dispatch_id": dispatch_id, "action_id": action_id}
            )
            state.unknowns.append(
                f"{kind} at seq {seq} names dispatch_id {dispatch_id} of no recorded attempt"
            )
            return
        if attempt.action_id != action_id:
            state.unmatched_outcomes.append(
                {"seq": seq, "kind": kind, "dispatch_id": dispatch_id, "action_id": action_id}
            )
            state.unknowns.append(
                f"{kind} at seq {seq} names dispatch_id {dispatch_id} of action "
                f"{attempt.action_id} but action {action_id}"
            )
            return
    else:
        # Legacy record without dispatch identity: an outcome can only answer an attempt
        # recorded before it that has no outcome yet; with one such attempt the binding
        # is unambiguous, with several it is not, and with none the record is repeating
        # itself or answering nothing.
        prior = [a for a in state.attempts if a.action_id == action_id and a.seq < seq]
        candidates = [
            a for a in prior if not a.acknowledgements and not a.failures and not a.ambiguous
        ]
        if not prior:
            state.unknowns.append(f"{kind} for undispatched action {action_id}")
            return
        if not candidates:
            state.unmatched_outcomes.append(
                {
                    "seq": seq,
                    "kind": kind,
                    "dispatch_id": None,
                    "action_id": action_id,
                    "answers": "no unanswered attempt (repeated outcome)",
                }
            )
            return
        if len(candidates) > 1:
            for candidate in candidates:
                candidate.ambiguous = True
            state.unmatched_outcomes.append(
                {
                    "seq": seq,
                    "kind": kind,
                    "dispatch_id": None,
                    "action_id": action_id,
                    "ambiguous_between": [c.key for c in candidates],
                }
            )
            return
        attempt = candidates[0]
    if kind == "dispatch_acknowledged":
        attempt.acknowledgements += 1
    else:
        attempt.failures += 1
        findings.append(
            Finding(
                "acknowledgement",
                "violated",
                f"attempt {attempt.key} of action {action_id} failed at dispatch: {event.get('reason')}",
                seq,
            )
        )


def coverage_window(state: State, generation: int, control_period: Fraction | None) -> dict:
    """Dispatch coverage of a generation (the version-1 ``useful_execution`` meaning).

    Two bases, reported explicitly. When the producer records control opportunities
    (any ``dispatch_refused`` event in the trace), coverage is dispatched opportunities over
    all opportunities of the generation: the producer's own control loop is the grid. This
    basis was added after the frozen cases ran, for records whose dispatch opportunities do
    not lie on a fixed period. Otherwise coverage is measured on the generation's tick grid
    as frozen: ticks from the first tick at or after the first response arrival to the
    generation's end, start + k * control_period.
    """
    if state.refusals or any(c["refused"] for c in state.opportunities.values()):
        counts = state.opportunities.get(generation, {"dispatched": 0, "refused": 0})
        total = counts["dispatched"] + counts["refused"]
        if total == 0:
            return {
                "basis": "opportunities",
                "ticks": 0,
                "dispatched": 0,
                "coverage": None,
                "window": None,
            }
        return {
            "basis": "opportunities",
            "ticks": total,
            "dispatched": counts["dispatched"],
            "coverage": counts["dispatched"] / total,
            "window": None,
        }
    return _grid_window(state, generation, control_period)


def _grid_window(state: State, generation: int, control_period: Fraction | None) -> dict:
    """Dispatch coverage over the control ticks of a generation from the first tick at or
    after the first response arrival to the generation's end (the tick before the next
    reset, or the last recorded time). Ticks lie on the generation's grid,
    start + k * control_period, in exact arithmetic. A generation in which no response
    arrived, or whose window holds no tick, is unresolved, not violated."""
    arrival = state.first_arrival.get(generation)
    origin = state.generation_start.get(generation, arrival)
    if generation in state.generation_end and control_period is not None:
        end = state.generation_end[generation] - control_period
    else:
        end = state.last_time
    if (
        arrival is None
        or origin is None
        or end is None
        or control_period is None
        or control_period <= 0
    ):
        return {"basis": "grid", "ticks": 0, "dispatched": 0, "coverage": None, "window": None}
    first_k = math.ceil((arrival - origin) / control_period)
    start = origin + max(first_k, 0) * control_period
    if end < start:
        return {"basis": "grid", "ticks": 0, "dispatched": 0, "coverage": None, "window": None}
    count = math.floor((end - start) / control_period) + 1
    # A dispatch lies on the grid when its offset from the window start is a whole number
    # of periods; the ticks are counted, never enumerated, so a wide window costs nothing.
    covered = sum(
        1
        for at in state.dispatch_ticks.get(generation, set())
        if start <= at <= end and ((at - start) / control_period).denominator == 1
    )
    return {
        "basis": "grid",
        "ticks": count,
        "dispatched": covered,
        "coverage": covered / count,
        "window": [number(start), number(end)],
    }


def _close(
    state: State, findings: list[Finding], control_period: Fraction | None, coverage_min: object
) -> None:
    pending = [a for a in state.attempts if a.outcome in ("unacknowledged", "ambiguous_legacy")]
    if pending:
        findings.append(
            Finding(
                "acknowledgement",
                "unresolved",
                f"{len(pending)} send attempt(s) have no acknowledgement and no failure bound "
                f"to them: {[a.key for a in pending][:4]}; unobserved, not failed",
                None,
                {
                    "history_a": "the dispatch reached the actuator",
                    "history_b": "the dispatch was lost",
                    "smallest_observation": "an acknowledgement or failure record per send "
                    "attempt, carrying its dispatch_id",
                },
            )
        )
    conflicting = [a for a in state.attempts if a.outcome == "conflicting"]
    if conflicting:
        findings.append(
            Finding(
                "acknowledgement",
                "unresolved",
                f"{len(conflicting)} send attempt(s) carry both an acknowledgement and a "
                f"failure: {[a.key for a in conflicting][:4]}; the record contradicts itself",
                None,
            )
        )
    if state.unmatched_outcomes:
        findings.append(
            Finding(
                "acknowledgement",
                "unresolved",
                f"{len(state.unmatched_outcomes)} acknowledgement/failure record(s) bind to no "
                "single recorded attempt",
                None,
            )
        )
    if state.activation_contradictions:
        findings.append(
            Finding(
                "configuration_binding",
                "unresolved",
                f"{len(state.activation_contradictions)} event(s) assert an activation counter "
                "that contradicts the recorded configuration transitions: "
                f"{state.activation_contradictions[:3]}",
                None,
            )
        )
    if control_period is None or not isinstance(coverage_min, (int, float)):
        findings.append(
            Finding(
                "useful_execution",
                "unresolved",
                "control_period or useful_coverage_min is not declared; coverage cannot be judged",
                None,
            )
        )
        return
    for generation in state.generations_seen:
        window = coverage_window(state, generation, control_period)
        if window["coverage"] is None:
            findings.append(
                Finding(
                    "useful_execution",
                    "unresolved",
                    f"generation {generation}: no response arrived, or no control tick or "
                    "recorded opportunity lies in the window, so dispatch coverage cannot be judged",
                    None,
                )
            )
        elif window["coverage"] < coverage_min:
            findings.append(
                Finding(
                    "useful_execution",
                    "violated",
                    f"generation {generation}: {window['dispatched']} of {window['ticks']} "
                    f"{window['basis']} units carried a dispatch (coverage "
                    f"{window['coverage']:.3f} < {coverage_min})",
                    None,
                )
            )
        else:
            findings.append(
                Finding(
                    "useful_execution",
                    "satisfied",
                    f"generation {generation}: {window['dispatched']} of {window['ticks']} "
                    f"{window['basis']} units carried a dispatch (coverage "
                    f"{window['coverage']:.3f})",
                    None,
                )
            )


# --- the producer's frozen usefulness contract -------------------------------------------


def _same_stamp(a: object, b: object) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    va, vb = _stamp_value(a), _stamp_value(b)
    return (
        va is not None
        and va == vb
        and a.get("clock") == b.get("clock")
        and a.get("unit") == b.get("unit")
    )


def assigned_usefulness(trace: dict, state: State) -> dict:
    """Read the producer's frozen whole-case usefulness contract on the recorded opportunities.

    The population is the contract's ``dispatch_opportunities`` (identity ``input_id``, time
    ``at``), the same for every remedy of a case. Each opportunity must be observed exactly
    once as a dispatch attempt or a refusal at the frozen time; a dispatch or refusal outside
    the list, a duplicated or unobserved-with-mismatched-time opportunity makes the
    membership invalid. Several attempts at one opportunity count once. Raw dispatched
    opportunities decide the contract status; validity under the frozen predicates and
    acknowledgement are counted separately and never substituted.
    """
    contract = trace.get("usefulness_contract")
    minimum = _int(trace.get("minimum_dispatches"))
    result: dict = {
        "basis": None,
        "scope": None,
        "status": "unresolved",
        "membership": "absent",
        "membership_problems": [],
        "minimum_dispatches": minimum,
        "opportunities": 0,
        "opportunities_observed": 0,
        "opportunities_unobserved": [],
        "opportunities_dispatched": 0,
        "opportunities_refused": 0,
        "raw_dispatch_attempts": len(state.attempts),
        "opportunities_valid": 0,
        "opportunities_validity_unresolved": 0,
        "opportunities_acknowledged": 0,
        "opportunities_valid_acknowledged": 0,
        "valid_acknowledged_status": "unresolved",
        "rows": [],
        "premise": "a frozen opportunity is counted as dispatched when at least one software "
        "send attempt was recorded for it; validity and acknowledgement are separate counts",
    }
    if not isinstance(contract, dict):
        result["detail"] = "no usefulness_contract on the trace; nothing to read"
        return result
    listed = contract.get("dispatch_opportunities")
    result["basis"] = contract.get("basis")
    result["scope"] = contract.get("scope")
    if minimum is None:
        minimum = _int(contract.get("minimum_dispatches"))
        result["minimum_dispatches"] = minimum
    elif _int(contract.get("minimum_dispatches")) not in (None, minimum):
        result["membership_problems"].append("minimum_dispatches disagrees with the contract")
    problems = result["membership_problems"]
    if not isinstance(listed, list) or minimum is None:
        problems.append("dispatch_opportunities or minimum_dispatches is missing")
        result["membership"] = "invalid"
        return result
    ids: list[str] = []
    for item in listed:
        if not isinstance(item, dict) or not isinstance(item.get("input_id"), str):
            problems.append("an opportunity lacks an input_id")
            continue
        if item["input_id"] in ids:
            problems.append(f"opportunity {item['input_id']} is listed twice")
        ids.append(item["input_id"])
    result["opportunities"] = len(ids)
    observed: dict[str, list[dict]] = {}
    for ev in state.opportunity_events:
        if ev["input_id"] is None or ev["input_id"] not in ids:
            problems.append(
                f"{ev['kind']} at seq {ev['seq']} (input_id {ev['input_id']!r}) is not a listed opportunity"
            )
            continue
        observed.setdefault(ev["input_id"], []).append(ev)
    attempts = {a.key: a for a in state.attempts}
    dispatched = refused = valid = unresolved_valid = acked = valid_acked = 0
    unobserved = []
    for item in listed:
        if not isinstance(item, dict) or not isinstance(item.get("input_id"), str):
            continue
        input_id = item["input_id"]
        events = observed.get(input_id, [])
        row = {
            "input_id": input_id,
            "at": item.get("at"),
            "observed": [e["kind"] for e in events],
            "attempts": [e["attempt"] for e in events if e["kind"] == "dispatch"],
            "refusal_reasons": [e["reason"] for e in events if e["kind"] == "refusal"],
            "counted": None,
            "valid": None,
            "acknowledged": None,
        }
        result["rows"].append(row)
        if not events:
            unobserved.append(input_id)
            continue
        for e in events:
            if not _same_stamp(e["at"], item.get("at")):
                problems.append(
                    f"opportunity {input_id} observed at {e['at']} but frozen at {item.get('at')}"
                )
        kinds = {e["kind"] for e in events}
        if kinds == {"refusal"} and len(events) == 1:
            refused += 1
            row["counted"] = "refused"
            continue
        if "refusal" in kinds or len(events) > 1 and kinds != {"dispatch"}:
            problems.append(f"opportunity {input_id} is both refused and dispatched")
        dispatched += 1
        row["counted"] = "dispatched"
        first = attempts.get(row["attempts"][0]) if row["attempts"] else None
        if first is None:
            continue
        flags = [
            first.validity.get(k)
            for k in (
                "bound",
                "generation",
                "configuration",
                "freshness",
                "first_attempt_of_action",
            )
        ]
        row["valid"] = False if any(f is False for f in flags) else (True if all(flags) else None)
        row["acknowledged"] = first.outcome == "acknowledged"
        if row["valid"] is True:
            valid += 1
        elif row["valid"] is None:
            unresolved_valid += 1
        if row["acknowledged"]:
            acked += 1
        if row["valid"] is True and row["acknowledged"]:
            valid_acked += 1
    result.update(
        {
            "opportunities_observed": len(ids) - len(unobserved),
            "opportunities_unobserved": unobserved,
            "opportunities_dispatched": dispatched,
            "opportunities_refused": refused,
            "opportunities_valid": valid,
            "opportunities_validity_unresolved": unresolved_valid,
            "opportunities_acknowledged": acked,
            "opportunities_valid_acknowledged": valid_acked,
        }
    )
    if problems:
        result["membership"] = "invalid"
        result["status"] = "unresolved"
        result["valid_acknowledged_status"] = "unresolved"
        return result
    result["membership"] = "valid"
    complete = not unobserved
    if dispatched >= minimum:
        result["status"] = "satisfied" if complete else "unresolved"
        if not complete:
            result["detail"] = "minimum met on the observed prefix; unobserved opportunities remain"
    else:
        result["status"] = "violated" if complete else "unresolved"
    if valid_acked >= minimum:
        result["valid_acknowledged_status"] = "satisfied" if complete else "unresolved"
    elif valid_acked + unresolved_valid < minimum and complete:
        result["valid_acknowledged_status"] = "violated"
    else:
        result["valid_acknowledged_status"] = "unresolved"
    return result


# --- the assessment record ---------------------------------------------------------------


def _identity_status(state: State) -> str:
    dispositions = {c["disposition"] for c in state.identity_conflicts}
    if "admitted" in dispositions:
        return "violated"
    if "pending" in dispositions:
        return "unresolved"
    return "satisfied"


def _status_of(items: list[Finding]) -> str:
    if any(f.status == "violated" for f in items):
        return "violated"
    if any(f.status == "unresolved" for f in items):
        return "unresolved"
    return "satisfied"


def _assessment(
    trace: dict,
    state: State,
    findings: list[Finding],
    problems: list[str],
    control_period: Fraction | None = None,
) -> dict:
    per_predicate: dict[str, dict] = {}
    for predicate in PREDICATES:
        items = [f for f in findings if f.predicate == predicate]
        per_predicate[predicate] = {
            "status": _status_of(items),
            "findings": [f.to_dict() for f in items],
        }
    if problems:
        contract = "invalid"
    elif any(p["status"] == "violated" for p in per_predicate.values()):
        contract = "violated"
    elif any(p["status"] == "unresolved" for p in per_predicate.values()):
        contract = "unresolved"
    else:
        contract = "satisfied"
    coverage = {
        str(generation): coverage_window(state, generation, control_period)
        for generation in state.generations_seen
    }
    usefulness = assigned_usefulness(trace, state) if not problems else None
    if problems or usefulness is None or usefulness["membership"] == "absent":
        assigned_contract = "invalid" if problems else None
    else:
        statuses = [p["status"] for name, p in per_predicate.items() if name != "useful_execution"]
        statuses.append(usefulness["status"])
        if "violated" in statuses:
            assigned_contract = "violated"
        elif "unresolved" in statuses:
            assigned_contract = "unresolved"
        else:
            assigned_contract = "satisfied"
    unacknowledged_attempts = [
        a.key for a in state.attempts if a.outcome in ("unacknowledged", "ambiguous_legacy")
    ]
    return {
        "schema": ASSESSMENT_SCHEMA,
        "assessment_version": {
            "schema": ASSESSMENT_SCHEMA,
            "supersedes": ["nisayon.temporal-assessment.v2", "nisayon.temporal-assessment.v1"],
            "changes": list(ASSESSMENT_CHANGES),
            "retrospective": "versions 2 and 3 were implemented after every retained trace of "
            "temporal-integration-001 had been executed; earlier results are kept",
        },
        "case_id": trace.get("case_id"),
        "software_execution": trace.get("execution_status", "unknown"),
        "evidence": {
            "problems": problems,
            "unknowns": list(state.unknowns),
            "unbound_responses": sorted(
                c.chunk_id for c in state.chunks.values() if c.req_id is None
            ),
            "unacknowledged_dispatches": sorted(
                {a.action_id for a in state.attempts if a.key in unacknowledged_attempts}
            ),
            "unacknowledged_attempts": unacknowledged_attempts,
            "attempts": [a.to_dict() for a in state.attempts],
            "unmatched_outcomes": list(state.unmatched_outcomes),
            "activation_transitions": list(state.transitions),
            "activation_contradictions": list(state.activation_contradictions),
            "non_integer_stamps": state.non_integer_stamps,
            "clocks": state.clocks.to_dict(),
            "clock_diagnostics": list(state.clocks.diagnostics),
            "identity_conflicts": list(state.identity_conflicts),
            "completeness": "incomplete"
            if (
                problems
                or state.unknowns
                or any(c.req_id is None for c in state.chunks.values())
                or state.clocks.status in ("conflicting", "unsupported")
                or any(c["disposition"] == "pending" for c in state.identity_conflicts)
            )
            else "complete",
        },
        "temporal_contract": contract,
        "predicates": per_predicate,
        "useful_execution": {
            "status": per_predicate["useful_execution"]["status"],
            "coverage_by_generation": coverage,
            "meaning": "version-1 grid/opportunity coverage against useful_coverage_min, "
            "kept under its original name and denominator",
        },
        "assigned_usefulness": usefulness,
        "assigned_contract": assigned_contract,
        "retrospective": {
            "chunk_target_alignment": {
                "status": _status_of(state.alignment),
                "findings": [f.to_dict() for f in state.alignment],
                "premises": [
                    "the chunk's first_step is the step its policy targeted (suite v2: the "
                    "bound observation's step)",
                    "the dispatch step is the executed local consumption counter",
                    "alignment means the action ran at the step it targeted; software indices "
                    "only, no physical state",
                ],
            },
            "observation_context": {
                "status": _status_of(state.observation_context),
                "findings": [f.to_dict() for f in state.observation_context],
                "premise": "the frozen rule fences prior requests, not prior observations; an "
                "observation from an earlier activation is reported, not scored",
            },
            "admissions_stricter_than_frozen_rule": list(state.strict_admissions),
            "chunk_identity": {
                "status": _identity_status(state),
                "conflicts": list(state.identity_conflicts),
                "premise": "a chunk id names one response; a different response under the "
                "same id is a conflict that the producer's admission decision resolves, and "
                "a queued action keeps the identity it was admitted with",
            },
            "note": "named after the retained traces were executed; not part of the frozen "
            "nine-predicate contract or of temporal_contract",
        },
        "age_readings": list(state.age_readings),
        "robot_task_outcome": "unmeasured",
        "controller_clock": state.controller_clock,
        "useful_coverage_min": USEFUL_COVERAGE_MIN,
        "dispatch_refusals": len(state.refusals),
        "exploratory_stale_overwrites": list(state.stale_overwrites),
        "repeated_deliveries": list(state.repeated_deliveries),
        "exploratory_after_freeze": {
            "queue_reset_before_first_dispatch": {
                str(g): {
                    "survivors_at_reset": state.survivors_at_reset.get(g, []),
                    "still_queued_at_first_dispatch": v,
                }
                for g, v in state.survivors_at_first_dispatch.items()
            },
            "note": "added after the frozen cases ran: the upstream fix clears the queue at the "
            "next control-loop start, after reset_completed, so it violates the frozen "
            "reset-time predicate while no stale action is dispatched; reported, not scored",
        },
        "final_state": state.to_dict(),
        "boundary": "software dispatch and recorded identities only; not physical actuation, not policy quality, not task success",
    }


def render(assessment: dict) -> str:
    """A short readable rendering of an assessment; the JSON is the record."""
    lines = [
        f"temporal assessment of {assessment.get('case_id')!r}: contract "
        f"{assessment['temporal_contract']}; software execution "
        f"{assessment['software_execution']}; evidence {assessment['evidence']['completeness']}; "
        f"robot task outcome {assessment['robot_task_outcome']}",
    ]
    for predicate, entry in assessment.get("predicates", {}).items():
        lines.append(f"  {predicate}: {entry['status']}")
        for finding in entry["findings"]:
            if finding["status"] != "satisfied":
                lines.append(f"    - {finding['detail']}")
                if finding.get("witness") and "smallest_observation" in finding["witness"]:
                    lines.append(
                        f"      smallest observation: {finding['witness']['smallest_observation']}"
                    )
    for generation, window in (
        assessment.get("useful_execution", {}).get("coverage_by_generation", {}).items()
    ):
        lines.append(
            f"  generation {generation}: {window['dispatched']} of {window['ticks']} "
            f"{window.get('basis', 'grid')} units dispatched"
            + (
                f" (coverage {window['coverage']:.3f})"
                if window["coverage"] is not None
                else " (no tick or opportunity in the window)"
            )
        )
    usefulness = assessment.get("assigned_usefulness")
    if usefulness and usefulness.get("membership") != "absent":
        lines.append(
            f"  assigned usefulness: {usefulness['status']} ({usefulness['opportunities_dispatched']} "
            f"of {usefulness['opportunities']} frozen opportunities dispatched, minimum "
            f"{usefulness['minimum_dispatches']}; valid {usefulness['opportunities_valid']}, "
            f"acknowledged {usefulness['opportunities_acknowledged']}, membership "
            f"{usefulness['membership']}); assigned contract {assessment.get('assigned_contract')}"
        )
    retro = assessment.get("retrospective", {})
    for name in ("chunk_target_alignment", "observation_context"):
        entry = retro.get(name)
        if entry and entry["status"] != "satisfied":
            lines.append(f"  retrospective {name}: {entry['status']}")
            for finding in entry["findings"]:
                lines.append(f"    - {finding['detail']}")
    for problem in assessment.get("evidence", {}).get("problems", []):
        lines.append(f"  malformed: {problem}")
    lines.append(f"  boundary: {assessment.get('boundary')}")
    return "\n".join(lines)
