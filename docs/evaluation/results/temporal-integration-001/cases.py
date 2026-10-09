"""Frozen constructed cases for the temporal reference assessment, with expected verdicts.

Every trace here is written by hand as an explicit event list; none is produced by an
executor. Expected statuses were written before the reference ran on them and are the
oracle for the differential check in ``run_cases.py``. Only ``early_reset_affected`` and
``early_reset_upstream_fix`` are grounded in a retained upstream source path (LeRobot issue
1116 and PR 1117, control_utils.py at a445d9c and 6163daa); the rest are constructed
controls and are labelled so. Virtual time is exact, in controller ticks.
"""

from __future__ import annotations

CONFIG = "cfgA" * 16  # a 64-character stand-in for a configuration digest
CONFIG_B = "cfgB" * 16
CLOCKS = {"names": ["controller", "server"], "declared_mappings": []}
CLOCKS_MAPPED = {
    "names": ["controller", "server"],
    "declared_mappings": [
        {"from": "server", "to": "controller", "offset": 100.0, "uncertainty": 0.5, "unit": "tick"}
    ],
}
CLOCKS_AMBIGUOUS = {
    "names": ["controller", "server"],
    "declared_mappings": [
        {"from": "server", "to": "controller", "offset": 100.0, "uncertainty": 1.0, "unit": "tick"}
    ],
}
CONFIGURATION = {
    "policy_id": "scripted-double",
    "config_sha256": CONFIG,
    "chunk_length": 3,
    "control_period": 1,
    "aggregation": "latest_arrival_wins",
    "max_age": 4,
    "steps_per_generation": 6,
    "useful_coverage_min": 0.8,
}


def t(value: float, clock: str = "controller") -> dict:
    return {"value": value, "clock": clock, "unit": "tick"}


def obs(seq, obs_id, generation, step, at):
    return {
        "seq": seq,
        "kind": "observation_acquired",
        "obs_id": obs_id,
        "generation": generation,
        "step": step,
        "at": t(at),
    }


def req(seq, req_id, obs_id, generation, at, config=CONFIG):
    return {
        "seq": seq,
        "kind": "request_sent",
        "req_id": req_id,
        "obs_id": obs_id,
        "generation": generation,
        "config_sha256": config,
        "at": t(at),
    }


def resp(seq, resp_id, req_id, chunk_id, first_step, at, ordinals=3, **extra):
    event = {
        "seq": seq,
        "kind": "response_arrived",
        "resp_id": resp_id,
        "req_id": req_id,
        "chunk_id": chunk_id,
        "first_step": first_step,
        "ordinals": ordinals,
        "at": t(at),
    }
    event.update(extra)
    return event


def admit(seq, chunk_id, admitted, at, replaced=(), skipped=(), reason="admitted"):
    return {
        "seq": seq,
        "kind": "queue_admitted",
        "chunk_id": chunk_id,
        "admitted": list(admitted),
        "skipped": list(skipped),
        "replaced": list(replaced),
        "reason": reason,
        "at": t(at),
    }


def dispatch(seq, chunk_id, ordinal, step, generation, at):
    return {
        "seq": seq,
        "kind": "action_dispatched",
        "action_id": f"{chunk_id}:{ordinal}",
        "chunk_id": chunk_id,
        "ordinal": ordinal,
        "step": step,
        "generation": generation,
        "at": t(at),
    }


def ack(seq, chunk_id, ordinal, at):
    return {
        "seq": seq,
        "kind": "dispatch_acknowledged",
        "action_id": f"{chunk_id}:{ordinal}",
        "at": t(at),
    }


def start(seq, generation, at):
    return {"seq": seq, "kind": "episode_start", "generation": generation, "at": t(at)}


def reset(seq, generation_from, generation_to, at, queued=()):
    return [
        {
            "seq": seq,
            "kind": "reset_requested",
            "generation_from": generation_from,
            "generation_to": generation_to,
            "at": t(at),
        },
        {
            "seq": seq + 1,
            "kind": "reset_completed",
            "generation": generation_to,
            "queued_at_reset": list(queued),
            "at": t(at),
        },
    ]


