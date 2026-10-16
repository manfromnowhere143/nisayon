"""Exposed cost controls and read-only D05 accounting; no simulator execution."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.costs import aggregate_commands
from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.checks import RunAssessment
from nisayon.evaluation.decision import aggregate_costs
from nisayon.evaluation.first_case import read_document, write_document
from nisayon.evaluation.schema import Quantity


def run(name, value, parent=None, unit="s", omitted=False):
    return RunAssessment(
        name,
        costs={}
        if omitted
        else {"wall": Quantity(value, unit, "interrupted" if value is None else None)},
        cost_parent=parent,
    )


def controls():
    # Literal expected totals: deliberately independent of the traversal algorithm.
    return [
        ("measured_root", [run("outer", 8)], 8),
        ("measured_parent", [run("inner", 2, "outer"), run("outer", 8)], 8),
        ("interrupted_parent", [run("inner", 2, "outer"), run("outer", None)], 2),
        ("omitted_parent_item", [run("inner", 2, "outer"), run("outer", None, omitted=True)], 2),
        (
            "interrupted_chain",
            [run("inner", 2, "middle"), run("middle", None, "outer"), run("outer", None)],
            2,
        ),
        (
            "measured_grandparent",
            [run("inner", 2, "middle"), run("middle", None, "outer"), run("outer", 10)],
            10,
        ),
        ("absent_parent", [run("inner", 2, "absent")], 2),
        ("independent_runs", [run("one", 2), run("two", 3)], 5),
        ("measured_zero", [run("inner", 0, "outer"), run("outer", 0)], 0),
        ("multiple_children", [run("one", 2, "outer"), run("two", 3, "outer"), run("outer", 8)], 8),
        ("cycle", [run("one", 2, "two"), run("two", 3, "one")], None),
        ("self_cycle", [run("one", 2, "one")], None),
        ("mixed_units", [run("one", 2), run("two", 3000, unit="ms")], None),
        ("negative_cost", [run("one", -2)], None),
        ("child_larger_than_parent", [run("inner", 9, "outer"), run("outer", 8)], None),
    ]


def check(rows, expected):
    costs = aggregate_costs({row.run_id: row for row in rows}, None, 0)
    item = costs["per_item"]["wall"]
    actual = item["known_total"]
    valid = actual == expected and (expected is not None or item.get("status") == "invalid")
    return {"passed": valid, "expected_known_total": expected, "observed": costs}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    results = []
    for name, rows, expected in controls():
        result = {"name": name, "input": [row.to_dict() for row in rows], **check(rows, expected)}
        # An independently written existing producer path, only where its input contract fits.
        if expected is not None and name != "omitted_parent_item":
            comparator = aggregate_commands(
                [
                    {
                        "id": row.run_id,
                        "wall_seconds": row.costs["wall"].value,
                        "parent_command_record_id": row.cost_parent,
                    }
                    for row in rows
                ]
            )
            result["existing_command_ledger"] = comparator
        result["reverse_order"] = check(list(reversed(rows)), expected)
        results.append(result)
    path = (
        root
        / "docs/experiments/results/development-baseline-qualification-001/D05-recurrent-carry/execution/bundle.json.gz"
    )
    source_bytes = path.read_bytes()
    original = read_document(path)
    changed = copy.deepcopy(original)
    target = next(row for row in changed["runs"] if row["id"] == "reference-0")
    for quantity in target["costs"]:
        if quantity["category"] == "reset_rollout_trace_write":
            quantity.update(value=None, missing="N034 constructed interruption control")
    retained = {}
    with tempfile.TemporaryDirectory(prefix="nisayon-cost-retention-") as directory:
        for label, data in (("unchanged", original), ("interrupted_copy", changed)):
            folder = Path(directory) / label
            folder.mkdir()
            decision = evaluate_bundle(write_document(data, folder / "bundle.json"))
            retained[label] = {
                "decision": decision["decision"],
                "costs": decision["costs"],
                "run_measurements": {
                    key: {"measurement": run["measurement"], "outcome": run["outcome"]}
                    for key, run in decision["runs"].items()
                },
            }
    assert path.read_bytes() == source_bytes
    content = {
        "schema": "nisayon.cost-retention-probe.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / "src/nisayon/evaluation").glob("*.py"))
        },
        "controls": results,
        "passed": sum(row["passed"] and row["reverse_order"]["passed"] for row in results),
        "total": len(results),
        "d05_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "retained_d05": retained,
        "scope": "Exposed software accounting controls and readback; no new simulator or robot execution.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        stream.write(json.dumps(content, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps({"out": str(args.out), "passed": content["passed"], "total": content["total"]})
    )


if __name__ == "__main__":
    main()
