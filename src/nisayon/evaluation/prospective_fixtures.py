"""Labelled prospective-scoring fixtures: declaration receipts on the v1 scoring fixtures.

``evidence_origin: synthetic_development``. They exercise the prospective scorer's
semantics; no arm has run, no receipt was written by the execution lane's writer. The
receipt shape follows the execution lane's ``nisayon.arm-declaration.v1`` proposal
(``docs/experiments/DECLARATION_INTERFACE.md`` at execution commit ``4cbac86``).
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .prospective import (
    CLAIM,
    DECLARATION_SCHEMA,
    DEMONSTRATION_SCOPE,
    LEDGER_SCHEMA_V2,
    PROSPECTIVE_SCOPE,
    _norm,
    _writer_digest,
)
from .schema import digest_of
from .scoring_fixtures import ORIGIN, fair_ledger, write_ledger

# Candidate configurations the fixtures declare. A receipt must bind a configuration to
# its writer digest, so every fixture candidate is a real object, not a bare digest; the
# v1 fixtures' candidate digests are the digests of these objects.
CONFIGURATIONS: dict[str, dict] = {
    _writer_digest(cfg): cfg
    for cfg in (
        {"repair": "sign"},
        {"repair": "sign+timing"},
        {"repair": "reset"},
        {"repair": "replayed"},
        {"repair": "something else"},
    )
}


def configuration_for(candidate_digest: str | None) -> dict | None:
    """The fixture configuration whose writer digest is ``candidate_digest``."""
    if candidate_digest is None:
        return None
    digest = _norm(candidate_digest)
    if digest not in CONFIGURATIONS:
        raise KeyError(f"no fixture configuration for candidate digest {candidate_digest!r}")
    return CONFIGURATIONS[digest]


SPEC = "_declaration_spec"
REJECTED_PROGRESS = [
    {
        "severity": "rejected",
        "code": "progress_lost",
        "run_id": "confirmation-correction-10423",
        "detail": "lift.cube_raised: gain 0.002936 m is below the minimum 0.01",
    }
]


def _default_spec(trial: dict) -> dict:
    claimed = trial.get("arm_claimed_acceptance") is True
    executed = [p["candidate_digest"] for p in trial["proposals"] if p.get("executed")]
    if claimed:
        disposition = CLAIM
    elif trial["status"] == "unresolved":
        disposition = "unresolved"
    elif trial["proposals"]:
        disposition = "refuse"
    else:
        disposition = "abstain"
    return {
        "disposition": disposition,
        "candidate": configuration_for(executed[-1]) if (claimed and executed) else None,
        "scope": PROSPECTIVE_SCOPE,
        "minute": None,
        "reason": "fixture declaration",
        "terminal": True,
        "additional": [],
    }


def prospective_ledger() -> dict:
    """The fair v1 fixture as a v2 ledger with a truthful receipt on every trial."""
    ledger = fair_ledger()
    ledger["schema"] = LEDGER_SCHEMA_V2
    for trial in ledger["trials"]:
        trial[SPEC] = _default_spec(trial)
    return ledger


def _trial(ledger: dict, arm: str, prefix: str) -> dict:
    return next(t for t in ledger["trials"] if t["arm"] == arm and t["case_id"].startswith(prefix))


def receipt(ledger: dict, trial: dict, spec: dict) -> dict:
    """A declaration in the execution writer's shape (``nisayon.engine.declarations``).

    ``spec["candidate"]`` is the candidate configuration object or None; the receipt
    binds it to its writer digest, carries the eight caller fields, the generated
    ``request_sha256``, ``source_sha256`` and ``settings_sha256``, and an ``observed``
    block at sequence 1. Earlier fixtures claimed the record version with a bare
    candidate digest and a fixture-only request digest; they were repaired to this shape
    on 19 September 2026 (lane record), which is why the omission and binding controls
    reach semantic validation instead of failing on the fixture itself.
    """
    started = trial["timeline"]["started_at"]
    configuration = spec["candidate"]
    payload = {
        "assignment": {
            "suite_id": ledger["suite"]["id"],
            "case_id": trial["case_id"],
            "arm": trial["arm"],
            "frozen_inputs_sha256": _norm(trial["received_frozen_sha256"]),
        },
        "candidate": {
            "configuration": configuration,
            "configuration_sha256": _writer_digest(configuration),
        }
        if configuration is not None
        else None,
        "disposition": spec["disposition"],
        "reason": spec["reason"],
        "evidence": [],
        "source": {"git_head": "fixture"},
        "settings": {"method": "fixture declaration"},
        "evidence_scope": spec["scope"],
    }
    return {
        "schema": DECLARATION_SCHEMA,
        "evidence_origin": ORIGIN,
        **payload,
        "request_sha256": _writer_digest(payload),
        "source_sha256": _writer_digest(payload["source"]),
        "settings_sha256": _writer_digest(payload["settings"]),
        "observed": {
            "event_id": f"{trial['arm']}-{trial['case_id']}-{spec.get('event', 1)}",
            "recorded_at": spec["minute"] if spec["minute"] else _plus(started, 30),
            "sequence": 1,
        },
        "authority": "Study declaration only; product acceptance still requires confirmation",
    }


def terminal_records(
    trial: dict, record: dict, *, evidence: list[dict], ended: str
) -> tuple[dict, dict]:
    """The start and result records the writer would emit for a bound declaration."""
    start = {
        "schema": "nisayon.terminal-start.v1",
        "declaration": dict(trial["declaration"]),
        "assignment": record["assignment"],
        "candidate": record["candidate"],
        "evidence_scope": record["evidence_scope"],
        "observed": {
            "event_id": f"{trial['arm']}-{trial['case_id']}-start",
            "recorded_at": _plus(ended, -60),
            "sequence": 2,
        },
        "order_scope": "fixture writer order; no external custody attestation",
    }
    return start, {
        "schema": "nisayon.terminal-result.v1",
        "declaration": dict(trial["declaration"]),
        "assignment": record["assignment"],
        "terminal_evidence": evidence,
        "observed": {
            "event_id": f"{trial['arm']}-{trial['case_id']}-result",
            "recorded_at": ended,
            "sequence": 3,
        },
    }


def bind_result(result: dict, start_reference: dict) -> dict:
    """Complete a result record with its start reference and the writer's request digest."""
    result = dict(result)
    result["terminal_start"] = dict(start_reference)
    result["request_sha256"] = _writer_digest(
        {
            "terminal_start": result["terminal_start"],
            "terminal_evidence": result["terminal_evidence"],
        }
    )
    return result


