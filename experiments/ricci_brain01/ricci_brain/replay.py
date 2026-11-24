"""Data-only replay: never imports retained producer code or reruns the policy."""

import gzip
import hashlib
import json
import tempfile
from collections import deque
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

import mujoco
import numpy as np

from .evaluation import evaluate, measure
from .interfaces import observation_from_dict, valid_packet
from .sensing import SensorConfig, Transducers


def read_json(path):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError("duplicate JSON key")
            out[k] = v
        return out

    def finite(x):
        v = float(x)
        if not np.isfinite(v) or (v == 0 and Decimal(x) != 0):
            raise ValueError("nonfinite or underflow JSON")
        return v

    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=pairs,
        parse_float=finite,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
    )


def replay(root):
    root = Path(root).resolve()
    manifest = read_json(root / "manifest.json")
    if manifest["schema"] != "ricci-brain01.episode.v2":
        raise ValueError("unsupported development packet schema; v2 replay required")
    names = set()
    for entry in manifest["files"]:
        p = Path(entry["path"])
        if p.is_absolute() or ".." in p.parts or str(p) in names:
            raise ValueError("unsafe or duplicate member")
        names.add(str(p))
        target = root / p
        if any(
            parent.is_symlink() for parent in [target, *target.parents] if parent != root.parent
        ):
            raise ValueError("symlink")
        content = target.read_bytes()
        if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"digest mismatch {p}")
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if actual != names | {"manifest.json"}:
        raise ValueError("file-set mismatch")
    if manifest["simulator_version"] != mujoco.__version__:
        raise ValueError("MuJoCo version mismatch")
    protocol = read_json(root / "source/protocol.json")
    config = read_json(root / "private-config.json")
    sensors = Transducers(
        SensorConfig(**read_json(root / "sensor-config.json")), config["sensor_seed"]
    )
    queue = deque()
    observation = None
    recorded = read_json(root / "truth.json")
    claimed = read_json(root / "result.json")
    rows = [json.loads(line) for line in (root / "policy.jsonl").read_text().splitlines()]
    environment = read_json(root / "environment.json")
    with np.load(root / "physics.npz", allow_pickle=False) as arrays:
        states = arrays["states"]
    if (
        len(states) != len(rows) + 1
        or len(recorded) != len(states)
        or len(environment) != len(rows)
    ):
        raise ValueError("incomplete trace")
    if not np.all(np.isfinite(states)):
        raise ValueError("nonfinite physics")
    expected_bytes = manifest["model_uncompressed_bytes"]
    if not 0 < expected_bytes < 120_000_000:
        raise ValueError("model size limit")
    with gzip.open(root / "model.mjb.gz", "rb") as stream:
        binary = stream.read(expected_bytes + 1)
    if len(binary) != expected_bytes:
        raise ValueError("model length mismatch")
    with tempfile.TemporaryDirectory(prefix="ricci-replay-") as directory:
        binary_path = Path(directory) / "model.mjb"
        binary_path.write_bytes(binary)
        m = mujoco.MjModel.from_binary_path(str(binary_path))
    d = mujoco.MjData(m)
    ev = mujoco.MjData(m)
    sensor_data = mujoco.MjData(m)
    spec = mujoco.mjtState(manifest["state_spec"])
    mujoco.mj_setState(m, d, states[0], spec)
    truth = []
    max_error = 0.0

    def measurement():
        current = np.zeros_like(states[0])
        mujoco.mj_getState(m, d, current, spec)
        mujoco.mj_setState(m, ev, current, spec)
        mujoco.mj_forward(m, ev)
        return measure(m, ev, manifest["rest_height"])

    truth.append(measurement())
    for i, row in enumerate(rows):
        if row["tick"] != i or abs(row["t"] - i * manifest["control_period_s"]) > 1e-10:
            raise ValueError("command clock discontinuity")
        obs = row["observation"]
        while queue and queue[0].delivered_s <= row["t"] + 1e-10:
            observation = queue.popleft()
        expected = None if observation is None else json.loads(json.dumps(asdict(observation)))
        if obs != expected:
            raise ValueError(f"sensor replay mismatch at {i}")
        if obs is not None and not valid_packet(observation_from_dict(obs.copy()), row["t"]):
            raise ValueError("invalid observed packet")
        if obs is not None and obs["delivered_s"] > row["t"] + 1e-10:
            raise ValueError("future observation consumed")
        applied = row["applied_command"]
        if i and applied != rows[i - 1]["command"]:
            raise ValueError("command delivery schedule mismatch")
        if not i and (
            applied["tick"] != -1
            or applied["release_fixture"]
            or not np.array_equal(applied["torque_nm"], d.ctrl)
        ):
            raise ValueError("startup command mismatch")
        d.ctrl[:] = applied["torque_nm"]
        for j in range(4):
            m.geom(f"right_sole_{j}").friction[0] = environment[i]["right_friction"]
        d.eq_active[m.equality("payload_lock").id] = environment[i]["payload_locked"]
        if applied["release_fixture"]:
            for side in ["left", "right"]:
                d.eq_active[m.equality(side + "_fixture").id] = False
        for sub in range(manifest["physics_steps_per_command"]):
            current = np.zeros_like(states[0])
            mujoco.mj_getState(m, d, current, spec)
            mujoco.mj_setState(m, sensor_data, current, spec)
            mujoco.mj_forward(m, sensor_data)
            packet = sensors.capture(
                m,
                sensor_data,
                i * manifest["physics_steps_per_command"] + sub,
                row["t"] + sub * m.opt.timestep,
            )
            if (
                config["scenario"] in ["dropout", "wrist_dropout"]
                and config["onset"]
                <= packet.acquired_s
                < config["onset"] + config["dropout_duration"]
            ):
                packet = replace(
                    packet,
                    valid=(False, False, False, False)
                    if config["scenario"] == "dropout"
                    else (True, True, True, False),
                )
            if (
                config["scenario"] == "stale"
                and config["onset"]
                <= packet.acquired_s
                < config["onset"] + config["dropout_duration"]
            ):
                packet = replace(packet, delivered_s=packet.delivered_s + 0.08)
            queue.append(packet)
            mujoco.mj_step(m, d)
        current = np.zeros_like(states[0])
        mujoco.mj_getState(m, d, current, spec)
        error = float(np.max(abs(current - states[i + 1])))
        max_error = max(max_error, error)
        if error > 1e-10:
            raise ValueError(f"physics replay divergence at {i}: {error}")
        truth.append(measurement())
    if truth != recorded:
        raise ValueError("truth measurement mismatch")
    result = evaluate(truth, protocol)
    for key, value in result.items():
        if claimed.get(key) != value:
            raise ValueError(f"producer verdict mismatch: {key}")
    return {
        "integrity": "verified",
        "physics_replay": "matched",
        "commands": len(rows),
        "physics_steps": len(rows) * manifest["physics_steps_per_command"],
        "max_state_error": max_error,
        "evaluation": result,
        "sensor_replay": "matched",
        "boundary": "recorded-action physics replay; not a changed-policy counterfactual",
    }
