"""The A1 runtime assessor decides identity, compatibility and competence separately from
manifest-bound evidence and returns one disposition; the execution lane's probe controls are
kept as regressions."""

from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from nisayon.evaluation import a1_runtime_assessor as assessor
from nisayon.evaluation import robomimic_reference as rr

h5py = pytest.importorskip("h5py")
KEYS = assessor.OBS_KEYS
DIMS = assessor.EXPECTED_DIMS
T = 4
SEEDS = list(range(200, 210))
TABLE_Z = 0.8
WHEEL_URL = "https://files.pythonhosted.org/packages/f4/15/x/robosuite-1.5.1-py3-none-any.whl"
MIT_TEXT = (
    "MIT License\n\nCopyright (c) 2024 robosuite\n\nPermission is hereby granted, free of charge, "
    "to any person obtaining a copy of this software...\n"
)
CHAIN = [
    "nisayon.a1-runtime-contract.v1",
    "nisayon.a1-runtime-contract-amendment.v1.1",
    "nisayon.a1-runtime-contract-amendment.v1.2",
    "nisayon.a1-runtime-contract-amendment.v1.3",
]
ENV_ARGS = json.dumps(
    {
        "env_name": "Lift",
        "env_version": "1.5.1",
        "type": 1,
        "env_kwargs": {
            "has_renderer": False,
            "has_offscreen_renderer": False,
            "ignore_done": True,
            "use_object_obs": True,
            "use_camera_obs": False,
            "control_freq": 20,
            "controller_configs": {
                "type": "BASIC",
                "body_parts": {"right": {"type": "OSC_POSE", "kp": 150}},
            },
            "robots": ["Panda"],
            "camera_depths": False,
            "reward_shaping": False,
        },
    }
)


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seal(store: Path) -> None:
    for name in ("seal.json", "artifact-manifest.json", "summary.json", "invocation.json"):
        (store / name).unlink(missing_ok=True)
    files = {str(p.relative_to(store)): _sha(p) for p in sorted(store.rglob("*")) if p.is_file()}
    _write(store / "artifact-manifest.json", {"schema": "manifest", "files": files})
    _write(store / "summary.json", {"schema": "summary"})
    _write(store / "invocation.json", {"schema": "invocation"})
    entries = {}
    for name in ("summary.json", "invocation.json", "artifact-manifest.json"):
        key = name.replace(".json", "").replace("artifact-manifest", "artifact_manifest")
        entries[key] = {"path": name, "sha256": _sha(store / name)}
    _write(store / "seal.json", {"schema": "seal", "source_commit": "deadbeef", **entries})


def _wheel(tmp_path: Path) -> dict:
    """A small but well-formed wheel: dist-info with METADATA, LICENSE and a verifying RECORD."""
    members = {
        "robosuite/__init__.py": b"__version__ = '1.5.1'\n",
        "robosuite/models/assets/arenas/table_arena.xml": b"<mujoco/>\n",
        "robosuite-1.5.1.dist-info/METADATA": b"Name: robosuite\nVersion: 1.5.1\nLicense-File: LICENSE\n",
        "robosuite-1.5.1.dist-info/LICENSE": MIT_TEXT.encode(),
    }
    rows = []
    for name, data in members.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append(f"{name},sha256={digest},{len(data)}")
    rows.append("robosuite-1.5.1.dist-info/RECORD,,")
    record = ("\n".join(rows) + "\n").encode()
    path = tmp_path / "robosuite-1.5.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
        archive.writestr("robosuite-1.5.1.dist-info/RECORD", record)
    return {
        "path": path,
        "sha256": _sha(path),
        "bytes": path.stat().st_size,
        "record": record,
        "record_sha256": hashlib.sha256(record).hexdigest(),
        "license_sha256": hashlib.sha256(MIT_TEXT.encode()).hexdigest(),
        "members": len(members),
    }


def _stats() -> dict:
    rng = np.random.default_rng(3)
    return {
        k: {
            "mean": rng.normal(size=(1, d)).astype(np.float32),
            "std": (rng.uniform(0.5, 1.5, size=(1, d)) + 1e-3).astype(np.float64),
        }
        for k, d in DIMS.items()
    }