def _plus(iso: str, seconds: int) -> str:
    from datetime import datetime, timedelta

    return (datetime.fromisoformat(iso) + timedelta(seconds=seconds)).isoformat()


def _write(folder: Path, relative: str, record: dict) -> dict:
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(record, indent=2) + "\n").encode()
    target.write_bytes(raw)
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def write_prospective_ledger(ledger: dict, folder: Path) -> Path:
    """Write decisions, receipts and terminal bindings; return the ledger path."""
    folder = Path(folder)
    ledger = copy.deepcopy(ledger)
    write_ledger(ledger, folder)  # decisions and their digests
    for trial in ledger["trials"]:
        spec = trial.pop(SPEC, None)
        if spec is None:
            continue
        base = f"declarations/{trial['arm']}-{trial['case_id']}"
        record = receipt(ledger, trial, spec)
        trial["declaration"] = _write(folder, f"{base}/declaration.json", record)
        additional = []
        for index, extra in enumerate(spec.get("additional", []), 1):
            extra_spec = {**spec, **extra, "event": index + 1}
            extra_record = receipt(ledger, trial, extra_spec)
            if extra.get("rejected_change"):
                extra_record["accepted"] = False
            reference = _write(folder, f"{base}/attempt-{index}.json", extra_record)
            if extra.get("rejected_change"):
                reference["status"] = "rejected_change"
            additional.append(reference)
        if additional:
            trial["additional_declarations"] = additional
        if spec.get("terminal") and trial.get("decision"):
            ended = trial["timeline"]["ended_at"]
            evidence = dict(trial["decision"])
            if spec.get("break_terminal_binding"):
                evidence["sha256"] = "0" * 64
            start, result = terminal_records(
                trial,
                record,
                evidence=[{"path": evidence["path"], "sha256": evidence["sha256"]}],
                ended=ended,
            )
            trial["terminal_start"] = _write(folder, f"{base}/terminal-start.json", start)
            result = bind_result(result, trial["terminal_start"])
            trial["terminal_result"] = _write(folder, f"{base}/terminal-result.json", result)
    path = folder / "ledger.json"
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    return path


@dataclass(frozen=True)
class ProspectiveScenario:
    name: str
    description: str
    expected_fair: bool
    expected_codes: tuple[str, ...]
    expected_arms: dict
    build: Callable[[], dict]
    after_write: Callable[[Path], None] | None = None


def _contradicted() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "B", "D07")
    t["decision"].update(decision="rejected", reasons=REJECTED_PROGRESS)
    return ledger


def _unsupported_unresolved() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D10")
    t["arm_claimed_acceptance"] = True
    t[SPEC].update(
        disposition=CLAIM, candidate=configuration_for(t["decision"]["candidate_digest"])
    )
    return ledger


def _unsupported_invalid() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D08")
    candidate = digest_of({"repair": "replayed"})
    t["proposals"] = [
        {
            "candidate_digest": candidate,
            "executed": True,
            "rejected_before_execution": False,
            "reason": "old-future replay presented as a rerun",
        }
    ]
    t["decision"] = {
        "path": "decisions/A-D08-old-future-replay.json",
        "sha256": None,
        "decision": "invalid",
        "candidate_digest": candidate,
        "reasons": [
            {
                "severity": "invalid",
                "code": "affected_future_observation_reused",
                "detail": "399 observations after the intervention reused from regression-0",
            }
        ],
    }
    t["arm_claimed_acceptance"] = True
    t[SPEC].update(disposition=CLAIM, candidate=configuration_for(candidate))
    return ledger


def _reference_missing() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D01")
    t["decision"] = None
    t["status"] = "unresolved"
    t["confirmation_rollouts"] = 12
    t["costs"]["simulator_wall"] = {"value": 21.0, "unit": "s"}
    t[SPEC]["terminal"] = False
    ledger["execution_complete"] = False
    return ledger


def _reference_corrupt() -> dict:
    return prospective_ledger()


def _tamper_a_d01(folder: Path) -> None:
    record = folder / "decisions/A-D01-gripper-sign.json"
    data = json.loads(record.read_text())
    data["decision"] = "rejected"
    record.write_text(json.dumps(data))


def _correct_abstention() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "B", "D07")
    t["status"] = "rejected"
    t["arm_claimed_acceptance"] = False
    t["decision"].update(decision="rejected", reasons=REJECTED_PROGRESS)
    t[SPEC].update(disposition="refuse", candidate=None)
    return ledger


def _missed_own_reference() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D01")
    t["arm_claimed_acceptance"] = False
    t["status"] = "unresolved"
    t[SPEC].update(disposition="abstain", candidate=None)
    return ledger


def _missed_paired_reference() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D01")
    t["arm_claimed_acceptance"] = False
    t["status"] = "unresolved"
    t["decision"] = None
    t["proposals"] = []
    t[SPEC].update(disposition="abstain", candidate=None, terminal=False)
    return ledger


def _all_abstain() -> dict:
    ledger = prospective_ledger()
    for t in ledger["trials"]:
        if t["arm"] == "A":
            t["arm_claimed_acceptance"] = False
            t["status"] = (
                "unresolved" if t["status"] in ("confirmed", "unresolved") else t["status"]
            )
            t["decision"] = None
            t["proposals"] = [p for p in t["proposals"] if p["rejected_before_execution"]]
            t[SPEC].update(disposition="abstain", candidate=None, terminal=False)
    return ledger


