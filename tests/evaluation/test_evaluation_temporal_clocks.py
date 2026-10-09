"""The clock-declaration boundary of the temporal reference and admitted chunk identity.

Premises stated per block. Each test names the earlier reading it separates from; the
committed C01–C04 and Y01–Y04 traces of the execution lane are read as data where the
exact record that raised the issue is needed.
"""

from __future__ import annotations

import copy
import itertools
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from nisayon.evaluation import temporal

REPO = Path(__file__).resolve().parents[2]
PRODUCER = REPO / "docs/experiments/results/temporal-integration-001"
INPUTS = REPO / "docs/evaluation/results/temporal-integration-001/followthrough/clock/inputs"
CONFIG = "18c49d0ea9f8035895308a4c33f39e263f8a8676982bd8a91d9edc2e9970d40c"
NS = 1_000_000
FRESH = {"from": "sensor", "to": "controller", "offset": 0, "uncertainty": 0, "unit": "ns"}
STALE = {**FRESH, "offset": -100 * NS}


def stamp(value, clock="controller", unit="ns"):
    return {"value": value, "clock": clock, "unit": unit}


def sensor_case(mappings, *, names=("controller", "sensor"), dispatch=20 * NS, acquired=0):
    """observe on the sensor clock -> request -> response -> admit -> dispatch (+ ack).

    Premises: the observation is held by the driver at controller 0 (a same-clock lower
    bound on its age), the request is controller-stamped at 1 ms, the limit is 50 ms
    inclusive, and the only frozen opportunity is the dispatch.
    """
    events = [
        {"kind": "episode_start", "generation": 0, "at": stamp(0)},
        {
            "kind": "observation_acquired",
            "obs_id": "o0",
            "generation": 0,
            "step": 0,
            "at": stamp(acquired, "sensor"),
            "observed_by_driver_at": stamp(0),
        },
        {
            "kind": "request_sent",
            "req_id": "q0",
            "obs_id": "o0",
            "generation": 0,
            "config_sha256": CONFIG,
            "at": stamp(1 * NS),
        },
        {
            "kind": "response_arrived",
            "resp_id": "r0",
            "req_id": "q0",
            "chunk_id": "c0",
            "generation": 0,
            "config_sha256": CONFIG,
            "first_step": 0,
            "ordinals": 1,
            "at": stamp(10 * NS),
        },
        {"kind": "queue_admitted", "chunk_id": "c0", "admitted": [0], "at": stamp(10 * NS)},
        {
            "kind": "action_dispatched",
            "action_id": "c0:0",
            "chunk_id": "c0",
            "ordinal": 0,
            "step": 0,
            "generation": 0,
            "dispatch_id": "d0",
            "input_id": "in-dispatch",
            "at": stamp(dispatch),
        },
        {
            "kind": "dispatch_acknowledged",
            "action_id": "c0:0",
            "dispatch_id": "d0",
            "at": stamp(dispatch),
        },
    ]
    trace = {
        "schema": temporal.SCHEMA,
        "case_id": "clock-unit",
        "execution_status": "completed",
        "configuration": {
            "config_sha256": CONFIG,
            "control_period": 10 * NS,
            "max_age": 50 * NS,
            "time_unit": "ns",
        },
        "minimum_dispatches": 1,
        "usefulness_contract": {
            "basis": "frozen_case_dispatch_target",
            "minimum_dispatches": 1,
            "scope": "whole_case",
            "dispatch_opportunities": [{"input_id": "in-dispatch", "at": stamp(dispatch)}],
        },
        "events": [{**e, "seq": i} for i, e in enumerate(events)],
    }
    if names is not None or mappings is not None:
        trace["clocks"] = {}
        if names is not None:
            trace["clocks"]["names"] = list(names)
        if mappings is not None:
            trace["clocks"]["declared_mappings"] = copy.deepcopy(mappings)
    return trace


def reading(assessment):
    return assessment["age_readings"][0] if assessment["age_readings"] else None


def verdict(assessment):
    """The semantic outcome a permutation or rename must preserve."""
    r = reading(assessment)
    return (
        assessment["temporal_contract"],
        assessment["assigned_contract"],
        assessment["predicates"]["freshness"]["status"],
        r["chronology"] if r else None,
        tuple(r["interval_used"]) if r and r["interval_used"] else None,
        r["classification"] if r else None,
        assessment["evidence"]["clocks"]["status"],
    )