def _stats_npz(path: Path, stats: dict) -> None:
    np.savez(
        path,
        **{f"{k}__mean": v["mean"] for k, v in stats.items()},
        **{f"{k}__std": v["std"] for k, v in stats.items()},
    )


def _trajectory(rng: np.random.Generator, steps: int) -> dict:
    obs = {k: rng.normal(size=(steps + 1, d)) for k, d in DIMS.items()}
    return {
        "obs": obs,
        "actions": rng.uniform(-1, 1, size=(steps, 7)),
        "states": rng.normal(size=(steps + 1, 32)),
    }


def _dataset(tmp_path: Path, demo: dict) -> Path:
    path = tmp_path / "lift.hdf5"
    with h5py.File(path, "w") as file:
        data = file.create_group("data")
        data.attrs["env_args"] = ENV_ARGS
        group = data.create_group("demo_0")
        group.attrs["model_file"] = "<mujoco/>"
        group.create_dataset("states", data=demo["states"][:-1])
        group.create_dataset("actions", data=demo["actions"])
        rewards = np.zeros(T)
        rewards[-1] = 1.0
        group.create_dataset("rewards", data=rewards)
        group.create_dataset("dones", data=np.zeros(T, dtype=np.int64))
        for k in KEYS:
            group.create_dataset(f"obs/{k}", data=demo["obs"][k][:-1])
            group.create_dataset(f"next_obs/{k}", data=demo["obs"][k][1:])
    return path


def _checkpoint(tmp_path: Path, stats: dict) -> Path:
    torch = pytest.importorskip("torch")
    path = tmp_path / "model.pth"
    torch.save({"obs_normalization_stats": stats, "model": {}}, path)
    return path


def _contracts(
    tmp_path: Path, dataset: Path, checkpoint: Path, pilot_stats: Path, wheel: dict
) -> list[Path]:
    v1 = tmp_path / "runtime-contract.v1.json"
    _write(v1, {"schema": "nisayon.a1-runtime-contract.v1", "case": "a1-runtime-001"})
    v11 = tmp_path / "runtime-contract.v1.1.json"
    _write(
        v11,
        {
            "schema": "nisayon.a1-runtime-contract-amendment.v1.1",
            "amends": {"path": v1.name, "sha256": _sha(v1)},
        },
    )
    v12 = tmp_path / "runtime-contract.v1.2.json"
    _write(
        v12,
        {
            "schema": "nisayon.a1-runtime-contract-amendment.v1.2",
            "amends": [
                {"path": v1.name, "sha256": _sha(v1)},
                {"path": v11.name, "sha256": _sha(v11)},
            ],
            "effective": {"route": "A"},
        },
    )
    v13 = tmp_path / "runtime-contract.v1.3.json"
    _write(
        v13,
        {
            "schema": "nisayon.a1-runtime-contract-amendment.v1.3",
            "amends": [
                {"path": v1.name, "sha256": _sha(v1)},
                {"path": v11.name, "sha256": _sha(v11)},
                {"path": v12.name, "sha256": _sha(v12)},
            ],
            "effective": {
                "contract_chain": CHAIN,
                "route": "A",
                "wheel": {"url": WHEEL_URL, "sha256": wheel["sha256"], "bytes": wheel["bytes"]},
                "wheel_allowance_bytes": 167772160,
                "other_download_ceiling_bytes": 24430709,
                "application_responses": {"cumulative_ceiling": 18, "consumed_before": 12},
                "reset_determinism_seed": 900,
                "replay": {"demo": "demo_0", "T": T, "attempts": ["R-1", "R-2"]},
                "development": {"seeds": SEEDS, "minimum_successes": 8, "horizon": 400},
                "dataset_sha256": _sha(dataset),
                "checkpoint_sha256": _sha(checkpoint),
                "pilot_statistics_sha256": _sha(pilot_stats),
                "thresholds": {
                    "first_frame_atol": 1e-6,
                    "trajectory_atol": 1e-3,
                    "time_atol": 1e-12,
                    "lift_margin_m": 0.04,
                },
            },
        },
    )
    return [v1, v11, v12, v13]