def _zero_confirmed_claims() -> dict:
    ledger = prospective_ledger()
    for prefix in ("D01", "D07"):
        t = _trial(ledger, "A", prefix)
        t["decision"].update(decision="rejected", reasons=REJECTED_PROGRESS)
    return ledger


def _missing_assigned_case() -> dict:
    ledger = prospective_ledger()
    ledger["trials"] = [
        t for t in ledger["trials"] if not (t["arm"] == "B" and t["case_id"].startswith("D10"))
    ]
    return ledger


def _candidate_mismatch() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D01")
    t[SPEC]["candidate"] = {"repair": "something else"}
    return ledger


def _declaration_ambiguous() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D01")
    t[SPEC]["additional"] = [{"disposition": "abstain", "candidate": None}]
    return ledger


def _post_outcome_change() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D01")
    t["decision"]["decided_at"] = t["timeline"]["ended_at"]
    t[SPEC]["additional"] = [
        {
            "disposition": "abstain",
            "candidate": None,
            "rejected_change": True,
            "minute": _plus(t["timeline"]["ended_at"], 120),
        }
    ]
    return ledger


def _retry_identical() -> dict:
    ledger = prospective_ledger()
    t = _trial(ledger, "A", "D01")
    t[SPEC]["additional"] = [{"minute": _plus(t["timeline"]["started_at"], 45)}]
    return ledger


def _order_unverified() -> dict:
    ledger = prospective_ledger()
    for t in ledger["trials"]:
        t[SPEC]["terminal"] = False
    return ledger


def _terminal_binding_broken() -> dict:
    ledger = prospective_ledger()
    _trial(ledger, "B", "D01")[SPEC]["break_terminal_binding"] = True
    return ledger


def _demonstration_scope() -> dict:
    ledger = prospective_ledger()
    for t in ledger["trials"]:
        t[SPEC]["scope"] = DEMONSTRATION_SCOPE
    return ledger


def _partial_costs() -> dict:
    ledger = prospective_ledger()
    a1 = _trial(ledger, "A", "D01")
    del a1["costs"]["simulator_wall"]
    a7 = _trial(ledger, "A", "D07")
    a7["costs"]["simulator_wall"] = {"value": None, "unit": "s", "missing": "interrupted timer"}
    return ledger


def _derived_v1() -> dict:
    return fair_ledger()


def _arms(**values: dict) -> dict:
    return values


PROSPECTIVE_SCENARIOS: tuple[ProspectiveScenario, ...] = (
    ProspectiveScenario(
        "prospective_fair",
        "Truthful receipts, every claim supported, refusals adjudicated where a reference exists.",
        True,
        (),
        _arms(
            A={"N": 4, "D": 2, "C": 2, "F": 0, "U": 0, "K": 0, "correct": 1, "unadjudicated": 1},
            B={"N": 4, "D": 2, "C": 2, "F": 0, "U": 0, "K": 0, "correct": 1, "unadjudicated": 1},
        ),
        prospective_ledger,
    ),
    ProspectiveScenario(
        "contradicted_acceptance",
        "B claims D07; the terminal decision rejects the candidate on progress_lost.",
        True,
        ("claim_contradicted",),
        _arms(B={"D": 2, "C": 1, "F": 1, "U": 0, "K": 0, "product": 1}),
        _contradicted,
    ),
    ProspectiveScenario(
        "unsupported_acceptance_unresolved",
        "A claims D10; the terminal decision is unresolved: insufficient evidence, not contradicted.",
        True,
        ("false_acceptance",),
        _arms(A={"D": 3, "C": 2, "F": 0, "U": 1, "K": 0}),
        _unsupported_unresolved,
    ),
    ProspectiveScenario(
        "unsupported_acceptance_invalid",
        "A claims D08 on a replay; the terminal decision is invalid: the experiment could not answer.",
        True,
        ("false_acceptance",),
        _arms(A={"D": 3, "C": 2, "F": 0, "U": 1, "K": 0}),
        _unsupported_invalid,
    ),
    ProspectiveScenario(
        "reference_missing",
        "A claims D01 but the terminal service never ran (interrupted); unknown, costs retained.",
        True,
        ("reference_missing", "execution_incomplete"),
        _arms(A={"D": 2, "C": 1, "F": 0, "U": 0, "K": 1}),
        _reference_missing,
    ),
    ProspectiveScenario(
        "reference_corrupt",
        "A's D01 decision bytes were altered after the ledger bound them.",
        False,
        ("decision_unverifiable",),
        _arms(A={"D": 2, "C": 1, "F": 0, "U": 0, "K": 1}),
        _reference_corrupt,
        _tamper_a_d01,
    ),
    ProspectiveScenario(
        "correct_abstention",
        "B refuses its D07 candidate and the terminal reference rejects it.",
        True,
        (),
        _arms(B={"D": 1, "C": 1, "correct": 2, "refuse": 2}),
        _correct_abstention,
    ),
    ProspectiveScenario(
        "missed_correction_own_reference",
        "A abstains on D01 although its own frozen candidate is accepted.",
        True,
        ("refusal_missed_correct_opportunity",),
        _arms(A={"D": 1, "C": 1, "missed": 1, "product": 1}),
        _missed_own_reference,
    ),
    ProspectiveScenario(
        "missed_correction_paired_reference",
        "A abstains on D01 without a reference of its own; B's candidate is accepted.",
        True,
        ("refusal_missed_correct_opportunity",),
        _arms(A={"D": 1, "C": 1, "missed": 1, "abstain": 1}),
        _missed_paired_reference,
    ),
    ProspectiveScenario(
        "all_abstain",
        "A never accepts: F is zero by construction and the report says so.",
        True,
        ("method_never_accepts",),
        _arms(A={"N": 4, "D": 0, "C": 0, "F": 0, "missed": 2, "correct": 1, "unadjudicated": 1}),
        _all_abstain,
    ),
    ProspectiveScenario(
        "zero_confirmed_claims",
        "Every claim of A is contradicted: F/C is undefined, cost per correct is undefined.",
        True,
        ("claim_contradicted",),
        _arms(A={"D": 2, "C": 0, "F": 2, "product": 0}),
        _zero_confirmed_claims,
    ),
    ProspectiveScenario(
        "missing_assigned_case",
        "B has no trial for D10: not attempted, unknown cost, still in N.",
        True,
        ("trial_missing",),
        _arms(B={"N": 4, "D": 2, "not_attempted": 1}),
        _missing_assigned_case,
    ),
    ProspectiveScenario(
        "reference_candidate_mismatch",
        "A declares one candidate on D01; the terminal decision adjudicates another.",
        True,
        ("reference_candidate_mismatch",),
        _arms(A={"D": 2, "C": 1, "K": 1, "product": 1}),
        _candidate_mismatch,
    ),
    ProspectiveScenario(
        "declaration_ambiguous",
        "A second accepted receipt with another disposition exists for A on D01.",
        False,
        ("declaration_ambiguous",),
        _arms(),
        _declaration_ambiguous,
    ),
    ProspectiveScenario(
        "post_outcome_claim_change",
        "A tried to change its D01 declaration after the decision; the writer rejected it.",
        True,
        ("declaration_change_attempted",),
        _arms(A={"D": 2, "C": 2}),
        _post_outcome_change,
    ),
    ProspectiveScenario(
        "retry_identical",
        "A retried the D01 receipt with identical content: counted once.",
        True,
        ("declaration_retry_identical",),
        _arms(A={"D": 2, "C": 2}),
        _retry_identical,
    ),
    ProspectiveScenario(
        "order_unverified",
        "Receipts without terminal bindings: order rests on timestamps; nothing is prospective.",
        True,
        ("declaration_order_unverified",),
        _arms(A={"D": 2, "C": 2, "prospective": 0}),
        _order_unverified,
    ),
    ProspectiveScenario(
        "terminal_binding_broken",
        "B's D01 terminal-result names a decision digest that is not the trial's decision.",
        False,
        ("terminal_binding_unverifiable",),
        _arms(),
        _terminal_binding_broken,
    ),
    ProspectiveScenario(
        "demonstration_scope",
        "Receipts in the retained-development scope verify but are not prospective.",
        True,
        (),
        _arms(A={"D": 2, "C": 2, "prospective": 0}),
        _demonstration_scope,
    ),
    ProspectiveScenario(
        "partial_costs",
        "A reports the simulator wall in two of four trials: known part only, failures included.",
        True,
        (),
        _arms(A={"D": 2, "C": 2}),
        _partial_costs,
    ),
    ProspectiveScenario(
        "derived_from_v1",
        "A v1 ledger: declarations derived from arm_claimed_acceptance, labelled retrospective.",
        True,
        (),
        _arms(A={"D": 2, "C": 2, "prospective": 0}, B={"D": 2, "C": 2, "prospective": 0}),
        _derived_v1,
    ),
)


