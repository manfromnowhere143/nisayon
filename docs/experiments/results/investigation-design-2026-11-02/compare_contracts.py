"""Exposed component comparison, not an engineering-agent benchmark.

Reference labels judge plan completeness only. The ordinary comparator uses
JSON Schema and a direct checklist; both receive exactly the same requirements.
"""

import argparse
import copy
import json
import math
import subprocess
import time
import types
from pathlib import Path

import jsonschema

from nisayon import engagement_agent as current

HERE = Path(__file__).resolve().parent
BASE = "0727ba6cde880b1432f591aabd7b2f230f493f08"


def ordinary(response, packet, legacy):
    """A conventional schema plus an engineer's finite completeness checklist."""
    jsonschema.validate(response, current.RESPONSE_SCHEMA)
    old = {k: v for k, v in response.items() if k != "experiment_design"}
    legacy.validate_response(old, packet)
    design = response["experiment_design"]
    if response["action"] != "investigate":
        assert not design
        return
    assert len(design) == 1
    d = design[0]
    declared = [a["answer"] for a in response["alternatives"]]
    observed = [p["answer"] for p in d["predictions"]]
    assert len(declared) == len(set(declared))
    assert sorted(declared) == sorted(observed)
    predictions = [p["observation"].strip().casefold() for p in d["predictions"]]
    assert all(predictions) and len(set(predictions)) >= 2
    assert all(x.strip() for x in d["oracle"].values())
    assert d["minimum_execution"].strip()
    for cost in d["estimated_costs"].values():
        assert cost["basis"].strip()
        number = cost["value"]
        if number is not None:
            assert type(number) in (int, float) and math.isfinite(number) and number >= 0
    assert all(x.strip() for x in d["unresolved_assumptions"])