def trace(
    case_id,
    events,
    *,
    source_kind,
    source_note,
    clocks=CLOCKS,
    configuration=CONFIGURATION,
    execution_status="completed",
):
    return {
        "schema": "nisayon.temporal-trace.v1",
        "case_id": case_id,
        "schedule_sha256": None,
        "source": {"kind": source_kind, "note": source_note},
        "clocks": clocks,
        "configuration": configuration,
        "execution_status": execution_status,
        "events": events,
    }


def healthy():
    """Two chunks, the second overlapping the first's last step under latest-arrival-wins."""
    e = [
        start(1, 0, 0),
        obs(2, "o0", 0, 0, 0),
        req(3, "r0", "o0", 0, 0),
        resp(4, "p0", "r0", "c0", 1, 1),
        admit(5, "c0", [0, 1, 2], 1),
    ]
    e += [
        dispatch(6, "c0", 0, 1, 0, 1),
        ack(7, "c0", 0, 1),
        dispatch(8, "c0", 1, 2, 0, 2),
        ack(9, "c0", 1, 2),
    ]
    e += [
        obs(10, "o1", 0, 2, 2),
        req(11, "r1", "o1", 0, 2),
        resp(12, "p1", "r1", "c1", 3, 3),
        admit(
            13,
            "c1",
            [0, 1, 2],
            3,
            replaced=["c0:2"],
            reason="latest arrival replaces the overlapping tail",
        ),
    ]
    e += [
        dispatch(14, "c1", 0, 3, 0, 3),
        ack(15, "c1", 0, 3),
        dispatch(16, "c1", 1, 4, 0, 4),
        ack(17, "c1", 1, 4),
        dispatch(18, "c1", 2, 5, 0, 5),
        ack(19, "c1", 2, 5),
    ]
    return trace(
        "healthy_execution",
        e,
        source_kind="constructed_control",
        source_note="positive control: overlapping chunks under the frozen aggregation rule, every dispatch acknowledged",
    )


def early_reset_affected():
    """Episode 0 ends early with c0:2 still queued; the affected control loop (no reset)
    dispatches it as the first action of episode 1. LeRobot issue 1116 at a445d9c."""
    e = [
        start(1, 0, 0),
        obs(2, "o0", 0, 0, 0),
        req(3, "r0", "o0", 0, 0),
        resp(4, "p0", "r0", "c0", 1, 1),
        admit(5, "c0", [0, 1, 2], 1),
    ]
    e += [
        dispatch(6, "c0", 0, 1, 0, 1),
        ack(7, "c0", 0, 1),
        dispatch(8, "c0", 1, 2, 0, 2),
        ack(9, "c0", 1, 2),
    ]
    e += reset(10, 0, 1, 3, queued=["c0:2"])
    e += [start(12, 1, 3), dispatch(13, "c0", 2, 0, 1, 3), ack(14, "c0", 2, 3)]
    e += [
        obs(15, "o1", 1, 1, 4),
        req(16, "r1", "o1", 1, 4),
        resp(17, "p1", "r1", "c1", 1, 5),
        admit(18, "c1", [0, 1, 2], 5),
    ]
    e += [
        dispatch(19, "c1", 0, 1, 1, 5),
        ack(20, "c1", 0, 5),
        dispatch(21, "c1", 1, 2, 1, 6),
        ack(22, "c1", 1, 6),
        dispatch(23, "c1", 2, 3, 1, 7),
        ack(24, "c1", 2, 7),
    ]
    return trace(
        "early_reset_affected",
        e,
        source_kind="upstream_source_bound",
        source_note="LeRobot issue 1116: policy action queue survives an early episode reset; control_utils.py at a445d9c has no policy.reset() at control_loop entry",
    )