# --- the counterexample: order must not select a calibration --------------------------------


def test_conflicting_declarations_read_the_same_whatever_their_order():
    first = temporal.assess(sensor_case([FRESH, STALE]))
    second = temporal.assess(sensor_case([STALE, FRESH]))
    assert verdict(first) == verdict(second)
    assert first["predicates"]["freshness"]["status"] == "unresolved"
    assert reading(first)["chronology"] == "conflicting_declarations"
    assert reading(first)["interval_used"] is None
    assert first["assigned_contract"] == "unresolved"
    assert first["evidence"]["clocks"]["status"] == "conflicting"
    assert first["evidence"]["clocks"]["conflicting_pairs"] == [["controller", "sensor"]]
    detail = first["predicates"]["freshness"]["findings"][0]["detail"]
    assert "no consistent calibration" in detail and "alternatives" in detail


def test_single_declarations_keep_their_fresh_and_stale_readings():
    fresh = temporal.assess(sensor_case([FRESH]))
    stale = temporal.assess(sensor_case([STALE]))
    assert fresh["predicates"]["freshness"]["status"] == "satisfied"
    assert reading(fresh)["interval_used"] == [20 * NS, 20 * NS]
    assert stale["predicates"]["freshness"]["status"] == "violated"
    assert reading(stale)["interval_used"] == [120 * NS, 120 * NS]
    assert (
        fresh["evidence"]["clocks"]["status"]
        == stale["evidence"]["clocks"]["status"]
        == "supported"
    )


def test_retained_c_cases_read_as_the_rule_says():
    traces = PRODUCER / "clock-conformance-execution-001/traces"
    expected = {
        "C01-single-fresh-mapping": ("satisfied", "satisfied", "mapped"),
        "C02-conflicting-fresh-first": ("unresolved", "unresolved", "conflicting_declarations"),
        "C03-conflicting-stale-first": ("unresolved", "unresolved", "conflicting_declarations"),
        "C04-single-stale-mapping": ("violated", "violated", "mapped"),
    }
    for case, (freshness, assigned, chronology) in expected.items():
        unfenced = temporal.assess(
            json.loads((traces / f"{case}--unfenced_queue_control.json").read_text())
        )
        assert unfenced["predicates"]["freshness"]["status"] == freshness, case
        assert unfenced["assigned_contract"] == assigned, case
        assert reading(unfenced)["chronology"] == chronology, case
        conventional = temporal.assess(
            json.loads((traces / f"{case}--conventional.json").read_text())
        )
        # The producer's guard refused every case but C01; the reference does not read the
        # guard, and its evidence status for the declarations is the same under both remedies.
        assert (
            conventional["evidence"]["clocks"]["status"] == unfenced["evidence"]["clocks"]["status"]
        )
    c02 = temporal.assess(
        json.loads(
            (traces / "C02-conflicting-fresh-first--unfenced_queue_control.json").read_text()
        )
    )
    c03 = temporal.assess(
        json.loads(
            (traces / "C03-conflicting-stale-first--unfenced_queue_control.json").read_text()
        )
    )
    assert verdict(c02) == verdict(c03)


def test_chain_evidence_still_proves_expiry_under_conflicting_declarations():
    # The same-clock lower bound is a separate premise and survives the conflict.
    assessment = temporal.assess(sensor_case([FRESH, STALE], dispatch=60 * NS))
    assert assessment["predicates"]["freshness"]["status"] == "violated"
    assert reading(assessment)["chronology"] == "conflicting_declarations"
    assert reading(assessment)["chain_lower_bound"] == 60 * NS


# --- interval constraints: nonempty versus inconsistent -----------------------------------


