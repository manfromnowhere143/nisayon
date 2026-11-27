"""Execute and inspect one finite contact protocol; never execute packet code."""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Callable
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest
from nisayon.qualification.measurements import MeasurementContract, assess_measurements
from nisayon.qualification.models import fields

from .protocol import PROTOCOL, source_identity, validate_experiment

ROLES = ("reference", "candidate")
CONDITIONS = ("low", "high")
MAX_BYTES = PROTOCOL["budgets"]["max_packet_bytes"]
IMPORTED_SOURCE = source_identity()


def model_xml(parameters: dict, role: str) -> str:
    """The guide removes rotation/lateral travel; contact still solves normal/sliding force."""
    return f'''<mujoco model="nisayon_contact_slider_v1">
  <option timestep="0.001" gravity="0 0 -9.81" solver="Newton" iterations="100"
          tolerance="1e-10" cone="elliptic" integrator="Euler"/>
  <worldbody>
    <geom name="surface" type="plane" size="2 0.25 0.01" rgba="0.24 0.27 0.3 1"/>
    <body name="slider" pos="0 0 0.021">
      <joint name="travel" type="slide" axis="1 0 0" damping="0"/>
      <joint name="normal" type="slide" axis="0 0 1" damping="0"/>
      <geom name="slider_contact" type="box" size="0.04 0.03 0.02"
            mass="{parameters["mass_kg"]}" rgba="0.65 0.68 0.72 1"/>
    </body>
  </worldbody>
  <contact><pair geom1="surface" geom2="slider_contact" condim="3"
      friction="{parameters[role + "_friction"]} {parameters[role + "_friction"]} 0 0 0"
      solref="0.01 1" solimp="0.99 0.99 0.001"/></contact>
  <actuator><motor name="force" joint="travel" gear="{parameters[role + "_gain"]}"/></actuator>
</mujoco>'''


def measurement_contract(parameters: dict) -> MeasurementContract:
    return MeasurementContract.from_dict(
        {
            "schema": "nisayon.qualification.measurement_contract.v1",
            "id": "contact-terminal-displacement-v1",
            "scope": "Terminal slider displacement in these two prescribed simulated conditions only",
            "metrics": {
                "displacement": {
                    "unit": "m",
                    "boundary": "end minus matched initial x",
                    "conditions": list(CONDITIONS),
                    "relation": "close",
                    "aggregation": "all",
                    "atol": parameters["displacement_tolerance_m"],
                    "rtol": 0.0,
                }
            },
        }
    )


def measurements(traces: list, complete: bool) -> dict:
    result = {}
    for role in ROLES:
        values = {}
        for trace in traces:
            if trace["role"] == role and trace["complete"] and trace["rows"]:
                rows = trace["rows"]
                values[trace["condition"]] = rows[-1]["x_m"] - rows[0]["x_m"]
        result[role] = {
            "schema": "nisayon.qualification.measurements.v1",
            "origin": "simulation",
            "complete": complete and set(values) == set(CONDITIONS),
            "metrics": {
                "displacement": {
                    "unit": "m",
                    "boundary": "end minus matched initial x",
                    "values": values,
                }
            },
        }
    return result


