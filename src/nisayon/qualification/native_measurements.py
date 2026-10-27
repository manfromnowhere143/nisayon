"""Capture and recompute a bounded LIBERO object-On measurement in MuJoCo.

MuJoCo is optional and imported only for capture/recomputation. This checks an
instantaneous predicate under a declared scene and producer. It does not prove
task completion, physical truth, honest instrumentation or deployment safety.
"""

from __future__ import annotations

import gzip
import hashlib
import inspect
import io
import math
import re
import zlib
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest, write_json

from .models import fields, identifier, label

LEGACY_SCHEMA = "nisayon.qualification.mujoco_on_protocol.v1"
CALL_SCHEMA = "nisayon.qualification.mujoco_on_protocol.v2"
SCHEMA = "nisayon.qualification.mujoco_on_protocol.v3"
EPISODE_SCHEMA = "nisayon.qualification.mujoco_on_protocol.v4"
FILES = {"protocol.json", "model.mjb.gz", "model.xml", "task.bddl", "sources.json", "frames.jsonl"}
MAX_MODEL_BYTES = 512 * 1024**2
LIMITS = {"model.mjb.gz": 256 * 1024**2, "frames.jsonl": 32 * 1024**2}
POSITION_ATOL = 1e-10


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _int(value, name, maximum=100_000):
    _require(type(value) is int and 0 <= value <= maximum, f"{name}:invalid_integer")
    return value


def _numbers(value, count, name):
    _require(isinstance(value, list) and len(value) == count, f"{name}:dimension")
    _require(all(type(x) in (int, float) and math.isfinite(x) for x in value), f"{name}:nonfinite")
    return value


def _runtime():
    import mujoco
    import numpy as np

    # Callbacks/plugins can introduce unrecorded state or external computation.
    for name in (
        "control",
        "passive",
        "contactfilter",
        "sensor",
        "act_dyn",
        "act_gain",
        "act_bias",
    ):
        _require(getattr(mujoco, "get_mjcb_" + name)() is None, "unsupported_mujoco_callback")
    return mujoco, np


def _numpy_identity(np):
    """Bind the native norm implementation, bundled libraries and CPU features."""
    import platform

    root = Path(np.__file__).parent
    core = np.core._multiarray_umath
    paths = [Path(core.__file__), *root.glob(".dylibs/*"), *root.parent.glob("numpy.libs/*")]
    return {
        "version": np.__version__,
        "machine": platform.machine(),
        "native_files": {
            str(path.relative_to(root.parent)): _sha(path.read_bytes())
            for path in sorted(set(paths))
            if path.is_file()
        },
        "cpu_features": dict(sorted(core.__cpu_features__.items())),
        "norm_source_sha256": _sha(inspect.getsource(np.linalg.norm).encode()),
    }


def _model_bytes(mj, np, model):
    _require(model.nplugin == 0, "unsupported_mujoco_plugin")
    size = mj.mj_sizeModel(model)
    _require(0 < size <= MAX_MODEL_BYTES, "compiled_model_size")
    raw = np.empty(size, dtype=np.uint8)
    mj.mj_saveModel(model, None, raw)
    return raw.tobytes()


def _state(mj, np, model, data):
    _require(data.model is model, "state_model_identity")
    _require(data.qpos.size == model.nq and data.qvel.size == model.nv, "state_model_dimensions")
    spec = mj.mjtState.mjSTATE_INTEGRATION
    size = mj.mj_stateSize(model, spec)
    _require(0 < size <= 65_536, "integration_state_size")
    result = np.empty(size, dtype=np.float64)
    mj.mj_getState(model, data, result, spec)
    return _numbers(result.tolist(), size, "integration_state")


def _producer_identity(producer):
    _require(callable(producer), "native_producer_required")
    return {
        "symbol": producer.__module__ + "." + producer.__qualname__,
        "source_sha256": _sha(inspect.getsource(producer).encode()),
    }


def _goal_matches(bddl, goal):
    tokens = re.findall(r"\(|\)|[^\s()]+", re.sub(r";[^\n]*", "", bddl.decode("utf-8")))
    _require(len(tokens) <= 100_000 and tokens.count(":goal") == 1, "single_bddl_goal_required")
    start = tokens.index(":goal") + 1

    def expression(i, depth=0):
        _require(depth < 64 and i < len(tokens), "invalid_bddl_goal")
        if tokens[i] != "(":
            _require(tokens[i] != ")", "invalid_bddl_goal")
            return tokens[i], i + 1
        result = []
        i += 1
        while i < len(tokens) and tokens[i] != ")":
            item, i = expression(i, depth + 1)
            result.append(item)
        _require(i < len(tokens), "invalid_bddl_goal")
        return result, i + 1

    value, _ = expression(start)
    expected = ["On", goal["object"], goal["target"]]
    _require(value == expected or value == ["And", expected], "bddl_goal_mapping_mismatch")


