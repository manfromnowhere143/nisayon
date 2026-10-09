"""Freeze the complete A1 pilot inputs, effective config, limits, and output schema."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import psutil
import robomimic
import robomimic.algo.algo as AlgoSource
import robomimic.algo.bc as BCSource
import robomimic.config.base_config as BaseConfigSource
import robomimic.config.bc_config as BCConfigSource
import robomimic.scripts.train as TrainSource
import robomimic.utils.dataset as DatasetSource
import robomimic.utils.file_utils as FileUtilsSource
import robomimic.utils.obs_utils as ObsUtils
import robomimic.utils.train_utils as TrainUtilsSource
import torch
from robomimic.algo import algo_factory
from robomimic.config import config_factory

from nisayon.engine.io import write_json

DRIVER = Path("scripts/experiments/run_a1_training_pilot.py")
MONITOR = Path("scripts/experiments/monitor_a1_training_pilot.py")
DRIVER_SPEC = importlib.util.spec_from_file_location("run_a1_training_pilot", DRIVER)
driver = importlib.util.module_from_spec(DRIVER_SPEC)
DRIVER_SPEC.loader.exec_module(driver)


class FreezeError(RuntimeError):
    """The pilot contract cannot truthfully be frozen."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _relative_source(module: Any) -> Path:
    return Path(module.__file__).resolve().relative_to(Path.cwd().resolve())


def runtime_record() -> dict[str, Any]:
    sources = [
        DRIVER,
        MONITOR,
        Path("pyproject.toml"),
        Path("uv.lock"),
        _relative_source(TrainSource),
        _relative_source(TrainUtilsSource),
        _relative_source(DatasetSource),
        _relative_source(FileUtilsSource),
        _relative_source(ObsUtils),
        _relative_source(AlgoSource),
        _relative_source(BCSource),
        _relative_source(BaseConfigSource),
        _relative_source(BCConfigSource),
    ]
    return {
        "versions": {
            "python": platform.python_version(),
            "robomimic": robomimic.__version__,
            "torch": torch.__version__,
            "numpy": np.__version__,
            "h5py": h5py.__version__,
            "psutil": psutil.__version__,
            "robosuite": importlib.metadata.version("robosuite"),
            "mujoco": importlib.metadata.version("mujoco"),
        },
        "source_sha256": {str(path): sha256(path) for path in sources},
        "driver_sha256": sha256(DRIVER),
        "monitor_sha256": sha256(MONITOR),
        "platform": platform.platform(),
    }


def model_evidence(config_document: dict[str, Any]) -> dict[str, Any]:
    config = config_factory(algo_name="bc", dic=config_document)
    ObsUtils.initialize_obs_utils_with_config(config)
    torch.set_num_threads(2)
    torch.manual_seed(config.train.seed)
    shapes = {
        "object": [10],
        "robot0_eef_pos": [3],
        "robot0_eef_quat": [4],
        "robot0_gripper_qpos": [2],
    }
    model = algo_factory(
        algo_name="bc",
        config=config,
        obs_key_shapes=shapes,
        ac_dim=7,
        device=torch.device("cpu"),
    )
    state = model.serialize()
    return {
        "model_class": type(model).__name__,
        "parameters": sum(parameter.numel() for parameter in model.nets.parameters()),
        "serialized_tensor_bytes": sum(
            tensor.numel() * tensor.element_size() for tensor in state.values()
        ),
        "state_entries": len(state),
        "device": "cpu",
        "optimizer_updates": 0,
        "simulator_constructed": False,
    }