def main():
    source = subprocess.check_output(
        ["git", "show", f"{BASE}:src/nisayon/engagement_agent.py"], text=True
    )
    legacy = types.ModuleType("nisayon.legacy_engagement_agent")
    legacy.__package__ = "nisayon"
    exec(compile(source, "retained-v1-engagement-agent", "exec"), legacy.__dict__)
    packet = {
        "schema": current.VERSION,
        "job_id": "a" * 64,
        "fingerprint": "b" * 64,
        "sources": [{"id": "thread", "text": "The baseline action parity check failed."}],
    }
    valid = {
        "job_id": packet["job_id"],
        "snapshot_fingerprint": packet["fingerprint"],
        "action": "investigate",
        "reason": "Separate input mismatch from equal-input variability.",
        "claims": [
            {
                "statement": "The report records a failed baseline parity check.",
                "citations": [{"source_id": "thread", "quote": packet["sources"][0]["text"]}],
            }
        ],
        "unknowns": ["Input witnesses are not yet supplied."],
        "question": "Were the transformed inputs equal?",
        "alternatives": [
            {"answer": "different", "resulting_action": "Check input preparation."},
            {"answer": "equal", "resulting_action": "Check runtime and random state."},
        ],
        "experiment": "Compare retained input bytes and digests before any new policy run.",
        "stop_condition": "If original inputs are absent, request evidence and stop.",
        "draft": "",
        "lesson_proposals": [],
        "experiment_design": [
            {
                "predictions": [
                    {"answer": "different", "observation": "At least one byte differs."},
                    {"answer": "equal", "observation": "Every retained input byte agrees."},
                ],
                "oracle": {
                    "measurement": "Byte comparison and independent digest recomputation.",
                    "identity": "Original input witnesses requested from the owner.",
                    "independence": "Does not use the policy output as its answer.",
                    "limitations": "Does not test state/RNG equality or robot outcomes.",
                },
                "minimum_execution": "Read two artifacts; no policy execution.",
                "estimated_costs": {
                    r: {
                        "value": None,
                        "basis": "Unknown until input volume and reviewer are known.",
                    }
                    for r in current.COST_RESOURCES
                },
                "unresolved_assumptions": ["Witnesses describe actual inputs used in both starts."],
            }
        ],
    }
    cases = []

    def add(name, expected, mutate=lambda r: None):
        r = copy.deepcopy(valid)
        mutate(r)
        cases.append({"name": name, "expected_reviewable": expected, "response": r})

    add("explicit_unknown_costs", True)
    add(
        "correct_quote_invalid_causal_claim",
        True,
        lambda r: r["claims"][0].update(
            statement="The baseline failed, so the patch is proven correct."
        ),
    )
    add("missing_design", False, lambda r: r.pop("experiment_design"))
    for field in (
        "predictions",
        "oracle",
        "minimum_execution",
        "estimated_costs",
        "unresolved_assumptions",
    ):
        add("missing_" + field, False, lambda r, f=field: r["experiment_design"][0].pop(f))
    add("missing_prediction", False, lambda r: r["experiment_design"][0]["predictions"].pop())
    add(
        "unbound_prediction",
        False,
        lambda r: r["experiment_design"][0]["predictions"][0].update(answer="third answer"),
    )
    add(
        "nondiscriminating_predictions",
        False,
        lambda r: r["experiment_design"][0]["predictions"][1].update(
            observation="At least one byte differs."
        ),
    )
    for field in ("identity", "independence", "limitations", "measurement"):
        add(
            "blank_oracle_" + field,
            False,
            lambda r, f=field: r["experiment_design"][0]["oracle"].update({f: " "}),
        )
    add(
        "missing_human_cost",
        False,
        lambda r: r["experiment_design"][0]["estimated_costs"].pop("human_minutes"),
    )
    add(
        "unexplained_unknown_cost",
        False,
        lambda r: r["experiment_design"][0]["estimated_costs"]["charges_usd"].update(basis=" "),
    )
    for label, number in [("negative", -1), ("boolean", True)]:
        add(
            label + "_cost",
            False,
            lambda r, n=number: r["experiment_design"][0]["estimated_costs"]["wall_seconds"].update(
                value=n
            ),
        )
    add("empty_execution", False, lambda r: r["experiment_design"][0].update(minimum_execution=" "))
    add(
        "blank_assumption",
        False,
        lambda r: r["experiment_design"][0].update(unresolved_assumptions=[" "]),
    )
    add(
        "fabricated_quote",
        False,
        lambda r: r["claims"][0]["citations"][0].update(quote="The real robot passed every task."),
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    out = parser.parse_args().out
    out.mkdir(exist_ok=False)
    (out / "cases.json").write_text(json.dumps({"packet": packet, "cases": cases}, indent=2) + "\n")
    rows = []
    for case in cases:
        for name in ("original_v1", "ordinary_schema_checklist", "nisayon_v2"):
            started = time.perf_counter_ns()
            try:
                r = case["response"]
                if name == "original_v1":
                    legacy.validate_response(
                        {k: v for k, v in r.items() if k != "experiment_design"}, packet
                    )
                elif name == "ordinary_schema_checklist":
                    ordinary(r, packet, legacy)
                else:
                    current.validate_response(r, packet)
                accepted, error = True, None
            except (ValueError, AssertionError, jsonschema.ValidationError) as caught:
                accepted, error = False, str(caught)[:400]
            rows.append(
                {
                    "case": case["name"],
                    "arm": name,
                    "reviewable": accepted,
                    "expected_reviewable": case["expected_reviewable"],
                    "error": error,
                    "elapsed_ns": time.perf_counter_ns() - started,
                }
            )
    totals = {}
    for name in ("original_v1", "ordinary_schema_checklist", "nisayon_v2"):
        items = [r for r in rows if r["arm"] == name]
        totals[name] = {
            "cases": len(items),
            "matches_completeness_reference": sum(
                r["reviewable"] == r["expected_reviewable"] for r in items
            ),
            "incomplete_plans_admitted": sum(
                r["reviewable"] and not r["expected_reviewable"] for r in items
            ),
            "reviewable_plans_blocked": sum(
                not r["reviewable"] and r["expected_reviewable"] for r in items
            ),
        }
    result = {
        "scope": "Exposed completeness controls, not semantic truth or agent superiority",
        "original_source": BASE,
        "totals": totals,
        "rows": rows,
        "complete_cost_advantage": "not_established",
        "limits": [
            "Same investigator authors implementation and cases",
            "Checklist is an ordinary capable component, not a live engineering agent",
            "Correct-quote invalid-causality control stays unadjudicated in every arm",
        ],
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
