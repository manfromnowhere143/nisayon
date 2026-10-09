"""The A1 packet assessor reports missing evidence as unresolved and grades a complete packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from nisayon.evaluation import a1_pilot_assessor as assessor
from nisayon.evaluation import robomimic_reference as rr

torch = pytest.importorskip("torch")
KEYS = assessor.OBS_KEYS


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def _seal(store: Path) -> None:
    files = {}
    for path in sorted(store.rglob("*")):
        if path.is_file() and path.name not in ("seal.json", "artifact-manifest.json"):
            files[str(path.relative_to(store))] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write(store / "artifact-manifest.json", {"schema": "manifest", "files": files})
    entries = {}
    for name in ("summary.json", "invocation.json", "artifact-manifest.json"):
        p = store / name
        if p.exists():
            entries[name.replace(".json", "").replace("artifact-manifest", "artifact_manifest")] = {
                "path": name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
    _write(store / "seal.json", {"schema": "seal", "source_commit": "deadbeef", **entries})


def _reference(tmp_path: Path, stats: dict) -> Path:
    emu = {
        k: {
            "mean": list(map(float, np.asarray(v["mean"]).reshape(-1))),
            "std": list(map(float, np.asarray(v["std"]).reshape(-1))),
        }
        for k, v in stats.items()
    }
    doc = {
        "data_contract": {"demos": 2, "frames_total": 20},
        "statistics_reference": {"robomimic_float32_emulation": emu, "exact_float64": emu},
    }
    path = tmp_path / "reference.json"
    _write(path, doc)
    return path


def _stats() -> dict:
    return {
        k: {
            "mean": np.full((1, d), 0.5, dtype=np.float32),
            "std": np.full((1, d), 2.0, dtype=np.float32),
        }
        for k, d in assessor.EXPECTED_DIMS.items()
    }


def test_empty_packet_reports_missing_evidence_not_failure(tmp_path):
    store = tmp_path / "packet"
    _write(store / "summary.json", {"schema": "summary"})
    _write(store / "invocation.json", {"schema": "invocation"})
    _seal(store)
    report = assessor.assess_packet(store)
    assert report["seal"]["status"] == "verified"
    for key in ("Q2", "Q3", "Q4", "Q5", "Q6"):
        assert report["checks"][key]["status"] == "unresolved"
        assert report["checks"][key]["missing_evidence"]
    assert report["checks"]["Q1"]["status"] == "unresolved"


def test_complete_synthetic_packet_is_graded_from_evidence(tmp_path):
    store = tmp_path / "packet"
    stats = _stats()
    raw = {
        k: np.random.default_rng(1).normal(size=(3, 10, d)).tolist()
        for k, d in assessor.EXPECTED_DIMS.items()
    }
    learner = {
        k: rr.normalize(
            np.asarray(raw[k]), stats[k]["mean"], stats[k]["std"], dtype="float32"
        ).tolist()
        for k in KEYS
    }
    _write(
        store / "summary.json",
        {
            "schema": "summary",
            "simulator_created": False,
            "device": "cpu",
            "costs": {"phases": {"training": 1.0}},
        },
    )
    _write(store / "invocation.json", {"schema": "invocation"})
    _write(
        store / "results" / "membership.json",
        {
            "schema": "membership",
            "membership": {"demo_count": 2, "total_frames": 20, "rule": "all"},
        },
    )
    _write(
        store / "results" / "override-conformance.json",
        {"schema": "override conformance", "passed": True},
    )
    _write(
        store / "results" / "first-batch.json",
        {"schema": "first batch witness", "raw": raw, "learner_input": learner},
    )
    _write(
        store / "results" / "updates.json",
        {
            "schema": "training updates",
            "updates": [{"loss": 1.0 / (i + 1)} for i in range(100)],
            "attempted_updates": 100,
        },
    )
    _write(
        store / "results" / "parameters.json",
        {"schema": "parameter change", "l2_norm_of_difference": 0.7},
    )
    _write(
        store / "results" / "reload.json",
        {"schema": "reload", "stats_bound": True, "parameters_equal": True, "rollouts": 0},
    )
    config = {"train": {"hdf5_normalize_obs": True}, "experiment": {"rollout": {"enabled": False}}}
    ckpt = {
        "model": {"w": torch.zeros(2)},
        "config": json.dumps(config),
        "obs_normalization_stats": {
            k: {"mean": v["mean"].tolist(), "std": v["std"].tolist()} for k, v in stats.items()
        },
    }
    (store / "results").mkdir(exist_ok=True)
    torch.save(ckpt, store / "results" / "model_epoch_1.pth")
    _seal(store)
    report = assessor.assess_packet(store, reference_path=_reference(tmp_path, stats))
    assert report["summary"] == {
        "Q1": "unresolved",
        "Q2": "supported",
        "Q3": "supported",
        "Q4": "supported",
        "Q5": "supported",
        "Q6": "supported",
    }
    assert report["checks"]["Q3"]["first_batch_witness"]["single_application_all_keys"]
    assert not report["checks"]["Q5"]["optimizer_state_present"]


def test_double_normalization_and_short_workload_are_not_accepted(tmp_path):
    store = tmp_path / "packet"
    stats = _stats()
    raw = {
        k: np.random.default_rng(2).normal(size=(2, 10, d)).tolist()
        for k, d in assessor.EXPECTED_DIMS.items()
    }
    once = {
        k: rr.normalize(np.asarray(raw[k]), stats[k]["mean"], stats[k]["std"], dtype="float32")
        for k in KEYS
    }
    twice = {
        k: rr.normalize(once[k], stats[k]["mean"], stats[k]["std"], dtype="float32").tolist()
        for k in KEYS
    }
    _write(store / "summary.json", {"schema": "summary"})
    _write(store / "invocation.json", {"schema": "invocation"})
    _write(
        store / "results" / "first-batch.json",
        {"schema": "first batch witness", "raw": raw, "learner_input": twice},
    )
    _write(
        store / "results" / "statistics.json",
        {
            "schema": "statistics",
            "obs_normalization_stats": {
                k: {"mean": v["mean"].tolist(), "std": v["std"].tolist()} for k, v in stats.items()
            },
        },
    )
    _write(
        store / "results" / "updates.json",
        {"schema": "training updates", "updates": [{"loss": 0.5}] * 40, "attempted_updates": 100},
    )
    _write(
        store / "results" / "parameters.json",
        {"schema": "parameter change", "l2_norm_of_difference": 0.1},
    )
    _seal(store)
    report = assessor.assess_packet(store, reference_path=_reference(tmp_path, stats))
    witness = report["checks"]["Q3"]["first_batch_witness"]["per_key"]["object"]
    assert witness["double_application"] and not witness["single_application"]
    assert report["checks"]["Q3"]["status"] == "differs"
    assert (
        report["checks"]["Q4"]["status"] == "differs"
        and report["checks"]["Q4"]["completed_updates"] == 40
    )


def test_jsonl_updates_and_npz_arrays_are_consumed(tmp_path):
    store = tmp_path / "packet"
    stats = _stats()
    raw = {
        k: np.random.default_rng(5).normal(size=(2, 10, d))
        for k, d in assessor.EXPECTED_DIMS.items()
    }
    learner = {
        k: rr.normalize(raw[k], stats[k]["mean"], stats[k]["std"], dtype="float32") for k in KEYS
    }
    _write(store / "summary.json", {"schema": "summary"})
    _write(store / "invocation.json", {"schema": "invocation"})
    _write(
        store / "report.json",
        {
            "schema": "pilot report",
            "device": "cpu",
            "simulator_created": False,
            "stats_bound": True,
            "parameters_equal": True,
            "rollouts": 0,
            "costs": {"training_wall_seconds": 3.0},
        },
    )
    (store / "results").mkdir(parents=True)
    (store / "results" / "updates.jsonl").write_text(
        "\n".join(json.dumps({"update": i + 1, "loss": 1.0 / (i + 1)}) for i in range(100)) + "\n"
    )
    np.savez(
        store / "results" / "first-batch.npz",
        **{f"raw/{k}": raw[k] for k in KEYS},
        **{f"learner/{k}": learner[k] for k in KEYS},
    )
    np.savez(
        store / "results" / "normalization-stats.npz",
        **{f"{k}/mean": stats[k]["mean"] for k in KEYS},
        **{f"{k}/std": stats[k]["std"] for k in KEYS},
    )
    _write(
        store / "results" / "parameters.json",
        {"schema": "parameter change", "l2_norm_of_difference": 0.4},
    )
    _write(
        store / "results" / "membership.json",
        {
            "schema": "membership",
            "membership": {"demo_count": 2, "total_frames": 20, "rule": "all"},
        },
    )
    _write(
        store / "results" / "override-conformance.json",
        {"schema": "override conformance", "passed": True},
    )
    config = {"train": {"hdf5_normalize_obs": True}, "experiment": {"rollout": {"enabled": False}}}
    torch.save(
        {
            "model": {"w": torch.zeros(1)},
            "config": json.dumps(config),
            "obs_normalization_stats": {
                k: {"mean": v["mean"].tolist(), "std": v["std"].tolist()} for k, v in stats.items()
            },
        },
        store / "results" / "model.pth",
    )
    _seal(store)
    report = assessor.assess_packet(store, reference_path=_reference(tmp_path, stats))
    assert (
        report["checks"]["Q4"]["completed_updates"] == 100
        and report["checks"]["Q4"]["status"] == "supported"
    )
    assert report["checks"]["Q3"]["first_batch_witness"]["single_application_all_keys"]
    assert report["checks"]["Q3"]["archive_equals_checkpoint"]
    assert report["checks"]["Q5"]["status"] == "supported"


def test_learner_array_is_preferred_over_dataset_normalized_and_float64_path_is_exact(tmp_path):
    store = tmp_path / "packet"
    stats = _stats()
    raw = {
        k: np.random.default_rng(9).normal(size=(2, 10, d))
        for k, d in assessor.EXPECTED_DIMS.items()
    }
    mean64 = {k: stats[k]["mean"].astype(np.float64) for k in KEYS}
    std64 = {k: stats[k]["std"].astype(np.float64) for k in KEYS}
    dataset_normalized = {k: rr.exact_normalize(raw[k], mean64[k], std64[k]) for k in KEYS}
    learner = {k: dataset_normalized[k].astype(np.float32) for k in KEYS}
    _write(store / "summary.json", {"schema": "summary"})
    _write(store / "invocation.json", {"schema": "invocation"})
    (store / "results").mkdir(parents=True)
    np.savez(
        store / "results" / "first-batch.npz",
        **{f"raw__{k}": raw[k] for k in KEYS},
        **{f"dataset_normalized__{k}": dataset_normalized[k] for k in KEYS},
        **{f"learner__{k}": learner[k] for k in KEYS},
    )
    _write(
        store / "results" / "statistics.json",
        {
            "schema": "statistics",
            "obs_normalization_stats": {
                k: {"mean": v["mean"].tolist(), "std": v["std"].tolist()} for k, v in stats.items()
            },
        },
    )
    _seal(store)
    report = assessor.assess_packet(store, reference_path=_reference(tmp_path, stats))
    witness = report["checks"]["Q3"]["first_batch_witness"]
    assert witness["single_application_all_keys"]
    assert all(v["single_application_bitwise"] for v in witness["per_key"].values())
