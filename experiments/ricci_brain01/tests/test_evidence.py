import json
from dataclasses import replace

import mujoco
import numpy as np
import pytest

from ricci_brain.analysis import action_latency, paired_interval
from ricci_brain.belief import HypothesisBank
from ricci_brain.control import WholeBodyController
from ricci_brain.episode import digest, run
from ricci_brain.interfaces import TaskIntent
from ricci_brain.model import initial_pose, load_robot, load_scene
from ricci_brain.replay import read_json, replay
from ricci_brain.sensing import SensorConfig, Transducers


def test_sole_friction_changes_effective_contact_not_only_metadata():
    m, _, q = load_scene()
    d = mujoco.MjData(m)
    d.qpos[:] = q
    d.qpos[2] -= 0.001
    ids = {m.geom(f"right_sole_{i}").id for i in range(4)}
    for i in ids:
        m.geom_friction[i, 0] = 0.04
    mujoco.mj_forward(m, d)
    contacts = [c for c in d.contact if {c.geom1, c.geom2} & ids]
    assert contacts and all(abs(c.friction[0] - 0.04) < 1e-12 for c in contacts)
    assert all(m.geom_priority[i] > m.geom("floor").priority for i in ids)


def test_payload_release_is_a_physical_generalized_force():
    m, _, q = load_scene()
    d = mujoco.MjData(m)
    d.qpos[:] = q
    joint = m.joint("payload_slide")
    address = joint.dofadr[0]
    d.eq_active[m.equality("payload_lock").id] = False
    mujoco.mj_forward(m, d)
    assert d.qfrc_passive[address] == pytest.approx(2.4)
    original = d.joint("payload_slide").qpos.copy()
    mujoco.mj_step(m, d)
    assert d.joint("payload_slide").qpos[0] > original[0]


def test_braking_envelope_infeasibility_returns_refusal():
    m, _ = load_robot()
    c = WholeBodyController(m)
    q = initial_pose(m)
    v = np.zeros(m.nv)
    v[6:] = 100
    torque, meta = c.solve(q, v, 0, TaskIntent())
    assert not meta["ok"] and meta["status"] == "infeasible_braking_envelope"
    assert np.all(np.isfinite(torque))


def test_compound_and_missing_measurements_remain_unknown():
    m, _, q = load_scene()
    d = mujoco.MjData(m)
    d.qpos[:] = q
    mujoco.mj_forward(m, d)
    obs = Transducers(SensorConfig(), 1).capture(m, d, 0, 0)
    bank = HypothesisBank()
    estimate = {"innovations": [{"nis": 100.0, "velocity_residual": [1, 0, 0]}]}
    bank.update(obs, estimate)
    moved = replace(obs, wrist_wrench=tuple(tuple(x + 20 for x in w) for w in obs.wrist_wrench))
    b = bank.update(moved, estimate)
    assert b["mode"] == "unknown_compound" and not b["calibrated_probabilities"]
    assert (
        bank.update(replace(moved, valid=(True, True, True, False)), estimate)["mode"]
        == "unknown_degraded"
    )


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    root = tmp_path_factory.mktemp("evidence") / "episode"
    run(root, duration=0.08)
    return root


def test_recorded_physics_sensors_and_verdict_reproduce(evidence):
    result = replay(evidence)
    assert result["max_state_error"] == 0
    assert result["sensor_replay"] == "matched"
    assert not result["evaluation"]["completed"]


def test_sensor_tamper_rejected_even_if_bytes_are_resealed(evidence, tmp_path):
    import shutil

    copy = tmp_path / "tamper"
    shutil.copytree(evidence, copy)
    path = copy / "policy.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["observation"]["specific_force"][0] += 1
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    manifest = json.loads((copy / "manifest.json").read_text())
    entry = next(e for e in manifest["files"] if e["path"] == "policy.jsonl")
    entry.update(bytes=path.stat().st_size, sha256=digest(path))
    (copy / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="sensor replay mismatch"):
        replay(copy)


@pytest.mark.parametrize("content", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e-9999}'])
def test_json_integrity_failures(tmp_path, content):
    p = tmp_path / "bad.json"
    p.write_text(content)
    with pytest.raises(ValueError):
        read_json(p)


def test_zero_discordance_does_not_report_zero_uncertainty():
    result = paired_interval([True] * 4, [True] * 4)
    assert result["difference"] == 0
    assert result["conservative_95_interval"][0] < -0.5
    assert result["conservative_95_interval"][1] > 0.5


def test_classifier_time_is_not_effective_action_time():
    reference = [
        {
            "t": i * 0.02,
            "observation": None,
            "applied_command": {"torque_nm": [0.0], "disposition": "accepted"},
            "decision_time_s": None,
            "guard": {"mode": "accepted"},
        }
        for i in range(5)
    ]
    rows = json.loads(json.dumps(reference))
    for row in rows[1:]:
        row["decision_time_s"] = 0.02
    rows[3]["applied_command"]["torque_nm"] = [1.0]
    result = action_latency(reference, rows, 0.002)
    assert result["decision_to_effective_s"] == pytest.approx(0.042)


def test_scenario_seed_path_and_reset_do_not_enter_policy_stream(tmp_path, monkeypatch):
    # A deterministic clock removes host scheduling as an alternate treatment.
    monkeypatch.setattr("ricci_brain.policy.time.perf_counter", lambda: 0.0)
    a = tmp_path / "nominal-seed-labelled"
    b = tmp_path / "slip-private-label"
    run(a, duration=0.08, scenario="nominal", sensor_seed=191)
    import itertools

    counter = itertools.count()
    monkeypatch.setattr("ricci_brain.policy.time.perf_counter", lambda: float(next(counter)))
    run(b, duration=0.08, scenario="slip", onset=4.5, sensor_seed=191)

    def inputs(path):
        return [
            {k: r[k] for k in ["tick", "t", "observation", "command", "applied_command"]}
            for r in map(json.loads, (path / "policy.jsonl").read_text().splitlines())
        ]

    assert inputs(a) == inputs(b)
    assert json.loads((b / "result.json").read_text())["timing"]["host_wall_deadline_misses"] > 0


@pytest.mark.parametrize(
    "scenario,reason", [("deadline", "missed_deadline"), ("stale", "stale_packet")]
)
def test_modeled_runtime_faults_replay_and_remain_unqualified(tmp_path, scenario, reason):
    root = tmp_path / scenario
    result = run(root, scenario=scenario, onset=0.08, duration=0.3)
    rows = [json.loads(line) for line in (root / "policy.jsonl").read_text().splitlines()]
    assert any(reason in r["guard"]["reasons"] for r in rows)
    assert result["censored"] and not result["protective_stop"]
    assert replay(root)["sensor_replay"] == "matched"


def test_one_control_period_command_delivery(evidence):
    rows = [json.loads(line) for line in (evidence / "policy.jsonl").read_text().splitlines()]
    assert rows[0]["applied_command"]["tick"] == -1
    for before, after in zip(rows, rows[1:], strict=False):
        assert after["applied_command"] == before["command"]
