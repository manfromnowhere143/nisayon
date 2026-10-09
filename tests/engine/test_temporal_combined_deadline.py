"""Both freshness boundaries matter; old controls stay frozen and exposed."""

from __future__ import annotations

import copy
import json

import pytest

from nisayon.engine.temporal_experiment import DEFAULT_SUITE, validate_suite
from nisayon.engine.temporal_runtime import TemporalRuntime


def declared_case(filename, prefix):
    suite = json.loads((DEFAULT_SUITE.parent / filename).read_bytes())
    case = next(c for c in suite["cases"] if c["id"].startswith(prefix + "-"))
    remedy = next(r for r in suite["remedies"] if r["id"] == "conventional")
    return copy.deepcopy(case), {**remedy, "deadline_check": "arrival_and_dispatch"}


def execute(case, remedy):
    events = []
    runtime = TemporalRuntime(case, remedy, events.append)
    runtime.start()
    for operation in case["schedule"]:
        runtime.execute(operation)
    return events


def test_stale_incoming_chunk_preserves_the_fresh_queued_action():
    case, remedy = declared_case("frozen-admission-conformance.v1.json", "Y03")
    events = execute(case, remedy)
    incoming = next(e for e in events if e["kind"] == "queue_admitted" and e["chunk_id"] == "c1")
    assert incoming["admitted"] == []
    assert incoming["replaced"] == []
    assert incoming["reason"] == "arrival_age_overdue"
    sent = [e for e in events if e["kind"] == "action_dispatched"]
    assert [(e["action_id"], e["value"]) for e in sent] == [("c0:0", 1)]
    assert sent[0]["age_guard"]["upper_ns"] == 20_000_000


def test_fresh_admission_does_not_authorize_expired_dispatch():
    case, remedy = declared_case("frozen-suite.v2.json", "T15")
    events = execute(case, remedy)
    sent = [e for e in events if e["kind"] == "action_dispatched"]
    assert [e["value"] for e in sent] == [10]
    refused = next(e for e in events if e["kind"] == "dispatch_refused")
    assert refused["reason"] == "dispatch_age_overdue"
    assert refused["age_guard"]["lower_ns"] == 51_000_000
    assert any(e["kind"] == "dispatch_acknowledged" for e in events)


def test_inclusive_deadline_remains_useful():
    case, remedy = declared_case("frozen-suite.v2.json", "T14")
    sent = [e for e in execute(case, remedy) if e["kind"] == "action_dispatched"]
    assert [e["value"] for e in sent] == [1]
    assert sent[0]["age_guard"]["upper_ns"] == 50_000_000


@pytest.mark.parametrize(
    "filename,prefix",
    [("frozen-suite.v2.json", "T11"), ("frozen-clock-conformance.v1.json", "C02")],
)
def test_absent_or_ambiguous_age_cannot_enter_the_queue(filename, prefix):
    case, remedy = declared_case(filename, prefix)
    events = execute(case, remedy)
    assert not any(e["kind"] == "action_dispatched" for e in events)
    admission = next(e for e in events if e["kind"] == "queue_admitted")
    assert admission["admitted"] == []
    assert admission["reason"] == "arrival_age_unresolved"


def test_combined_option_is_an_explicit_validated_declaration():
    case, remedy = declared_case("frozen-suite.v2.json", "T14")
    suite = json.loads(DEFAULT_SUITE.read_bytes())
    suite.update(
        cases=[case],
        remedies=[remedy],
        assignments=[
            {
                "id": case["id"] + "--" + remedy["id"],
                "case_id": case["id"],
                "remedy_id": remedy["id"],
            }
        ],
    )
    validate_suite(suite)
