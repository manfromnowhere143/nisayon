"""The temporal reference model: clocks, predicates, frozen cases and malformed traces."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from nisayon.evaluation import temporal

REPO = Path(__file__).resolve().parents[2]
STUDY = REPO / "docs/evaluation/results/temporal-integration-001"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, STUDY / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cases = load("cases")


def stamp(value, clock="controller"):
    return {"value": value, "clock": clock, "unit": "tick"}


def test_ages_are_exact_within_a_clock_and_intervals_across_a_declared_mapping():
    assert temporal.age_interval(stamp(5), stamp(2), []) == (3, 3)
    assert temporal.age_interval(stamp(5), stamp(2, "server"), []) is None
    mapping = [
        {"from": "server", "to": "controller", "offset": 100, "uncertainty": 0.5, "unit": "tick"}
    ]
    assert temporal.age_interval(stamp(3), stamp(-100, "server"), mapping) == (2.5, 3.5)
    assert (
        temporal.age_interval(stamp(3), stamp(-100, "server"), [{**mapping[0], "unit": "ms"}])
        is None
    )
    assert temporal.age_interval(stamp(3), None, mapping) is None
    assert (
        temporal.age_interval({"value": 3, "clock": "controller", "unit": "ms"}, stamp(1), [])
        is None
    )


def test_boundary_rule_and_classification():
    assert temporal.classify_age((4, 4), 4) == "within"
    assert temporal.classify_age((4.0, 4.5), 4) == "overlapping"
    assert temporal.classify_age((4.1, 4.5), 4) == "beyond"
    assert temporal.classify_age(None, 4) == "unknown"
    assert temporal.classify_age((1, 2), None) == "unknown"


@pytest.mark.parametrize("build", cases.CASES, ids=lambda b: b.__name__)
def test_frozen_cases_match_their_written_expectations_except_the_retained_disagreement(build):
    trace = build()
    assessment = temporal.assess(trace)
    expected = {p: "satisfied" for p in temporal.PREDICATES}
    expected.update(cases.EXPECTED[trace["case_id"]])
    observed = {p: assessment["predicates"][p]["status"] for p in temporal.PREDICATES}
    if trace["case_id"] == "early_reset_upstream_fix":
        # Retained: the fix clears the queue at the next control-loop entry, after
        # reset_completed, so the frozen reset-time predicate is violated while no stale
        # action is dispatched. The exploratory reading records the empty survivor set.
        expected["queue_reset"] = "violated"
        reading = assessment["exploratory_after_freeze"]["queue_reset_before_first_dispatch"]
        assert reading["1"]["survivors_at_reset"] == ["c0:2"]
        assert reading["1"]["still_queued_at_first_dispatch"] == []
    assert observed == expected
    assert assessment["robot_task_outcome"] == "unmeasured"


def test_affected_reset_case_dispatches_the_survivor_and_the_exploratory_reading_shows_it():
    assessment = temporal.assess(cases.early_reset_affected())
    assert assessment["temporal_contract"] == "violated"
    reading = assessment["exploratory_after_freeze"]["queue_reset_before_first_dispatch"]["1"]
    assert reading["still_queued_at_first_dispatch"] == ["c0:2"]


def test_two_history_witnesses_are_retained_for_missing_evidence():
    assessment = temporal.assess(cases.incomplete_raw_evidence())
    fencing = assessment["predicates"]["generation_fencing"]["findings"]
    assert any(f.get("witness", {}).get("smallest_observation") for f in fencing)
    assert assessment["evidence"]["completeness"] == "incomplete"
    assert "c0" in assessment["evidence"]["unbound_responses"]


def test_malformed_traces_are_invalid_not_satisfied():
    assert temporal.assess({"schema": "other"})["temporal_contract"] == "invalid"
    trace = cases.healthy()
    trace["events"][3] = {"seq": 4, "kind": "response_arrived"}  # required fields missing
    assessment = temporal.assess(trace)
    assert assessment["temporal_contract"] == "invalid"
    assert any("lacks" in p for p in assessment["evidence"]["problems"])
    trace = cases.healthy()
    trace["events"][2]["seq"] = 1  # not increasing
    assert temporal.assess(trace)["temporal_contract"] == "invalid"


def test_same_tick_replacement_prevents_a_stale_dispatch():
    enumerate_orders = load("enumerate_orders")
    replaced = temporal.assess(enumerate_orders.build_trace("affected", 3, 1, 3))
    dispatched = temporal.assess(enumerate_orders.build_trace("affected", 3, 1, 4))
    assert replaced["predicates"]["generation_fencing"]["status"] == "satisfied"
    assert dispatched["predicates"]["generation_fencing"]["status"] == "violated"
    assert enumerate_orders.oracle_v2("affected", 3, 1, 3) == "satisfied"
    assert enumerate_orders.oracle_v1("affected", 3, 1) == "violated"


def test_assessment_is_json_serializable_and_reports_costs_separately():
    assessment = temporal.assess(cases.healthy())
    json.dumps(assessment, allow_nan=False)
    assert assessment["useful_execution"]["coverage_by_generation"]["0"]["coverage"] == 1.0
    assert "robot_task_outcome" in assessment and assessment["software_execution"] == "completed"


def test_public_temporal_command_assesses_the_execution_lane_example(tmp_path):
    import subprocess
    import sys

    example = REPO / "docs/experiments/results/temporal-integration-001/interface-example.json"
    if not example.is_file():
        pytest.skip("the execution lane's interface example is not in this tree")
    out = tmp_path / "assessment.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "temporal",
            str(example),
            "--json",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert completed.returncode == 0, completed.stderr
    assessment = json.loads(out.read_text())
    assert assessment["schema"] == temporal.ASSESSMENT_SCHEMA
    assert assessment["controller_clock"] == "virtual_controller"
    assert assessment["temporal_contract"] == "satisfied"
    assert assessment["software_execution"] == "not_executed"
    assert assessment["useful_execution"]["coverage_by_generation"]["0"]["coverage"] == 1.0


def test_coverage_window_follows_the_generation_tick_grid():
    trace = cases.healthy()
    # Shift every arrival half a tick later: dispatches stay on the grid, coverage is unchanged.
    for event in trace["events"]:
        if event["kind"] == "response_arrived":
            event["at"]["value"] += 0.5
    assessment = temporal.assess(trace)
    assert assessment["useful_execution"]["coverage_by_generation"]["0"]["coverage"] == 1.0


def test_dispatch_refused_is_neither_a_dispatch_nor_a_failure():
    trace = cases.late_response_fenced()
    trace["events"].append(
        {"seq": 99, "kind": "dispatch_refused", "reason": "obsolete generation", "at": stamp(3)}
    )
    assessment = temporal.assess(trace)
    assert assessment["dispatch_refusals"] == 1
    assert assessment["evidence"]["problems"] == []
    assert assessment["predicates"]["acknowledgement"]["status"] == "satisfied"
    assert assessment["predicates"]["generation_fencing"]["status"] == "satisfied"


def test_duplicate_delivery_identity_is_reported():
    trace = cases.duplicate_response()
    for event in trace["events"]:
        if event["kind"] == "response_arrived" and event["resp_id"] == "p0-dup":
            event["delivery_id"] = "d2"
    assessment = temporal.assess(trace)
    assert assessment["repeated_deliveries"] == [{"seq": 8, "chunk_id": "c0", "delivery_id": "d2"}]
    assert assessment["predicates"]["duplicate_dispatch"]["status"] == "violated"


def test_a_repeated_delivery_that_is_not_readmitted_after_dispatch_is_not_a_violation():
    trace = cases.duplicate_response()
    # Drop the second admission and the double dispatch: the duplicate is merely recorded.
    trace["events"] = [
        e for e in trace["events"] if not (e["kind"] == "queue_admitted" and e["seq"] == 9)
    ]
    trace["events"] = [
        e for e in trace["events"] if not (e["kind"] == "action_dispatched" and e["seq"] == 10)
    ]
    trace["events"] = [
        e for e in trace["events"] if not (e["kind"] == "dispatch_acknowledged" and e["seq"] == 11)
    ]
    assessment = temporal.assess(trace)
    assert assessment["predicates"]["duplicate_dispatch"]["status"] == "satisfied"
    assert len(assessment["repeated_deliveries"]) == 1


def test_negative_age_is_inconsistent_and_unresolved():
    assert temporal.classify_age((-3, -1), 4) == "inconsistent"
    # Version 1 read (-1, 1) as within; version 2 leaves chronology unresolved until
    # same-clock chain evidence bounds the age (tests in test_evaluation_temporal_v2.py).
    assert temporal.classify_age((-1, 1), 4) == "chronology_unresolved"
    trace = cases.healthy()
    trace["clocks"] = {
        "names": ["controller", "sensor"],
        "declared_mappings": [
            {"from": "sensor", "to": "controller", "offset": 0, "uncertainty": 0, "unit": "tick"}
        ],
    }
    trace["events"][1]["at"] = {"value": 100, "clock": "sensor", "unit": "tick"}
    assessment = temporal.assess(trace)
    assert assessment["predicates"]["freshness"]["status"] == "unresolved"
    assert any(
        "inconsistent age" in f["detail"] for f in assessment["predicates"]["freshness"]["findings"]
    )
    assert assessment["age_readings"][0]["classification"] == "inconsistent"


def test_response_assertions_must_agree_with_the_bound_request():
    trace = cases.healthy()
    for event in trace["events"]:
        if event["kind"] == "response_arrived" and event["chunk_id"] == "c0":
            event["config_sha256"] = cases.CONFIG_B
            event["generation"] = 7
    assessment = temporal.assess(trace)
    findings = assessment["predicates"]["request_binding"]["findings"]
    assert assessment["predicates"]["request_binding"]["status"] == "violated"
    assert any("asserts configuration" in f["detail"] for f in findings)
    assert any("claims generation 7" in f["detail"] for f in findings)


def test_stale_overwrite_is_an_exploratory_reading_not_a_verdict():
    assessment = temporal.assess(cases.out_of_order_arrival())
    assert assessment["temporal_contract"] == "satisfied"
    overwrites = assessment["exploratory_stale_overwrites"]
    assert {o["replaced"] for o in overwrites} == {"c1:1", "c1:2"}
    assert all(o["by_chunk"] == "c0" for o in overwrites)


def test_coverage_uses_recorded_opportunities_when_the_producer_records_refusals():
    trace = cases.late_response_fenced()
    # Two refusals at the fenced arrival tick and dense dispatch afterwards.
    trace["events"].append(
        {"seq": 90, "kind": "dispatch_refused", "reason": "fenced", "at": stamp(3)}
    )
    assessment = temporal.assess(trace)
    window = assessment["useful_execution"]["coverage_by_generation"]["1"]
    assert window["basis"] == "opportunities"
    assert window["ticks"] == window["dispatched"] + 1
    grid = temporal.assess(cases.healthy())["useful_execution"]["coverage_by_generation"]["0"]
    assert grid["basis"] == "grid"
