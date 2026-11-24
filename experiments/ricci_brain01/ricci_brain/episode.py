"""Private simulation runner. This side owns seeds, scenario config and truth."""

import gzip
import hashlib
import json
import platform
import shutil
import subprocess
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

import mujoco
import numpy as np

from .evaluation import evaluate, measure
from .interfaces import Command, TaskIntent
from .model import fetch_reference, load_robot, load_scene
from .policy import Policy
from .sensing import SensorConfig, Transducers

HERE = Path(__file__).resolve().parents[1]
STATE = mujoco.mjtState.mjSTATE_INTEGRATION
PINNED_FILES = ["protocol.json", "reference.json", "uv.lock", "pyproject.toml", "campaign.json"]


def source_identity():
    paths = [*(HERE / "ricci_brain").glob("*.py"), *(HERE / name for name in PINNED_FILES)]
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


IMPORTED_SOURCES = {**source_identity()}


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state(model, data):
    result = np.zeros(mujoco.mj_stateSize(model, STATE))
    mujoco.mj_getState(model, data, result, STATE)
    return result


def run(
    output,
    *,
    sensor_seed=11,
    payload_mass=0.15,
    timestep=0.002,
    iterations=80,
    latency_s=0.004,
    noise_scale=1.0,
    friction=0.6,
    duration=13.0,
    task="lift_step_place",
    scenario="nominal",
    onset=4.5,
    slip_friction=0.04,
    arm="none",
    shared_action="shared",
    privileged_delay=0.0,
    dropout_duration=0.12,
    contact_time_constant=0.02,
):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)

    def source_stable():
        return IMPORTED_SOURCES == source_identity()

    if not source_stable():
        raise RuntimeError("source changed since module import")
    started = time.perf_counter()
    config = dict(
        sensor_seed=sensor_seed,
        payload_mass=payload_mass,
        timestep=timestep,
        iterations=iterations,
        latency_s=latency_s,
        noise_scale=noise_scale,
        friction=friction,
        duration=duration,
        task=task,
        scenario=scenario,
        onset=onset,
        slip_friction=slip_friction,
        arm=arm,
        shared_action=shared_action,
        privileged_delay=privileged_delay,
        dropout_duration=dropout_duration,
        contact_time_constant=contact_time_constant,
    )
    dump(output / "private-config.json", config)
    fetch_reference()
    protocol = json.loads((HERE / "protocol.json").read_text())
    dt = protocol["control_period_s"]
    if not np.isclose(dt / timestep, round(dt / timestep)):
        raise ValueError("noninteger physics/control clock ratio")
    nsub = round(dt / timestep)
    model, xml, q0 = load_scene(
        payload_mass=payload_mass,
        timestep=timestep,
        iterations=iterations,
        contact_time_constant=contact_time_constant,
    )
    # A single coherent sole friction is applied before initial state creation.
    for s in ["left", "right"]:
        for i in range(4):
            model.geom(f"{s}_sole_{i}").friction[0] = friction
    data = mujoco.MjData(model)
    data.qpos[:] = q0
    mujoco.mj_forward(model, data)
    rest_height = float(data.body("tray").xpos[2])
    mujoco.mj_saveModel(model, str(output / "model.mjb"), None)
    model_bytes = (output / "model.mjb").read_bytes()
    (output / "model.mjb.gz").write_bytes(gzip.compress(model_bytes, compresslevel=1, mtime=0))
    (output / "model.mjb").unlink()
    (output / "model.xml").write_text(xml)
    source = output / "source"
    source.mkdir()
    for path in sorted((HERE / "ricci_brain").glob("*.py")):
        shutil.copyfile(path, source / path.name)
    for name in PINNED_FILES:
        shutil.copyfile(HERE / name, source / name)
    reference, _ = load_robot(timestep=timestep, iterations=iterations)
    policy = Policy(reference, TaskIntent(kind=task), arm=arm, shared_action=shared_action)
    pending_command = Command(-1, tuple(policy.supervisor.last), False, "startup")
    data.ctrl[:] = pending_command.torque_nm
    mujoco.mj_forward(model, data)
    cfg = SensorConfig(
        latency_s=latency_s,
        gyro_sigma=0.001 * noise_scale,
        accel_sigma=0.025 * noise_scale,
        encoder_sigma=0.0001 * noise_scale,
        velocity_sigma=0.001 * noise_scale,
        force_sigma=0.12 * noise_scale,
        torque_sigma=0.01 * noise_scale,
    )
    sensors = Transducers(cfg, sensor_seed)
    dump(output / "sensor-config.json", asdict(cfg))
    queue = deque()
    observation = None
    rows = []
    states = [state(model, data)]
    truth = []
    environment = []
    sensor_data = mujoco.MjData(model)
    # Separate evaluator data prevents its forward calls changing live integration state.
    evaluator_data = mujoco.MjData(model)

    def measurement():
        mujoco.mj_setState(model, evaluator_data, state(model, data), STATE)
        mujoco.mj_forward(model, evaluator_data)
        return measure(model, evaluator_data, rest_height)

    truth.append(measurement())
    startup = time.perf_counter() - started
    failure = None
    with (
        (output / "policy.jsonl").open("w") as log,
        (output / "physics-prefix.jsonl").open("w") as prefix,
    ):
        prefix.write(
            json.dumps({"state": states[0].tolist(), "truth": truth[0]}, allow_nan=False) + "\n"
        )
        prefix.flush()
        for tick in range(round(duration / dt)):
            now = tick * dt
            while queue and queue[0].delivered_s <= now + 1e-10:
                observation = queue.popleft()
            private_mode = (
                scenario
                if arm in ["privileged", "fixed"] and now >= onset + privileged_delay
                else None
            )
            modeled_elapsed = (
                0.03 if scenario == "deadline" and onset <= now < onset + dropout_duration else dt
            )
            command, meta = policy.step(
                observation, tick, now, private_mode, modeled_elapsed_s=modeled_elapsed
            )
            applied_command = pending_command
            pending_command = command
            row = {
                "tick": tick,
                "t": now,
                "observation": None if observation is None else asdict(observation),
                "command": asdict(command),
                "applied_command": asdict(applied_command),
                **meta,
            }
            log.write(json.dumps(row, allow_nan=False) + "\n")
            log.flush()
            rows.append(row)
            # Physics advances under the previous command during the full
            # modeled computation/delivery period, identically for every arm.
            data.ctrl[:] = applied_command.torque_nm
            if now >= onset and scenario in ["slip", "compound", "same_response"]:
                for i in range(4):
                    model.geom(f"right_sole_{i}").friction[0] = slip_friction
            if now >= onset and scenario in ["load", "compound", "same_response"]:
                data.eq_active[model.equality("payload_lock").id] = False
            # Record every model-side change explicitly; no changed qpos or velocity.
            environment.append(
                {
                    "right_friction": float(model.geom("right_sole_0").friction[0]),
                    "payload_locked": bool(data.eq_active[model.equality("payload_lock").id]),
                }
            )
            if applied_command.release_fixture:
                for s in ["left", "right"]:
                    data.eq_active[model.equality(s + "_fixture").id] = False
            for sub in range(nsub):
                mujoco.mj_setState(model, sensor_data, state(model, data), STATE)
                mujoco.mj_forward(model, sensor_data)
                packet = sensors.capture(
                    model, sensor_data, tick * nsub + sub, now + sub * timestep
                )
                if (
                    scenario in ["dropout", "wrist_dropout"]
                    and onset <= packet.acquired_s < onset + dropout_duration
                ):
                    from dataclasses import replace

                    packet = replace(
                        packet,
                        valid=(False, False, False, False)
                        if scenario == "dropout"
                        else (True, True, True, False),
                    )
                if scenario == "stale" and onset <= packet.acquired_s < onset + dropout_duration:
                    from dataclasses import replace

                    packet = replace(packet, delivered_s=packet.delivered_s + 0.08)
                queue.append(packet)
                mujoco.mj_step(model, data)
            states.append(state(model, data))
            truth.append(measurement())
            prefix.write(
                json.dumps(
                    {
                        "state": states[-1].tolist(),
                        "truth": truth[-1],
                        "environment": environment[-1],
                    },
                    allow_nan=False,
                )
                + "\n"
            )
            prefix.flush()
            if meta["guard"]["terminate_unqualified"]:
                failure = "protective_continuation_exhausted"
                break
            if truth[-1]["pelvis"][2] < protocol["thresholds"]["fall_pelvis_height_m"]:
                failure = "fall"
                break
    np.savez_compressed(output / "physics.npz", states=np.array(states))
    dump(output / "truth.json", truth)
    dump(output / "environment.json", environment)
    result = evaluate(truth, protocol)
    result["execution_end"] = failure or "horizon"
    if failure and result["completed"]:
        raise AssertionError("incomplete episode cannot complete")
    result["timing"] = {
        "startup_wall_s": startup,
        "total_wall_s": time.perf_counter() - started,
        "policy_median_s": float(np.median([r["policy_wall_s"] for r in rows])),
        "policy_p99_s": float(np.quantile([r["policy_wall_s"] for r in rows], 0.99)),
        "missed_deadlines": sum("missed_deadline" in r["guard"]["reasons"] for r in rows),
        "host_wall_deadline_misses": sum(r["wall_deadline_missed"] for r in rows),
        "modeled_command_delay_s": dt,
        "hardware_realtime_qualified": False,
        "fallback_steps": sum(r["guard"]["mode"] != "accepted" for r in rows),
    }
    dump(output / "result.json", result)
    if not source_stable():
        raise RuntimeError("source changed during episode; prefix not sealed")
    manifest = {
        "schema": "ricci-brain01.episode.v2",
        "evidence_origin": "simulator",
        "execution_mode": "full_closed_loop",
        "simulator_version": mujoco.__version__,
        "state_spec": int(STATE),
        "physics_steps_per_command": nsub,
        "control_period_s": dt,
        "command_delivery_delay_s": dt,
        "rest_height": rest_height,
        "platform": platform.platform(),
        "model_uncompressed_bytes": len(model_bytes),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True
        ).strip(),
        "files": [
            {"path": str(p.relative_to(output)), "bytes": p.stat().st_size, "sha256": digest(p)}
            for p in sorted(output.rglob("*"))
            if p.is_file()
        ],
    }
    dump(output / "manifest.json", manifest)
    return result
