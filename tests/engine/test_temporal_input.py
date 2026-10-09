"""Reject unsupported execution declarations without repairing missing evidence."""

from __future__ import annotations

import copy
import json

import pytest

from nisayon.engine.temporal_experiment import DEFAULT_SUITE, run_suite, validate_suite
from nisayon.engine.temporal_runtime import TemporalRuntime


def suite():
    result = json.loads(DEFAULT_SUITE.read_bytes())
    result["cases"] = result["cases"][:1]
    result["remedies"] = [r for r in result["remedies"] if r["id"] == "conventional"]
    result["assignments"] = result["assignments"][3:4]
    return result


def test_all_retained_development_plans_remain_supported():
    paths = sorted(DEFAULT_SUITE.parent.glob("frozen-*.json"))
    assert DEFAULT_SUITE in paths
    for path in paths:
        declaration = json.loads(path.read_bytes())
        if path.name == "frozen-audit-coverage.v1.json":
            # Coverage freezes result membership; it is not an execution plan.
            # Name this one distinct document explicitly so malformed or new
            # execution plans still reach the production validator below.
            assert declaration["schema"] == "nisayon.temporal-audit-coverage.v1"
            continue
        validate_suite(declaration)


@pytest.mark.parametrize(
    "field,value",
    [
        ("time_unit", "ms"),
        ("aggregation", "average_all_chunks"),
        ("control_period", True),
        ("max_age", -1),
        ("config_sha256", "different-from-initial-configuration"),
    ],
)
def test_unsupported_execution_configuration_is_rejected(field, value):
    declared = suite()
    declared["cases"][0]["configuration"][field] = value
    with pytest.raises(ValueError):
        validate_suite(declared)


def test_response_step_cannot_alias_integer_queue_keys_through_boolean():
    declared = suite()
    declared["cases"][0]["schedule"][2]["first_step"] = False
    with pytest.raises(ValueError):
        validate_suite(declared)


@pytest.mark.parametrize("invalid", ["chunk", "sink", "clock", "remedy"])
def test_unsupported_operations_are_rejected_before_source_capture(invalid):
    declared = suite()
    case = declared["cases"][0]
    if invalid == "chunk":
        case["schedule"][2]["values"] = [1] * (case["configuration"]["chunk_length"] + 1)
    elif invalid == "sink":
        case["schedule"][3]["sink_outcome"] = {"unimplemented": True}
    elif invalid == "clock":
        case["clocks"]["declared_mappings"] = [{"from": [], "to": "controller"}]
    else:
        declared["remedies"][0]["deadline_check"] = []
    with pytest.raises(ValueError):
        validate_suite(declared)


def test_duplicate_json_members_do_not_silently_select_a_frozen_plan(tmp_path, monkeypatch):
    from nisayon.engine import temporal_experiment

    declared = suite()
    # The ordinary JSON decoder silently chooses the second value.
    text = json.dumps(declared).replace('"max_age": 50000000', '"max_age": 1, "max_age": 50000000')
    path = tmp_path / "suite.json"
    path.write_text(text)
    calls = []

    def source(_repo):
        calls.append("source")
        raise AssertionError("An ambiguous plan reached source capture")

    monkeypatch.setattr(temporal_experiment, "source_snapshot", source)
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        run_suite(path, tmp_path / "output", tmp_path)
    assert not calls
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("fresh_request", [False, True])
def test_later_observation_does_not_retroactively_bind_an_earlier_request(fresh_request):
    declared = suite()
    case = declared["cases"][0]
    observe, request, response, dispatch = case["schedule"]
    request["at_ns"], observe["at_ns"] = 0, 1_000_000
    case["schedule"] = [request, observe]
    if fresh_request:
        later = copy.deepcopy(request)
        later.update(id="fresh-request", req_id="q1", at_ns=2_000_000)
        case["schedule"].append(later)
    case["schedule"].append(response)
    if fresh_request:
        later = copy.deepcopy(response)
        later.update(
            id="fresh-response",
            req_id="q1",
            resp_id="r-c1",
            chunk_id="c1",
            delivery_id="fresh-delivery",
            at_ns=11_000_000,
            values=[2],
        )
        case["schedule"].append(later)
    case["schedule"].append(dispatch)
    events = []
    runtime = TemporalRuntime(case, declared["remedies"][0], events.append)
    runtime.start()
    for operation in case["schedule"]:
        runtime.execute(operation)
    values = [e["value"] for e in events if e["kind"] == "action_dispatched"]
    assert values == ([2] if fresh_request else []), events
    old = next(e for e in events if e["kind"] == "queue_admitted" and e["chunk_id"] == "c0")
    assert old["admitted"] == [], events
    assert old["reason"] == "unbound_request_or_observation"
    requests = [e for e in events if e["kind"] == "request_sent"]
    assert requests[0]["observation_available_at_send"] is False
    if fresh_request:
        assert requests[1]["observation_available_at_send"] is True