def early_reset_upstream_fix():
    """The same schedule under PR 1117: policy.reset() at control-loop entry empties the queue."""
    e = [
        start(1, 0, 0),
        obs(2, "o0", 0, 0, 0),
        req(3, "r0", "o0", 0, 0),
        resp(4, "p0", "r0", "c0", 1, 1),
        admit(5, "c0", [0, 1, 2], 1),
    ]
    e += [
        dispatch(6, "c0", 0, 1, 0, 1),
        ack(7, "c0", 0, 1),
        dispatch(8, "c0", 1, 2, 0, 2),
        ack(9, "c0", 1, 2),
    ]
    e += reset(10, 0, 1, 3, queued=["c0:2"])
    e += [
        admit(12, "c0", [], 3, replaced=["c0:2"], reason="policy.reset() at control_loop entry"),
        start(13, 1, 3),
    ]
    e += [
        obs(14, "o1", 1, 0, 3),
        req(15, "r1", "o1", 1, 3),
        resp(16, "p1", "r1", "c1", 1, 4),
        admit(17, "c1", [0, 1, 2], 4),
    ]
    e += [
        dispatch(18, "c1", 0, 1, 1, 4),
        ack(19, "c1", 0, 4),
        dispatch(20, "c1", 1, 2, 1, 5),
        ack(21, "c1", 1, 5),
        dispatch(22, "c1", 2, 3, 1, 6),
        ack(23, "c1", 2, 6),
    ]
    e += [
        obs(24, "o2", 1, 3, 6),
        req(25, "r2", "o2", 1, 6),
        resp(26, "p2", "r2", "c2", 4, 7),
        admit(27, "c2", [0, 1], 7),
    ]
    e += [
        dispatch(28, "c2", 0, 4, 1, 7),
        ack(29, "c2", 0, 7),
        dispatch(30, "c2", 1, 5, 1, 8),
        ack(31, "c2", 1, 8),
    ]
    return trace(
        "early_reset_upstream_fix",
        e,
        source_kind="upstream_source_bound",
        source_note="LeRobot PR 1117 at 6163daa: five added lines call policy.reset() at control_loop entry",
    )


def late_response_after_reset():
    """A chunk requested in generation 0 arrives after the reset; a producer without
    generation fencing admits and dispatches it in generation 1."""
    e = [start(1, 0, 0), obs(2, "o0", 0, 0, 0), req(3, "r0", "o0", 0, 0)]
    e += reset(4, 0, 1, 2, queued=[])
    e += [
        start(6, 1, 2),
        resp(7, "p0", "r0", "c0", 1, 3),
        admit(8, "c0", [0, 1, 2], 3),
        dispatch(9, "c0", 0, 1, 1, 3),
        ack(10, "c0", 0, 3),
    ]
    e += [
        obs(11, "o1", 1, 1, 3),
        req(12, "r1", "o1", 1, 3),
        resp(13, "p1", "r1", "c1", 2, 4),
        admit(14, "c1", [0, 1, 2], 4, replaced=["c0:1", "c0:2"]),
    ]
    e += [
        dispatch(15, "c1", 0, 2, 1, 4),
        ack(16, "c1", 0, 4),
        dispatch(17, "c1", 1, 3, 1, 5),
        ack(18, "c1", 1, 5),
        dispatch(19, "c1", 2, 4, 1, 6),
        ack(20, "c1", 2, 6),
    ]
    return trace(
        "late_response_after_reset",
        e,
        source_kind="constructed_control",
        source_note="not reachable in the pinned async client, which has no in-process reset; a stale response after a reset is a distinct case from an uncleared queue",
    )


