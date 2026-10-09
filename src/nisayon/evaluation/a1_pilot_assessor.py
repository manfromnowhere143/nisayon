"""Assess a sealed A1 pilot packet against the frozen acceptance checks Q1–Q7.

The packet is the execution lane's sealed directory (``seal.json``, ``summary.json``,
``invocation.json``, ``artifact-manifest.json``, ``inputs/``, ``results/``, ``commands/``).
This module reads it without editing it, binds the assessment to the seal, the contract
version, the dataset digest and the manifest, locates the training evidence by content
(configuration, membership, bound statistics, per-update log, first-batch witness,
checkpoint, reload record, costs), and grades each check from the frozen rules in
``a1-amendment.v1.2.json``. Evidence that is absent yields ``unresolved`` with the exact
item named; nothing is inferred from a configured flag.

Independent references: ``robomimic_reference`` for the statistics and the transformation;
``torch`` only to open the checkpoint after its digest is verified (the checkpoint is a
pickle written by the producer, so its bytes are bound before loading).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from . import robomimic_reference as rr
from .schema import Malformed, load_json

ASSESSMENT_SCHEMA = "nisayon.a1-pilot.assessment.v1"
OBS_KEYS = ["object", "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos"]
EXPECTED_DIMS = {"object": 10, "robot0_eef_pos": 3, "robot0_eef_quat": 4, "robot0_gripper_qpos": 2}
DATASET_SHA256 = "2067777cb8b532e9263dd09fd6448c41cc31224bb27be4a3b734010ae13eb540"
DATASET_BYTES = 21084088
UPDATE_BUDGET = 100
Q3_MEAN_RTOL = 1e-5
Q3_STD_RTOL = 1e-4
BATCH_RTOL = 1e-5
BATCH_ATOL = 1e-6
DURABLE_CAP = 16 * 1024 * 1024


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_json(root: Path) -> dict[str, dict]:
    """Every JSON, JSON-lines and numpy archive in the packet keyed by relative path.

    JSON-lines files become ``{"schema": "<name> updates", "updates": [rows]}``; numpy
    archives become ``{"schema": "<name> arrays", "arrays": {key: list}}`` so that the
    content finders below can treat them like any other record.
    """
    out: dict[str, dict] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        try:
            if path.suffix == ".json":
                document = json.loads(path.read_text())
                if isinstance(document, dict):
                    out[rel] = document
            elif path.suffix == ".jsonl":
                rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                out[rel] = {"schema": f"{path.stem} updates jsonl", "updates": rows}
            elif path.suffix == ".npz":
                with np.load(path, allow_pickle=False) as archive:
                    out[rel] = {
                        "schema": f"{path.stem} arrays npz",
                        "arrays": {k: archive[k].tolist() for k in archive.files},
                        "dtypes": {k: str(archive[k].dtype) for k in archive.files},
                        "shapes": {k: list(archive[k].shape) for k in archive.files},
                    }
        except (OSError, ValueError):
            continue
    return out


def _find(documents: dict[str, dict], *needles: str) -> list[tuple[str, dict]]:
    """Documents whose schema or relative path contains every needle (case-insensitive)."""
    hits = []
    for rel, doc in documents.items():
        haystack = (rel + " " + str(doc.get("schema", ""))).lower()
        if all(n.lower() in haystack for n in needles):
            hits.append((rel, doc))
    return hits


def _arrays_to_stats(arrays: dict) -> dict:
    """``{"object/mean": [...], "object_std": [...]}`` style archives into robomimic's form."""
    stats: dict = {}
    for name, values in arrays.items():
        lowered = name.lower()
        for key in OBS_KEYS:
            if key in lowered:
                kind = "mean" if "mean" in lowered else "std" if "std" in lowered else None
                if kind:
                    stats.setdefault(key, {})[kind] = values
    return {k: v for k, v in stats.items() if "mean" in v and "std" in v}


def _unresolved(item: str, missing: str) -> dict:
    return {"status": "unresolved", "missing_evidence": missing, "item": item}


