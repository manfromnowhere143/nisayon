"""Export a small real generation before extending the recorded case library."""

import os
from pathlib import Path

from . import ADAPTER_VERSION
from .bytes import MAX_OBJECT_BYTES, ExportError, canonical, parse, read, sha256
from .contract import DOCUMENT
from .kinematics import Kinematics
from .source import Sources, admit_bundle, admit_decision, admit_raw

EXPERIMENT = "development-ablation-001"


class Store:
    def __init__(self, root: Path):
        self.root, self.files = root, {}

    def put(self, value: dict, kind: str, required: bool = True):
        DOCUMENT.validate_python(value, strict=True)
        data = canonical(value) + b"\n"
        if len(data) > MAX_OBJECT_BYTES:
            raise ExportError("export object exceeds the 16 MiB limit")
        digest = sha256(data)
        relative = ("generations/" if kind == "manifest" else "objects/") + digest + ".json"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if read(target) != data:
                raise ExportError("refuse to replace an immutable object")
        else:
            with target.open("xb") as stream:
                stream.write(data)
        ref = {
            "path": relative,
            "sha256": digest,
            "byte_length": len(data),
            "media_type": "application/json",
            "kind": kind,
            "required": required,
        }
        if kind != "manifest":
            self.files[relative] = ref
        return ref

    def expose(self, manifest):
        # Discovery is replaced only after the whole generation validates.
        from .validate import validate_generation

        validate_generation(self.root, manifest, strict_optional=True)
        for filename, schema in [
            ("integrity.json", "nisayon.ui-integrity.v1"),
            ("evidence.json", "nisayon.ui-discovery.v1"),
        ]:
            data = canonical({"schema": schema, "manifest": manifest}) + b"\n"
            temporary = self.root / (filename + ".tmp")
            with temporary.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.root / filename)


def memory_state(raw_value, digest):
    if digest is None:
        return "unavailable"
    if raw_value is not None and raw_value.get("hidden") is None:
        return "initialized_none"
    return "present"


def sample(index, row, raw, run, bundle_source_id, raw_source_id, run_index):
    before = row.get("policy_state_sha256")
    after = row.get("policy_state_after_sha256")
    observations = (
        None
        if raw is None
        else {
            name: raw[name] for name in ["observation", "captured_observation", "next_observation"]
        }
    )
    return {
        "row_index": index,
        "step": row["step"],
        "action_sim_time_s": row["action_sim_time_s"],
        "next_sim_time_s": row["next_sim_time_s"],
        "observation_sim_time_s": row["observation_sim_time_s"],
        "observation_age_s": row["action_sim_time_s"] - row["observation_sim_time_s"],
        "original": row,
        "observations": observations,
        "memory": {
            "before": memory_state(None if raw is None else raw.get("policy_state_before"), before),
            "after": memory_state(None if raw is None else raw.get("policy_state_after"), after),
            "before_sha256": before,
            "after_sha256": after,
            "episode_reset": run.get("policy_reset", {}).get("episode_reset_applied")
            if index == 0
            else None,
            "reset_before_inference": row.get("policy_reset_before_inference"),
        },
        "source": {"source_id": bundle_source_id, "pointer": f"/runs/{run_index}/trace/{index}"},
        "raw_source": {"source_id": raw_source_id, "line": index + 2} if raw_source_id else None,
    }


def findings(samples, key, predicates):
    result = []
    checks = [
        (
            "gripper_transport_mismatch",
            "Gripper command differs after normalized clipping.",
            "abs(clip(intended_action[6], -max_abs_executed_action, max_abs_executed_action) - executed_action[6]) > threshold",
            1e-9,
            lambda s: (
                abs(
                    max(
                        -predicates["max_abs_executed_action"],
                        min(
                            predicates["max_abs_executed_action"],
                            s["original"]["intended_action"][6],
                        ),
                    )
                    - s["original"]["executed_action"][6]
                )
                > 1e-9
            ),
        ),
        (
            "observation_age_violation",
            "Consumed observation exceeds the recorded age obligation.",
            "action_sim_time_s - observation_sim_time_s > max_observation_age_s",
            predicates["max_observation_age_s"],
            lambda s: s["observation_age_s"] > predicates["max_observation_age_s"],
        ),
    ]
    for code, detail, definition, threshold, predicate in checks:
        first = next((s for s in samples if predicate(s)), None)
        if first:
            result.append(
                {
                    "id": key["bundle_sha256"] + "/" + key["run_id"] + "/" + code,
                    "kind": "descriptive",
                    "code": code,
                    "detail": detail,
                    "run": key,
                    "row_index": first["row_index"],
                    "phase": "before",
                    "step": first["step"],
                    "definition": definition,
                    "threshold": threshold,
                    "source": first["source"],
                }
            )
    return result


def sample_indexes(samples):
    """Recorded reset/availability marks; no inferred memory-health metric."""
    return {
        "episode_reset": [s["row_index"] for s in samples if s["memory"]["episode_reset"] is True],
        "reset_before_inference": [
            s["row_index"] for s in samples if s["memory"]["reset_before_inference"] is True
        ],
        "initialized_none_before": [
            s["row_index"] for s in samples if s["memory"]["before"] == "initialized_none"
        ],
        "unavailable_policy_before": [
            s["row_index"] for s in samples if s["memory"]["before"] == "unavailable"
        ],
        "equal_policy_digest": [
            s["row_index"]
            for s in samples
            if s["memory"]["before_sha256"] is not None
            and s["memory"]["before_sha256"] == s["memory"]["after_sha256"]
        ],
    }


