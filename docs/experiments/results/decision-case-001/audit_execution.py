"""Read retained DC01 inputs fieldwise; no new physics or acceptance decision."""

import copy
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.store import verify_execution

STORE = Path("artifacts/engine-integration-001/decision-case-001/execution")
OUT = Path("artifacts/engine-integration-001/decision-case-001/extended-audit.json")


def first_rows(run_id):
    with gzip.open(STORE / (run_id + ".jsonl.gz"), "rt") as stream:
        return json.loads(next(stream)), json.loads(next(stream))


def main():
    bundle = json.loads((STORE / "bundle.json").read_text())
    integrity = verify_execution(bundle, STORE)
    pairs = []
    for a, b in zip(bundle["runs"][::2], bundle["runs"][1::2], strict=True):
        ah, ar = first_rows(a["id"])
        bh, br = first_rows(b["id"])
        configs = [copy.deepcopy(r["configuration"]) for r in (a, b)]
        for cfg in configs:
            cfg["deployment"].pop("controller_target")
        states = [copy.deepcopy(h["reset"]) for h in (ah, bh)]
        for state in states:
            state["controller"].pop("initial_joint")
        checks = {
            **{
                name: a[name] == b[name]
                for name in (
                    "seed",
                    "case_id",
                    "code_sha256",
                    "dependencies_sha256",
                    "policy_sha256",
                    "execution_identity_sha256",
                )
            },
            "configuration_except_target": configs[0] == configs[1],
            "recorded_state_except_target": states[0] == states[1],
            **{
                name: ah[name] == bh[name]
                for name in (
                    "numpy_rng",
                    "torch_rng",
                    "python_rng",
                    "policy_reset",
                )
            },
            **{
                name: ar[name] == br[name]
                for name in (
                    "observation",
                    "policy_state_before",
                    "intended_action",
                    "executed_action",
                )
            },
            "XML": file_digest(STORE / (a["id"] + ".xml"))
            == file_digest(STORE / (b["id"] + ".xml")),
        }
        pairs.append(
            {"seed": a["seed"], "checks": checks, "all_recorded_inputs_match": all(checks.values())}
        )
    old_path = Path(
        "artifacts/development-ablation-001/D01-gripper-sign/A/diagnostic/execution/reference-0.run.json"
    )
    old = json.loads(old_path.read_text())
    new = bundle["runs"][0]
    comparison = {}
    for key in ("cube_height_m", "executed_action", "action_sim_time_s", "next_sim_time_s"):
        delta = np.asarray([r[key] for r in old["trace"]]) - np.asarray(
            [r[key] for r in new["trace"]]
        )
        comparison[key] = {
            "exactly_equal": bool(np.all(delta == 0)),
            "max_abs_difference": float(np.max(np.abs(delta))),
        }
    result = {
        "observed_at": datetime.now(UTC).isoformat(),
        "scope": "Post-run input audit and historical comparison; not a new pre-outcome freeze",
        "bundle_sha256": file_digest(STORE / "bundle.json"),
        "integrity": integrity,
        "pairs": pairs,
        "historical_restored_comparison": {
            "source": str(old_path),
            "sha256": file_digest(old_path),
            "steps": [len(old["trace"]), len(new["trace"])],
            "outcomes": [old["task_outcome"], new["task_outcome"]],
            "quantities": comparison,
            "reading": "Explicit symmetric refresh is not asserted bitwise equal to the historical omitted-setting run. These measured differences do not regrade that record.",
        },
        "known_nested_run_walls_s": sum(r["costs"][0]["value"] for r in bundle["runs"]),
        "timing_boundary": "Run walls include reset, inference, simulation and trace writes; simulator-step-only wall was not separately measured.",
        "omitted_state": [
            "all controller caches",
            "MuJoCo internal solver caches",
            "all observable buffers",
            "OS scheduling",
        ],
    }
    write_json(OUT, result)
    print(json.dumps(result, indent=2))
    assert integrity["status"] == "verified"
    assert all(p["all_recorded_inputs_match"] for p in pairs)


if __name__ == "__main__":
    main()
