"""Read the pinned, public CureWM scalar records without running a policy.

This is an exposed retrospective readback, not fresh confirmation. The independent
AUROC calculation uses direct pair comparisons. Original pure metric functions
are loaded from their verified definitions, without executing the bootstrap driver.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import time
from pathlib import Path

COMMIT = "8a7ee5dfd71eab09020db57754e72a4dc23c825b"
SUITES = {
    "Goal": (["ho_A", "ho_B", "ho2_A", "ho2_B"], "pre"),
    "Spatial": (["spatial_A", "spatial_B"], "base"),
    "Object": (["object_A", "object_B"], "base"),
    "LIBERO-10": (["10_A", "10_B"], "base"),
}


def index_records(records: list[dict]) -> dict:
    indexed = {}
    for record in records:
        key = (record["_shard"], record["name"])
        if not all(isinstance(part, str) and part for part in key):
            raise ValueError("Invalid record identity")
        if key in indexed:
            raise ValueError("Duplicate record identity")
        if type(record["outcome"]) is not bool:
            raise ValueError("Outcome must be explicit Boolean")
        for field in ("value_fail_action", "value_nominal_action"):
            value = record[field]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Nonfinite or invalid score")
        if re.match(r"d\d+", record["name"]) is None:
            raise ValueError("Missing source demonstration identity")
        indexed[key] = record
    return indexed


def require_matching(arms: list[dict]) -> None:
    if len(arms) != 3 or not arms[0]:
        raise ValueError("Three nonempty arms are required")
    keys = set(arms[0])
    for arm in arms[1:]:
        if set(arm) != keys:
            raise ValueError("Incomplete arm coverage")
        for key in keys:
            for field in ("outcome", "family", "severity"):
                if arm[key][field] != arms[0][key][field]:
                    raise ValueError("Paired metadata differs")


def pair_auroc(failures: list[float], survivors: list[float]) -> float:
    if not failures or not survivors:
        raise ValueError("Both outcome classes are required")
    twice_wins = sum(
        2 * (success > failure) + (success == failure)
        for success in survivors
        for failure in failures
    )
    return twice_wins / (2 * len(failures) * len(survivors))


def controls() -> int:
    assert pair_auroc([0.0], [1.0]) == 1.0
    assert pair_auroc([1.0], [0.0]) == 0.0
    assert pair_auroc([0.5], [0.5]) == 0.5
    assert pair_auroc([0.0, 1.0], [0.0, 1.0]) == 0.5
    base = {
        "_shard": "control",
        "name": "d0001_test",
        "outcome": False,
        "family": "control",
        "severity": 1,
        "value_fail_action": 0.25,
        "value_nominal_action": 0.75,
    }
    valid = index_records([base])
    require_matching([valid, valid, valid])
    bad_calls = [
        lambda: index_records([base, base]),
        lambda: index_records([dict(base, outcome=None)]),
        lambda: index_records([dict(base, value_fail_action=float("nan"))]),
        lambda: require_matching([valid, valid, {}]),
        lambda: require_matching([valid, valid, index_records([dict(base, outcome=True)])]),
        lambda: pair_auroc([], [0.5]),
    ]
    for call in bad_calls:
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("Invalid control was accepted")
    return 11


def audit(source: Path) -> dict:
    ledger = json.loads((source / "analysis-source-ledger.json").read_text())
    for entry in ledger:
        if entry["commit"] != COMMIT:
            raise ValueError("Unexpected source revision")
        payload = (source / entry["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise ValueError("Pinned file changed")
    native_path = source / "analysis/grid44.py"
    module = ast.parse(native_path.read_text())
    definitions = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in {"auroc", "metrics"}
    ]
    if len(definitions) != 2:
        raise ValueError("Expected native pure functions are absent")
    native = {}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(native_path), "exec"), native)
    rows = []
    for suite, (shards, released_tag) in SUITES.items():
        arms = {}
        for label, tag in [("released", released_tag), ("control", "ctrl"), ("CureWM", "post")]:
            records = []
            for shard in shards:
                path = source / "analysis" / f"probe_{tag}fa_{shard}.jsonl"
                for line in path.read_text().splitlines():
                    if line.strip():
                        record = json.loads(line)
                        if "_shard" in record:
                            raise ValueError("Unexpected reserved readback field")
                        records.append(dict(record, _shard=shard))
            arms[label] = index_records(records)
        require_matching(list(arms.values()))
        for label, indexed in arms.items():
            records = list(indexed.values())
            failures = [r["value_fail_action"] for r in records if not r["outcome"]]
            survivors = [r["value_fail_action"] for r in records if r["outcome"]]
            optimism = 100 * sum(v > 0.5 for v in failures) / len(failures)
            false_alarm = 100 * sum(v <= 0.5 for v in survivors) / len(survivors)
            auroc = pair_auroc(failures, survivors)
            reference = native["metrics"](records)
            for key, calculated in [("opt", optimism), ("fa", false_alarm), ("auroc", auroc)]:
                if not math.isclose(calculated, reference[key], rel_tol=0, abs_tol=1e-12):
                    raise ValueError("Independent and native metrics differ")
            clusters = {(r["_shard"], re.match(r"d\d+", r["name"]).group()) for r in records}
            rows.append(
                {
                    "suite": suite,
                    "arm": label,
                    "failures": len(failures),
                    "survivors": len(survivors),
                    "declared_demo_clusters": len(clusters),
                    "optimism_percent": optimism,
                    "false_positive_percent": false_alarm,
                    "auroc": auroc,
                    "matches_native_pure_metrics": True,
                }
            )
    return {
        "source_commit": COMMIT,
        "status": "supported_public_record_readback",
        "controls_passed": controls(),
        "matched_cells": len(rows),
        "records_per_arm": sum(
            r["failures"] + r["survivors"] for r in rows if r["arm"] == "released"
        ),
        "rows": rows,
        "limits": [
            "Public exposed scalar records; no fresh simulator or policy execution.",
            "Cluster identities follow declared shard/demo names, not independently checked trajectories.",
            "A diagnostic threshold is not a calibrated probability or an owner decision rule.",
            "No robot task success, owner savings, replay validity or generalization reproduced.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Output must not already exist")
    started = time.monotonic()
    result = audit(args.source)
    result["elapsed_seconds"] = time.monotonic() - started
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "status",
                    "controls_passed",
                    "matched_cells",
                    "records_per_arm",
                    "elapsed_seconds",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
