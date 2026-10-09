"""Seal the completed A1 v1.2 training evidence without duplicating its checkpoint."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.store import create_manifest, verify_manifest

CASE = "a1-feasibility-001"
SCHEMA = "nisayon.a1-training-execution-seal.v1"
DURABLE_CAP = 16 * 1024**2
UPDATE_BUDGET = 100
TRAINING_RUN_ID = "999a6bfaa52f4eac8d5314ca5e162c46"
EXPECTED_CONTRACT_SHA256 = "12283fa15dd038c5f3c1a8e7722bd8a70eaafd76aa958751cfc64007e7326de8"
EXPECTED_DATASET_SHA256 = "2067777cb8b532e9263dd09fd6448c41cc31224bb27be4a3b734010ae13eb540"
EXPECTED_DATASET_BYTES = 21_084_088
EVALUATION_ROOT = Path("/Users/danielwahnich/workspace/nisayon-fable5")

PILOT_FILES = (
    "checkpoint-reload.json",
    "effective-config.json",
    "first-batch.json",
    "first-batch.npz",
    "model.pth",
    "normalization-stats.json",
    "normalization-stats.npz",
    "report.json",
    "resource-monitor.json",
    "training-contract.json",
    "updates.jsonl",
)

EXECUTION_INPUTS = (
    "phase-start.json",
    "authorization.v1.json",
    "acquisition-protocol.v1.json",
    "acquisition-reservation-v1.2.json",
    "acquisition-delivery-v1.2.json",
    "source-ledger.v1.json",
    "source-ledger.v2.json",
    "dataset-inspection-delivery-v1.2.json",
    "training-contract.v1.json",
    "training-reservation-v1.2.json",
    "execution-delivery-001.json",
    "README.md",
)

EVALUATION_INPUTS = (
    "PILOT_ACCEPTANCE.md",
    "a1-amendment.v1.2.json",
    "pilot-acceptance.v1.json",
    "pilot-verdict-003.json",
)

SOURCE_FILES = (
    "scripts/experiments/acquire_a1_substitute.py",
    "scripts/experiments/verify_a1_substitute.py",
    "scripts/experiments/inspect_a1_dataset.py",
    "scripts/experiments/run_a1_training_pilot.py",
    "scripts/experiments/monitor_a1_training_pilot.py",
    "scripts/experiments/freeze_a1_training_contract.py",
    "scripts/experiments/seal_a1_training_packet.py",
    "tests/engine/test_acquire_a1_substitute.py",
    "tests/engine/test_inspect_a1_dataset.py",
    "tests/engine/test_run_a1_training_pilot.py",
    "tests/engine/test_monitor_a1_training_pilot.py",
    "tests/engine/test_freeze_a1_training_contract.py",
    "pyproject.toml",
    "uv.lock",
)

# Every retained amendment command from the last pre-acquisition resource sample through
# the sole training invocation. Non-zero records are evidence, not discarded attempts.
COMMAND_IDS = (
    "bea8eb900e4443efb522a1c6a66c4536",
    "47ba1b8a5883415180f2ad8a7345aa08",
    "3ff5dee95b3f4a1b8bb97a677ca2f2e7",
    "e72bbf4ddd0e406cb150432648346ae4",
    "d1f7aa2019bf4d9194254257619b6b64",
    "650d9910fef641ebbb0995b5387e1971",
    "42622c2037c04628b97fecbc6ec9f1f0",
    "1f2ff26351b24f4d96547a8f6a920eec",
    "7486b0ce56d04d13b3e75cf6536b6175",
    "2e3f6262432949469e8db422c0f7006a",
    "82a75c26bb3d4fab8a6a68bb702f8937",
    "1f57e72afca8499a91360ae15b273b55",
    "4899b57d951749b0a0af2705052c9ed2",
    "291cbb474430433ea3e6501be7f35896",
    "7bd88478ea4844fca8db67fbc4ed3bf9",
    "715d8cbd5639446296520d7167f47ede",
    "2affeb44a4fc4ecdb8367ec432f57e03",
    "c68b243386e54958b93c3a0b564eb9a0",
    "6fc2a78002a44f019a640d4c3fd44c72",
    "9723fe5508d7438dafe34d847bb9f613",
    "9ceebc3f076d4d99896a972310ca9c1f",
    "4184e6ce3d854fd2891d6e8556b6ab38",
    "c951fd2b58fb4eeaac80beac87889b68",
    "9904dbbb38c74b68834d62d040fe51ac",
    "61793714ef63474e964d7c0de221e45b",
    "8fa448403b9c4058b0680e2c463a75b5",
    "fc7348d1ae264751a174497375d184e4",
    "94ed0fc53ce1406a889f7ffedc1b2d00",
    TRAINING_RUN_ID,
)


class SealError(RuntimeError):
    """The retained bytes do not support a complete A1 training seal."""


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise SealError(f"Expected a JSON object: {path}")
    return value


def _identity(path: Path, *, display: str | None = None) -> dict[str, Any]:
    return {
        "path": display or str(path),
        "bytes": path.stat().st_size,
        "sha256": file_digest(path),
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SealError(message)


def _copy_create(source: Path, target: Path) -> None:
    if not source.is_file() or source.is_symlink():
        raise SealError(f"Packet source must be a regular file: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, target.open("xb") as writer:
        shutil.copyfileobj(reader, writer, length=1024 * 1024)


def _tree_entries(source: Path, destination: str) -> list[tuple[Path, str]]:
    return [
        (path, f"{destination}/{path.relative_to(source).as_posix()}")
        for path in sorted(source.rglob("*"))
        if path.is_file()
    ]


def _read_updates(path: Path) -> list[dict[str, Any]]:
    updates = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise SealError(f"Update line {number} is not an object")
        updates.append(value)
    return updates


def _time_witness(path: Path) -> dict[str, Any]:
    text = path.read_text()

    def value(pattern: str, cast: type[float] | type[int]) -> float | int:
        match = re.search(pattern, text, re.MULTILINE)
        if match is None:
            raise SealError(f"Missing /usr/bin/time witness: {pattern}")
        return cast(match.group(1))

    return {
        "real_seconds": value(r"^real ([0-9.]+)$", float),
        "user_cpu_seconds": value(r"^user ([0-9.]+)$", float),
        "system_cpu_seconds": value(r"^sys ([0-9.]+)$", float),
        "maximum_resident_bytes": value(r"^\s*([0-9]+)\s+maximum resident set size$", int),
        "swaps": value(r"^\s*([0-9]+)\s+swaps$", int),
        "source": _identity(path, display=f"commands/{TRAINING_RUN_ID}/stderr.log"),
    }


def continuation_estimate(report: dict[str, Any], updates: list[dict[str, Any]]) -> dict[str, Any]:
    """Retain a formula and bounded examples; this does not authorize more training."""
    measured = report["costs"]
    step_times = sorted(float(row["attributable_step_seconds"]) for row in updates)
    count = len(step_times)
    median = (
        step_times[count // 2]
        if count % 2
        else (step_times[count // 2 - 1] + step_times[count // 2]) / 2
    )
    maximum = max(step_times)
    step_sum = sum(step_times)
    fixed = float(measured["internal_total_wall_seconds"]) - step_sum
    _require(fixed >= 0, "Measured fixed-time remainder is negative")

    examples = []
    for update_count in (100, 1_000, 5_000):
        examples.append(
            {
                "optimizer_updates": update_count,
                "median_step_estimate_seconds": fixed + update_count * median,
                "maximum_observed_step_estimate_seconds": fixed + update_count * maximum,
            }
        )
    return {
        "formula": "measured non-update remainder + N * observed per-update statistic",
        "measured_non_update_remainder_seconds": fixed,
        "observed_step_seconds": {
            "minimum": min(step_times),
            "median": median,
            "maximum": maximum,
            "sum_for_executed_100": step_sum,
        },
        "bounded_examples": examples,
        "uncertainty": [
            "examples assume the same dataset, architecture, batch and machine state",
            "the maximum is observed, not a statistical upper bound",
            "CPU, memory, thermal, storage and numerical behavior are not projected",
            "no continuation is authorized or executed by this estimate",
        ],
    }


def validate_evidence(root: Path, output: Path) -> dict[str, Any]:
    """Validate all consequential claims before adding a byte to the pilot directory."""
    for name in PILOT_FILES:
        _require((output / name).is_file(), f"Missing pilot evidence: {name}")
    for forbidden in ("seal.json", "artifact-manifest.json", "summary.json", "invocation.json"):
        _require(
            not (output / forbidden).exists(), f"Pilot is already or partly sealed: {forbidden}"
        )

    contract_path = root / "docs/experiments/results/a1-feasibility-001/training-contract.v1.json"
    dataset_path = root / "artifacts/assets/lift/ph/low_dim_v15.hdf5"
    run_root = root / ".nisayon/runs" / TRAINING_RUN_ID
    report = _load(output / "report.json")
    monitor = _load(output / "resource-monitor.json")
    reload = _load(output / "checkpoint-reload.json")
    first_batch = _load(output / "first-batch.json")
    run = _load(run_root / "run.json")
    updates = _read_updates(output / "updates.jsonl")

    _require(file_digest(contract_path) == EXPECTED_CONTRACT_SHA256, "Contract digest differs")
    _require(
        file_digest(output / "training-contract.json") == EXPECTED_CONTRACT_SHA256,
        "Executed contract copy differs",
    )
    _require(dataset_path.stat().st_size == EXPECTED_DATASET_BYTES, "Dataset size differs")
    _require(file_digest(dataset_path) == EXPECTED_DATASET_SHA256, "Dataset digest differs")
    _require(
        run.get("id") == TRAINING_RUN_ID and run.get("returncode") == 0, "Run did not complete"
    )
    _require(run.get("process_status") == "completed", "Run process status differs")
    _require(run.get("scientific_status") == "not_assessed", "Producer run status was promoted")
    tested_source = report["repository"]["head"]
    _require(tested_source == run["git"]["head"], "Report and recorder source differ")
    _require(report["repository"].get("changes") == [], "Training source was dirty")
    _require(run["git"].get("changes") == [], "Recorder source was dirty")
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", tested_source, "HEAD"],
        check=False,
    )
    _require(ancestor.returncode == 0, "Tested training source is not an ancestor of the sealer")

    _require(len(updates) == UPDATE_BUDGET, "Executed update count differs from 100")
    _require(
        [row.get("update") for row in updates] == list(range(1, 101)), "Updates are not 1..100"
    )
    _require(
        all(math.isfinite(float(row["metrics"]["Loss"])) for row in updates),
        "A recorded loss is non-finite",
    )
    _require(
        all(math.isfinite(float(row["metrics"]["Policy_Grad_Norms"])) for row in updates),
        "A recorded gradient norm is non-finite",
    )
    _require(
        all(row.get("all_parameters_finite_after_update") is True for row in updates),
        "A post-update parameter check failed",
    )
    workload = report["workload"]
    _require(workload["updates_executed"] == UPDATE_BUDGET, "Report update count differs")
    _require(workload["all_losses_finite"] is True, "Report marks a non-finite loss")
    _require(workload["parameter_l2_difference"] > 0, "Parameters did not change")
    _require(
        workload["parameter_state_before_sha256"] != workload["parameter_state_after_sha256"],
        "Parameter digests did not change",
    )

    runtime = report["runtime"]
    guards = report["guards"]
    _require(runtime["device"] == "cpu" and runtime["cuda_requested"] is False, "CPU gate differs")
    _require(runtime["rollouts"] == 0, "A rollout occurred")
    _require(runtime["environment_constructions"] == 0, "An environment was constructed")
    _require(runtime["network_attempts"] == 0, "A training network attempt occurred")
    _require(runtime["remote_telemetry"] is False, "Remote telemetry was enabled")
    _require(all(value == 0 for value in guards.values()), "A prohibited operation was attempted")

    normalization = report["normalization"]
    _require(normalization["override_calls"] == 9_666, "Override call count differs")
    _require(normalization["restored_before_training_epoch"] is True, "Override was not restored")
    _require(
        normalization["run_epoch_obs_normalization_stats"] is None, "Loop would normalize twice"
    )
    _require(first_batch["single_application_passed"] is True, "First-batch witness failed")
    for comparison in first_batch["comparisons"].values():
        _require(comparison["dataset_equals_single_formula_bitwise"] is True, "Dataset map differs")
        _require(
            comparison["learner_equals_single_formula_after_float32_bitwise"] is True,
            "Learner input differs from one application",
        )
        _require(
            comparison["learner_equals_double_formula_bitwise"] is False,
            "Double application was not discriminated",
        )
    first_npz = first_batch["npz"]
    _require(
        _identity(output / "first-batch.npz", display=first_npz["path"]) == first_npz,
        "First-batch archive identity differs",
    )

    checkpoint = output / "model.pth"
    _require(checkpoint.stat().st_size == reload["bytes"], "Checkpoint size differs")
    _require(file_digest(checkpoint) == reload["sha256"], "Checkpoint digest differs")
    _require(reload["config_hdf5_normalize_obs"] is True, "Checkpoint normalization flag differs")
    _require(reload["obs_normalization_stats_present"] is True, "Checkpoint statistics are absent")
    _require(
        reload["loaded_model_state_sha256"] == reload["saved_model_state_sha256"],
        "Reloaded parameters differ",
    )
    _require(
        all(all(parts.values()) for parts in reload["loaded_statistics_bitwise_equal"].values()),
        "Reloaded statistics differ",
    )
    _require(reload["policy_action_invocations"] == 0, "Reload invoked an action")

    limits = monitor["limits"]
    _require(monitor["child_returncode"] == 0, "Monitored child failed")
    _require(monitor["terminated_by_monitor"] is False, "Monitor terminated the child")
    _require(monitor["violations"] == [], "A resource guard fired")
    _require(
        monitor["peak_process_tree_rss_bytes"] <= limits["maximum_process_rss_bytes"], "RSS cap"
    )
    _require(monitor["peak_temporary_bytes"] <= limits["maximum_temporary_bytes"], "Temporary cap")
    _require(
        monitor["durable_output_bytes_after_receipt"] <= limits["maximum_durable_output_bytes"],
        "Durable output cap",
    )
    _require(checkpoint.stat().st_size <= limits["maximum_checkpoint_bytes"], "Checkpoint cap")
    _require(
        monitor["minimum_free_disk_bytes_observed"] >= limits["minimum_free_disk_bytes"],
        "Free-disk floor",
    )
    _require(
        monitor["maximum_observed_process_tree_cpu_seconds"]
        <= limits["maximum_process_cpu_seconds"],
        "CPU cap",
    )
    _require(float(run["wall_seconds"]) <= limits["maximum_outer_wall_seconds"], "Wall cap")

    return {
        "contract_path": contract_path,
        "dataset_path": dataset_path,
        "run_root": run_root,
        "report": report,
        "monitor": monitor,
        "reload": reload,
        "first_batch": first_batch,
        "run": run,
        "updates": updates,
        "tested_source": tested_source,
        "time_witness": _time_witness(run_root / "stderr.log"),
    }


def make_adapters(
    evidence: dict[str, Any], inspection: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    report = evidence["report"]
    reload = evidence["reload"]
    updates = evidence["updates"]
    update_identity = _identity(
        Path(report["checkpoint"]["path"]).parent / "updates.jsonl",
        display="updates.jsonl",
    )
    flat_updates = [
        {
            "update": row["update"],
            "loss": row["metrics"]["Loss"],
            "gradient_norm": row["metrics"]["Policy_Grad_Norms"],
            "elapsed_wall_seconds": row["elapsed_wall_seconds"],
            "process_cpu_seconds": row["process_cpu_seconds"],
            "attributable_step_seconds": row["attributable_step_seconds"],
            "all_parameters_finite_after_update": row["all_parameters_finite_after_update"],
        }
        for row in updates
    ]
    return {
        "results/training-membership.json": {
            "schema": "nisayon.a1-training-membership.v1",
            "membership": inspection["membership"],
            "source": "inputs/execution/dataset-inspection-delivery-v1.2.json",
        },
        "results/override-conformance.json": {
            "schema": "nisayon.a1-training-override-conformance.v1",
            "passed": True,
            "synthetic_control": {
                "command_record_id": "4184e6ce3d854fd2891d6e8556b6ab38",
                "source_test": "source/tests/engine/test_run_a1_training_pilot.py",
                "rank_two_fixture_represents_both_B_D_and_T_D": True,
                "scope": "generic numeric and implementation conformance; not task evidence",
            },
            "executed_witness": {
                "override_calls": report["normalization"]["override_calls"],
                "shape_signatures": report["normalization"]["override_shape_signatures"],
                "restored_before_training_epoch": report["normalization"][
                    "restored_before_training_epoch"
                ],
                "first_batch_single_application_passed": evidence["first_batch"][
                    "single_application_passed"
                ],
            },
        },
        "results/training-updates.json": {
            "schema": "nisayon.a1-training-updates-adapter.v1",
            "attempted_updates": UPDATE_BUDGET,
            "completed_updates": len(flat_updates),
            "updates": flat_updates,
            "source": update_identity,
            "derivation": "loss and gradient norm are copied from each raw metrics object; timing and finiteness fields are copied without aggregation",
        },
        "results/parameter-change.json": {
            "schema": "nisayon.a1-parameter-change.v1",
            "before_sha256": report["workload"]["parameter_state_before_sha256"],
            "after_sha256": report["workload"]["parameter_state_after_sha256"],
            "l2_norm_of_difference": report["workload"]["parameter_l2_difference"],
            "source": _identity(
                Path(report["checkpoint"]["path"]).parent / "report.json", display="report.json"
            ),
        },
        "results/reload-witness.json": {
            "schema": "nisayon.a1-checkpoint-reload-witness.v1",
            "loaded": True,
            "stats_bound": reload["obs_normalization_stats_present"],
            "parameters_equal": reload["loaded_model_state_sha256"]
            == reload["saved_model_state_sha256"],
            "statistics_bitwise_equal": reload["loaded_statistics_bitwise_equal"],
            "rollouts": 0,
            "policy_actions": reload["policy_action_invocations"],
            "checkpoint": {
                "bytes": reload["bytes"],
                "sha256": reload["sha256"],
                "kind": reload["kind"],
                "resumable_training_checkpoint": reload["resumable_training_checkpoint"],
            },
            "source": _identity(
                Path(report["checkpoint"]["path"]).parent / "checkpoint-reload.json",
                display="checkpoint-reload.json",
            ),
        },
        "results/current-costs.json": {
            "schema": "nisayon.a1-training-costs.v1",
            "costs": report["costs"],
            "outer_recorder": {
                "wall_seconds": evidence["run"]["wall_seconds"],
                "scope": "parent recorder wall; nested monitor, child and phase times are not added",
            },
            "process_time_witness": evidence["time_witness"],
            "resource_monitor": {
                key: evidence["monitor"][key]
                for key in (
                    "peak_process_tree_rss_bytes",
                    "maximum_observed_process_tree_cpu_seconds",
                    "peak_temporary_bytes",
                    "peak_durable_output_bytes",
                    "durable_output_bytes_after_receipt",
                    "minimum_free_disk_bytes_observed",
                    "sample_count",
                    "measurement_limit",
                )
            },
            "continuation_estimate": continuation_estimate(report, updates),
        },
    }


def _packet_entries(root: Path, evidence: dict[str, Any]) -> list[tuple[Path, str]]:
    result_root = root / "docs/experiments/results/a1-feasibility-001"
    evaluation_result = root / "docs/evaluation/results/a1-pilot-001"
    artifact_root = root / "artifacts/a1-feasibility-001"
    entries: list[tuple[Path, str]] = []
    entries.extend((result_root / name, f"inputs/execution/{name}") for name in EXECUTION_INPUTS)
    entries.extend(
        (evaluation_result / name, f"inputs/evaluation/{name}") for name in EVALUATION_INPUTS
    )
    entries.extend(
        (path, f"inputs/rights/{path.name}")
        for path in sorted((artifact_root / "sources").iterdir())
        if path.is_file()
    )
    for name in (
        "acquisition-receipt-v1.2.json",
        "dataset-inventory-v1.2.json",
        "resource-pre-training-v1.2.json",
    ):
        entries.append((artifact_root / name, f"inputs/private/{name}"))
    for command_id in COMMAND_IDS:
        command_root = root / ".nisayon/runs" / command_id
        for name in ("run.json", "stdout.log", "stderr.log"):
            entries.append((command_root / name, f"commands/{command_id}/{name}"))
    entries.extend((root / name, f"source/{name}") for name in SOURCE_FILES)
    entries.extend(
        _tree_entries(root / "artifacts/a1-pilot-001/execution-001", "zz-history/stopped-pilot")
    )
    destinations = [destination for _, destination in entries]
    _require(len(destinations) == len(set(destinations)), "Duplicate packet destinations")
    for source, _destination in entries:
        _require(source.is_file() and not source.is_symlink(), f"Missing packet input: {source}")
    return entries


def _command_disposition(root: Path) -> dict[str, Any]:
    records = []
    for command_id in COMMAND_IDS:
        path = root / ".nisayon/runs" / command_id / "run.json"
        run = _load(path)
        records.append(
            {
                "id": command_id,
                "label": run["label"],
                "returncode": run.get("returncode"),
                "wall_seconds": run.get("wall_seconds"),
                "started_at": run.get("started_at"),
                "ended_at": run.get("ended_at"),
                "preserved_at": f"commands/{command_id}",
            }
        )
    return {
        "records": records,
        "nonzero_records": [record for record in records if record["returncode"] != 0],
        "unrecorded_preinspection_failure": "a direct documentation check named the absent scripts/validate_docs.py and exited before validation; cost is unmeasured; the corrected check is retained as command 82a75c26bb3d4fab8a6a68bb702f8937",
        "unrecorded_preseal_format_failure": "the first local sealer check passed lint but ruff format --check returned 1 before pytest; ruff format changed only the two new files, and recorded command 27521b8d90944a838c3e38b390abb347 then passed lint, format and three tests; the failed command's wall and CPU cost are unmeasured",
        "historical_stopped_pilot": {
            "preserved_at": "zz-history/stopped-pilot",
            "scope": "all four failures in the formal historical packet, including the two failures named before sealing, plus six pre-freeze interactive web calls whose response bytes and CPU remain unknown",
        },
    }


def seal_in_place(
    output: Path,
    entries: list[tuple[Path, str]],
    *,
    adapters: dict[str, dict[str, Any]],
    invocation: dict[str, Any],
    summary: dict[str, Any],
    source_commit: str,
    dataset_identity: dict[str, Any],
    durable_cap: int = DURABLE_CAP,
) -> dict[str, Any]:
    """Add a content-bound seal to an existing create-only pilot output."""
    _require(output.is_dir(), "Pilot output directory is absent")
    reserved = {"seal.json", "artifact-manifest.json", "summary.json", "invocation.json"}
    targets = (
        [destination for _, destination in entries]
        + list(adapters)
        + [
            "summary.json",
            "invocation.json",
        ]
    )
    _require(len(targets) == len(set(targets)), "Duplicate packet targets")
    for target in [*targets, *reserved]:
        _require(not (output / target).exists(), f"Packet target already exists: {target}")

    projected = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    projected += sum(source.stat().st_size for source, _ in entries)
    projected += sum(
        len(json.dumps(value, indent=2, allow_nan=False)) + 1 for value in adapters.values()
    )
    projected += len(json.dumps(invocation, indent=2, allow_nan=False)) + 1
    projected += len(json.dumps(summary, indent=2, allow_nan=False)) + 1
    _require(projected < durable_cap, "Projected packet exceeds the durable cap before sealing")

    for source, destination in entries:
        _copy_create(source, output / destination)
    for destination, document in adapters.items():
        write_json(output / destination, document)
    write_json(output / "invocation.json", invocation)
    write_json(output / "summary.json", summary)

    members = []
    for path in output.rglob("*"):
        relative = path.relative_to(output).as_posix()
        if path.is_file() and relative not in ("artifact-manifest.json", "seal.json"):
            members.append(relative)
    manifest = create_manifest(output, members)
    before_seal = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    _require(before_seal < durable_cap, "Packet exceeds the durable cap before seal.json")
    seal = {
        "schema": SCHEMA,
        "case": CASE,
        "sealed_at": datetime.now(UTC).isoformat(),
        "source_commit": source_commit,
        "status": "executed_complete_pending_independent_assessment",
        "summary": _identity(output / "summary.json", display="summary.json"),
        "invocation": _identity(output / "invocation.json", display="invocation.json"),
        "artifact_manifest": manifest,
        "dataset_external_to_packet": dataset_identity,
        "retained_logical_bytes_before_seal": before_seal,
        "durable_cap_bytes": durable_cap,
        "absent_by_design": [
            "dataset payload (retained once under the source cap and supplied separately to the assessor)",
            "optimizer state",
            "random-number-generator state",
            "simulator rollout",
            "policy action",
            "task outcome",
            "confirmed repair",
        ],
        "premise": "Integrity binds retained bytes; independent assessment decides correctness and scope.",
    }
    write_json(output / "seal.json", seal)
    members_readback = verify_manifest(output, manifest)
    _require(set(members_readback) == set(members), "Manifest readback changed member identity")
    retained = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    _require(retained <= durable_cap, "Sealed packet exceeds the durable cap")
    return {
        "schema": "nisayon.a1-training-execution-readback.v1",
        "store": str(output.resolve()),
        "seal_sha256": file_digest(output / "seal.json"),
        "manifest_sha256": manifest["sha256"],
        "summary_sha256": file_digest(output / "summary.json"),
        "invocation_sha256": file_digest(output / "invocation.json"),
        "manifest_files": len(members_readback),
        "retained_bytes": retained,
        "durable_cap_bytes": durable_cap,
        "status": seal["status"],
    }


def build_packet(output: Path) -> dict[str, Any]:
    root = Path.cwd().resolve()
    _require(_git(root, "status", "--porcelain=v1") == "", "Execution worktree must be clean")
    _require(
        _git(EVALUATION_ROOT, "status", "--porcelain=v1") == "",
        "Evaluation worktree must be clean while its prospective freeze is bound",
    )
    evaluation_head = _git(EVALUATION_ROOT, "rev-parse", "HEAD")
    evidence = validate_evidence(root, output)
    inspection_path = (
        root / "docs/experiments/results/a1-feasibility-001/dataset-inspection-delivery-v1.2.json"
    )
    inspection = _load(inspection_path)
    adapters = make_adapters(evidence, inspection)
    entries = _packet_entries(root, evidence)
    failures = _command_disposition(root)
    report = evidence["report"]
    monitor = evidence["monitor"]
    current_head = _git(root, "rev-parse", "HEAD")
    dataset_identity = _identity(
        evidence["dataset_path"], display="artifacts/assets/lift/ph/low_dim_v15.hdf5"
    )
    invocation = {
        "schema": "nisayon.a1-training-execution-invocation.v1",
        "declared_at": datetime.now(UTC).isoformat(),
        "source": {
            "tested_training_commit": evidence["tested_source"],
            "sealer_commit": current_head,
            "execution_branch": _git(root, "branch", "--show-current"),
            "evaluation_freeze_commit": evaluation_head,
            "contract_sha256": EXPECTED_CONTRACT_SHA256,
            "driver_sha256": file_digest(root / "scripts/experiments/run_a1_training_pilot.py"),
            "monitor_sha256": file_digest(
                root / "scripts/experiments/monitor_a1_training_pilot.py"
            ),
            "sealer_sha256": file_digest(root / "scripts/experiments/seal_a1_training_packet.py"),
            "dependency_lock_sha256": file_digest(root / "uv.lock"),
        },
        "training_command_record": _identity(
            evidence["run_root"] / "run.json", display=f"commands/{TRAINING_RUN_ID}/run.json"
        ),
        "training_command_record_id": TRAINING_RUN_ID,
        "dataset": dataset_identity,
        "dataset_copied_into_packet": False,
        "network_during_training": 0,
        "network_during_seal": 0,
        "optimizer_updates_during_seal": 0,
        "policy_or_simulator_execution_during_seal": False,
        "sealer_command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
        "sealer_command_record_root": os.environ.get("NISAYON_COMMAND_RECORD_ROOT"),
    }
    summary = {
        "schema": "nisayon.a1-training-execution-summary.v1",
        "case": CASE,
        "status": "executed_complete_pending_independent_assessment",
        "decision": "producer evidence supports feasibility within the authorized 100-update local CPU pilot budget; independent assessment remains required",
        "device": "cpu",
        "simulator_created": False,
        "environment_constructed": False,
        "rollouts": 0,
        "policy_actions": 0,
        "network_attempts": 0,
        "remote_telemetry": False,
        "workload": report["workload"],
        "normalization": {
            "override_calls": report["normalization"]["override_calls"],
            "restored_before_training_epoch": report["normalization"][
                "restored_before_training_epoch"
            ],
            "run_epoch_obs_normalization_stats": report["normalization"][
                "run_epoch_obs_normalization_stats"
            ],
            "first_batch_single_application_passed": evidence["first_batch"][
                "single_application_passed"
            ],
        },
        "checkpoint": report["checkpoint"],
        "costs": {
            "training": report["costs"],
            "outer_recorder_wall_seconds": evidence["run"]["wall_seconds"],
            "process_time_witness": evidence["time_witness"],
            "resource_monitor": {
                "peak_process_tree_rss_bytes": monitor["peak_process_tree_rss_bytes"],
                "maximum_observed_process_tree_cpu_seconds": monitor[
                    "maximum_observed_process_tree_cpu_seconds"
                ],
                "peak_temporary_bytes": monitor["peak_temporary_bytes"],
                "durable_output_bytes_after_receipt": monitor["durable_output_bytes_after_receipt"],
                "minimum_free_disk_bytes_observed": monitor["minimum_free_disk_bytes_observed"],
                "violations": monitor["violations"],
                "measurement_limit": monitor["measurement_limit"],
            },
            "acquisition": _load(
                root / "docs/experiments/results/a1-feasibility-001/acquisition-delivery-v1.2.json"
            )["measured_costs"],
            "dataset_inventory": inspection["costs"],
            "continuation_estimate": continuation_estimate(report, evidence["updates"]),
            "nesting_rule": "phase, child, monitor, /usr/bin/time and recorder durations are retained in their own scopes and are not summed",
            "cost_per_confirmed_repair": None,
        },
        "failures_and_history": failures,
        "claims": report["claims"],
        "claim_ladder": {
            "A_permission_and_custody": "producer-supported for the official substitute; independent assessment pending; Stanford permission unresolved",
            "B_offline_data_implementation_compatibility": "producer-supported within the pinned offline path; independent assessment pending",
            "C_effective_normalized_training": "producer-supported for exactly 100 updates; independent assessment pending",
            "D_checkpoint_reloadability": "producer-supported without an action or rollout; independent assessment pending",
            "E_measured_resource_feasibility": "producer-supported for this pilot; independent assessment pending",
            "F_simulator_compatibility": "unresolved and version-mismatched metadata recorded",
            "G_policy_competence": "unresolved",
            "H_task_intervention_and_confirmed_repair": "unobserved",
            "I_comparative_value": "unproven",
        },
        "ready_to_execute": True,
        "executed": True,
        "independently_assessed": False,
        "next": "Opus reads this immutable packet, the separate dataset payload and its pre-output reference under frozen Q1-Q7; no further training or rollout is authorized",
    }
    readback = seal_in_place(
        output,
        entries,
        adapters=adapters,
        invocation=invocation,
        summary=summary,
        source_commit=evidence["tested_source"],
        dataset_identity=dataset_identity,
    )
    _require(
        _git(EVALUATION_ROOT, "rev-parse", "HEAD") == evaluation_head
        and _git(EVALUATION_ROOT, "status", "--porcelain=v1") == "",
        "Evaluation freeze changed while the packet was sealed",
    )
    return readback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_packet(args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
