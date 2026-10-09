"""No-physics boundary controls for the case-specific controller intervention."""

import json
from types import SimpleNamespace

import pytest

from nisayon.engine.configuration import Deployment
from nisayon.engine.diagnostics import configuration_difference, deployment_from_record
from nisayon.engine.io import digest


def test_legacy_configuration_bytes_stay_bound_to_retained_evidence():
    from pathlib import Path

    path = Path("docs/experiments/results/development-ablation-001/frozen-suite.json")
    suite = json.loads(path.read_text())
    # The compatibility premise is real retained configuration identity, rather
    # than another literal copy of the new implementation's defaults.
    for incident in suite["cases"]:
        for name in ("working", "changed"):
            old = incident["frozen"][name]
            assert deployment_from_record(old).record() == old
            assert digest(old) == incident["frozen"][name + "_digest"]


def test_explicit_target_is_round_trippable_and_changes_candidate_identity():
    restored = Deployment(controller_target="restored")
    nominal = Deployment(controller_target="nominal")
    assert deployment_from_record(nominal.record()) == nominal
    assert digest(restored.record()) != digest(nominal.record())
    assert configuration_difference(Deployment(), restored) == {}
    assert configuration_difference(Deployment(), nominal) == {
        "controller_target": {"working": "restored", "changed": "nominal"}
    }
    assert configuration_difference(nominal, Deployment()) == {
        "controller_target": {"working": "nominal", "changed": "restored"}
    }


@pytest.mark.parametrize("value", [True, {}, [], 1, "random"])
def test_unknown_target_is_rejected_before_execution(value):
    with pytest.raises(ValueError, match="Controller target"):
        Deployment(controller_target=value)


@pytest.mark.parametrize("height", [None, float("nan"), True])
def test_missing_progress_cannot_become_zero_in_the_pair_scorer(tmp_path, height):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "controller_target_probe", Path("scripts/experiments/controller_target_probe.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    incomplete = {
        "process_status": "completed",
        "measurement_status": "observed",
        "task_outcome": "failed",
        "trace": [{"cube_height_m": height}],
    }
    with pytest.raises(ValueError, match="Missing/nonfinite progress"):
        module.audit_pairs(tmp_path, [incomplete, incomplete])


def test_nominal_intervention_calls_controller_without_changing_restored_state():
    np = pytest.importorskip("numpy")
    pytest.importorskip("robosuite")
    pytest.importorskip("robomimic")
    from nisayon.engine.lift import configure_controller_target

    nominal = np.arange(7, dtype=float)
    qpos = nominal + 0.02
    calls = []
    controller = SimpleNamespace(initial_joint=qpos.copy())

    def update(target):
        calls.append(target.copy())
        controller.initial_joint = target.copy()

    controller.update_initial_joints = update
    env = SimpleNamespace(
        robots=[
            SimpleNamespace(
                controller=controller, init_qpos=nominal, _ref_joint_pos_indexes=list(range(7))
            )
        ],
        sim=SimpleNamespace(data=SimpleNamespace(qpos=qpos.copy())),
    )
    before = env.sim.data.qpos.copy()
    restored = configure_controller_target(env, "restored")
    assert len(calls) == 1
    np.testing.assert_array_equal(calls[0], before)
    assert restored["target_minus_restored_rad"] == [0.0] * 7
    result = configure_controller_target(env, "nominal")
    assert len(calls) == 2
    np.testing.assert_array_equal(calls[1], nominal)
    np.testing.assert_array_equal(env.sim.data.qpos, before)
    assert result["target_minus_nominal_rad"] == [0.0] * 7
    # A controller that ignores the request must not produce a declared success.
    controller.initial_joint = qpos.copy()
    controller.update_initial_joints = lambda target: None
    with pytest.raises(ValueError, match="does not match"):
        configure_controller_target(env, "nominal")
