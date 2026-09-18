"""Combine run assessments and the confirmation into one scoped decision."""

from __future__ import annotations

import hashlib
import importlib.metadata
import time
from datetime import UTC, datetime
from pathlib import Path

from . import codes
from .bundle import Bundle, load_bundle
from .case import Case, parse_case
from .checks import MEASUREMENT_CODES, Finding, RunAssessment, TraceStore, assess_run
from .confirmation import ConfirmationAssessment, assess_confirmation
from .schema import Malformed, canonical_json, digest_of, load_json, parse_quantity, sha256_bytes

DECISION_SCHEMA = "nisayon.decision.v1"
PROTOCOL_ID = "first-case-obligation-v0.1"


def _version() -> str:
    try:
        return importlib.metadata.version("nisayon-workspace")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def evaluator_sources_sha256() -> str | None:
    """One digest over the evaluator's own source files, so a decision names the exact
    evaluator that made it independently of a package version or a Git checkout."""
    folder = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    try:
        for path in sorted(folder.glob("*.py")):
            digest.update(path.name.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    except OSError:
        return None
    return digest.hexdigest()


def aggregate_costs(
    assessments: dict[str, RunAssessment], case: Case | None, unparsed: int
) -> dict:
    # A run whose cost_parent_run_id names another run in the bundle (an executed prefix
    # inside its main run's measured wall) is listed under that parent, not added again.
    nested = {
        a.run_id: a.cost_parent
        for a in assessments.values()
        if a.cost_parent and a.cost_parent in assessments and a.cost_parent != a.run_id
    }
    parent_missing = {
        a.run_id: a.cost_parent
        for a in assessments.values()
        if a.cost_parent and a.cost_parent not in assessments
    }
    items: dict[str, dict] = {}
    for a in assessments.values():
        for name, quantity in a.costs.items():
            item = items.setdefault(
                name,
                {
                    "unit": quantity.unit,
                    "known_total": 0.0,
                    "known_runs": 0,
                    "missing_runs": 0,
                    "missing_reasons": [],
                    "nested_known_total": 0.0,
                    "nested_runs": 0,
                },
            )
            if item["unit"] != quantity.unit:
                item["unit_conflict"] = True
            if a.run_id in nested:
                item["nested_runs"] += 1
                if quantity.value is not None:
                    item["nested_known_total"] = round(
                        item["nested_known_total"] + quantity.value, 9
                    )
            elif quantity.value is None:
                item["missing_runs"] += 1
                if quantity.missing not in item["missing_reasons"]:
                    item["missing_reasons"].append(quantity.missing)
            else:
                item["known_total"] = round(item["known_total"] + quantity.value, 9)
                item["known_runs"] += 1
    preparation: dict = {}
    if case is not None:
        for name, raw in case.preparation_costs.items():
            try:
                preparation[name] = parse_quantity(raw, f"case.preparation_costs.{name}").to_dict()
            except Malformed as error:
                preparation[name] = {"error": str(error)}
    runs_without_costs = [a.run_id for a in assessments.values() if not a.costs]
    return {
        "per_item": items,
        "preparation": preparation,
        "runs_counted": len(assessments),
        "runs_nested_in_parent": nested,
        "cost_parent_missing": parent_missing,
        "runs_without_cost_records": runs_without_costs,
        "records_unparsed": unparsed,
        "note": "Unknown costs are not zero. Totals cover recorded items over every run in the bundle, "
        "including invalid and failed attempts. A run nested in a counted parent's wall is "
        "listed under nested_known_total and not added to known_total; a run whose declared "
        "parent is absent is counted on its own.",
    }


def _limits(case: Case | None, origin: str, assessments: dict[str, RunAssessment]) -> list[str]:
    limits = [
        "The decision covers the finite declared conditions; it is not a stochastic reliability estimate.",
        "Digest matches bind bytes, not physical truth.",
        "Measurements come from the producer's adapter. This evaluator checks their internal consistency "
        "and the declared predicates; it does not verify the adapter or the simulator.",
        "Freshness is checked against the declared exploration set, runs in this bundle and prior "
        "confirmations in this bundle. Custody outside the bundle is not verified.",
    ]
    if origin == "synthetic_development":
        limits.insert(
            0, "Evidence origin synthetic_development: this exercises evaluator behaviour only."
        )
    if case is not None and case.omitted_state:
        limits.append("State declared as not captured: " + "; ".join(case.omitted_state) + ".")
    partial = sorted(
        a.run_id
        for a in assessments.values()
        if a.activation_step is not None and a.measurement == "valid"
    )
    if partial:
        limits.append(
            "Intervention runs are valid under the recorded reset and provenance premises only."
        )
    return limits


def violates(a: RunAssessment, case: Case) -> bool | None:
    """Whether a run violates the case's declared failure obligation; None when unmeasured."""
    match case.failure_obligation:
        case "timing":
            status = a.timing
            return None if status in ("unknown", "unmeasured") else status == "violated"
        case "progress":
            return None if a.progress == "unknown" else a.progress == "lost"
        case "constraints":
            return None if a.constraints == "unknown" else a.constraints == "violated"
        case "reset":
            return a.reset_evidence.get("policy_state") == "carried"
        case _:
            return None if a.outcome == "unknown" else a.outcome == "failed"


def candidate_verdicts(
    assessments: dict[str, RunAssessment],
    confirmation: ConfirmationAssessment | None,
    decision: str,
) -> dict[str, dict]:
    """One line per candidate: rejected on any valid failing obligation, else its confirmation status."""
    reference_completed = {
        a.condition_id
        for a in assessments.values()
        if a.role == "reference" and a.measurement == "valid" and a.outcome == "completed"
    }
    verdicts: dict[str, dict] = {}
    for a in sorted(assessments.values(), key=lambda item: item.run_id):
        if not a.candidate or a.role == "probe":
            continue
        entry = verdicts.setdefault(
            a.candidate["digest"],
            {
                "id": a.candidate["id"],
                "digest": a.candidate["digest"],
                "runs": [],
                "valid_runs": 0,
                "invalid_or_unresolved_runs": [],
                "obligation_failures": [],
                "status": "unconfirmed",
            },
        )
        entry["runs"].append(a.run_id)
        if a.measurement != "valid":
            entry["invalid_or_unresolved_runs"].append(a.run_id)
            continue
        entry["valid_runs"] += 1
        for finding in a.obligation_failures():
            # A failed outcome counts only where the working reference completes the condition.
            if finding.code == codes.OUTCOME_FAILED and a.condition_id not in reference_completed:
                continue
            entry["obligation_failures"].append(finding.to_dict())
    for entry in verdicts.values():
        if entry["obligation_failures"]:
            entry["status"] = "rejected"
        elif confirmation is not None and confirmation.candidate_digest == entry["digest"]:
            entry["status"] = decision
    return verdicts


HISTORY_PATTERNS = ("*.decision.json", "*bundle.json.gz", "*bundle.json")


def expand_history(paths: list[Path] | tuple[Path, ...]) -> list[Path]:
    """A directory of retained records stands for every decision and bundle inside it.

    The execution lane binds its history as a directory of copied decisions and
    compressed bundles; reading only the decisions would silently drop the bundles'
    consumed conditions.
    """
    expanded: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir() and not (path / "case.json").is_file():
            found: set[Path] = set()
            for pattern in HISTORY_PATTERNS:
                found.update(path.rglob(pattern))
            expanded.extend(sorted(found))
        else:
            expanded.append(path)
    return expanded


def _same_file(a: object, b: Path | None) -> bool:
    if not isinstance(a, str) or b is None:
        return False
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def _traces_agree(data: dict, own_traces: dict[str, str] | None) -> bool:
    """A retained decision's run trace digests against this record's; the same execution
    has the same traces, another execution under the same freeze does not."""
    if own_traces is None:
        return True
    runs = data.get("runs") if isinstance(data.get("runs"), dict) else {}
    compared = 0
    for run_id, run in runs.items():
        retained = run.get("trace_digest") if isinstance(run, dict) else None
        current = own_traces.get(str(run_id))
        if retained is None or current is None:
            continue
        compared += 1
        if retained != current:
            return False
    return compared > 0


def _is_own_record(
    data: dict,
    own_digest: str | None,
    own_path: Path | None,
    own_protocol: str | None,
    own_traces: dict[str, str] | None = None,
) -> bool:
    """Whether a history entry is this record's own retained decision or the record itself.

    A decision matches by ``bundle_sha256``. A decision retained before bundle digests
    existed matches by file or by producer protocol digest, and only when its run trace
    digests equal this record's: another execution under the same freeze has other traces
    and is not this record.
    """
    if data.get("schema") == DECISION_SCHEMA:
        retained = data.get("bundle_sha256")
        if isinstance(retained, str):
            return bool(own_digest) and retained == own_digest
        protocol = ((data.get("confirmation") or {}).get("protocol") or {}).get(
            "producer_protocol_sha256"
        )
        named = _same_file(data.get("bundle"), own_path) or (
            bool(own_protocol) and protocol == own_protocol
        )
        return named and _traces_agree(data, own_traces)
    if data.get("schema") == "nisayon.first_case.v1":
        return bool(own_digest) and digest_of(data) == own_digest
    return False


def _parse_stamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def _frozen_after(entry_frozen_at: object, own_frozen_at: object) -> bool:
    """True only when both freeze times parse and the entry was frozen strictly later.

    Conditions a later confirmation spent were free when this record froze; that later
    record is the reuse, not this one. An unknown time counts as earlier, which is the
    conservative direction.
    """
    entry, own = _parse_stamp(entry_frozen_at), _parse_stamp(own_frozen_at)
    return entry is not None and own is not None and entry > own


def _entry_frozen_at(data: dict) -> object:
    confirmation = data.get("confirmation") if isinstance(data.get("confirmation"), dict) else {}
    if data.get("schema") == DECISION_SCHEMA:
        return confirmation.get("frozen_at")
    if data.get("schema") == "nisayon.first_case.v1":
        return confirmation.get("frozen_at")
    candidate = (
        confirmation.get("candidate") if isinstance(confirmation.get("candidate"), dict) else {}
    )
    return candidate.get("frozen_at")


def _bare(digest: object) -> str | None:
    """A digest without its ``sha256:`` prefix; the producer and the evaluator differ."""
    return digest.removeprefix("sha256:").lower() if isinstance(digest, str) else None


def _classify_history(
    paths: list[Path] | tuple[Path, ...],
    case_id: str,
    own_digest: str | None = None,
    own_path: Path | None = None,
    own_protocol: str | None = None,
    own_frozen_at: object = None,
    policy_sha256: str | None = None,
    own_traces: dict[str, str] | None = None,
) -> tuple[list[tuple[Path, dict, str]], list[str], list[str]]:
    """Split the history into entries that count, this record's own entries, and later ones.

    Order comes from the evaluator's own ``decided_at`` stamps, which a producer does not
    write: an entry decided after this record's first retained decision consumed nothing
    before it. Only when both this record's decision and the entry predate those stamps
    do the declared freeze times order them. A record with no retained decision of its
    own counts every entry, so a backdated re-execution cannot make an earlier
    confirmation look later than itself.
    """

    # An entry belongs to this history when it names the same case or the same task
    # policy: conditions are spent per policy, and renaming a case frees nothing.
    def same_task(entry_case_id: object, entry_policy: object) -> bool:
        if entry_case_id == case_id:
            return True
        return bool(policy_sha256) and _bare(entry_policy) == _bare(policy_sha256)

    loaded: list[tuple[Path, dict, str]] = []
    for raw in expand_history(paths):
        path = Path(raw)
        try:
            if path.is_dir():
                conf = (
                    load_json(path / "confirmation.json")
                    if (path / "confirmation.json").is_file()
                    else {}
                )
                case_data = load_json(path / "case.json") if (path / "case.json").is_file() else {}
                if isinstance(case_data, dict) and isinstance(conf, dict):
                    task = case_data.get("task") if isinstance(case_data.get("task"), dict) else {}
                    policy = task.get("policy") if isinstance(task.get("policy"), dict) else {}
                    if same_task(case_data.get("id"), policy.get("sha256")):
                        runs: list[dict] = []
                        runs_dir = path / "runs"
                        if runs_dir.is_dir():
                            for run_path in sorted(runs_dir.glob("*.json")):
                                try:
                                    run = load_json(run_path)
                                except (Malformed, OSError):
                                    continue
                                if isinstance(run, dict):
                                    runs.append(run)
                        loaded.append(
                            (path, {"schema": "dir", "confirmation": conf, "runs": runs}, "dir")
                        )
                continue
            if path.suffix == ".gz":
                from .first_case import read_document

                data = read_document(path)
            else:
                data = load_json(path)
        except (Malformed, OSError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("schema") == DECISION_SCHEMA:
            task = data.get("task") if isinstance(data.get("task"), dict) else {}
            if same_task(data.get("case_id"), task.get("policy_sha256")):
                loaded.append((path, data, "decision"))
        elif data.get("schema") == "nisayon.first_case.v1":
            case_data = data.get("case") if isinstance(data.get("case"), dict) else {}
            policy = case_data.get("policy") if isinstance(case_data.get("policy"), dict) else {}
            if same_task(case_data.get("id"), policy.get("sha256")):
                loaded.append((path, data, "bundle"))
    own: list[str] = []
    own_decided: list[datetime] = []
    own_legacy = False
    rest: list[tuple[Path, dict, str]] = []
    for path, data, kind in loaded:
        if kind == "dir":
            is_own = own_path is not None and _same_file(str(path), own_path)
        else:
            is_own = _is_own_record(data, own_digest, own_path, own_protocol, own_traces)
        if not is_own:
            rest.append((path, data, kind))
            continue
        own.append(str(path))
        if kind == "decision":
            stamp = _parse_stamp(data.get("decided_at"))
            if stamp is None:
                own_legacy = True
            else:
                own_decided.append(stamp)
    # A record whose earliest retained decision predates the stamps is ordered as legacy
    # even when a later re-evaluation of it carries a stamp: every stamped entry was
    # decided after it, and legacy entries are ordered by declared freeze times.
    first_decided = None if own_legacy else (min(own_decided) if own_decided else None)
    counted: list[tuple[Path, dict, str]] = []
    later: list[str] = []
    for path, data, kind in rest:
        decided = _parse_stamp(data.get("decided_at")) if kind == "decision" else None
        if not own:
            is_later = False
        elif own_legacy:
            is_later = decided is not None or (
                kind == "decision" and _frozen_after(_entry_frozen_at(data), own_frozen_at)
            )
        elif first_decided is not None and decided is not None:
            is_later = decided > first_decided
        else:
            is_later = False
        if is_later:
            later.append(str(path))
        else:
            counted.append((path, data, kind))
    return counted, own, later


def retained_protocols(
    paths: list[Path] | tuple[Path, ...],
    case_id: str,
    own_digest: str | None = None,
    own_path: Path | None = None,
    own_protocol: str | None = None,
    own_frozen_at: object = None,
    policy_sha256: str | None = None,
    own_traces: dict[str, str] | None = None,
) -> dict:
    """Producer protocol digests retained for (candidate, condition set) pairs of this case.

    A confirmation whose conditions and candidate match a retained decision but whose
    protocol digest differs has been rewritten after the fact. This record's own retained
    decision and decisions made after it are not earlier protocols.
    """
    counted, _own, _later = _classify_history(
        paths, case_id, own_digest, own_path, own_protocol, own_frozen_at, policy_sha256, own_traces
    )
    retained: dict[tuple[str, frozenset[str]], set[str]] = {}
    for _path, data, kind in counted:
        if kind != "decision":
            continue
        confirmation = data.get("confirmation") or {}
        digest = (confirmation.get("protocol") or {}).get("producer_protocol_sha256")
        candidate = (confirmation.get("candidate") or {}).get("digest")
        conditions = frozenset(str(c) for c in confirmation.get("fresh_condition_ids", []))
        if digest and candidate and conditions:
            retained.setdefault((candidate, conditions), set()).add(str(digest))
    return retained


def unreadable_history(paths: list[Path] | tuple[Path, ...]) -> list[str]:
    """History paths that cannot be read; a mistyped required history must not shrink silently."""
    problems = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            if not (path / "case.json").is_file() and not any(
                any(path.rglob(pattern)) for pattern in HISTORY_PATTERNS
            ):
                problems.append(f"{path}: no case.json and no retained decisions or bundles")
            continue
        if not path.is_file():
            problems.append(f"{path}: missing")
            continue
        try:
            if path.suffix == ".gz":
                from .first_case import read_document

                read_document(path)
            else:
                data = load_json(path)
                if not isinstance(data, dict) or not data.get("schema"):
                    problems.append(f"{path}: no schema")
        except (Malformed, OSError) as error:
            problems.append(f"{path}: {error}")
    return problems


def consumed_from_history(paths: list[Path] | tuple[Path, ...], case_id: str) -> set[str]:
    """Condition IDs already used for this case in retained decisions, bundles or documents."""
    return history_consumption(paths, case_id)[0]


def history_consumption(
    paths: list[Path] | tuple[Path, ...],
    case_id: str,
    own_digest: str | None = None,
    own_path: Path | None = None,
    own_protocol: str | None = None,
    own_frozen_at: object = None,
    policy_sha256: str | None = None,
    own_traces: dict[str, str] | None = None,
) -> tuple[set[str], list[str], list[str]]:
    """Consumed condition IDs for this case, the entries that are this record, and the
    entries decided after it.

    The execution lane passes every retained decision as history. The decision of the
    record under evaluation, or the record's own bundle file, names conditions this
    confirmation consumes, not conditions consumed before it. A confirmation decided
    after this record's first decision spent conditions that were free at the time; it
    is the reuse, not this record. Both kinds are listed and contribute nothing.
    """
    counted, own, later = _classify_history(
        paths, case_id, own_digest, own_path, own_protocol, own_frozen_at, policy_sha256, own_traces
    )
    consumed: set[str] = set()
    for _path, data, kind in counted:
        confirmation = data.get("confirmation") or {}
        if kind == "dir":
            consumed.update(
                str(item.get("id"))
                for item in confirmation.get("conditions", [])
                if isinstance(item, dict) and item.get("id")
            )
        elif kind == "decision":
            consumed.update(str(c) for c in confirmation.get("fresh_condition_ids", []))
            consumed.update(str(c) for c in confirmation.get("reproduction_condition_ids", []))
        else:
            consumed.update(str(c) for c in confirmation.get("condition_ids", []))
        # Every executed run spent its condition, whatever the declared list says.
        runs = data.get("runs")
        run_items = (
            runs.values() if isinstance(runs, dict) else runs if isinstance(runs, list) else []
        )
        for run in run_items:
            if isinstance(run, dict) and run.get("condition_id"):
                consumed.add(str(run["condition_id"]))
    return consumed, own, later


def inline_trace_digests(runs: dict[str, dict]) -> dict[str, str]:
    """The trace digests the run checks will compute for inline traces, before assessment."""
    digests: dict[str, str] = {}
    for run_id, run in runs.items():
        trace = run.get("trace") if isinstance(run, dict) else None
        if isinstance(trace, dict):
            try:
                digests[str(run_id)] = sha256_bytes((canonical_json(trace) + "\n").encode())
            except (TypeError, ValueError):
                continue
    return digests


def native_bundle_digest(bundle: Bundle) -> str | None:
    """A content digest of a loaded bundle directory, so a retained decision can name it."""
    try:
        return digest_of(
            {"case": bundle.case, "confirmation": bundle.confirmation, "runs": bundle.runs}
        )
    except (TypeError, ValueError):
        return None


def _evidence_summary(result: dict, assessments: dict[str, RunAssessment], case: Case) -> dict:
    """What the decision rests on: measured, inherited, verified or missing."""
    codes_seen = {f["code"] for f in result["reasons"]} | {n["code"] for n in result["notes"]}
    confirmation = result.get("confirmation") or {}
    codes_seen |= {f["code"] for f in confirmation.get("findings", [])}
    assigned = {
        pair[key]
        for pair in confirmation.get("pairs", [])
        for key in ("reference_run_id", "candidate_run_id")
    }
    timing = {assessments[r].timing for r in assigned if r in assessments} or {
        a.timing for a in assessments.values()
    }
    if timing and timing <= {"satisfied", "violated"}:
        timing_status = "measured_from_acquisition_stamps"
    elif "unmeasured" in timing:
        timing_status = "unmeasured" if timing <= {"unmeasured", "unknown"} else "partly_unmeasured"
    else:
        timing_status = "unknown"
    if codes.IDENTITY_MISMATCH in codes_seen:
        identity = "mismatch"
    elif codes.IDENTITY_UNBOUND in codes_seen:
        identity = "unbound"
    elif codes.IDENTITY_VERIFIED in codes_seen:
        identity = "verified_per_run"
    elif codes.IDENTITY_INHERITED in codes_seen:
        identity = "inherited_from_bundle"
    else:
        identity = "not_applicable"
    run_codes = {f["code"] for run in result["runs"].values() for f in run["findings"]}
    if codes.ARTIFACT_DIGEST_MISMATCH in run_codes | codes_seen:
        artifacts = "digest_mismatch"
    elif codes.ARTIFACT_MANIFEST_VERIFIED in codes_seen:
        artifacts = "manifest_verified"
    elif (
        codes.RAW_ARTIFACT_UNVERIFIED in run_codes or codes.ARTIFACT_STORE_UNVERIFIED in codes_seen
    ):
        artifacts = "raw_store_unverified"
    elif codes.RAW_ARTIFACT_VERIFIED in run_codes:
        artifacts = "raw_files_verified_under_local_root"
    else:
        artifacts = "trace_artifacts_verified_by_digest"
    if (
        codes.REPRODUCTION_NOT_POST_FREEZE in codes_seen
        or codes.REPRODUCTION_EVIDENCE_PRECEDES_FREEZE in codes_seen
    ):
        reproduction = "pre_freeze_evidence"
    elif any(pair.get("role") == "reproduction" for pair in confirmation.get("pairs", [])):
        reproduction = "post_freeze_rerun"
    else:
        reproduction = "missing"
    if codes.CANDIDATE_DEPLOYABILITY_UNDECLARED in run_codes:
        deployability = "undeclared"
    elif codes.CANDIDATE_DEPLOYABILITY_ASSUMED in run_codes:
        deployability = "assumed"
    else:
        deployability = "declared"
    return {
        "obligation": case.obligation,
        "timing": timing_status,
        "identity": identity,
        "artifacts": artifacts,
        "reproduction": reproduction,
        "deployability": deployability,
        "progress_predicate": "evaluator_added_not_preregistered"
        if case.evaluator_added_predicates
        else "producer_frozen",
        "custody": "producer-declared contamination status; no independent custody was verified",
    }


def evaluate_loaded(
    bundle: Bundle,
    known_synthetic_digests: frozenset[str] = frozenset(),
    extra_findings: list[Finding] | tuple[Finding, ...] = (),
    producer: dict | None = None,
    history_consumed: set[str] | frozenset[str] = frozenset(),
    history_protocols: dict | None = None,
    history_problems: list[str] | tuple[str, ...] = (),
    history_self: list[str] | tuple[str, ...] = (),
    history_later: list[str] | tuple[str, ...] = (),
    history_paths: list[str] | tuple[str, ...] = (),
) -> dict:
    started = time.perf_counter()
    result = _evaluate_loaded(
        bundle,
        known_synthetic_digests,
        extra_findings,
        producer,
        history_consumed,
        history_protocols,
        history_problems,
        history_self,
        history_later,
        history_paths,
    )
    result["evaluation_wall_s"] = round(time.perf_counter() - started, 6)
    return result


def _evaluate_loaded(
    bundle: Bundle,
    known_synthetic_digests: frozenset[str],
    extra_findings: list[Finding] | tuple[Finding, ...],
    producer: dict | None,
    history_consumed: set[str] | frozenset[str],
    history_protocols: dict | None,
    history_problems: list[str] | tuple[str, ...],
    history_self: list[str] | tuple[str, ...] = (),
    history_later: list[str] | tuple[str, ...] = (),
    history_paths: list[str] | tuple[str, ...] = (),
) -> dict:
    result: dict = {
        "schema": DECISION_SCHEMA,
        "evaluator": {
            "name": "nisayon.evaluation",
            "version": _version(),
            "sources_sha256": evaluator_sources_sha256(),
            "protocol": PROTOCOL_ID,
        },
        "bundle": str(bundle.root),
        "bundle_sha256": (producer or {}).get("bundle_sha256") or native_bundle_digest(bundle),
        "decided_at": datetime.now(UTC).isoformat(),
        # The history this decision was made under, so a reader can tell a decision made
        # with every retained record from one made with none.
        "history": {
            "paths": [str(path) for path in history_paths],
            "consumed_condition_count": len(history_consumed),
            "own_entries": [str(item) for item in history_self],
            "later_entries": [str(item) for item in history_later],
            "unreadable": [str(item) for item in history_problems],
        },
        "artifact_root": str(bundle.artifact_root),
        "case_id": None,
        "evidence_origin": None,
        "decision": "invalid",
        "scope": "",
        "reasons": [],
        "premises": {"reference_established": None, "regression_reproduced": None},
        "runs": {},
        "unparsed_records": bundle.unparsed,
        "confirmation": None,
        "candidates": {},
        "costs": {},
        "limits": [],
        "notes": [f.to_dict() for f in extra_findings if f.severity == codes.INFO],
        "producer": producer,
    }
    case: Case | None = None
    blocking: list[Finding] = [f for f in extra_findings if f.severity != codes.INFO]
    for problem in history_problems:
        blocking.append(
            Finding(
                codes.HISTORY_UNREADABLE,
                f"a supplied history path could not be read, so the consumed-condition set may be "
                f"incomplete: {problem}",
            )
        )
    if bundle.case_error is not None:
        blocking.append(
            Finding(codes.MALFORMED_RECORD, bundle.case_error.detail, path=bundle.case_error.path)
        )
    else:
        try:
            case = parse_case(bundle.case)
        except Malformed as error:
            blocking.append(Finding(codes.MALFORMED_RECORD, error.detail, path=error.path))
    if case is None:
        result["reasons"] = [f.to_dict() for f in blocking]
        result["scope"] = "no decision: the case record is malformed"
        result["costs"] = aggregate_costs({}, None, len(bundle.unparsed))
        result["limits"] = _limits(None, "unknown", {})
        return result
    result["case_id"] = case.id
    result["task"] = {"policy_sha256": _bare((case.policy or {}).get("digest"))}
    result["evaluator"]["protocol"] = case.obligation
    if case.evaluator_added_predicates:
        detail = (
            f"predicates {list(case.evaluator_added_predicates)} were declared by the evaluation "
            "lane, not frozen by the producer; they are checked retrospectively and cannot count "
            "as preregistered"
        )
        if case.strict:
            blocking.append(Finding(codes.PREREGISTRATION_MISSING, detail))
        else:
            result["notes"].append(Finding(codes.PREDICATE_NOT_PREREGISTERED, detail).to_dict())
    store = TraceStore(bundle.artifact_root, bundle.runs, case.timing.clock)
    assessments: dict[str, RunAssessment] = {}
    # Reference and regression runs first so intervention runs can compare against their sources.
    ordered = sorted(bundle.runs.values(), key=lambda run: run.get("candidate") is not None)
    for run in ordered:
        a = assess_run(run, case, store, assessments, known_synthetic_digests)
        assessments[a.run_id] = a
    result["runs"] = {rid: a.to_dict() for rid, a in assessments.items()}
    origins = {case.evidence_origin} | {
        a.evidence_origin for a in assessments.values() if a.evidence_origin
    }
    if "synthetic_development" in origins:
        origin = "synthetic_development"
    elif origins <= {"simulator", "invalid_replay_control"}:
        origin = "simulator"
    else:
        origin = "/".join(sorted(origins))
    result["evidence_origin"] = origin
    result["evidence_origins"] = sorted(origins)

    references = [
        a
        for a in assessments.values()
        if a.role == "reference"
        and a.condition_id == case.reproduction_condition_id
        and a.measurement == "valid"
    ]
    regressions = [
        a
        for a in assessments.values()
        if a.role == "regression"
        and a.condition_id == case.reproduction_condition_id
        and a.measurement == "valid"
    ]
    reference_ok = any(a.outcome == "completed" and violates(a, case) is False for a in references)
    regression_ok = any(violates(a, case) for a in regressions)
    if case.calibration:
        result["premises"] = {"reference_established": None, "regression_reproduced": None}
        reference_ok = regression_ok = True  # premises do not apply to calibration probes
    else:
        result["premises"] = {
            "reference_established": reference_ok,
            "regression_reproduced": regression_ok,
        }
    if not reference_ok:
        blocking.append(
            Finding(
                codes.REFERENCE_NOT_ESTABLISHED,
                f"no valid working-revision run completes the failing condition {case.reproduction_condition_id!r}",
            )
        )
    if not regression_ok:
        blocking.append(
            Finding(
                codes.REGRESSION_NOT_REPRODUCED,
                f"no valid changed-revision run fails the failing condition {case.reproduction_condition_id!r}",
            )
        )
    for a in assessments.values():
        if a.evidence_origin in {"simulator", "hardware"}:
            blocking.extend(
                f for f in a.findings if f.code == codes.SYNTHETIC_PRESENTED_AS_MEASUREMENT
            )

    confirmation: ConfirmationAssessment | None = None
    if bundle.confirmation_error is not None:
        blocking.append(
            Finding(
                codes.MALFORMED_RECORD,
                bundle.confirmation_error.detail,
                path=bundle.confirmation_error.path,
            )
        )
    elif bundle.confirmation is None and case.calibration:
        blocking.append(
            Finding(
                codes.CALIBRATION_ONLY,
                "calibration probes only: no working or changed revision, no frozen candidate "
                "and no confirmation; per-run assessments are retained, nothing is scored",
            )
        )
    elif bundle.confirmation is None:
        blocking.append(
            Finding(
                codes.CONFIRMATION_MISSING,
                "no confirmation record: the candidate has not been frozen and confirmed on "
                "fresh conditions",
            )
        )
    else:
        confirmation = assess_confirmation(
            bundle.confirmation, case, assessments, bundle.prior, history_consumed
        )
        result["confirmation"] = confirmation.to_dict()
        if history_self:
            result["notes"].append(
                Finding(
                    codes.HISTORY_CONTAINS_THIS_RECORD,
                    f"the supplied history includes this record itself ({len(history_self)} "
                    f"entries, for example {history_self[0]}); its conditions are consumed by "
                    "this confirmation, not before it",
                ).to_dict()
            )
        if history_later:
            result["notes"].append(
                Finding(
                    codes.HISTORY_LATER_RECORDS,
                    f"{len(history_later)} history entries were decided after this record's "
                    f"first retained decision (for example {history_later[0]}); conditions they "
                    "spent were free when this record was confirmed, so they are not prior "
                    "consumption here",
                ).to_dict()
            )
        if (
            not history_consumed
            and not history_problems
            and not bundle.prior
            and not history_self
            and not history_later
        ):
            result["notes"].append(
                Finding(
                    codes.HISTORY_ABSENT,
                    "no retained history was supplied; consumed conditions and rewritten protocols "
                    "could only be checked against this bundle's own records",
                ).to_dict()
            )
        if history_protocols and confirmation.producer_protocol_digest:
            key = (confirmation.candidate_digest, frozenset(confirmation.fresh_condition_ids))
            retained = history_protocols.get(key, set())
            if retained and confirmation.producer_protocol_digest not in retained:
                blocking.append(
                    Finding(
                        codes.PROTOCOL_MISMATCH,
                        "the frozen protocol digest differs from the digest retained for the same "
                        "candidate and condition set in an earlier decision; the protocol was "
                        "rewritten after the fact",
                    )
                )
        blocking.extend(f for f in confirmation.findings if f.severity != codes.INFO)
        # Name the underlying cause when an assigned run is invalid or cannot be assessed.
        assigned = set(confirmation.assigned_candidate_run_ids) | {
            pair.reference_run_id for pair in confirmation.pairs
        }
        for run_id in sorted(assigned):
            a = assessments.get(run_id)
            if a is not None and a.measurement != "valid":
                blocking.extend(
                    f
                    for f in a.findings
                    if f.code in MEASUREMENT_CODES and f.severity != codes.INFO
                )
        # Outcome is judged through the paired rule above; progress, constraints, timing and
        # repair scope are absolute obligations on every assigned candidate run.
        gaps: dict[str, list[Finding]] = {}
        for run_id in confirmation.assigned_candidate_run_ids:
            a = assessments.get(run_id)
            if a is not None and a.measurement == "valid":
                blocking.extend(
                    f for f in a.obligation_failures() if f.code != codes.OUTCOME_FAILED
                )
                for finding in a.unmeasured_obligations():
                    gaps.setdefault(finding.code, []).append(finding)
        # One reason per gap code: the same missing declaration repeats on every assigned run.
        for code, findings in gaps.items():
            runs = [f.run_id for f in findings]
            blocking.append(
                Finding(
                    code,
                    f"{findings[0].detail} ({len(findings)} assigned candidate runs: "
                    f"{runs[:3]}{'...' if len(runs) > 3 else ''})",
                    run_id=runs[0],
                )
            )
    severity = codes.strongest([f.severity for f in blocking])
    decision = {
        codes.INVALID: "invalid",
        codes.REJECTED: "rejected",
        codes.UNRESOLVED: "unresolved",
    }.get(severity, "accepted")
    result["decision"] = decision
    order = {codes.INVALID: 0, codes.REJECTED: 1, codes.UNRESOLVED: 2, codes.INFO: 3}
    result["reasons"] = [f.to_dict() for f in sorted(blocking, key=lambda f: order[f.severity])]
    if confirmation:
        pairs = confirmation.pairs
        fresh = [p for p in pairs if p.role == "fresh"]
        reproduction = [p for p in pairs if p.role == "reproduction"]
        summary = {
            "reproduction": reproduction[0].verdict if reproduction else "missing",
            "fresh_declared": len(confirmation.fresh_condition_ids),
            "fresh_assigned": len(fresh),
            "fresh_pass": sum(p.verdict == "pass" for p in fresh),
            "fresh_regression": sum(p.verdict == "regression" for p in fresh),
            "fresh_both_failed": sum(p.verdict == "both_failed" for p in fresh),
            "fresh_improved": sum(p.verdict == "improved" for p in fresh),
            "fresh_gap_or_invalid": sum(p.verdict in {"gap", "invalid"} for p in fresh),
        }
        result["confirmation"]["summary"] = summary
        scope = (
            f"{decision}: candidate {confirmation.candidate_id!r} as a deployable repair of case "
            f"{case.id!r} under {case.obligation}; reproduction condition "
            f"{confirmation.reproduction_condition_ids or 'unassigned'} plus "
            f"{summary['fresh_assigned']} of {summary['fresh_declared']} declared fresh conditions"
        )
    elif case.calibration:
        scope = (
            f"calibration probes for case {case.id!r} under {case.obligation}; no scored incident"
        )
    else:
        scope = f"case {case.id!r} under {case.obligation}; no frozen candidate confirmed"
    if origin == "synthetic_development":
        scope += "; synthetic development fixture, not an experiment result"
    result["scope"] = scope
    result["candidates"] = candidate_verdicts(assessments, confirmation, decision)
    result["evidence"] = _evidence_summary(result, assessments, case)
    result["obligation"] = {
        "version": case.obligation,
        "strict": case.strict,
        "predicates_digest": case.predicates_digest,
        "evaluator_added_predicates": list(case.evaluator_added_predicates),
    }
    result["costs"] = aggregate_costs(assessments, case, len(bundle.unparsed))
    result["limits"] = _limits(case, origin, assessments)
    return result


def _evaluate_bundle(
    bundle: Path,
    artifact_root: Path | None = None,
    known_synthetic_digests: frozenset[str] = frozenset(),
    history: list[Path] | tuple[Path, ...] = (),
) -> dict:
    """Decide a bundle directory (``nisayon.case.v1`` layout) or an execution-lane bundle file.

    ``history`` names retained decisions, bundles or documents whose confirmation conditions
    are already consumed for the case.
    """
    path = Path(bundle)
    if path.is_file():
        from .first_case import evaluate_first_case

        return evaluate_first_case(path, artifact_root, known_synthetic_digests, history)
    loaded = load_bundle(path, artifact_root)
    consumed: set[str] = set()
    protocols: dict = {}
    problems: list[str] = []
    own: list[str] = []
    later: list[str] = []
    if history and isinstance(loaded.case, dict) and isinstance(loaded.case.get("id"), str):
        confirmation = loaded.confirmation if isinstance(loaded.confirmation, dict) else {}
        candidate = confirmation.get("candidate") if isinstance(confirmation, dict) else None
        task = loaded.case.get("task") if isinstance(loaded.case.get("task"), dict) else {}
        policy = task.get("policy") if isinstance(task.get("policy"), dict) else {}
        identity = {
            "own_digest": native_bundle_digest(loaded),
            "own_path": path,
            "own_frozen_at": candidate.get("frozen_at") if isinstance(candidate, dict) else None,
            "policy_sha256": _bare(policy.get("digest")),
            "own_traces": inline_trace_digests(loaded.runs),
        }
        consumed, own, later = history_consumption(list(history), loaded.case["id"], **identity)
        protocols = retained_protocols(list(history), loaded.case["id"], **identity)
        problems = unreadable_history(list(history))
    return evaluate_loaded(
        loaded,
        known_synthetic_digests,
        history_consumed=consumed,
        history_protocols=protocols,
        history_problems=problems,
        history_self=own,
        history_later=later,
        history_paths=[str(item) for item in history],
    )


def evaluate_bundle(
    bundle: Path,
    artifact_root: Path | None = None,
    known_synthetic_digests: frozenset[str] = frozenset(),
    history: list[Path] | tuple[Path, ...] = (),
) -> dict:
    """Decide a bundle directory or an execution-lane bundle file; wall time covers everything."""
    started = time.perf_counter()
    result = _evaluate_bundle(bundle, artifact_root, known_synthetic_digests, history)
    result["evaluation_wall_s"] = round(time.perf_counter() - started, 6)
    return result
