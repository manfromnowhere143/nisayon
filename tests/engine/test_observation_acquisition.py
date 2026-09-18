from types import SimpleNamespace

import pytest

from nisayon.engine.observations import SensorRecorder


class Observable:
    def __init__(self, sensor):
        self._sensor = sensor
        self.modality = "robot0"

    def is_enabled(self):
        return True

    def is_active(self):
        return True


class Environment:
    def __init__(self):
        self.sim = SimpleNamespace(data=SimpleNamespace(time=0.0))
        self._observables = {"robot0_eef_pos": Observable(lambda cache: [self.sim.data.time])}
        self.observation = {}

    def _update_observables(self, force=False):
        for name, observable in self._observables.items():
            self.observation[name] = observable._sensor({})


def test_receiving_stale_value_does_not_retimestamp_its_capture():
    env = Environment()
    recorder = SensorRecorder(env, host_origin=0)
    env.sim.data.time = 1.0
    env._update_observables()
    first = recorder.capture(env.observation, ["robot0_eef_pos"], step=0)
    env.sim.data.time = 2.0
    stale = recorder.capture(env.observation, ["robot0_eef_pos"], step=1)
    assert stale.oldest_simulation_s == first.oldest_simulation_s == 1.0
    assert env.sim.data.time - stale.oldest_simulation_s == 1.0
    assert stale.received_host_s >= first.received_host_s
    assert stale.component_stamps == first.component_stamps


def test_values_are_copied_and_new_reset_sensors_are_instrumented_once():
    env = Environment()
    recorder = SensorRecorder(env, host_origin=0)
    env._update_observables()
    first = recorder.capture(env.observation, ["robot0_eef_pos"], step=0)
    env.observation["robot0_eef_pos"][0] = 999
    assert first.values["robot0_eef_pos"] == [0.0]
    env._observables["robot0_eef_pos"]._sensor = lambda cache: [42]
    env.sim.data.time = 3.0
    env._update_observables()
    env._update_observables()
    final = recorder.capture(env.observation, ["robot0_eef_pos"], step=1)
    assert final.values["robot0_eef_pos"] == [42]
    assert final.component_stamps["robot0_eef_pos"].sequence == 3
    assert final.oldest_simulation_s == 3.0


def test_absent_capture_evidence_is_a_gap_instead_of_zero_age():
    env = Environment()
    recorder = SensorRecorder(env, host_origin=0)
    with pytest.raises(ValueError, match="No actual sensor acquisition"):
        recorder.capture({"robot0_eef_pos": [0]}, ["robot0_eef_pos"], step=0)


def test_sensor_that_advances_simulation_cannot_supply_a_point_timestamp():
    env = Environment()

    def advances(cache):
        env.sim.data.time += 1
        return [1]

    env._observables["robot0_eef_pos"]._sensor = advances
    SensorRecorder(env, host_origin=0)
    with pytest.raises(RuntimeError, match="advanced during one sensor"):
        env._update_observables()