def _protocol(value):
    fields(
        value,
        {
            "schema",
            "id",
            "scope",
            "mujoco_version",
            "model_sha256",
            "model_bytes",
            "capture_source_sha256",
            "bddl_sha256",
            "producer",
            "goal",
            "entities",
            "frames",
            "position_atol",
        },
        {"numpy_runtime", "ending"},
    )
    _require(
        value["schema"] in (SCHEMA, CALL_SCHEMA, LEGACY_SCHEMA, EPISODE_SCHEMA),
        "unsupported_measurement_protocol",
    )
    if value["schema"] in (SCHEMA, EPISODE_SCHEMA):
        _require(isinstance(value.get("numpy_runtime"), dict), "numpy_runtime_required")
    _require(("ending" in value) == (value["schema"] == EPISODE_SCHEMA), "ending_schema")
    identifier(value["id"])
    label(value["scope"], "scope")
    label(value["mujoco_version"], "mujoco version")
    producer = fields(value["producer"], {"symbol", "source_sha256"})
    label(producer["symbol"], "producer symbol")
    _require(0 < _int(value["model_bytes"], "model_bytes", MAX_MODEL_BYTES), "compiled_model_size")
    for sha in (
        value["model_sha256"],
        value["bddl_sha256"],
        producer["source_sha256"],
        value["capture_source_sha256"],
    ):
        _require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha), "invalid_sha256")
    _require(value["position_atol"] == POSITION_ATOL, "unsupported_position_tolerance")
    goal = fields(value["goal"], {"predicate", "object", "target"})
    _require(goal["predicate"] == "libero_object_on_v1", "unsupported_predicate")
    _require(goal["object"] != goal["target"], "distinct_goal_entities_required")
    for role in ("object", "target"):
        identifier(goal[role])
    entities = fields(value["entities"], {goal["object"], goal["target"]})
    seen = set()
    for entity in entities.values():
        fields(entity, {"body", "contact_geoms"})
        identifier(entity["body"])
        geoms = entity["contact_geoms"]
        _require(isinstance(geoms, list) and 1 <= len(geoms) <= 1024, "contact_geom_coverage")
        for geom in geoms:
            identifier(geom)
        _require(len(set(geoms)) == len(geoms) and not seen.intersection(geoms), "ambiguous_geom")
        seen.update(geoms)
    _require(len({e["body"] for e in entities.values()}) == 2, "distinct_bodies_required")
    frames = value["frames"]
    _require(isinstance(frames, list) and 1 <= len(frames) <= 4096, "frame_count")
    keys = []
    for row in frames:
        fields(
            row,
            {"episode", "step"}
            if value["schema"] == LEGACY_SCHEMA
            else {"episode", "step", "call"},
        )
        identifier(row["episode"])
        _int(row["step"], "step")
        call = 0 if value["schema"] == LEGACY_SCHEMA else _int(row["call"], "call", 1000)
        keys.append((row["episode"], row["step"], call))
    _require(len(keys) == len(set(keys)), "duplicate_frame_ownership")
    previous = {}
    for episode, step, call in keys:
        _require(episode not in previous or (step, call) > previous[episode], "frame_order")
        previous[episode] = (step, call)
    if "ending" in value:
        ending = fields(value["ending"], {"kind", "calls_per_step"})
        calls = _int(ending["calls_per_step"], "calls_per_step", 3)
        _require(ending["kind"] == "first_success" and calls in (2, 3), "ending_rule")
        episode, first, _ = keys[0]
        expected = [
            (episode, step, call)
            for step in range(first, first + len(keys) // calls)
            for call in range(calls)
        ]
        _require(keys == expected, "ending_frame_plan")
    return value


def _ending_reason(protocol, successes):
    """Check a frozen maximum plan, never shorten it after observing a result."""
    maximum = len(protocol["frames"])
    if "ending" not in protocol:
        _require(len(successes) == maximum, "frame_coverage")
        return "window_complete"
    calls = protocol["ending"]["calls_per_step"]
    _require(0 < len(successes) <= maximum and len(successes) % calls == 0, "frame_coverage")
    _require(all(type(value) is bool for value in successes), "native_boolean_required")
    outcomes = []
    for index in range(0, len(successes), calls):
        group = successes[index : index + calls]
        _require(all(value is group[-1] for value in group), "step_success_disagreement")
        outcomes.append(group[-1])
    _require(not any(outcomes[:-1]), "execution_after_first_success")
    _require(outcomes[-1] or len(successes) == maximum, "incomplete_capture")
    return "native_success" if outcomes[-1] else "maximum_steps"


def _bindings(mj, model, protocol):
    result = {}
    for name, entity in protocol["entities"].items():
        body = mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, entity["body"])
        _require(body > 0, "unknown_body")
        geoms = []
        for name_ in entity["contact_geoms"]:
            geom = mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, name_)
            _require(geom >= 0, "unknown_contact_geom")
            ancestor = int(model.geom_bodyid[geom])
            while ancestor and ancestor != body:
                ancestor = int(model.body_parentid[ancestor])
            _require(ancestor == body, "contact_geom_wrong_body")
            geoms.append(geom)
        result[name] = {"body": body, "geoms": geoms}
    return result


