"""The six admitted, already observed development cases and their frozen decisions."""

from pathlib import Path

from . import ADAPTER_VERSION
from .bytes import (
    MAX_BUNDLE_BYTES,
    ExportError,
    check_bytes,
    decompress,
    inside,
    parse,
    read,
    sha256,
)
from .exporter import EXPERIMENT, Store, export_runs
from .source import Sources, admit_bundle, admit_decision, producer_digest, project_private_paths

CASES = (
    "D01-gripper-sign",
    "D03-observation-backlog",
    "D05-recurrent-carry",
    "D06-stateless-inference",
    "D08-old-future-replay",
    "D10-opaque-policy-state",
)


class Archive:
    """Check the archived exact-byte receipt before reading a selected record."""

    def __init__(self, root: Path, sources: Sources):
        self.root, self.sources = root, sources
        data = read(root / "archive-manifest.json")
        receipt = parse(data)
        if receipt.get("schema") != "nisayon.comparison-archive.v1":
            raise ExportError("unsupported source archive")
        self.files = {entry["path"]: entry for entry in receipt["files"]}
        if len(self.files) != len(receipt["files"]):
            raise ExportError("duplicate archive path")
        sources.add(
            "archive:" + sha256(data), data, "json", EXPERIMENT + "/archive-manifest.json", receipt
        )

    def bytes(self, relative):
        if relative not in self.files:
            raise ExportError("input is not in the retained archive")
        entry = self.files[relative]
        data = read(inside(self.root, relative), MAX_BUNDLE_BYTES)
        check_bytes(data, entry["sha256"], entry["bytes"])
        return data

    def json(self, relative):
        data = self.bytes(relative)
        value = parse(data, MAX_BUNDLE_BYTES)
        sid = self.sources.add(
            "record:" + sha256(data), data, "json", EXPERIMENT + "/" + relative, value
        )
        return value, {"source_id": sid, "pointer": ""}


def _equal(actual, expected, message):
    if actual != expected:
        raise ExportError(message)


def _trial_bindings(archive, case_id, arm):
    trial, locator = archive.json(f"{case_id}/{arm}/trial.json")
    suite, suite_locator = archive.json("frozen-suite.json")
    ledger, ledger_locator = archive.json("comparison-ledger.json")
    _equal(trial["case_id"], case_id, "trial case mismatch")
    _equal(trial["arm"], arm, "trial arm mismatch")
    matched = [t for t in ledger["trials"] if (t["case_id"], t["arm"]) == (case_id, arm)]
    _equal(matched, [trial], "trial differs from frozen comparison ledger")
    indexed = [(i, c) for i, c in enumerate(suite["cases"]) if c["id"] == case_id]
    if len(indexed) != 1:
        raise ExportError("case is missing or duplicated in frozen suite")
    index, case = indexed[0]
    _equal(
        trial["received_frozen_sha256"],
        producer_digest(case["frozen"]),
        "trial input digest mismatch",
    )
    _equal(
        ledger["suite"]["case_ledger_sha256"],
        producer_digest(suite),
        "suite/ledger binding mismatch",
    )
    for key in ["decision", "diagnosis", "confirmation"]:
        if trial.get(key):
            data = archive.bytes(trial[key]["path"])
            check_bytes(data, trial[key]["sha256"])
    diagnosis, diagnosis_locator = archive.json(f"{case_id}/{arm}/diagnostic/diagnosis.json")
    _equal(diagnosis["case_id"], case_id, "diagnosis case mismatch")
    _equal(diagnosis["arm"], arm, "diagnosis arm mismatch")
    redactions = []
    projected = {
        **project_private_paths(trial, redactions),
        "source": locator,
        "frozen_input_source": {**suite_locator, "pointer": f"/cases/{index}/frozen"},
        "ledger_source": ledger_locator,
        "diagnosis_source": diagnosis_locator,
        "diagnosis_record": project_private_paths(diagnosis, redactions),
        "projection_redactions": redactions,
    }
    return trial, projected


