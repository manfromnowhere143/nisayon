"""Prospective, operator-reported active effort; no inference from agent runtime.

This example measures declared intervals and composes receipt-backed costs. It
does not authenticate a human, prove attention, verify invoices, or identify a
causal effect. The existing finite cost-target evaluator supplies the quality
and complete-cost arithmetic; this example adds measurement and owner review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path

from nisayon.engine.cost_target import DECISIONS, PHASES, assess_cost_target

ARMS = ("baseline", "candidate", "shared")
CHARGES = ("provider", "compute", "other")


def number(value: object) -> Fraction:
    if (
        type(value) not in (int, float)
        or (type(value) is float and not math.isfinite(value))
        or value < 0
    ):
        raise ValueError("Expected a finite nonnegative number")
    return Fraction(value)


def nonempty(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a nonempty identity or reference")
    return value


def exact(value: dict, keys) -> None:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"Required fields: {sorted(keys)}")


def quantity(item: dict) -> Fraction | None:
    exact(item, ("value", "reference", "reason"))
    if not isinstance(item["reference"], str) or not isinstance(item["reason"], str):
        raise ValueError("References and reasons must be strings")
    if item["value"] is None:
        nonempty(item["reason"])
        return None
    nonempty(item["reference"])
    return number(item["value"])


def microseconds(duration: timedelta) -> int:
    return ((duration.days * 86400 + duration.seconds) * 1_000_000) + duration.microseconds


def display_quantities(report: dict) -> dict:
    """Keep exact rational witnesses beside approximate JSON display values.

    JSON pointers address every computed Fraction, including signed differences.
    An overflow display null remains distinct from an unknown, which has no
    rational witness. Neither display values nor ratios may adjudicate the gate.
    """
    witnesses = {}

    def display(value, path):
        if isinstance(value, Fraction):
            try:
                approximate = float(value)
            except OverflowError:
                approximate = None
            witnesses[path] = {
                "numerator": str(value.numerator),
                "denominator": str(value.denominator),
                "display": "overflow"
                if approximate is None
                else "exact"
                if Fraction(approximate) == value
                else "rounded",
            }
            return approximate
        if isinstance(value, dict):
            return {
                key: display(item, f"{path}/{key.replace('~', '~0').replace('/', '~1')}")
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [display(item, f"{path}/{index}") for index, item in enumerate(value)]
        return value

    result = display(report, "")
    result["exact_quantities"] = witnesses
    result["arithmetic"] = (
        "Exact supplied integers and finite binary floats; durations rounded to microseconds "
        "with ties to even. Costs and comparisons use rational arithmetic. Numeric report "
        "fields and finite-comparison ratios are display values; use exact_quantities at "
        "the indicated JSON pointers to reconstruct phase ledgers. Unknowns have no witness."
    )
    return result


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("Activity timestamps must explicitly use UTC")
    return result


def read_json(data: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(data, object_pairs_hook=unique)


def read_activity(data: bytes) -> tuple[dict, datetime, datetime | None, bool]:
    rows = [read_json(line) for line in data.decode().splitlines()]
    if len(rows) not in (1, 2):
        raise ValueError("An activity requires one start and at most one stop")
    start = rows[0]
    exact(start, ("event", "id", "actor", "arm", "case", "phase", "reference", "utc", "ns"))
    if start["event"] != "start" or type(start["ns"]) is not int or start["ns"] < 0:
        raise ValueError("Invalid start event or monotonic clock")
    for field in ("id", "actor", "case", "reference"):
        nonempty(start[field])
    if start["arm"] not in ARMS or start["phase"] not in PHASES:
        raise ValueError("Unknown activity arm or phase")
    begin = timestamp(start["utc"])
    if len(rows) == 1:
        return start, begin, None, False
    stop = rows[1]
    exact(stop, ("event", "id", "utc", "ns", "status"))
    if (
        stop["event"] != "stop"
        or stop["id"] != start["id"]
        or type(stop["ns"]) is not int
        or stop["ns"] < start["ns"]
        or stop["status"] not in ("completed", "interrupted")
    ):
        raise ValueError("Invalid stop event or monotonic clock")
    duration_ns = stop["ns"] - start["ns"]
    wall_ns = microseconds(timestamp(stop["utc"]) - begin) * 1000
    if abs(wall_ns - duration_ns) > 1_000_000_000:
        raise ValueError("UTC and monotonic clocks disagree by more than one second")
    # Monotonic duration supplies the interval length. UTC only aligns people and
    # sessions. Microsecond resolution is explicit, never a claim of exact attention.
    end = begin + timedelta(microseconds=round(Fraction(duration_ns, 1000)))
    return start, begin, end, stop["status"] == "completed"


def activities(document: dict, root: Path) -> tuple[dict, set, list, dict]:
    people = document["actors"]
    by_person = defaultdict(list)
    unfinished, identities, seen_ids, seen_paths = set(), {}, set(), set()
    entries = list((root / "activities").rglob("*"))
    if (root / "activities").is_symlink() or any(path.is_symlink() for path in entries):
        raise ValueError("Activity records and their directory must not be symlinks")
    discovered = {path.resolve() for path in entries if path.is_file()}
    for name in document["activity_files"]:
        path = (root / nonempty(name)).resolve()
        if Path(name).is_absolute() or not path.is_relative_to((root / "activities").resolve()):
            raise ValueError("Activity files must remain inside the activities directory")
        if not (root / "activities").resolve().is_relative_to(root.resolve()):
            raise ValueError("The activities directory must not escape the ledger")
        if path in seen_paths:
            raise ValueError("Duplicate activity path")
        seen_paths.add(path)
        data = path.read_bytes()
        record, begin, end, complete = read_activity(data)
        if record["id"] in seen_ids:
            raise ValueError("Duplicate activity identity")
        seen_ids.add(record["id"])
        if record["actor"] not in people or record["case"] not in (
            *document["cases"],
            "preparation",
        ):
            raise ValueError("Activity has an unassigned actor or case")
        key = (record["arm"], record["phase"], record["actor"])
        identities[name] = hashlib.sha256(data).hexdigest()
        if not complete:
            unfinished.add(key)
        if end is not None:
            by_person[record["actor"]].append((begin, end, key, record["case"]))
    if seen_paths != discovered:
        raise ValueError("Retain every activity file, including interrupted and open prefixes")
    totals, overlaps = defaultdict(Fraction), []
    for person, spans in by_person.items():
        merged = []
        for begin, end, key, case in sorted(spans):
            if merged and begin < merged[-1][1]:
                previous = merged[-1]
                if (key, case) != (previous[2], previous[3]):
                    raise ValueError("One person's active intervals have conflicting allocations")
                overlaps.append(person)
                previous[1] = max(previous[1], end)
            else:
                merged.append([begin, end, key, case])
        for begin, end, key, _case in merged:
            totals[key] += Fraction(microseconds(end - begin), 1_000_000)
    return totals, unfinished, sorted(set(overlaps)), identities


def assess(document: dict, root: Path) -> dict:
    exact(
        document,
        (
            "schema",
            "kind",
            "scope",
            "protocol_reference",
            "actors",
            "cases",
            "activity_files",
            "coverage",
        ),
    )
    if document["schema"] != "nisayon.owner-effort.v1" or document["kind"] not in (
        "prepared",
        "synthetic_control",
        "owner_comparison",
    ):
        raise ValueError("Unknown ledger schema or kind")
    scope = nonempty(document["scope"])
    nonempty(document["protocol_reference"])
    if not isinstance(document["activity_files"], list):
        raise ValueError("Activity files must be an explicit list")
    if not isinstance(document["actors"], dict) or not document["actors"]:
        raise ValueError("Declare every participating person")
    rates = {}
    for actor, item in document["actors"].items():
        nonempty(actor)
        exact(item, ("role", "usd_per_hour"))
        if item["role"] not in ("owner", "engineering"):
            raise ValueError("Human roles are owner or engineering; agent runtime is separate")
        rates[actor] = quantity(item["usd_per_hour"])
    if not any(item["role"] == "owner" for item in document["actors"].values()):
        raise ValueError("An owner-effort comparison requires a declared owner")
    if not isinstance(document["cases"], dict) or not document["cases"]:
        raise ValueError("Retain every assigned case")
    expected, outcomes, pending, rejected = {}, {arm: {} for arm in ARMS[:2]}, [], []
    stages = set()
    for case, item in document["cases"].items():
        nonempty(case)
        if case == "preparation":
            raise ValueError("The preparation identity is reserved for costs")
        exact(item, ("stage", "selection_reference", "expected", "baseline", "candidate"))
        if item["stage"] not in ("initial", "reuse"):
            raise ValueError("Declare initial or reuse stage")
        stages.add(item["stage"])
        if item["selection_reference"] is None:
            pending.append(f"{case}:selection")
        else:
            nonempty(item["selection_reference"])
        if item["expected"] is None:
            pending.append(f"{case}:quality")
        elif item["expected"] not in DECISIONS:
            raise ValueError("Unknown expected decision")
        else:
            expected[case] = item["expected"]
        for arm in ARMS[:2]:
            row = item[arm]
            exact(row, ("decision", "valid", "reference", "owner_acceptance", "owner_reference"))
            if row["decision"] not in DECISIONS or type(row["valid"]) is not bool:
                raise ValueError("Unknown decision or evidence validity")
            nonempty(row["reference"])
            outcomes[arm][case] = {key: row[key] for key in ("decision", "valid", "reference")}
            acceptance = row["owner_acceptance"]
            if acceptance not in ("pending", "accepted", "rejected"):
                raise ValueError("Unknown owner acceptance")
            if acceptance == "pending":
                pending.append(f"{case}:{arm}:owner_review")
            else:
                nonempty(row["owner_reference"])
                if acceptance == "rejected":
                    rejected.append(f"{case}:{arm}")
    totals, unfinished, overlaps, identities = activities(document, root)
    exact(document["coverage"], ARMS)
    values, known, missing = {}, {}, []
    for arm in ARMS:
        exact(document["coverage"][arm], PHASES)
        for phase in PHASES:
            item = document["coverage"][arm][phase]
            exact(item, ("actors", "charges_usd"))
            exact(item["actors"], document["actors"])
            exact(item["charges_usd"], CHARGES)
            phase_usd, owner_seconds = Fraction(0), Fraction(0)
            for actor, declaration in item["actors"].items():
                exact(declaration, ("complete", "reference", "reason"))
                if type(declaration["complete"]) is not bool:
                    raise ValueError("Coverage completeness must be boolean")
                nonempty(
                    declaration["reference"] if declaration["complete"] else declaration["reason"]
                )
                key = (arm, phase, actor)
                seconds = totals[key]
                complete = declaration["complete"] and key not in unfinished
                known["/".join(key)] = seconds
                if not complete:
                    missing.append("/".join(key))
                if document["actors"][actor]["role"] == "owner":
                    owner_seconds = (
                        (owner_seconds + seconds)
                        if complete and owner_seconds is not None
                        else None
                    )
                rate = rates[actor]
                # A known zero duration needs no wage valuation. Unknown time
                # still blocks a total, even at a declared zero wage.
                cost = (
                    seconds * rate / 3600
                    if complete and rate is not None
                    else Fraction(0)
                    if complete and seconds == 0
                    else None
                )
                phase_usd = phase_usd + cost if phase_usd is not None and cost is not None else None
            for charge in item["charges_usd"].values():
                amount = quantity(charge)
                phase_usd = (
                    phase_usd + amount if phase_usd is not None and amount is not None else None
                )
            values[arm, phase] = (owner_seconds, phase_usd)
    ledgers = {unit: {} for unit in ("owner_active_seconds", "USD")}
    for index, unit in enumerate(ledgers):
        for arm in ARMS[:2]:
            phases = {}
            for phase in PHASES:
                own, shared = values[arm, phase][index], values["shared", phase][index]
                value = own + shared if own is not None and shared is not None else None
                phases[phase] = {
                    "value": value,
                    "reference": "receipt-bound activity and coverage in this report",
                    "reason": "Incomplete coverage, interruption, charges or valuation"
                    if value is None
                    else "",
                }
            ledgers[unit][arm] = {"unit": unit, "scope": scope, "phases": phases}
    comparisons = {}
    if len(expected) == len(document["cases"]):
        for unit, pair in ledgers.items():
            comparisons[unit] = assess_cost_target(
                expected,
                **outcomes,
                baseline_costs=pair["baseline"],
                candidate_costs=pair["candidate"],
            )
    complete = comparisons.get("USD", {})
    reasons = list(pending) + [f"complete_cost:{reason}" for reason in complete.get("reasons", [])]
    if stages != {"initial", "reuse"}:
        reasons.append("initial_and_separate_reuse_required")
    if document["kind"] != "owner_comparison":
        reasons.append("no_owner_experiment")
    status = "unresolved"
    if rejected or complete.get("status") == "contradicted":
        status = "contradicted"
    elif not reasons:
        status = complete.get("status", "unresolved")
    report = {
        "schema": "nisayon.owner-effort-report.v2",
        "kind": document["kind"],
        "status": status,
        "scope": scope,
        "assigned_cases": list(document["cases"]),
        "activity_sha256": identities,
        "known_active_seconds_by_arm_phase_person": dict(sorted(known.items())),
        "overlapping_timers_unioned_for": overlaps,
        "incomplete_activity_or_coverage": sorted(missing),
        "owner_rejected": rejected,
        "reasons": reasons,
        "phase_ledgers": ledgers,
        "study_phase_totals": {
            unit: {
                phase: sum(values[arm, phase][index] for arm in ARMS)
                if all(values[arm, phase][index] is not None for arm in ARMS)
                else None
                for phase in PHASES
            }
            for index, unit in enumerate(ledgers)
        },
        "finite_comparisons": comparisons,
        "baseline_minus_candidate_owner_seconds_by_phase": {
            phase: values["baseline", phase][0] - values["candidate", phase][0]
            if values["baseline", phase][0] is not None
            and values["candidate", phase][0] is not None
            else None
            for phase in PHASES
        },
        "premises": "Operator-reported attention, all assigned cases and people, complete coverage, disjoint charges, rates, expected decisions and owner receipts require external checking. Shared work is charged once to each arm. No causal or population savings estimate; no authentication, independent review or attention detection.",
    }
    return display_quantities(report)


def track(path: Path, *, actor: str, arm: str, case: str, phase: str, reference: str) -> int:
    """A durable prefix survives EOF, interruption or termination; never overwrite."""
    for value in (actor, case, reference):
        nonempty(value)
    if arm not in ARMS or phase not in PHASES:
        raise ValueError("Unknown activity arm or phase")
    if not sys.stdin.isatty():
        raise ValueError("Interactive human timer requires a terminal")
    identity = uuid.uuid4().hex
    with path.open("x") as stream:

        def append(record):
            stream.write(json.dumps(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        append(
            {
                "event": "start",
                "id": identity,
                "actor": actor,
                "arm": arm,
                "case": case,
                "phase": phase,
                "reference": reference,
                "utc": datetime.now(UTC).isoformat(),
                "ns": time.monotonic_ns(),
            }
        )
        print(
            "Active human interval started. Press Enter to stop; stop before waiting or switching work.",
            flush=True,
        )
        status = "completed"
        try:
            if sys.stdin.readline() == "":
                status = "interrupted"
        except KeyboardInterrupt:
            status = "interrupted"
        append(
            {
                "event": "stop",
                "id": identity,
                "utc": datetime.now(UTC).isoformat(),
                "ns": time.monotonic_ns(),
                "status": status,
            }
        )
    return 0 if status == "completed" else 1


def prepared_ledger(scope: str, protocol: str) -> dict:
    def unknown():
        return {"value": None, "reference": "", "reason": "Not measured"}

    def outcome():
        return {
            "decision": "unresolved",
            "valid": False,
            "reference": "Not executed",
            "owner_acceptance": "pending",
            "owner_reference": None,
        }

    return {
        "schema": "nisayon.owner-effort.v1",
        "kind": "prepared",
        "scope": nonempty(scope),
        "protocol_reference": nonempty(protocol),
        "actors": {
            actor: {"role": role, "usd_per_hour": unknown()}
            for actor, role in (("owner", "owner"), ("builder", "engineering"))
        },
        "cases": {
            stage: {
                "stage": stage,
                "selection_reference": None,
                "expected": None,
                "baseline": outcome(),
                "candidate": outcome(),
            }
            for stage in ("initial", "reuse")
        },
        "activity_files": [],
        "coverage": {
            arm: {
                phase: {
                    "actors": {
                        actor: {"complete": False, "reference": "", "reason": "Not measured"}
                        for actor in ("owner", "builder")
                    },
                    "charges_usd": {charge: unknown() for charge in CHARGES},
                }
                for phase in PHASES
            }
            for arm in ARMS
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    initialize = sub.add_parser("init", help="Create an unmeasured, unenrolled ledger")
    initialize.add_argument("output", type=Path)
    initialize.add_argument("--scope", required=True)
    initialize.add_argument("--protocol-reference", required=True)
    timer = sub.add_parser("track", help="Record one operator-reported active interval")
    timer.add_argument("output", type=Path)
    for name in ("actor", "case", "reference"):
        timer.add_argument(f"--{name}", required=True)
    timer.add_argument("--arm", choices=ARMS, required=True)
    timer.add_argument("--phase", choices=PHASES, required=True)
    report = sub.add_parser("assess", help="Read a declared ledger without executing owner code")
    report.add_argument("ledger", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            document = prepared_ledger(args.scope, args.protocol_reference)
            with args.output.open("x") as stream:
                stream.write(json.dumps(document, indent=2) + "\n")
            return 0
        if args.command == "track":
            return track(
                args.output,
                actor=args.actor,
                arm=args.arm,
                case=args.case,
                phase=args.phase,
                reference=args.reference,
            )
        data = args.ledger.read_bytes()
        result = assess(read_json(data.decode()), args.ledger.parent)
        result["ledger_sha256"] = hashlib.sha256(data).hexdigest()
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        print(json.dumps({"status": "invalid", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