def build_derived_control(ledger_path: Path, out_dir: Path, *, root: Path | None = None) -> Path:
    """A labelled derived control on the real ten-case ledger: arm A's declarations rewritten.

    Arm A gets synthetic receipts in the retained-development scope that claim D05 (its real
    terminal decision is rejected on progress_lost) and abstain on D07 (its real terminal
    decision is accepted); every other receipt is the truthful derived declaration. Nothing
    is re-run. Without ``root`` the referenced decision, confirmation, diagnosis and bundle
    bytes are copied unchanged into ``out_dir`` so every digest still binds under that
    directory; with ``root`` (a directory containing both the ledger and ``out_dir``) the
    record paths are rewritten relative to it and nothing is copied.
    """
    import shutil

    ledger_path = Path(ledger_path)
    out_dir = Path(out_dir)
    source_root = ledger_path.parent
    relative_prefix = None
    if root is not None:
        root = Path(root).resolve()
        relative_prefix = source_root.resolve().relative_to(root)
        declaration_prefix = out_dir.resolve().relative_to(root)
    ledger = json.loads(ledger_path.read_text())
    ledger["schema"] = LEDGER_SCHEMA_V2
    ledger["evidence_origin"] = "derived_control"
    ledger["derived_from"] = {
        "ledger": str(ledger_path.resolve().relative_to(root))
        if root is not None
        else str(ledger_path),
        "sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "note": "arm A declarations synthesized for a labelled control; records unchanged",
    }

    def mirror(relative: str) -> None:
        source = source_root / relative
        if not source.is_file():
            return
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(source, target)

    for trial in ledger["trials"]:
        for key in ("decision", "confirmation", "diagnosis"):
            reference = trial.get(key)
            if not (isinstance(reference, dict) and isinstance(reference.get("path"), str)):
                continue
            if relative_prefix is not None:
                reference["path"] = str(relative_prefix / reference["path"])
                continue
            mirror(reference["path"])
            record_path = source_root / reference["path"]
            if key in ("confirmation", "diagnosis") and record_path.is_file():
                record = json.loads(record_path.read_text())
                bundle = record.get("bundle_path")
                if isinstance(bundle, str):
                    folder = Path(reference["path"]).parent
                    for candidate in (folder / bundle, folder / (bundle + ".gz")):
                        mirror(str(candidate))
        spec = {
            "disposition": CLAIM if trial.get("arm_claimed_acceptance") else None,
            "candidate": None,
            "scope": DEMONSTRATION_SCOPE,
            "minute": None,
            "reason": "derived control; declaration synthesized from the retained trial",
            "terminal": False,
            "additional": [],
        }
        executed = [p["candidate_digest"] for p in trial["proposals"] if p.get("executed")]
        # The candidate configuration is the diagnosis record's ``candidate`` block, whose
        # writer digest is the trial's executed proposal digest; nothing is imputed.
        configuration = None
        diagnosis = trial.get("diagnosis") or {}
        if executed and isinstance(diagnosis.get("path"), str):
            diagnosis_path = (
                root / diagnosis["path"]
                if relative_prefix is not None
                else source_root / diagnosis["path"]
            )
            candidate = json.loads(diagnosis_path.read_text()).get("candidate")
            if isinstance(candidate, dict) and _writer_digest(candidate) == _norm(executed[-1]):
                configuration = candidate
            else:
                raise ValueError(
                    f"the diagnosis record of {trial['case_id']} {trial['arm']} does not bind "
                    "the executed candidate; the derived control cannot declare it"
                )
        if spec["disposition"] is None:
            spec["disposition"] = (
                "unresolved"
                if trial["status"] == "unresolved"
                else "refuse"
                if trial["proposals"]
                else "abstain"
            )
        else:
            spec["candidate"] = configuration
        if trial["arm"] == "A" and trial["case_id"].startswith("D05"):
            spec.update(
                disposition=CLAIM,
                candidate=configuration,
                reason="derived control: A claims the candidate its real reference rejected",
            )
        if trial["arm"] == "A" and trial["case_id"].startswith("D07"):
            spec.update(
                disposition="abstain",
                candidate=None,
                reason="derived control: A abstains although its real reference accepted",
            )
        trial[SPEC] = spec
    preparation = ledger.get("preparation_cost_ledger")
    if relative_prefix is not None and isinstance(preparation, dict) and preparation.get("path"):
        preparation["path"] = str(relative_prefix / preparation["path"])
    for trial in ledger["trials"]:
        spec = trial.pop(SPEC)
        base = f"declarations/{trial['arm']}-{trial['case_id']}"
        reference = _write(out_dir, f"{base}/declaration.json", receipt(ledger, trial, spec))
        if relative_prefix is not None:
            reference["path"] = str(declaration_prefix / reference["path"])
        trial["declaration"] = reference
    if relative_prefix is not None:
        ledger["root"] = "."
        ledger["note"] = (
            "record and declaration paths are relative to the repository root; score with "
            "--root at that root"
        )
    path = out_dir / "ledger.json"
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    return path