def verify_seal(store: Path) -> dict:
    seal_path = store / "seal.json"
    if not seal_path.exists():
        return {"sealed": False, "status": "unresolved", "missing_evidence": "seal.json"}
    seal = load_json(seal_path)
    checks: dict = {"sealed": True, "seal_sha256": _sha(seal_path), "entries": {}}
    for key in ("summary", "invocation", "artifact_manifest"):
        entry = seal.get(key) if isinstance(seal, dict) else None
        if isinstance(entry, dict) and "path" in entry:
            path = store / entry["path"]
            checks["entries"][entry["path"]] = path.exists() and _sha(path) == entry.get("sha256")
    manifest_entry = (seal.get("artifact_manifest") or {}) if isinstance(seal, dict) else {}
    manifest_path = store / manifest_entry.get("path", "artifact-manifest.json")
    bad: list[str] = []
    count = 0
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        files = manifest.get("files") if isinstance(manifest, dict) else None
        items = (
            files.items()
            if isinstance(files, dict)
            else [(f.get("path"), f.get("sha256")) for f in (files or [])]
        )
        for path, digest in items:
            count += 1
            if isinstance(digest, dict):
                digest = digest.get("sha256")
            target = store / str(path)
            if not target.exists() or _sha(target) != digest:
                bad.append(str(path))
    checks["manifest_entries"] = count
    checks["manifest_entries_bad"] = bad
    checks["status"] = (
        "verified"
        if checks["entries"] and all(checks["entries"].values()) and not bad and count
        else "differs"
    )
    checks["seal"] = seal
    return checks


def q1_permission_and_custody(
    store: Path, documents: dict[str, dict], dataset: Path | None
) -> dict:
    result: dict = {"item": "Q1 permission and custody"}
    hits = _find(documents, "acquisition")
    result["acquisition_records"] = [rel for rel, _ in hits]
    declared = None
    for _rel, doc in hits:
        obj = doc.get("acquired_object") or doc.get("dataset") or {}
        if obj.get("actual_sha256") or obj.get("sha256"):
            declared = {
                "sha256": obj.get("actual_sha256") or obj.get("sha256"),
                "bytes": obj.get("actual_bytes") or obj.get("bytes"),
            }
            break
    if dataset is not None and dataset.exists():
        actual = {"sha256": _sha(dataset), "bytes": dataset.stat().st_size}
        result["payload"] = actual
        result["payload_matches_publisher"] = actual == {
            "sha256": DATASET_SHA256,
            "bytes": DATASET_BYTES,
        }
    else:
        result["payload"] = None
    result["declared"] = declared
    if result.get("payload_matches_publisher"):
        result["status"] = "supported"
        result["scope"] = (
            "the official repository object under its MIT card declaration; the Stanford object stays unresolved"
        )
    elif dataset is None:
        result.update(
            _unresolved(result["item"], "dataset payload path not available to the assessor")
        )
    else:
        result["status"] = "differs"
    return result


def q2_data_compatibility(documents: dict[str, dict], reference: dict | None) -> dict:
    result: dict = {"item": "Q2 data and implementation compatibility"}
    inspection = _find(documents, "inspection") + _find(documents, "membership")
    result["records"] = [rel for rel, _ in inspection]
    membership = None
    for _rel, doc in inspection:
        m = doc.get("membership")
        if isinstance(m, dict) and m.get("demo_count"):
            membership = m
            break
    if membership is None:
        result.update(
            _unresolved(result["item"], "a membership record with demo_count and total_frames")
        )
        return result
    result["membership"] = {k: membership.get(k) for k in ("demo_count", "total_frames", "rule")}
    if reference:
        expected = reference["data_contract"]
        result["matches_reference"] = (
            membership.get("demo_count") == expected["demos"]
            and membership.get("total_frames") == expected["frames_total"]
        )
    override = _find(documents, "override") + _find(documents, "conformance")
    result["override_control_records"] = [rel for rel, _ in override]
    control_pass = None
    for _rel, doc in override:
        for key in ("passed", "all_shapes_equal", "conformance", "status"):
            if key in doc:
                control_pass = doc[key]
                break
    result["override_control"] = control_pass
    env_free = None
    for _rel, doc in (
        _find(documents, "training") + _find(documents, "summary") + _find(documents, "report")
    ):
        for key in ("simulator_created", "environment_constructed", "environments_created"):
            if key in doc:
                env_free = not bool(doc[key])
    result["no_environment_construction"] = env_free
    if result.get("matches_reference") and control_pass not in (None, False, "failed") and env_free:
        result["status"] = "supported"
    elif control_pass is None or env_free is None:
        result.update(
            _unresolved(
                result["item"],
                "override conformance control and an explicit no-environment statement",
            )
        )
    else:
        result["status"] = "differs"
    return result


