"""Score an arm comparison ledger (``nisayon.comparison.v1``) without re-running anything.

The scorer checks that the comparison was fair, counts what happened to every
assigned case per arm, and aggregates costs without inventing missing ones.
It reports no ratio between arms; the reader draws the comparison under the
stated unknowns.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from .schema import (
    Malformed,
    Quantity,
    boolean,
    digest_of,
    finite,
    integer,
    load_json,
    mapping,
    parse_quantity,
    parse_wall_time,
    require,
    sequence,
    string,
)

LEDGER_SCHEMA = "nisayon.comparison.v1"
SCORE_SCHEMA = "nisayon.comparison.score.v1"
STATUSES = {
    "confirmed",
    "rejected",
    "unresolved",
    "invalid",
    "unsupported",
    "timeout",
    "not_attempted",
}
ARM_KINDS = {"scripted", "agent"}
SELECTIONS = {"fixed", "adaptive"}
BLOCKING = {
    "agent_context_not_isolated",
    "agent_undeclared",
    "arm_budgets_differ",
    "decision_not_bound_to_trial",
    "decision_unverifiable",
    "decision_shared_between_arms",
    "trial_record_unverifiable",
    "trial_duplicated",
    "unknown_reference",
    "frozen_inputs_differ",
    "arms_not_matched",
    "cost_unit_conflict",
    "invalid_case_confirmed",
    "malformed_ledger",
}


def _digest_matches(declared: str, value: object) -> bool:
    computed = digest_of(value)
    bare = computed.removeprefix("sha256:")
    return declared in (computed, bare)


def _parse_trial(item: object, index: int, cases: dict, arms: dict) -> tuple[dict, list[dict]]:
    path = f"trials[{index}]"
    data = mapping(item, path)
    findings: list[dict] = []
    trial = {
        "arm": string(data, "arm", path),
        "case_id": string(data, "case_id", path),
        "status": string(data, "status", path, allowed=STATUSES),
        "declared_status": string(data, "status", path, allowed=STATUSES),
        "received_frozen_sha256": data.get("received_frozen_sha256"),
        "decision": data.get("decision"),
        "arm_claimed_acceptance": data.get("arm_claimed_acceptance"),
        "proposals": [],
        "diagnostic_rollouts": integer(
            data.get("diagnostic_rollouts", 0), f"{path}.diagnostic_rollouts", minimum=0
        ),
        "confirmation_rollouts": integer(
            data.get("confirmation_rollouts", 0), f"{path}.confirmation_rollouts", minimum=0
        ),
        "retries": integer(data.get("retries", 0), f"{path}.retries", minimum=0),
        "timeline": None,
        "full_trial_timeline": None,
        "confirmation_timeline": None,
        "time_to_confirmed_correction_s": None,
        "records": {},
        "costs": {},
    }
    # Retained records a trial binds by path and digest (the execution lane names its
    # diagnosis and confirmation result this way); each is verified when a root is given.
    for name in ("diagnosis", "confirmation"):
        item = data.get(name)
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            trial["records"][name] = {"path": item["path"], "sha256": item.get("sha256")}
    if trial["arm_claimed_acceptance"] is not None and not isinstance(
        trial["arm_claimed_acceptance"], bool
    ):
        raise Malformed(f"{path}.arm_claimed_acceptance", "expected true, false or null")
    if trial["arm"] not in arms:
        findings.append(
            {"code": "unknown_reference", "detail": f"{path}: arm {trial['arm']!r} is not declared"}
        )
    if trial["case_id"] not in cases:
        findings.append(
            {
                "code": "unknown_reference",
                "detail": f"{path}: case {trial['case_id']!r} is not in the suite",
            }
        )
    for pindex, proposal in enumerate(sequence(data.get("proposals", []), f"{path}.proposals")):
        ppath = f"{path}.proposals[{pindex}]"
        pdata = mapping(proposal, ppath)
        trial["proposals"].append(
            {
                "candidate_digest": pdata.get("candidate_digest"),
                "executed": boolean(pdata, "executed", ppath) if "executed" in pdata else False,
                "rejected_before_execution": boolean(pdata, "rejected_before_execution", ppath)
                if "rejected_before_execution" in pdata
                else False,
                "reason": pdata.get("reason"),
            }
        )
    # ``timeline`` is the diagnostic interval the budget applies to. The full trial interval
    # and the confirmation interval are retained separately so the reported elapsed wall can
    # describe the complete result without disguising confirmation time as diagnosis.
    trial["timeline"] = _interval(data, "timeline", path)
    trial["full_trial_timeline"] = _interval(data, "full_trial_timeline", path)
    trial["confirmation_timeline"] = _interval(data, "confirmation_timeline", path)
    if trial["full_trial_timeline"] and trial["timeline"]:
        if (
            trial["full_trial_timeline"][0] > trial["timeline"][0]
            or trial["full_trial_timeline"][1] < trial["timeline"][1]
        ):
            raise Malformed(
                f"{path}.full_trial_timeline", "the full trial does not contain its diagnosis"
            )
    if trial["confirmation_timeline"] and trial["full_trial_timeline"]:
        if (
            trial["confirmation_timeline"][0] < trial["full_trial_timeline"][0]
            or trial["confirmation_timeline"][1] > trial["full_trial_timeline"][1]
        ):
            raise Malformed(
                f"{path}.confirmation_timeline", "the confirmation lies outside the full trial"
            )
    if data.get("time_to_confirmed_correction_s") is not None:
        value = finite(
            data["time_to_confirmed_correction_s"], f"{path}.time_to_confirmed_correction_s"
        )
        if value < 0:
            raise Malformed(f"{path}.time_to_confirmed_correction_s", "negative duration")
        if trial["full_trial_timeline"]:
            span = (
                trial["full_trial_timeline"][1] - trial["full_trial_timeline"][0]
            ).total_seconds()
            if value > span + 1e-6:
                findings.append(
                    {
                        "code": "time_to_correction_exceeds_trial",
                        "detail": f"{path}: time_to_confirmed_correction_s {value} exceeds the full "
                        f"trial interval of {span:.6f} s",
                    }
                )
        trial["time_to_confirmed_correction_s"] = value
    for name, raw in mapping(data.get("costs", {}), f"{path}.costs").items():
        trial["costs"][name] = parse_quantity(raw, f"{path}.costs.{name}")
    if trial["decision"] is not None:
        ddata = mapping(trial["decision"], f"{path}.decision")
        trial["decision"] = {
            "path": ddata.get("path"),
            "sha256": ddata.get("sha256"),
            "decision": ddata.get("decision"),
            "candidate_digest": ddata.get("candidate_digest"),
        }
    return trial, findings


def _interval(data: dict, key: str, path: str) -> tuple[datetime, datetime] | None:
    if data.get(key) is None:
        return None
    tdata = mapping(data[key], f"{path}.{key}")
    started = parse_wall_time(
        {"value": tdata.get("started_at"), "clock": "wall_utc"}, f"{path}.{key}.started_at"
    )
    ended = parse_wall_time(
        {"value": tdata.get("ended_at"), "clock": "wall_utc"}, f"{path}.{key}.ended_at"
    )
    if ended < started:
        raise Malformed(f"{path}.{key}", "the interval ends before it starts")
    return (started, ended)


def _same_digest(declared: object, actual: object) -> bool:
    if not isinstance(declared, str) or not isinstance(actual, str):
        return False
    return declared.removeprefix("sha256:").lower() == actual.removeprefix("sha256:").lower()


def _verify_record(reference: dict, root: Path | None) -> str | None:
    """Why a path-and-digest reference cannot be verified, or None when it verifies."""
    if root is None:
        return "no root given; the path cannot be resolved"
    target = (root / reference["path"]).resolve()
    if not target.is_relative_to(root.resolve()):
        return "path escapes the root"
    if not target.is_file():
        return f"{reference['path']!r} not found under the root"
    if not isinstance(reference.get("sha256"), str) or not reference["sha256"].strip():
        return "digest not declared"
    if not _same_digest(reference["sha256"], hashlib.sha256(target.read_bytes()).hexdigest()):
        return "digest mismatch"
    return None


def _binding_problem(trial: dict, root: Path | None, verification: dict) -> str | None:
    """Why the trial's decision is not bound to the execution the trial names, or None.

    The trial names its confirmation result (or, without one, its diagnosis) by path and
    digest. That record names the decision it produced and the bundle it was made on.
    The trial's decision must be that decision, and the decision's ``bundle_sha256`` must
    be the digest of that bundle's document. A decision of another execution that shares
    the case, candidate or protocol is therefore not this trial's decision.
    """
    reference = trial.get("records", {}).get("confirmation") or trial.get("records", {}).get(
        "diagnosis"
    )
    if reference is None or root is None:
        return None
    target = (root / reference["path"]).resolve()
    if not target.is_file() or _verify_record(reference, root) is not None:
        return None  # already reported as trial_record_unverifiable
    try:
        record = load_json(target)
    except Malformed as error:
        return f"execution record malformed: {error}"
    if not isinstance(record, dict):
        return "execution record is not an object"
    named = record.get("decision") if isinstance(record.get("decision"), dict) else {}
    if not _same_digest(named.get("sha256"), (trial.get("decision") or {}).get("sha256")):
        return "the execution record names a different decision than the trial"
    bundle_path = record.get("bundle_path")
    if not isinstance(bundle_path, str) or not isinstance(record.get("bundle_sha256"), str):
        return "the execution record does not name its bundle by path and digest"
    bundle_file = (target.parent / bundle_path).resolve()
    if not bundle_file.is_relative_to(root.resolve()):
        return f"bundle {bundle_path!r} escapes the root"
    if bundle_file.is_file():
        declared = record["bundle_sha256"]
        if not _same_digest(declared, hashlib.sha256(bundle_file.read_bytes()).hexdigest()):
            return "the bundle's bytes differ from the digest the execution record declares"
    elif bundle_file.with_name(bundle_file.name + ".gz").is_file():
        # A retained copy keeps the bundle compressed; the decision's digest is over the
        # document, so the document still binds although the bytes differ.
        bundle_file = bundle_file.with_name(bundle_file.name + ".gz")
    else:
        return f"bundle {bundle_path!r} not found under the root"
    decision_bundle = verification.get("bundle_sha256")
    if not isinstance(decision_bundle, str):
        return "the decision carries no bundle_sha256; it predates execution binding"
    try:
        document = load_json(bundle_file)
    except Malformed as error:
        return f"bundle malformed: {error}"
    if not _same_digest(decision_bundle, digest_of(document)):
        return "the decision was made on a different bundle than the one the trial names"
    return None


def _verify_decision(trial: dict, root: Path | None, arm_id: str) -> dict:
    """Establish the trial's decision from retained bytes.

    Only a record that is found under the root, matches the digest the ledger declares for
    it, parses as a decision and belongs to the trial's case can support a confirmation.
    Anything else is named; a declaration in the ledger is never evidence on its own.
    """
    result: dict = {
        "decision": None,
        "candidate": None,
        "case_id": None,
        "verified": False,
        "how": "",
    }
    decision = trial["decision"]
    if decision is None:
        result["how"] = "no decision record named"
        return result
    if not isinstance(decision.get("path"), str) or not decision["path"].strip():
        result["how"] = "decision path not named"
        return result
    if root is None:
        result["how"] = "no root given; the decision path cannot be resolved"
        return result
    target = (root / decision["path"]).resolve()
    if not target.is_relative_to(root.resolve()):
        result["how"] = "decision path escapes the root"
        return result
    if not target.is_file():
        result["how"] = f"record {decision['path']!r} not found under the root"
        return result
    if not isinstance(decision.get("sha256"), str) or not decision["sha256"].strip():
        result["how"] = "record digest not declared; the ledger does not bind the decision bytes"
        return result
    raw = target.read_bytes()
    if not _same_digest(decision["sha256"], hashlib.sha256(raw).hexdigest()):
        result["how"] = "record digest mismatch"
        return result
    try:
        record = load_json(target)
    except Malformed as error:
        result["how"] = f"record malformed: {error}"
        return result
    if not isinstance(record, dict) or record.get("schema") != "nisayon.decision.v1":
        result["how"] = "record is not a decision"
        return result
    result["decision"] = record.get("decision")
    result["candidate"] = ((record.get("confirmation") or {}).get("candidate") or {}).get("digest")
    result["case_id"] = record.get("case_id")
    result["bundle_sha256"] = record.get("bundle_sha256")
    # The shared record names the case it decided; an arm-specific execution of the case
    # carries the arm suffix. Any other case is somebody else's decision.
    if result["case_id"] not in (trial["case_id"], f"{trial['case_id']}-{arm_id}"):
        result["how"] = f"record belongs to case {result['case_id']!r}, not {trial['case_id']!r}"
        return result
    result["verified"] = True
    result["how"] = "record verified"
    declared = decision.get("decision")
    if declared is not None and declared != result["decision"]:
        result["misdeclared"] = (
            f"the ledger declares {declared!r}; the verified record says {result['decision']!r}"
        )
    return result


def score_comparison(ledger: object, root: Path | None = None) -> dict:
    findings: list[dict] = []
    result: dict = {
        "schema": SCORE_SCHEMA,
        "fair": False,
        "solver_kind": None,
        "suite": None,
        "arms": {},
        "cases": {},
        "findings": findings,
        "limits": [
            "The scorer computes no ratio between arms; unknown cost components stay unknown.",
            "Cost per confirmed correction is undefined when nothing is confirmed.",
            "Cumulative simulator wall and elapsed wall are different quantities.",
            "A scripted development ablation is not an agent comparison.",
        ],
    }
    try:
        data = mapping(ledger, "ledger")
        schema = string(data, "schema", "ledger")
        if schema != LEDGER_SCHEMA:
            raise Malformed("ledger.schema", f"expected {LEDGER_SCHEMA}, found {schema!r}")
        suite = mapping(require(data, "suite", "ledger"), "ledger.suite")
        result["suite"] = {
            "id": string(suite, "id", "ledger.suite"),
            "obligation": suite.get("obligation"),
            "evaluator_commit": suite.get("evaluator_commit"),
            "solver_kind": suite.get("solver_kind"),
        }
        cases: dict[str, dict] = {}
        for index, item in enumerate(sequence(require(data, "cases", "ledger"), "ledger.cases")):
            cpath = f"ledger.cases[{index}]"
            cdata = mapping(item, cpath)
            case_id = string(cdata, "id", cpath)
            if case_id in cases:
                raise Malformed(f"{cpath}.id", f"duplicate case {case_id!r}")
            budget = mapping(cdata.get("budget", {}), f"{cpath}.budget")
            cases[case_id] = {
                "family": cdata.get("family"),
                "intended_class": cdata.get("intended_class"),
                "budget": {
                    "max_rollouts": integer(
                        budget["max_rollouts"], f"{cpath}.budget.max_rollouts", minimum=0
                    )
                    if "max_rollouts" in budget
                    else None,
                    "max_wall_seconds": finite(
                        budget["max_wall_seconds"], f"{cpath}.budget.max_wall_seconds"
                    )
                    if "max_wall_seconds" in budget
                    else None,
                },
                "frozen": mapping(require(cdata, "frozen", cpath), f"{cpath}.frozen"),
            }
        arms: dict[str, dict] = {}
        for index, item in enumerate(sequence(require(data, "arms", "ledger"), "ledger.arms")):
            apath = f"ledger.arms[{index}]"
            adata = mapping(item, apath)
            arm_id = string(adata, "id", apath)
            if arm_id in arms:
                raise Malformed(f"{apath}.id", f"duplicate arm {arm_id!r}")
            arms[arm_id] = {
                "kind": string(adata, "kind", apath, allowed=ARM_KINDS),
                "validity_layer": boolean(adata, "validity_layer", apath),
                "selection": string(adata, "selection", apath, allowed=SELECTIONS),
                "agent": adata.get("agent"),
                "budget": adata.get("budget"),
            }
        trials: list[dict] = []
        for index, item in enumerate(sequence(require(data, "trials", "ledger"), "ledger.trials")):
            trial, trial_findings = _parse_trial(item, index, cases, arms)
            findings.extend(trial_findings)
            trials.append(trial)
    except Malformed as error:
        findings.append({"code": "malformed_ledger", "detail": str(error)})
        return result

    kinds = {arm["kind"] for arm in arms.values()}
    # An agent arm must say which model, settings and context boundary it ran under; a
    # boundary other than isolated means the agent could read the shared development
    # workspace, and no outcome of that arm is a fair measurement.
    for arm_id, arm in sorted(arms.items()):
        if arm["kind"] != "agent":
            continue
        agent = arm.get("agent")
        required = ("model", "settings_sha256", "context_boundary")
        if not isinstance(agent, dict) or any(not agent.get(key) for key in required):
            findings.append(
                {
                    "code": "agent_undeclared",
                    "detail": f"agent arm {arm_id!r} does not declare model, settings_sha256 and "
                    "context_boundary",
                    "arm": arm_id,
                }
            )
        elif agent.get("context_boundary") != "isolated":
            findings.append(
                {
                    "code": "agent_context_not_isolated",
                    "detail": f"agent arm {arm_id!r} declares context boundary "
                    f"{agent.get('context_boundary')!r}; only an isolated agent is comparable",
                    "arm": arm_id,
                }
            )
    # Arms that declare a total budget (tokens, wall, calls) must declare the same one;
    # an arm with more room is not a matched arm.
    declared_budgets = {
        arm_id: arm["budget"] for arm_id, arm in arms.items() if arm.get("budget") is not None
    }
    if declared_budgets and (
        len(declared_budgets) != len(arms)
        or len({digest_of(b) for b in declared_budgets.values()}) > 1
    ):
        findings.append(
            {
                "code": "arm_budgets_differ",
                "detail": "arms do not declare the same total budget "
                f"({sorted(declared_budgets)} declare one; {sorted(arms)} are compared)",
            }
        )
    if kinds == {"agent"}:
        result["solver_kind"] = "agent_trial"
        signatures = {digest_of(arm.get("agent")) for arm in arms.values()}
        if len(signatures) > 1:
            findings.append(
                {
                    "code": "arms_not_matched",
                    "detail": "agent arms declare different models, settings or context boundaries",
                }
            )
    elif kinds == {"scripted"}:
        result["solver_kind"] = "scripted_development_ablation"
    else:
        result["solver_kind"] = "mixed"
        findings.append(
            {
                "code": "arms_not_matched",
                "detail": "scripted and agent arms cannot be compared as equals",
            }
        )

    by_key: dict[tuple[str, str], dict] = {}
    for trial in trials:
        key = (trial["arm"], trial["case_id"])
        if key in by_key:
            findings.append(
                {
                    "code": "trial_duplicated",
                    "detail": f"arm {key[0]!r} has more than one trial for case {key[1]!r}",
                    "arm": key[0],
                    "case_id": key[1],
                }
            )
            continue
        by_key[key] = trial
    for arm_id in arms:
        for case_id in cases:
            if (arm_id, case_id) not in by_key:
                findings.append(
                    {
                        "code": "trial_missing",
                        "detail": f"arm {arm_id!r} has no trial for case {case_id!r}; counted as not attempted with unknown cost",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
                by_key[(arm_id, case_id)] = {
                    "arm": arm_id,
                    "case_id": case_id,
                    "status": "not_attempted",
                    "declared_status": "not_attempted",
                    "received_frozen_sha256": None,
                    "decision": None,
                    "arm_claimed_acceptance": None,
                    "proposals": [],
                    "diagnostic_rollouts": 0,
                    "confirmation_rollouts": 0,
                    "retries": 0,
                    "timeline": None,
                    "costs": {},
                    "synthesized": True,
                }

    units: dict[str, str] = {}
    for (arm_id, case_id), trial in by_key.items():
        if arm_id not in arms or case_id not in cases:
            continue
        case = cases[case_id]
        if trial.get("received_frozen_sha256") is not None and not _digest_matches(
            trial["received_frozen_sha256"], case["frozen"]
        ):
            findings.append(
                {
                    "code": "frozen_inputs_differ",
                    "detail": f"arm {arm_id!r} received different frozen inputs for {case_id!r}",
                    "arm": arm_id,
                    "case_id": case_id,
                }
            )
        budget = case["budget"]
        duration = None
        if trial.get("timeline"):
            duration = (trial["timeline"][1] - trial["timeline"][0]).total_seconds()
        over = (
            budget["max_rollouts"] is not None
            and trial["diagnostic_rollouts"] > budget["max_rollouts"]
        ) or (
            budget["max_wall_seconds"] is not None
            and duration is not None
            and duration > budget["max_wall_seconds"]
        )
        if over:
            findings.append(
                {
                    "code": "budget_exceeded",
                    "detail": f"arm {arm_id!r} exceeded the budget on {case_id!r}; counted as timeout",
                    "arm": arm_id,
                    "case_id": case_id,
                }
            )
            trial["status"] = "timeout"
        for name, reference in trial.get("records", {}).items():
            problem = _verify_record(reference, root)
            if problem is not None:
                findings.append(
                    {
                        "code": "trial_record_unverifiable",
                        "detail": f"arm {arm_id!r} binds its {name} record for {case_id!r} to bytes "
                        f"that cannot be verified: {problem}",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
        verification = _verify_decision(trial, root, arm_id)
        trial["decision_verification"] = verification["how"]
        decision, candidate = verification["decision"], verification["candidate"]
        proposed = candidate is not None and any(
            _same_digest(p.get("candidate_digest"), candidate) for p in trial["proposals"]
        )
        bound = True
        if verification["verified"]:
            problem = _binding_problem(trial, root, verification)
            if problem is not None:
                bound = False
                # A confirmation rides on the binding; an unresolved or rejected trial's
                # decision is reported unbound without blocking the comparison.
                claims = trial["declared_status"] == "confirmed" or (
                    trial.get("arm_claimed_acceptance") is True
                )
                findings.append(
                    {
                        "code": "decision_not_bound_to_trial"
                        if claims
                        else "decision_binding_unverified",
                        "detail": f"arm {arm_id!r}: the decision named for {case_id!r} is not bound "
                        f"to the execution the trial names: {problem}",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
            elif not trial.get("records") and trial["declared_status"] == "confirmed":
                findings.append(
                    {
                        "code": "trial_names_no_execution_record",
                        "detail": f"arm {arm_id!r} confirms {case_id!r} without naming a "
                        "confirmation or diagnosis record; the decision cannot be bound to "
                        "an execution",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
        supported = verification["verified"] and decision == "accepted" and proposed and bound
        if trial["decision"] is not None and not verification["verified"]:
            findings.append(
                {
                    "code": "decision_unverifiable",
                    "detail": f"arm {arm_id!r} names a decision record for {case_id!r} that cannot "
                    f"be verified: {verification['how']}",
                    "arm": arm_id,
                    "case_id": case_id,
                }
            )
        if verification.get("misdeclared"):
            findings.append(
                {
                    "code": "decision_misdeclared",
                    "detail": f"arm {arm_id!r} misreports the decision on {case_id!r}: "
                    f"{verification['misdeclared']}",
                    "arm": arm_id,
                    "case_id": case_id,
                }
            )
        if trial["declared_status"] == "confirmed" and not supported:
            if not verification["verified"]:
                why = verification["how"]
            elif decision != "accepted":
                why = f"the verified record says {decision!r}"
            elif candidate is None:
                why = "the verified record names no confirmed candidate"
            elif not proposed:
                why = f"the record's candidate {candidate[:19]!r} is not among the arm's proposals"
            else:
                why = "the decision is not bound to this trial's execution"
            findings.append(
                {
                    "code": "confirmation_unsupported",
                    "detail": f"arm {arm_id!r} reports {case_id!r} confirmed; {why}; counted as a "
                    "false acceptance",
                    "arm": arm_id,
                    "case_id": case_id,
                }
            )
            trial["status"] = "unresolved"
            trial["false_acceptance"] = True
        if trial.get("arm_claimed_acceptance") is True and decision != "accepted":
            findings.append(
                {
                    "code": "false_acceptance",
                    "detail": f"arm {arm_id!r} claimed acceptance on {case_id!r}; the shared decision says {decision!r}",
                    "arm": arm_id,
                    "case_id": case_id,
                }
            )
            trial["false_acceptance"] = True
        if case["intended_class"] == "invalid" and "confirmed" in (
            trial["status"],
            trial["declared_status"],
        ):
            findings.append(
                {
                    "code": "invalid_case_confirmed",
                    "detail": f"arm {arm_id!r} confirmed the invalid-experiment control {case_id!r}",
                    "arm": arm_id,
                    "case_id": case_id,
                }
            )
        for name, quantity in trial["costs"].items():
            if name in units and units[name] != quantity.unit:
                findings.append(
                    {
                        "code": "cost_unit_conflict",
                        "detail": f"cost {name!r} is reported in {units[name]!r} and {quantity.unit!r}",
                    }
                )
            units.setdefault(name, quantity.unit)

    for arm_id in arms:
        arm_trials = [t for (a, c), t in by_key.items() if a == arm_id and c in cases]
        counts = {status: 0 for status in sorted(STATUSES)}
        by_family: dict[str, int] = {}
        false_acceptances = 0
        rejected_before = executed = diagnostic = confirmation_rollouts = retries = 0
        costs: dict[str, dict] = {}
        starts: list[datetime] = []
        ends: list[datetime] = []
        full_starts: list[datetime] = []
        full_ends: list[datetime] = []
        scopes: list[str] = []
        times_to_correction: list[float] = []
        for trial in arm_trials:
            counts[trial["status"]] += 1
            if trial.get("false_acceptance"):
                false_acceptances += 1
            if trial["status"] == "confirmed":
                family = str(cases[trial["case_id"]]["family"])
                by_family[family] = by_family.get(family, 0) + 1
            rejected_before += sum(1 for p in trial["proposals"] if p["rejected_before_execution"])
            executed += sum(1 for p in trial["proposals"] if p["executed"])
            diagnostic += trial["diagnostic_rollouts"]
            confirmation_rollouts += trial["confirmation_rollouts"]
            retries += trial["retries"]
            if trial.get("timeline"):
                starts.append(trial["timeline"][0])
                ends.append(trial["timeline"][1])
            full = trial.get("full_trial_timeline") or trial.get("timeline")
            if full:
                full_starts.append(full[0])
                full_ends.append(full[1])
                scopes.append("full_trial" if trial.get("full_trial_timeline") else "diagnostic")
            if (
                trial["status"] == "confirmed"
                and trial.get("time_to_confirmed_correction_s") is not None
            ):
                times_to_correction.append(trial["time_to_confirmed_correction_s"])
            for name, quantity in trial["costs"].items():
                item = costs.setdefault(
                    name,
                    {
                        "unit": quantity.unit,
                        "known_total": 0.0,
                        "known_trials": 0,
                        "missing_trials": 0,
                    },
                )
                if quantity.value is None:
                    item["missing_trials"] += 1
                else:
                    item["known_total"] = round(item["known_total"] + quantity.value, 9)
                    item["known_trials"] += 1
        reported = {name for trial in arm_trials for name in trial["costs"]}
        for name in reported:
            costs[name]["unreported_trials"] = (
                len(arm_trials) - costs[name]["known_trials"] - costs[name]["missing_trials"]
            )
        confirmed = counts["confirmed"]
        per_confirmed = {}
        for name, item in costs.items():
            if confirmed == 0:
                per_confirmed[name] = {
                    "value": None,
                    "unit": item["unit"],
                    "missing": "no confirmed correction",
                }
            elif item["known_trials"] == 0:
                per_confirmed[name] = {
                    "value": None,
                    "unit": item["unit"],
                    "missing": "not measured in any trial",
                }
            elif item["missing_trials"] or item.get("unreported_trials"):
                per_confirmed[name] = {
                    "value": round(item["known_total"] / confirmed, 9),
                    "unit": item["unit"],
                    "note": "known part only; some trials did not report this component",
                }
            else:
                per_confirmed[name] = {
                    "value": round(item["known_total"] / confirmed, 9),
                    "unit": item["unit"],
                }
        simulator = costs.get("simulator_wall")
        result["arms"][arm_id] = {
            **arms[arm_id],
            "assigned_cases": len(arm_trials),
            "outcomes": counts,
            "confirmed_by_family": by_family,
            "false_acceptances": false_acceptances,
            "invalid_proposals_rejected_before_execution": rejected_before,
            "executed_proposals": executed,
            "diagnostic_rollouts": diagnostic,
            "confirmation_rollouts": confirmation_rollouts,
            "rollouts": diagnostic + confirmation_rollouts,
            "retries": retries,
            "costs": costs,
            "known_cost_per_confirmed_correction": per_confirmed,
            "cumulative_simulator_wall_s": simulator["known_total"] if simulator else None,
            "diagnostic_elapsed_wall_s": round((max(ends) - min(starts)).total_seconds(), 6)
            if starts
            else None,
            "elapsed_wall_s": round((max(full_ends) - min(full_starts)).total_seconds(), 6)
            if full_starts
            else None,
            "elapsed_wall_scope": (
                None
                if not scopes
                else "full_trial"
                if all(s == "full_trial" for s in scopes)
                else "diagnostic_only"
                if all(s == "diagnostic" for s in scopes)
                else "mixed"
            ),
            "time_to_confirmed_correction_s": {
                "known_total": round(sum(times_to_correction), 6),
                "confirmed_trials_with_time": len(times_to_correction),
                "mean": round(sum(times_to_correction) / len(times_to_correction), 6),
            }
            if times_to_correction
            else None,
            "trials_with_timeline": len(starts),
        }
    result["cases"] = {
        case_id: {
            "family": case["family"],
            "intended_class": case["intended_class"],
            "outcomes": {arm_id: by_key[(arm_id, case_id)]["status"] for arm_id in arms},
        }
        for case_id, case in cases.items()
    }
    # Each arm pays for its own confirmation; two arms naming the same decision bytes
    # would let one arm count a confirmation it did not run.
    by_record: dict[tuple[str, str], list[str]] = {}
    for (arm_id, case_id), trial in by_key.items():
        decision = trial.get("decision")
        if isinstance(decision, dict) and isinstance(decision.get("path"), str):
            by_record.setdefault((case_id, "path " + decision["path"]), []).append(arm_id)
            if isinstance(decision.get("sha256"), str):
                digest = decision["sha256"].removeprefix("sha256:").lower()
                by_record.setdefault((case_id, "bytes " + digest), []).append(arm_id)
    for (case_id, record), arm_ids in sorted(by_record.items()):
        if len(set(arm_ids)) > 1:
            findings.append(
                {
                    "code": "decision_shared_between_arms",
                    "detail": f"arms {sorted(set(arm_ids))} name the same decision record "
                    f"({record[:25]}) for {case_id!r}; a confirmation belongs to the arm that ran it",
                    "case_id": case_id,
                }
            )
    if ledger.get("execution_complete") is False:
        findings.append(
            {
                "code": "execution_incomplete",
                "detail": "the ledger declares its execution incomplete; assigned trials that are "
                "absent count as not attempted with unknown cost, and no arm total is final",
            }
        )
    result["fair"] = not any(f["code"] in BLOCKING for f in findings)
    return result


def score_file(path: Path, root: Path | None = None) -> dict:
    """Score a ledger file; decision paths resolve against the ledger's directory by default."""
    path = Path(path)
    return score_comparison(load_json(path), path.parent if root is None else root)


