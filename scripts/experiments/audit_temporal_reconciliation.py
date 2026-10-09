"""Compare the sealed execution readback with the evaluation owner's delivery.

Read retained results and interrupted stores only. Archive every reassessment
member without changing its bytes; do not execute or repair a software schedule.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import tarfile
import time
from collections import Counter
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.temporal_store import _read, inspect_store
from nisayon.evaluation.temporal import assess

RESULTS = Path("docs/experiments/results/temporal-integration-001")
OWNER = Path("docs/evaluation/results/temporal-integration-001/followthrough")


def archive_packet(root: Path, target: Path) -> dict:
    members = {
        p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": file_digest(p)}
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w|") as archive:
            for name, expected in members.items():
                payload = (root / name).read_bytes()
                if digest_bytes(payload) != expected["sha256"]:
                    raise ValueError("Reassessment member changed while archiving")
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(payload), 0o644, 0
                archive.addfile(info, io.BytesIO(payload))
    # Verify the archived payloads by reading them, without extracting or
    # importing their contents. Retained raw and archive copies are counted.
    seen = {}
    with tarfile.open(target, "r:gz") as archive:
        for member in archive:
            if not member.isfile():
                raise ValueError("Unexpected archive member")
            stream = archive.extractfile(member)
            assert stream is not None
            data = stream.read()
            seen[member.name] = {"bytes": len(data), "sha256": digest_bytes(data)}
    if seen != members:
        raise ValueError("Archive does not preserve every reassessment byte")
    return {
        "path": str(target),
        "sha256": file_digest(target),
        "bytes": target.stat().st_size,
        "members": members,
        "verified_by_readback": True,
    }


def digest_bytes(data: bytes) -> str:
    from hashlib import sha256

    return sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument("--owner-results", type=Path)
    parser.add_argument("--owner-before", type=Path)
    parser.add_argument("--owner-dispositions", type=Path)
    parser.add_argument("--owner-delivery")
    args = parser.parse_args()
    final_options = (
        args.coverage,
        args.owner_results,
        args.owner_before,
        args.owner_dispositions,
        args.owner_delivery,
    )
    if any(final_options):
        if not all(final_options):
            parser.error("Final coverage audit requires every --owner-* option and --coverage")
        from audit_temporal_closeout import run_closeout

        from nisayon.engine.temporal_audit import CoverageError

        try:
            run_closeout(args, archive_packet)
        except CoverageError as error:
            write_json(
                args.out,
                {
                    "schema": "nisayon.temporal-reconciliation-audit.v2",
                    "status": "incomplete_or_invalid",
                    "issue": error.details,
                    "scientific_acceptance": "not_granted",
                },
            )
            print(json.dumps(error.details))
            raise SystemExit(1) from error
        return
    wall, cpu = time.perf_counter(), time.process_time()
    root = args.reconciliation
    result = _read(root / "reconciliation.json")
    assert result["stopped"] is None and result["execution_performed"] is False
    owner_comparison = _read(OWNER / "comparison.json")
    assert not owner_comparison["unexplained_changes"]
    resolutions = _read(OWNER / "disagreements-resolution.json")
    assert len(resolutions["table"]) == 59 and not resolutions["expectations_edited"]
    populations, owner_agreement, ties = [], [], []
    for population in result["populations"]:
        name = population["name"]
        assert population["status"] == "readback_complete"
        assert population["complete_records"] == population["assignment_count"]
        owner_path = OWNER / "after/full" / (name + ".json")
        owner_results = (
            {row["assignment_id"]: row["assessment"] for row in json.loads(owner_path.read_bytes())}
            if owner_path.exists()
            else None
        )
        actual, matrix = {}, []
        for row in population["rows"]:
            detail_path = root / row["current_detail"]["path"]
            assert file_digest(detail_path) == row["current_detail"]["sha256"]
            detail = _read(detail_path)
            assert detail["assignment"] == row["assignment"]
            reference = detail["reference_assessment"]
            identity = row["assignment"]["id"]
            actual[identity] = reference
            useful = reference["assigned_usefulness"]
            matrix.append(
                {
                    "assignment": row["assignment"],
                    "legacy_contract": reference["temporal_contract"],
                    "legacy_useful_execution": reference["useful_execution"]["status"],
                    "assigned_contract": reference["assigned_contract"],
                    "assigned_usefulness": {
                        k: v for k, v in useful.items() if k not in {"rows", "premise"}
                    },
                    "retrospective": {
                        k: v["status"]
                        for k, v in reference["retrospective"].items()
                        if isinstance(v, dict) and "status" in v
                    },
                }
            )
            if row["assignment"]["remedy_id"] == "selected_intervention":
                other = identity.removesuffix("selected_intervention") + "conventional"
                # Compare complete semantic records after all members are read.
                ties.append({"population": name, "selected": identity, "conventional": other})
        if owner_results is not None:
            assert actual == owner_results, name
            owner_agreement.append(
                {
                    "population": name,
                    "assignments": len(actual),
                    "owner_sha256": file_digest(owner_path),
                }
            )
        for pair in ties:
            if pair["population"] == name:
                assert actual[pair["selected"]] == actual[pair["conventional"]]
                pair["full_assessments_equal"] = True
        populations.append(
            {k: v for k, v in population.items() if k not in {"rows", "current_assessment_costs"}}
            | {"matrix": matrix}
        )
    assert sum(p["assignment_count"] for p in populations) == 190
    assert sum(p["assignments"] for p in owner_agreement) == 178
    prefix_owner = {
        row["assignment_id"]: row["assessment"]
        for row in json.loads((OWNER / "after/full/interrupted_prefixes.json").read_bytes())
    }
    prefixes = []
    for historical in _read(RESULTS / "recovery-001.json")["assignments"]:
        store = Path(historical["raw_store"])
        inspection = inspect_store(store)
        old_inspection = _read(Path(historical["inspection"]["path"]))
        changes = {}
        for key in old_inspection.keys() | inspection.keys():
            before, after = old_inspection.get(key), inspection.get(key)
            if before == after:
                continue
            if key == "raw_event_records":
                assert key not in old_inspection and isinstance(after, list)
                reason = "Current inspector exposes the already retained raw event envelopes."
            elif key in {"evidence_gaps", "unacknowledged_attempts"}:
                assert [
                    {k: v for k, v in row.items() if k != "dispatch_id"} for row in after
                ] == before
                dispatched = {
                    e["seq"]: e
                    for e in inspection["trace"]["events"]
                    if e["kind"] == "action_dispatched"
                }
                for row in after:
                    if "dispatch_id" in row:
                        event = dispatched[row["event_seq"]]
                        assert row["dispatch_id"] == event["dispatch_id"]
                        assert row["action_id"] == event["action_id"]
                reason = (
                    "Current inspector names the dispatch identity present in the original event."
                )
            else:
                raise ValueError(f"Unexpected change to interrupted-store inspection: {key}")
            changes[key] = {"before": before, "after": after, "reason": reason}
        assert inspection["integrity"] == "verified_prefix"
        assert inspection["process_outcome"] == "unknown"
        reference = assess(inspection["trace"])
        identity = inspection["assignment"]["id"] + "@" + historical["stage"]
        assert reference == prefix_owner[identity], identity
        # The final opportunity's send can meet the raw dispatch minimum on
        # an interrupted prefix. It neither supplies its missing acknowledgement
        # nor establishes process completion or the complete assigned contract.
        assert reference["assigned_contract"] != "satisfied"
        prefixes.append(
            {
                "identity": identity,
                "store": str(store),
                "snapshot_sha256": inspection["snapshot_sha256"],
                "original_snapshot_trace_and_costs_unchanged": True,
                "inspection_field_changes": changes,
                "integrity": inspection["integrity"],
                "process_outcome": inspection["process_outcome"],
                "original_execution_costs": inspection["costs"],
                "reference_assessment": reference,
                "owner_assessment_equal": True,
                "retry_performed": False,
            }
        )
    archive = archive_packet(root, args.archive)
    report = {
        "schema": "nisayon.temporal-reconciliation-audit.v1",
        "driver_sha256": file_digest(Path(__file__)),
        "reconciliation_sha256": file_digest(root / "reconciliation.json"),
        "evaluation_delivery": result["evaluation_delivery"],
        "execution_source": result["reader_source"],
        "populations": populations,
        "owner_full_assessment_agreement": owner_agreement,
        "conventional_selected_pairs": ties,
        "pairs_by_population": dict(Counter(p["population"] for p in ties)),
        "prefixes": prefixes,
        "original_usefulness_disagreements": {
            "count": 59,
            "resolution_source": str(OWNER / "disagreements-resolution.json"),
            "sha256": file_digest(OWNER / "disagreements-resolution.json"),
            "resolutions": resolutions["resolutions"],
            "expectations_edited": False,
        },
        "retained_archive": archive,
        "current_costs": {
            "wall_s_before_final_write": time.perf_counter() - wall,
            "cpu_s_before_final_write": time.process_time() - cpu,
            "scope": "Readback comparison, three prefix assessments and verified archiving; all original costs and reassessment costs are historical, not added again.",
        },
        "new_queue_executions": 0,
        "new_simulator_executions": 0,
        "robot_task_outcome": "unmeasured",
        "scientific_acceptance": "not_granted",
        "boundary": "Agreement between the owner reference and this verified-record adapter is an integration check, not independent experimental replication. Retrospective readings remain outside both frozen contracts.",
    }
    write_json(args.out, report)
    print(
        json.dumps(
            {
                "assignments": 190,
                "owner_matches": 178,
                "prefixes": 3,
                "pairs": report["pairs_by_population"],
                "archive_bytes": archive["bytes"],
                "costs": report["current_costs"],
            }
        )
    )


if __name__ == "__main__":
    main()
