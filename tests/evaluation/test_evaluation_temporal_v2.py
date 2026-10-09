"""Discriminating tests for the version-2 temporal reference: one block per issue.

Each test states the old reading it separates from, on a trace small enough to check by
hand. Producer traces retained under docs/experiments are read as data where a test needs
the exact record that raised the issue.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction
from pathlib import Path

from nisayon.evaluation import temporal

REPO = Path(__file__).resolve().parents[2]
PRODUCER = REPO / "docs/experiments/results/temporal-integration-001"
CONFIG = "18c49d0ea9f8035895308a4c33f39e263f8a8676982bd8a91d9edc2e9970d40c"
OTHER = "7bc9430a5d79f3e343eeab0bc28f1bb8f10b08a8086aeca723fdf425c646ff4f"
NS = 1_000_000


def stamp(value, clock="controller"):
    return {"value": value, "clock": clock, "unit": "ns"}


def trace(events: list[dict], **overrides) -> dict:
    """A minimal trace: one controller clock, 10 ms period, 50 ms inclusive limit."""
    base = {
        "schema": temporal.SCHEMA,
        "case_id": "unit",
        "execution_status": "completed",
        "clocks": {"names": ["controller", "sensor"], "declared_mappings": []},
        "configuration": {
            "config_sha256": CONFIG,
            "control_period": 10 * NS,
            "max_age": 50 * NS,
            "time_unit": "ns",
        },
        "events": [{**e, "seq": i} for i, e in enumerate(events)],
    }
    base.update(overrides)
    return base


def chain(acquired_at, dispatch_at, *, request_at=None, held_at=None, activation=None):
    """observe → request → response → admit → dispatch → acknowledge, one action."""
    observation = {
        "kind": "observation_acquired",
        "obs_id": "o0",
        "generation": 0,
        "step": 0,
        "at": acquired_at,
    }
    if held_at is not None:
        observation["observed_by_driver_at"] = held_at
    request = {
        "kind": "request_sent",
        "req_id": "q0",
        "obs_id": "o0",
        "generation": 0,
        "config_sha256": CONFIG,
        "at": request_at or stamp(1 * NS),
    }
    if activation is not None:
        request["activation"] = activation
    return [
        {"kind": "episode_start", "generation": 0, "at": stamp(0)},
        observation,
        request,
        {
            "kind": "response_arrived",
            "resp_id": "r0",
            "req_id": "q0",
            "chunk_id": "c0",
            "generation": 0,
            "config_sha256": CONFIG,
            "first_step": 0,
            "ordinals": 1,
            "at": stamp(2 * NS),
        },
        {"kind": "queue_admitted", "chunk_id": "c0", "admitted": [0], "at": stamp(2 * NS)},
        {
            "kind": "action_dispatched",
            "action_id": "c0:0",
            "chunk_id": "c0",
            "ordinal": 0,
            "step": 0,
            "generation": 0,
            "dispatch_id": "d0",
            "input_id": "in-dispatch",
            "at": dispatch_at,
        },
        {
            "kind": "dispatch_acknowledged",
            "action_id": "c0:0",
            "dispatch_id": "d0",
            "at": dispatch_at,
        },
    ]


def status(assessment, predicate):
    return assessment["predicates"][predicate]["status"]


def reading(assessment, index=0):
    return assessment["age_readings"][index]


# --- E. exact deadline arithmetic ---------------------------------------------------------


def shifted(events: list[dict], epoch: int) -> list[dict]:
    """The same events with every controller stamp translated by a constant epoch."""
    moved = copy.deepcopy(events)
    for event in moved:
        for key in ("at", "observed_by_driver_at"):
            if isinstance(event.get(key), dict) and event[key]["clock"] == "controller":
                event[key] = stamp(event[key]["value"] + epoch)
    return moved


def test_deadline_equality_is_within_and_one_nanosecond_beyond_is_violated_at_any_epoch():
    for epoch in (0, 2**54, 2**60):
        equal = temporal.assess(trace(shifted(chain(stamp(0), stamp(50 * NS)), epoch)))
        assert status(equal, "freshness") == "satisfied", epoch
        assert reading(equal)["interval_used"] == [50 * NS, 50 * NS]
        over = temporal.assess(trace(shifted(chain(stamp(0), stamp(50 * NS + 1)), epoch)))
        assert status(over, "freshness") == "violated", epoch
        assert reading(over)["interval_used"] == [50 * NS + 1, 50 * NS + 1]


def test_float_conversion_would_have_lost_the_excess_at_two_to_the_54():
    # The version-1 defect, stated as arithmetic: at 2^54 the float spacing is 4 ns.
    assert float(2**54 + 50 * NS + 1) - float(2**54) == 50 * NS
    interval = temporal.age_interval(stamp(2**54 + 50 * NS + 1), stamp(2**54), [])
    assert interval == (Fraction(50 * NS + 1), Fraction(50 * NS + 1))


def test_constant_clock_origin_shift_does_not_change_any_duration_verdict():
    events = chain(stamp(0), stamp(50 * NS + 1))
    unshifted = temporal.assess(trace(events))
    moved = temporal.assess(trace(shifted(events, 2**54)))
    assert status(unshifted, "freshness") == status(moved, "freshness") == "violated"
    assert reading(unshifted)["interval_used"] == reading(moved)["interval_used"]
    assert (
        unshifted["useful_execution"]["coverage_by_generation"]["0"]["coverage"]
        == moved["useful_execution"]["coverage_by_generation"]["0"]["coverage"]
    )


def test_mapped_clock_boundary_is_exact_in_offset_and_uncertainty():
    mapping = {"from": "sensor", "to": "controller", "offset": 7, "uncertainty": 3, "unit": "ns"}
    # acquisition 100 on the sensor clock is 107 +- 3 on the controller clock.
    exact = temporal.age_interval(stamp(107 + 50 * NS), stamp(100, "sensor"), [mapping])
    assert exact == (50 * NS - 3, 50 * NS + 3)
    inside = temporal.age_interval(stamp(107 + 50 * NS - 3), stamp(100, "sensor"), [mapping])
    assert temporal.classify_age(inside, 50 * NS) == "within"
    beyond = temporal.age_interval(stamp(107 + 50 * NS + 4), stamp(100, "sensor"), [mapping])
    assert temporal.classify_age(beyond, 50 * NS) == "beyond"
    assert temporal.classify_age(exact, 50 * NS) == "overlapping"


def test_non_integer_inputs_are_computed_exactly_and_flagged():
    assessment = temporal.assess(trace(chain(stamp(0.5), stamp(50 * NS + 0.5))))
    assert status(assessment, "freshness") == "satisfied"
    assert reading(assessment)["interval_used"] == [50 * NS, 50 * NS]
    assert reading(assessment)["non_integer_inputs"] is True
    assert assessment["evidence"]["non_integer_stamps"] is True
    # A third of a nanosecond survives as an exact fraction, not a rounded float.
    third = temporal.age_interval(stamp(Fraction(1, 3) + 5), stamp(Fraction(1, 3)), [])
    assert third == (5, 5)


def test_retained_x06_trace_reads_violated_with_the_one_nanosecond_excess():
    path = PRODUCER / "precision-execution-001/traces"
    for remedy in ("unfenced_queue_control", "reset_only", "arrival_deadline_only"):
        record = json.loads((path / f"X06-deadline-resolution-boundary--{remedy}.json").read_text())
        assessment = temporal.assess(record)
        assert status(assessment, "freshness") == "violated", remedy
        assert reading(assessment)["interval_used"] == [50 * NS + 1, 50 * NS + 1]


# --- D. chronology and clock uncertainty ---------------------------------------------------


def crossing_zero(held_at=None, request_at=None):
    mapping = {
        "from": "sensor",
        "to": "controller",
        "offset": 0,
        "uncertainty": 10 * NS,
        "unit": "ns",
    }
    events = chain(stamp(0, "sensor"), stamp(3 * NS), held_at=held_at, request_at=request_at)
    return trace(
        events,
        clocks={"names": ["controller", "sensor"], "declared_mappings": [mapping]},
    )


def test_interval_crossing_zero_is_unresolved_without_chain_evidence_and_never_clamped():
    request_on_sensor = stamp(1 * NS, "sensor")
    assessment = temporal.assess(crossing_zero(request_at=request_on_sensor))
    assert status(assessment, "freshness") == "unresolved"
    r = reading(assessment)
    assert r["mapped_interval"] == [-7 * NS, 13 * NS]
    assert r["chain_lower_bound"] is None
    assert r["classification"] == "chronology_unresolved"
    assert r["interval_used"] == [-7 * NS, 13 * NS]  # reported as declared, not clamped


def test_same_clock_chain_evidence_bounds_the_age_and_records_the_premise():
    assessment = temporal.assess(crossing_zero(held_at=stamp(0)))
    assert status(assessment, "freshness") == "satisfied"
    r = reading(assessment)
    assert r["chain_lower_bound"] == 3 * NS
    assert r["interval_used"] == [3 * NS, 13 * NS]
    assert "acquisition precedes possession" in r["premise"]
    finding = assessment["predicates"]["freshness"]["findings"][0]
    assert finding["status"] == "satisfied" and "chain premise" in finding["detail"]
    # Without the driver stamp the controller-stamped request still bounds it, more loosely.
    weaker = temporal.assess(crossing_zero())
    assert reading(weaker)["chain_lower_bound"] == 2 * NS
    assert reading(weaker)["interval_used"] == [2 * NS, 13 * NS]


def test_mapping_disjoint_from_chain_evidence_is_inconsistent():
    mapping = {
        "from": "sensor",
        "to": "controller",
        "offset": 100 * NS,
        "uncertainty": NS,
        "unit": "ns",
    }
    assessment = temporal.assess(
        trace(
            chain(stamp(0, "sensor"), stamp(3 * NS), held_at=stamp(0)),
            clocks={"names": ["controller", "sensor"], "declared_mappings": [mapping]},
        )
    )
    assert status(assessment, "freshness") == "unresolved"
    assert reading(assessment)["chronology"] == "mapping_contradicts_chain"
    assert reading(assessment)["classification"] == "inconsistent"


def test_chain_evidence_alone_can_prove_staleness_without_a_mapping():
    # Unmapped sensor clock, but the controller-stamped request is 60 ms before dispatch.
    events = chain(stamp(0, "sensor"), stamp(61 * NS), request_at=stamp(1 * NS))
    assessment = temporal.assess(trace(events))
    assert status(assessment, "freshness") == "violated"
    r = reading(assessment)
    assert r["chronology"] == "unmapped" and r["mapped_interval"] is None
    assert r["chain_lower_bound"] == 60 * NS and r["classification"] == "beyond"


def test_arrival_is_a_bound_on_age_and_never_the_acquisition_time():
    events = chain(None, stamp(20 * NS), held_at=stamp(0))
    assessment = temporal.assess(trace(events))
    assert status(assessment, "freshness") == "unresolved"
    r = reading(assessment)
    assert r["chronology"] == "absent_acquisition"
    assert r["mapped_interval"] is None and r["chain_lower_bound"] == 20 * NS


def test_chronology_categories_stay_distinct():
    same = temporal.assess(trace(chain(stamp(0), stamp(3 * NS))))
    assert reading(same)["chronology"] == "same_clock"
    unmapped = temporal.assess(trace(chain(stamp(0, "sensor"), stamp(3 * NS))))
    assert reading(unmapped)["chronology"] == "unmapped"
    mapped = temporal.assess(crossing_zero(held_at=stamp(0)))
    assert reading(mapped)["chronology"] == "mapped"
    whole_negative = temporal.assess(trace(chain(stamp(9 * NS), stamp(3 * NS))))
    assert reading(whole_negative)["classification"] == "inconsistent"
    assert status(whole_negative, "freshness") == "unresolved"


# --- B. configuration activation and observation provenance --------------------------------


def aba(dispatch_activation_field=None, request_activation=0):
    """A → B → A between request and dispatch; content hash equal at dispatch."""
    events = chain(stamp(0), stamp(5 * NS), activation=request_activation)
    changes = [
        {
            "kind": "configuration_changed",
            "from_sha256": CONFIG,
            "to_sha256": OTHER,
            "activation": 1,
            "at": stamp(2 * NS),
        },
        {
            "kind": "configuration_changed",
            "from_sha256": OTHER,
            "to_sha256": CONFIG,
            "activation": 2,
            "at": stamp(3 * NS),
        },
    ]
    events = events[:3] + changes + events[3:]
    if dispatch_activation_field is not None:
        events[-2]["activation"] = dispatch_activation_field
    return trace(events)


def test_returned_content_hash_does_not_restore_the_activation_context():
    assessment = temporal.assess(aba())
    assert status(assessment, "configuration_binding") == "violated"
    detail = assessment["predicates"]["configuration_binding"]["findings"][0]["detail"]
    assert "activation 0" in detail and "activation 2" in detail and "returned" in detail
    assert assessment["final_state"]["activation"] == 2
    assert [t["activation"] for t in assessment["evidence"]["activation_transitions"]] == [1, 2]


def test_asserted_activation_contradicting_recorded_transitions_is_a_distinct_finding():
    assessment = temporal.assess(aba(dispatch_activation_field=0))
    contradictions = assessment["evidence"]["activation_contradictions"]
    assert contradictions == [{"seq": 7, "kind": "action_dispatched", "asserted": 0, "derived": 2}]
    findings = assessment["predicates"]["configuration_binding"]["findings"]
    assert any(
        "contradicts the recorded configuration transitions" in f["detail"] for f in findings
    )
    assert status(assessment, "configuration_binding") == "violated"  # the ABA violation stands


def test_without_recorded_transitions_content_equality_is_the_whole_context():
    assessment = temporal.assess(trace(chain(stamp(0), stamp(5 * NS))))
    assert status(assessment, "configuration_binding") == "satisfied"
    assert assessment["evidence"]["activation_transitions"] == []


def test_unbound_response_after_a_transition_leaves_activation_unresolved_not_zero():
    events = chain(stamp(0), stamp(5 * NS))
    events[3]["req_id"] = None
    events.insert(
        3,
        {
            "kind": "configuration_changed",
            "from_sha256": CONFIG,
            "to_sha256": CONFIG,
            "at": stamp(2 * NS),
        },
    )
    assessment = temporal.assess(trace(events))
    assert status(assessment, "configuration_binding") == "unresolved"
    detail = assessment["predicates"]["configuration_binding"]["findings"][0]["detail"]
    assert "cannot be established" in detail


def test_retained_x03_and_r11_traces_read_the_activation_rule_and_the_null_reduction():
    x03 = json.loads(
        (
            PRODUCER
            / "boundary-execution-001/traces/X03-configuration-aba--unfenced_queue_control.json"
        ).read_text()
    )
    assessment = temporal.assess(x03)
    assert status(assessment, "configuration_binding") == "violated"
    violated = [
        f
        for f in assessment["predicates"]["configuration_binding"]["findings"]
        if f["status"] == "violated"
    ]
    assert [f["seq"] for f in violated] == [7]  # c0:0 only; c1:0 belongs to activation 2
    r11 = PRODUCER / "aba-reduction-execution-001/traces"
    unfenced = temporal.assess(
        json.loads(
            (r11 / "R11-reuse-original-observation--unfenced_queue_control.json").read_text()
        )
    )
    conventional = temporal.assess(
        json.loads((r11 / "R11-reuse-original-observation--conventional.json").read_text())
    )
    # The failure is preserved in the unfenced record and the frozen rule does not fence
    # the current request q1; the observation's earlier activation is reported separately.
    assert status(unfenced, "configuration_binding") == "violated"
    assert unfenced["retrospective"]["observation_context"]["status"] == "violated"
    assert unfenced["retrospective"]["observation_context"]["findings"][0]["detail"].startswith(
        "action c1:0"
    )
    # The conventional remedy fenced q1 too (stricter than the frozen rule) and dispatched
    # nothing, so R11 is not a smaller witness of useful conventional behaviour.
    assert conventional["assigned_usefulness"]["status"] == "violated"
    assert conventional["assigned_usefulness"]["opportunities_dispatched"] == 0
    assert [
        s["chunk_id"] for s in conventional["retrospective"]["admissions_stricter_than_frozen_rule"]
    ] == ["c1"]


# --- C. acknowledgement belongs to a send attempt -------------------------------------------


def two_attempts(first_outcome: list[dict], second_outcome: list[dict]):
    events = chain(stamp(0), stamp(3 * NS))
    dispatch = events[5]
    events = events[:6] + first_outcome
    second = {
        **dispatch,
        "dispatch_id": "d1",
        "input_id": "in-dispatch-2",
        "step": 1,
        "at": stamp(5 * NS),
    }
    events += [
        {"kind": "queue_admitted", "chunk_id": "c0", "admitted": [0], "at": stamp(4 * NS)},
        second,
        *second_outcome,
    ]
    return trace(events)


def test_a_later_acknowledgement_cannot_attest_the_first_attempt():
    assessment = temporal.assess(
        two_attempts(
            [],
            [
                {
                    "kind": "dispatch_acknowledged",
                    "action_id": "c0:0",
                    "dispatch_id": "d1",
                    "at": stamp(5 * NS),
                }
            ],
        )
    )
    assert status(assessment, "acknowledgement") == "unresolved"
    assert status(assessment, "duplicate_dispatch") == "violated"
    outcomes = {a["attempt"]: a["outcome"] for a in assessment["evidence"]["attempts"]}
    assert outcomes == {"d0": "unacknowledged", "d1": "acknowledged"}
    assert assessment["evidence"]["unacknowledged_attempts"] == ["d0"]
    assert assessment["evidence"]["unacknowledged_dispatches"] == ["c0:0"]


def test_an_acknowledgement_binds_by_dispatch_id_whatever_its_position():
    late_first = [
        {
            "kind": "dispatch_acknowledged",
            "action_id": "c0:0",
            "dispatch_id": "d0",
            "at": stamp(6 * NS),
        }
    ]
    assessment = temporal.assess(two_attempts([], late_first))
    outcomes = {a["attempt"]: a["outcome"] for a in assessment["evidence"]["attempts"]}
    assert outcomes == {"d0": "acknowledged", "d1": "unacknowledged"}


def test_conflicting_unmatched_and_ambiguous_legacy_outcomes_are_explicit():
    conflicting = temporal.assess(
        two_attempts(
            [
                {
                    "kind": "dispatch_acknowledged",
                    "action_id": "c0:0",
                    "dispatch_id": "d0",
                    "at": stamp(3 * NS),
                },
                {
                    "kind": "dispatch_failed",
                    "action_id": "c0:0",
                    "dispatch_id": "d0",
                    "reason": "late error",
                    "at": stamp(3 * NS),
                },
            ],
            [
                {
                    "kind": "dispatch_acknowledged",
                    "action_id": "c0:0",
                    "dispatch_id": "d1",
                    "at": stamp(5 * NS),
                }
            ],
        )
    )
    assert {a["attempt"]: a["outcome"] for a in conflicting["evidence"]["attempts"]}[
        "d0"
    ] == "conflicting"
    assert status(conflicting, "acknowledgement") == "violated"  # the failure record stands
    unmatched = temporal.assess(
        two_attempts(
            [],
            [
                {
                    "kind": "dispatch_acknowledged",
                    "action_id": "c0:0",
                    "dispatch_id": "d9",
                    "at": stamp(5 * NS),
                }
            ],
        )
    )
    assert unmatched["evidence"]["unmatched_outcomes"][0]["dispatch_id"] == "d9"
    assert status(unmatched, "acknowledgement") == "unresolved"
    legacy = two_attempts(
        [], [{"kind": "dispatch_acknowledged", "action_id": "c0:0", "at": stamp(5 * NS)}]
    )
    for event in legacy["events"]:
        event.pop("dispatch_id", None)
    ambiguous = temporal.assess(legacy)
    assert {a["outcome"] for a in ambiguous["evidence"]["attempts"]} == {"ambiguous_legacy"}
    assert status(ambiguous, "acknowledgement") == "unresolved"


def test_legacy_in_order_acknowledgements_stay_attributable():
    legacy = two_attempts(
        [{"kind": "dispatch_acknowledged", "action_id": "c0:0", "at": stamp(3 * NS)}],
        [{"kind": "dispatch_acknowledged", "action_id": "c0:0", "at": stamp(5 * NS)}],
    )
    for event in legacy["events"]:
        event.pop("dispatch_id", None)
    assessment = temporal.assess(legacy)
    assert {a["outcome"] for a in assessment["evidence"]["attempts"]} == {"acknowledged"}
    assert status(assessment, "acknowledgement") == "satisfied"


def test_retained_x04_trace_preserves_the_first_unacknowledged_attempt():
    record = json.loads(
        (
            PRODUCER
            / "boundary-execution-001/traces/X04-duplicate-with-lost-first-ack--unfenced_queue_control.json"
        ).read_text()
    )
    assessment = temporal.assess(record)
    assert status(assessment, "acknowledgement") == "unresolved"
    assert assessment["evidence"]["unacknowledged_attempts"] == [
        "X04-duplicate-with-lost-first-ack-input-03:send"
    ]
    assert assessment["assigned_usefulness"]["opportunities_acknowledged"] == 1
    assert assessment["assigned_usefulness"]["opportunities_dispatched"] == 2


# --- A. the producer's frozen usefulness contract -------------------------------------------


def with_contract(events, opportunities, minimum=1, **overrides):
    return trace(
        events,
        minimum_dispatches=minimum,
        usefulness_contract={
            "basis": "frozen_case_dispatch_target",
            "minimum_dispatches": minimum,
            "scope": "whole_case",
            "dispatch_opportunities": opportunities,
        },
        **overrides,
    )


def test_assigned_contract_counts_frozen_opportunities_not_grid_ticks():
    events = chain(stamp(0), stamp(20 * NS))
    events[3]["at"] = events[4]["at"] = stamp(10 * NS)
    record = with_contract(events, [{"input_id": "in-dispatch", "at": stamp(20 * NS)}])
    assessment = temporal.assess(record)
    # Legacy: ticks 10 and 20 ms, one dispatch, coverage 0.5, violated under 0.8.
    assert status(assessment, "useful_execution") == "violated"
    assert assessment["useful_execution"]["coverage_by_generation"]["0"]["coverage"] == 0.5
    # Assigned: one frozen opportunity, dispatched, minimum 1.
    usefulness = assessment["assigned_usefulness"]
    assert usefulness["status"] == "satisfied" and usefulness["membership"] == "valid"
    assert usefulness["opportunities_dispatched"] == 1 and usefulness["opportunities_valid"] == 1
    assert usefulness["valid_acknowledged_status"] == "satisfied"
    assert assessment["assigned_contract"] == "satisfied"
    assert assessment["temporal_contract"] == "violated"


def test_membership_problems_cannot_disappear():
    events = chain(stamp(0), stamp(3 * NS))
    listed = [{"input_id": "in-dispatch", "at": stamp(3 * NS)}]
    omitted = temporal.assess(
        with_contract(events, listed + [{"input_id": "in-missing", "at": stamp(9 * NS)}])
    )
    assert omitted["assigned_usefulness"]["opportunities_unobserved"] == ["in-missing"]
    assert omitted["assigned_usefulness"]["status"] == "unresolved"
    assert "observed prefix" in omitted["assigned_usefulness"]["detail"]
    duplicated = temporal.assess(with_contract(events, listed + listed))
    assert duplicated["assigned_usefulness"]["membership"] == "invalid"
    unlisted = temporal.assess(
        with_contract(events, [{"input_id": "in-other", "at": stamp(3 * NS)}])
    )
    assert unlisted["assigned_usefulness"]["membership"] == "invalid"
    assert any(
        "not a listed opportunity" in p
        for p in unlisted["assigned_usefulness"]["membership_problems"]
    )
    moved = temporal.assess(
        with_contract(events, [{"input_id": "in-dispatch", "at": stamp(4 * NS)}])
    )
    assert moved["assigned_usefulness"]["membership"] == "invalid"
    absent = temporal.assess(trace(events))
    assert absent["assigned_usefulness"]["membership"] == "absent"
    assert absent["assigned_contract"] is None


def test_duplicate_attempts_at_one_opportunity_count_once_and_validity_is_separate():
    events = chain(stamp(0), stamp(3 * NS))
    second = {**events[5], "dispatch_id": "d1", "step": 1}
    events = events[:6] + [
        {"kind": "queue_admitted", "chunk_id": "c0", "admitted": [0], "at": stamp(3 * NS)},
        second,
    ]
    record = with_contract(events, [{"input_id": "in-dispatch", "at": stamp(3 * NS)}], minimum=2)
    usefulness = temporal.assess(record)["assigned_usefulness"]
    assert usefulness["raw_dispatch_attempts"] == 2
    assert usefulness["opportunities_dispatched"] == 1
    assert usefulness["status"] == "violated"


def test_refused_opportunities_and_stale_dispatches_are_reported_separately():
    events = chain(stamp(0), stamp(60 * NS))  # stale: 60 ms > 50 ms
    events += [
        {
            "kind": "dispatch_refused",
            "reason": "empty_queue",
            "input_id": "in-refused",
            "at": stamp(70 * NS),
        }
    ]
    record = with_contract(
        events,
        [
            {"input_id": "in-dispatch", "at": stamp(60 * NS)},
            {"input_id": "in-refused", "at": stamp(70 * NS)},
        ],
    )
    usefulness = temporal.assess(record)["assigned_usefulness"]
    assert usefulness["status"] == "satisfied"  # raw contract: one attempt of minimum one
    assert usefulness["opportunities_refused"] == 1
    assert usefulness["opportunities_valid"] == 0 and usefulness["opportunities_acknowledged"] == 1
    assert usefulness["valid_acknowledged_status"] == "violated"


def test_the_prefix_trace_reads_the_contract_as_unresolved_never_retrying():
    recovery = json.loads((PRODUCER / "recovery-001.json").read_text())
    prefix = next(a for a in recovery["assignments"] if a["stage"] == "after_dispatch_before_ack")
    assessment = temporal.assess(prefix["inspection"]["record"]["trace"])
    assert assessment["software_execution"] == "unknown"
    assert status(assessment, "acknowledgement") == "unresolved"
    usefulness = assessment["assigned_usefulness"]
    assert usefulness["opportunities_dispatched"] == 1 and usefulness["status"] == "satisfied"
    assert usefulness["opportunities_acknowledged"] == 0
    assert usefulness["valid_acknowledged_status"] == "violated"


# --- F. monotonicity is not chunk-target alignment ------------------------------------------


def test_alignment_is_a_separate_retrospective_reading():
    events = chain(stamp(0), stamp(3 * NS))
    events[5]["step"] = 1  # dispatched at step 1, targeted first_step 0 + ordinal 0
    assessment = temporal.assess(trace(events))
    assert status(assessment, "dispatch_order") == "satisfied"
    alignment = assessment["retrospective"]["chunk_target_alignment"]
    assert alignment["status"] == "violated"
    assert alignment["findings"][0]["witness"] == {
        "dispatched_step": 1,
        "target_step": 0,
        "generation": 0,
    }
    assert "chunk_target_alignment" not in assessment["predicates"]


def test_alignment_stays_unresolved_when_the_target_is_not_established():
    events = chain(stamp(0), stamp(3 * NS))
    events[3]["req_id"] = None
    unbound = temporal.assess(trace(events))
    assert unbound["retrospective"]["chunk_target_alignment"]["status"] == "unresolved"
    events = chain(stamp(0), stamp(3 * NS))
    events[5]["target_step"] = 4  # the producer's own target disagrees with first_step + ordinal
    disagreeing = temporal.assess(trace(events))
    assert disagreeing["retrospective"]["chunk_target_alignment"]["status"] == "unresolved"
    events = chain(stamp(0), stamp(3 * NS))
    events[3]["first_step"] = 2  # differs from the bound observation's step 0
    events[5]["step"] = 2
    misdeclared = temporal.assess(trace(events))
    assert misdeclared["retrospective"]["chunk_target_alignment"]["status"] == "unresolved"


def test_retained_alignment_mismatches_are_exactly_the_sixteen_read_by_the_producer():
    readback = json.loads((PRODUCER / "alignment-readback-001.json").read_text())
    expected = {r["assignment"]["id"] for r in readback["assignments"] if r["alignment_mismatches"]}
    assert len(expected) == 16
    observed, unresolved = set(), set()
    for directory in (
        "execution-001/traces",
        "boundary-execution-001/traces",
        "precision-execution-001/traces",
        "aba-reduction-execution-001/traces",
    ):
        for path in sorted((PRODUCER / directory).glob("*.json")):
            record = json.loads(path.read_text())
            assessment = temporal.assess(record)
            alignment = assessment["retrospective"]["chunk_target_alignment"]["status"]
            if alignment == "violated":
                observed.add(record["assignment"]["id"])
            elif alignment == "unresolved":
                unresolved.add(record["assignment"]["id"])
            assert status(assessment, "dispatch_order") == "satisfied", path.name
    # The producer's readback compares indices only. R08 deletes request q1, so its chunk
    # c1 names an unrecorded request: the index differs, but the target is not established
    # under the declared premise, and the reading is unresolved rather than violated.
    assert observed == expected - {"R08-delete-request--unfenced_queue_control"}
    assert "R08-delete-request--unfenced_queue_control" in unresolved
    assert not any("conventional" in a or "selected" in a for a in observed | unresolved)


# --- bounded interaction check ----------------------------------------------------------------


def test_the_six_corrections_report_independently_on_one_trace():
    """ABA transition, two attempts of one action, a crossing-zero mapping and a frozen
    opportunity contract at a 2^60 epoch: each reading is present and none masks another."""
    epoch = 2**60
    mapping = {
        "from": "sensor",
        "to": "controller",
        "offset": 0,
        "uncertainty": 10 * NS,
        "unit": "ns",
    }
    events = chain(
        stamp(epoch, "sensor"), stamp(epoch + 5 * NS), held_at=stamp(epoch), activation=0
    )
    for event in events[:3]:
        if event["kind"] != "observation_acquired":
            event["at"] = stamp(epoch + event["at"]["value"])
    events[3]["at"] = events[4]["at"] = stamp(epoch + 4 * NS)
    changes = [
        {
            "kind": "configuration_changed",
            "from_sha256": CONFIG,
            "to_sha256": OTHER,
            "at": stamp(epoch + 2 * NS),
        },
        {
            "kind": "configuration_changed",
            "from_sha256": OTHER,
            "to_sha256": CONFIG,
            "at": stamp(epoch + 3 * NS),
        },
    ]
    events = events[:3] + changes + events[3:6]
    second = {
        **events[-1],
        "dispatch_id": "d1",
        "input_id": "in-second",
        "step": 1,
        "at": stamp(epoch + 9 * NS),
    }
    events += [
        {"kind": "queue_admitted", "chunk_id": "c0", "admitted": [0], "at": stamp(epoch + 8 * NS)},
        second,
        {
            "kind": "dispatch_acknowledged",
            "action_id": "c0:0",
            "dispatch_id": "d1",
            "at": stamp(epoch + 9 * NS),
        },
    ]
    record = with_contract(
        events,
        [
            {"input_id": "in-dispatch", "at": stamp(epoch + 5 * NS)},
            {"input_id": "in-second", "at": stamp(epoch + 9 * NS)},
        ],
        clocks={"names": ["controller", "sensor"], "declared_mappings": [mapping]},
    )
    assessment = temporal.assess(record)
    assert status(assessment, "configuration_binding") == "violated"  # B, both attempts
    assert status(assessment, "duplicate_dispatch") == "violated"
    assert status(assessment, "acknowledgement") == "unresolved"  # C: d0 unacknowledged
    assert status(assessment, "freshness") == "satisfied"  # D: chain bound 5 and 9 ms
    assert [r["interval_used"] for r in assessment["age_readings"]] == [
        [5 * NS, 15 * NS],
        [9 * NS, 19 * NS],
    ]
    assert assessment["age_readings"][0]["mapped_interval"] == [
        -5 * NS,
        15 * NS,
    ]  # E: exact at 2^60
    usefulness = assessment["assigned_usefulness"]  # A
    assert usefulness["opportunities_dispatched"] == 2 and usefulness["opportunities_valid"] == 0
    assert usefulness["opportunities_acknowledged"] == 1
    assert assessment["retrospective"]["chunk_target_alignment"]["status"] == "violated"  # F
    assert status(assessment, "dispatch_order") == "satisfied"


def test_a_response_contradicting_its_request_is_not_a_valid_dispatch():
    events = chain(stamp(0), stamp(3 * NS))
    events[3]["config_sha256"] = OTHER  # asserted by the response; the request was under CONFIG
    assessment = temporal.assess(
        with_contract(events, [{"input_id": "in-dispatch", "at": stamp(3 * NS)}])
    )
    assert status(assessment, "request_binding") == "violated"
    usefulness = assessment["assigned_usefulness"]
    assert usefulness["opportunities_dispatched"] == 1 and usefulness["opportunities_valid"] == 0
    assert usefulness["valid_acknowledged_status"] == "violated"
    assert assessment["evidence"]["attempts"][0]["validity"]["bound"] is False