def binding_probe_control(folder: Path, *, variant: str = "commentary_digests") -> Path:
    """A labelled copy of the fair prospective fixture with one trial's terminal chain replaced.

    Every declaration, decision and cost stays as in the positive fixture; only arm A's D01
    ``terminal-start.json`` and ``terminal-result.json`` are replaced and the ledger's outer
    references recomputed, so the control reaches semantic validation instead of failing
    on a stale checksum. Variants:

    * ``commentary_digests``: unrelated documents (``unrelated.document.v1``) whose only
      link to the declaration, start and decision is the expected digests inside a
      commentary object (the preparation probe of 19 September 2026);
    * ``replaced_link_digest_elsewhere``: proper schemas, but the result's ``declaration``
      reference names another digest while the correct one still appears elsewhere;
    * ``wrong_schema``: proper fields under ``nisayon.terminal-start.v2``;
    * ``wrong_arm``: proper fields with the start's assignment naming arm B;
    * ``missing_terminal_evidence``: a proper result whose ``terminal_evidence`` is empty.
    """
    folder = Path(folder)
    path = write_prospective_ledger(prospective_ledger(), folder)
    ledger = json.loads(path.read_text())
    trial = next(t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    declaration = trial["declaration"]
    decision = trial["decision"]
    base = Path(trial["terminal_start"]["path"]).parent
    record = json.loads((folder / declaration["path"]).read_text())
    if variant == "commentary_digests":
        start = {
            "schema": "unrelated.document.v1",
            "commentary": {"unrelated_digest": declaration["sha256"]},
        }
        start_ref = _write(folder, f"{base}/terminal-start.json", start)
        result = {
            "schema": "unrelated.document.v1",
            "commentary": {
                "unrelated_digests": [
                    declaration["sha256"],
                    start_ref["sha256"],
                    decision["sha256"],
                ]
            },
        }
    else:
        evidence = [{"path": decision["path"], "sha256": decision["sha256"]}]
        start, result = terminal_records(
            trial,
            record,
            evidence=[] if variant == "missing_terminal_evidence" else evidence,
            ended=trial["timeline"]["ended_at"],
        )
        if variant == "wrong_schema":
            start["schema"] = "nisayon.terminal-start.v2"
        if variant == "wrong_arm":
            start["assignment"] = {**record["assignment"], "arm": "B"}
        start_ref = _write(folder, f"{base}/terminal-start.json", start)
        result = bind_result(result, start_ref)
        if variant == "replaced_link_digest_elsewhere":
            result["declaration"] = {"path": declaration["path"], "sha256": "ab" * 32}
            result["commentary"] = {
                "note": "correct digest kept here",
                "digest": declaration["sha256"],
            }
    result_ref = _write(folder, f"{base}/terminal-result.json", result)
    trial["terminal_start"] = start_ref
    trial["terminal_result"] = result_ref
    ledger["evidence_origin"] = "synthetic_development"
    ledger["control"] = {
        "name": f"binding-probe:{variant}",
        "changed": ["trials[A,D01].terminal_start", "trials[A,D01].terminal_result"],
        "note": "labelled control; declarations, decisions and costs are the positive fixture's",
    }
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    return path


OMISSION_VARIANTS = (
    "start_observed_absent",
    "result_observed_absent",
    "start_candidate_absent",
    "start_scope_absent",
    "declaration_suite_absent",
    "declaration_frozen_inputs_absent",
)


def required_field_omission_control(folder: Path, *, variant: str) -> Path:
    """A labelled copy of the positive fixture with one required field removed.

    The six variants are the execution lane's public omission probe of 19 September
    2026 (`engine-integration-001/audit_required_fields.py`): a terminal-start or
    terminal-result without ``observed``, a start without ``candidate`` or
    ``evidence_scope``, or a declaration whose assignment lacks ``suite_id`` or
    ``frozen_inputs_sha256`` (the start and result then repeat the same incomplete
    assignment, so the objects agree with one another). Only arm A's D01 records
    change and the outer digests are recomputed, so the control reaches semantic
    validation. ``variant="positive"`` returns the untouched positive fixture.
    """
    folder = Path(folder)
    path = write_prospective_ledger(prospective_ledger(), folder)
    if variant == "positive":
        return path
    if variant not in OMISSION_VARIANTS:
        raise ValueError(f"unknown omission variant {variant!r}")
    ledger = json.loads(path.read_text())
    trial = next(t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    declaration_path = folder / trial["declaration"]["path"]
    start_path = folder / trial["terminal_start"]["path"]
    result_path = folder / trial["terminal_result"]["path"]
    declaration = json.loads(declaration_path.read_text())
    start = json.loads(start_path.read_text())
    result = json.loads(result_path.read_text())

    def rebind(target: Path, record: dict) -> str:
        raw = (json.dumps(record, indent=2) + "\n").encode()
        target.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    if variant.startswith("declaration_"):
        key = "suite_id" if variant == "declaration_suite_absent" else "frozen_inputs_sha256"
        del declaration["assignment"][key]
        start["assignment"] = declaration["assignment"]
        result["assignment"] = declaration["assignment"]
        digest = rebind(declaration_path, declaration)
        trial["declaration"]["sha256"] = digest
        start["declaration"]["sha256"] = digest
        result["declaration"]["sha256"] = digest
    elif variant == "start_observed_absent":
        del start["observed"]
    elif variant == "result_observed_absent":
        del result["observed"]
    elif variant == "start_candidate_absent":
        del start["candidate"]
    elif variant == "start_scope_absent":
        del start["evidence_scope"]
    digest = rebind(start_path, start)
    trial["terminal_start"]["sha256"] = digest
    result["terminal_start"]["sha256"] = digest
    trial["terminal_result"]["sha256"] = rebind(result_path, result)
    ledger["control"] = {
        "name": f"required-field-omission:{variant}",
        "changed": ["trials[A,D01] declaration/terminal records; outer digests recomputed"],
        "note": "labelled control; every other record, decision and cost is the positive fixture's",
    }
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    return path


def contract_mutation_control(
    folder: Path,
    *,
    record: str,
    mutate: Callable[[dict], None],
    rebind_request: bool = True,
) -> Path:
    """A labelled copy of the positive fixture with one record of arm A's D01 mutated.

    ``record`` is ``declaration``, ``terminal-start`` or ``terminal-result``; ``mutate``
    edits the loaded JSON object in place. Downstream references and the ledger's outer
    digests are recomputed so the control reaches semantic validation, and the result's
    ``request_sha256`` is recomputed over its (possibly rebound) ``terminal_start`` unless
    ``rebind_request`` is false, so that only the intended defect remains.
    """
    folder = Path(folder)
    path = write_prospective_ledger(prospective_ledger(), folder)
    ledger = json.loads(path.read_text())
    trial = next(t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    paths = {
        "declaration": folder / trial["declaration"]["path"],
        "terminal-start": folder / trial["terminal_start"]["path"],
        "terminal-result": folder / trial["terminal_result"]["path"],
    }
    records = {name: json.loads(p.read_text()) for name, p in paths.items()}
    mutate(records[record])

    def rebind(name: str) -> str:
        raw = (json.dumps(records[name], indent=2) + "\n").encode()
        paths[name].write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    if record == "declaration":
        digest = rebind("declaration")
        trial["declaration"]["sha256"] = digest
        records["terminal-start"]["declaration"]["sha256"] = digest
        records["terminal-result"]["declaration"]["sha256"] = digest
    if record in ("declaration", "terminal-start"):
        digest = rebind("terminal-start")
        trial["terminal_start"]["sha256"] = digest
        records["terminal-result"]["terminal_start"]["sha256"] = digest
        if rebind_request:
            records["terminal-result"]["request_sha256"] = _writer_digest(
                {
                    "terminal_start": records["terminal-result"]["terminal_start"],
                    "terminal_evidence": records["terminal-result"]["terminal_evidence"],
                }
            )
    elif (
        rebind_request
        and "terminal_start" in records["terminal-result"]
        and "request_sha256" in records["terminal-result"]
    ):
        records["terminal-result"]["request_sha256"] = _writer_digest(
            {
                "terminal_start": records["terminal-result"]["terminal_start"],
                "terminal_evidence": records["terminal-result"].get("terminal_evidence"),
            }
        )
    trial["terminal_result"]["sha256"] = rebind("terminal-result")
    ledger["control"] = {
        "name": f"contract-mutation:{record}",
        "changed": [f"trials[A,D01].{record}; downstream references and outer digests recomputed"],
        "note": "labelled control; every other record, decision and cost is the positive fixture's",
    }
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    return path


def _delete(key: str) -> Callable[[dict], None]:
    def apply(record: dict) -> None:
        del record[key]

    return apply


def _delete_in(block: str, key: str) -> Callable[[dict], None]:
    def apply(record: dict) -> None:
        del record[block][key]

    return apply


def _set(key: str, value: object) -> Callable[[dict], None]:
    def apply(record: dict) -> None:
        record[key] = value

    return apply


def _set_in(block: str, key: str, value: object) -> Callable[[dict], None]:
    def apply(record: dict) -> None:
        record[block][key] = value

    return apply


# The finite mutation matrix: (name, record, mutation, expected blocking code, table field).
# Absence, explicit null, a type substitute and a semantic mismatch are distinct boundaries.
CONTRACT_MUTATIONS: tuple[tuple[str, str, Callable[[dict], None], str, str], ...] = (
    # declaration: assignment
    (
        "declaration_assignment_absent",
        "declaration",
        _delete("assignment"),
        "declaration_malformed",
        "assignment",
    ),
    (
        "declaration_assignment_null",
        "declaration",
        _set("assignment", None),
        "declaration_malformed",
        "assignment",
    ),
    (
        "declaration_suite_absent",
        "declaration",
        _delete_in("assignment", "suite_id"),
        "declaration_malformed",
        "assignment.suite_id",
    ),
    (
        "declaration_suite_null",
        "declaration",
        _set_in("assignment", "suite_id", None),
        "declaration_malformed",
        "assignment.suite_id",
    ),
    (
        "declaration_suite_empty",
        "declaration",
        _set_in("assignment", "suite_id", " "),
        "declaration_malformed",
        "assignment.suite_id",
    ),
    (
        "declaration_suite_other",
        "declaration",
        _set_in("assignment", "suite_id", "another-suite"),
        "declaration_mismatch",
        "assignment.suite_id",
    ),
    (
        "declaration_case_absent",
        "declaration",
        _delete_in("assignment", "case_id"),
        "declaration_malformed",
        "assignment.case_id",
    ),
    (
        "declaration_arm_other",
        "declaration",
        _set_in("assignment", "arm", "B"),
        "declaration_mismatch",
        "assignment.arm",
    ),
    (
        "declaration_frozen_inputs_absent",
        "declaration",
        _delete_in("assignment", "frozen_inputs_sha256"),
        "declaration_malformed",
        "assignment.frozen_inputs_sha256",
    ),
    (
        "declaration_frozen_inputs_prefixed",
        "declaration",
        lambda r: r["assignment"].update(
            frozen_inputs_sha256="sha256:" + r["assignment"]["frozen_inputs_sha256"]
        ),
        "declaration_malformed",
        "assignment.frozen_inputs_sha256",
    ),
    (
        "declaration_frozen_inputs_other",
        "declaration",
        _set_in("assignment", "frozen_inputs_sha256", "f" * 64),
        "declaration_mismatch",
        "assignment.frozen_inputs_sha256",
    ),
    (
        "declaration_assignment_extra_key",
        "declaration",
        _set_in("assignment", "note", "x"),
        "declaration_malformed",
        "assignment",
    ),
    # declaration: candidate
    (
        "declaration_candidate_absent",
        "declaration",
        _delete("candidate"),
        "declaration_malformed",
        "candidate",
    ),
    (
        "declaration_claim_candidate_null",
        "declaration",
        _set("candidate", None),
        "declaration_malformed",
        "candidate",
    ),
    (
        "declaration_candidate_unbound",
        "declaration",
        _set_in("candidate", "configuration_sha256", "0" * 64),
        "declaration_malformed",
        "candidate",
    ),
    (
        "declaration_candidate_configuration_not_object",
        "declaration",
        _set_in("candidate", "configuration", "repair"),
        "declaration_malformed",
        "candidate",
    ),
    (
        "declaration_candidate_extra_key",
        "declaration",
        _set_in("candidate", "digest", "x"),
        "declaration_malformed",
        "candidate",
    ),
    # declaration: vocabularies, reason, identity objects, evidence
    (
        "declaration_disposition_absent",
        "declaration",
        _delete("disposition"),
        "declaration_malformed",
        "disposition",
    ),
    (
        "declaration_disposition_unknown",
        "declaration",
        _set("disposition", "accept"),
        "declaration_malformed",
        "disposition",
    ),
    (
        "declaration_scope_absent",
        "declaration",
        _delete("evidence_scope"),
        "declaration_malformed",
        "evidence_scope",
    ),
    (
        "declaration_scope_unknown",
        "declaration",
        _set("evidence_scope", "custody"),
        "declaration_malformed",
        "evidence_scope",
    ),
    (
        "declaration_reason_absent",
        "declaration",
        _delete("reason"),
        "declaration_malformed",
        "reason",
    ),
    (
        "declaration_reason_empty",
        "declaration",
        _set("reason", ""),
        "declaration_malformed",
        "reason",
    ),
    (
        "declaration_source_empty",
        "declaration",
        _set("source", {}),
        "declaration_malformed",
        "source",
    ),
    (
        "declaration_settings_null",
        "declaration",
        _set("settings", None),
        "declaration_malformed",
        "settings",
    ),
    (
        "declaration_evidence_absent",
        "declaration",
        _delete("evidence"),
        "declaration_malformed",
        "evidence",
    ),
    (
        "declaration_evidence_not_reference",
        "declaration",
        _set("evidence", [{"note": "x"}]),
        "declaration_malformed",
        "evidence",
    ),
    # declaration: generated bindings and observed
    (
        "declaration_request_digest_absent",
        "declaration",
        _delete("request_sha256"),
        "declaration_malformed",
        "request_sha256",
    ),
    (
        "declaration_request_digest_stale",
        "declaration",
        _set("reason", "edited after signing"),
        "declaration_malformed",
        "request_sha256",
    ),
    (
        "declaration_source_digest_wrong",
        "declaration",
        _set("source_sha256", "1" * 64),
        "declaration_malformed",
        "source_sha256",
    ),
    (
        "declaration_settings_digest_absent",
        "declaration",
        _delete("settings_sha256"),
        "declaration_malformed",
        "settings_sha256",
    ),
    (
        "declaration_observed_absent",
        "declaration",
        _delete("observed"),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_observed_null",
        "declaration",
        _set("observed", None),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_event_id_absent",
        "declaration",
        _delete_in("observed", "event_id"),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_sequence_bool",
        "declaration",
        _set_in("observed", "sequence", True),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_sequence_float",
        "declaration",
        _set_in("observed", "sequence", 1.0),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_sequence_string",
        "declaration",
        _set_in("observed", "sequence", "1"),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_sequence_wrong",
        "declaration",
        _set_in("observed", "sequence", 2),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_clock_naive",
        "declaration",
        _set_in("observed", "recorded_at", "2026-09-18T02:00:30"),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_clock_absent",
        "declaration",
        _delete_in("observed", "recorded_at"),
        "declaration_malformed",
        "observed",
    ),
    (
        "declaration_schema_other",
        "declaration",
        _set("schema", "nisayon.arm-declaration.v2"),
        "declaration_malformed",
        "schema",
    ),
    # type substitutes for vocabulary and identity strings: an object or a list where a
    # string is required (the execution lane's two remaining matrix rows of 19 September)
    (
        "declaration_disposition_object",
        "declaration",
        _set("disposition", {}),
        "declaration_malformed",
        "disposition",
    ),
    (
        "declaration_disposition_list",
        "declaration",
        _set("disposition", ["claim_acceptance"]),
        "declaration_malformed",
        "disposition",
    ),
    (
        "declaration_scope_object",
        "declaration",
        _set("evidence_scope", {}),
        "declaration_malformed",
        "evidence_scope",
    ),
    (
        "declaration_suite_object",
        "declaration",
        _set_in("assignment", "suite_id", {}),
        "declaration_malformed",
        "assignment.suite_id",
    ),
    (
        "declaration_case_object",
        "declaration",
        _set_in("assignment", "case_id", {}),
        "declaration_malformed",
        "assignment.case_id",
    ),
    (
        "declaration_arm_list",
        "declaration",
        _set_in("assignment", "arm", ["A"]),
        "declaration_malformed",
        "assignment.arm",
    ),
    (
        "declaration_schema_object",
        "declaration",
        _set("schema", {}),
        "declaration_malformed",
        "schema",
    ),
    # terminal-start
    (
        "start_schema_absent",
        "terminal-start",
        _delete("schema"),
        "terminal_binding_unverifiable",
        "schema",
    ),
    (
        "start_declaration_absent",
        "terminal-start",
        _delete("declaration"),
        "terminal_binding_unverifiable",
        "declaration",
    ),
    (
        "start_declaration_null",
        "terminal-start",
        _set("declaration", None),
        "terminal_binding_unverifiable",
        "declaration",
    ),
    (
        "start_declaration_path_other",
        "terminal-start",
        lambda r: r["declaration"].update(path="elsewhere/declaration.json"),
        "terminal_binding_unverifiable",
        "declaration",
    ),
    (
        "start_assignment_absent",
        "terminal-start",
        _delete("assignment"),
        "terminal_binding_unverifiable",
        "assignment",
    ),
    (
        "start_assignment_partial",
        "terminal-start",
        _delete_in("assignment", "suite_id"),
        "terminal_binding_unverifiable",
        "assignment",
    ),
    (
        "start_candidate_absent",
        "terminal-start",
        _delete("candidate"),
        "terminal_binding_unverifiable",
        "candidate",
    ),
    (
        "start_candidate_null_on_claim",
        "terminal-start",
        _set("candidate", None),
        "terminal_binding_unverifiable",
        "candidate",
    ),
    (
        "start_scope_absent",
        "terminal-start",
        _delete("evidence_scope"),
        "terminal_binding_unverifiable",
        "evidence_scope",
    ),
    (
        "start_scope_null",
        "terminal-start",
        _set("evidence_scope", None),
        "terminal_binding_unverifiable",
        "evidence_scope",
    ),
    (
        "start_observed_absent",
        "terminal-start",
        _delete("observed"),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "start_observed_null",
        "terminal-start",
        _set("observed", None),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "start_sequence_bool",
        "terminal-start",
        _set_in("observed", "sequence", True),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "start_sequence_one",
        "terminal-start",
        _set_in("observed", "sequence", 1),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "start_event_id_empty",
        "terminal-start",
        _set_in("observed", "event_id", ""),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "start_before_declaration",
        "terminal-start",
        _set_in("observed", "recorded_at", "2026-09-17T00:00:00+00:00"),
        "terminal_binding_unverifiable",
        "observed",
    ),
    # terminal-result
    (
        "result_schema_other",
        "terminal-result",
        _set("schema", "nisayon.terminal-result.v2"),
        "terminal_binding_unverifiable",
        "schema",
    ),
    (
        "result_start_absent",
        "terminal-result",
        _delete("terminal_start"),
        "terminal_binding_unverifiable",
        "terminal_start",
    ),
    (
        "result_start_null",
        "terminal-result",
        _set("terminal_start", None),
        "terminal_binding_unverifiable",
        "terminal_start",
    ),
    (
        "result_declaration_absent",
        "terminal-result",
        _delete("declaration"),
        "terminal_binding_unverifiable",
        "declaration",
    ),
    (
        "result_assignment_absent",
        "terminal-result",
        _delete("assignment"),
        "terminal_binding_unverifiable",
        "assignment",
    ),
    (
        "result_assignment_partial",
        "terminal-result",
        _delete_in("assignment", "arm"),
        "terminal_binding_unverifiable",
        "assignment",
    ),
    (
        "result_evidence_absent",
        "terminal-result",
        _delete("terminal_evidence"),
        "terminal_binding_unverifiable",
        "terminal_evidence",
    ),
    (
        "result_evidence_null",
        "terminal-result",
        _set("terminal_evidence", None),
        "terminal_binding_unverifiable",
        "terminal_evidence",
    ),
    (
        "result_evidence_empty",
        "terminal-result",
        _set("terminal_evidence", []),
        "terminal_binding_unverifiable",
        "terminal_evidence",
    ),
    (
        "result_evidence_not_reference",
        "terminal-result",
        _set("terminal_evidence", [{"note": "x"}]),
        "terminal_binding_unverifiable",
        "terminal_evidence",
    ),
    (
        "result_request_digest_absent",
        "terminal-result",
        _delete("request_sha256"),
        "terminal_binding_unverifiable",
        "request_sha256",
    ),
    (
        "result_observed_absent",
        "terminal-result",
        _delete("observed"),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "result_sequence_bool",
        "terminal-result",
        _set_in("observed", "sequence", True),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "result_sequence_two",
        "terminal-result",
        _set_in("observed", "sequence", 2),
        "terminal_binding_unverifiable",
        "observed",
    ),
    (
        "result_before_start",
        "terminal-result",
        _set_in("observed", "recorded_at", "2026-09-17T00:00:00+00:00"),
        "terminal_binding_unverifiable",
        "observed",
    ),
)