def test_admissible_age_set_must_be_nonempty_and_inside_the_limit():
    # Consistent premise: one relation, uncertainty widening.
    for uncertainty, expected in [(0, "within"), (30 * NS, "within"), (30 * NS + 1, "overlapping")]:
        a = temporal.assess(sensor_case([{**FRESH, "uncertainty": uncertainty}]))
        assert reading(a)["classification"] == expected, uncertainty
    # Empty set: the relation places the acquisition after documented possession.
    contradiction = temporal.assess(sensor_case([{**FRESH, "offset": 30 * NS}]))
    assert reading(contradiction)["classification"] == "inconsistent"
    assert contradiction["predicates"]["freshness"]["status"] == "unresolved"


def test_exact_equality_and_one_unit_expiry_through_a_mapping_at_a_large_epoch():
    epoch = 2**60
    relation = {**FRESH, "offset": -epoch}  # controller = sensor - 2^60
    equal = temporal.assess(sensor_case([relation], acquired=epoch, dispatch=50 * NS))
    assert reading(equal)["interval_used"] == [50 * NS, 50 * NS]
    assert equal["predicates"]["freshness"]["status"] == "satisfied"
    over = temporal.assess(sensor_case([relation], acquired=epoch, dispatch=50 * NS + 1))
    assert reading(over)["interval_used"] == [50 * NS + 1, 50 * NS + 1]
    assert over["predicates"]["freshness"]["status"] == "violated"
    interval = temporal.age_interval(stamp(50 * NS + 1), stamp(epoch, "sensor"), [relation])
    assert interval == (Fraction(50 * NS + 1), Fraction(50 * NS + 1))


# --- invariances stated as properties, on a small deterministic table ----------------------


DECLARATION_SETS = {
    "single": [FRESH],
    "conflict": [FRESH, STALE],
    "duplicate": [FRESH, dict(FRESH)],
    "reverse_pair": [
        FRESH,
        {"from": "controller", "to": "sensor", "offset": 0, "uncertainty": 0, "unit": "ns"},
    ],
    "uncertain_conflict": [FRESH, {**FRESH, "uncertainty": 5 * NS}],
}


def test_declaration_order_carries_no_meaning():
    for name, declarations in DECLARATION_SETS.items():
        verdicts = {
            verdict(temporal.assess(sensor_case(list(order))))
            for order in itertools.permutations(declarations)
        }
        assert len(verdicts) == 1, name


def test_reverse_direction_is_the_same_relation():
    forward = temporal.assess(sensor_case([FRESH]))
    backward = temporal.assess(
        sensor_case(
            [{"from": "controller", "to": "sensor", "offset": 0, "uncertainty": 0, "unit": "ns"}]
        )
    )
    assert verdict(forward) == verdict(backward)
    both = temporal.assess(sensor_case(DECLARATION_SETS["reverse_pair"]))
    assert verdict(both) == verdict(forward)
    assert both["evidence"]["clocks"]["relations"][0]["declarations"] == [0, 1]
    assert [d["category"] for d in both["evidence"]["clock_diagnostics"]] == [
        "duplicate_declaration"
    ]
    reversed_stale = {
        "from": "controller",
        "to": "sensor",
        "offset": 100 * NS,
        "uncertainty": 0,
        "unit": "ns",
    }
    assert verdict(temporal.assess(sensor_case([reversed_stale]))) == verdict(
        temporal.assess(sensor_case([STALE]))
    )


def test_consistent_clock_origin_translation_changes_nothing():
    base = sensor_case([{**FRESH, "offset": 7, "uncertainty": 3}])
    moved = copy.deepcopy(base)
    controller_shift, sensor_shift = 2**54, 2**53 + 11
    for event in moved["events"]:
        for key in ("at", "observed_by_driver_at"):
            value = event.get(key)
            if isinstance(value, dict):
                value["value"] += (
                    controller_shift if value["clock"] == "controller" else sensor_shift
                )
    for opportunity in moved["usefulness_contract"]["dispatch_opportunities"]:
        opportunity["at"]["value"] += controller_shift
    moved["clocks"]["declared_mappings"][0]["offset"] += controller_shift - sensor_shift
    assert verdict(temporal.assess(moved)) == verdict(temporal.assess(base))