def confirmation_projection(archive, case_id, arm, bundle, bundle_sha, original_decision, trial):
    folder = f"{case_id}/{arm}/confirmation"
    result, result_source = archive.json(folder + "/confirmation-result.json")
    protocol, protocol_source = archive.json(folder + "/execution/frozen-protocol.json")
    joint, joint_source = archive.json(folder + "/execution/joint-freeze.json")
    _equal(result["bundle_sha256"], bundle_sha, "confirmation result exact bundle mismatch")
    _equal(
        result["protocol_sha256"],
        producer_digest(protocol),
        "confirmation protocol digest mismatch",
    )
    _equal(
        bundle["confirmation"]["protocol_sha256"],
        producer_digest(protocol),
        "bundle protocol mismatch",
    )
    _equal(
        protocol["joint_freeze_sha256"],
        archive.sources.entries[joint_source["source_id"]]["sha256"],
        "joint freeze byte mismatch",
    )
    _equal(
        producer_digest(joint["candidates"][arm]),
        bundle["confirmation"]["candidate_sha256"],
        "candidate freeze mismatch",
    )
    _equal(protocol["candidate"], joint["candidates"][arm], "protocol candidate mismatch")
    _equal(
        result["decision"],
        {**result["decision"], "decision": original_decision["decision"]},
        "confirmation decision status mismatch",
    )
    _equal(
        trial["decision"]["sha256"],
        result["decision"]["sha256"],
        "trial/confirmation decision identity mismatch",
    )
    _equal(result["status"], trial["status"], "trial/confirmation status mismatch")
    confirmation = original_decision["confirmation"]
    _equal(
        confirmation["fresh_condition_ids"],
        bundle["confirmation"]["condition_ids"],
        "evaluator condition identity mismatch",
    )
    _equal(
        protocol["condition_ids"],
        bundle["confirmation"]["condition_ids"],
        "protocol condition identity mismatch",
    )
    _equal(
        result["candidate_digest"],
        confirmation["candidate"]["digest"],
        "evaluator candidate binding mismatch",
    )
    by_id = {run["id"]: run for run in bundle["runs"]}
    pairs = []
    for pair in confirmation["pairs"]:
        mapped = dict(pair)
        for role in ["reference", "candidate"]:
            run_id = pair[role + "_run_id"]
            if run_id not in by_id:
                raise ExportError("condition refers to an absent execution")
            _equal(
                by_id[run_id]["condition_id"], pair["condition_id"], "paired condition/run mismatch"
            )
            _equal(
                original_decision["runs"][run_id]["outcome"]["observed"],
                pair[role + "_outcome"],
                "paired outcome binding mismatch",
            )
            mapped[role + "_run"] = {"bundle_sha256": bundle_sha, "run_id": run_id}
        pairs.append(mapped)
    redactions = []
    return {
        "availability": "recorded",
        "source": result_source,
        "bundle_sha256": bundle_sha,
        "protocol_source": protocol_source,
        "joint_freeze_source": joint_source,
        "result": project_private_paths(result, redactions),
        "pairs": pairs,
        "summary": confirmation["summary"],
        "findings": confirmation["findings"],
        "fresh_condition_ids": confirmation["fresh_condition_ids"],
        "reproduction_condition_ids": confirmation["reproduction_condition_ids"],
        "candidate": confirmation["candidate"],
        "frozen_at": confirmation["frozen_at"],
        "projection_redactions": redactions,
    }


def replay_decision_source(archive, raw_root, executed, executed_sha, case_id, arm):
    """Bind the rejected proposal, never turn its copied rows into executed samples."""
    relative = f"{case_id}/{arm}/diagnostic/derived-replay.json.gz"
    packed = archive.bytes(relative)
    decoded = decompress(packed)
    check_bytes(decoded, archive.files[relative]["source_sha256"])
    _equal(
        decoded,
        read(raw_root / case_id / arm / "diagnostic/derived-replay.json", MAX_BUNDLE_BYTES),
        "derived replay raw/archive bytes mismatch",
    )
    derived = parse(decoded, MAX_BUNDLE_BYTES)
    actual = {run["id"]: run for run in executed["runs"]}
    derived_runs = {run["id"]: run for run in derived["runs"]}
    _equal(len(derived_runs), len(derived["runs"]), "duplicate derived run identity")
    for run_id, run in actual.items():
        _equal(derived_runs.get(run_id), run, "derived proposal changed a recorded execution")
    for key in executed:
        if key not in {"plans", "runs"}:
            _equal(derived.get(key), executed[key], "derived proposal changed execution context")
    controls = [run for run in derived["runs"] if run["id"] not in actual]
    if not controls or any(
        run.get("evidence_origin") != "invalid_replay_control" for run in controls
    ):
        raise ExportError("derived source contains an unqualified additional execution")
    digest = sha256(decoded)
    archive.sources.add(
        "compressed:" + sha256(packed), packed, "gzip-json", EXPERIMENT + "/" + relative
    )
    sid = archive.sources.add(
        "bundle:" + digest,
        decoded,
        "json",
        EXPERIMENT + "/" + relative.removesuffix(".gz"),
        derived,
    )
    locators = [
        {
            "source": {"source_id": sid, "pointer": f"/runs/{index}"},
            "run_id": run["id"],
            "evidence_origin": run["evidence_origin"],
            "executed": False,
            "available_as_recorded_run": False,
            "execution_bundle_sha256": executed_sha,
        }
        for index, run in enumerate(derived["runs"])
        if run["id"] not in actual
    ]
    return derived, digest, locators


