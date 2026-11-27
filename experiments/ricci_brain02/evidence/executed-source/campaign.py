"""Bounded native factorial using unchanged Brain 01 execution and evidence.

Fixed interventions are evaluator-side causal probes, not deployable policies.
No fresh confirmation or candidate promotion is performed by this program.
"""

import argparse
import json
import shutil
import time
from pathlib import Path

from .evidence import sha256, write_json


def run_campaign(protocol: Path, expected_digest: str, output: Path) -> None:
    from ricci_brain.episode import run, source_identity

    if sha256(protocol) != expected_digest:
        raise ValueError("protocol differs from prospective freeze")
    definition = json.loads(protocol.read_text())
    if definition["schema"] != "ricci.rb02.factorial.v1":
        raise ValueError("unsupported protocol")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(protocol, output / "protocol.json")
    source = source_identity()
    driver = sha256(Path(__file__))
    write_json(
        output / "source-binding.json",
        {"brain01": source, "driver_sha256": driver, "protocol_sha256": expected_digest},
    )
    index = []
    started = time.perf_counter()
    max_bytes = definition["limits"]["max_artifact_bytes"]
    for case in definition["episodes"]:
        if source != source_identity() or driver != sha256(Path(__file__)):
            raise RuntimeError("source changed during campaign")
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        reason = None
        if used + definition["limits"]["episode_reservation_bytes"] > max_bytes:
            reason = "artifact_budget"
        elif shutil.disk_usage(output).free < definition["limits"]["minimum_free_bytes"]:
            reason = "disk_floor"
        elif time.perf_counter() - started > definition["limits"]["maximum_wall_s"]:
            reason = "wall_budget"
        if reason:
            write_json(
                output / "incomplete.json",
                {"reason": reason, "next_case": case["id"], "completed_episodes": len(index)},
            )
            raise RuntimeError(f"bounded campaign stopped: {reason}")
        target = output / case["id"]
        print(json.dumps({"state": "running", "case": case["id"]}), flush=True)
        # Operational exceptions propagate. Partial output is retained; scientific
        # failure, censoring and noncompletion are successful executions of a case.
        result = run(target, **case["config"])
        record = {**case, "result": result, "manifest_sha256": sha256(target / "manifest.json")}
        index.append(record)
        write_json(output / "index.json", index)
        print(
            json.dumps(
                {
                    "state": "sealed",
                    "case": case["id"],
                    "outcome": result["outcome"],
                    "censored": result["censored"],
                }
            ),
            flush=True,
        )
    write_json(
        output / "cost.json",
        {
            "episodes": len(index),
            "wall_s": time.perf_counter() - started,
            "artifact_bytes": sum(p.stat().st_size for p in output.rglob("*") if p.is_file()),
            "native_episode_wall_s": sum(r["result"]["timing"]["total_wall_s"] for r in index),
            "simulated_s": sum(r["result"]["measurements"]["duration_s"] for r in index),
            "human_review_cost": None,
            "maintenance_cost": None,
            "scope": "Execution measurements; no complete-work savings claim.",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run_campaign(args.protocol, args.sha256, args.out)


if __name__ == "__main__":
    main()
