"""Mutations of the execution lane's interface example through the public command.

Each variant changes one thing in the producer's own record shape and is assessed with
``python -m nisayon.evaluation temporal``. The expected outcome is written beside each
mutation before running. Inputs and assessments are retained.

Usage: mutate_example.py EXAMPLE OUT_DIR
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
from pathlib import Path

MUTATIONS = {
    "unchanged": (lambda d: d, "satisfied", {}),
    # A dispatch without a time cannot be placed on a tick: its age is unknown and, under
    # the frozen coverage rule, it covers no tick, so the contract reads violated.
    "dispatch_without_time": (
        lambda d: _set(d, "action_dispatched", "at", None),
        "violated",
        {"freshness": "unresolved", "useful_execution": "violated"},
    ),
    "non_monotone_seq": (lambda d: _seq(d), "invalid", {}),
    "response_without_request": (
        lambda d: _set(d, "response_arrived", "req_id", None),
        "unresolved",
        {"request_binding": "unresolved", "freshness": "unresolved"},
    ),
    "acquisition_in_undeclared_clock": (
        lambda d: _clock(d, "observation_acquired", "server"),
        "unresolved",
        {"freshness": "unresolved"},
    ),
    "dispatch_in_other_generation": (
        lambda d: _set(d, "action_dispatched", "generation", 1),
        "violated",
        {"generation_fencing": "violated"},
    ),
    "acknowledgement_dropped": (
        lambda d: _drop(d, "dispatch_acknowledged"),
        "unresolved",
        {"acknowledgement": "unresolved"},
    ),
    "dispatch_failed_instead": (
        lambda d: _fail(d),
        "violated",
        {"acknowledgement": "violated"},
    ),
    "unknown_event_kind": (lambda d: _kind(d), "invalid", {}),
}


def _events(d):
    return d["events"]


def _set(d, kind, key, value):
    for e in _events(d):
        if e["kind"] == kind:
            e[key] = value
    return d


def _seq(d):
    _events(d)[2]["seq"] = _events(d)[1]["seq"]
    return d


def _clock(d, kind, clock):
    for e in _events(d):
        if e["kind"] == kind and isinstance(e.get("at"), dict):
            e["at"]["clock"] = clock
    return d


def _drop(d, kind):
    d["events"] = [e for e in _events(d) if e["kind"] != kind]
    return d


def _fail(d):
    for e in _events(d):
        if e["kind"] == "dispatch_acknowledged":
            e["kind"] = "dispatch_failed"
            e["reason"] = "constructed: actuator rejected the command"
    return d


def _kind(d):
    _events(d)[-1]["kind"] = "not_an_event"
    return d


def main(argv: list[str]) -> int:
    example = json.loads(Path(argv[1]).read_text())
    out = Path(argv[2])
    (out / "inputs").mkdir(parents=True, exist_ok=True)
    (out / "assessments").mkdir(parents=True, exist_ok=True)
    rows = []
    for name, (mutate, expected_contract, expected_predicates) in MUTATIONS.items():
        trace = mutate(copy.deepcopy(example))
        trace["case_id"] = f"interface-example/{name}"
        path = out / "inputs" / f"{name}.json"
        path.write_text(json.dumps(trace, indent=1) + "\n")
        target = out / "assessments" / f"{name}.json"
        started = time.perf_counter()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "nisayon.evaluation",
                "temporal",
                str(path),
                "--json",
                "--out",
                str(target),
            ],
            capture_output=True,
            text=True,
        )
        wall = time.perf_counter() - started
        assessment = json.loads(target.read_text()) if target.is_file() else None
        observed = (
            {p: v["status"] for p, v in assessment["predicates"].items()} if assessment else None
        )
        agree = (
            assessment is not None
            and assessment["temporal_contract"] == expected_contract
            and all(observed.get(p) == s for p, s in expected_predicates.items())
        )
        rows.append(
            {
                "mutation": name,
                "returncode": completed.returncode,
                "command_wall_s": round(wall, 6),
                "expected_contract": expected_contract,
                "expected_predicates": expected_predicates,
                "observed_contract": assessment["temporal_contract"] if assessment else None,
                "observed_not_satisfied": {
                    p: s for p, s in (observed or {}).items() if s != "satisfied"
                },
                "problems": assessment["evidence"]["problems"]
                if assessment
                else completed.stderr[-300:],
                "agrees": agree,
            }
        )
        print(
            f"{'ok ' if agree else 'BAD'} {name}: {rows[-1]['observed_contract']} {rows[-1]['observed_not_satisfied']}"
        )
    summary = {
        "schema": "nisayon.temporal-integration.producer-mutations.v1",
        "example": str(argv[1]),
        "mutations": len(rows),
        "agreeing": sum(r["agrees"] for r in rows),
        "rows": rows,
        "scope": "the execution lane's constructed interface example, mutated one field at a time and assessed through the public command; not executed records",
    }
    (out / "mutations.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"{summary['agreeing']} of {summary['mutations']} agree")
    return 0 if summary["agreeing"] == summary["mutations"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