def _reading(data, bindings, goal):
    positions = {name: data.xpos[item["body"]].tolist() for name, item in bindings.items()}
    contacts = []
    for contact in data.contact[: data.ncon]:
        a, b = int(contact.geom1), int(contact.geom2)
        # Keep contact presence semantics of robosuite, including margin contacts.
        if (a in bindings[goal["object"]]["geoms"] and b in bindings[goal["target"]]["geoms"]) or (
            b in bindings[goal["object"]]["geoms"] and a in bindings[goal["target"]]["geoms"]
        ):
            contacts.append([a, b, float(contact.dist)])
    return {"positions": positions, "contacts": sorted(contacts)}


def _on(reading, goal):
    obj = _numbers(reading["positions"][goal["object"]], 3, "object_position")
    target = _numbers(reading["positions"][goal["target"]], 3, "target_position")
    import numpy as np

    # Preserve the native float64 operation at the strict 0.03 m boundary.
    distance = float(np.linalg.norm(np.asarray(target[:2]) - np.asarray(obj[:2])))
    _require(math.isfinite(distance), "nonfinite_horizontal_distance")
    return {
        "success": target[2] <= obj[2] and bool(reading["contacts"]) and distance < 0.03,
        "horizontal_distance_m": distance,
        "height_difference_m": obj[2] - target[2],
        "object_target_contact": bool(reading["contacts"]),
    }


