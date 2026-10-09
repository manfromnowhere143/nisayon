"""Freeze five exploratory boundary controls after the first complete batch.

These controls do not replace or extend the original scored population. Their
purpose is to check exact clock translation, activation context and attempt IDs.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import digest, write_json
from nisayon.engine.temporal_experiment import DEFAULT_SUITE, validate_suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--precision-only", action="store_true")
    args = parser.parse_args()
    original = json.loads(DEFAULT_SUITE.read_bytes())
    by_prefix = {case["id"].split("-")[0]: case for case in original["cases"]}
    cases = []
    for name, shift in (("X01-deadline-plus-one", 0), ("X02-deadline-plus-one-shifted", 2**60)):
        case = copy.deepcopy(by_prefix["T14"])
        case["id"] = name
        case["question"] = (
            "An exact 50000001 ns age exceeds the inclusive 50000000 ns deadline; a common epoch translation must not change this fact."
        )
        for row in case["schedule"]:
            row["at_ns"] += shift
            if row["operation"] == "dispatch":
                row["at_ns"] += 1
        case["exact_clock_translation_ns"] = shift
        cases.append(case)
    aba = copy.deepcopy(by_prefix["T08"])
    aba["id"] = "X03-configuration-aba"
    aba["question"] = (
        "An old request remains obsolete after configuration A to B to A; same content does not recover the old activation context."
    )
    obs0, req0, changed, obs1, req1, old_reply, new_reply, send = copy.deepcopy(aba["schedule"])
    original_sha = aba["initial_configuration"]
    returned = {"operation": "configure", "at_ns": 3_000_000, "config_sha256": original_sha}
    old_reply["at_ns"] = 4_000_000
    old_send = {**send, "at_ns": 5_000_000}
    obs1["at_ns"], req1["at_ns"], new_reply["at_ns"], send["at_ns"] = (
        6_000_000,
        7_000_000,
        8_000_000,
        9_000_000,
    )
    new_reply["config_sha256"] = original_sha
    aba["schedule"] = [
        obs0,
        req0,
        changed,
        returned,
        old_reply,
        old_send,
        obs1,
        req1,
        new_reply,
        send,
    ]
    cases.append(aba)
    lost = copy.deepcopy(by_prefix["T06"])
    lost["id"] = "X04-duplicate-with-lost-first-ack"
    lost["question"] = (
        "A second send of the same action ID cannot acknowledge the first attempt whose acknowledgement is missing."
    )
    next(row for row in lost["schedule"] if row["operation"] == "dispatch")["sink_outcome"] = (
        "ack_missing"
    )
    cases.append(lost)
    crossing = copy.deepcopy(by_prefix["T13"])
    crossing["id"] = "X05-clock-crosses-zero"
    crossing["question"] = (
        "The declared age interval is [-7000000,13000000] ns: it crosses the chronology boundary and does not establish nonnegative age."
    )
    next(row for row in crossing["schedule"] if row["operation"] == "dispatch")["at_ns"] = 3_000_000
    cases.append(crossing)
    if args.precision_only:
        precision = copy.deepcopy(cases[1])
        precision["id"] = "X06-deadline-resolution-boundary"
        delta = 2**54 - precision["exact_clock_translation_ns"]
        for row in precision["schedule"]:
            row["at_ns"] += delta
        precision["exact_clock_translation_ns"] = 2**54
        precision["refinement_reason"] = (
            "The 2**60 translation retained a beyond-deadline predicate while rounding the "
            "50000001 ns age to 50000128. This separately frozen 2**54 case checks the "
            "representable boundary at which float conversion can hide the one-nanosecond excess."
        )
        cases = [precision]
    for case in cases:
        case["evidence_role"] = "exploratory_integration_counterexample"
        for index, row in enumerate(case["schedule"]):
            row["id"] = f"{case['id']}-input-{index:02d}"
            if row["operation"] == "response":
                row["delivery_id"] = f"{case['id']}-delivery-{index:02d}"
    suite = {
        "schema": "nisayon.temporal-suite.v1",
        "id": "temporal-reference-precision-001"
        if args.precision_only
        else "temporal-reference-boundary-001",
        "protocol_revision": 1,
        "frozen_at": datetime.now(UTC).isoformat(),
        "case_origin": "exploratory constructed controls after first 120-assignment batch",
        "parent_suite": {"path": str(DEFAULT_SUITE), "sha256": digest(original)},
        "cases": cases,
        "remedies": copy.deepcopy(original["remedies"]),
        "assignments": [
            {"id": c["id"] + "--" + r["id"], "case_id": c["id"], "remedy_id": r["id"]}
            for c in cases
            for r in original["remedies"]
        ],
        "limits": copy.deepcopy(original["limits"]),
        "comparison": copy.deepcopy(original["comparison"]),
        "analysis_plan": {
            "clock_translation": "Compare exact integer timestamp differences on X01 and X02. Common offsets do not change elapsed duration or deadline predicates.",
            "configuration_activation": "Evaluate the old request against the retained intervening configuration activations, not content hash equality alone.",
            "acknowledgement": "Bind outcomes to dispatch_id; retain the first missing acknowledgement even if a later duplicate send is acknowledged.",
            "chronology": "Record whether a clock interval crossing zero establishes the declared nonnegative-age premise; do not silently assume the premise.",
            "population": f"Report all {len(cases) * len(original['remedies'])} exploratory assignments separately from the original 120 and any prior exploratory controls. These are integration counterexamples, not new independent or robot incidents.",
        },
    }
    validate_suite(suite)
    write_json(args.out, suite)
    print(
        json.dumps(
            {"cases": len(cases), "assignments": len(suite["assignments"]), "sha256": digest(suite)}
        )
    )


if __name__ == "__main__":
    main()