def render_score(score: dict) -> str:
    lines = [
        f"Comparison score: {'fair' if score['fair'] else 'NOT FAIR'} · solver {score['solver_kind']}"
        + (f" · suite {score['suite']['id']}" if score.get("suite") else ""),
    ]
    if score["findings"]:
        lines.append("Findings:")
        for finding in score["findings"]:
            lines.append(f"  - {finding['code']}: {finding['detail']}")
    if score["arms"]:
        lines.append("Arms:")
        header = (
            f"  {'arm':<5}{'kind':<10}{'valid':<7}{'sel':<10}{'cases':<7}{'conf':<6}{'rej':<5}"
            f"{'unres':<7}{'inv':<5}{'unsup':<7}{'tout':<6}{'n/a':<5}{'false':<7}{'rej<exec':<10}{'rollouts':<10}sim wall"
        )
        lines.append(header)
        for arm_id, arm in score["arms"].items():
            o = arm["outcomes"]
            lines.append(
                f"  {arm_id:<5}{arm['kind']:<10}{str(arm['validity_layer']):<7}{arm['selection']:<10}"
                f"{arm['assigned_cases']:<7}{o['confirmed']:<6}{o['rejected']:<5}{o['unresolved']:<7}"
                f"{o['invalid']:<5}{o['unsupported']:<7}{o['timeout']:<6}{o['not_attempted']:<5}"
                f"{arm['false_acceptances']:<7}{arm['invalid_proposals_rejected_before_execution']:<10}"
                f"{arm['rollouts']:<10}{arm['cumulative_simulator_wall_s']}"
            )
        lines.append("Elapsed wall:")
        for arm_id, arm in score["arms"].items():
            lines.append(
                f"  {arm_id} diagnostic {arm['diagnostic_elapsed_wall_s']} s · "
                f"{arm['elapsed_wall_scope'] or 'no timeline'} {arm['elapsed_wall_s']} s · "
                f"time to confirmed correction {arm['time_to_confirmed_correction_s']}"
            )
        lines.append("Known cost per confirmed correction:")
        for arm_id, arm in score["arms"].items():
            for name, item in arm["known_cost_per_confirmed_correction"].items():
                value = (
                    item["value"]
                    if item["value"] is not None
                    else f"undefined ({item.get('missing')})"
                )
                lines.append(
                    f"  {arm_id} {name}: {value} {item['unit']}"
                    + (f" ({item['note']})" if item.get("note") else "")
                )
    if score["cases"]:
        lines.append("Cases:")
        for case_id, case in score["cases"].items():
            lines.append(
                f"  {case_id:<28}{str(case['intended_class']):<36}"
                + "  ".join(f"{a}={s}" for a, s in case["outcomes"].items())
            )
    lines.append("Limits:")
    for limit in score["limits"]:
        lines.append(f"  - {limit}")
    return "\n".join(lines)


__all__ = [
    "LEDGER_SCHEMA",
    "SCORE_SCHEMA",
    "Quantity",
    "render_score",
    "score_comparison",
    "score_file",
]