def export_runs(
    bundle, sid, bundle_sha, raw_root, sources, store, bindings, label, projected_decision, stage
):
    plans = {plan["id"]: plan for plan in bundle["plans"]}
    runs, events, reports = [], [], []
    for run_index, run in enumerate(bundle["runs"]):
        raw_sid, rows = admit_raw(raw_root, run, sources, label)
        kinematics = Kinematics(raw_root, run, sources, bindings)
        model_ref = store.put(kinematics.document, "model", required=False)
        key = {"bundle_sha256": bundle_sha, "run_id": run["id"]}
        samples, frames = [], []
        for index, row, raw in rows:
            samples.append(sample(index, row, raw, run, sid, raw_sid, run_index))
            frames.extend(kinematics.frame(index, phase, raw, row) for phase in ["before", "after"])
        sample_ref = store.put(
            {"schema": "nisayon.ui-samples.v1", "run": key, "rows": samples}, "samples"
        )
        reconstruction = kinematics.reconstruction(key, model_ref, raw_sid, frames)
        reconstruction_ref = store.put(reconstruction, "reconstruction", required=False)
        events.extend(findings(samples, key, bundle["case"]["predicates"]))
        reports.append(
            {
                "run": key,
                "rows": len(samples),
                "frames": len(frames),
                "maximum_residuals": reconstruction["maximum_residuals"],
            }
        )
        runs.append(
            {
                "key": key,
                "role": plans[run["plan_id"]]["role"],
                "plan_id": run["plan_id"],
                "plan": plans[run["plan_id"]],
                "execution": {
                    field: run.get(field)
                    for field in [
                        "seed",
                        "execution_mode",
                        "evidence_origin",
                        "initial_state_sha256",
                        "reset_id",
                        "started_at",
                        "ended_at",
                    ]
                },
                "stage": stage,
                "condition_id": run["condition_id"],
                "process_status": run["process_status"],
                "measurement_status": run["measurement_status"],
                "task_outcome": run["task_outcome"],
                "samples": sample_ref,
                "reconstruction": reconstruction_ref,
                "model": model_ref,
                "source": {"source_id": sid, "pointer": f"/runs/{run_index}"},
                "raw_source_id": raw_sid,
                "sample_count": len(samples),
                "last_next_sim_time_s": samples[-1]["next_sim_time_s"] if samples else None,
                "reset": {
                    "policy_reset": run.get("policy_reset"),
                    "policy_state_reset": run.get("policy_state_reset"),
                },
                "costs": run["costs"],
                "cost_parent_run_id": run.get("cost_parent_run_id"),
                "evaluator": projected_decision["runs"].get(run["id"]),
                "indexes": sample_indexes(samples),
            }
        )
    return runs, events, reports


def export_d01(compact: Path, raw_root: Path, output: Path, qualification: Path):
    sources, store = Sources(), Store(output)
    label = EXPERIMENT + "/D01-gripper-sign/B/diagnostic/execution"
    bundle, sid, bundle_sha = admit_bundle(compact, raw_root, sources, label)
    qualification_bytes = read(qualification)
    qualified = parse(qualification_bytes)
    bindings = {
        item["name"]: item["sha256_at_qualification"]
        for item in qualified["current_local_mesh_bindings"]
    }
    sources.add(
        "qualification:" + sha256(qualification_bytes),
        qualification_bytes,
        "json",
        "retained-state qualification",
        qualified,
    )
    for path in sorted(Path(__file__).parent.glob("*.py")):
        data = read(path)
        sources.add("adapter:" + path.name, data, "python", "ui_export/" + path.name)
    projected_decision, _ = admit_decision(
        compact.parent.parent / "diagnostic-decision.json",
        bundle,
        bundle_sha,
        "diagnostic",
        sources,
    )
    decision_ref = store.put(projected_decision, "decision")
    runs, events, reports = export_runs(
        bundle,
        sid,
        bundle_sha,
        raw_root,
        sources,
        store,
        bindings,
        label,
        projected_decision,
        "diagnostic",
    )
    case_key = EXPERIMENT + "/D01-gripper-sign/B"
    case = {
        "schema": "nisayon.ui-case.v1",
        "case_key": case_key,
        "case_id": "D01-gripper-sign",
        "experiment_id": EXPERIMENT,
        "arm": "B",
        "task": bundle["case"]["task"],
        "predicates": bundle["case"]["predicates"],
        "runs": runs,
        "decisions": [decision_ref],
        "findings": events,
        "trial": None,
        "confirmation": {"availability": "not_in_this_generation"},
        "comparison_alignment": "Simulation seconds from each recorded reset; select an actual sample in each run. An ended run remains ended.",
        "limitations": [
            "First boundary contains diagnostic runs only. Confirmation acceptance is not inferred from diagnostic task completion.",
            "Kinematic frames and original observations remain separate; residuals are not a tolerance.",
        ],
    }
    case_ref = store.put(case, "case")
    manifest = {
        "schema": "nisayon.ui-generation.v1",
        "adapter": "nisayon.ui-export/" + ADAPTER_VERSION,
        "experiment_id": EXPERIMENT,
        "capabilities": [
            "recorded_samples",
            "articulated_schematic",
            "evaluator_decisions",
            "source_inspection",
        ],
        "sources": list(sources.entries.values()),
        "cases": [{"case_key": case_key, "case_id": case["case_id"], "object": case_ref}],
        "files": list(store.files.values()),
        "limitations": [
            "Local inspection only. Byte integrity does not independently establish physical truth.",
            "No simulation steps, policy inference, contact reconstruction or mesh redistribution.",
        ],
    }
    manifest_ref = store.put(manifest, "manifest")
    store.expose(manifest_ref)
    return {
        "manifest": manifest_ref,
        "sources": len(sources.entries),
        "runs": reports,
        "output_bytes": sum(ref["byte_length"] for ref in store.files.values())
        + manifest_ref["byte_length"],
    }
