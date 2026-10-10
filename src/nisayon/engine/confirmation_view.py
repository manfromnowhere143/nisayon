"""Read-only, source-bound confirmation evidence export. No robot execution."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from .confirmation_costs import reconcile, trial_costs
from .confirmation_pairs import assigned_pairs, iter_pairs
from .development_diagnostics import measured_run_costs
from .io import canonical_bytes, decode_json, digest, file_digest, write_json
from .recovery import inspect_execution
from .store import resolve_member, verify_execution, verify_manifest

INPUTS = "docs/experiments/results/confirmation-engine-001/inputs.json"


def _json(data: bytes) -> dict:
    result = decode_json(data)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def dependencies(repo: Path) -> dict:
    paths = sorted((repo / "src/nisayon/engine").glob("*.py"))
    paths += sorted((repo / "src/nisayon/evaluation").glob("*.py"))
    paths += [repo / "uv.lock", repo / "pyproject.toml"]
    paths += sorted((repo / "docs/evaluation/results/confirmation-feasibility-001").glob("*.py"))
    paths += sorted(
        (repo / "docs/evaluation/results/confirmation-feasibility-001").glob("spec.json")
    )
    return {
        **{str(p.relative_to(repo)): file_digest(p) for p in paths},
        "runtime_python": {
            "version": sys.version,
            "implementation": sys.implementation.name,
            "executable_sha256": file_digest(Path(sys.executable).resolve()),
        },
    }


class PinnedInputs:
    """Pinned Git bytes define membership; changed local copies remain explicit."""

    def __init__(self, repo: Path, commit: str):
        self.repo = repo.resolve()
        self.commit = subprocess.check_output(
            ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=repo, text=True
        ).strip()
        self.sources: dict[str, dict] = {}
        self.cache: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        if path not in self.cache:
            data = subprocess.check_output(["git", "show", f"{self.commit}:{path}"], cwd=self.repo)
            expected = hashlib.sha256(data).hexdigest()
            try:
                actual = file_digest(resolve_member(self.repo, path))
            except (OSError, ValueError):
                actual = None
            self.sources[path] = {
                "path": path,
                "expected_sha256": expected,
                "observed_sha256": actual,
                "status": "unchanged" if actual == expected else "missing_or_changed",
            }
            self.cache[path] = data
        return self.cache[path]

    def document(self, path: str) -> dict:
        return _json(self.read(path))

    def issues(self, prefix: str) -> list[str]:
        return [
            f"source_missing_or_changed:{name}"
            for name, source in self.sources.items()
            if name.startswith(prefix) and source["status"] != "unchanged"
        ]


def _bound_document(reader: PinnedInputs, base: str, reference: dict) -> dict:
    name = f"{base}/{reference['path']}"
    document = reader.document(name)
    if reader.sources[name]["expected_sha256"] != reference["sha256"]:
        raise ValueError(f"Pinned metadata reference disagrees: {name}")
    return document


def _raw_confirmation(
    reader: PinnedInputs, base: str, root: Path, result: dict, header: dict, protocol: dict
) -> tuple[dict, dict, list[str], dict]:
    issues = []
    timings = {}
    start = time.perf_counter()
    bundle = None
    source = {
        "root_locator": str(root),
        "bundle_sha256_expected": result["bundle_sha256"],
        "status": "unavailable",
        "files": [],
    }
    try:
        bundle_path = resolve_member(root, "bundle.json")
        data = bundle_path.read_bytes()
        source["bundle_sha256_observed"] = hashlib.sha256(data).hexdigest()
        bundle = _json(data)
        if source["bundle_sha256_observed"] != result["bundle_sha256"]:
            issues.append("raw_bundle_bytes_changed")
    except (OSError, ValueError) as error:
        issues.append(f"raw_bundle_unavailable:{error}")
    if bundle is None:
        # Compact evidence permits inspection, never raw-evidence admission.
        compact = reader.read(f"{base}/execution/bundle.json.gz")
        data = gzip.decompress(compact)
        if hashlib.sha256(data).hexdigest() != result["bundle_sha256"]:
            issues.append("compact_bundle_bytes_disagree_with_result")
        bundle = _json(data)
        source["fallback"] = "pinned_compact_bundle; raw evidence still required"
    timings["bundle_read_and_decode_s"] = time.perf_counter() - start
    start = time.perf_counter()
    try:
        if bundle.get("confirmation") != header.get("confirmation"):
            raise ValueError("Raw confirmation header differs from pinned header")
        if (
            file_digest(resolve_member(root, "frozen-protocol.json"))
            != reader.sources[f"{base}/execution/frozen-protocol.json"]["expected_sha256"]
        ):
            raise ValueError("Raw frozen protocol differs from pinned result")
        source["verification"] = verify_execution(bundle, root)
        # Recheck every manifest member after verification. No path/mtime cache.
        members = verify_manifest(root, bundle["artifact_manifest"])
        source["files"] = list(members.values())
        manifest = bundle["artifact_manifest"]
        source["files"].append(
            {"path": manifest["path"], "sha256": manifest["sha256"], "bytes": None}
        )
        source["files"].append(
            {"path": "bundle.json", "sha256": source["bundle_sha256_observed"], "bytes": None}
        )
        if file_digest(resolve_member(root, "bundle.json")) != source["bundle_sha256_observed"]:
            raise ValueError("Bundle changed during inspection")
        source["status"] = "verified" if not issues else "invalid"
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        issues.append(f"raw_integrity_unavailable_or_invalid:{error}")
        source["status"] = "incomplete_or_invalid"
        try:
            source["recovery"] = inspect_execution(root)
            # Processing time belongs to the command receipt, not the stable view.
            source["recovery"].pop("inspected_at", None)
        except (OSError, ValueError, KeyError, TypeError) as recovery_error:
            source["recovery"] = {"status": "unavailable", "reason": str(recovery_error)}
    if bundle.get("assignments") != protocol.get("assignments"):
        issues.append("raw_assignments_differ_from_pinned_protocol")
    timings["required_verification_s"] = time.perf_counter() - start
    return bundle, source, issues, timings


def _trial(
    reader: PinnedInputs, comparison: str, case: dict, arm: str, raw_base: Path, ledger: dict
) -> tuple[dict, dict]:
    start = time.perf_counter()
    base = f"docs/experiments/results/{comparison}"
    trial_base = f"{base}/{case['id']}/{arm}"
    trial = reader.document(f"{trial_base}/trial.json")
    expected_trials = [
        t for t in ledger["trials"] if t.get("case_id") == case["id"] and t.get("arm") == arm
    ]
    issues = []
    if len(expected_trials) != 1 or expected_trials[0] != trial:
        issues.append("trial_does_not_match_unique_ledger_assignment")
    if (trial.get("case_id"), trial.get("arm")) != (case["id"], arm):
        issues.append("trial_identity_mismatch")
    if trial.get("received_frozen_sha256") != digest(case["frozen"]):
        issues.append("trial_received_inputs_differ_from_frozen_case")
    decision = _bound_document(reader, base, trial["decision"]) if trial.get("decision") else None
    diagnosis = (
        _bound_document(reader, base, trial["diagnosis"]) if trial.get("diagnosis") else None
    )
    output = {
        "comparison": comparison,
        "case_id": case["id"],
        "arm": arm,
        "original_incident_id": case.get("original_incident_id", case["id"]),
        "repetition_id": case["id"] if case.get("original_incident_id") else None,
        "historical_status": trial.get("status"),
        "historical_decision": decision,
        "frozen_condition_reservations": {
            "condition_ids": case["frozen"]["confirmation_condition_ids"],
            "status": "confirmation_scheduled"
            if trial.get("confirmation")
            else "never_reached_confirmation",
            "reuse": "Conditions remain consumed/reserved under the original protocol; no new allocation.",
        },
        "diagnostic": {
            "result": trial.get("diagnosis"),
            "rollouts": trial.get("diagnostic_rollouts"),
            "records_retained": trial.get("diagnostic_records_retained"),
            "timeline": trial.get("timeline"),
            "proposals": trial.get("proposals"),
            "status": diagnosis.get("status") if diagnosis else None,
            "recorded_run_costs": diagnosis.get("costs") if diagnosis else None,
            "phase_wall_s": diagnosis.get("phase_wall_s") if diagnosis else None,
            "diagnostic_final_check_wall_s": diagnosis.get("diagnostic_final_check_wall_s")
            if diagnosis
            else None,
            "bundle_source": {
                "path": diagnosis.get("bundle_path"),
                "sha256": diagnosis.get("bundle_sha256"),
                "root_locator": str(raw_base / comparison / case["id"] / arm / "diagnostic"),
                "verification": "diagnostic source referenced, not reverified by this confirmation reader",
            }
            if diagnosis
            else None,
            "partition": "diagnostic; excluded from confirmation pairs",
        },
        "retries": trial.get("retries"),
        "declaration": {
            "contract": trial.get("declaration_contract"),
            "reference": trial.get("arm_declaration"),
            "legacy_claim": trial.get("arm_claimed_acceptance"),
            "timing": "legacy result-derived claim, not a prospective declaration"
            if not trial.get("declaration_contract")
            else "inspect bound declaration timestamps",
            "exposure": "retained exposed development evidence; later demonstrations remain retrospective",
        },
        "confirmation": None,
    }
    result = None
    timings = {}
    if trial.get("confirmation"):
        result = _bound_document(reader, base, trial["confirmation"])
        confirmation_base = f"{trial_base}/confirmation"
        header = reader.document(f"{confirmation_base}/execution/bundle-header.json")
        protocol = reader.document(f"{confirmation_base}/execution/frozen-protocol.json")
        # The producer's protocol identity is a canonical-content digest;
        # the independently retained source binding is a file-bytes digest.
        protocol_hash = digest(protocol)
        if (
            result.get("case_id") != case["id"]
            or result.get("arm") != arm
            or result.get("protocol_sha256") != protocol_hash
            or digest(protocol["candidate"]) != result.get("candidate_digest")
            or result.get("candidate_digest") != trial.get("decision", {}).get("candidate_digest")
        ):
            issues.append("confirmation_result_identity_mismatch")
        if protocol["condition_ids"] != case["frozen"]["confirmation_condition_ids"]:
            issues.append("protocol_conditions_differ_from_frozen_suite")
        root = raw_base / comparison / case["id"] / arm / "confirmation/execution"
        bundle, raw, raw_issues, timings = _raw_confirmation(
            reader, confirmation_base, root, result, header, protocol
        )
        issues += raw_issues + reader.issues(trial_base)
        identity = {
            key: output[key]
            for key in ("comparison", "case_id", "arm", "original_incident_id", "repetition_id")
        }
        identity.update(
            candidate_sha256=result["candidate_digest"],
            protocol_sha256=protocol_hash,
            protocol_id=protocol["protocol_id"],
        )
        evidence = assigned_pairs(bundle, protocol, identity, binding_issues=issues)
        if any(pair["state"] != "complete" for pair in evidence["pairs"]):
            issues.append("assigned_pair_evidence_incomplete_or_invalid")
        try:
            costs = measured_run_costs(bundle.get("runs", []))
            cost_check = {"recomputed": costs, "matches_recorded": costs == result.get("costs")}
        except (KeyError, ValueError, TypeError) as error:
            cost_check = {"recomputed": None, "matches_recorded": False, "reason": str(error)}
        if not cost_check["matches_recorded"]:
            issues.append("run_costs_differ_or_cannot_be_reconciled")
        output["confirmation"] = {
            **evidence,
            "protocol": protocol,
            "raw_source": raw,
            "run_cost_check": cost_check,
            "identity": identity,
        }
    output["costs"] = trial_costs(trial, result, assigned=bool(trial.get("confirmation")))
    issues += reader.issues(base + "/frozen-suite.json")
    issues += reader.issues(base + "/comparison-")
    issues += reader.issues(trial_base)
    output["issues"] = sorted(set(issues))
    output["state"] = (
        "incomplete_or_invalid"
        if issues
        else ("complete" if result else "confirmation_not_scheduled")
    )
    if output["confirmation"] and issues:
        for pair in output["confirmation"]["pairs"]:
            pair["state"] = "incomplete_or_invalid"
            pair["issues"] = sorted(set(pair["issues"] + issues))
    timings["extraction_s"] = time.perf_counter() - start - sum(timings.values())
    return output, timings


def build_view(
    repo: Path,
    spec: dict,
    *,
    raw_base: Path | None = None,
    selection: list[list[str]] | None = None,
) -> tuple[dict, dict]:
    """No cached verdict: every invocation rereads and verifies the input bytes."""
    start = time.perf_counter()
    repo = repo.resolve()
    raw_base = (raw_base or repo / spec["raw_root"]).resolve()
    before = dependencies(repo)
    reader = PinnedInputs(repo, spec["source_commit"])
    trials, scores, membership, timings, jobs = [], {}, [], [], []
    for comparison in spec["comparisons"]:
        base = f"docs/experiments/results/{comparison}"
        suite = reader.document(f"{base}/frozen-suite.json")
        ledger = reader.document(f"{base}/comparison-ledger.json")
        score = reader.document(f"{base}/comparison-score.json")
        scores[comparison] = score
        assigned = [(case["id"], arm["id"]) for case in suite["cases"] for arm in suite["arms"]]
        original = [(t["case_id"], t["arm"]) for t in ledger["trials"]]
        scored = [
            (case, arm) for case, value in score["cases"].items() for arm in value["outcomes"]
        ]
        if (
            len(set(assigned)) != len(assigned)
            or sorted(original) != sorted(assigned)
            or sorted(scored) != sorted(assigned)
        ):
            raise ValueError("Original score/ledger trial membership differs from frozen suite")
        membership.append(
            {"comparison": comparison, "assigned_trials": assigned, "ledger_and_score_match": True}
        )
        for case in suite["cases"]:
            for arm in suite["arms"]:
                key = [comparison, case["id"], arm["id"]]
                if selection is not None and key not in selection:
                    continue
                jobs.append((comparison, case, arm["id"], ledger))
    if selection is not None:
        by_key = {(job[0], job[1]["id"], job[2]): job for job in jobs}
        keys = [tuple(key) for key in selection]
        if len(set(keys)) != len(keys) or any(key not in by_key for key in keys):
            raise ValueError("Selection must name unique assigned trials")
        jobs = [by_key[key] for key in keys]
    for comparison, case, arm, ledger in jobs:
        trial, timing = _trial(reader, comparison, case, arm, raw_base, ledger)
        trials.append(trial)
        timings.append({"trial": [comparison, case["id"], arm], **timing})
    changed = []
    for name, source in reader.sources.items():
        try:
            current = file_digest(resolve_member(repo, name))
        except (OSError, ValueError):
            current = None
        if current != source["observed_sha256"]:
            changed.append(name)
    after = dependencies(repo)
    if changed or after != before:
        raise ValueError(f"Input/dependency changed during export: {changed}")
    view = {
        "schema": "nisayon.confirmation-view.v1",
        "status": "proposed_read_only_view",
        "source_commit": reader.commit,
        "input_spec": spec,
        "input_spec_sha256": digest(spec),
        "dependencies": before,
        "sources": list(reader.sources.values()),
        "assignment_membership": membership,
        "selection": selection,
        "order": spec["order"],
        "trials": trials,
        "costs": reconcile(trials, scores) if selection is None else None,
        "limits": [
            "Raw evidence remains authoritative. Complete means structurally bound, not scientifically accepted.",
            "Development conditions are exposed; seeds and repetitions do not establish independent incidents, exchangeability or stationarity.",
            "Retrospective prefix analysis is neither fresh confirmation nor a robot counterfactual.",
            "Progress is in meters without clipping, normalization or an inferred score range.",
            "This reader provides no exactly-once execution service and changes no stopping rule.",
        ],
        "scientific_acceptance": "none",
    }
    return view, {"trials": timings, "total_read_wall_s": time.perf_counter() - start}


def validate_view(view: dict, repo: Path, *, expected_content_sha256: str) -> dict:
    """Check the retained output digest as well as all input/dependency bytes.

    The caller obtains the expected digest from its retained output manifest;
    hashes bind bytes, not an author's authority or the truth of a measurement.
    """
    issues = []
    if digest(view) != expected_content_sha256:
        issues.append("derived_view_bytes_changed")
    if dependencies(repo) != view["dependencies"]:
        issues.append("adapter_or_evaluation_dependency_changed")
    for source in view["sources"]:
        try:
            current = file_digest(resolve_member(repo, source["path"]))
        except (OSError, ValueError):
            current = None
        if current != source["observed_sha256"] or source["status"] != "unchanged":
            issues.append(f"metadata_unavailable_or_changed:{source['path']}")
    for trial in view["trials"]:
        if trial["state"] == "incomplete_or_invalid":
            issues.append(f"trial_incomplete_or_invalid:{trial['case_id']}/{trial['arm']}")
        if not trial["confirmation"]:
            continue
        raw = trial["confirmation"]["raw_source"]
        for source in raw["files"]:
            try:
                current = file_digest(resolve_member(Path(raw["root_locator"]), source["path"]))
            except (OSError, ValueError):
                current = None
            if current != source["sha256"]:
                issues.append(f"raw_unavailable_or_changed:{raw['root_locator']}/{source['path']}")
    return {"status": "current" if not issues else "invalidated", "issues": issues}


def load_export(directory: Path, repo: Path) -> tuple[dict, dict]:
    """Read an export with its output manifest, then revalidate dependencies."""
    manifest = _json(resolve_member(directory, "manifest.json").read_bytes())
    view_path = resolve_member(directory, "view.json")
    if file_digest(view_path) != manifest["view_sha256"]:
        raise ValueError("Derived view file differs from its retained output manifest")
    for name, expected in manifest["files"].items():
        if file_digest(resolve_member(directory, name)) != expected:
            raise ValueError(f"Export output differs from its manifest: {name}")
    view = _json(view_path.read_bytes())
    return view, validate_view(view, repo, expected_content_sha256=manifest["view_sha256"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--inputs", type=Path, default=Path(INPUTS))
    parser.add_argument("--raw-base", type=Path)
    parser.add_argument("--trial", nargs=3, action="append", metavar=("COMPARISON", "CASE", "ARM"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = _json(args.inputs.read_bytes())
    if args.out.exists():
        parser.error("Use a new output directory; prior attempts are retained")
    raw_base = (args.raw_base or args.repo / spec["raw_root"]).resolve()
    for comparison in spec["comparisons"]:
        for protected in (
            raw_base / comparison,
            args.repo / "docs/experiments/results" / comparison,
        ):
            if args.out.resolve().is_relative_to(protected.resolve()):
                parser.error("Export must be outside the original evidence stores")
    view, timing = build_view(args.repo, spec, raw_base=args.raw_base, selection=args.trial)
    start = time.perf_counter()
    data = canonical_bytes(view)
    timing["serialization_s"] = time.perf_counter() - start
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "view.json").write_bytes(data)
    write_json(args.out / "costs.json", view["costs"])
    write_json(args.out / "timing.json", timing)
    manifest = {
        "schema": "nisayon.confirmation-export.v1",
        "source_commit": view["source_commit"],
        "view_sha256": hashlib.sha256(data).hexdigest(),
        "output_bytes": len(data),
        "files": {p.name: file_digest(p) for p in sorted(args.out.iterdir())},
        "assigned_trials": len(view["trials"]),
        "assigned_pairs": sum(1 for _ in iter_pairs(view)),
        "incomplete_pairs": sum(p["state"] != "complete" for p in iter_pairs(view)),
        "scientific_acceptance": "none",
    }
    write_json(args.out / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
