"""Producer admission guard for explicitly related, unit-rate software clocks.

This is not the evaluator. A driver's schedule time is never a substitute for
an absent acquisition timestamp. The caller decides what to do with unknowns.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Age:
    status: str
    lower_ns: int | None
    upper_ns: int | None
    reason: str

    def record(self) -> dict:
        return asdict(self)


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _stamp(value: object) -> bool:
    return (
        isinstance(value, dict)
        and _integer(value.get("value"))
        and isinstance(value.get("clock"), str)
        and bool(value["clock"])
        and value.get("unit") == "ns"
    )


def age_at(acquired: dict | None, dispatched: dict | None, clocks: dict, max_age: int) -> Age:
    """Bound dispatch minus acquisition under one explicit clock relation.

    A mapping means ``to = from + offset ± uncertainty``. Multiple relations,
    drift, other units and undeclared clocks have no supported interpretation.
    Inclusive equality is within the deadline; a crossing interval is unknown.
    """

    def unknown(why):
        return Age("unresolved", None, None, why)

    if not _integer(max_age) or max_age < 0:
        return unknown("unsupported_deadline")
    if not _stamp(acquired) or not _stamp(dispatched):
        return unknown("missing_or_unsupported_timestamp")
    assert acquired is not None and dispatched is not None
    origin, destination = acquired["clock"], dispatched["clock"]
    if origin not in clocks.get("names", []) or destination not in clocks.get("names", []):
        return unknown("undeclared_clock")
    offset = uncertainty = 0
    if origin != destination:
        relations = [
            row
            for row in clocks.get("declared_mappings", [])
            if {row.get("from"), row.get("to")} == {origin, destination}
        ]
        if len(relations) != 1:
            return unknown("missing_or_multiple_clock_relations")
        relation = relations[0]
        offset, uncertainty = relation.get("offset"), relation.get("uncertainty")
        if (
            not _integer(offset)
            or not _integer(uncertainty)
            or uncertainty < 0
            or relation.get("unit") != "ns"
            or relation.get("rate", 1) != 1
            or relation.get("drift", 0) != 0
        ):
            return unknown("unsupported_clock_relation")
        if relation["from"] != origin:
            offset = -offset
    center = dispatched["value"] - acquired["value"] - offset
    lower, upper = center - uncertainty, center + uncertainty
    if upper < 0:
        return Age("inconsistent", lower, upper, "acquisition_definitely_after_dispatch")
    if lower < 0 or lower <= max_age < upper:
        return Age("unresolved", lower, upper, "interval_crosses_admissibility_boundary")
    if lower > max_age:
        return Age("overdue", lower, upper, "age_exceeds_deadline")
    return Age("within", lower, upper, "age_within_inclusive_deadline")
