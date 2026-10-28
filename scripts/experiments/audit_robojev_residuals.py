"""Reanalyse pinned public RoboJev scores; no media, model inference or policy ranking.

Fetch the two files from DATASET_URL at REVISION, then pass them explicitly.
The raw files are hashed before parsing. Outputs are descriptive and exploratory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from nisayon.engine.io import decode_json
from nisayon.qualification import summarize_monitoring
from nisayon.qualification.models import fields, label

DATASET_URL = "https://huggingface.co/datasets/josefchen/RoboJev-evals"
REVISION = "dc55456160a7c4c19ac9d11dbfddc69b5c9843c6"
HASHES = {
    "benchmark": "c0f91f3587a400408cad927c07df09c1de1ab6d945b0b98015db73867538254e",
    "summary": "bcd1f6cf710c8b0315a3b4ae69914ca95ae926a1b1098ae12cb37759770dc198",
}
JUDGES = ("RoboJev-27B", "JEV-27B-VL (10 frames)")
REFERENCE = f"RoboJev-evals@{REVISION}/benchmark.jsonl human labels"
MODEL_REVISION = "e089a9b69a365744b80765057d86583647af95a9"
SUITES = ("so101", "unseen", "community")


def normalize(raw: list[dict], judge: str) -> list[dict]:
    """Validate source identity joins instead of relying on equal list lengths."""
    rows, seen, tasks = [], set(), {}
    for item in raw:
        fields(
            item,
            {"suite", "id", "task", "label", "scored", "source", "group", "episode", "predictions"},
        )
        for name in ("suite", "id", "task", "label", "source", "group", "episode"):
            label(item[name], name)
        suite = item["suite"]
        if suite not in SUITES:
            raise ValueError("Unknown source suite")
        if item["label"] not in {"success", "failure", "unclear"}:
            raise ValueError("Unknown source label")
        if type(item["scored"]) is not bool or item["scored"] != (item["label"] != "unclear"):
            raise ValueError("Source label and scored flag disagree")
        if not isinstance(item["predictions"], dict) or judge not in item["predictions"]:
            raise ValueError("Missing judge identity; a null score must be explicit")
        policy, session = None, None
        parts = item["id"].split("/")
        if suite == "so101":
            if len(parts) != 4 or not all(parts):
                raise ValueError("Invalid SO101 episode identity")
            group, policy, session, episode = parts
            if (group, episode, item["source"]) != (
                item["group"],
                item["episode"],
                "armnet/armnetbench_v01_robometer",
            ):
                raise ValueError("SO101 task/episode/source join disagrees")
            if tasks.setdefault(group, item["task"]) != item["task"]:
                raise ValueError("SO101 task instruction changed within a task group")
        elif suite == "unseen":
            if (
                parts != ["rbm-ood", item["group"], item["episode"]]
                or item["source"] != "robometer/rbm-1m-ood"
            ):
                raise ValueError("Unseen-domain source join disagrees")
        elif item["id"] != f"{item['source']}/{item['episode']}":
            raise ValueError("Community source join disagrees")
        episode_id = f"{suite}/{item['id']}"
        if episode_id in seen:
            raise ValueError("Duplicate source episode")
        seen.add(episode_id)
        rows.append(
            {
                "episode_id": episode_id,
                "task_id": item["task"],
                "policy_id": policy,
                "session_id": session,
                "outcome": "unclear" if not item["scored"] else item["label"],
                "score": item["predictions"][judge],
            }
        )
    # Validate every score before any filtering, including excluded binary labels.
    summarize_monitoring(
        rows, evaluator_id=judge, reference_id=REFERENCE, input_protocol="dense-v1"
    )
    return rows


def summarize(rows: list[dict], judge: str) -> dict:
    report = summarize_monitoring(
        rows, evaluator_id=judge, reference_id=REFERENCE, input_protocol="dense-v1", threshold=0.5
    )
    return {
        key: report[key]
        for key in ("input_sha256", "counts", "matrix", "rates", "missing_prediction_bounds")
    }


def task_standardized(rows: list[dict], tasks: list[str]) -> dict:
    """Equal task weight, then condition on failure; do not average FPRs."""
    masses = dict.fromkeys(("success", "failure", "miss", "retained"), 0.0)
    if not tasks or len(tasks) != len(set(tasks)):
        raise ValueError("Task standardization needs unique nonempty common tasks")
    for task in tasks:
        cell = [row for row in rows if row["task_id"] == task]
        if not cell or any(
            row["outcome"] not in ("success", "failure") or row["score"] is None for row in cell
        ):
            raise ValueError("Task standardization requires complete binary labels and scores")
        weight = 1 / (len(tasks) * len(cell))
        for row in cell:
            masses[row["outcome"]] += weight
            if row["score"] >= 0.5:
                masses["retained" if row["outcome"] == "success" else "miss"] += weight
    return {
        "episodes": sum(row["task_id"] in tasks for row in rows),
        "sessions": len(
            {(row["task_id"], row["session_id"]) for row in rows if row["task_id"] in tasks}
        ),
        "reference_success": masses["success"],
        "confirmed_misses_per_episode": masses["miss"],
        "conditional_miss": masses["miss"] / masses["failure"] if masses["failure"] else None,
        "valid_success_retention": masses["retained"] / masses["success"]
        if masses["success"]
        else None,
        "weighted_failure_mass": masses["failure"],
    }


def build_report(raw: list[dict], upstream: dict) -> dict:
    if upstream["model_revision"] != MODEL_REVISION:
        raise ValueError("Unexpected source model revision")
    normalized = {judge: normalize(raw, judge) for judge in JUDGES}
    report = {
        "schema": "nisayon.research.robojev_residual_audit.v1",
        "status": "exploratory_reanalysis_of_public_records",
        "source": {"url": DATASET_URL, "revision": REVISION, "sha256": HASHES},
        "threshold": 0.5,
        "model_revision": MODEL_REVISION,
        "acceptance_relation": "score >= threshold",
        "judges": {},
        "common_answered_comparison": {},
        "deployment_decision": "unresolved",
        "limit": "Human reference labels are not independently readjudicated. Policy IDs name cross-sectional cohorts, not a before/after improvement. Task standardization cannot remove session, checkpoint, initial-state or sampling confounding. All comparisons are exposed and descriptive; no confidence intervals, causal conclusion or model ranking is supplied.",
    }
    for judge, rows in normalized.items():
        if upstream["metrics"][judge]["protocol"] != "dense-v1":
            raise ValueError("Matched input-protocol declaration changed")
        by_suite = {
            suite: [row for row, source in zip(rows, raw, strict=True) if source["suite"] == suite]
            for suite in SUITES
        }
        task_policy, sessions, policies = defaultdict(list), defaultdict(list), defaultdict(list)
        for row, source in zip(rows, raw, strict=True):
            if source["suite"] != "so101":
                continue
            task_policy[(source["group"], row["policy_id"])].append(row)
            sessions[(source["group"], row["policy_id"], row["session_id"])].append(row)
            policies[row["policy_id"]].append(row)
        pairs = []
        for a, b in combinations(sorted(policies), 2):
            common = sorted(
                {row["task_id"] for row in policies[a]} & {row["task_id"] for row in policies[b]}
            )
            pair = {"policy_a": a, "policy_b": b, "common_tasks": common}
            if common:
                pair.update(
                    {
                        "a": task_standardized(policies[a], common),
                        "b": task_standardized(policies[b], common),
                    }
                )
            else:
                pair["status"] = "no_common_tasks"
            pairs.append(pair)
        suites = {suite: summarize(group, judge) for suite, group in by_suite.items()}
        reproduced = {}
        for suite in ("so101", "unseen"):
            rates = suites[suite]["rates"]
            actual = (
                rates["valid_success_retention"]["value"] + 1 - rates["conditional_miss"]["value"]
            ) / 2
            expected = upstream["metrics"][judge][f"{suite}_bacc"]
            if abs(actual - expected) > 0.000051:
                raise ValueError("Released balanced accuracy did not reproduce")
            reproduced[suite] = {"computed": actual, "published": expected}
        report["judges"][judge] = {
            "input_protocol": "dense-v1",
            "all": summarize(rows, judge),
            "suites": suites,
            "balanced_accuracy_readback": reproduced,
            "so101_pooled_policies": [
                {"policy": key, "summary": summarize(group, judge)}
                for key, group in sorted(policies.items())
            ],
            "so101_task_policy": [
                {"task": key[0], "policy": key[1], "summary": summarize(group, judge)}
                for key, group in sorted(task_policy.items())
            ],
            "so101_sessions": [
                {
                    "task": key[0],
                    "policy": key[1],
                    "session": key[2],
                    "summary": summarize(group, judge),
                }
                for key, group in sorted(sessions.items())
            ],
            "so101_common_task_pairs": pairs,
            "accepted_reference_failures": [
                row["episode_id"]
                for row in rows
                if row["outcome"] == "failure" and row["score"] is not None and row["score"] >= 0.5
            ],
            "rejected_reference_successes": [
                row["episode_id"]
                for row in rows
                if row["outcome"] == "success" and row["score"] is not None and row["score"] < 0.5
            ],
        }
    for suite in SUITES:
        indices = [
            i
            for i, item in enumerate(raw)
            if item["suite"] == suite
            and all(normalized[judge][i]["score"] is not None for judge in JUDGES)
        ]
        report["common_answered_comparison"][suite] = {
            "episodes": len(indices),
            "excluded_unanswered": sum(item["suite"] == suite for item in raw) - len(indices),
            "judges": {
                judge: summarize([rows[i] for i in indices], judge)
                for judge, rows in normalized.items()
            },
        }
    return report


def build_completion_report(raw: list[dict], upstream: dict) -> dict:
    """Keep the frozen original audit intact; report a separate post hoc analysis."""
    original = build_report(raw, upstream)
    report = {
        "schema": "nisayon.research.robojev_completion_audit.v1",
        "status": "post_hoc_finite_record_completion_analysis",
        "source": original["source"],
        "threshold": original["threshold"],
        "model_revision": original["model_revision"],
        "acceptance_relation": original["acceptance_relation"],
        "judges": {},
        "deployment_decision": "unresolved",
        "limit": (
            "Bounds vary unclear reference labels and missing scores in the released cohort. "
            "Known reference labels are assumed correct. They neither adjudicate unknown "
            "episodes nor correct omitted episodes, selection, label noise or population drift. "
            "This is a post hoc analysis of exposed records, not a fresh policy experiment."
        ),
    }
    for judge in JUDGES:
        rows = normalize(raw, judge)
        suites = {}
        for suite in SUITES:
            group = [row for row, source in zip(rows, raw, strict=True) if source["suite"] == suite]
            suites[suite] = summarize_monitoring(
                group,
                evaluator_id=judge,
                reference_id=REFERENCE,
                input_protocol="dense-v1",
                threshold=report["threshold"],
            )
        report["judges"][judge] = {
            "suites": suites,
            "balanced_accuracy_readback": original["judges"][judge]["balanced_accuracy_readback"],
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--completion-bounds",
        action="store_true",
        help="Write a separate analysis of ambiguous labels and missing scores",
    )
    args = parser.parse_args()
    data = {}
    for kind in ("benchmark", "summary"):
        content = getattr(args, kind).read_bytes()
        if hashlib.sha256(content).hexdigest() != HASHES[kind]:
            raise ValueError(f"{kind} SHA256 differs from the pinned release")
        data[kind] = content
    raw = [decode_json(line) for line in data["benchmark"].splitlines()]
    build = build_completion_report if args.completion_bounds else build_report
    report = build(raw, decode_json(data["summary"]))
    with args.out.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {"episodes": len(raw), "judges": list(report["judges"]), "status": report["status"]}
        )
    )


if __name__ == "__main__":
    main()
