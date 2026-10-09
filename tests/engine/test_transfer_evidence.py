"""Labelled software controls, never additional robot or confirmation evidence."""

import io
import json
import subprocess
import sys

import numpy as np
import pytest

from nisayon.engine import transfer_evidence as evidence


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


@pytest.fixture
def packet(tmp_path, monkeypatch):
    root = tmp_path / "raw"
    root.mkdir()
    files, records = {}, []
    for seed in evidence.SEEDS:
        for mode in ("unchanged", "corrected"):
            success = mode == "corrected" and seed != 180104
            steps = 2 if success else 400
            n = steps + 1
            obj = np.zeros((n, 10), dtype=np.float64)
            obj[:, :3] = [0.1, 0.2, 0.82]
            obj[:, 6] = 1
            if success:
                obj[-1, 2] = 0.85
            eef = np.tile([0.3, 0.4, 1.0], (n, 1))
            obj[:, 7:10] = obj[:, :3] - eef
            obs = {
                "object": obj,
                "robot0_eef_pos": eef,
                "robot0_eef_quat": np.tile([0.0, 0.0, 0.0, 1.0], (n, 1)),
                "robot0_gripper_qpos": np.zeros((n, 2)),
            }
            flags = np.zeros(n, dtype=bool)
            flags[-1] = success
            states = np.zeros((n, 32))
            states[:, 0] = np.arange(n) * 0.05
            intended = np.full((steps, 7), 1.2, dtype=np.float32)
            arrays = {
                "states": states,
                "sim_time": states[:, 0].copy(),
                "cube_z": obj[:, 2].copy(),
                "table_z": np.full(n, 0.8),
                "success": flags,
                "reward": flags.astype(np.float64),
                "intended_actions": intended,
                "actions": np.ones((steps, 7), dtype=np.float32),
                "obs__object-state": obj.copy(),
                **{f"obs__{key}": value for key, value in obs.items()},
            }
            for key, value in obs.items():
                passed = value[:-1].copy()
                if mode == "corrected" and key == "object":
                    passed[:, 7:10] *= -1
                arrays[f"policy_obs__{key}"] = passed
                arrays[f"network_input__{key}"] = passed.astype(np.float32)
            stem = f"paired-execution/{seed}-{mode}"
            xml = b"<labelled-software-fixture/>"
            initial = {
                "state_and_observation_sha256": evidence._array_digest(
                    {"state": states[0], **{key: value[0] for key, value in obs.items()}}
                ),
                "model_sha256": evidence._sha(xml),
                "controller": {"goal_pos": None},
                "uncaptured": "synthetic fixture; no simulator",
            }
            buffer = io.BytesIO()
            np.savez_compressed(buffer, **arrays)
            data = buffer.getvalue()
            row = {
                "seed": seed,
                "mode": mode,
                "failure": None,
                "steps": steps,
                "outcome": "success" if success else "task_failure",
                "trace_sha256": evidence._sha(data),
                "initial_condition_sha256": evidence._sha(
                    json.dumps(initial, sort_keys=True).encode()
                ),
                "clipped_components": steps * 7,
                "max_cube_above_table_m": float(np.max(obj[:, 2] - 0.8)),
            }
            files[stem + ".npz"] = data
            files[stem + ".json"] = encoded(row)
            files[stem + "-initial.json"] = encoded(initial)
            files[stem + ".xml"] = xml
            records.append(row)
    steps = 4418
    result = {
        "schema": "nisayon.b2-transfer.result.v1",
        "case": evidence.CASE,
        "protocol_sha256": evidence.PROTOCOL_SHA256,
        "assessment_mode": "single_lane_non_independent",
        "completed": True,
        "episodes": records,
        "verdict": {
            "paired_conditions": 10,
            "unchanged_successes": 0,
            "corrected_successes": 9,
            "paired_repairs": 9,
            "paired_regressions": 0,
            "execution_failures": 0,
            "all_captured_initial_conditions_equal": True,
            "required_paired_repairs": 8,
            "supported": True,
        },
        "parameter_sha256_before": evidence.WEIGHTS_SHA256,
        "parameter_sha256_after": evidence.WEIGHTS_SHA256,
        "operations": {
            "control_calls_completed": steps,
            "control_calls_started": steps,
            "policy_calls_started": steps,
            "environment_constructions_started": 20,
            "explicit_env_resets_started": 20,
            "state_assignments_started": 0,
            "xml_resets_started": 0,
        },
        "contract_physics_substeps_upper": steps * 25,
    }
    protocol = {
        "case": evidence.CASE,
        "seeds": list(evidence.SEEDS),
        "criteria": {"paired_repairs_at_least": 8},
    }
    protocol_bytes = encoded(protocol)
    monkeypatch.setattr(evidence, "PROTOCOL_SHA256", evidence._sha(protocol_bytes))
    result["protocol_sha256"] = evidence.PROTOCOL_SHA256
    files["paired-execution/result.json"] = encoded(result)
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
    manifest = {
        "schema": "nisayon.artifact_manifest.v1",
        "files": {name: evidence._sha(data) for name, data in files.items()},
        "file_sizes": {name: len(data) for name, data in files.items()},
    }
    manifest_bytes = encoded(manifest)
    (root / "artifact-manifest.json").write_bytes(manifest_bytes)
    monkeypatch.setattr(evidence, "MANIFEST_SHA256", evidence._sha(manifest_bytes))
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_bytes(protocol_bytes)
    return root, protocol_path, files, protocol