def q3_effective_normalization(
    store: Path, documents: dict[str, dict], reference: dict | None, checkpoint: dict | None
) -> dict:
    result: dict = {"item": "Q3 effective normalized training"}
    stats = None
    if checkpoint and isinstance(checkpoint.get("obs_normalization_stats"), dict):
        stats = checkpoint["obs_normalization_stats"]
        result["statistics_source"] = "checkpoint"
        for rel, doc in _find(documents, "stat", "npz"):
            arrays = doc.get("arrays") or {}
            archive_stats = _arrays_to_stats(arrays)
            if archive_stats:
                result["statistics_archive"] = rel
                result["archive_equals_checkpoint"] = all(
                    np.array_equal(
                        np.asarray(archive_stats[k][s], dtype=np.float32).reshape(-1),
                        np.asarray(stats[k][s], dtype=np.float32).reshape(-1),
                    )
                    for k in OBS_KEYS
                    if k in archive_stats and k in stats
                    for s in ("mean", "std")
                )
    else:
        for rel, doc in _find(documents, "statistic"):
            candidate = doc.get("obs_normalization_stats") or doc.get("statistics") or doc
            if all(k in candidate for k in OBS_KEYS):
                stats = candidate
                result["statistics_source"] = rel
                break
    if stats is None:
        result.update(
            _unresolved(
                result["item"],
                "bound obs_normalization_stats in the checkpoint or a statistics record",
            )
        )
        return result
    if reference:
        emulation = {
            k: {"mean": np.array(v["mean"]), "std": np.array(v["std"])}
            for k, v in reference["statistics_reference"]["robomimic_float32_emulation"].items()
        }
        comparison = rr.compare_statistics(
            emulation, stats, OBS_KEYS, mean_rtol=Q3_MEAN_RTOL, std_rtol=Q3_STD_RTOL
        )
        result["against_reference_emulation"] = comparison
        exact = {
            k: {"mean": np.array(v["mean"]), "std": np.array(v["std"])}
            for k, v in reference["statistics_reference"]["exact_float64"].items()
        }
        result["against_exact_float64"] = rr.compare_statistics(
            exact, stats, OBS_KEYS, mean_rtol=1e-4, std_rtol=1e-4
        )
    witness = None
    for rel, doc in _find(documents, "batch"):
        if any(k in doc for k in ("raw", "normalized", "learner_input", "first_batch")):
            witness = (rel, doc)
            break
        arrays = doc.get("arrays")
        if isinstance(arrays, dict):
            raw = {k: arrays[n] for k in OBS_KEYS for n in arrays if "raw" in n and k in n}
            learner = {
                k: arrays[n]
                for k in OBS_KEYS
                for n in arrays
                if ("learner" in n or "normalized" in n) and k in n and "cached" not in n
            }
            if raw and learner:
                witness = (
                    rel,
                    {"raw": raw, "learner_input": learner, "array_names": sorted(arrays)},
                )
                break
    if witness is None:
        result["first_batch_witness"] = _unresolved(
            "first batch",
            "a recorded first batch with raw values (or indices) and the learner input",
        )
    else:
        rel, doc = witness
        outcome = {"record": rel}
        raw = doc.get("raw") or doc.get("raw_batch")
        learner = doc.get("learner_input") or doc.get("normalized") or doc.get("first_batch")
        if isinstance(raw, dict) and isinstance(learner, dict):
            per_key = {}
            for key in OBS_KEYS:
                if key not in raw or key not in learner:
                    per_key[key] = "missing"
                    continue
                x = np.asarray(raw[key], dtype=np.float64)
                observed = np.asarray(learner[key], dtype=np.float32)
                mean = np.array(stats[key]["mean"], dtype=np.float32).astype(np.float64)
                std = np.array(stats[key]["std"], dtype=np.float64)
                # executed path: robomimic caches observations in their file dtype
                # (float64); the override computes in float64 with float32 means; the
                # learner casts to float32. Compared exactly, then at the frozen tolerance.
                once = rr.exact_normalize(x, mean, std).astype(np.float32)
                twice = rr.exact_normalize(once.astype(np.float64), mean, std).astype(np.float32)
                exact_single = observed.shape == once.shape and np.array_equal(observed, once)
                single = observed.shape == once.shape and np.allclose(
                    observed, once, rtol=BATCH_RTOL, atol=BATCH_ATOL
                )
                double = observed.shape == twice.shape and np.allclose(
                    observed, twice, rtol=BATCH_RTOL, atol=BATCH_ATOL
                )
                # diagnostic only: the float32-arithmetic variant this lane first assumed
                once32 = rr.normalize(x, mean, std, dtype="float32")
                diff32 = (
                    float(np.max(np.abs(observed.astype(np.float64) - once32)))
                    if observed.shape == once32.shape
                    else None
                )
                per_key[key] = {
                    "single_application": bool(single),
                    "single_application_bitwise": bool(exact_single),
                    "double_application": bool(double),
                    "float32_arithmetic_max_abs_diff": diff32,
                    "dtype": str(observed.dtype),
                    "shape": list(observed.shape),
                }
            outcome["per_key"] = per_key
            outcome["single_application_all_keys"] = all(
                isinstance(v, dict) and v["single_application"] for v in per_key.values()
            )
        else:
            outcome["missing_evidence"] = "raw and learner-input arrays for the same batch"
        result["first_batch_witness"] = outcome
    stats_ok = bool(result.get("against_reference_emulation", {}).get("within"))
    batch_ok = bool(result.get("first_batch_witness", {}).get("single_application_all_keys"))
    if stats_ok and batch_ok:
        result["status"] = "supported"
    elif "missing_evidence" in result.get("first_batch_witness", {}) or "status" in result.get(
        "first_batch_witness", {}
    ):
        result["status"] = "unresolved"
        result["missing_evidence"] = (
            "first-batch witness" if stats_ok else "statistics agreement and first-batch witness"
        )
    else:
        result["status"] = "differs"
    return result