def _replay_arrays(demo: dict, cube_z: np.ndarray) -> dict:
    success = cube_z > TABLE_Z + 0.04
    arrays = {
        "states": demo["states"],
        "actions": demo["actions"],
        "cube_z": cube_z,
        "table_z": np.full(T + 1, TABLE_Z),
        "success": success,
        "reward": np.where(success, 1.0, 0.0),
        "sim_time": np.arange(T + 1) * 0.05,
    }
    for k in KEYS:
        arrays[f"obs__{k}"] = demo["obs"][k]
    arrays["obs__object-state"] = demo["obs"]["object"].copy()
    return arrays


def _episode_arrays(rng: np.random.Generator, stats: dict, steps: int, succeed: bool) -> dict:
    obs = {k: rng.normal(size=(steps, d)) for k, d in DIMS.items()}
    cube = np.full(steps, TABLE_Z + 0.01)
    if succeed:
        cube[-1] = TABLE_Z + 0.05
    success = cube > TABLE_Z + 0.04
    witness_steps = np.array(sorted({0, 1, 2, steps - 1} & set(range(steps))))
    arrays = {
        "actions": rng.uniform(-1, 1, size=(steps, 7)).astype(np.float32),
        "success": success,
        "reward": np.where(success, 1.0, 0.0),
        "cube_z": cube,
        "table_z": np.full(steps, TABLE_Z),
        "inference_s": np.full(steps, 0.002),
        "step_s": np.full(steps, 0.005),
        "witness_steps": witness_steps,
    }
    for k in KEYS:
        arrays[f"obs__{k}"] = obs[k]
        raw = obs[k][witness_steps]
        mean = stats[k]["mean"].reshape(-1).astype(np.float64)
        std = stats[k]["std"].reshape(-1)
        arrays[f"witness_raw__{k}"] = raw
        arrays[f"witness_consumed__{k}"] = rr.exact_normalize(raw, mean, std).astype(np.float32)
    return arrays


