"""Selection, incomplete references and exact finite-population inference controls."""

import copy
from collections import Counter
from fractions import Fraction
from itertools import combinations, product

import pytest

from nisayon.engine.io import digest
from nisayon.qualification import (
    assess_monitoring_audit,
    freeze_monitoring_audit,
    monitoring_audit_panel,
    summarize_monitoring,
)
from nisayon.qualification.monitoring_audit import (
    BINDINGS,
    DECISIONS,
    _failure_interval,
    _metrics,
)


def inputs(populations=(4, 4, 4, 4), sizes=(2, 2, 2, 2)):
    rows = []
    for decision, count in zip(DECISIONS, populations, strict=True):
        for _ in range(count):
            i = len(rows)
            rows.append(
                {
                    "episode_id": f"e{i:04}",
                    "task_id": "task",
                    "session_id": "one-session",
                    "execution_sha256": digest(["execution", i]),
                    "judge_input_sha256": digest(["frames", i]),
                    "decision": decision,
                }
            )
    return {
        "frame": rows,
        "bindings": {k: digest(k) for k in BINDINGS},
        "sample_sizes": dict(zip(DECISIONS, sizes, strict=True)),
    }


@pytest.fixture
def plan(tmp_path, monkeypatch):
    monkeypatch.setattr("nisayon.qualification.monitoring_audit.secrets.randbelow", lambda n: 0)
    return freeze_monitoring_audit(**inputs(), output=tmp_path / "plan.json")


def labels(plan, outcome="success"):
    return [
        {
            "audit_sha256": plan["sha256"],
            "episode_id": r["episode_id"],
            "outcome": outcome,
            "reference_sha256": digest([r["episode_id"], outcome]),
        }
        for r in plan["selected"]
    ]


def test_panel_omits_predictions_and_keeps_exact_episode_references(plan):
    panel = monitoring_audit_panel(plan)
    assert panel["audit_sha256"] == plan["sha256"]
    assert len(panel["episodes"]) == 8
    for row in panel["episodes"]:
        assert set(row) == {
            "episode_id",
            "task_id",
            "session_id",
            "execution_sha256",
            "judge_input_sha256",
        }
    assert {r["inclusion_probability"]["value"] for r in plan["selected"]} == {0.5}


def test_complete_sample_keeps_four_decision_strata_and_unknown_deployment(plan):
    report = assess_monitoring_audit(plan, labels(plan))
    assert report["status"] == "finite_frame_estimate"
    assert report["coverage"] == {
        "frame": 16,
        "assigned": 8,
        "returned": 8,
        "binary_adjudicated": 8,
        "unclear": 0,
        "unmeasured": 0,
        "invalid": 0,
    }
    assert report["deployment_decision"] == "unresolved"
    assert report["point_estimates"]["valid_success_retention"] == 0.25
    assert report["simultaneous_intervals"]["accepted_failures_per_episode"]["upper"] > 0
    assert report["strata"]["abstained"]["population"] == 4
    assert report["strata"]["unanswered"]["population"] == 4


@pytest.mark.parametrize("kind", ["missing", "unclear", "unmeasured"])
def test_incomplete_adjudication_widens_instead_of_imputing(plan, kind):
    full = labels(plan)
    baseline = assess_monitoring_audit(plan, full)
    if kind == "missing":
        full.pop(0)
    else:
        full[0]["outcome"] = kind
    report = assess_monitoring_audit(plan, full)
    assert report["status"] == "incomplete_adjudication"
    assert report["coverage"]["binary_adjudicated"] == 7
    assert report["point_estimates"] is None
    for key, bounds in baseline["simultaneous_intervals"].items():
        actual = report["simultaneous_intervals"][key]
        if bounds["lower"] is not None:
            assert actual["lower"] <= bounds["lower"]
            assert actual["upper"] >= bounds["upper"]


def test_no_labels_yields_full_uncertainty(plan):
    report = assess_monitoring_audit(plan, [])
    assert report["coverage"]["unmeasured"] == 8
    assert report["point_estimates"] is None
    interval = report["simultaneous_intervals"]["success_fraction"]
    assert (interval["lower"], interval["upper"], interval["denominator"]) == (0.0, 1.0, 16)


def test_invalid_reference_blocks_population_inference(plan):
    rows = labels(plan)
    rows[0]["outcome"] = "invalid"
    rows[0]["reference_sha256"] = None
    report = assess_monitoring_audit(plan, rows)
    assert report["status"] == "invalid_reference"
    assert report["simultaneous_intervals"] is None
    assert report["point_estimates"] is None
    assert report["coverage"]["invalid"] == 1