def analyze(traces: list, parameters: dict, complete: bool) -> dict:
    """An explicit model fit, separate from qualification; no residual is a probability."""
    estimates = {}
    for role in ROLES:
        episodes = [t for t in traces if t["role"] == role and t["complete"]]
        unresolved = {
            "status": "unresolved",
            "gain": None,
            "effective_friction": None,
            "conditions": [],
        }
        if not complete or len(episodes) != 2:
            estimates[role] = {
                **unresolved,
                "reason": "incomplete or insufficient sliding observations",
            }
            continue
        if (
            parameters["high_force_n"] - parameters["low_force_n"]
            < PROTOCOL["analysis"]["min_force_separation_n"]
        ):
            estimates[role] = {**unresolved, "reason": "insufficient independent force excitation"}
            continue
        fits = []
        for episode in sorted(episodes, key=lambda t: CONDITIONS.index(t["condition"])):
            rows = [r for r in episode["rows"] if r["t_s"] >= 0.025]
            if len(rows) < 4 or any(r["v_m_s"] <= 0.03 for r in rows):
                break
            x, y = [r["t_s"] for r in rows], [r["v_m_s"] for r in rows]
            mx, my = sum(x) / len(x), sum(y) / len(y)
            slope = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sum(
                (a - mx) ** 2 for a in x
            )
            rmse = math.sqrt(
                sum((b - (my + slope * (a - mx))) ** 2 for a, b in zip(x, y, strict=True)) / len(x)
            )
            fits.append(
                {
                    "condition": episode["condition"],
                    "acceleration_m_s2": slope,
                    "velocity_residual_rms_m_s": rmse,
                    "samples": len(rows),
                }
            )
        if len(fits) != 2 or any(
            f["velocity_residual_rms_m_s"] > PROTOCOL["analysis"]["max_velocity_residual_rms_m_s"]
            for f in fits
        ):
            estimates[role] = {
                **unresolved,
                "reason": "sustained sliding model not supported",
                "conditions": fits,
            }
            continue
        gain = (
            parameters["mass_kg"]
            * (fits[1]["acceleration_m_s2"] - fits[0]["acceleration_m_s2"])
            / (parameters["high_force_n"] - parameters["low_force_n"])
        )
        friction = (
            gain * parameters["low_force_n"] / parameters["mass_kg"] - fits[0]["acceleration_m_s2"]
        ) / 9.81
        if gain <= 0 or friction < 0:
            estimates[role] = {
                **unresolved,
                "reason": "incompatible effective parameters",
                "conditions": fits,
            }
            continue
        estimates[role] = {
            "status": "model_fit",
            "gain": gain,
            "effective_friction": friction,
            "conditions": fits,
            "reason": "conditional mean-motion fit; instantaneous soft-contact forces remain in the trace",
        }
    return {
        "schema": "nisayon.lab.contact-analysis.v1",
        "estimates": estimates,
        "single_input": "one acceleration equation cannot identify both gain and friction",
        "inputs": ["command_n", "t_s", "v_m_s", "declared mass"],
        "limit": "Exposed deterministic simulation and prescribed interventions; no autonomous discovery, calibrated uncertainty, held-out transfer or cost advantage.",
    }


class _Cancelled(Exception):
    pass