def build_packet(tmp_path: Path, *, successes: int = 8) -> dict:
    rng = np.random.default_rng(11)
    demo = _trajectory(rng, T)
    dataset = _dataset(tmp_path, demo)
    stats = _stats()
    checkpoint = _checkpoint(tmp_path, stats)
    pilot_stats = tmp_path / "normalization-stats.npz"
    _stats_npz(pilot_stats, stats)
    wheel = _wheel(tmp_path)
    contracts = _contracts(tmp_path, dataset, checkpoint, pilot_stats, wheel)
    store = tmp_path / "packet"
    store.mkdir()
    _write(store / "source-ledger.v3.json", {"schema": "ledger", "responses": 13})
    _write(
        store / "dependency-gate-001.json",
        {
            "route": "A",
            "wheel_url": WHEEL_URL,
            "wheel_sha256_expected": wheel["sha256"],
            "wheel_bytes_expected": wheel["bytes"],
            "downloaded_bytes": wheel["bytes"],
            "wheel_downloaded_bytes": wheel["bytes"],
            "other_downloaded_bytes": 0,
            "responses": {"consumed_before": 12, "used": 1, "cumulative_ceiling": 18},
            "ledger": {
                "path": "source-ledger.v3.json",
                "sha256": _sha(store / "source-ledger.v3.json"),
            },
            "stopped": False,
            "stop_reason": None,
        },
    )
    (store / "dist-info").mkdir()
    (store / "dist-info" / "RECORD").write_bytes(wheel["record"])
    (store / "dist-info" / "LICENSE").write_text(MIT_TEXT)
    _write(
        store / "acquisition-receipt-001.json",
        {
            "wheel_bytes": wheel["bytes"],
            "wheel_bytes_expected": wheel["bytes"],
            "wheel_sha256": wheel["sha256"],
            "wheel_sha256_expected": wheel["sha256"],
            "compared_against_retained_metadata": True,
            "verified_before_installation": True,
            "record": {"verified": True, "members": wheel["members"], "bad": 0},
            "license": {
                "member": "robosuite-1.5.1.dist-info/LICENSE",
                "sha256": wheel["license_sha256"],
                "declaration": "MIT",
                "covers_distribution": True,
            },
        },
    )
    packages = {
        name: {"version": version, "sha256": hashlib.sha256(name.encode()).hexdigest()}
        for name, version in (
            ("mujoco", "3.2.7"),
            ("numpy", "1.26.4"),
            ("torch", "2.5.1"),
            ("robomimic", "0.3.0"),
        )
    }
    packages["robosuite"] = {"version": "1.5.1", "sha256": wheel["sha256"]}
    _write(
        store / "runtime-identity.json",
        {
            "robosuite_version": "1.5.1",
            "historical": {
                "robosuite_version": "1.4.1",
                "lock_sha256_before": "a" * 64,
                "lock_sha256_after": "a" * 64,
                "pyproject_sha256_before": "b" * 64,
                "pyproject_sha256_after": "b" * 64,
                "venv_sha256_before": "c" * 64,
                "venv_sha256_after": "c" * 64,
            },
            "packages": packages,
            "installation": {"index_access_disabled": True, "dependency_resolution_pinned": True},
            "mink_adaptation": {
                "reachable_from_lift_path": False,
                "static_evidence": "no module-level import of mink on the Lift/OSC path",
                "absent_from_sys_modules_after_construction": True,
                "absent_from_sys_modules_after_episodes": True,
            },
        },
    )
    kwargs = dict(json.loads(ENV_ARGS)["env_kwargs"])
    kwargs.update(assessor.FORCED_FLAGS)
    _write(store / "env-args.json", {"consumed_env_args": ENV_ARGS, "make_kwargs": kwargs})
    _write(
        store / "controller.json",
        {
            "right": dict(assessor.EXPECTED_CONTROLLER),
            "gripper": {"type": "GRIP"},
            "action_dim": 7,
            "action_low": [-1.0] * 7,
            "action_high": [1.0] * 7,
        },
    )
    _write(
        store / "timing.json",
        {
            "control_freq": 20,
            "control_timestep": 0.05,
            "model_timestep": 0.002,
            "opt_timestep": 0.002,
        },
    )
    close = np.stack([np.linspace(0.0208, 0.001, 10), -np.linspace(0.0208, 0.001, 10)], axis=1)
    np.savez(
        store / "probe.npz",
        gripper_close_qpos=close,
        gripper_open_qpos=close[::-1],
        sim_time=np.arange(21) * 0.05,
    )
    _write(
        store / "reset-determinism.json",
        {
            "seed": 900,
            "state_sha256": ["s", "s"],
            "obs_sha256": ["o", "o"],
            "separate_processes": True,
        },
    )
    cube = np.full(T + 1, TABLE_Z + 0.01)
    cube[-1] = TABLE_Z + 0.05
    for attempt in ("R-1", "R-2"):
        np.savez(store / f"replay-{attempt}.npz", **_replay_arrays(demo, cube))
        _write(
            store / f"replay-{attempt}.json", {"attempt": attempt, "completed": True, "steps": T}
        )
    for i, seed in enumerate(SEEDS):
        succeed = i < successes
        steps = 3 if succeed else 400
        np.savez(store / f"episode-E-{seed}.npz", **_episode_arrays(rng, stats, steps, succeed))
        _write(
            store / f"episode-E-{seed}.json",
            {
                "seed": seed,
                "started": True,
                "completed": True,
                "termination": "success" if succeed else "horizon",
                "steps": steps,
                "parameter_sha256": "d" * 64,
            },
        )
    _stats_npz(store / "inference-stats.npz", stats)
    _write(
        store / "policy-identity.json",
        {
            "checkpoint_sha256": _sha(checkpoint),
            "parameter_sha256_before": "d" * 64,
            "parameter_sha256_after": "d" * 64,
        },
    )
    _write(store / "costs.json", {"R-1": {"wall_s": 1.0}})
    _write(store / "failures.json", {"failures": []})
    _seal(store)
    return {
        "store": store,
        "contracts": contracts,
        "dataset": dataset,
        "pilot_stats": pilot_stats,
        "checkpoint": checkpoint,
        "wheel": wheel["path"],
        "wheel_info": wheel,
    }