def test_recompute_from_arrays_preserves_failure_and_relocates(packet, tmp_path):
    root, protocol, _, _ = packet
    first = evidence.inspect_transfer(root, protocol)
    assert first["integrity"] == "verified", first
    assert first["recomputed"]["network_input_array_witnesses_checked"] == 17672
    assert first["recomputed"]["verdict"]["corrected_successes"] == 9
    assert first["recomputed"]["pairs"][4]["corrected_success"] is False
    relocated = tmp_path / "renamed"
    root.rename(relocated)
    assert evidence.inspect_transfer(relocated, protocol) == first


@pytest.mark.parametrize("part", ["protocol", "manifest", "member", "missing", "symlink"])
def test_inconsistent_or_missing_packet_never_grants_support(packet, part, tmp_path):
    root, protocol, _, _ = packet
    member = root / "paired-execution/180100-corrected.npz"
    if part == "protocol":
        protocol.write_text("{}")
    elif part == "manifest":
        (root / "artifact-manifest.json").write_text("{}")
    elif part == "member":
        data = member.read_bytes()
        member.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    elif part == "missing":
        member.unlink()
    else:
        external = tmp_path / "external.npz"
        member.rename(external)
        member.symlink_to(external)
    result = evidence.inspect_transfer(root, protocol)
    assert result["integrity"] == ("incomplete" if part == "missing" else "invalid")
    assert result["decision"] == "unresolved"
    assert result["recomputed"] is None


@pytest.mark.parametrize(
    ("array", "mutation", "message"),
    [
        ("network_input__object", "wrong", "network input mismatch"),
        ("policy_obs__object", "wrong", "policy input mismatch"),
        ("policy_obs__robot0_eef_pos", "wrong", "policy input mismatch"),
        ("network_input__robot0_eef_quat", "drop", "invalid trace array"),
        ("obs__object-state", "wrong", "raw object observation mismatch"),
        ("reward", "wrong", "height, success and reward"),
        ("success", "wrong", "height, success and reward"),
        ("actions", "wrong", "executed actions"),
        ("states", "wrong", "control clock"),
        ("sim_time", "wrong", "control clock"),
        ("network_input__object", "dtype", "invalid trace array"),
        ("intended_actions", "nan", "invalid trace array"),
    ],
)
def test_semantic_checks_reject_rehashed_bad_arrays(packet, array, mutation, message):
    _, _, files, _ = packet
    stem = "paired-execution/180100-corrected"
    arrays = evidence._arrays(files[stem + ".npz"])
    if mutation == "drop":
        arrays[array] = arrays[array][:-1]
    elif mutation == "dtype":
        arrays[array] = arrays[array].astype(np.float64)
    elif mutation == "nan":
        arrays[array].flat[0] = np.nan
    else:
        arrays[array].flat[0] += 1
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    files[stem + ".npz"] = buffer.getvalue()
    row = evidence._json(files[stem + ".json"])
    row["trace_sha256"] = evidence._sha(files[stem + ".npz"])
    files[stem + ".json"] = encoded(row)
    with pytest.raises(ValueError, match=message):
        evidence._episode(files, 180100, "corrected")