@pytest.mark.parametrize(
    "change",
    [
        "population_sha256",
        "policy_sha256",
        "runtime_sha256",
        "evaluator_sha256",
        "input_protocol_sha256",
        "reference_protocol_sha256",
        "frame",
        "draw",
        "selected",
        "confidence",
        "schema",
        "unit",
    ],
)
def test_changed_plan_cannot_inherit_adjudications(plan, change):
    original = labels(plan)
    if change in BINDINGS:
        plan["bindings"][change] = digest("changed")
    elif change == "frame":
        plan["frame"][0]["execution_sha256"] = digest("changed")
    elif change == "draw":
        plan["draws"]["accepted"][0] = 1
    elif change == "selected":
        plan["selected"][0]["inclusion_probability"]["value"] = True
    elif change == "confidence":
        plan["confidence"] = 0.99
    elif change == "schema":
        plan["schema"] = "unknown"
    else:
        plan["sampling_unit"] = "frame"
    with pytest.raises(ValueError):
        assess_monitoring_audit(plan, original)


def test_rehashed_new_design_still_refuses_old_adjudications(plan):
    original = labels(plan)
    plan["bindings"]["policy_sha256"] = digest("another policy")
    plan["sha256"] = digest({k: v for k, v in plan.items() if k != "sha256"})
    with pytest.raises(ValueError, match="different audit"):
        assess_monitoring_audit(plan, original)


@pytest.mark.parametrize(
    "change", ["duplicate", "unassigned", "unknown", "missing_reference", "extra", "wrong_audit"]
)
def test_bad_adjudications_are_refused(plan, change):
    rows = labels(plan)
    if change == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif change == "unassigned":
        rows[0]["episode_id"] = "e0003"
    elif change == "unknown":
        rows[0]["outcome"] = "probably fine"
    elif change == "missing_reference":
        rows[0]["reference_sha256"] = None
    elif change == "extra":
        rows[0]["judge_prediction"] = "accepted"
    else:
        rows[0]["audit_sha256"] = digest("stale attempt")
    with pytest.raises(ValueError):
        assess_monitoring_audit(plan, rows)


@pytest.mark.parametrize(
    "change",
    [
        "reject_only",
        "empty_stratum_sample",
        "duplicate_episode",
        "duplicate_execution",
        "boolean_size",
        "oversample",
        "prelabelled",
        "unknown_decision",
        "bad_binding",
        "nan",
        "boolean_confidence",
        "empty",
        "too_large",
    ],
)
def test_bad_designs_fail_before_creating_a_plan(tmp_path, change):
    value = inputs()
    if change == "reject_only":
        value["sample_sizes"]["accepted"] = 0
    elif change == "empty_stratum_sample":
        value = inputs((4, 4, 0, 0), (2, 2, 1, 0))
    elif change == "duplicate_episode":
        value["frame"][1]["episode_id"] = value["frame"][0]["episode_id"]
    elif change == "duplicate_execution":
        value["frame"][1]["execution_sha256"] = value["frame"][0]["execution_sha256"]
    elif change == "boolean_size":
        value["sample_sizes"]["accepted"] = True
    elif change == "oversample":
        value["sample_sizes"]["accepted"] = 5
    elif change == "prelabelled":
        value["frame"][0]["outcome"] = "success"
    elif change == "unknown_decision":
        value["frame"][0]["decision"] = "missing"
    elif change == "bad_binding":
        value["bindings"]["policy_sha256"] = None
    elif change == "nan":
        value["confidence"] = float("nan")
    elif change == "boolean_confidence":
        value["confidence"] = True
    elif change == "empty":
        value["frame"] = []
    else:
        value["frame"] *= 257
    out = tmp_path / "plan.json"
    with pytest.raises(ValueError):
        freeze_monitoring_audit(**value, output=out)
    assert not out.exists()


def test_plan_is_create_only_without_consuming_randomness(plan, tmp_path, monkeypatch):
    def fail(_):
        pytest.fail("Must refuse an existing plan before drawing again")

    monkeypatch.setattr("nisayon.qualification.monitoring_audit.secrets.randbelow", fail)
    with pytest.raises(FileExistsError):
        freeze_monitoring_audit(**inputs(), output=tmp_path / "plan.json")