def _assess(fixture: dict, **overrides) -> dict:
    kwargs = {
        "contract_paths": fixture["contracts"],
        "dataset": fixture["dataset"],
        "pilot_stats": fixture["pilot_stats"],
        "checkpoint": fixture["checkpoint"],
        "wheel": fixture["wheel"],
    }
    kwargs.update(overrides)
    return assessor.assess_packet(fixture["store"], **kwargs)


def _edit_npz(path: Path, mutate) -> None:
    with np.load(path) as archive:
        arrays = {k: archive[k] for k in archive.files}
    mutate(arrays)
    np.savez(path, **arrays)


def _edit_json(path: Path, mutate) -> None:
    doc = json.loads(path.read_text())
    mutate(doc)
    _write(path, doc)


def test_complete_packet_is_compatible_and_competent(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path, successes=8)
    report = _assess(fixture)
    assert report["seal"]["status"] == "verified"
    assert report["bindings"]["contract_chain_verified"] is True
    assert len(report["bindings"]["contract_documents"]) == 4
    assert report["bindings"]["pilot_stats"]["bound"] is True
    assert report["bindings"]["dataset"]["bound"] and report["bindings"]["checkpoint"]["bound"]
    assert report["gate"]["status"] == "within"
    assert report["permission_and_custody"]["status"] == "pass", report["permission_and_custody"]
    assert report["permission_and_custody"]["recomputed"]["record_members"] == 4
    assert all(v == "pass" for v in report["verdicts"]["criteria"].values()), report["verdicts"]
    assert report["compatibility_checks"]["C9"]["statistics_equality"] == {
        "pilot_packet": True,
        "checkpoint": True,
    }
    assert report["replay"]["reproducibility"]["status"] == "agree"
    fidelity = report["replay"]["fidelity"]["attempts"]["R-1"]
    assert fidelity["status"] == "complete" and fidelity["faithful_through_step"] == T
    assert report["competence"]["successes"] == 8
    assert report["competence"]["outcomes"] == {"success": 8, "task_failure": 2}
    assert report["verdicts"]["Q-C_compatibility"] == "compatible"
    assert report["verdicts"]["Q-K_competence"] == "competent_for_development"
    assert report["disposition"] == "D3_qualified_and_competent"
    assert "disposition D3_qualified_and_competent" in assessor.render(report)