def late_response_fenced():
    """The same schedule with generation fencing: the stale chunk is rejected, execution continues."""
    e = [start(1, 0, 0), obs(2, "o0", 0, 0, 0), req(3, "r0", "o0", 0, 0)]
    e += reset(4, 0, 1, 2, queued=[])
    e += [
        start(6, 1, 2),
        resp(7, "p0", "r0", "c0", 1, 3),
        admit(
            8, "c0", [], 3, skipped=[0, 1, 2], reason="generation 0 response fenced in generation 1"
        ),
    ]
    e += [
        obs(9, "o1", 1, 0, 2),
        req(10, "r1", "o1", 1, 2),
        resp(11, "p1", "r1", "c1", 1, 3),
        admit(12, "c1", [0, 1, 2], 3),
    ]
    e += [
        dispatch(13, "c1", 0, 1, 1, 3),
        ack(14, "c1", 0, 3),
        dispatch(15, "c1", 1, 2, 1, 4),
        ack(16, "c1", 1, 4),
        dispatch(17, "c1", 2, 3, 1, 5),
        ack(18, "c1", 2, 5),
    ]
    e += [
        obs(19, "o2", 1, 3, 5),
        req(20, "r2", "o2", 1, 5),
        resp(21, "p2", "r2", "c2", 4, 6),
        admit(22, "c2", [0, 1], 6),
        dispatch(23, "c2", 0, 4, 1, 6),
        ack(24, "c2", 0, 6),
        dispatch(25, "c2", 1, 5, 1, 7),
        ack(26, "c2", 1, 7),
    ]
    return trace(
        "late_response_fenced",
        e,
        source_kind="constructed_control",
        source_note="competent remedy: reject responses of an obsolete generation",
    )


def duplicate_response():
    e = [
        start(1, 0, 0),
        obs(2, "o0", 0, 0, 0),
        req(3, "r0", "o0", 0, 0),
        resp(4, "p0", "r0", "c0", 1, 1),
        admit(5, "c0", [0, 1, 2], 1),
    ]
    e += [dispatch(6, "c0", 0, 1, 0, 1), ack(7, "c0", 0, 1)]
    e += [
        resp(8, "p0-dup", "r0", "c0", 1, 2),
        admit(9, "c0", [0, 1, 2], 2, reason="duplicate delivery admitted again"),
    ]
    e += [
        dispatch(10, "c0", 0, 2, 0, 2),
        ack(11, "c0", 0, 2),
        dispatch(12, "c0", 1, 3, 0, 3),
        ack(13, "c0", 1, 3),
        dispatch(14, "c0", 2, 4, 0, 4),
        ack(15, "c0", 2, 4),
    ]
    return trace(
        "duplicate_response",
        e,
        source_kind="constructed_control",
        source_note="a duplicate delivery re-admitted after dispatch; the pinned client's sequential receiver does not produce duplicates",
    )


def out_of_order_arrival():
    """An older chunk (request r0) arrives after a newer one (r1) and, under latest-arrival-wins,
    overwrites the fresher actions for the overlapping steps."""
    e = [
        start(1, 0, 0),
        obs(2, "o0", 0, 0, 0),
        req(3, "r0", "o0", 0, 0),
        obs(4, "o1", 0, 1, 1),
        req(5, "r1", "o1", 0, 1),
    ]
    e += [
        resp(6, "p1", "r1", "c1", 2, 2),
        admit(7, "c1", [0, 1, 2], 2),
        dispatch(8, "c1", 0, 2, 0, 2),
        ack(9, "c1", 0, 2),
    ]
    e += [
        resp(10, "p0", "r0", "c0", 1, 3),
        admit(
            11,
            "c0",
            [2],
            3,
            skipped=[0, 1],
            replaced=["c1:1", "c1:2"],
            reason="older response replaces fresher queued actions",
        ),
    ]
    e += [dispatch(12, "c0", 2, 3, 0, 3), ack(13, "c0", 2, 3)]
    e += [
        obs(14, "o2", 0, 3, 3),
        req(15, "r2", "o2", 0, 3),
        resp(16, "p2", "r2", "c2", 4, 4),
        admit(17, "c2", [0, 1], 4),
        dispatch(18, "c2", 0, 4, 0, 4),
        ack(19, "c2", 0, 4),
        dispatch(20, "c2", 1, 5, 0, 5),
        ack(21, "c2", 1, 5),
    ]
    return trace(
        "out_of_order_arrival",
        e,
        source_kind="constructed_control",
        source_note="not reachable in the pinned client: one sequential receiver over one channel; constructed to exercise freshness under reordering",
    )


def overlapping_chunks_aggregated():
    e = healthy()["events"]
    return trace(
        "overlapping_chunks_aggregated",
        e,
        source_kind="upstream_source_bound",
        source_note="the pinned client's _aggregate_action_queues replaces overlapping steps by the latest arrival and drops uncovered queued actions; constructed schedule on that rule",
    )


