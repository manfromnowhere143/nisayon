"""Bounded native factorial using unchanged Brain 01 execution and evidence.

Fixed interventions are evaluator-side causal probes, not deployable policies.
No fresh confirmation or candidate promotion is performed by this program.
"""

import argparse
import json
import math
import re
import shutil
import time
from pathlib import Path

from nisayon.engine.io import decode_json

from .evidence import sha256, write_json


def validate_definition(definition: dict) -> None:
    """Bound execution before creating artifacts or dispatching a native run."""
    if definition.get("schema") != "ricci.rb02.factorial.v1":
        raise ValueError("unsupported protocol")
    episodes = definition.get("episodes")
    if not isinstance(episodes, list) or not 1 <= len(episodes) <= 40:
        raise ValueError("episode count outside research bound")
    bounds = {
        "max_episodes": (len(episodes), 40),
        "max_artifact_bytes": (120_000_000, 3 * 1024**3),
        "episode_reservation_bytes": (120_000_000, 256 * 1024**2),
        "minimum_free_bytes": (2 * 1024**3, 1024**4),
        "maximum_wall_s": (1, 1200),
    }
    limits = definition.get("limits", {})
    for name, (low, high) in bounds.items():
        value = limits.get(name)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"invalid resource bound: {name}")
    if limits["episode_reservation_bytes"] > limits["max_artifact_bytes"]:
        raise ValueError("artifact budget cannot hold one episode reservation")
    names = set()
    for case in episodes:
        name = case.get("id")
        if not isinstance(name, str) or re.fullmatch(r"[a-z0-9_-]{1,100}", name) is None:
            raise ValueError("unsafe episode identity")
        if name in names:
            raise ValueError("duplicate episode identity")
        names.add(name)
        config = case.get("config")
        if not isinstance(config, dict):
            raise ValueError("episode config must be an object")
        for key, default, low, high in (
            ("duration", 13, 0.02, 13),
            ("timestep", 0.002, 0.001, 0.02),
            ("iterations", 80, 1, 80),
        ):
            value = config.get(key, default)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"invalid execution bound: {key}")
            if key == "iterations" and type(value) is not int:
                raise ValueError("iterations must be an integer")


def run_campaign(protocol: Path, expected_digest: str, output: Path) -> None:
    from ricci_brain.episode import run, source_identity

    if sha256(protocol) != expected_digest:
        raise ValueError("protocol differs from prospective freeze")
    definition = decode_json(protocol.read_bytes())
    validate_definition(definition)
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