@pytest.mark.parametrize("bad", [-1, 4, True, 0.5])
def test_malformed_draws_are_rejected_even_with_updated_digest(plan, bad):
    plan["draws"]["accepted"][0] = bad
    plan["sha256"] = digest({k: v for k, v in plan.items() if k != "sha256"})
    with pytest.raises(ValueError):
        monitoring_audit_panel(plan)


def test_sampling_is_uniform_over_all_small_draw_paths(tmp_path, monkeypatch):
    observed = Counter()
    # 4 choices followed by 3 choices: every 2-element subset occurs twice.
    for first, second in product(range(4), range(3)):
        stream = iter((first, second))
        monkeypatch.setattr(
            "nisayon.qualification.monitoring_audit.secrets.randbelow",
            lambda n, stream=stream: next(stream),
        )
        p = freeze_monitoring_audit(
            **inputs((4, 0, 0, 0), (2, 0, 0, 0)), output=tmp_path / f"{first}-{second}.json"
        )
        observed[tuple(sorted(row["episode_id"] for row in p["selected"]))] += 1
    assert len(observed) == 6
    assert set(observed.values()) == {2}


def test_weighting_does_not_treat_disproportionate_audit_as_a_census(tmp_path, monkeypatch):
    monkeypatch.setattr("nisayon.qualification.monitoring_audit.secrets.randbelow", lambda n: 0)
    p = freeze_monitoring_audit(**inputs((8, 2, 0, 0), (2, 2, 0, 0)), output=tmp_path / "plan.json")
    rows = labels(p, "failure")
    rows[1]["outcome"] = "success"
    report = assess_monitoring_audit(p, rows)
    metrics = report["point_estimates"]
    assert metrics["accepted_failures_per_episode"] == 0.4
    assert metrics["accepted_failures_per_episode"] != 1 / 4
    assert metrics["success_fraction"] == 0.4
    assert report["strata"]["accepted"]["estimated_failure_total"]["value"] == 4


def test_reject_all_loses_valid_successes_even_with_no_false_acceptance(tmp_path):
    p = freeze_monitoring_audit(**inputs((0, 4, 0, 0), (0, 4, 0, 0)), output=tmp_path / "plan.json")
    report = assess_monitoring_audit(p, labels(p))
    bounds = report["simultaneous_intervals"]
    assert bounds["accepted_failures_per_episode"]["upper"] == 0
    assert bounds["valid_success_retention"]["upper"] == 0
    assert bounds["accepted_set_error"]["upper"] is None
    assert bounds["accepted_failures_per_failure"]["can_be_undefined"]
    assert report["deployment_decision"] == "unresolved"


@pytest.mark.parametrize("alpha", [Fraction(1, 2), Fraction(1, 10), Fraction(1, 20)])
def test_exact_tail_inversion_and_coverage_by_enumerating_finite_samples(alpha):
    for N in range(1, 9):
        for n in range(1, N + 1):
            samples = list(combinations(range(N), n))
            distributions = {
                K: Counter(sum(i < K for i in s) for s in samples) for K in range(N + 1)
            }
            intervals = {k: _failure_interval(N, n, k, alpha / 2) for k in range(n + 1)}
            for k, actual in intervals.items():
                allowed = [
                    K
                    for K, dist in distributions.items()
                    if Fraction(sum(v for x, v in dist.items() if x <= k), len(samples))
                    >= alpha / 2
                    and Fraction(sum(v for x, v in dist.items() if x >= k), len(samples))
                    >= alpha / 2
                ]
                assert actual == (min(allowed), max(allowed))
            for K, dist in distributions.items():
                covered = sum(
                    count for k, count in dist.items() if intervals[k][0] <= K <= intervals[k][1]
                )
                assert Fraction(covered, len(samples)) >= 1 - alpha


