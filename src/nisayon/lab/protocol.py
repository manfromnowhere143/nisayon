"""A versioned contact adapter, not a replacement for existing evidence contracts."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import math
import platform
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest
from nisayon.qualification.models import fields

VERSION = "nisayon.lab.contact.v1"
MUJOCO_VERSION = "3.3.2"
PARAMETERS = {
    "mass_kg": (0.4, 0.2, 1.0, "kg", "Slider mass; identical in both systems"),
    "reference_friction": (0.3, 0.05, 1.0, "1", "Reference sliding friction"),
    "candidate_friction": (0.45, 0.05, 1.0, "1", "Candidate sliding friction"),
    "reference_gain": (1.0, 0.5, 1.5, "1", "Reference command-to-force gain"),
    "candidate_gain": (1.0, 0.5, 1.5, "1", "Candidate command-to-force gain"),
    "low_force_n": (2.0, 1.0, 8.0, "N", "First prescribed force command"),
    "high_force_n": (4.0, 1.0, 8.0, "N", "Second prescribed force command"),
    "duration_s": (0.3, 0.1, 0.5, "s", "Duration after each matched reset"),
    "displacement_tolerance_m": (0.005, 0.0, 0.05, "m", "Declared equivalence obligation"),
}
PROTOCOL = {
    "schema": VERSION,
    "id": "contact-force-separation",
    "revision": 2,
    "status": "research_preview",
    "embodiment": "two-axis guided rigid slider; no proprietary robot",
    "visualization": {
        "slider_half_size_m": [0.04, 0.03, 0.02],
        "surface": "infinite physical plane; finite presentation crop has no contact boundaries",
        "frame_mapping": "MuJoCo z-up to Three y-up: (x,z,-y)",
        "interpolation": "none; display exact retained rows",
        "force_arrow_scale_m_per_n": 0.02,
    },
    "solver": {
        "name": "MuJoCo",
        "version": MUJOCO_VERSION,
        "integrator": "Euler",
        "solver": "Newton",
        "iterations": 100,
        "timestep_s": 0.001,
        "cone": "elliptic",
        "contact_solref": [0.01, 1.0],
    },
    "coordinates": {
        "frame": "bench_world",
        "axes": "x travel, y lateral, z up",
        "units": "SI",
        "gravity_m_s2": [0.0, 0.0, -9.81],
    },
    "initial_state": {
        "distribution": "one deterministic state per role and input",
        "settle_s": 0.2,
        "travel_m": 0.0,
        "velocity_m_s": 0.05,
        "randomness": "none",
        "paired_reset": "same qpos and qvel after settling",
    },
    "intervention": "two prescribed constant force commands; independent physics futures",
    "action": "command N times declared motor gain; no learned policy or feedback controller",
    "measurement_period_s": 0.005,
    "measurement_phase": "state and forces after mj_forward at the reported simulation time",
    "channels": {
        "x_m": {"unit": "m", "origin": "simulated", "use": "analysis"},
        "v_m_s": {"unit": "m/s", "origin": "simulated", "use": "analysis"},
        "a_m_s2": {"unit": "m/s2", "origin": "simulated", "use": "analysis"},
        "command_n": {"unit": "N", "origin": "declared", "use": "analysis"},
        "applied_n": {"unit": "N", "origin": "simulated", "use": "validation_only"},
        "contact_x_n": {"unit": "N", "origin": "simulated", "use": "validation_only"},
        "normal_n": {"unit": "N", "origin": "simulated", "use": "validation_only"},
    },
    "analysis": {
        "model": "mean acceleration = gain*u/m - effective_mu*g",
        "acceleration": "least-squares velocity slope after 0.025 s, separately per input",
        "max_velocity_residual_rms_m_s": 0.025,
        "min_force_separation_n": 0.1,
        "interpretation": "conditional effective parameters, not calibrated material estimates",
    },
    "obligation": "candidate terminal displacement within declared absolute tolerance of reference",
    "qualification_authority": "nisayon.qualification.assess_measurements",
    "limits": [
        "exposed, prescribed experiment; no autonomous diagnosis or adaptive cost claim",
        "soft contact simulation, rigid guided body, known mass; not hardware validation",
        "force channels are simulator validation, not physical sensors",
        "stiction, loss of contact or inadequate excitation leave the fit unresolved",
        "no statistical generalization, safety certificate or deployment authorization",
    ],
    "budgets": {
        "episodes": 4,
        "max_physics_steps": 3000,
        "max_wall_s": 10.0,
        "max_packet_bytes": 2_000_000,
        "max_measurements": 404,
    },
    "failure": "retain incomplete measurements; qualification unresolved",
    "cancellation": "cooperative check at every physics step; retain partial packet",
}


# Revision 1 differed only in its presentation description. Preserve read-only
# inspection of retained development packets; execute only the current revision.
PREVIOUS_PROTOCOL = copy.deepcopy(PROTOCOL)
PREVIOUS_PROTOCOL["revision"] = 1
PREVIOUS_PROTOCOL["visualization"]["surface"] = "infinite plane shown as a finite 2 m bench"


def validate_parameters(value: object) -> dict:
    """Normalize supported numeric values before computing semantic identity."""
    obj = fields(value, set(PARAMETERS))
    result = {}
    for name, (_, low, high, _, _) in PARAMETERS.items():
        number = obj[name]
        if (
            type(number) not in (float, int)
            or not math.isfinite(number)
            or not low <= number <= high
        ):
            raise ValueError(f"{name}: expected finite number in [{low}, {high}]")
        result[name] = float(number)
    if result["high_force_n"] <= result["low_force_n"]:
        raise ValueError("high_force_n must exceed low_force_n")
    # Integral measurement periods prevent silent horizon rounding.
    ticks = result["duration_s"] / PROTOCOL["measurement_period_s"]
    if abs(ticks - round(ticks)) > 1e-10:
        raise ValueError("duration_s must be a multiple of 0.005 s")
    fastest = result["high_force_n"] * max(result["reference_gain"], result["candidate_gain"])
    travel_bound = (
        0.05 * result["duration_s"] + fastest / result["mass_kg"] * result["duration_s"] ** 2 / 2
    )
    if travel_bound > 1.5:
        raise ValueError("force, mass and duration exceed the declared 1.5 m travel bound")
    return result


def source_identity() -> dict:
    root = Path(__file__).parent
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            root / "protocol.py",
            root / "contact.py",
            root.parent / "qualification" / "measurements.py",
            root.parent / "qualification" / "models.py",
            root.parent / "engine" / "io.py",
        ]
    }


def runtime_identity() -> dict:
    versions = {}
    for name in ("mujoco", "numpy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "packages": versions,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "system": platform.system(),
    }


def experiment(parameters: dict | None = None) -> dict:
    """A semantic specification: no run id, timestamp, path or host scheduling."""
    values = validate_parameters(
        parameters if parameters is not None else {key: row[0] for key, row in PARAMETERS.items()}
    )
    spec = {
        "schema": "nisayon.lab.experiment.v1",
        "protocol": PROTOCOL,
        "protocol_sha256": digest(PROTOCOL),
        "parameters": values,
        "producer": source_identity(),
        "runtime": runtime_identity(),
    }
    return {"experiment_id": digest(spec), "spec": spec}


def validate_experiment(value: object, *, executable: bool = True) -> dict:
    obj = fields(value, {"experiment_id", "spec"})
    spec = fields(
        obj["spec"], {"schema", "protocol", "protocol_sha256", "parameters", "producer", "runtime"}
    )
    if obj["experiment_id"] != digest(spec):
        raise ValueError("experiment identity mismatch")
    supported = [PROTOCOL] if executable else [PROTOCOL, PREVIOUS_PROTOCOL]
    if spec["schema"] != "nisayon.lab.experiment.v1" or spec["protocol"] not in supported:
        raise ValueError("unsupported protocol")
    if spec["protocol_sha256"] != digest(spec["protocol"]):
        raise ValueError("protocol identity mismatch")
    if (
        not isinstance(spec["producer"], dict)
        or set(spec["producer"]) != set(source_identity())
        or any(
            not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
            for v in spec["producer"].values()
        )
    ):
        raise ValueError("invalid producer identity")
    values = validate_parameters(spec["parameters"])
    if canonical_bytes(values) != canonical_bytes(spec["parameters"]):
        raise ValueError("noncanonical parameters")
    if executable:
        if spec["producer"] != source_identity() or spec["runtime"] != runtime_identity():
            raise ValueError("source or dependency identity changed; validate a new experiment")
        if spec["runtime"]["packages"]["mujoco"] != MUJOCO_VERSION:
            raise ValueError(
                "Contact execution requires the locked native profile: uv sync --frozen --group native"
            )
    return decode_json(canonical_bytes(obj))


def capabilities() -> dict:
    defaults = experiment()
    available = defaults["spec"]["runtime"]["packages"]["mujoco"] == MUJOCO_VERSION
    properties = {
        name: {
            "type": "number",
            "default": row[0],
            "minimum": row[1],
            "maximum": row[2],
            "unit": row[3],
            "title": row[4],
        }
        for name, row in PARAMETERS.items()
    }
    properties["duration_s"]["multipleOf"] = 0.005
    return {
        "schema": "nisayon.lab.capabilities.v1",
        "execution": "local_registered_protocols",
        "instruments": [
            {
                "id": "contact",
                "label": "Contact dynamics",
                "status": "research_preview",
                "executable": available,
                "operations": ["validate", "execute", "cancel", "inspect", "export"]
                if available
                else ["validate", "inspect", "export"],
                "protocol": PROTOCOL,
                "parameters_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(properties),
                    "properties": properties,
                },
                "default": defaults,
            }
        ],
        "qualification": "existing measurement kernel; deployment remains unresolved",
    }
