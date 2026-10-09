"""Audit the explicit final population against a named committed owner delivery."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from collections import Counter
from pathlib import Path

from freeze_temporal_audit_coverage import build

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.temporal_audit import CoverageError, changed_paths, exact_index, owner_index
from nisayon.engine.temporal_store import _read, inspect_store
from nisayon.engine.temporal_workflow import load_assessment
from nisayon.evaluation import temporal


def git_bytes(repo, ref, path):
    relative = path.resolve().relative_to(repo.resolve()).as_posix()
    return subprocess.check_output(["git", "show", ref + ":" + relative], cwd=repo)


def pinned_json(repo, delivery, path):
    data = path.read_bytes()
    if git_bytes(repo, delivery, path) != data:
        raise CoverageError("owner_file_differs_from_delivery", path=str(path), delivery=delivery)
    return json.loads(data)


def read_owner(repo, path, delivery, coverage, *, installed):
    manifest = pinned_json(repo, delivery, path)
    source = manifest["source"]
    module = repo / "src/nisayon/evaluation/temporal.py"
    if (
        source.get("module_path") != "src/nisayon/evaluation/temporal.py"
        or source.get("module") != "nisayon.evaluation.temporal"
        or source.get("git_status_module") != ""
        or source.get("interpreter") != platform.python_version()
    ):
        raise CoverageError("unsupported_owner_source", source=source)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", source["git_head"], delivery], cwd=repo, check=True
    )
    actual = hashlib.sha256(git_bytes(repo, source["git_head"], module)).hexdigest()
    if source["module_sha256"] != actual:
        raise CoverageError("owner_module_binding", source=source)
    if installed and (
        actual != file_digest(module) or source["assessment_schema"] != temporal.ASSESSMENT_SCHEMA
    ):
        raise CoverageError("owner_reference_not_installed", source=source)
    directory = path.parent / "full"
    full = {p.stem: pinned_json(repo, delivery, p) for p in sorted(directory.glob("*.json"))}
    for population in manifest["populations"]:
        for row in population["rows"]:
            if population["name"] in {"demonstration", "interrupted_prefixes"}:
                # These two owner populations explicitly use canonical JSON
                # hashes. The frozen coverage independently binds their traces.
                canonical_hash = row["trace_sha256"]
            else:
                # Exported trace files have different whitespace from the raw
                # stores. Verify the named file bytes first, then its content.
                trace_path = repo / row["trace_path"]
                trace = pinned_json(repo, delivery, trace_path)
                if (
                    file_digest(trace_path) != row["trace_sha256"]
                    or trace_path.stat().st_size != row["trace_bytes"]
                ):
                    raise CoverageError("owner_trace_file_binding", path=str(trace_path))
                canonical_hash = digest(trace)
            row["trace_canonical_sha256"] = canonical_hash
    return manifest, owner_index(coverage, manifest, full, source)


def disposition_row(member, before, after, explanation, population, owner_trace_sha256):
    identity = member["identity"]
    if (
        explanation.get("trace_sha256") != owner_trace_sha256
        or explanation.get("case_id") != member["assignment"]["case_id"]
        or explanation.get("remedy_id") != member["assignment"]["remedy_id"]
    ):
        raise CoverageError("disposition_input_mismatch", population=population, identity=identity)
    statuses = {
        name: {
            "v1": before["predicates"][name]["status"],
            "v2": after["predicates"][name]["status"],
        }
        for name in before["predicates"]
    }
    if explanation.get("predicates") != statuses:
        raise CoverageError(
            "disposition_predicate_mismatch", population=population, identity=identity
        )
    # Check the owner's aggregate and retrospective readings too. This binds
    # the disposition to the full results without recreating semantic rules.
    for field, expected in {
        "temporal_contract": {"v1": before["temporal_contract"], "v2": after["temporal_contract"]},
        "completeness": {
            "v1": before["evidence"]["completeness"],
            "v2": after["evidence"]["completeness"],
        },
        "assigned_contract": after["assigned_contract"],
        **{
            name: after["retrospective"][name]["status"]
            for name in ("chunk_target_alignment", "observation_context", "chunk_identity")
        },
    }.items():
        if explanation.get(field) != expected:
            raise CoverageError(
                "disposition_summary_mismatch",
                population=population,
                identity=identity,
                field=field,
            )
    changed = [name for name, values in statuses.items() if values["v1"] != values["v2"]]
    reasons = exact_index(
        explanation["changes"],
        changed,
        key=lambda r: r["predicate"],
        scope=population + ":dispositions:" + identity,
    )
    for name, reason in reasons.items():
        if (
            reason.get("before") != statuses[name]["v1"]
            or reason.get("after") != statuses[name]["v2"]
            or not reason.get("reason")
            or not reason.get("issue")
        ):
            raise CoverageError(
                "unexplained_predicate_change", population=population, identity=identity
            )
    return {
        "changed_fields": changed_paths(before, after),
        "predicate_changes": explanation["changes"],
        "before_schema": before["schema"],
        "after_schema": after["schema"],
        "before_sha256": digest(before),
        "after_sha256": digest(after),
    }


def run_closeout(args, archive_packet):
    wall, cpu = time.perf_counter(), time.process_time()
    repo, root = Path.cwd(), args.reconciliation
    coverage = pinned_json(repo, "HEAD", args.coverage)
    if build(repo, coverage["frozen_input_commit"]) != coverage:
        raise CoverageError("coverage_or_original_inputs_changed")
    result, inputs = _read(root / "reconciliation.json"), _read(root / "reconciliation-inputs.json")
    if (
        result["stopped"] is not None
        or result["execution_performed"] is not False
        or result["inputs_sha256"] != file_digest(root / "reconciliation-inputs.json")
    ):
        raise CoverageError("reconciliation_incomplete_or_changed")
    if inputs["evaluation_delivery"] != result["evaluation_delivery"]:
        raise CoverageError("reconciliation_delivery_mismatch")
    module = repo / "src/nisayon/evaluation/temporal.py"
    if git_bytes(repo, result["evaluation_delivery"], module) != module.read_bytes():
        raise CoverageError("reconciliation_reference_not_installed")
    before_manifest, owner_before = read_owner(
        repo, args.owner_before, args.owner_delivery, coverage, installed=False
    )
    after_manifest, owner_after = read_owner(
        repo, args.owner_results, args.owner_delivery, coverage, installed=True
    )
    explanation = pinned_json(repo, args.owner_delivery, args.owner_dispositions)
    if (
        explanation["before"]["source"] != before_manifest["source"]
        or explanation["after"]["source"] != after_manifest["source"]
        or explanation["unexplained_changes"]
    ):
        raise CoverageError("disposition_source_or_unexplained_changes")
    expected_populations = [*coverage["populations"], coverage["prefix_population"]]
    explanations = exact_index(
        explanation["populations"],
        [p["owner_population"] for p in expected_populations],
        key=lambda p: p["name"],
        scope="disposition populations",
    )
    dispositions = {}
    owner_trace_hashes = {
        (p["name"], r["assignment_id"]): r["trace_sha256"]
        for p in after_manifest["populations"]
        for r in p["rows"]
    }
    for population in expected_populations:
        rows = explanations[population["owner_population"]]["rows"]
        dispositions[population["name"]] = exact_index(
            rows,
            [m["identity"] for m in population["members"]],
            key=lambda r: r["assignment_id"],
            scope=population["name"] + ":dispositions",
        )
    names = [p["name"] for p in coverage["populations"]]
    reconciled = exact_index(
        result["populations"], names, key=lambda p: p["name"], scope="reconciled populations"
    )
    declarations = exact_index(
        inputs["populations"],
        names,
        key=lambda p: p["name"],
        scope="reconciliation input populations",
    )
    populations, pairs, all_actual = [], [], {}
    for population in coverage["populations"]:
        name, packet = population["name"], Path(population["packet"])
        current, declared = reconciled[name], declarations[name]
        ids = [m["identity"] for m in population["members"]]
        if (
            current["status"] != "readback_complete"
            or current["assignment_count"] != len(ids)
            or current["complete_records"] != len(ids)
            or declared["suite_sha256"] != population["suite_sha256"]
            or (repo / declared["packet"]).resolve() != packet.resolve()
        ):
            raise CoverageError("reconciliation_population_binding", population=name)
        indexed = exact_index(
            current["rows"],
            ids,
            key=lambda r: r["assignment"]["id"],
            scope=name + ":reconciled rows",
        )
        saved = load_assessment(root / name, packet)
        sealed = exact_index(
            saved["assignments"],
            ids,
            key=lambda r: r["assignment"]["id"],
            scope=name + ":sealed rows",
        )
        rows = []
        for member in population["members"]:
            identity = member["identity"]
            row, sealed_row = indexed[identity], sealed[identity]
            detail_path = root / row["current_detail"]["path"]
            if (
                not detail_path.resolve().is_relative_to(root.resolve())
                or file_digest(detail_path) != row["current_detail"]["sha256"]
                or detail_path.resolve() != (root / name / sealed_row["detail"]["path"]).resolve()
                or row["current_detail"]["sha256"] != sealed_row["detail"]["sha256"]
            ):
                raise CoverageError(
                    "reconciliation_detail_binding", population=name, identity=identity
                )
            detail = _read(detail_path)
            reference = detail["reference_assessment"]
            if (
                row["assignment"] != member["assignment"]
                or detail["assignment"] != member["assignment"]
                or detail["row"]["assignment"] != member["assignment"]
                or row["input_snapshot_sha256"] != member["snapshot_sha256"]
                or row["trace_sha256"] != member["trace_sha256"]
                or row["original_execution_costs"] != sealed_row["original_execution_costs"]
                or digest(row["original_execution_costs"]) != member["original_costs_sha256"]
                or row["process_outcome"] != sealed_row["process_outcome"]
                or row["integrity"] != sealed_row["integrity"]
                or row["complete_record"] != sealed_row["complete_record"]
                or row["assigned_contract"] != sealed_row["assigned_contract"]
                or row["contract_after"] != sealed_row["temporal_contract"]
                or row["trace_sha256"] != sealed_row["trace_sha256"]
                or row["input_snapshot_sha256"] != sealed_row["input_snapshot_sha256"]
            ):
                raise CoverageError(
                    "reconciled_execution_binding", population=name, identity=identity
                )
            if sealed_row.get("attempt_id") != member["recorded_execution_identity"].get(
                "attempt_id"
            ):
                raise CoverageError("attempt_identity_changed", population=name, identity=identity)
            if reference != owner_after[(name, identity)]:
                raise CoverageError(
                    "owner_assessment_disagrees", population=name, identity=identity
                )
            historical = row["historical_result"]
            if file_digest(repo / historical["path"]) != historical["sha256"]:
                raise CoverageError(
                    "historical_assessment_changed", population=name, identity=identity
                )
            old = _read(repo / historical["path"])
            old = old.get("reference_assessment", old)
            delta = disposition_row(
                member,
                owner_before[(name, identity)],
                reference,
                dispositions[name][identity],
                name,
                owner_trace_hashes[(population["owner_population"], identity)],
            )
            rows.append(
                {
                    "identity": identity,
                    "assignment": member["assignment"],
                    "recorded_execution_identity": member["recorded_execution_identity"],
                    "snapshot_sha256": member["snapshot_sha256"],
                    "trace_sha256": member["trace_sha256"],
                    "process_outcome": row["process_outcome"],
                    "integrity": row["integrity"],
                    "reference_result": row["current_detail"],
                    "historical_result": historical,
                    "changed_fields_from_original_assessment": changed_paths(old, reference),
                    "named_correction_delta": delta,
                    "temporal_contract": reference["temporal_contract"],
                    "assigned_contract": reference["assigned_contract"],
                    "assigned_usefulness": reference["assigned_usefulness"],
                    "robot_task_outcome": "unmeasured",
                    "owner_assessment_equal": True,
                    "original_costs_unchanged": True,
                }
            )
            all_actual[(name, identity)] = reference
        members = {m["identity"]: m for m in population["members"]}
        for pair in population["required_pairs"]:
            selected, conventional = members[pair["selected"]], members[pair["conventional"]]
            same_events = selected["events_sha256"] == conventional["events_sha256"]
            same_assessment = (
                all_actual[(name, pair["selected"])] == all_actual[(name, pair["conventional"])]
            )
            if (
                not same_events
                or not same_assessment
                or selected["case_sha256"] != pair["case_sha256"]
                or conventional["case_sha256"] != pair["case_sha256"]
            ):
                raise CoverageError("comparator_pair_disagrees", population=name, pair=pair)
            pairs.append(
                {
                    "population": name,
                    **pair,
                    "events_equal": same_events,
                    "full_assessments_equal": same_assessment,
                }
            )
        populations.append(
            {"name": name, "assignments": len(rows), "owner_coverage": "complete", "rows": rows}
        )
    prefixes = []
    for member in coverage["prefix_population"]["members"]:
        identity = member["identity"]
        inspection = inspect_store(Path(member["store"]))
        if (
            inspection["snapshot_sha256"] != member["snapshot_sha256"]
            or digest(inspection["trace"]) != member["trace_sha256"]
            or digest(inspection["costs"]) != member["original_costs_sha256"]
            or inspection["integrity"] != "verified_prefix"
            or inspection["process_outcome"] != "unknown"
        ):
            raise CoverageError("prefix_evidence_changed", identity=identity)
        reference = temporal.assess(inspection["trace"])
        if (
            reference != owner_after[("interrupted_prefixes", identity)]
            or reference["assigned_contract"] == "satisfied"
        ):
            raise CoverageError("prefix_interpretation_disagrees", identity=identity)
        delta = disposition_row(
            member,
            owner_before[("interrupted_prefixes", identity)],
            reference,
            dispositions["interrupted_prefixes"][identity],
            "interrupted_prefixes",
            owner_trace_hashes[("interrupted_prefixes", identity)],
        )
        prefixes.append(
            {
                "identity": identity,
                "store": member["store"],
                "snapshot_sha256": inspection["snapshot_sha256"],
                "trace_sha256": member["trace_sha256"],
                "process_outcome": inspection["process_outcome"],
                "integrity": inspection["integrity"],
                "original_execution_costs": inspection["costs"],
                "reference_assessment": reference,
                "named_correction_delta": delta,
                "owner_assessment_equal": True,
                "retry_performed": False,
            }
        )
    archive = archive_packet(root, args.archive)
    report = {
        "schema": "nisayon.temporal-reconciliation-audit.v2",
        "status": "complete",
        "coverage_manifest": {"path": str(args.coverage), "sha256": file_digest(args.coverage)},
        "reconciliation_sha256": file_digest(root / "reconciliation.json"),
        "evaluation_delivery": result["evaluation_delivery"],
        "reader_source": result["reader_source"],
        "owner_delivery": args.owner_delivery,
        "owner_before": {"path": str(args.owner_before), "sha256": file_digest(args.owner_before)},
        "owner_after": {"path": str(args.owner_results), "sha256": file_digest(args.owner_results)},
        "owner_dispositions": {
            "path": str(args.owner_dispositions),
            "sha256": file_digest(args.owner_dispositions),
        },
        "owner_coverage": {
            "status": "complete",
            "assignments": sum(p["assignments"] for p in populations),
            "prefixes": len(prefixes),
            "missing": [],
        },
        "populations": populations,
        "conventional_selected_pairs": pairs,
        "pairs_by_population": dict(Counter(p["population"] for p in pairs)),
        "prefixes": prefixes,
        "retained_archive": archive,
        "current_costs": {
            "wall_s_before_final_write": time.perf_counter() - wall,
            "cpu_s_before_final_write": time.process_time() - cpu,
        },
        "execution_performed": False,
        "scientific_acceptance": "not_granted",
        "boundary": "All frozen role assignments and separately scoped interrupted prefixes. Identity and full-result agreement are internal engineering checks, not independent replication or robot acceptance. Every before/after field remains retained; historical execution costs are not new charges.",
    }
    write_json(args.out, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "owner_coverage": report["owner_coverage"],
                "pairs": report["pairs_by_population"],
                "archive_bytes": archive["bytes"],
                "costs": report["current_costs"],
            }
        )
    )