def configuration_change():
    e = [
        start(1, 0, 0),
        obs(2, "o0", 0, 0, 0),
        req(3, "r0", "o0", 0, 0),
        {
            "seq": 4,
            "kind": "configuration_changed",
            "from_sha256": CONFIG,
            "to_sha256": CONFIG_B,
            "at": t(1),
        },
    ]
    e += [
        resp(5, "p0", "r0", "c0", 1, 1),
        admit(6, "c0", [0, 1, 2], 1),
        dispatch(7, "c0", 0, 1, 0, 1),
        ack(8, "c0", 0, 1),
        dispatch(9, "c0", 1, 2, 0, 2),
        ack(10, "c0", 1, 2),
        dispatch(11, "c0", 2, 3, 0, 3),
        ack(12, "c0", 2, 3),
    ]
    e += [
        obs(13, "o1", 0, 3, 3),
        req(14, "r1", "o1", 0, 3, config=CONFIG_B),
        resp(15, "p1", "r1", "c1", 4, 4),
        admit(16, "c1", [0, 1], 4),
        dispatch(17, "c1", 0, 4, 0, 4),
        ack(18, "c1", 0, 4),
        dispatch(19, "c1", 1, 5, 0, 5),
        ack(20, "c1", 1, 5),
    ]
    return trace(
        "configuration_change",
        e,
        source_kind="constructed_control",
        source_note="a response computed under the old configuration dispatched after the change; issue 2866 / PR 3160 motivate full configuration identity (path, type, device, rename map)",
    )


def ambiguous_clock():
    """Acquisition stamped in the server clock; the declared mapping has one tick of
    uncertainty, so ages 1 to 3 read within, 4 and 5 overlap the limit and 6 is beyond."""
    e = [
        start(1, 0, 0),
        {
            "seq": 2,
            "kind": "observation_acquired",
            "obs_id": "o0",
            "generation": 0,
            "step": 0,
            "at": t(-100.0, "server"),
        },
        req(3, "r0", "o0", 0, 0),
        resp(4, "p0", "r0", "c0", 1, 1),
        admit(5, "c0", [0, 1, 2], 1),
        dispatch(6, "c0", 0, 1, 0, 1),
        ack(7, "c0", 0, 1),
        dispatch(8, "c0", 1, 2, 0, 2),
        ack(9, "c0", 1, 2),
        dispatch(10, "c0", 2, 3, 0, 3),
        ack(11, "c0", 2, 3),
        {
            "seq": 12,
            "kind": "observation_acquired",
            "obs_id": "o1",
            "generation": 0,
            "step": 1,
            "at": t(-99.0, "server"),
        },
        req(13, "r1", "o1", 0, 1),
        resp(14, "p1", "r1", "c1", 4, 4),
        admit(15, "c1", [0, 1, 2], 4),
        dispatch(16, "c1", 0, 4, 0, 4),
        ack(17, "c1", 0, 4),
        dispatch(18, "c1", 1, 5, 0, 5),
        ack(19, "c1", 1, 5),
        dispatch(20, "c1", 2, 6, 0, 7),
        ack(21, "c1", 2, 7),
    ]
    return trace(
        "ambiguous_clock_mapping",
        e,
        source_kind="constructed_control",
        source_note="server-stamped acquisitions with a declared +-1 tick mapping: ages 1-3 within, 4-5 overlapping, 6 beyond the limit 4; coverage 6 of 7 ticks",
        clocks=CLOCKS_AMBIGUOUS,
    )


def lost_acknowledgement():
    e = healthy()["events"]
    e = [x for x in e if not (x["kind"] == "dispatch_acknowledged" and x["action_id"] == "c1:1")]
    return trace(
        "lost_dispatch_acknowledgement",
        e,
        source_kind="constructed_control",
        source_note="one dispatch has no acknowledgement and no failure record",
    )