def q4_executed_workload(documents: dict[str, dict]) -> dict:
    result: dict = {"item": "Q4 executed optimizer updates"}
    log = None
    for rel, doc in (
        _find(documents, "update") + _find(documents, "training") + _find(documents, "loss")
    ):
        for key in ("updates", "per_update", "losses", "steps"):
            if isinstance(doc.get(key), list) and doc[key]:
                log = (rel, key, doc[key], doc)
                break
        if log:
            break
    if log is None:
        result.update(_unresolved(result["item"], "a per-update log with losses and timestamps"))
        return result
    rel, key, entries, doc = log
    losses = []
    for e in entries:
        value = e.get("loss") if isinstance(e, dict) else e
        try:
            losses.append(float(value))
        except (TypeError, ValueError):
            losses.append(math.nan)
    result["record"] = rel
    result["completed_updates"] = len(entries)
    result["all_finite"] = all(math.isfinite(v) for v in losses)
    result["first_loss"] = losses[0] if losses else None
    result["last_loss"] = losses[-1] if losses else None
    attempted = doc.get("attempted_updates") or doc.get("attempts")
    result["attempted_updates_declared"] = attempted
    result["within_budget"] = len(entries) <= UPDATE_BUDGET and (
        attempted is None or (isinstance(attempted, (int, float)) and attempted <= UPDATE_BUDGET)
    )
    change = None
    for _rel, d in _find(documents, "parameter") + _find(documents, "weights"):
        for k in ("l2_norm_of_difference", "parameter_change_l2", "difference_norm"):
            if k in d:
                change = d[k]
    result["parameter_change_l2"] = change
    device = None
    for _rel, d in (
        _find(documents, "training")
        + _find(documents, "summary")
        + _find(documents, "config")
        + _find(documents, "report")
    ):
        for k in ("device", "torch_device"):
            if k in d:
                device = d[k]
    result["device"] = device
    if (
        len(entries) == UPDATE_BUDGET
        and result["all_finite"]
        and change
        and float(change) > 0
        and (device in (None, "cpu") or str(device).startswith("cpu"))
    ):
        result["status"] = "supported" if device is not None else "unresolved"
        if device is None:
            result["missing_evidence"] = "an explicit device record (cpu)"
    elif change is None:
        result["status"] = "unresolved"
        result["missing_evidence"] = (
            "a parameter-change record (state before the first update and after the last)"
        )
    else:
        result["status"] = (
            "differs" if len(entries) != UPDATE_BUDGET or not result["all_finite"] else "unresolved"
        )
    return result


