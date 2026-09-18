"""The two lanes' readings of the same records agree.

The execution lane's ordinary diagnostic checks (task, progress, timing of the reference
and regression runs in its committed qualification results) and the evaluator's retained
run readings for the same records must not disagree. A disagreement is a finding for one
lane or the other, never silently absorbed.

Consumed conditions are reconciled per declared frozen suite, not against one global
total: every seed a suite assigns is spent; every seed a retained decision observed is
accounted for; the execution lane's index marks as observed exactly what retained
decisions observed; unexecuted assignments stay distinguishable from observations; the
index's evidence bytes match the committed files; and no seed is assigned twice.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "docs/evaluation/results/audit-2026-09-18"
RESULTS = REPO / "docs/experiments/results"
LEDGER = REPO / "work/development/consumed-conditions.json"
QUALIFICATION = REPO / "docs/evaluation/results/native-v4-qualification-001/summary.json"
POLICY = "3ee222cab41f78ba27afca7ef6f70f9f21bd3cc0a37bd79c0b2351dbede51605"
OBSERVED = "observed_development"
ASSIGNED = "assigned_development_all_spent_including_unused"
SOURCES = {
    "development-boundary-002": "development-boundary-002-",
    "development-baseline-qualification-001": "development-baseline-",
}
TIMING = {"met": "satisfied", "violated": "violated", "unmeasured": "unmeasured"}


def load(path: Path) -> dict:
    if path.with_suffix(path.suffix + ".gz").is_file():
        with gzip.open(path.with_suffix(path.suffix + ".gz"), "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def seeds_of(conditions) -> set[int]:
    found: set[int] = set()
    for condition in conditions:
        for seed in re.findall(r"seed-(\d+)", str(condition)):
            found.add(int(seed))
    return found


@pytest.mark.skipif(
    not all(
        (RESULTS / s / "qualification-results.json").exists()
        or (RESULTS / s / "qualification-results.json.gz").exists()
        for s in SOURCES
    ),
    reason="qualification results absent",
)
def test_ordinary_diagnostic_checks_agree_with_the_retained_readings():
    compared = 0
    differences = []
    for source, prefix in SOURCES.items():
        results = load(RESULTS / source / "qualification-results.json")
        for diagnosis in results["results"]:
            case_id = diagnosis["case_id"]
            retained = AUDIT / f"{prefix}{case_id.split('-')[0]}.decision.json"
            if not retained.is_file():
                continue
            runs = json.loads(retained.read_text())["runs"]
            selection = diagnosis.get("selection") or {}
            for role, run_id in (("reference", "reference-0"), ("regression", "regression-0")):
                theirs, mine = selection.get(role) or {}, runs.get(run_id)
                if not theirs or mine is None:
                    continue
                for name, their_value, my_value in (
                    ("task", theirs.get("task"), mine["outcome"]["observed"]),
                    ("progress", theirs.get("progress"), mine["progress"]),
                    ("timing", TIMING.get(theirs.get("timing")), mine["timing"]),
                ):
                    if their_value is None:
                        continue
                    compared += 1
                    if their_value != my_value:
                        differences.append((case_id, run_id, name, their_value, my_value))
    assert compared >= 60, compared
    assert differences == []


def retained_observations() -> tuple[set[int], dict[str, set[int]]]:
    """Seeds every retained decision observed, and the fresh seeds of each confirmation."""
    observed: set[int] = set()
    confirmations: dict[str, set[int]] = {}
    for path in sorted(AUDIT.glob("*.decision.json")):
        decision = json.loads(path.read_text())
        policy = (decision.get("task") or {}).get("policy_sha256")
        if policy not in (None, POLICY):
            continue
        conditions = {r.get("condition_id") for r in (decision.get("runs") or {}).values()}
        confirmation = decision.get("confirmation") or {}
        fresh = set(confirmation.get("fresh_condition_ids") or [])
        conditions |= fresh | set(confirmation.get("reproduction_condition_ids") or [])
        observed |= seeds_of(conditions)
        if fresh:
            confirmations[path.name] = seeds_of(fresh)
    return observed, confirmations


def declared_suites() -> dict[str, dict[str, set[int]]]:
    """Every committed frozen suite: its assigned confirmation seeds per case."""
    suites: dict[str, dict[str, set[int]]] = {}
    for path in sorted(RESULTS.glob("*/frozen-suite.json")):
        suite = json.loads(path.read_text())
        suites[path.parent.name] = {
            case_id: {int(seed) for seed in seeds}
            for case_id, seeds in (suite.get("condition_seeds") or {}).items()
        }
    return suites


@pytest.mark.skipif(not LEDGER.is_file(), reason="consumed-conditions ledger absent")
def test_consumed_seeds_reconcile_per_declared_suite():
    mine, confirmations = retained_observations()
    entries = [
        entry
        for entry in json.loads(LEDGER.read_text())["entries"]
        if str(entry.get("namespace", "")).endswith(POLICY)
    ]
    theirs: dict[str, set[int]] = {}
    for entry in entries:
        theirs.setdefault(str(entry.get("status")), set()).update(
            int(seed) for seed in entry.get("seeds", [])
        )
    observed, assigned = theirs.get(OBSERVED, set()), theirs.get(ASSIGNED, set())
    everything = set().union(*theirs.values()) if theirs else set()
    assert mine and observed
    # The index's evidence bytes are the committed files, whatever their status.
    for entry in entries:
        evidence = entry.get("evidence") or {}
        target = REPO / str(evidence.get("path"))
        assert target.is_file(), f"evidence missing: {evidence.get('path')}"
        assert hashlib.sha256(target.read_bytes()).hexdigest() == evidence.get("sha256"), (
            f"evidence bytes differ: {evidence.get('path')}"
        )
    # Every seed the execution lane marks observed is in a retained decision, and every
    # seed a retained decision observed is indexed, except this lane's own qualification
    # seeds while they await indexing.
    qualification: set[int] = set()
    if QUALIFICATION.is_file():
        qualification = set(json.loads(QUALIFICATION.read_text())["seeds"])
    assert observed <= mine, sorted(observed - mine)[:10]
    assert mine - everything <= qualification, sorted(mine - everything - qualification)[:10]
    # Per declared suite: no seed assigned twice; assigned seeds are spent in the index;
    # a case's seeds are either all observed by a retained confirmation or none are,
    # and the unobserved ones are not marked observed by the index.
    suites = declared_suites()
    assert suites, "no committed frozen suite"
    seen: dict[int, str] = {}
    unexecuted: set[int] = set()
    executed_cases = 0
    for suite_id, cases in suites.items():
        for case_id, seeds in cases.items():
            for seed in seeds:
                assert seed not in seen, f"seed {seed} assigned by {seen[seed]} and {suite_id}"
                seen[seed] = f"{suite_id}/{case_id}"
            assert seeds <= assigned, f"{suite_id}/{case_id}: assigned seeds not spent"
            if seeds <= mine:
                executed_cases += 1
                assert any(seeds == fresh for fresh in confirmations.values()), (
                    f"{suite_id}/{case_id}: observed seeds match no retained confirmation"
                )
            else:
                assert not (seeds & mine), f"{suite_id}/{case_id}: partially observed seeds"
                unexecuted |= seeds
    assert executed_cases >= 1
    assert not (unexecuted & observed), sorted(unexecuted & observed)[:10]
    assert assigned - mine == unexecuted, (
        sorted(assigned - mine - unexecuted)[:10],
        sorted(unexecuted - (assigned - mine))[:10],
    )