def export_case(
    compact_root: Path, raw_root: Path, output: Path, qualification: Path, case_id: str, arm="B"
):
    if case_id not in CASES or arm != "B":
        raise ExportError("case/arm is outside the admitted UI slice")
    sources, store = Sources(), Store(output)
    archive = Archive(compact_root, sources)
    trial, trial_projection = _trial_bindings(archive, case_id, arm)
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
    runs, events, reports, decisions = [], [], [], []
    confirmation = {
        "availability": "not_recorded",
        "reason": "No confirmation was executed for this retained trial.",
    }
    stages = ["diagnostic", "confirmation"] if trial.get("confirmation") else ["diagnostic"]
    case_source = None
    for stage in stages:
        relative = f"{case_id}/{arm}/{stage}/execution/bundle.json.gz"
        archive.bytes(relative)
        bundle, sid, bundle_sha = admit_bundle(
            compact_root / relative,
            raw_root / case_id / arm / stage / "execution",
            sources,
            EXPERIMENT + "/" + relative.removesuffix("/bundle.json.gz"),
        )
        case_source = bundle["case"]
        decision_name = "diagnostic-decision.json" if stage == "diagnostic" else "decision.json"
        decision_relative = f"{case_id}/{arm}/{stage}/{decision_name}"
        archive.bytes(decision_relative)
        decision_bundle, decision_bundle_sha = bundle, bundle_sha
        if case_id == "D08-old-future-replay":
            decision_bundle, decision_bundle_sha, controls = replay_decision_source(
                archive, raw_root, bundle, bundle_sha, case_id, arm
            )
            trial_projection["derived_controls"] = controls
        projected, original = admit_decision(
            compact_root / decision_relative, decision_bundle, decision_bundle_sha, stage, sources
        )
        if decision_bundle_sha != bundle_sha:
            projected["execution_bundle_sha256"] = bundle_sha
        decisions.append(store.put(projected, "decision"))
        stage_runs, stage_events, stage_reports = export_runs(
            bundle,
            sid,
            bundle_sha,
            raw_root / case_id / arm / stage / "execution",
            sources,
            store,
            bindings,
            EXPERIMENT + "/" + relative.removesuffix("/bundle.json.gz"),
            projected,
            stage,
        )
        runs.extend(stage_runs)
        events.extend(stage_events)
        reports.extend(stage_reports)
        if stage == "confirmation":
            confirmation = confirmation_projection(
                archive, case_id, arm, bundle, bundle_sha, original, trial
            )
    case_key = f"{EXPERIMENT}/{case_id}/{arm}"
    case = {
        "schema": "nisayon.ui-case.v1",
        "case_key": case_key,
        "case_id": case_id,
        "experiment_id": EXPERIMENT,
        "arm": arm,
        "task": case_source["task"],
        "predicates": case_source["predicates"],
        "runs": runs,
        "decisions": decisions,
        "findings": events,
        "trial": trial_projection,
        "confirmation": confirmation,
        "comparison_alignment": "Simulation seconds from each recorded reset. Prefix runs have their own run key and clock origin. Select actual samples; never extend an ended trajectory.",
        "limitations": [
            "Both original development comparisons found no decision or efficiency advantage.",
            "These are already observed scripted development conditions, not unseen faults or a safety claim.",
            "Original observations, reconstructed configurations, trial status and evaluator decisions are separate.",
            "No contacts are reconstructed. A before-frame residual compares the consumed observation, which may be stale.",
            "Costs retain source nesting and unavailable categories; they are not summed by the UI adapter.",
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
            "trial_status",
            "condition_pairs",
        ],
        "sources": list(sources.entries.values()),
        "cases": [{"case_key": case_key, "case_id": case_id, "object": case_ref}],
        "files": list(store.files.values()),
        "limitations": [
            "Local inspection only. No simulation, inference, contact reconstruction, mesh redistribution or new scientific outcome.",
            "One case per generation bounds decoding and optional scene resources during case switches.",
            "Byte integrity establishes the declared binding, not physical truth or independent experiment review.",
        ],
    }
    ref = store.put(manifest, "manifest")
    store.expose(ref)
    return {
        "case_key": case_key,
        "manifest": ref,
        "runs": reports,
        "trial_status": trial["status"],
        "decision_statuses": [parse(read(output / d["path"]))["decision"] for d in decisions],
        "output_bytes": sum(f["byte_length"] for f in store.files.values()) + ref["byte_length"],
    }