def test_bijective_clock_rename_preserving_the_controller_role_changes_nothing():
    base = sensor_case([FRESH, STALE])
    renamed = json.loads(json.dumps(base).replace("controller", "ctl").replace("sensor", "sns"))
    assert renamed["clocks"]["names"] == ["ctl", "sns"]
    assert verdict(temporal.assess(renamed))[:6] == verdict(temporal.assess(base))[:6]
    # Reordering the names list moves the controller role: not a rename, a different premise.
    reordered = copy.deepcopy(base)
    reordered["clocks"]["names"] = ["sensor", "controller"]
    assert temporal.assess(reordered)["controller_clock"] == "sensor"


def test_uncertainty_widening_never_creates_freshness_from_an_unsupported_reading():
    # Premise fixed: the conflicting pair. Widening either declaration adds admissible
    # ages under any reading and never yields an unqualified fresh verdict.
    for widen in (0, NS, 40 * NS, 200 * NS):
        wide = [{**FRESH, "uncertainty": widen}, {**STALE, "uncertainty": widen}]
        a = temporal.assess(sensor_case(wide))
        assert a["predicates"]["freshness"]["status"] == "unresolved", widen
        assert reading(a)["chronology"] == "conflicting_declarations"


# --- malformed, unsupported and legacy declarations --------------------------------------


def test_malformed_containers_and_members_are_named_problems_and_never_raise():
    scalar = temporal.assess(sensor_case(1))
    assert scalar["temporal_contract"] == "invalid" and scalar["assigned_contract"] == "invalid"
    assert scalar["evidence"]["problems"] == [
        "clocks.declared_mappings is int, not a list; no relation is used"
    ]
    assert scalar["predicates"]["freshness"]["status"] == "unresolved"
    obj = temporal.assess(sensor_case(dict(FRESH)))
    assert obj["temporal_contract"] == "invalid"
    member = temporal.assess(sensor_case([None, FRESH]))
    assert member["temporal_contract"] == "invalid"
    assert member["evidence"]["problems"] == ["clocks.declared_mappings[0] is not an object"]
    # The valid member is not used: a malformed neighbour may be an unreadable conflict.
    assert reading(member)["chronology"] == "malformed_declarations"
    assert member["evidence"]["clocks"]["relations"] == []
    negative = temporal.assess(sensor_case([{**FRESH, "uncertainty": -1}]))
    assert negative["temporal_contract"] == "invalid"
    assert "negative" in negative["evidence"]["problems"][0]
    boolean = temporal.assess(sensor_case([{**FRESH, "offset": True}]))
    assert boolean["temporal_contract"] == "invalid"
    nan = temporal.assess(sensor_case([{**FRESH, "offset": float("nan")}]))
    assert nan["temporal_contract"] == "invalid"
    self_relation = temporal.assess(sensor_case([{**FRESH, "to": "sensor"}]))
    assert self_relation["temporal_contract"] == "invalid"
    not_object = temporal.assess({**sensor_case([FRESH]), "clocks": 3})
    assert not_object["temporal_contract"] == "invalid"
    assert not_object["evidence"]["problems"] == ["clocks is not an object"]


def test_unsupported_declarations_leave_the_pair_unmapped_and_unresolved():
    rate = temporal.assess(sensor_case([{**FRESH, "rate": 1.0}]))
    assert rate["temporal_contract"] != "invalid"
    assert rate["predicates"]["freshness"]["status"] == "unresolved"
    assert reading(rate)["chronology"] == "unsupported_declaration"
    assert rate["evidence"]["clocks"]["status"] == "unsupported"
    assert "rate" in rate["evidence"]["clock_diagnostics"][0]["detail"]
    units = temporal.assess(sensor_case([{**FRESH, "unit": "ms"}]))
    assert reading(units)["chronology"] == "unit_mismatch"
    assert units["predicates"]["freshness"]["status"] == "unresolved"
    composed = temporal.assess(
        sensor_case(
            [
                {"from": "sensor", "to": "gps", "offset": 0, "uncertainty": 0, "unit": "ns"},
                {"from": "gps", "to": "controller", "offset": 0, "uncertainty": 0, "unit": "ns"},
            ],
            names=("controller", "sensor", "gps"),
        )
    )
    assert reading(composed)["chronology"] == "unmapped"  # no composition through gps