def incomplete_raw_evidence():
    """A response without a request binding and an observation without an acquisition time."""
    e = [
        start(1, 0, 0),
        {
            "seq": 2,
            "kind": "observation_acquired",
            "obs_id": "o0",
            "generation": 0,
            "step": 0,
            "at": None,
        },
        req(3, "r0", "o0", 0, 0),
        {
            "seq": 4,
            "kind": "response_arrived",
            "resp_id": "p0",
            "req_id": None,
            "chunk_id": "c0",
            "first_step": 1,
            "ordinals": 3,
            "at": t(1),
        },
        admit(5, "c0", [0, 1, 2], 1),
    ]
    e += [
        dispatch(6, "c0", 0, 1, 0, 1),
        ack(7, "c0", 0, 1),
        dispatch(8, "c0", 1, 2, 0, 2),
        ack(9, "c0", 1, 2),
        dispatch(10, "c0", 2, 3, 0, 3),
        ack(11, "c0", 2, 3),
    ]
    e += [
        obs(12, "o1", 0, 3, 3),
        req(13, "r1", "o1", 0, 3),
        resp(14, "p1", "r1", "c1", 4, 4),
        admit(15, "c1", [0, 1], 4),
        dispatch(16, "c1", 0, 4, 0, 4),
        ack(17, "c1", 0, 4),
        dispatch(18, "c1", 1, 5, 0, 5),
        ack(19, "c1", 1, 5),
        {
            "seq": 20,
            "kind": "evidence_gap",
            "what": "acquisition time of o0",
            "reason": "recorder did not stamp the first frame",
        },
    ]
    return trace(
        "incomplete_raw_evidence",
        e,
        source_kind="constructed_control",
        source_note="two compatible histories: the unbound chunk may belong to this or an earlier generation; the unstamped observation may be fresh or stale",
    )


def drop_all_policy():
    e = [
        start(1, 0, 0),
        obs(2, "o0", 0, 0, 0),
        req(3, "r0", "o0", 0, 0),
        resp(4, "p0", "r0", "c0", 1, 1),
        admit(5, "c0", [], 1, skipped=[0, 1, 2], reason="stop policy drops every chunk"),
    ]
    e += [
        obs(6, "o1", 0, 0, 2),
        req(7, "r1", "o1", 0, 2),
        resp(8, "p1", "r1", "c1", 1, 3),
        admit(9, "c1", [], 3, skipped=[0, 1, 2], reason="stop policy drops every chunk"),
    ]
    return trace(
        "stop_drop_all",
        e,
        source_kind="constructed_control",
        source_note="a correction that refuses every chunk satisfies every identity predicate and fails usefulness",
    )


CASES = [
    healthy,
    early_reset_affected,
    early_reset_upstream_fix,
    late_response_after_reset,
    late_response_fenced,
    duplicate_response,
    out_of_order_arrival,
    overlapping_chunks_aggregated,
    configuration_change,
    ambiguous_clock,
    lost_acknowledgement,
    incomplete_raw_evidence,
    drop_all_policy,
]

# Expected statuses per predicate, written before running the reference; "satisfied" for
# any predicate not listed. The temporal_contract expectation follows: violated if any
# violated, else unresolved if any unresolved, else satisfied.
EXPECTED = {
    "healthy_execution": {},
    "early_reset_affected": {"generation_fencing": "violated", "queue_reset": "violated"},
    "early_reset_upstream_fix": {},
    "late_response_after_reset": {
        "generation_fencing": "violated",
        "useful_execution": "unresolved",
    },
    "late_response_fenced": {"useful_execution": "unresolved"},
    "duplicate_response": {"duplicate_dispatch": "violated"},
    "out_of_order_arrival": {},
    "overlapping_chunks_aggregated": {},
    "configuration_change": {"configuration_binding": "violated"},
    "ambiguous_clock_mapping": {"freshness": "violated"},
    "lost_dispatch_acknowledgement": {"acknowledgement": "unresolved"},
    "incomplete_raw_evidence": {
        "request_binding": "unresolved",
        "generation_fencing": "unresolved",
        "configuration_binding": "unresolved",
        "freshness": "unresolved",
    },
    "stop_drop_all": {"useful_execution": "violated"},
}