class MujocoOnRecorder:
    """Append owned frames around actual calls to a trusted native predicate.

    The caller binds the real native objects and sources before collection.
    Capture never forwards, steps, resets or corrects the live simulation.
    The producer must be read-only. Failure leaves an unsealed prefix.
    """

    def __init__(
        self,
        output,
        *,
        model,
        goal,
        entities,
        frames,
        producer,
        model_xml,
        bddl,
        sources,
        identifier_="native-on",
        scope="Bounded native object-On measurements",
        ending=None,
    ):
        self.mj, self.np = _runtime()
        self.model, self.producer = model, producer
        self.root = Path(output).absolute()
        _require(self.root.resolve() == self.root, "symlink_output")
        raw = _model_bytes(self.mj, self.np, model)
        self.protocol = _protocol(
            {
                "schema": SCHEMA if ending is None else EPISODE_SCHEMA,
                **({} if ending is None else {"ending": ending}),
                "id": identifier_,
                "scope": scope,
                "mujoco_version": self.mj.__version__,
                "numpy_runtime": _numpy_identity(self.np),
                "model_sha256": _sha(raw),
                "model_bytes": len(raw),
                "capture_source_sha256": _sha(Path(__file__).read_bytes()),
                "bddl_sha256": _sha(bddl),
                "producer": _producer_identity(producer),
                "goal": goal,
                "entities": entities,
                "frames": [{"call": 0, **frame} for frame in frames],
                "position_atol": POSITION_ATOL,
            }
        )
        # Freeze caller-owned dictionaries, not references to mutable declarations.
        self.protocol = decode_json(canonical_bytes(self.protocol))
        _goal_matches(bddl, self.protocol["goal"])
        self.bindings = _bindings(self.mj, model, self.protocol)
        self.protocol_sha256 = digest(self.protocol)
        _require(
            isinstance(sources, dict) and {"native_predicate", "native_contact"} <= sources.keys(),
            "native_sources_required",
        )
        source_bytes = {**sources, "producer": inspect.getsource(producer).encode()}
        for name, content in source_bytes.items():
            identifier(name)
            _require(isinstance(content, bytes) and len(content) <= 1024**2, "source_file_bound")
        source_record = {
            name: {"sha256": _sha(content), "text": content.decode("utf-8")}
            for name, content in source_bytes.items()
        }
        self.root.mkdir(parents=True, exist_ok=False)
        compressed = gzip.compress(raw, compresslevel=1, mtime=0)
        _require(len(compressed) <= LIMITS["model.mjb.gz"], "compressed_model_size")
        (self.root / "model.mjb.gz").write_bytes(compressed)
        (self.root / "model.xml").write_bytes(model_xml)
        (self.root / "task.bddl").write_bytes(bddl)
        write_json(self.root / "protocol.json", self.protocol)
        write_json(self.root / "sources.json", source_record)
        (self.root / "frames.jsonl").touch(exist_ok=False)
        self.index = 0
        self.closed = False
        self.failed = False
        self.successes = []

    def capture(self, data, *, episode, step, call=0, observation_state=None):
        """Record a call; an optional Euler origin must reconstruct the live state."""
        return self._guarded_capture(
            data, episode=episode, step=step, call=call, observation_state=observation_state
        )[0]

    def native_call(
        self, data, *, episode, step, call=0, observation_state=None, _context_check=None
    ):
        """Record a call and preserve the native producer's exact Boolean type."""
        return self._guarded_capture(
            data,
            episode=episode,
            step=step,
            call=call,
            observation_state=observation_state,
            _context_check=_context_check,
        )[1]

    def _guarded_capture(self, data, **owner):
        try:
            return self._capture(data, **owner)
        except BaseException:
            self.failed = True
            raise

    def _capture(self, data, *, episode, step, call, observation_state, _context_check=None):
        if _context_check is not None:
            _context_check()
        _runtime()
        _require(
            not self.closed and not self.failed and self.index < len(self.protocol["frames"]),
            "capture_closed",
        )
        _require(digest(self.protocol) == self.protocol_sha256, "capture_protocol_changed")
        if "ending" in self.protocol:
            calls = self.protocol["ending"]["calls_per_step"]
            _require(
                not (self.index and self.index % calls == 0 and self.successes[-1]),
                "execution_after_first_success",
            )
        owner = {"episode": episode, "step": step, "call": call}
        _require(
            canonical_bytes(owner) == canonical_bytes(self.protocol["frames"][self.index]),
            "frame_ownership_mismatch",
        )
        _require(_producer_identity(self.producer) == self.protocol["producer"], "producer_changed")
        _require(
            _sha(_model_bytes(self.mj, self.np, self.model)) == self.protocol["model_sha256"],
            "live_model_changed",
        )
        before = _state(self.mj, self.np, self.model, data)
        origin = {"kind": "synchronized"}
        if observation_state is not None:
            values = _numbers(list(observation_state), len(before), "observation_state")
            origin = {
                "kind": "euler_pre_step",
                "integration_state": values,
                "state_sha256": digest(values),
            }
        observed = _reading(data, self.bindings, self.protocol["goal"])
        native = self.producer()
        if _context_check is not None:
            _context_check()
        _require(type(native) in (bool, self.np.bool_), "native_boolean_required")
        _require(
            canonical_bytes(before) == canonical_bytes(_state(self.mj, self.np, self.model, data)),
            "native_producer_changed_state",
        )
        _require(
            canonical_bytes(observed)
            == canonical_bytes(_reading(data, self.bindings, self.protocol["goal"])),
            "native_producer_changed_observation",
        )
        _require(
            _sha(_model_bytes(self.mj, self.np, self.model)) == self.protocol["model_sha256"],
            "native_producer_changed_model",
        )
        row = {
            "owner": owner,
            "sequence": self.index,
            "protocol_sha256": digest(self.protocol),
            "integration_state": before,
            "state_sha256": digest(before),
            "observed": observed,
            "native_success": bool(native),
            "production": {"calls": 1, "producer": self.protocol["producer"]},
            "observation_origin": origin,
        }
        with (self.root / "frames.jsonl").open("ab") as stream:
            stream.write(canonical_bytes(row) + b"\n")
            stream.flush()
        self.index += 1
        self.successes.append(bool(native))
        return row, native

    def finalize(self):
        _require(
            not self.closed
            and not self.failed
            and self.index == len(self.successes)
            and ("ending" in self.protocol or self.index == len(self.protocol["frames"])),
            "incomplete_capture",
        )
        _require(digest(self.protocol) == self.protocol_sha256, "capture_protocol_changed")
        _ending_reason(self.protocol, self.successes)
        seal = {
            "schema": "nisayon.qualification.mujoco_measurement_seal.v1",
            "frames": self.index,
            "files": {name: _sha((self.root / name).read_bytes()) for name in sorted(FILES)},
        }
        write_json(self.root / "seal.json", seal)
        self.closed = True
        return seal


