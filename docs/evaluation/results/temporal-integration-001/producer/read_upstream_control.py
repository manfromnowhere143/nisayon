"""Independently re-derive the execution lane's source-bound historical control readings.

The execution lane's ``upstream-control-001.json`` records six software runs of the actual
LeRobot caller, control loop and ACT queue methods with scripted doubles, in its own event
schema, plus 48 extraction records binding each executed definition to the retained source
bytes. This reader does not run any of that. It checks that every extraction's file digest
matches the retained packet, re-derives per run the number of software dispatches and the
number whose action originated in an earlier episode from the raw events, and compares
those with the producer's own measurements.

Usage: read_upstream_control.py READBACK PACKET_DIR OUT_DIR
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    readback = json.loads(Path(argv[1]).read_text())
    packet = Path(argv[2])
    out = Path(argv[3])
    extraction_matches = 0
    mismatched_files = []
    for e in readback["extractions"]:
        actual = hashlib.sha256((packet / e["file"]).read_bytes()).hexdigest()
        if actual == e["file_sha256"]:
            extraction_matches += 1
        else:
            mismatched_files.append(e["file"])
    runs = []
    for run in readback["runs"]:
        dispatches = [e for e in run["events"] if e["kind"] == "action_dispatched"]
        cross = [
            e
            for e in dispatches
            if e.get("episode") is not None
            and e["action"].get("origin_episode") is not None
            and e["action"]["origin_episode"] != e["episode"]
        ]
        resets = [e for e in run["events"] if e["kind"] == "policy_reset"]
        measured = run.get("measurements", {})
        runs.append(
            {
                "assignment_id": run["assignment_id"],
                "variant": run["variant"],
                "upstream_commit": run["upstream_commit"],
                "rederived": {
                    "software_dispatches": len(dispatches),
                    "cross_episode_dispatches": len(cross),
                    "cross_episode_actions": [
                        f"{e['action']['chunk_id']}:{e['action']['ordinal']} in episode {e['episode']}"
                        for e in cross
                    ],
                    "policy_resets": len(resets),
                    "actions_removed_by_resets": sum(
                        len(e.get("removed_actions", [])) for e in resets
                    ),
                },
                "producer_measurements": {
                    "software_dispatches": measured.get("software_dispatches"),
                    "origin_episode_mismatches": measured.get("origin_episode_mismatches"),
                },
                "agrees": measured.get("software_dispatches") == len(dispatches)
                and measured.get("origin_episode_mismatches") == len(cross),
                "robot_task_outcome": run.get("provenance", {}).get("robot_task_outcome"),
            }
        )
    result = {
        "schema": "nisayon.temporal-integration.upstream-control-readback.v1",
        "readback_sha256": hashlib.sha256(Path(argv[1]).read_bytes()).hexdigest(),
        "extractions": len(readback["extractions"]),
        "extraction_file_digests_matching_packet": extraction_matches,
        "mismatched_files": mismatched_files,
        "runs": runs,
        "all_runs_agree": all(r["agrees"] for r in runs),
        "reading": "the affected source dispatches one action of the previous episode's chunk as the first action of the next episode; the upstream fix and the conventional reset dispatch none; the drained-queue variants dispatch every action in its own episode; these are software dispatch counts from scripted doubles, not robot outcomes",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "upstream-control-readback.json").write_text(json.dumps(result, indent=2) + "\n")
    for r in runs:
        print(
            f"{r['assignment_id']}: dispatches {r['rederived']['software_dispatches']} cross-episode {r['rederived']['cross_episode_dispatches']} {r['rederived']['cross_episode_actions']} agrees {r['agrees']}"
        )
    print(f"extractions matching packet: {extraction_matches} of {len(readback['extractions'])}")
    return 0 if result["all_runs_agree"] and not mismatched_files else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
