"""Post-freeze record controls, supplementing (never replacing) the v1 audit.

No selector or simulator imports. The original frozen audit remains available
so its metadata omissions and the later controls are reproducible.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction as Q

from audit_campaign import audit_trial, bounds


def decode(raw: bytes | str) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"nonfinite JSON: {value}")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def numeric(value: object) -> Q:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite numeric value required, excluding booleans")
    return Q(str(value))


def strict_trial(row: dict, case: dict, protocol: dict) -> dict:
    if (
        row["schema"] != "nisayon.edpi.trial.v1"
        or row["case"] != case["id"]
        or row["method"] not in protocol["methods"]
        or row["budget"] not in protocol["budgets_control_steps"]
        or type(row["number"]) is not int
        or row["number"] < 0
        or row["seed"] not in (protocol["random_seeds"] if row["method"] == "random" else [0])
    ):
        raise ValueError("invalid assigned trial identity")
    if (
        row["probe_pairs"] != len(row["raw"])
        or row["confirmation_pairs"] != len(row["confirmation_raw"])
        or row["reused_pairs"] != 0
    ):
        raise ValueError("inconsistent experiment counts")
    for key in ("wall_seconds", "selector_seconds_including_startup_ipc"):
        if numeric(row[key]) < 0:
            raise ValueError("negative resource measurement")
    resets = set()
    for stage, name in (("", "raw"), ("confirmation:", "confirmation_raw")):
        for item in row[name]:
            task, pair = item["task"], item["pair"]
            for role in ("reference", "candidate"):
                record, system = pair[role], case[role]
                identity = f"trial-{row['number']}:{stage}{task['id']}:{role}"
                if record["reset_id"] != identity or identity in resets:
                    raise ValueError("reset identity or stage mismatch")
                resets.add(identity)
                if record["initial_state"] != record["states"][0]:
                    raise ValueError("initial-state metadata differs from trajectory")
                if type(record["controls"]) is not int or record["controls"] != task["steps"]:
                    raise ValueError("arm control count mismatch")
                if record["wall_clock_realtime"] is not False:
                    raise ValueError("unqualified real-time claim")
                duration = Q(task["steps"], 100)
                force = numeric(system["gain"]) * (
                    Q(2943, 1000) + 2 * numeric(task["distance_m"]) / duration**2
                )
                if abs(numeric(record["force_n"]) - force) > Q(1, 10**12):
                    raise ValueError("applied force identity differs")
                reading, quantum = numeric(record["reading_m"]), numeric(system["sensor_quantum_m"])
                if abs(reading - round(reading / quantum) * quantum) > Q(1, 10**12):
                    raise ValueError("reading does not use declared quantization")
                for state in record["states"]:
                    if len(state) != 3:
                        raise ValueError("state dimension mismatch")
                    for value in state:
                        numeric(value)
    reserve = sum(t["cost"] for t in protocol["confirmation_tasks"])
    observed, spent, position = {}, 0, 0
    for index, choice in enumerate(row["choices"]):
        if (
            choice["observations"] != observed
            or choice["remaining"] != row["budget"] - reserve - spent
        ):
            raise ValueError("acquisition trace does not match available evidence")
        if choice["probe"] is None:
            if index != len(row["choices"]) - 1:
                raise ValueError("trace continues after stopping")
            continue
        if position >= len(row["raw"]) or row["raw"][position]["task"]["id"] != choice["probe"]:
            raise ValueError("acquisition choice differs from execution")
        item = row["raw"][position]
        if item["task"]["cost"] > choice["remaining"]:
            raise ValueError("acquisition used confirmation reserve")
        observed[choice["probe"]] = item["pair"]["difference"]
        spent += item["task"]["cost"]
        position += 1
    if position != len(row["raw"]):
        raise ValueError("execution lacks acquisition record")
    for key, tasks, rows in (
        ("diagnostic", protocol["tasks"], row["raw"]),
        ("confirmation", protocol["confirmation_tasks"], row["confirmation_raw"]),
    ):
        if row[key] is None:
            continue
        cells = {r["task"]["id"]: r["pair"]["difference"] for r in rows}
        low, high, _ = bounds(tasks, cells)
        if (
            row[key]["observed_conditions"] != len(cells)
            or row[key]["superiority"] != (high < 0)
            or row[key]["equivalence_within_one_eighth"] != (low >= -Q(1, 8) and high <= Q(1, 8))
        ):
            raise ValueError("claim scope or relation differs")
    return audit_trial(row, case, protocol)