def test_broken_seal_or_unmanifested_member_invalidates_the_assessment(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    (store / "costs.json").write_text('{"R-1": {"wall_s": 2.0}}\n')
    report = _assess(fixture)
    assert report["seal"]["status"] == "differs"
    assert report["verdicts"]["Q-C_compatibility"] == "invalid"
    assert report["disposition"] == "invalid_packet"
    (store / "costs.json").write_text('{"R-1": {"wall_s": 1.0}}\n')
    _seal(store)
    _write(store / "000-runtime-identity.json", {"robosuite_version": "9.9"})
    report = _assess(fixture)
    assert report["seal"]["status"] == "verified"
    assert report["compatibility_checks"]["C1"]["status"] == "pass", "unmanifested member ignored"
    _seal(store)
    report = _assess(fixture)
    assert report["compatibility_checks"]["C1"]["missing_evidence"].endswith("ambiguous")
    assert report["verdicts"]["Q-C_compatibility"] == "unresolved"


def test_amendment_chain_and_effective_values_are_consumed(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    contract = assessor.load_effective_contract(fixture["contracts"])
    assert contract["effective"]["reset_determinism_seed"] == 900
    assert contract["chain_verified"]
    with pytest.raises(assessor.Malformed):
        assessor.load_effective_contract(fixture["contracts"][:2])
    truncated = assessor.load_effective_contract(fixture["contracts"][:3])
    assert truncated["chain_verified"] is False, "a truncated chain misses the frozen sequence"
    v1, v11, v12, v13 = fixture["contracts"]
    _edit_json(v11, lambda d: d.update({"note": "mutated"}))
    _edit_json(
        v13, lambda d: d.update({"amends": [a for a in d["amends"] if "v1.1" not in a["path"]]})
    )
    contract = assessor.load_effective_contract(fixture["contracts"])
    assert contract["chain_verified"] is False, "an unbound mutated intermediate invalidates"
    report = _assess(fixture)
    assert report["disposition"] == "invalid_contract_chain"


def test_incomplete_replays_cannot_qualify_compatibility(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    for attempt in ("R-1", "R-2"):
        _edit_json(store / f"replay-{attempt}.json", lambda d: d.update({"completed": False}))
    _seal(store)
    report = _assess(fixture)
    assert report["replay"]["reproducibility"]["status"] == "incomplete"
    assert report["compatibility_checks"]["C6"]["status"] == "unresolved"
    assert report["verdicts"]["Q-C_compatibility"] == "unresolved"
    assert report["disposition"] == "D1_materially_unresolved"
    assert report["verdicts"]["Q-K_competence"] == "reported_under_unqualified_runtime"


def test_replay_disagreement_names_the_element_and_keeps_competence_separate(
    tmp_path: Path,
) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]

    def bump(arrays: dict) -> None:
        arrays["obs__robot0_eef_pos"][2, 1] += 1e-9

    _edit_npz(store / "replay-R-2.npz", bump)
    _seal(store)
    report = _assess(fixture)
    reproducibility = report["replay"]["reproducibility"]
    assert reproducibility["status"] == "differ"
    assert reproducibility["differences"]["obs__robot0_eef_pos"]["index"] == [2, 1]
    assert report["verdicts"]["Q-C_compatibility"] == "incompatible"
    assert report["disposition"] == "D1_runtime_incompatible"
    assert report["competence"]["successes"] == 8, "competence counts stay reported"


def test_bindings_and_identity_are_required(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    report = _assess(fixture, pilot_stats=None, checkpoint=None, wheel=None)
    assert report["compatibility_checks"]["C9"]["status"] == "unresolved"
    assert report["bindings"]["checkpoint"]["bound"] is False
    assert report["permission_and_custody"]["status"] == "unresolved"
    assert report["verdicts"]["Q-C_compatibility"] == "unresolved"

    def drop_state(arrays: dict) -> None:
        del arrays["obs__object-state"]

    _edit_npz(store / "replay-R-1.npz", drop_state)
    _edit_json(
        store / "runtime-identity.json",
        lambda d: (d["packages"].pop("torch"), d.pop("mink_adaptation")),
    )
    _seal(store)
    report = _assess(fixture)
    assert report["compatibility_checks"]["C4"]["status"] == "unresolved"
    c1 = report["compatibility_checks"]["C1"]
    assert c1["status"] == "fail" and c1["mink_mode"] == "unaccounted"
    assert c1["checks"]["packages_complete"] is False


def test_policy_drift_and_action_contract_are_adjudicated(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    _edit_json(
        store / "policy-identity.json", lambda d: d.update({"parameter_sha256_after": "e" * 64})
    )
    _seal(store)
    report = _assess(fixture)
    assert report["competence"]["verdict"] == "invalid_evidence"
    assert report["disposition"] == "D1_materially_unresolved"
    _edit_json(
        store / "policy-identity.json", lambda d: d.update({"parameter_sha256_after": "d" * 64})
    )

    def widen(arrays: dict) -> None:
        arrays["actions"] = arrays["actions"].astype(np.float64)
        arrays["actions"][0, 0] = 2.0

    _edit_npz(store / "episode-E-200.npz", widen)
    _seal(store)
    report = _assess(fixture)
    row = report["competence"]["episodes"]["E-200"]
    assert row["outcome"] == "invalid_evidence" and "float64" in row["invalid_reason"]
    assert report["competence"]["successes"] == 7
    assert report["competence"]["verdict"] == "not_competent"
    assert report["disposition"] == "D2_qualified_not_competent"
    assert report["competence"]["episodes"]["E-201"]["components_outside_unit"] == 0


def test_double_normalization_fails_c9_and_fidelity_reports_the_first_divergence(
    tmp_path: Path,
) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    with np.load(store / "inference-stats.npz") as archive:
        stats = {k: archive[k] for k in archive.files}
    mean = stats["object__mean"].reshape(-1).astype(np.float64)
    std = stats["object__std"].reshape(-1)

    def double(arrays: dict) -> None:
        once = arrays["witness_consumed__object"].astype(np.float64)
        arrays["witness_consumed__object"] = rr.exact_normalize(once, mean, std).astype(np.float32)

    _edit_npz(store / "episode-E-201.npz", double)

    def diverge(arrays: dict) -> None:
        arrays["obs__object"][3, 0] += 0.5
        arrays["obs__object-state"][3, 0] += 0.5

    _edit_npz(store / "replay-R-1.npz", diverge)
    _seal(store)
    report = _assess(fixture)
    c9 = report["compatibility_checks"]["C9"]
    assert c9["status"] == "fail"
    assert c9["witnesses"]["E-201"]["single_application_bitwise"] is False
    assert c9["witnesses"]["E-200"]["status"] == "pass"
    fidelity = report["replay"]["fidelity"]["attempts"]["R-1"]
    assert fidelity["faithful_through_step"] == 2 and fidelity["first_divergence"]["step"] == 2
    assert report["replay"]["reproducibility"]["status"] == "differ"
    assert report["disposition"] == "D1_runtime_incompatible"


def test_gate_stop_needs_evidence_and_permission_is_separate(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    _write(store / "dependency-gate-001.json", {"stopped": True})
    _seal(store)
    report = _assess(fixture)
    assert report["gate"]["status"] == "unresolved"
    assert report["disposition"] == "D1_materially_unresolved"
    info = fixture["wheel_info"]
    ledger_sha = _sha(store / "source-ledger.v3.json")
    _edit_json(
        store / "dependency-gate-001.json",
        lambda d: d.update(
            {
                "route": "A",
                "wheel_url": WHEEL_URL,
                "wheel_sha256_expected": "0" * 64,
                "wheel_bytes_expected": info["bytes"],
                "downloaded_bytes": 0,
                "responses": {"consumed_before": 12, "used": 0, "cumulative_ceiling": 18},
                "ledger": {"path": "source-ledger.v3.json", "sha256": ledger_sha},
                "stop_mechanism": "storage_floor",
                "stop_reason": "free disk projection below the floor",
            }
        ),
    )
    _seal(store)
    report = _assess(fixture)
    assert report["gate"]["status"] == "unresolved", "a stop with the wrong pin is unresolved"
    _edit_json(
        store / "dependency-gate-001.json",
        lambda d: d.update({"wheel_sha256_expected": info["sha256"]}),
    )
    _seal(store)
    report = _assess(fixture)
    assert report["gate"]["status"] == "stopped"
    assert report["gate"]["stop_mechanism"] == "storage_floor"
    assert report["disposition"] == "G0_stopped_storage_floor"
    _edit_json(
        store / "dependency-gate-001.json",
        lambda d: d.update({"stopped": False, "downloaded_bytes": info["bytes"]}),
    )
    _edit_json(
        store / "acquisition-receipt-001.json",
        lambda d: d["license"].update({"declaration": "unknown"}),
    )
    _seal(store)
    report = _assess(fixture)
    assert report["permission_and_custody"]["checks"]["license_recognised"] is False
    assert report["disposition"] == "P0_not_qualified_permission_or_gate"


def test_custody_is_recomputed_from_the_wheel_not_declared(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    _edit_json(
        store / "runtime-identity.json",
        lambda d: d["packages"]["torch"].update({"sha256": "p" * 64}),
    )
    _seal(store)
    report = _assess(fixture)
    assert report["compatibility_checks"]["C1"]["checks"]["packages_complete"] is False
    _edit_json(
        store / "runtime-identity.json",
        lambda d: d["packages"]["torch"].update({"sha256": hashlib.sha256(b"torch").hexdigest()}),
    )
    (store / "source-ledger.v3.json").unlink()
    _seal(store)
    report = _assess(fixture)
    assert report["gate"]["ledger_member_verified"] is False
    assert report["gate"]["status"] == "differs"
    assert report["disposition"] == "P0_not_qualified_permission_or_gate"
    _write(store / "source-ledger.v3.json", {"schema": "ledger", "responses": 13})
    (store / "dist-info" / "LICENSE").write_text("All rights reserved.\n")
    _seal(store)
    report = _assess(fixture)
    assert report["permission_and_custody"]["checks"]["license_member_retained"] is False
    (store / "dist-info" / "LICENSE").write_text(MIT_TEXT)
    _seal(store)
    tampered = tmp_path / "tampered.whl"
    with zipfile.ZipFile(fixture["wheel"]) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "robosuite/__init__.py":
                data = b"__version__ = '1.5.1'  # tampered\n"
            dst.writestr(item, data)
    report = _assess(fixture, wheel=tampered)
    checks = report["permission_and_custody"]["checks"]
    assert checks["sha256_equal_retained_metadata"] is False
    assert checks["record_members_verified"] is False
    assert report["disposition"] == "P0_not_qualified_permission_or_gate"


def test_statistics_dtype_and_policy_checkpoint_binding_are_required(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    with np.load(store / "inference-stats.npz") as archive:
        arrays = {k: archive[k] for k in archive.files}
    arrays["object__mean"] = arrays["object__mean"].astype(np.float64)
    np.savez(store / "inference-stats.npz", **arrays)
    _seal(store)
    report = _assess(fixture)
    c9 = report["compatibility_checks"]["C9"]
    assert c9["statistics_equality"] == {"pilot_packet": False, "checkpoint": False}
    assert c9["status"] == "fail"
    assert report["disposition"] == "D1_runtime_incompatible"
    _stats_npz(store / "inference-stats.npz", _stats())
    _edit_json(store / "policy-identity.json", lambda d: d.update({"checkpoint_sha256": "0" * 64}))
    _seal(store)
    report = _assess(fixture)
    preconditions = report["competence"]["preconditions"]
    assert preconditions["policy_identity_names_the_effective_checkpoint"] is False
    assert report["competence"]["verdict"] == "invalid_evidence"
    _edit_json(
        store / "policy-identity.json",
        lambda d: d.update({"checkpoint_sha256": _sha(fixture["checkpoint"])}),
    )
    _edit_json(store / "episode-E-203.json", lambda d: d.update({"parameter_sha256": "f" * 64}))
    _seal(store)
    report = _assess(fixture)
    bound = report["competence"]["preconditions"]
    assert bound["every_started_episode_loaded_that_parameter_digest"] is False
    assert report["competence"]["verdict"] == "invalid_evidence"


def test_missing_episode_and_missing_evidence_are_distinguished(tmp_path: Path) -> None:
    fixture = build_packet(tmp_path)
    store = fixture["store"]
    (store / "episode-E-209.npz").unlink()
    (store / "episode-E-209.json").unlink()
    (store / "timing.json").unlink()
    _seal(store)
    report = _assess(fixture)
    competence = report["competence"]
    assert competence["started"] == 9 and competence["verdict"] == "unresolved"
    assert competence["episodes"]["E-209"]["outcome"] == "missing_evidence"
    assert report["compatibility_checks"]["C5"]["status"] == "unresolved"
    assert report["verdicts"]["Q-C_compatibility"] == "unresolved"
    assert report["disposition"] == "D1_materially_unresolved"


def test_cli_accepts_the_amendment_chain(tmp_path: Path) -> None:
    import subprocess
    import sys

    fixture = build_packet(tmp_path)
    out = tmp_path / "assessment.json"
    command = [
        sys.executable,
        "-m",
        "nisayon.evaluation",
        "a1-runtime-assess",
        str(fixture["store"]),
    ]
    for contract in fixture["contracts"]:
        command += ["--contract", str(contract)]
    command += [
        "--dataset",
        str(fixture["dataset"]),
        "--pilot-stats",
        str(fixture["pilot_stats"]),
        "--checkpoint",
        str(fixture["checkpoint"]),
        "--wheel",
        str(fixture["wheel"]),
        "--out",
        str(out),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "disposition D3_qualified_and_competent" in completed.stdout
    written = json.loads(out.read_text())
    assert [d["sha256"] for d in written["bindings"]["contract_documents"]] == [
        _sha(p) for p in fixture["contracts"]
    ]