def execute(
    value: dict,
    output: str | Path,
    *,
    cancel: Callable[[], bool] | None = None,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Trusted local registered experiment. Output is create-only, finite and data-only."""
    value = validate_experiment(value)
    if source_identity() != IMPORTED_SOURCE:
        raise ValueError("producer source changed after import; restart before execution")
    import mujoco as mj
    import numpy as np

    # No unrecorded plugin or process-global callback may change the plant.
    for name in (
        "control",
        "passive",
        "contactfilter",
        "sensor",
        "act_dyn",
        "act_gain",
        "act_bias",
    ):
        if getattr(mj, "get_mjcb_" + name)() is not None:
            raise ValueError("unsupported MuJoCo callback")
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    parameters = value["spec"]["parameters"]
    started = time.perf_counter()
    traces: list[dict] = []
    status, error = "complete", None
    steps = round(parameters["duration_s"] / PROTOCOL["solver"]["timestep_s"])
    expected_rows = (steps // 5 + 1) * 4
    documents: dict[str, bytes] = {"experiment.json": canonical_bytes(value)}
    here = Path(__file__).parent
    for source in (
        here / "protocol.py",
        here / "contact.py",
        here.parent / "qualification" / "measurements.py",
        here.parent / "qualification" / "models.py",
        here.parent / "engine" / "io.py",
    ):
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != value["spec"]["producer"][source.name]:
            raise ValueError("source changed while retaining producer")
        documents["source-" + source.name + ".txt"] = raw

    def check():
        if cancel is not None and cancel():
            raise _Cancelled("cancelled by operator")
        if time.perf_counter() - started > PROTOCOL["budgets"]["max_wall_s"]:
            raise TimeoutError("declared execution wall budget exceeded")

    def sample(model, data, command):
        mj.mj_forward(model, data)
        contacts = []
        for i in range(data.ncon):
            contact = data.contact[i]
            if contact.efc_address < 0:
                continue
            force = np.zeros(6)
            mj.mj_contactForce(model, data, i, force)
            world = contact.frame.reshape(3, 3).T @ force[:3]
            if contact.geom1 == model.geom("slider_contact").id:
                world = -world
            contacts.append(
                {"position_m": contact.pos.tolist(), "force_on_slider_world_n": world.tolist()}
            )
        row = {
            "t_s": float(data.time),
            "x_m": float(data.qpos[0]),
            "z_m": float(data.xpos[1, 2]),
            "v_m_s": float(data.qvel[0]),
            "a_m_s2": float(data.qacc[0]),
            "command_n": command,
            "applied_n": float(data.qfrc_actuator[0]),
            "contact_x_n": float(data.qfrc_constraint[0]),
            "normal_n": float(data.qfrc_constraint[1]),
            "contacts": contacts,
        }
        # These checks establish numerical consistency, not independent physical truth.
        balance = parameters["mass_kg"] * row["a_m_s2"] - row["applied_n"] - row["contact_x_n"]
        if not all(math.isfinite(row[k]) for k in row if k != "contacts") or abs(balance) > 1e-7:
            raise ValueError("nonfinite state or horizontal force balance failure")
        contact_sum = sum(c["force_on_slider_world_n"][0] for c in contacts)
        if abs(contact_sum - row["contact_x_n"]) > 1e-7:
            raise ValueError("contact-frame force mismatch")
        return row

    try:
        # Settle once. Every independent future receives this exact integration state.
        initial_model = mj.MjModel.from_xml_string(model_xml(parameters, "reference"))
        initial = mj.MjData(initial_model)
        for _ in range(200):
            check()
            mj.mj_step(initial_model, initial)
        initial.time = 0.0
        initial.qpos[0] = 0.0
        initial.qvel[:] = [0.05, 0.0]
        initial.qacc_warmstart[:] = 0
        state_kind = mj.mjtState.mjSTATE_INTEGRATION
        state = np.empty(mj.mj_stateSize(initial_model, state_kind))
        mj.mj_getState(initial_model, initial, state, state_kind)
        state_record = {"state_spec": int(state_kind), "values": state.tolist()}
        initial_id = digest(state_record)
        documents["initial-state.json"] = canonical_bytes({**state_record, "sha256": initial_id})
        for role in ROLES:
            xml = model_xml(parameters, role)
            documents[f"{role}.xml"] = xml.encode()
            model = mj.MjModel.from_xml_string(xml)
            if model.nplugin != 0:
                raise ValueError("plugins unsupported")
            for condition in CONDITIONS:
                check()
                data = mj.MjData(model)
                mj.mj_setState(model, data, state, state_kind)
                command = parameters[condition + "_force_n"]
                data.ctrl[0] = command
                trace = {
                    "role": role,
                    "condition": condition,
                    "initial_state_sha256": initial_id,
                    "model_sha256": hashlib.sha256(xml.encode()).hexdigest(),
                    "complete": False,
                    "rows": [sample(model, data, command)],
                }
                traces.append(trace)
                for tick in range(1, steps + 1):
                    check()
                    mj.mj_step(model, data)
                    if tick % 5 == 0:
                        trace["rows"].append(sample(model, data, command))
                        if progress:
                            progress(
                                {
                                    "phase": "executing",
                                    "measurements": sum(len(t["rows"]) for t in traces),
                                    "expected_measurements": expected_rows,
                                    "role": role,
                                    "condition": condition,
                                    "simulation_time_s": float(data.time),
                                }
                            )
                trace["complete"] = True
        if source_identity() != IMPORTED_SOURCE:
            raise ValueError("producer source changed during execution")
    except _Cancelled as exc:
        status, error = "cancelled", str(exc)
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"
    complete = status == "complete"
    observed = measurements(traces, complete)
    contract = measurement_contract(parameters)
    assessment = assess_measurements(contract, observed["reference"], observed["candidate"])
    analysis = analyze(traces, parameters, complete)
    result = {
        "schema": "nisayon.lab.execution.v1",
        "experiment_id": value["experiment_id"],
        "status": status,
        "error": error,
        "wall_s": time.perf_counter() - started,
        "complete": complete,
        "measurements": sum(len(t["rows"]) for t in traces),
        "expected_measurements": expected_rows,
        "qualification": assessment,
    }
    for name, record in {
        "traces.json": traces,
        "measurements.json": observed,
        "contract.json": contract.record(),
        "analysis.json": analysis,
        "result.json": result,
    }.items():
        documents[name] = canonical_bytes(record)
    manifest = {
        "schema": "nisayon.lab.packet.v1",
        "experiment_id": value["experiment_id"],
        "files": [
            {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in sorted(documents.items())
        ],
    }
    if sum(len(raw) for raw in documents.values()) > MAX_BYTES:
        raise ValueError("packet budget exceeded; output is unsealed")
    for name, raw in documents.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
    with (destination / "manifest.json").open("xb") as stream:
        stream.write(canonical_bytes(manifest))
    return {**result, "packet_sha256": digest(manifest)}


def inspect_packet(directory: str | Path, *, expected_sha256: str | None = None) -> dict:
    """Bounded integrity/semantic readback; never imports a producer from a packet."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("packet must be a local regular directory")
    manifest_path = directory / "manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or manifest_path.stat().st_size > 32_000
    ):
        raise ValueError("missing or oversized manifest")
    manifest = fields(decode_json(manifest_path.read_bytes()), {"schema", "experiment_id", "files"})
    if manifest["schema"] != "nisayon.lab.packet.v1":
        raise ValueError("unsupported packet")
    packet_id = digest(manifest)
    if expected_sha256 is not None and packet_id != expected_sha256:
        raise ValueError("packet root identity mismatch")
    if not isinstance(manifest["files"], list) or not 11 <= len(manifest["files"]) <= 14:
        raise ValueError("packet member count")
    documents, total = {}, 0
    allowed = {
        "experiment.json",
        "traces.json",
        "measurements.json",
        "contract.json",
        "analysis.json",
        "result.json",
        "initial-state.json",
        "reference.xml",
        "candidate.xml",
    }
    allowed |= {"source-" + name + ".txt" for name in source_identity()}
    for entry in manifest["files"]:
        fields(entry, {"path", "bytes", "sha256"})
        name = entry["path"]
        if name not in allowed or name in documents:
            raise ValueError("unsafe or duplicate packet member")
        size = entry["bytes"]
        if type(size) is not int or not 0 <= size <= MAX_BYTES:
            raise ValueError("member size limit")
        total += size
        path = directory / name
        if (
            total > MAX_BYTES
            or path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != size
        ):
            raise ValueError("packet missing member or byte limit")
        with path.open("rb") as stream:
            raw = stream.read(size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("packet member digest mismatch")
        documents[name] = raw
    if {p.name for p in directory.iterdir()} != set(documents) | {"manifest.json"}:
        raise ValueError("packet file-set mismatch")
    required = {
        "experiment.json",
        "traces.json",
        "measurements.json",
        "contract.json",
        "analysis.json",
        "result.json",
    }
    if not required <= set(documents):
        raise ValueError("missing scientific records")
    value = validate_experiment(decode_json(documents["experiment.json"]), executable=False)
    if value["experiment_id"] != manifest["experiment_id"]:
        raise ValueError("packet experiment mismatch")
    for name, expected in value["spec"]["producer"].items():
        source = documents.get("source-" + name + ".txt")
        if source is None or hashlib.sha256(source).hexdigest() != expected:
            raise ValueError("retained producer source mismatch")
    parameters = value["spec"]["parameters"]
    result = decode_json(documents["result.json"])
    fields(
        result,
        {
            "schema",
            "experiment_id",
            "status",
            "error",
            "wall_s",
            "complete",
            "measurements",
            "expected_measurements",
            "qualification",
        },
    )
    if (
        result["schema"] != "nisayon.lab.execution.v1"
        or result["experiment_id"] != value["experiment_id"]
    ):
        raise ValueError("execution identity mismatch")
    if result["status"] not in {"complete", "cancelled", "failed"} or result["complete"] is not (
        result["status"] == "complete"
    ):
        raise ValueError("execution completion mismatch")
    traces = decode_json(documents["traces.json"])
    if not isinstance(traces, list) or len(traces) > 4:
        raise ValueError("trace count")
    identities = set()
    for trace in traces:
        fields(
            trace, {"role", "condition", "initial_state_sha256", "model_sha256", "complete", "rows"}
        )
        pair = trace["role"], trace["condition"]
        if (
            pair[0] not in ROLES
            or pair[1] not in CONDITIONS
            or pair in identities
            or type(trace["complete"]) is not bool
        ):
            raise ValueError("trace identity")
        identities.add(pair)
        if not isinstance(trace["rows"], list) or not 1 <= len(trace["rows"]) <= 101:
            raise ValueError("measurement count")
        for index, row in enumerate(trace["rows"]):
            fields(
                row,
                {
                    "t_s",
                    "x_m",
                    "z_m",
                    "v_m_s",
                    "a_m_s2",
                    "command_n",
                    "applied_n",
                    "contact_x_n",
                    "normal_n",
                    "contacts",
                },
            )
            if any(
                type(v) not in (int, float) or not math.isfinite(v)
                for k, v in row.items()
                if k != "contacts"
            ):
                raise ValueError("invalid measurement")
            if abs(row["t_s"] - index * 0.005) > 1e-10:
                raise ValueError("measurement timestamp discontinuity")
            if row["command_n"] != parameters[pair[1] + "_force_n"]:
                raise ValueError("command semantics mismatch")
            if abs(row["applied_n"] - row["command_n"] * parameters[pair[0] + "_gain"]) > 1e-10:
                raise ValueError("actuation semantics mismatch")
            if (
                abs(parameters["mass_kg"] * row["a_m_s2"] - row["applied_n"] - row["contact_x_n"])
                > 1e-7
            ):
                raise ValueError("force balance mismatch")
            if not isinstance(row["contacts"], list) or len(row["contacts"]) > 8:
                raise ValueError("contact count")
            for contact in row["contacts"]:
                fields(contact, {"position_m", "force_on_slider_world_n"})
                for vec in contact.values():
                    if (
                        not isinstance(vec, list)
                        or len(vec) != 3
                        or any(type(v) not in (int, float) or not math.isfinite(v) for v in vec)
                    ):
                        raise ValueError("invalid contact vector")
            if (
                abs(
                    sum(c["force_on_slider_world_n"][0] for c in row["contacts"])
                    - row["contact_x_n"]
                )
                > 1e-7
            ):
                raise ValueError("contact-frame force mismatch")
        if trace["complete"] and abs(trace["rows"][-1]["t_s"] - parameters["duration_s"]) > 1e-10:
            raise ValueError("incomplete horizon")
        xml_name = pair[0] + ".xml"
        if (
            xml_name not in documents
            or hashlib.sha256(documents[xml_name]).hexdigest() != trace["model_sha256"]
        ):
            raise ValueError("model identity mismatch")
        if documents[xml_name].decode() != model_xml(parameters, pair[0]):
            raise ValueError("model and protocol disagree")
    if traces:
        initial = decode_json(documents.get("initial-state.json", b"null"))
        fields(initial, {"state_spec", "values", "sha256"})
        if (
            type(initial["state_spec"]) is not int
            or not isinstance(initial["values"], list)
            or not 1 <= len(initial["values"]) <= 64
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in initial["values"])
        ):
            raise ValueError("invalid initial integration state")
        if (
            digest({"state_spec": initial["state_spec"], "values": initial["values"]})
            != initial["sha256"]
        ):
            raise ValueError("initial state digest mismatch")
        if any(t["initial_state_sha256"] != initial["sha256"] for t in traces):
            raise ValueError("paired initial-state mismatch")
    if result["complete"] and (len(traces) != 4 or not all(t["complete"] for t in traces)):
        raise ValueError("complete run lacks required conditions")
    observed = measurements(traces, result["complete"])
    contract = measurement_contract(parameters)
    assessment = assess_measurements(contract, observed["reference"], observed["candidate"])
    analysis = analyze(traces, parameters, result["complete"])
    if (
        observed != decode_json(documents["measurements.json"])
        or contract.record() != decode_json(documents["contract.json"])
        or assessment != result["qualification"]
        or analysis != decode_json(documents["analysis.json"])
    ):
        raise ValueError("derived scientific record mismatch")
    if result["measurements"] != sum(len(t["rows"]) for t in traces):
        raise ValueError("measurement accounting mismatch")
    if result["expected_measurements"] != (round(parameters["duration_s"] / 0.005) + 1) * 4:
        raise ValueError("expected measurement accounting mismatch")
    if (
        type(result["wall_s"]) not in (int, float)
        or not math.isfinite(result["wall_s"])
        or result["wall_s"] < 0
    ):
        raise ValueError("invalid wall cost")
    return {
        "schema": "nisayon.lab.inspection.v1",
        "integrity": "verified",
        "packet_sha256": packet_id,
        "experiment": value,
        "result": result,
        "traces": traces,
        "analysis": analysis,
        "limit": "Integrity and recomputed recorded relations; not independent physical truth or new execution.",
    }
