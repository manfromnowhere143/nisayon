"""Exercise the optional audit on a linked copy of retained diagnostic evidence.

This is an interface positive control after the comparison. No model selects
the action, no physics is re-executed, and no result is fresh confirmation.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import time
from pathlib import Path

from nisayon.engine.agent_diagnostics import response_schema
from nisayon.engine.execution_store import ExecutionStore
from nisayon.engine.io import file_digest, write_json
from nisayon.evaluation import evaluate_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(strict=True), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    original = json.loads((source / "bundle.json").read_text())
    original_hash = file_digest(source / "bundle.json")
    # Immutable originals are read through hard links; only new snapshot paths
    # are created. No existing linked file is opened for writing or deletion.
    copied = output / "store"
    shutil.copytree(source, copied, copy_function=os.link)
    store = object.__new__(ExecutionStore)
    store.root = copied
    store.header = copy.deepcopy(
        {k: v for k, v in original.items() if k not in {"assignments", "runs", "artifact_manifest"}}
    )
    store.runs = copy.deepcopy(original["runs"])
    store.assignments = copy.deepcopy(original["assignments"])
    store.sealed, store.snapshots = False, 0
    audit_start = time.perf_counter()
    snapshot, integrity = store.snapshot()
    assessment = evaluate_bundle(snapshot, artifact_root=copied)
    audit_wall = time.perf_counter() - audit_start
    write_json(output / "decision.json", assessment)
    # These are exactly the fields the frozen controller exposes on its next
    # public packet. Private case labels and host paths are not returned.
    public = {
        "integrity": integrity,
        "decision": assessment["decision"],
        "runs": {
            rid: {
                k: value.get(k)
                for k in ("measurement", "outcome", "progress", "timing", "constraints", "findings")
            }
            for rid, value in assessment["runs"].items()
        },
    }
    write_json(output / "public-audit-observation.json", public)
    available = "audit" in response_schema("B")["properties"]["action"]["enum"]
    require_b_only = "audit" not in response_schema("A")["properties"]["action"]["enum"]
    unchanged = file_digest(source / "bundle.json") == original_hash
    result = {
        "schema": "nisayon.retained-audit-interface-probe.v1",
        "scope": "Post-comparison scripted positive control on retained diagnostic evidence, not a live-model request or fresh confirmation",
        "source": {"locator": str(source / "bundle.json"), "sha256": original_hash},
        "available_in_B_schema": available,
        "absent_from_A_schema": require_b_only,
        "integrity": integrity,
        "decision": assessment["decision"],
        "returned_run_ids": sorted(public["runs"]),
        "audit_wall_s": audit_wall,
        "total_probe_wall_s": time.perf_counter() - start,
        "source_unchanged": unchanged,
        "physical_runs_executed": 0,
        "live_model_calls": 0,
        "model_tokens": None,
        "token_boundary": "No model inference in this scripted probe; primary engineering-session tokens unmeasured",
        "observable_result": {
            "path": "public-audit-observation.json",
            "sha256": file_digest(output / "public-audit-observation.json"),
        },
        "remaining_limit": "The scored model never requested this tool. This checks the actual snapshot/evaluator path and inspectable return fields, not the value of an unobserved model decision after reading them.",
    }
    write_json(output / "probe.json", result)
    print(json.dumps(result, indent=2))
    if not (available and require_b_only and unchanged and integrity["status"] == "verified"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
