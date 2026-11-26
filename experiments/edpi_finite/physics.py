"""Small constant-force block experiment; all downstream states are recomputed."""

from __future__ import annotations

import math


def rollout(system: dict, task: dict, *, reset_id: str) -> dict:
    if any(
        type(system.get(k)) not in (int, float) or not math.isfinite(system[k]) or system[k] <= 0
        for k in ("mass_kg", "friction", "gain", "action_units_per_newton", "sensor_quantum_m")
    ):
        raise ValueError("physical parameters must be positive finite numbers")
    if (
        type(task.get("steps")) is not int
        or not 1 <= task["steps"] <= 100
        or type(task.get("distance_m")) not in (int, float)
        or not math.isfinite(task["distance_m"])
        or task["distance_m"] <= 0
        or type(task.get("origin_m")) not in (int, float)
        or not math.isfinite(task["origin_m"])
    ):
        raise ValueError("invalid finite task")
    if not isinstance(reset_id, str) or not reset_id.strip():
        raise ValueError("explicit reset identity required")
    mass, friction = system["mass_kg"], system["friction"]
    goal, steps = task["distance_m"], task["steps"]
    dt, gravity = 0.01, 9.81
    duration = steps * dt
    # The controller uses its declared nominal calibration, never actual dynamics.
    force = system["gain"] * (0.3 * gravity + 2 * goal / duration**2)
    encoded_force = force * system["action_units_per_newton"]
    applied_force = encoded_force / system["action_units_per_newton"]
    acceleration = max(0.0, applied_force / mass - friction * gravity)
    x, velocity = task["origin_m"], 0.0
    states = [[0.0, x, velocity]]
    for step in range(steps):
        x += velocity * dt + 0.5 * acceleration * dt**2
        velocity += acceleration * dt
        states.append([(step + 1) * dt, x, velocity])
    relative = x - task["origin_m"]
    quantum = system["sensor_quantum_m"]
    reading = round(relative / quantum) * quantum
    if not all(math.isfinite(v) for row in states for v in row):
        raise ValueError("nonfinite physical execution")
    return {
        "reset_id": reset_id,
        "initial_state": states[0],
        "states": states,
        "force_n": applied_force,
        "reading_m": reading,
        "measurement_error_m": quantum / 2 + 1e-12,
        "controls": steps,
        "wall_clock_realtime": False,
    }


def loss_interval(record: dict, task: dict) -> list[int]:
    y, error = record["reading_m"], record["measurement_error_m"]
    if not math.isfinite(y) or not math.isfinite(error) or error < 0:
        raise ValueError("invalid bounded measurement")
    low, high = y - error, y + error
    target, tolerance = task["distance_m"], 0.01
    if low >= target - tolerance and high <= target + tolerance:
        return [0, 0]
    if high < target - tolerance or low > target + tolerance:
        return [1, 1]
    return [0, 1]


def pair(reference: dict, candidate: dict, task: dict, *, reset_id: str) -> dict:
    old = rollout(reference, task, reset_id=reset_id + ":reference")
    new = rollout(candidate, task, reset_id=reset_id + ":candidate")
    if old["initial_state"] != new["initial_state"]:
        raise ValueError("invalid initial-state pairing")
    a, b = loss_interval(old, task), loss_interval(new, task)
    return {
        "reference": old,
        "candidate": new,
        "reference_loss": a,
        "candidate_loss": b,
        "difference": [b[0] - a[1], b[1] - a[0]],
        "controls": old["controls"] + new["controls"],
        "resets": 2,
        "pairing": "equal initial position/velocity and duration; no random simulation state",
    }