def assemble_contract(
    *,
    implementation_commit: str,
    dataset: dict[str, Any],
    inventory: dict[str, Any],
    runtime: dict[str, Any],
    config: dict[str, Any],
    model: dict[str, Any],
    output_root: str,
    temporary_root: str,
) -> dict[str, Any]:
    training_demos = [item["id"] for item in inventory["membership"]["demos"]]
    if len(training_demos) != inventory["membership"]["demo_count"]:
        raise FreezeError("inventory demo list and count differ")
    return {
        "schema": "nisayon.a1-training-contract.v1",
        "case": "a1-feasibility-001",
        "frozen_at": datetime.now(UTC).isoformat(),
        "frozen_before": "optimizer update 1, any pilot checkpoint, and any output under the assigned output root",
        "authority": "Daniel Wahnich's bounded A1 CPU-only normalized-training pilot under Opus amendment v1.2; exactly 100 total optimizer updates including retries; no rollout, GPU, paid compute, hardware, reserved access, publication or push",
        "implementation_commit": implementation_commit,
        "amendment": {
            "path": "docs/evaluation/results/a1-pilot-001/a1-amendment.v1.2.json",
            "sha256": "e79c857d5db7bbad895f7e1fc60710fc17cb208497e0a7723749aad2a0df1346",
        },
        "dataset": {
            **dataset,
            "training_demos": training_demos,
            "training_demo_count": inventory["membership"]["demo_count"],
            "training_frames": inventory["membership"]["total_frames"],
            "training_sequence_starts": inventory["membership"][
                "sequence_starts_with_declared_padding"
            ],
            "filter_key": None,
            "validation_filter_key": None,
            "masks_recorded_not_used": inventory["membership"]["masks"],
            "inventory_path": "artifacts/a1-feasibility-001/dataset-inventory-v1.2.json",
            "inventory_sha256": inventory["identity"]["sha256"],
            "environment_version_declared": "1.5.1",
            "held_robosuite_version": "1.4.1",
            "simulator_compatibility": "unresolved and not tested by this offline pilot",
        },
        "robomimic_config": config,
        "robomimic_config_sha256": canonical_sha256(config),
        "runtime": runtime,
        "model_preflight": model,
        "normalization": {
            "statistics_population": "all 200 declared training demos and all 9666 observation rows",
            "statistics_formula": "unchanged robomimic 0.3.0 float32 per-trajectory means and squared deviations, parallel population merge, std=sqrt(M2/n)+1e-3",
            "training_override": "broadcast (x-mean)/std over arbitrary leading dimensions only while SequenceDataset builds its cached normalized items",
            "single_application": "TrainUtils.run_epoch receives obs_normalization_stats=None; first-batch raw, cached and learner arrays must establish one application and reject a double application before update 1",
            "inference_path": "unmodified robomimic policy_from_checkpoint and RolloutPolicy statistics binding; reload only, no policy action",
        },
        "workload": {
            "optimizer_updates_assigned_total": 100,
            "optimizer_updates_consumed_before": 0,
            "training_invocations_authorized": 1,
            "automatic_retry": False,
            "epochs": 1,
            "batches": 100,
            "batch_size": 100,
            "sequence_length": 10,
            "sampled_sequence_examples": 10000,
            "loader_batches_per_complete_drop_last_pass": 96,
            "note": "the pinned 100-step epoch consumes 96 drop-last batches, then the first four batches of a second shuffled iterator; every assignment is retained",
            "stop": "after update 100 or first non-finite logged value, non-finite parameter, prohibited operation, resource guard, or identity mismatch",
        },
        "execution_environment": {
            "CUDA_VISIBLE_DEVICES": "",
            "PYTORCH_ENABLE_MPS_FALLBACK": "0",
            "OMP_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "VECLIB_MAXIMUM_THREADS": "2",
            "NUMEXPR_NUM_THREADS": "2",
            "PYTHONHASHSEED": "0",
            "WANDB_MODE": "disabled",
            "HF_HUB_OFFLINE": "1",
            "TMPDIR": temporary_root,
        },
        "limits": {
            "maximum_outer_wall_seconds": 1200,
            "maximum_internal_wall_seconds": 1100,
            "maximum_process_cpu_seconds": 1800,
            "maximum_process_rss_bytes": 4294967296,
            "maximum_temporary_bytes": 201326592,
            "maximum_durable_output_bytes": 16777216,
            "maximum_precheckpoint_telemetry_bytes": 4194304,
            "maximum_checkpoint_bytes": 12582912,
            "minimum_free_disk_bytes": 5368709120,
            "monitor_sample_interval_seconds": 0.1,
            "known_measurement_limit": "discrete RSS and filesystem samples do not bound unseen peaks",
        },
        "outputs": {
            "root": output_root,
            "temporary_root": temporary_root,
            "checkpoint": f"{output_root}/model.pth",
            "updates": f"{output_root}/updates.jsonl",
            "first_batch_arrays": f"{output_root}/first-batch.npz",
            "statistics_arrays": f"{output_root}/normalization-stats.npz",
            "report": f"{output_root}/report.json",
            "resource_monitor": f"{output_root}/resource-monitor.json",
            "retention": "inference checkpoint plus all telemetry under 16 MiB; no optimizer or RNG state; partial and failure outputs are retained",
        },
        "checkpoint": {
            "selection": "the sole checkpoint after update 100 and epoch 1; no loss or rollout selection",
            "kind": "inference only",
            "held_family_checkpoint_bytes": 7959022,
            "estimated_parameter_tensor_bytes": model["serialized_tensor_bytes"],
            "reserved_maximum_bytes": 12582912,
            "omitted": ["optimizer state", "random-number-generator state"],
            "reload": "policy_from_checkpoint on CPU; compare state and statistics; instantiate no environment and request no action",
        },
        "guards": {
            "network": "socket connections fail closed",
            "environment": "create_env_from_metadata fails closed",
            "rollout": "run_rollout and RolloutPolicy.__call__ fail closed",
            "machine": "parent monitor terminates the process group on wall, CPU, RSS, temporary, durable or free-disk violation",
            "device": "CPU object and CPU parameters asserted before update 1",
        },
        "outcome_schema": {
            "assigned_executed_unresolved_updates": True,
            "per_update_losses_timestamps_assignments": True,
            "first_batch_raw_cached_learner_arrays": True,
            "statistics_and_checkpoint_identity": True,
            "parameter_change_and_reload": True,
            "failures_cancellations_missing_records": True,
            "measured_fixed_per_update_save_reload_costs": True,
        },
        "claim_ceiling": {
            "can_test": [
                "official-object permission and custody",
                "offline data and implementation compatibility",
                "effective normalized training",
                "checkpoint reloadability",
                "bounded local resource feasibility",
            ],
            "cannot_test": [
                "simulator compatibility",
                "policy competence",
                "task outcome",
                "confirmed repair",
                "comparative advantage",
                "the original external-incident objective",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--dataset-bytes", type=int, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--custody-receipt-sha256", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--temporary-root", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.out.exists() or args.out.is_symlink():
        raise SystemExit("refusing to overwrite a frozen training contract")
    if args.dataset.is_symlink() or not args.dataset.is_file():
        raise SystemExit("dataset is absent, non-regular, or a symlink")
    if (
        args.dataset.stat().st_size != args.dataset_bytes
        or sha256(args.dataset) != args.dataset_sha256
    ):
        raise SystemExit("dataset differs from the accepted identity")
    if sha256(args.inventory) != args.inventory_sha256:
        raise SystemExit("dataset inventory digest differs")
    inventory = json.loads(args.inventory.read_text())
    if not inventory["completed"] or not inventory["compatibility"]["offline_contract_passed"]:
        raise SystemExit("dataset inventory did not pass the offline contract")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise SystemExit("worktree must be clean before freezing the contract")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != args.implementation_commit:
        raise SystemExit("implementation commit must be the current clean HEAD")
    for path in (Path(args.output_root), Path(args.temporary_root)):
        if path.exists() or path.is_symlink():
            raise SystemExit(f"frozen run path already exists: {path}")

    config = driver.make_robomimic_config(str(args.dataset), args.output_root)
    contract = assemble_contract(
        implementation_commit=args.implementation_commit,
        dataset={
            "path": str(args.dataset),
            "bytes": args.dataset_bytes,
            "sha256": args.dataset_sha256,
            "custody_receipt_sha256": args.custody_receipt_sha256,
        },
        inventory={**inventory, "identity": {"sha256": args.inventory_sha256}},
        runtime=runtime_record(),
        config=config,
        model=model_evidence(config),
        output_root=args.output_root,
        temporary_root=args.temporary_root,
    )
    write_json(args.out, contract)
    print(
        json.dumps(
            {
                "contract": str(args.out),
                "sha256": sha256(args.out),
                "config_sha256": contract["robomimic_config_sha256"],
                "model_preflight": contract["model_preflight"],
                "optimizer_updates": 0,
                "simulator_constructed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
