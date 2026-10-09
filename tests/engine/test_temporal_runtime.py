"""Constructed message controls: no simulation, hidden answers or learned calls."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nisayon.engine.temporal_clocks import age_at
from nisayon.engine.temporal_experiment import validate_suite
from nisayon.engine.temporal_runtime import TemporalRuntime, stamp

SUITE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/experiments/results/temporal-integration-001/frozen-suite.v2.json"
    ).read_bytes()
)


def execute(case_id, remedy_id="conventional", *, mutate=None):
    case = copy.deepcopy(next(c for c in SUITE["cases"] if c["id"].startswith(case_id + "-")))
    if mutate:
        mutate(case)
    remedy = next(r for r in SUITE["remedies"] if r["id"] == remedy_id)
    events = []
    runtime = TemporalRuntime(case, remedy, events.append)
    runtime.start()
    for operation in case["schedule"]:
        runtime.execute(operation)
    return events, runtime


def dispatched(events):
    return [e for e in events if e["kind"] == "action_dispatched"]


def test_frozen_assignments_have_all_six_remedies_and_validate():
    validate_suite(SUITE)
    assert len(SUITE["assignments"]) == 120
    missing = copy.deepcopy(SUITE)
    missing["assignments"].pop()
    with pytest.raises(ValueError, match="Every case/remedy"):
        validate_suite(missing)


@pytest.mark.parametrize(
    "case_id,values",
    [
        ("T01", [1]),
        ("T02", [10]),
        ("T03", [10]),
        ("T04", [10]),
        ("T05", [1]),
        ("T06", [1]),
        ("T07", [1, 10, 11]),
        ("T08", [10]),
        ("T09", []),
        ("T10", []),
        ("T11", []),
        ("T12", []),
        ("T13", []),
        ("T14", [1]),
        ("T15", [10]),
        ("T16", [1]),
        ("T17", [1]),
        ("T18", []),
        ("T19", [1]),
        ("T20", []),
    ],
)
def test_conventional_controls_and_selected_interface_parity(case_id, values):
    ordinary, runtime = execute(case_id)
    selected, _ = execute(case_id, "selected_intervention")
    assert [e["value"] for e in dispatched(ordinary)] == values
    assert ordinary == selected
    opportunities = [e for e in ordinary if e["kind"] in {"action_dispatched", "dispatch_refused"}]
    assert len(opportunities) == runtime.counts["control_opportunities"]


def test_queue_reset_cannot_replace_inflight_generation_fence():
    incomplete, _ = execute("T03", "reset_only")
    fenced, _ = execute("T03")
    assert [e["value"] for e in dispatched(incomplete)] == [1]
    assert [e["value"] for e in dispatched(fenced)] == [10]
    refusal = next(e for e in fenced if e["kind"] == "queue_admitted" and e["chunk_id"] == "c0")
    assert refusal["skipped"] == [0]
    assert refusal["reason"] == "generation_fence"


def test_duplicate_delivery_and_reordered_overlap_have_distinct_identity():
    duplicate, _ = execute("T06", "unfenced_queue_control")
    attempts = dispatched(duplicate)
    assert [e["action_id"] for e in attempts] == ["c0:0", "c0:0"]
    assert attempts[0]["dispatch_id"] != attempts[1]["dispatch_id"]
    overlap, _ = execute("T07")
    admission = next(e for e in overlap if e["kind"] == "queue_admitted" and e["chunk_id"] == "c1")
    assert admission["replaced"] == ["c0:1", "c0:2"]
    assert "c0:0" not in admission["replaced"]


def test_arrival_check_admits_an_action_that_expires_in_queue():
    arrival, _ = execute("T15", "arrival_deadline_only")
    conventional, _ = execute("T15")
    assert dispatched(arrival)[0]["value"] == 1
    assert dispatched(arrival)[0]["at"]["value"] == 51_000_000
    assert [e["value"] for e in dispatched(conventional)] == [10]
    refusal = next(e for e in conventional if e["kind"] == "dispatch_refused")
    assert refusal["age_guard"]["lower_ns"] == 51_000_000


def test_stop_all_preserves_opportunities_but_has_no_useful_dispatches():
    events, runtime = execute("T07", "drop_all")
    assert not dispatched(events)
    assert runtime.counts["control_opportunities"] == 3
    assert len([e for e in events if e["kind"] == "dispatch_refused"]) == 3


def test_missing_ack_and_failed_send_remain_different():
    unacknowledged, _ = execute("T16")
    failed, _ = execute("T17")
    assert len(dispatched(unacknowledged)) == len(dispatched(failed)) == 1
    assert not any(e["kind"] == "dispatch_acknowledged" for e in unacknowledged + failed)
    assert any(e["kind"] == "evidence_gap" for e in unacknowledged)
    assert any(e["kind"] == "dispatch_failed" for e in failed)
    assert not any(e["kind"] == "dispatch_failed" for e in unacknowledged)


def test_acquisition_null_is_not_replaced_with_driver_time():
    events, _ = execute("T11")
    observation = next(e for e in events if e["kind"] == "observation_acquired")
    assert observation["at"] is None
    assert observation["observed_by_driver_at"] == stamp(0)
    refusal = next(e for e in events if e["kind"] == "dispatch_refused")
    assert refusal["age_guard"]["status"] == "unresolved"


def test_clock_relation_direction_equality_and_unsupported_information():
    clocks = {
        "names": ["sensor", "controller"],
        "declared_mappings": [
            {"from": "sensor", "to": "controller", "offset": 100, "uncertainty": 0, "unit": "ns"},
        ],
    }
    sensor = {"value": 5, "clock": "sensor", "unit": "ns"}
    assert age_at(sensor, stamp(155), clocks, 50).record() == {
        "status": "within",
        "lower_ns": 50,
        "upper_ns": 50,
        "reason": "age_within_inclusive_deadline",
    }
    reverse = {
        "names": clocks["names"],
        "declared_mappings": [
            {"from": "controller", "to": "sensor", "offset": -100, "uncertainty": 0, "unit": "ns"},
        ],
    }
    assert age_at(sensor, stamp(155), clocks, 50) == age_at(sensor, stamp(155), reverse, 50)
    clocks["declared_mappings"][0]["uncertainty"] = 10
    assert age_at(sensor, stamp(155), clocks, 50).status == "unresolved"
    assert age_at(sensor, stamp(94), clocks, 50).status == "inconsistent"
    clocks["declared_mappings"][0]["rate"] = 1.1
    assert age_at(sensor, stamp(155), clocks, 50).status == "unresolved"


def test_configuration_activation_fences_aba_even_when_content_hash_returns():
    # Exploratory regression beyond the frozen schedule, declared as such.
    def aba(case):
        schedule = case["schedule"]
        original = case["initial_configuration"]
        schedule.insert(
            3,
            {
                "id": "exploratory-aba",
                "at_ns": 2_000_000,
                "operation": "configure",
                "config_sha256": original,
            },
        )
        for row in schedule:
            if row["operation"] == "response" and row["req_id"] == "q1":
                row["config_sha256"] = original

    events, _ = execute("T08", mutate=aba)
    old = next(e for e in events if e["kind"] == "queue_admitted" and e["chunk_id"] == "c0")
    assert old["reason"] == "configuration_fence"
    assert [e["value"] for e in dispatched(events)] == [10]


@pytest.mark.parametrize("epoch", [0, 2**54, 2**60])
@pytest.mark.parametrize(
    "delta,status", [(49_999_999, "within"), (50_000_000, "within"), (50_000_001, "overdue")]
)
def test_exact_nanosecond_deadline_is_invariant_to_epoch(epoch, delta, status):
    result = age_at(stamp(epoch), stamp(epoch + delta), {"names": ["controller"]}, 50_000_000)
    assert result.status == status
    assert result.lower_ns == result.upper_ns == delta
