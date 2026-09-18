"""Timestamp actual robosuite sensor calls without changing their values.

Simulator time and host monotonic time are separate clocks. A composite policy
observation carries all component acquisition stamps and uses the oldest one
for its age obligation. Receiving a cached value does not recapture the sensor.
"""

from __future__ import annotations

import functools
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SensorStamp:
    sequence: int
    simulation_s: float
    host_started_s: float
    host_finished_s: float


@dataclass(frozen=True)
class CapturedObservation:
    step: int
    values: dict[str, Any]
    component_stamps: dict[str, SensorStamp]
    received_host_s: float

    @property
    def oldest_simulation_s(self) -> float:
        if not self.component_stamps:
            raise ValueError("Policy observation has no measured acquisition stamps")
        return min(stamp.simulation_s for stamp in self.component_stamps.values())

    def metadata(self) -> dict:
        return {
            "step": self.step,
            "oldest_capture_sim_time_s": self.oldest_simulation_s,
            "received_host_s": self.received_host_s,
            "components": {key: asdict(value) for key, value in self.component_stamps.items()},
        }


class SensorRecorder:
    """Instrument one environment instance, including sensors replaced by reset."""

    def __init__(self, env, *, host_origin: float):
        self.env = env
        self.host_origin = host_origin
        self.stamps: dict[str, SensorStamp] = {}
        self.sequence = 0
        original_update = env._update_observables

        @functools.wraps(original_update)
        def update(*args, **kwargs):
            # robosuite replaces sensor functions at hard reset. Wrap the actual
            # current callbacks immediately before the upstream update invokes them.
            for name, observable in env._observables.items():
                sensor = observable._sensor
                if getattr(sensor, "_nisayon_sensor_recorder", None) is not self:
                    observable._sensor = self._wrap(name, sensor)
            return original_update(*args, **kwargs)

        env._update_observables = update

    def _wrap(self, name, sensor):
        @functools.wraps(sensor)
        def acquired(*args, **kwargs):
            simulation = float(self.env.sim.data.time)
            begin = time.perf_counter() - self.host_origin
            value = sensor(*args, **kwargs)
            end = time.perf_counter() - self.host_origin
            if simulation != float(self.env.sim.data.time):
                raise RuntimeError("Simulator time advanced during one sensor callback")
            self.sequence += 1
            self.stamps[name] = SensorStamp(self.sequence, simulation, begin, end)
            return value

        acquired._nisayon_sensor_recorder = self
        return acquired

    def capture(
        self, observation: dict, policy_keys: list[str], *, step: int
    ) -> CapturedObservation:
        components = set()
        values = {}
        for key in policy_keys:
            actual_key = "object-state" if key == "object" else key
            values[key] = observation[actual_key].copy()
            if key == "object":
                components.update(
                    name
                    for name, item in self.env._observables.items()
                    if item.is_enabled() and item.is_active() and item.modality == "object"
                )
            else:
                components.add(key)
        missing = components - self.stamps.keys()
        if missing:
            raise ValueError(f"No actual sensor acquisition recorded for {sorted(missing)}")
        return CapturedObservation(
            step=step,
            values=values,
            component_stamps={key: self.stamps[key] for key in sorted(components)},
            received_host_s=time.perf_counter() - self.host_origin,
        )