def _packet(root):
    root = Path(root).absolute()
    _require(root.resolve() == root and root.is_dir(), "measurement_directory_required")
    _require({p.name for p in root.iterdir()} == FILES | {"seal.json"}, "incomplete_or_extra_files")
    raw = {}
    for name in FILES | {"seal.json"}:
        path = root / name
        _require(not path.is_symlink() and path.is_file(), "regular_measurement_file_required")
        with path.open("rb") as stream:
            raw[name] = stream.read(LIMITS.get(name, 4 * 1024**2) + 1)
        _require(len(raw[name]) <= LIMITS.get(name, 4 * 1024**2), "measurement_file_bound")
    seal = fields(decode_json(raw["seal.json"]), {"schema", "frames", "files"})
    _require(seal["schema"] == "nisayon.qualification.mujoco_measurement_seal.v1", "seal_schema")
    _require(seal["files"] == {name: _sha(raw[name]) for name in FILES}, "measurement_integrity")
    protocol = _protocol(decode_json(raw["protocol.json"]))
    with gzip.GzipFile(fileobj=io.BytesIO(raw["model.mjb.gz"])) as stream:
        model = stream.read(protocol["model_bytes"] + 1)
    _require(
        len(model) == protocol["model_bytes"] and _sha(model) == protocol["model_sha256"],
        "scene_identity",
    )
    raw["model.mjb"] = model
    _require(protocol["bddl_sha256"] == _sha(raw["task.bddl"]), "task_identity")
    _goal_matches(raw["task.bddl"], protocol["goal"])
    sources = decode_json(raw["sources.json"])
    _require(
        isinstance(sources, dict)
        and {"native_predicate", "native_contact", "producer"} <= sources.keys(),
        "native_sources_required",
    )
    for name, item in sources.items():
        identifier(name)
        fields(item, {"sha256", "text"})
        _require(
            isinstance(item["text"], str) and _sha(item["text"].encode()) == item["sha256"],
            "source_identity",
        )
    _require(
        sources["producer"]["sha256"] == protocol["producer"]["source_sha256"],
        "producer_source_identity",
    )
    rows = [decode_json(line) for line in raw["frames.jsonl"].splitlines()]
    _require(
        _int(seal["frames"], "frame_count", 4096) == len(rows),
        "frame_coverage",
    )
    _ending_reason(protocol, [row["native_success"] for row in rows])
    return raw, protocol, rows