def q5_checkpoint(
    store: Path, documents: dict[str, dict], checkpoint_path: Path | None, checkpoint: dict | None
) -> dict:
    result: dict = {"item": "Q5 checkpoint identity and reload"}
    if checkpoint_path is None or checkpoint is None:
        result.update(
            _unresolved(result["item"], "a checkpoint file whose digest is recorded in the packet")
        )
        return result
    result["checkpoint"] = {
        "path": str(checkpoint_path.relative_to(store))
        if str(checkpoint_path).startswith(str(store))
        else str(checkpoint_path),
        "bytes": checkpoint_path.stat().st_size,
        "sha256": _sha(checkpoint_path),
    }
    config = (
        json.loads(checkpoint["config"])
        if isinstance(checkpoint.get("config"), str)
        else checkpoint.get("config")
    )
    result["config_hdf5_normalize_obs"] = (config or {}).get("train", {}).get("hdf5_normalize_obs")
    result["config_rollout_enabled"] = (
        (config or {}).get("experiment", {}).get("rollout", {}).get("enabled")
    )
    result["stats_bound"] = isinstance(checkpoint.get("obs_normalization_stats"), dict)
    result["state_dict_tensors"] = (
        len(checkpoint.get("model", {})) if isinstance(checkpoint.get("model"), dict) else None
    )
    result["optimizer_state_present"] = "optimizer" in checkpoint
    result["rng_state_present"] = any(
        k in checkpoint for k in ("rng", "rng_state", "torch_rng_state")
    )
    reload = None
    for rel, doc in (
        _find(documents, "reload") + _find(documents, "load") + _find(documents, "report")
    ):
        if any(
            k in doc
            for k in ("loaded", "policy_from_checkpoint", "stats_bound", "parameters_equal")
        ):
            reload = (rel, doc)
            break
    if reload is None:
        result["reload"] = _unresolved(
            "reload",
            "a recorded load through policy_from_checkpoint with statistics bound and parameters compared",
        )
    else:
        rel, doc = reload
        result["reload"] = {
            "record": rel,
            "stats_bound": doc.get("stats_bound"),
            "parameters_equal": doc.get("parameters_equal"),
            "rollout": doc.get("rollout", doc.get("rollouts")),
        }
    if (
        result["stats_bound"]
        and result["config_hdf5_normalize_obs"]
        and isinstance(result.get("reload"), dict)
        and result["reload"].get("parameters_equal")
        and result["reload"].get("stats_bound")
    ):
        result["status"] = "supported"
        result["scope"] = (
            "serialization and recovery of the expected state; inference equivalence on prescribed probes and training resumption were not checked (no optimizer or RNG state)"
        )
    elif "missing_evidence" in result.get("reload", {}):
        result["status"] = "unresolved"
        result["missing_evidence"] = "reload witness"
    else:
        result["status"] = "differs"
    return result