def test_metric_rectangle_extrema_against_every_compatible_count_vector():
    populations = dict(zip(DECISIONS, (2, 2, 1, 1), strict=True))
    options = [
        [(a, b) for a in range(N + 1) for b in range(a, N + 1)] for N in populations.values()
    ]
    for chosen in product(*options):
        interval = dict(zip(DECISIONS, chosen, strict=True))
        bounds = _metrics(populations, interval)
        cases = []
        for counts in product(*(range(a, b + 1) for a, b in chosen)):
            F, A, N, fa = sum(counts), 2, 6, counts[0]
            cases.append(
                {
                    "success_fraction": (N - F) / N,
                    "accepted_failures_per_episode": fa / N,
                    "accepted_failures_per_failure": fa / F if F else None,
                    "valid_success_retention": (A - fa) / (N - F) if N != F else None,
                    "accepted_set_error": fa / A,
                }
            )
        for metric, actual in bounds.items():
            values = [c[metric] for c in cases if c[metric] is not None]
            assert actual["lower"] == (min(values) if values else None)
            assert actual["upper"] == (max(values) if values else None)
            if "can_be_undefined" in actual:
                assert actual["can_be_undefined"] == any(c[metric] is None for c in cases)


def test_exact_rational_endpoints_remain_available_beside_decimal_display():
    intervals = {"accepted": (1, 1), "rejected": (0, 0), "abstained": (0, 0), "unanswered": (0, 0)}
    populations = {"accepted": 10, "rejected": 0, "abstained": 0, "unanswered": 0}
    bounds = _metrics(populations, intervals)["accepted_set_error"]
    for key in ("lower_exact", "upper_exact"):
        assert Fraction(bounds[key]["numerator"], bounds[key]["denominator"]) == Fraction(1, 10)


def test_discrete_tail_equality_is_retained_conservatively():
    # At K=4, seeing no failures in 5 of 10 has probability 6/252 = 1/42.
    assert _failure_interval(10, 5, 0, Fraction(1, 42)) == (0, 4)
    assert _failure_interval(10, 5, 0, Fraction(1, 40)) == (0, 3)
    assert _failure_interval(10, 5, 5, Fraction(1, 42)) == (6, 10)
    assert _failure_interval(10, 5, 5, Fraction(1, 40)) == (7, 10)


def test_full_census_agrees_with_existing_descriptive_monitoring(tmp_path):
    p = freeze_monitoring_audit(**inputs((4, 4, 0, 0), (4, 4, 0, 0)), output=tmp_path / "plan.json")
    outcomes = {
        row["episode_id"]: "failure" if i % 3 == 0 else "success"
        for i, row in enumerate(p["frame"])
    }
    supplied = labels(p)
    for row in supplied:
        row["outcome"] = outcomes[row["episode_id"]]
    audit = assess_monitoring_audit(p, supplied)
    old = summarize_monitoring(
        [
            {
                "episode_id": r["episode_id"],
                "task_id": r["task_id"],
                "policy_id": "fixed",
                "session_id": r["session_id"],
                "outcome": outcomes[r["episode_id"]],
                "score": 1 if r["decision"] == "accepted" else 0,
            }
            for r in p["frame"]
        ],
        evaluator_id="fixture",
        reference_id="authored",
        input_protocol="fixed",
    )
    mapping = {
        "success_fraction": "reference_success",
        "accepted_failures_per_episode": "confirmed_misses_per_episode",
        "accepted_failures_per_failure": "conditional_miss",
        "valid_success_retention": "valid_success_retention",
        "accepted_set_error": "labelled_acceptance_error",
    }
    for key, prior in mapping.items():
        assert audit["point_estimates"][key] == old["rates"][prior]["value"]
        bounds = audit["simultaneous_intervals"][key]
        assert bounds["lower"] == bounds["upper"] == old["rates"][prior]["value"]


def test_joint_coverage_across_strata_by_enumerating_all_samples():
    alpha = Fraction(1, 2)
    samples = list(combinations(range(5), 3))
    intervals = {k: _failure_interval(5, 3, k, alpha / 4) for k in range(4)}
    for a, b in product(range(6), repeat=2):
        covered = 0
        for first, second in product(samples, repeat=2):
            ia = intervals[sum(i < a for i in first)]
            ib = intervals[sum(i < b for i in second)]
            covered += ia[0] <= a <= ia[1] and ib[0] <= b <= ib[1]
        assert Fraction(covered, len(samples) ** 2) >= 1 - alpha


def test_unknown_reference_union_contains_every_binary_completion():
    for N in range(1, 9):
        for n in range(1, N + 1):
            intervals = {k: _failure_interval(N, n, k, Fraction(1, 40)) for k in range(n + 1)}
            for known_failures in range(n + 1):
                for missing in range(n - known_failures + 1):
                    union = (intervals[known_failures][0], intervals[known_failures + missing][1])
                    for k in range(known_failures, known_failures + missing + 1):
                        assert union[0] <= intervals[k][0] <= intervals[k][1] <= union[1]
