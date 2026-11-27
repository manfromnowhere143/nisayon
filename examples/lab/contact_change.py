"""Execute one declared contact change and independently inspect its sealed packet."""

import argparse
import json
import time
from pathlib import Path

from nisayon.lab import execute, experiment, inspect_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unchanged", action="store_true")
    parser.add_argument("--require-supported", action="store_true")
    args = parser.parse_args()
    parameters = experiment()["spec"]["parameters"]
    if args.unchanged:
        parameters["candidate_friction"] = parameters["reference_friction"]
    specification = experiment(parameters)
    started = time.perf_counter()
    result = execute(specification, args.out)
    packet = inspect_packet(args.out, expected_sha256=result["packet_sha256"])
    verdict = packet["result"]["qualification"]["verdict"]
    print(
        json.dumps(
            {
                "experiment_id": specification["experiment_id"],
                "packet_sha256": packet["packet_sha256"],
                "execution": result["status"],
                "verdict": verdict,
                "deployment_decision": packet["result"]["qualification"]["deployment_decision"],
                "elapsed_s": time.perf_counter() - started,
                "scope": "Four prescribed native simulations; declared displacement relation only.",
            },
            indent=2,
        )
    )
    if result["status"] != "complete":
        raise SystemExit(2)
    if args.require_supported and verdict != "supported":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
