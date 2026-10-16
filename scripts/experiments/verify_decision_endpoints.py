"""Read back N027's fixed public rollout packet; never execute a robot policy.

The reference experiment and discordance calculation are from Jun Ji et al.,
benchmark-ranking-determinacy v2.0.0. Attribution and upstream MIT terms:
docs/experiments/results/decision-endpoint-001/UPSTREAM_LICENSE.txt.
The native success predicates are from ManiSkill 3.0.1 (Apache-2.0).
This incident-specific reader is not an independently designed experiment.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

PROTOCOL_SHA = "67bcefce0de89bedfc368b55b8fc8ad6161279dd951df3e69d3d381cae3fa89d"
STARTS = [731250001, 893460001, 1135790001, 1579130001]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def verdict(lower: float, upper: float) -> str:
    return "joint" if lower > 0 else "cartesian" if upper < 0 else "abstain"


def compare_native(actual, expected, tolerance: float) -> float:
    """Require exact structure/counts, with the declared tolerance for floats."""
    require(type(actual) is type(expected), "Native result type differs from release")
    if isinstance(expected, dict):
        require(actual.keys() == expected.keys(), "Native result keys differ")
        return max(compare_native(actual[k], v, tolerance) for k, v in expected.items())
    if isinstance(expected, list):
        require(len(actual) == len(expected), "Native result length differs")
        return max(compare_native(a, b, tolerance) for a, b in zip(actual, expected, strict=True))
    if isinstance(expected, float):
        error = abs(actual - expected)
        require(error <= tolerance, "Native result exceeds declared numerical tolerance")
        return error
    require(actual == expected, "Native nonfloating result differs from release")
    return 0.0


def verify(args, report: dict) -> None:
    import numpy as np
    from scipy.stats import binomtest

    require(digest(args.protocol) == PROTOCOL_SHA, "N027 protocol changed")
    protocol = read(args.protocol)
    require(
        digest(args.protocol.parent / "DECISION.md") == protocol["decision_sha256"],
        "N027 decision changed",
    )
    require(platform.python_version() == "3.11.16", "Unexpected readback Python")
    for name, version in {"numpy": "1.26.4", "scipy": "1.12.0"}.items():
        require(importlib.metadata.version(name) == version, f"Unexpected {name}")
    source = args.artifacts / "source"
    packet = source / protocol["source_prefix"]
    files = {item["path"]: item for item in protocol["source_files"]}
    found = {str(p.relative_to(source)) for p in packet.rglob("*") if p.is_file()}
    require(found == set(files), "Missing or extra source packet file")
    source_before = {}
    for relative, expected in files.items():
        data = (source / relative).read_bytes()
        blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        require(len(data) == expected["bytes"], f"Source size: {relative}")
        require(blob == expected["git_blob_sha1"], f"Source Git binding: {relative}")
        source_before[relative] = hashlib.sha256(data).hexdigest()
    receipts = read(args.artifacts / "packet-sources.json")
    require(len(receipts) == len(files), "Source receipt inventory")
    for receipt in receipts:
        relative = str(Path(receipt["path"]).relative_to(source))
        require(source_before[relative] == receipt["sha256"], "Download SHA mismatch")
    frozen = read(packet / "FROZEN_RUNTIME_AMENDMENT_V2.json")
    for name, expected in frozen["files"].items():
        require(digest(packet / name) == expected, f"Original source freeze: {name}")
    require(
        digest(packet / "FROZEN_BEFORE_EXECUTION.json")
        == frozen["original_frozen_manifest_sha256"],
        "Original freeze binding",
    )
    environment = read(packet / "prior_reference/ENVIRONMENT.json")
    predicates = read(args.artifacts / "native-predicate-sources.json")
    require(len(predicates) == 3, "Predicate source inventory")
    for row in predicates:
        suffix = row["url"].split("a4a4f9272ad64b1564035874b605ceb687b63ed8/")[1]
        installed = environment["source_files"][".venv-windows-ms3/Lib/site-packages/" + suffix]
        require(digest(Path(row["path"])) == installed["sha256"], f"Predicate: {suffix}")
    config = read(args.artifacts / "native-predicate-config.json")
    require(digest(Path(config["path"])) == config["sha256"], "Native configuration changed")
    config_tree = ast.parse(Path(config["path"]).read_text())
    assignment = next(
        node
        for node in config_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "PICK_CUBE_CONFIGS" for t in node.targets)
    )
    panda_node = next(
        value
        for key, value in zip(assignment.value.keys, assignment.value.values, strict=True)
        if ast.literal_eval(key) == "panda"
    )
    panda = ast.literal_eval(panda_node)
    require(panda["goal_thresh"] == 0.025, "Unexpected native Panda goal threshold")
    report["predicate_source_binding"] = {
        "runtime_file_hashes_matched": 3,
        "config_sha256": config["sha256"],
        "configuration_limit": config["limit"],
    }
    checkpoint_sources = read(args.artifacts / "checkpoint-metadata-sources.json")
    checkpoint_ids = {}
    for task in protocol["tasks"]:
        live = args.artifacts / f"native-hf-{task}.json"
        receipt = next(x for x in checkpoint_sources if Path(x["path"]) == live)
        require(digest(live) == receipt["sha256"], "Checkpoint metadata changed")
        require(environment["public_model_revision"] in receipt["url"], "Model revision")
        archived_name = (
            "hf_pickcube_tree.json" if task == "PickCube-v1" else "hf_pushcube_tree.json"
        )
        archived = read(packet / "prior_reference" / archived_name)
        for mode in protocol["modes"]:
            name = f"demos/{task}/rl/ppo_{mode}_ckpt.pt"
            public_id = next(x["lfs"]["oid"] for x in read(live) if x["path"] == name)
            old_id = next(x["lfs"]["oid"] for x in archived if x["path"] == name)
            require(public_id == old_id, "Published checkpoint metadata disagreement")
            checkpoint_ids[task, mode] = public_id

    original = read(packet / "RESULTS.json")
    replay = args.artifacts / "upstream-replay/confirmatory"
    replay_changes = [
        str(p.relative_to(packet))
        for p in packet.rglob("*")
        if p.is_file() and digest(p) != digest(replay / p.relative_to(packet))
    ]
    require(set(replay_changes) <= {"RESULTS.json", "RESULTS.md"}, "Native input changed")
    native_error = compare_native(
        read(replay / "RESULTS.json"), original, protocol["numeric_tolerance"]
    )
    report["native_replay"] = {
        "exact_structure_counts_and_nonfloating_values": True,
        "max_floating_abs_error": native_error,
        "numeric_tolerance": protocol["numeric_tolerance"],
        "changed_copy_files": replay_changes,
        "script_sha256": digest(packet / "analyze_portable.py"),
    }

    sequences, cells, pairing = {}, [], []
    state_checks = 0
    recorded_execution_seconds = 0.0
    report["predicate_margins"] = {}
    raw_names = set()
    for task in protocol["tasks"]:
        old_paths = sorted((packet / "prior_reference/full_grid").glob(task + "*.json"))
        require(len(old_paths) == 10, "Prior full-grid inventory")
        if task == "PickCube-v1":
            old_paths += [
                packet / "prior_reference" / f"pilot_{m}_nominal.json" for m in ["joint", "ee"]
            ]
        old = {canonical(e["initial_state"]) for p in old_paths for e in read(p)["episodes"]}
        seen = set()
        for batch, start in enumerate(STARTS):
            reference = None
            for mode in protocol["modes"]:
                for setting in protocol["settings"]:
                    name = f"{task}_{mode}_{setting}_batch{batch}.json"
                    raw_names.add(name)
                    rec = read(packet / "raw_v2" / name)
                    expected = {
                        "task": task,
                        "mode": mode,
                        "batch": batch,
                        "setting": setting,
                        "num_scenes": 256,
                        "steps": 100,
                        "scene_seed_vector_start": start,
                        "sim_freq": 100,
                        "control_freq": 20,
                        "plan_sha256": frozen["files"]["PLAN.md"],
                        "evaluator_sha256": frozen["files"]["run_confirmatory_v2.py"],
                        "frozen_manifest_sha256": digest(
                            packet / "FROZEN_RUNTIME_AMENDMENT_V2.json"
                        ),
                        "checkpoint_sha256": checkpoint_ids[task, mode],
                        "platform": environment["platform"],
                    }
                    require(all(rec[k] == v for k, v in expected.items()), f"Metadata: {name}")
                    require(
                        rec["versions"]
                        == {
                            k: environment["versions"][k]
                            for k in ["mani_skill", "sapien", "torch", "numpy", "gymnasium"]
                        },
                        f"Runtime versions: {name}",
                    )
                    gain = {"gain_half": 0.5, "gain_double": 2.0}.get(setting, 1.0)
                    force = {"force_half": 0.5, "force_double": 2.0}.get(setting, 1.0)
                    nominal = {"stiffness": 1000.0, "damping": 100.0, "force_limit": 100.0}
                    applied = {
                        "stiffness": 1000 * gain,
                        "damping": 100 * gain,
                        "force_limit": 100 * force,
                    }
                    require(
                        rec["nominal_gains"] == nominal and rec["applied_gains"] == applied,
                        f"Gains: {name}",
                    )
                    episodes = rec["episodes"]
                    require(len(episodes) == 256, f"Episode inventory: {name}")
                    seq = np.asarray([e["success_sequence"] for e in episodes])
                    require(
                        seq.shape == (256, 100) and np.isin(seq, [0, 1]).all(), f"Outcomes: {name}"
                    )
                    states = canonical([e["initial_state"] for e in episodes])
                    full = canonical(rec["initial_state_dict"])
                    if reference is None:
                        reference = (states, full)
                        for e in episodes:
                            s = e["initial_state"]
                            projection = canonical(
                                {
                                    "qpos": s["qpos"],
                                    "cube_pose": s["cube_state"][:7],
                                    "goal_pose": s["goal_state"][:7],
                                }
                            )
                            require(
                                projection not in seen and projection not in old,
                                "Repeated or exploratory initial state",
                            )
                            seen.add(projection)
                    require((states, full) == reference, f"Physical pairing: {name}")
                    for slot, episode in enumerate(episodes):
                        require(
                            episode["scene_slot"] == slot
                            and episode["requested_reset_seed"] == start + slot,
                            f"Slot identity: {name}",
                        )
                        for state_key in ["initial_state", "state_at_50", "state_at_100"]:
                            state = episode[state_key]
                            for key, width in {
                                "qpos": 9,
                                "qvel": 9,
                                "cube_state": 13,
                                "goal_state": 13,
                            }.items():
                                require(
                                    len(state[key]) == width and np.isfinite(state[key]).all(),
                                    f"State values: {name}/{slot}/{state_key}/{key}",
                                )
                        for step in [50, 100]:
                            state = episode[f"state_at_{step}"]
                            cube = np.asarray(state["cube_state"][:3], dtype=np.float32)
                            goal = np.asarray(state["goal_state"][:3], dtype=np.float32)
                            if task == "PushCube-v1":
                                margins = [
                                    float(np.float32(0.1) - np.linalg.norm(cube[:2] - goal[:2])),
                                    float(np.float32(0.025) - cube[2]),
                                ]
                                success = all(m > 0 for m in margins)
                            else:
                                speed = np.max(
                                    np.abs(np.asarray(state["qvel"][:-2], dtype=np.float32))
                                )
                                margins = [
                                    float(np.float32(0.025) - np.linalg.norm(cube - goal)),
                                    float(np.float32(0.2) - speed),
                                ]
                                success = all(m >= 0 for m in margins)
                            require(
                                int(success) == int(seq[slot, step - 1]),
                                f"State-derived success: {name}/{slot}/{step}",
                            )
                            key = f"{task}/step{step}"
                            old_margin = report["predicate_margins"].get(key, [float("inf")] * 2)
                            report["predicate_margins"][key] = [
                                min(a, abs(b)) for a, b in zip(old_margin, margins, strict=True)
                            ]
                            state_checks += 1
                    sequences[task, mode, setting, batch] = seq.astype(int)
                    recorded_execution_seconds += rec["elapsed_seconds"]
                    report["raw_cells_checked"] = len(sequences)
                    report["state_derived_labels_checked"] = state_checks
        require(len(seen) == 1024, "Unique scene inventory")
        pairing.append(
            {
                "task": task,
                "unique_projected_initial_states": len(seen),
                "exploratory_overlap": 0,
                "full_state_matches": True,
            }
        )
    require(raw_names == {p.name for p in (packet / "raw_v2").glob("*.json")}, "Raw inventory")
    for name, sha in frozen["retained_original_raw"].items():
        require(digest(packet / "raw" / name) == sha, "Technical-repeat original binding")
        old, new = read(packet / "raw" / name), read(packet / "raw_v2" / name)
        require(
            all(
                old[k] == new[k] for k in ["initial_state_dict", "initial_observations", "episodes"]
            ),
            "Technical repeat disagrees",
        )
    report["technical_repeat"] = {
        "episodes": 256,
        "identical": True,
        "additional_independent_evidence": False,
    }

    max_error = 0.0
    envelopes = []
    radius = {n: math.sqrt(2 * math.log(40 / 0.05) / n) for n in [4, 1024]}
    for task in protocol["tasks"]:
        for endpoint in protocol["endpoints"]:
            rows = []
            for setting in protocol["settings"]:
                vectors = []
                for mode in protocol["modes"]:
                    seq = np.concatenate([sequences[task, mode, setting, b] for b in range(4)])
                    vectors.append(
                        seq[:, :50].any(axis=1).astype(int) if endpoint == "ever50" else seq[:, 49]
                    )
                a, b = vectors
                diff = a - b
                plus, minus = int((diff == 1).sum()), int((diff == -1).sum())
                confidence = 1 - 2 * protocol["component_tail"]
                pos = binomtest(plus, len(diff)).proportion_ci(confidence, method="exact")
                neg = binomtest(minus, len(diff)).proportion_ci(confidence, method="exact")
                lower, upper = float(pos.low - neg.high), float(pos.high - neg.low)
                estimate = float(diff.mean())
                row = {
                    "task": task,
                    "endpoint": endpoint,
                    "setting": setting,
                    "n": len(diff),
                    "joint_successes": int(a.sum()),
                    "cartesian_successes": int(b.sum()),
                    "joint_only": plus,
                    "cartesian_only": minus,
                    "difference": estimate,
                    "lower": lower,
                    "upper": upper,
                    "verdict": verdict(lower, upper),
                }
                expected = original["results"][task][endpoint]["cells"][setting]
                for key in [
                    "n",
                    "joint_successes",
                    "cartesian_successes",
                    "joint_only",
                    "cartesian_only",
                    "difference",
                    "verdict",
                ]:
                    require(
                        row[key] == expected[key],
                        f"Published count or decision: {task}/{endpoint}/{setting}/{key}",
                    )
                for key in ["lower", "upper"]:
                    error = abs(row[key] - expected[key])
                    max_error = max(max_error, error)
                    require(
                        error <= protocol["numeric_tolerance"], "Published interval disagreement"
                    )
                row["batch_counts"] = [
                    {
                        "batch": i,
                        "joint": int(a[256 * i : 256 * (i + 1)].sum()),
                        "cartesian": int(b[256 * i : 256 * (i + 1)].sum()),
                    }
                    for i in range(4)
                ]
                require(row["batch_counts"] == expected["batch_counts"], "Published batch counts")
                row["batch_mean_differences"] = diff.reshape(4, 256).mean(axis=1).tolist()
                row["hoeffding"] = {
                    str(n): {"lower": max(-1.0, estimate - r), "upper": min(1.0, estimate + r)}
                    for n, r in radius.items()
                }
                cells.append(row)
                rows.append(row)
            lower, upper = min(x["lower"] for x in rows), max(x["upper"] for x in rows)
            expected = original["results"][task][endpoint]["envelope"]
            require(
                abs(lower - expected["lower"]) <= protocol["numeric_tolerance"]
                and abs(upper - expected["upper"]) <= protocol["numeric_tolerance"],
                "Published envelope disagreement",
            )
            envelopes.append(
                {
                    "task": task,
                    "endpoint": endpoint,
                    "lower": lower,
                    "upper": upper,
                    "verdict": verdict(lower, upper),
                    "batch_model_lower": min(x["hoeffding"]["4"]["lower"] for x in rows),
                    "batch_model_upper": max(x["hoeffding"]["4"]["upper"] for x in rows),
                }
            )
    require(state_checks == 40960 and len(cells) == 20, "Incomplete readback")
    require(
        source_before == {name: digest(source / name) for name in files},
        "Original packet changed during analysis",
    )
    report.update(
        status="reproduced_recorded_analysis",
        source_files_verified=len(files),
        source_sha256=source_before,
        source_unchanged=True,
        physical_pairing=pairing,
        checkpoint_hashes={f"{task}/{mode}": sha for (task, mode), sha in checkpoint_ids.items()},
        checkpoint_weights_downloaded=False,
        state_derived_labels_checked=state_checks,
        state_derived_label_disagreements=0,
        raw_cells=len(raw_names),
        recorded_rollouts=20480,
        new_policy_rollouts=0,
        primary_cells=cells,
        endpoint_envelopes=envelopes,
        max_interval_abs_error=max_error,
        hoeffding_radius=radius,
        original_reported_execution_seconds_sum=recorded_execution_seconds,
        interpretation="Conditional arithmetic and source-consistency reproduction. Scene independence is assumed; the four-independent-batch sensitivity changes that premise, not the data. No counterfactual actions, causal controller-only effect, physical replication, or comparative cost advantage.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "nisayon.decision-endpoint.readback.v1",
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "script_sha256": digest(Path(__file__)),
        "protocol_sha256": digest(args.protocol),
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
    }
    try:
        verify(args, report)
    except Exception as exc:
        report.update(
            status="invalid_readback",
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
    report["ended_at"] = datetime.now(UTC).isoformat()
    (args.out / "result.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: report.get(k)
                for k in [
                    "status",
                    "error",
                    "recorded_rollouts",
                    "state_derived_labels_checked",
                    "max_interval_abs_error",
                    "endpoint_envelopes",
                ]
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "reproduced_recorded_analysis" else 1


if __name__ == "__main__":
    raise SystemExit(main())