@pytest.mark.parametrize(
    "field", ["verdict", "episodes", "weights", "operations", "controller", "model"]
)
def test_producer_claims_and_initial_bindings_are_checked(packet, field):
    _, _, files, protocol = packet
    result = evidence._json(files["paired-execution/result.json"])
    if field == "verdict":
        result["verdict"]["corrected_successes"] = 10
    elif field == "episodes":
        result["episodes"].pop()
    elif field == "weights":
        result["parameter_sha256_after"] = "0" * 64
    elif field == "operations":
        result["operations"]["control_calls_completed"] += 1
    elif field == "controller":
        key = "paired-execution/180100-corrected-initial.json"
        initial = evidence._json(files[key])
        initial["controller"]["goal_pos"] = [1, 2, 3]
        files[key] = encoded(initial)
    else:
        files["paired-execution/180100-corrected.xml"] = b"changed"
    files["paired-execution/result.json"] = encoded(result)
    with pytest.raises(ValueError):
        evidence._recompute(files, protocol)


def test_seven_repairs_do_not_meet_the_frozen_obligation(packet):
    _, _, files, protocol = packet
    result = evidence._json(files["paired-execution/result.json"])
    for index, seed in [(1, 180100), (3, 180101)]:
        source = "paired-execution/180104-corrected"
        target = f"paired-execution/{seed}-corrected"
        for suffix in (".npz", "-initial.json", ".xml"):
            files[target + suffix] = files[source + suffix]
        row = evidence._json(files[source + ".json"])
        row["seed"] = seed
        files[target + ".json"] = encoded(row)
        result["episodes"][index] = row
    result["verdict"].update(corrected_successes=7, paired_repairs=7, supported=False)
    # Two previously two-step successes each become full 400-step failures.
    for key in ("control_calls_started", "control_calls_completed", "policy_calls_started"):
        result["operations"][key] += 796
    result["contract_physics_substeps_upper"] += 796 * 25
    files["paired-execution/result.json"] = encoded(result)
    recomputed = evidence._recompute(files, protocol)
    assert recomputed["verdict"]["supported"] is False
    assert recomputed["verdict"]["paired_repairs"] == 7


def test_internally_bound_but_unequal_initial_states_do_not_support_repair(packet):
    _, _, files, protocol = packet
    key = "paired-execution/180100-corrected"
    initial = evidence._json(files[key + "-initial.json"])
    initial["controller"]["goal_pos"] = [1, 2, 3]
    files[key + "-initial.json"] = encoded(initial)
    row = evidence._json(files[key + ".json"])
    row["initial_condition_sha256"] = evidence._sha(json.dumps(initial, sort_keys=True).encode())
    files[key + ".json"] = encoded(row)
    result = evidence._json(files["paired-execution/result.json"])
    result["episodes"][1] = row
    result["verdict"].update(all_captured_initial_conditions_equal=False, supported=False)
    files["paired-execution/result.json"] = encoded(result)
    recomputed = evidence._recompute(files, protocol)
    assert recomputed["verdict"]["supported"] is False
    assert recomputed["verdict"]["paired_repairs"] == 9


@pytest.mark.parametrize("name", ["../other", "/absolute", "a/../b", "a//b", "a\\b", ""])
def test_manifest_paths_cannot_escape_or_alias(tmp_path, name):
    with pytest.raises(ValueError, match="unsafe"):
        evidence._member(tmp_path, name)


def test_duplicate_json_and_object_arrays_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        evidence._json(b'{"verdict": false, "verdict": true}')
    buffer = io.BytesIO()
    np.savez(buffer, unsafe=np.array([None], dtype=object))
    with pytest.raises(ValueError, match="Object arrays"):
        evidence._arrays(buffer.getvalue())


def test_cli_works_outside_repository_and_does_not_import_execution_stack(tmp_path):
    code = """
import importlib.abc
import sys
class NoExecution(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.split('.')[0] in {'torch', 'mujoco', 'robosuite', 'robomimic'}:
            raise AssertionError('execution dependency imported: ' + fullname)
sys.meta_path.insert(0, NoExecution())
from nisayon.cli import main
main()
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            "verify-lift-transfer",
            "--packet",
            "missing",
            "--protocol",
            "missing.json",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["integrity"] == "incomplete"


def test_cli_derived_output_cannot_enter_packet_or_replace_input(packet, monkeypatch, capsys):
    from nisayon.cli import main

    root, protocol, _, _ = packet
    for output in [root / "report.json", protocol]:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "nisayon",
                "verify-lift-transfer",
                "--packet",
                str(root),
                "--protocol",
                str(protocol),
                "--out",
                str(output),
            ],
        )
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
        assert "outside the raw packet" in capsys.readouterr().err
    output = root.parent / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nisayon",
            "verify-lift-transfer",
            "--packet",
            str(root),
            "--protocol",
            str(protocol),
            "--out",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 0
    original = output.read_bytes()
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert output.read_bytes() == original