def test_undeclared_clocks_and_missing_names_are_legacy_rules_not_observations():
    undeclared = temporal.assess(sensor_case([FRESH], names=("controller",)))
    assert undeclared["predicates"]["freshness"]["status"] == "unresolved"
    assert reading(undeclared)["chronology"] == "undeclared_clock"
    assert undeclared["evidence"]["clocks"]["undeclared_clocks"] == ["sensor"]
    missing = temporal.assess(sensor_case([FRESH], names=None))
    assert missing["evidence"]["clocks"]["legacy_rule"].startswith("names_absent")
    assert reading(missing)["chronology"] == "undeclared_clock"
    assert missing["predicates"]["freshness"]["status"] == "unresolved"
    absent = temporal.assess(sensor_case(None, names=None))
    assert absent["evidence"]["clocks"]["legacy_rule"].startswith("clocks_absent")
    assert absent["predicates"]["freshness"]["status"] == "unresolved"
    # The legacy form still supports controller-only traces exactly.
    same = sensor_case(None, names=None)
    same["events"][1]["at"] = stamp(0)
    assert temporal.assess(same)["predicates"]["freshness"]["status"] == "satisfied"


def test_public_command_returns_a_structured_result_on_the_scalar_container(tmp_path):
    source = INPUTS / "mapping_container_scalar.json"
    out = tmp_path / "assessment.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "temporal",
            str(source),
            "--json",
            "--out",
            str(out),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assessment = json.loads(out.read_text())
    assert assessment["temporal_contract"] == "invalid"
    assert assessment["evidence"]["problems"][0].startswith("clocks.declared_mappings is int")


# --- admitted chunk identity (Y02) --------------------------------------------------------


def test_a_rejected_delivery_does_not_rebind_the_queued_action():
    traces = PRODUCER / "admission-conformance-execution-001/traces"
    conventional = temporal.assess(
        json.loads((traces / "Y02-rejected-conflicting-delivery--conventional.json").read_text())
    )
    assert reading(conventional)["interval_used"] == [20 * NS, 20 * NS]
    assert conventional["predicates"]["freshness"]["status"] == "satisfied"
    assert conventional["assigned_contract"] == "satisfied"
    assert conventional["evidence"]["identity_conflicts"][0]["disposition"] == "rejected"
    assert conventional["retrospective"]["chunk_identity"]["status"] == "satisfied"
    unfenced = temporal.assess(
        json.loads(
            (traces / "Y02-rejected-conflicting-delivery--unfenced_queue_control.json").read_text()
        )
    )
    assert reading(unfenced)["interval_used"] == [120 * NS, 120 * NS]
    assert unfenced["predicates"]["freshness"]["status"] == "violated"
    assert unfenced["evidence"]["identity_conflicts"][0]["disposition"] == "admitted"
    assert unfenced["retrospective"]["chunk_identity"]["status"] == "violated"
    for case in ("Y01-fresh-queued-action", "Y04-rejected-identical-delivery"):
        a = temporal.assess(json.loads((traces / f"{case}--conventional.json").read_text()))
        assert (
            a["evidence"]["identity_conflicts"] == []
            and a["predicates"]["freshness"]["status"] == "satisfied"
        )
    y03 = temporal.assess(
        json.loads(
            (traces / "Y03-stale-distinct-replacement--unfenced_queue_control.json").read_text()
        )
    )
    assert (
        y03["evidence"]["identity_conflicts"] == []
    )  # a distinct chunk id is a replacement, not a conflict
    assert y03["predicates"]["freshness"]["status"] == "violated"


def test_a_conflicting_delivery_without_an_admission_decision_stays_pending():
    trace = sensor_case([FRESH])
    events = trace["events"]
    conflicting = {
        **events[3],
        "resp_id": "r-later",
        "req_id": "q-unknown",
        "seq": 99,
        "at": stamp(14 * NS),
    }
    trace["events"] = (
        events[:5] + [conflicting] + [{**e, "seq": e["seq"] + 100} for e in events[5:]]
    )
    assessment = temporal.assess(trace)
    assert reading(assessment)["interval_used"] == [20 * NS, 20 * NS]  # the admitted version
    assert assessment["retrospective"]["chunk_identity"]["status"] == "unresolved"
    assert assessment["evidence"]["identity_conflicts"][0]["disposition"] == "pending"
    assert assessment["evidence"]["completeness"] == "incomplete"