def reassess_native_measurements(root):
    """Recompute positions/contacts in a new data object; execute no owner code."""
    result = {
        "schema": "nisayon.qualification.native_measurement_assessment.v1",
        "status": "invalid",
        "verdict": "unresolved",
        "frames": [],
        "errors": [],
        "deployment_decision": "unresolved",
        "measurement_adequacy": "unresolved",
        "reviewer_source_sha256": _sha(Path(__file__).read_bytes()),
        "scope": "Instantaneous native object-On agreement under the captured simulator, model, mapping and trusted producer. No policy execution, episode success or physical-world qualification.",
    }
    try:
        raw, protocol, rows = _packet(root)
        mj, np = _runtime()
        _require(mj.__version__ == protocol["mujoco_version"], "mujoco_version_mismatch")
        if "numpy_runtime" not in protocol:
            result.update(status="runtime_unqualified", errors=["numpy_runtime_not_recorded"])
            return result
        _require(
            canonical_bytes(protocol["numpy_runtime"]) == canonical_bytes(_numpy_identity(np)),
            "numpy_runtime_mismatch",
        )
        model = mj.MjModel.from_binary_path("model.mjb", assets={"model.mjb": raw["model.mjb"]})
        _require(model.nplugin == 0, "unsupported_mujoco_plugin")
        bindings = _bindings(mj, model, protocol)
        previous_time = {}
        for index, row in enumerate(rows):
            required = {
                "owner",
                "sequence",
                "protocol_sha256",
                "integration_state",
                "state_sha256",
                "observed",
                "native_success",
                "production",
            }
            if protocol["schema"] != LEGACY_SCHEMA:
                required.add("observation_origin")
            fields(
                row,
                required,
            )
            _require(_int(row["sequence"], "sequence") == index, "frame_sequence")
            _require(
                canonical_bytes(row["owner"]) == canonical_bytes(protocol["frames"][index]),
                "frame_ownership_mismatch",
            )
            _require(row["protocol_sha256"] == digest(protocol), "frame_protocol_mismatch")
            _require(row["state_sha256"] == digest(row["integration_state"]), "state_integrity")
            _require(type(row["native_success"]) is bool, "native_boolean_required")
            _require(
                canonical_bytes(row["production"])
                == canonical_bytes({"calls": 1, "producer": protocol["producer"]}),
                "native_production_missing_or_changed",
            )
            data = mj.MjData(model)
            size = mj.mj_stateSize(model, mj.mjtState.mjSTATE_INTEGRATION)
            _require(size <= 65_536, "integration_state_size")
            state = np.array(
                _numbers(row["integration_state"], size, "integration_state"), dtype=np.float64
            )
            mj.mj_setState(model, data, state, mj.mjtState.mjSTATE_INTEGRATION)
            episode = row["owner"]["episode"]
            current_time = data.time
            previous = previous_time.get(episode)
            same_step = previous is not None and row["owner"]["step"] == previous[0]
            _require(
                previous is None
                or (data.time == previous[1] if same_step else data.time > previous[1]),
                "stale_episode_time",
            )
            previous_time[episode] = (row["owner"]["step"], data.time)
            origin = row.get("observation_origin", {"kind": "synchronized"})
            fields(origin, {"kind"}, {"integration_state", "state_sha256"})
            _require(
                origin["kind"] in ("synchronized", "euler_pre_step"), "unknown_observation_origin"
            )
            transition_checked = origin["kind"] == "euler_pre_step"
            if transition_checked:
                fields(origin, {"kind", "integration_state", "state_sha256"})
                _require(
                    model.opt.integrator == mj.mjtIntegrator.mjINT_EULER,
                    "unsupported_observation_integrator",
                )
                observed_state = _numbers(origin["integration_state"], size, "observation_state")
                _require(
                    digest(observed_state) == origin["state_sha256"], "observation_state_identity"
                )
                observation = mj.MjData(model)
                mj.mj_setState(
                    model, observation, np.array(observed_state), mj.mjtState.mjSTATE_INTEGRATION
                )
                # The recorded control and complete state must actually produce the
                # current state. A stale origin cannot simply claim an earlier time.
                mj.mj_step(model, observation)
                _require(
                    canonical_bytes(_state(mj, np, model, observation))
                    == canonical_bytes(row["integration_state"]),
                    "observation_transition_mismatch",
                )
                mj.mj_setState(
                    model, data, np.array(observed_state), mj.mjtState.mjSTATE_INTEGRATION
                )
            else:
                fields(origin, {"kind"})
            measurement_time = data.time
            mj.mj_fwdPosition(model, data)
            fresh = _reading(data, bindings, protocol["goal"])
            observed = fields(row["observed"], {"positions", "contacts"})
            fields(observed["positions"], set(bindings))
            for name in bindings:
                saved = _numbers(observed["positions"][name], 3, "observed_position")
                _require(
                    all(
                        abs(a - b) <= POSITION_ATOL
                        for a, b in zip(saved, fresh["positions"][name], strict=True)
                    ),
                    "stale_or_wrong_entity_position",
                )
            _require(
                canonical_bytes(observed["contacts"]) == canonical_bytes(fresh["contacts"]),
                "stale_or_wrong_entity_contact",
            )
            reference = _on(fresh, protocol["goal"])
            result["frames"].append(
                {
                    "owner": row["owner"],
                    "native_success": row["native_success"],
                    "reference": reference,
                    "agrees": row["native_success"] == reference["success"],
                    "measurement_time": measurement_time,
                    "native_call_time": current_time,
                    "transition_checked": transition_checked,
                }
            )
        consistent = all(frame["agrees"] for frame in result["frames"])
        result.update(
            status="consistent" if consistent else "contradicted",
            verdict="supported" if consistent else "rejected",
            protocol_sha256=digest(protocol),
            packet_sha256=_sha(raw["seal.json"]),
            recomputation="position_recomputation_with_declared_native_call_timing",
        )
    except ImportError as error:
        result.update(status="runtime_unavailable", errors=[str(error)])
    except (ValueError, TypeError, KeyError, OSError, OverflowError, EOFError, zlib.error) as error:
        result["errors"] = [str(error)]
    return result
