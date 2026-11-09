"""Validate the static trust boundary and exact moment locators, without a simulator."""

import math
import re
from pathlib import Path

from .bytes import ExportError, check_bytes, inside, parse, read
from .contract import DOCUMENT, FileRef
from .semantics import check_context
from .source import producer_digest

SCHEMAS = {
    "manifest": "generation",
    "case": "case",
    "samples": "samples",
    "model": "model",
    "reconstruction": "reconstruction",
    "decision": "decision",
}


def _require(condition, message):
    if not condition:
        raise ExportError(message)


def _unique(values, label):
    _require(len(values) == len(set(values)), "duplicate " + label)


def load_object(root: Path, ref: dict):
    FileRef.model_validate(ref, strict=True)
    _require(ref["path"].endswith("/" + ref["sha256"] + ".json"), "path/digest disagreement")
    data = read(inside(root, ref["path"]))
    check_bytes(data, ref["sha256"], ref["byte_length"])
    value = parse(data)
    DOCUMENT.validate_python(value, strict=True)
    _require(
        value["schema"] == "nisayon.ui-" + SCHEMAS[ref["kind"]] + ".v1",
        "object kind/schema mismatch",
    )
    return value


def validate_generation(
    root: Path, manifest_ref: dict | None = None, *, expected_sha256=None, strict_optional=False
):
    if manifest_ref is None and expected_sha256 is not None:
        _require(
            isinstance(expected_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
            "invalid pinned generation digest",
        )
        path = f"generations/{expected_sha256}.json"
        try:
            data = read(inside(root, path))
            check_bytes(data, expected_sha256)
        except (OSError, ValueError) as error:
            raise ExportError(f"pinned generation unavailable or invalid: {error}") from error
        manifest_ref = {
            "path": path,
            "sha256": expected_sha256,
            "byte_length": len(data),
            "media_type": "application/json",
            "kind": "manifest",
            "required": True,
        }
    if manifest_ref is None:
        discovery = parse(read(root / "evidence.json"))
        DOCUMENT.validate_python(discovery, strict=True)
        _require(discovery["schema"] == "nisayon.ui-discovery.v1", "invalid discovery")
        manifest_ref = discovery["manifest"]
    if expected_sha256 is not None:
        _require(manifest_ref["sha256"] == expected_sha256, "pinned generation mismatch")
    _require(manifest_ref["kind"] == "manifest", "expected manifest reference")
    manifest = load_object(root, manifest_ref)
    _require(
        len(manifest["files"]) <= 2048 and len(manifest["sources"]) <= 10_000,
        "manifest item limit exceeded",
    )
    _require(
        sum(ref["byte_length"] for ref in manifest["files"]) <= 128 * 1024 * 1024,
        "generation byte limit exceeded",
    )
    _unique([s["id"] for s in manifest["sources"]], "source identity")
    _unique([c["case_key"] for c in manifest["cases"]], "case identity")
    _unique([f["path"] for f in manifest["files"]], "object path")
    sources = {s["id"]: s for s in manifest["sources"]}
    refs = {ref["path"]: ref for ref in manifest["files"]}
    objects, unavailable = {}, {}

    def registered(ref, kind, required=False):
        _require(refs.get(ref["path"]) == ref, "unbound child reference")
        _require(ref["kind"] == kind, "child reference kind mismatch")
        _require(not required or ref["required"], f"{kind} cannot be optional")

    for ref in manifest["files"]:
        try:
            objects[ref["path"]] = load_object(root, ref)
        except (OSError, ValueError) as error:
            if ref["required"] or strict_optional:
                raise ExportError(f"{ref['kind']} {ref['path']}: {error}") from error
            unavailable[ref["path"]] = str(error)
    cases = {}
    for item in manifest["cases"]:
        registered(item["object"], "case", required=True)
        case = objects[item["object"]["path"]]
        _require(
            case["case_key"] == item["case_key"] and case["case_id"] == item["case_id"],
            "case identity mismatch",
        )
        _require(case["experiment_id"] == manifest["experiment_id"], "experiment identity mismatch")
        _unique(
            [(r["key"]["bundle_sha256"], r["key"]["run_id"]) for r in case["runs"]], "run identity"
        )
        _unique([f["id"] for f in case["findings"]], "finding identity")
        cases[item["case_key"]] = case
        by_key = {}
        for run in case["runs"]:
            registered(run["samples"], "samples", required=True)
            series = objects[run["samples"]["path"]]
            key = run["key"]
            by_key[(key["bundle_sha256"], key["run_id"])] = run
            _require(series["run"] == key, "sample bundle/run mismatch")
            source = sources.get(run["source"]["source_id"])
            _require(
                source is not None
                and source["encoding"] == "json"
                and source["sha256"] == key["bundle_sha256"],
                "run source binding mismatch",
            )
            _require(
                isinstance(run["source"].get("pointer"), str)
                and re.fullmatch(r"/runs/(0|[1-9][0-9]*)", run["source"]["pointer"]) is not None,
                "invalid run source pointer",
            )
            _require(
                run["raw_source_id"] is None or run["raw_source_id"] in sources,
                "unknown raw source",
            )
            _require(run["sample_count"] == len(series["rows"]), "sample count mismatch")
            if run.get("last_next_sim_time_s") is not None:
                _require(
                    bool(series["rows"])
                    and run["last_next_sim_time_s"] == series["rows"][-1]["next_sim_time_s"],
                    "recording end time mismatch",
                )
            _unique([s["step"] for s in series["rows"]], "sample step")
            for index, sample in enumerate(series["rows"]):
                _validate_sample(sample, index, run)
                if index:
                    _require(
                        sample["action_sim_time_s"] >= series["rows"][index - 1]["next_sim_time_s"],
                        "run state time overlaps or reverses",
                    )
            if run.get("indexes"):
                from .exporter import sample_indexes

                _require(
                    run["indexes"] == sample_indexes(series["rows"]),
                    "recorded marker index mismatch",
                )
            if run["model"]:
                registered(run["model"], "model")
                model = objects.get(run["model"]["path"])
                if model:
                    try:
                        _validate_model(model, sources)
                    except ValueError as error:
                        if strict_optional or run["model"]["required"]:
                            raise
                        unavailable[run["model"]["path"]] = str(error)
                        objects.pop(run["model"]["path"], None)
            if run["reconstruction"]:
                registered(run["reconstruction"], "reconstruction")
                ref = run["reconstruction"]
                reconstruction = objects.get(ref["path"])
                if reconstruction:
                    try:
                        _require(
                            run["model"] is not None and run["model"]["path"] in objects,
                            "reconstruction model unavailable",
                        )
                        _validate_reconstruction(
                            reconstruction, series, run, objects[run["model"]["path"]]
                        )
                    except ValueError as error:
                        if strict_optional or ref["required"]:
                            raise
                        unavailable[ref["path"]] = str(error)
                        objects.pop(ref["path"], None)
        for finding in case["findings"]:
            key = finding["run"]
            run = by_key.get((key["bundle_sha256"], key["run_id"]))
            _require(
                run is not None and finding["row_index"] < run["sample_count"],
                "invalid finding locator",
            )
            selected = objects[run["samples"]["path"]]["rows"][finding["row_index"]]
            _require(
                finding["step"] == selected["step"] and finding["source"] == selected["source"],
                "finding source mismatch",
            )
        for ref in case["decisions"]:
            registered(ref, "decision", required=True)
            decision = objects[ref["path"]]
            source = sources.get(decision["source"]["source_id"])
            _require(source is not None and source["encoding"] == "json", "decision source missing")
            bundle_sources = [
                s
                for s in sources.values()
                if s["sha256"] == decision["bundle_sha256"] and s["encoding"] == "json"
            ]
            _require(
                len(bundle_sources) == 1
                and bundle_sources[0]["canonical_json_sha256"]
                == decision["source_canonical_bundle_sha256"],
                "decision bundle binding mismatch",
            )
        check_context(case, sources, objects)
    return {
        "generation_sha256": manifest_ref["sha256"],
        "manifest": manifest,
        "cases": cases,
        "objects": objects,
        "unavailable": unavailable,
    }


def _validate_sample(sample, index, run):
    original = sample["original"]
    required = {
        "step",
        "action_sim_time_s",
        "next_sim_time_s",
        "observation_sim_time_s",
        "intended_action",
        "executed_action",
        "cube_height_m",
        "task_success",
        "policy_state_sha256",
        "policy_state_after_sha256",
        "state_before_sha256",
        "state_after_sha256",
        "observation_sha256",
        "next_observation_sha256",
        "captured_observation_sha256",
        "policy_reset_before_inference",
    }
    _require(required <= original.keys(), "missing original reading or binding")
    _require(type(original["step"]) is int and original["step"] >= 0, "invalid original step")
    for field in [
        "action_sim_time_s",
        "next_sim_time_s",
        "observation_sim_time_s",
        "cube_height_m",
    ]:
        _require(
            type(original[field]) in (int, float) and math.isfinite(original[field]),
            "invalid original number",
        )
    _require(type(original["task_success"]) is bool, "invalid original task flag")
    _require(type(original["policy_reset_before_inference"]) is bool, "invalid original reset flag")
    for field in required:
        if field.endswith("_sha256"):
            value = original[field]
            nullable = field in {"policy_state_sha256", "policy_state_after_sha256"}
            _require(
                (nullable and value is None)
                or (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None),
                "invalid original digest",
            )
    _require(sample["row_index"] == index, "sample row index mismatch")
    for field in ["step", "action_sim_time_s", "next_sim_time_s", "observation_sim_time_s"]:
        _require(sample[field] == original[field], "original sample value mismatch")
    _require(sample["next_sim_time_s"] >= sample["action_sim_time_s"], "sample time reverses")
    _require(
        sample["observation_sim_time_s"] <= sample["action_sim_time_s"],
        "consumed observation comes from the future",
    )
    _require(
        sample["observation_age_s"]
        == sample["action_sim_time_s"] - sample["observation_sim_time_s"],
        "observation age mismatch",
    )
    for field in ["intended_action", "executed_action"]:
        _require(
            isinstance(original.get(field), list) and len(original[field]) == 7,
            "invalid action dimension",
        )
        _require(
            all(type(v) in (int, float) and math.isfinite(v) for v in original[field]),
            "invalid action number",
        )
    expected = {
        "source_id": run["source"]["source_id"],
        "pointer": run["source"]["pointer"] + f"/trace/{index}",
    }
    _require(sample["source"] == expected, "sample source locator mismatch")
    if sample["raw_source"]:
        _require(
            sample["raw_source"] == {"source_id": run["raw_source_id"], "line": index + 2},
            "raw line binding mismatch",
        )
    _require(
        (sample["raw_source"] is None) == (run["raw_source_id"] is None),
        "raw source availability mismatch",
    )
    if sample["observations"] is not None:
        for field in ["observation", "captured_observation", "next_observation"]:
            _require(field in sample["observations"], "missing projected observation")
            _require(
                producer_digest(sample["observations"][field]) == original[field + "_sha256"],
                "original observation digest mismatch",
            )
    for side, field in [("before", "policy_state_sha256"), ("after", "policy_state_after_sha256")]:
        digest = original.get(field)
        _require(sample["memory"][side + "_sha256"] == digest, "memory digest mismatch")
        _require(
            (sample["memory"][side] == "unavailable") == (digest is None),
            "memory availability mismatch",
        )
    _require(
        sample["memory"]["reset_before_inference"] == original["policy_reset_before_inference"],
        "memory reset flag mismatch",
    )
    policy_reset = run["reset"].get("policy_reset")
    _require(policy_reset is None or isinstance(policy_reset, dict), "invalid policy reset record")
    expected_reset = (policy_reset or {}).get("episode_reset_applied") if index == 0 else None
    _require(sample["memory"]["episode_reset"] == expected_reset, "episode reset marker mismatch")


def _validate_model(model, sources):
    _require(
        model["source_id"] in sources and sources[model["source_id"]]["encoding"] == "mjcf",
        "model source binding mismatch",
    )
    for field in ["bodies", "sites", "geoms"]:
        _unique([node["id"] for node in model[field]], field + " identity")
    body_ids = {node["id"] for node in model["bodies"]}
    for index, node in enumerate(model["bodies"]):
        _require(node["id"] == index, "body declaration order mismatch")
        _require(
            node["parent_id"] in body_ids
            and (node["parent_id"] < index or index == node["parent_id"] == 0),
            "invalid body ancestry",
        )
    _require(
        all(node["body_id"] in body_ids for field in ["sites", "geoms"] for node in model[field]),
        "unknown owning body",
    )
    _require(
        all(size >= 0 for node in model["geoms"] for size in node["size"]), "negative geometry size"
    )


def _validate_reconstruction(reconstruction, samples, run, model):
    _require(reconstruction["run"] == run["key"], "reconstruction bundle/run mismatch")
    _require(reconstruction["model"] == run["model"], "reconstruction model mismatch")
    _require(
        reconstruction["raw_source_id"] == run["raw_source_id"],
        "reconstruction raw source mismatch",
    )
    _require(
        len(reconstruction["frames"]) == 2 * run["sample_count"], "incomplete reconstruction phases"
    )
    for index, frame in enumerate(reconstruction["frames"]):
        row_index, phase = index // 2, ("before", "after")[index % 2]
        _require(
            frame["row_index"] == row_index and frame["phase"] == phase, "frame row/phase mismatch"
        )
        original = samples["rows"][row_index]["original"]
        _require(
            frame["stored_time_s"]
            == original["action_sim_time_s" if phase == "before" else "next_sim_time_s"],
            "frame time mismatch",
        )
        _require(
            frame["state_sha256"] == original["state_" + phase + "_sha256"],
            "frame state binding mismatch",
        )
        for field in ["bodies", "sites", "geoms"]:
            _require(len(frame[field]) == len(model[field]), "frame/model dimension mismatch")
            for pose in frame[field]:
                _require(
                    abs(sum(q * q for q in pose[3:]) - 1) < 1e-9,
                    "derived quaternion is not unit length",
                )


def select(generation, moment):
    _require(
        moment.get("generation_sha256") == generation["generation_sha256"],
        "selection generation mismatch",
    )
    _require(
        moment.get("phase") in {"before", "after"} and moment.get("clock") == "simulation",
        "invalid phase or clock",
    )
    case = generation["cases"].get(moment.get("case_key"))
    _require(case is not None, "unknown selected case")
    run = next((r for r in case["runs"] if r["key"] == moment.get("run")), None)
    _require(run is not None, "unknown selected run")
    index = moment.get("row_index")
    _require(type(index) is int and 0 <= index < run["sample_count"], "invalid selected row")
    sample = generation["objects"][run["samples"]["path"]]["rows"][index]
    reconstruction = generation["objects"].get((run["reconstruction"] or {}).get("path"))
    frame = (
        None
        if reconstruction is None
        else reconstruction["frames"][2 * index + (moment["phase"] == "after")]
    )
    return {"sample": sample, "frame": frame, "run": run}