def q6_costs(store: Path, documents: dict[str, dict], checkpoint_path: Path | None) -> dict:
    result: dict = {"item": "Q6 measured resource feasibility"}
    costs = None
    for rel, doc in (
        _find(documents, "cost") + _find(documents, "summary") + _find(documents, "report")
    ):
        if any(k in doc for k in ("measured_costs", "known_costs", "costs", "phases")):
            costs = (
                rel,
                doc.get("measured_costs")
                or doc.get("known_costs")
                or doc.get("costs")
                or doc.get("phases"),
            )
            break
    if costs is None:
        result.update(_unresolved(result["item"], "a measured cost record with phases"))
        return result
    result["record"], result["costs"] = costs
    durable = 0
    for path in store.rglob("*"):
        if path.is_file() and "inputs/sources" not in str(path) and not path.name.endswith(".hdf5"):
            durable += path.stat().st_size
    result["packet_bytes_excluding_dataset"] = durable
    result["within_durable_cap"] = durable <= DURABLE_CAP
    result["dataset_scope"] = "counted under the acquisition and source caps, not the durable cap"
    result["status"] = "supported" if result["within_durable_cap"] else "differs"
    return result


def find_checkpoint(store: Path) -> tuple[Path | None, dict | None]:
    candidates = sorted(store.rglob("*.pth")) + sorted(store.rglob("*.pt"))
    if not candidates:
        return None, None
    path = candidates[0]
    import torch

    return path, torch.load(path, map_location="cpu", weights_only=False)


def assess_packet(
    store: Path, *, reference_path: Path | None = None, dataset: Path | None = None
) -> dict:
    store = Path(store)
    reference = load_json(reference_path) if reference_path else None
    documents = _walk_json(store)
    seal = verify_seal(store)
    checkpoint_path, checkpoint = find_checkpoint(store)
    report: dict = {
        "schema": ASSESSMENT_SCHEMA,
        "store": str(store),
        "seal": {k: v for k, v in seal.items() if k != "seal"},
        "bindings": {
            "producer_commit": (seal.get("seal") or {}).get("source_commit"),
            "contract": "a1-amendment.v1.2.json",
            "dataset_sha256": DATASET_SHA256,
            "reference": str(reference_path) if reference_path else None,
            "reference_sha256": _sha(reference_path) if reference_path else None,
            "assessor": {
                "path": "src/nisayon/evaluation/a1_pilot_assessor.py",
                "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
        },
        "documents_seen": sorted(documents),
        "checks": {},
    }
    report["checks"]["Q1"] = q1_permission_and_custody(store, documents, dataset)
    report["checks"]["Q2"] = q2_data_compatibility(documents, reference)
    report["checks"]["Q3"] = q3_effective_normalization(store, documents, reference, checkpoint)
    report["checks"]["Q4"] = q4_executed_workload(documents)
    report["checks"]["Q5"] = q5_checkpoint(store, documents, checkpoint_path, checkpoint)
    report["checks"]["Q6"] = q6_costs(store, documents, checkpoint_path)
    report["summary"] = {k: v.get("status") for k, v in report["checks"].items()}
    return report


def render(report: dict) -> str:
    lines = [
        f"packet {report['store']}: seal {report['seal'].get('status')} ({report['seal'].get('manifest_entries')} entries, bad {report['seal'].get('manifest_entries_bad')})"
    ]
    for key, check in report["checks"].items():
        line = f"  {key}: {check.get('status')}"
        if check.get("missing_evidence"):
            line += f" (missing: {check['missing_evidence']})"
        lines.append(line)
    return "\n".join(lines)


def assess_file(
    store: Path, reference_path: Path | None, dataset: Path | None, out: Path | None
) -> dict:
    report = assess_packet(store, reference_path=reference_path, dataset=dataset)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return report


__all__ = ["assess_packet", "assess_file", "render", "verify_seal", "Malformed"]
