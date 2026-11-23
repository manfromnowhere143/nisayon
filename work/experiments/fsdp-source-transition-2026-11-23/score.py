"""Independent contract scoring over complete two-rank native observations."""

import argparse
import hashlib
import json
from pathlib import Path


def score(root, expected_cases, expected_source=None, expected_probe=None):
    root = Path(root)
    failures, unresolved, seen = [], [], set()
    observations = []
    for rank in (0, 1):
        path = root / f"rank-{rank}.json"
        if not path.is_file():
            unresolved.append(f"rank {rank}: missing observation")
            continue
        data = json.loads(path.read_text())
        observations.append(
            {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
        if data["rank"] != rank or data["world_size"] != 2 or data["device"] != "cpu":
            unresolved.append(f"rank {rank}: incorrect environment/identity")
        if expected_source and data["source_sha256"] != expected_source:
            unresolved.append(f"rank {rank}: wrong source")
        if expected_probe and data["probe_sha256"] != expected_probe:
            unresolved.append(f"rank {rank}: wrong probe")
        if len(data["rows"]) != expected_cases:
            unresolved.append(f"rank {rank}: incomplete assigned cases")
        for row in data["rows"]:
            key = (rank, row["case"])
            if key in seen or not 0 <= row["case"] < expected_cases:
                unresolved.append(f"{key}: duplicated/unknown case")
            seen.add(key)
            if row["status"] != "executed":
                unresolved.append(
                    f"{key}: native error {row.get('error_type')}: {row.get('error')}"
                )
                continue
            errors = []
            assignments = row["assignments"]
            if len(assignments) != 1 or assignments[0].get("assign") is not True:
                errors.append("actual assignment missing or repeated")
            elif row["owned"] and assignments[0]["source_keys"]:
                errors.append("owned source retained before assignment")
            if row["owned"] and row.get("source_keys_after"):
                errors.append("owned source retained after return")
            if not row["owned"] and not row["borrowed_unchanged"]:
                errors.append("borrowed dictionary changed")
            if (
                not row["returned_original_model"]
                or not row["state_keys_match"]
                or not row["value_checks"]
            ):
                errors.append("loaded model/state incomplete")
            for value in row["value_checks"]:
                if not (
                    value["exact_values"]
                    and value["shape"] == value["expected_shape"]
                    and value["dtype"] == value["expected_dtype"]
                    and value["device"] == "cpu"
                    and value["sharded"] == value["expected_sharded"]
                ):
                    errors.append("incorrect value/placement: " + value["name"])
            if errors:
                failures.append({"rank": rank, "case": row["case"], "errors": errors})
    if len(seen) != 2 * expected_cases:
        unresolved.append("two-rank assignment is incomplete")
    return {
        "status": "unresolved"
        if unresolved
        else "rejected"
        if failures
        else "supported_cpu_loader_contract",
        "expected_cases_per_rank": expected_cases,
        "rank_observations": len(seen),
        "failures": failures,
        "unresolved": unresolved,
        "observations": observations,
        "automatic_acceptance": False,
        "gpu_offload_memory_claim": "not_tested",
        "full_accelerate_integration": "not_tested",
        "complete_cost_advantage": "unknown",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--cases", type=int, required=True)
    parser.add_argument("--source")
    parser.add_argument("--probe")
    args = parser.parse_args()
    print(json.dumps(score(args.root, args.cases, args.source, args.probe), indent=2))
