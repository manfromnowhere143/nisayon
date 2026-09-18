"""Bind the bounded model comparison's decisions, packets, calls and disjoint costs.

Read-only analysis of one known incident repeated three times. This is neither
fresh confirmation nor independent replication; no model calls or physics run.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from collections import Counter
from pathlib import Path

from explain_development_parity import audit_arm, bound, compare_arms, read, ref, require

from nisayon.engine.costs import aggregate_commands
from nisayon.engine.identity import code_identity, project_root
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.store import resolve_member
from nisayon.evaluation.scoring import score_comparison


def common_packet(packet: dict) -> dict:
    """Remove only the predeclared B tool; keep all other information/budgets."""
    result = copy.deepcopy(packet)
    result["available_actions"].pop("audit", None)
    return result


def split_model_cost(parts: dict, model_wall: float) -> dict:
    result = dict(parts)
    residual = result.pop("diagnostic_unpartitioned_s")
    require(math.isfinite(model_wall) and model_wall >= 0, "Invalid model wall")
    require(model_wall <= residual + 1e-5, "Model wall overlaps other diagnostic costs")
    result["diagnostic_model_command_s"] = model_wall
    result["diagnostic_other_unpartitioned_s"] = residual - model_wall
    require(math.isclose(sum(result.values()), sum(parts.values())), "Cost partition changed")
    return result


def call_evidence(folder: Path, reference: dict, suite: dict) -> dict:
    path, result = bound(folder, reference)
    call = path.parent
    invocation, record = read(call / "invocation.json"), result["command_record"]
    require(read(call / "command-record.json") == record, "Call receipt changed")
    require(invocation["command"] == record["command"], "Call command changed")
    require(read(call / "response.json") == result["response"], "Model request changed")
    require(result["model"] == suite["settings"]["model"], "Model differs from freeze")
    require(result["effort"] == suite["settings"]["effort"], "Reasoning setting differs")
    require(record["git"]["head"] == suite["code"]["git_head"], "Call used other source")
    require(digest(record["command"][-1]) == suite["settings"]["prompt_sha256"], "Prompt differs")
    packet = folder / "packets" / call.name
    for name, sha in invocation["public_packet"].items():
        require(file_digest(resolve_member(packet, name)) == sha, "Changed public packet")
    log = Path(result["events_reference"]["locator"])
    require(file_digest(log) == result["events_reference"]["sha256"], "Call events changed")
    events = [json.loads(line) for line in log.read_text().splitlines()]
    usage = [e["usage"] for e in events if e["type"] == "turn.completed"]
    require(result["usage_complete"] and usage == result["usage_events"], "Usage not evidenced")
    require(len(usage) == 1, "Unknown number of completed model turns")
    commands = [
        {key: e["item"].get(key) for key in ("command", "exit_code", "status")}
        for e in events
        if e["type"] == "item.completed" and e.get("item", {}).get("type") == "command_execution"
    ]
    return {
        "result": reference,
        "invocation": ref(folder, call / "invocation.json"),
        "events": result["events_reference"],
        "public_packet": invocation["public_packet"],
        "command_record_id": record["id"],
        "parent_command_record_id": record["parent_command_record_id"],
        "model": result["model"],
        "response": result["response"],
        "command_wall_s": record["wall_seconds"],
        "usage": usage[0],
        "observed_shell_commands": commands,
        "observed_shell_failures": sum(c["exit_code"] != 0 for c in commands),
        "provider_internal_retries": None,
    }


def analyze(root: Path) -> dict:
    suite, ledger = read(root / "frozen-suite.json"), read(root / "comparison-ledger.json")
    require(ledger["execution_complete"], "Incomplete experiment")
    require(digest(suite) == ledger["suite"]["case_ledger_sha256"], "Freeze binding changed")
    require(ledger["cases"] == suite["cases"] and ledger["arms"] == suite["arms"], "Arms changed")
    trials = {(t["case_id"], t["arm"]): t for t in ledger["trials"]}
    require(
        len(suite["cases"]) == 3 and len(trials) == len(ledger["trials"]) == 6, "Assignments lost"
    )
    require(len(set(suite["retained_original_incident_ids"])) == 10, "Original incident omitted")
    require(
        {c["original_incident_id"] for c in suite["cases"]} == {"D07-sign-and-backlog"},
        "Incident identity changed",
    )
    score = score_comparison(ledger, root)
    require(score == read(root / "comparison-score.json"), "Retrospective score differs")
    report = {
        "schema": "nisayon.bounded-comparison-analysis.v1",
        "scope": "Retrospective analysis of three paired repetitions of one known development incident, not a held-out AI-agent benchmark",
        "raw_root_locator": str(root),
        "analysis_code": code_identity(),
        "bindings": {
            name: ref(root, root / name)
            for name in (
                "frozen-suite.json",
                "comparison-ledger.json",
                "comparison-score.json",
                "preparation-costs.json",
            )
        },
        "frozen_code": suite["code"],
        "unique_development_incidents": 1,
        "paired_assignments": 3,
        "fresh_condition_seeds": sum(len(v) for v in suite["condition_seeds"].values()),
        "score": score,
        "pairs": [],
        "totals": {},
        "cost_boundary": "Model commands, simulator executions and checks partition own phases; they are not added to phase or outer command walls. Cached input is a subset. Shared invocation residual and historical preparation are separate. Human/provider/energy and unrecorded development costs remain unknown.",
    }
    parent_ids = set()
    for case in suite["cases"]:
        arms, packets = {}, {}
        for arm in ("A", "B"):
            trial = trials[case["id"], arm]
            detail = audit_arm(root, case, trial)
            path, diagnosis = bound(root, trial["diagnosis"])
            calls = [call_evidence(path.parent, c, suite) for c in diagnosis["calls"]]
            usage = {
                key: sum(c["usage"][key] for c in calls)
                for key in ("input_tokens", "output_tokens", "cached_input_tokens")
            }
            require(
                all(usage[k] == diagnosis["agent_usage"][k] for k in usage),
                "Call tokens do not reconcile",
            )
            require(
                usage["input_tokens"] + usage["output_tokens"]
                == trial["costs"]["agent_tokens"]["value"],
                "Trial tokens double-counted or omitted",
            )
            require(usage["cached_input_tokens"] <= usage["input_tokens"], "Invalid cached subset")
            parent_ids.update(c["parent_command_record_id"] for c in calls)
            detail.update(
                {
                    "calls": calls,
                    "tokens": usage,
                    "requests": diagnosis["history"],
                    "optional_audit_requests": sum(
                        h["request"]["action"] == "audit" for h in diagnosis["history"]
                    ),
                }
            )
            detail["cost_partition"] = split_model_cost(
                detail["cost_partition"], sum(c["command_wall_s"] for c in calls)
            )
            detail["progress_violations_in_confirmation_pairs"] = sum(
                r["progress"] == "lost"
                for name, r in read(root / trial["decision"]["path"])["runs"].items()
                if name.startswith("confirmation-")
            )
            arms[arm] = detail
            packets[arm] = read(path.parent / "packets/00/packet.json")
        parity = compare_arms(arms["A"], arms["B"])
        parity["initial_packet_except_optional_tool"] = common_packet(
            packets["A"]
        ) == common_packet(packets["B"])
        report["pairs"].append(
            {
                "case_id": case["id"],
                "order": suite["schedule"][case["id"]],
                "parity": parity,
                "arms": arms,
            }
        )
    require(len(parent_ids) == 1 and None not in parent_ids, "Missing parent cost scope")
    parent = project_root() / ".nisayon/runs" / parent_ids.pop() / "run.json"
    outer = read(parent)
    require(outer["process_status"] == "completed", "Outer command not complete")
    report["outer_command_record"] = {
        "locator": str(parent),
        "sha256": file_digest(parent),
        "record": outer,
    }
    for arm in ("A", "B"):
        values = [p["arms"][arm] for p in report["pairs"]]
        report["totals"][arm] = {
            "outcomes": dict(Counter(v["trial_status"] for v in values)),
            "assigned_repetitions": len(values),
            "accepted_repetitions": sum(v["accepted"] for v in values),
            "optional_audit_requests": sum(v["optional_audit_requests"] for v in values),
            "physical_runs": sum(
                p["physical_runs"] for v in values for p in v["physical"].values()
            ),
            "model_calls": sum(len(v["calls"]) for v in values),
            "tokens": {k: sum(v["tokens"][k] for v in values) for k in values[0]["tokens"]},
            "cost_partition": {
                k: sum(v["cost_partition"][k] for v in values) for k in values[0]["cost_partition"]
            },
            "own_phase_wall_s": sum(v["own_phase_wall_s"] for v in values),
            "observed_shell_failures": sum(
                c["observed_shell_failures"] for v in values for c in v["calls"]
            ),
            "progress_violations_in_confirmation_pairs": sum(
                v["progress_violations_in_confirmation_pairs"] for v in values
            ),
        }
    report["measured_invocation_wall_s"] = ledger["measured_invocation_wall_s"]
    report["shared_invocation_residual_s"] = ledger["measured_invocation_wall_s"] - sum(
        t["own_phase_wall_s"] for t in report["totals"].values()
    )
    report["outer_command_wrapper_and_final_score_s"] = (
        outer["wall_seconds"] - ledger["measured_invocation_wall_s"]
    )
    preparation = read(root / "preparation-costs.json")
    report["historical_recorded_command_wall_s"] = preparation["known_command_wall_sum_s"]
    report["updated_mission_preparation_commands"] = aggregate_commands(
        [
            r
            for r in preparation["command_records"]
            if r["started_at"] >= "2026-09-18T07:18:12" and r["id"] != outer["id"]
        ]
    )
    report["all_measured_paths_equal"] = all(all(p["parity"].values()) for p in report["pairs"])
    return report


def table(report: dict) -> str:
    lines = [
        "| Pair / order | Accepted A / B | Runs A / B | Calls A / B | Own phases A / B (s) | Tokens A / B | B audits |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for pair in report["pairs"]:
        a, b = pair["arms"]["A"], pair["arms"]["B"]
        counts = [sum(p["physical_runs"] for p in v["physical"].values()) for v in (a, b)]
        tokens = [v["tokens"]["input_tokens"] + v["tokens"]["output_tokens"] for v in (a, b)]
        lines.append(
            f"| {pair['case_id']} / {''.join(pair['order'])} | {a['accepted']} / {b['accepted']} | {counts[0]} / {counts[1]} | {len(a['calls'])} / {len(b['calls'])} | {a['own_phase_wall_s']:.3f} / {b['own_phase_wall_s']:.3f} | {tokens[0]} / {tokens[1]} | {b['optional_audit_requests']} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(strict=True), args.output.resolve()
    require(not output.exists() and not output.is_relative_to(root), "Use a new analysis directory")
    result = analyze(root)
    write_json(output / "analysis.json", result)
    (output / "table.md").write_text(table(result))
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "all_measured_paths_equal",
                    "totals",
                    "shared_invocation_residual_s",
                    "updated_mission_preparation_commands",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
