"""Confirmation-feasibility prototype: exact enumeration of decision procedures; no physics.

One command takes the frozen specification and emits a machine-readable result stating,
for each procedure and scenario, which objective it answers, the assumptions it needs,
the exact accept, reject and defer probabilities, the expected cost with both members
of every pair charged, and the identity of the inputs and algorithms behind the numbers.
Every fixed-rate procedure is enumerated exactly on the (n, k_plus, k_minus) lattice;
nothing is simulated with random numbers.

Usage: feasibility.py --spec spec.json --out DIR [--real-records docs/experiments/results]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
import time
from functools import cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "nisayon.confirmation-feasibility.result.v1"
ALGORITHM_VERSION = "feasibility.py 2026-09-19 exact-lattice-1"
REPRODUCTION_RUNS = 3  # reference, regression and candidate reruns on the registered failure
CONDITIONS = 32


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- exact binomial machinery -------------------------------------------------------------


@cache
def binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, k + 1))


def cp_upper(k: int, n: int, beta: float) -> float:
    """Smallest p with P(Bin(n, p) <= k) <= beta: one-sided Clopper-Pearson upper bound."""
    if k >= n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > beta:
            lo = mid
        else:
            hi = mid
    return hi


def cp_lower(k: int, n: int, beta: float) -> float:
    """Largest p with P(Bin(n, p) >= k) <= beta: one-sided Clopper-Pearson lower bound."""
    if k <= 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if 1 - binom_cdf(k - 1, n, mid) > beta:
            hi = mid
        else:
            lo = mid
    return lo


def zero_event_requirement(q: float, alpha: float) -> int:
    """Smallest n such that (1 - q)^n <= alpha: the pairs any valid level-alpha test needs
    before it may accept on an all-concordant record."""
    return math.ceil(math.log(alpha) / math.log(1 - q))


# --- lattice enumeration -------------------------------------------------------------------


def enumerate_lattice(p_plus: float, p_minus: float, n_max: int, decide) -> dict:
    """Exact accept/reject/defer probabilities and expected pairs for a rule whose decision
    at step n depends only on (n, k_plus, k_minus). ``decide(n, kp, km)`` returns
    'accept', 'reject' or None (continue). At n_max an undecided path is 'defer'."""
    p_zero = 1 - p_plus - p_minus
    assert p_zero >= -1e-12
    live = {(0, 0): 1.0}
    accept = reject = expected_pairs = 0.0
    for n in range(1, n_max + 1):
        nxt: dict[tuple[int, int], float] = {}
        for (kp, km), mass in live.items():
            for dkp, dkm, prob in ((1, 0, p_plus), (0, 1, p_minus), (0, 0, p_zero)):
                if prob <= 0:
                    continue
                key = (kp + dkp, km + dkm)
                nxt[key] = nxt.get(key, 0.0) + mass * prob
        live = {}
        for (kp, km), mass in nxt.items():
            outcome = decide(n, kp, km)
            if outcome == "accept":
                accept += mass
                expected_pairs += mass * n
            elif outcome == "reject":
                reject += mass
                expected_pairs += mass * n
            else:
                live[(kp, km)] = mass
    defer = sum(live.values())
    expected_pairs += defer * n_max
    return {
        "accept": accept,
        "reject": reject,
        "defer": defer,
        "expected_pairs": expected_pairs,
        "expected_runs": REPRODUCTION_RUNS + 2 * expected_pairs,
    }


# --- procedures ----------------------------------------------------------------------------


def finite_conjunction(n: int, stop_on_violation: bool):
    def decide(step, kp, km):
        if km > 0 and stop_on_violation:
            return "reject"
        if step == n:
            return "reject" if km > 0 else "accept"
        return None

    return decide


def fixed_cp_o1(n: int, q: float, alpha: float):
    def decide(step, kp, km):
        if step < n:
            return None
        if cp_upper(km, n, alpha) < q:
            return "accept"
        if cp_lower(km, n, alpha) > q:
            return "reject"
        return "defer"

    return decide


def fixed_paired_binomial_o2(n: int, epsilon: float, alpha: float, m: int = 1):
    beta = alpha / (4 * m)

    def decide(step, kp, km):
        if step < n:
            return None
        lower = cp_lower(kp, n, beta) - cp_upper(km, n, beta)
        upper = cp_upper(kp, n, beta) - cp_lower(km, n, beta)
        if lower >= -epsilon:
            return "accept"
        if upper < -epsilon:
            return "reject"
        return "defer"

    return decide


def sprt_o1(q: float, alpha: float):
    threshold = zero_event_requirement(q, alpha)

    def decide(step, kp, km):
        if km > 0:
            return "reject"
        if step >= threshold:
            return "accept"
        return None

    return decide


def betting_o2(epsilon: float, alpha: float, xi: float, xi_reject: float | None = None):
    """Evidence integrator M_n = prod(1 + xi (x_i + epsilon)) for H0: g <= -epsilon, and a
    mirror M'_n = prod(1 - xi' (x_i + epsilon)) for H0': g >= -epsilon. Fixed predictable
    rates; both are nonnegative supermartingales under their nulls. The first to reach
    1/alpha decides. This is the form of N-SCORE's equation 3 with a margin shift, not
    N-SCORE's optimized rate and not its code."""
    assert xi * (1 - epsilon) <= 1 + 1e-12
    xi_r = xi if xi_reject is None else xi_reject
    assert xi_r * (1 + epsilon) <= 1 + 1e-12
    up, zero, down = 1 + xi * (1 + epsilon), 1 + xi * epsilon, 1 - xi * (1 - epsilon)
    up_r, zero_r, down_r = 1 - xi_r * (1 + epsilon), 1 - xi_r * epsilon, 1 + xi_r * (1 - epsilon)

    def decide(step, kp, km):
        k0 = step - kp - km
        m_accept = up**kp * zero**k0 * down**km
        m_reject = up_r**kp * zero_r**k0 * down_r**km
        if m_accept >= 1 / alpha:
            return "accept"
        if m_reject >= 1 / alpha:
            return "reject"
        return None

    return decide


def peeking_cp_o1(q: float, alpha: float):
    def decide(step, kp, km):
        if cp_upper(km, step, alpha) < q:
            return "accept"
        return None

    return decide


# --- scenarios -----------------------------------------------------------------------------


def scenario_parameters(scenario: dict) -> tuple[float, float]:
    if "groups" in scenario:
        p_plus = sum(g["share"] * g["p_plus"] for g in scenario["groups"])
        p_minus = sum(g["share"] * g["p_minus"] for g in scenario["groups"])
        return p_plus, p_minus
    return scenario["p_plus"], scenario["p_minus"]


def run_grid(spec: dict) -> list[dict]:
    alpha = spec["error_allocation"]["alpha_per_candidate_decision"]
    rows = []
    for scenario in spec["scenario_grid"]["scenarios"]:
        p_plus, p_minus = scenario_parameters(scenario)
        missing = scenario.get("missing_pairs", 0)
        procedures = []
        for n_max in spec["stopping_rules"]["n_max_grid"]:
            n = n_max
            procedures.append(("F0_finite_conjunction", {"n": n}, finite_conjunction(n, False), n))
            procedures.append(
                (
                    "F0_finite_conjunction_stop_on_violation",
                    {"n": n},
                    finite_conjunction(n, True),
                    n,
                )
            )
            for q in spec["proposed_contracts_under_study"]["O1_harmful_disagreement_bound"][
                "q_grid"
            ]:
                procedures.append(
                    ("F1_fixed_exact_binomial_O1", {"n": n, "q": q}, fixed_cp_o1(n, q, alpha), n)
                )
                procedures.append(
                    ("S1_sequential_sprt_O1", {"n_max": n, "q": q}, sprt_o1(q, alpha), n)
                )
                procedures.append(
                    ("P1_peeking_fixed_interval", {"n_max": n, "q": q}, peeking_cp_o1(q, alpha), n)
                )
            for eps in spec["proposed_contracts_under_study"]["O2_non_inferiority_of_success"][
                "epsilon_grid"
            ]:
                procedures.append(
                    (
                        "F2_fixed_paired_binomial_O2",
                        {"n": n, "epsilon": eps},
                        fixed_paired_binomial_o2(n, eps, alpha),
                        n,
                    )
                )
                for xi in (0.25, 0.5, 0.75):
                    procedures.append(
                        (
                            "S2_sequential_betting_O2",
                            {"n_max": n, "epsilon": eps, "xi": xi},
                            betting_o2(eps, alpha, xi, min(xi, 1 / (1 + eps))),
                            n,
                        )
                    )
            for xi in (0.25, 0.5, 0.75):
                procedures.append(
                    (
                        "S3_sequential_betting_O3_superiority",
                        {"n_max": n, "xi": xi},
                        betting_o2(0.0, alpha, xi, xi),
                        n,
                    )
                )
        for name, params, decide, n_max in procedures:
            if missing:
                result = {
                    "accept": 0.0,
                    "reject": 0.0,
                    "defer": 1.0,
                    "expected_pairs": float(n_max - missing),
                    "expected_runs": REPRODUCTION_RUNS + 2 * (n_max - missing),
                    "state": "invalid" if name.startswith("F0") else "defer",
                    "note": "missing required evidence: the finite obligation names the gap (assigned_outcome_missing); statistical rules defer; no rule accepts on a shortened denominator",
                }
            else:
                result = enumerate_lattice(p_plus, p_minus, n_max, decide)
            rows.append(
                {
                    "scenario": scenario["id"],
                    "p_plus": p_plus,
                    "p_minus": p_minus,
                    "procedure": name,
                    "parameters": params,
                    **{k: (round(v, 9) if isinstance(v, float) else v) for k, v in result.items()},
                }
            )
        if "groups" in scenario:
            # Protected-group requirement: the smaller group at its expected pair count.
            for g in scenario["groups"]:
                for n_max in spec["stopping_rules"]["n_max_grid"]:
                    n_g = max(1, round(n_max * g["share"]))
                    for q in spec["proposed_contracts_under_study"][
                        "O1_harmful_disagreement_bound"
                    ]["q_grid"]:
                        result = enumerate_lattice(
                            g["p_plus"], g["p_minus"], n_g, fixed_cp_o1(n_g, q, alpha)
                        )
                        rows.append(
                            {
                                "scenario": scenario["id"] + f"/group_share_{g['share']}",
                                "p_plus": g["p_plus"],
                                "p_minus": g["p_minus"],
                                "procedure": "F1_fixed_exact_binomial_O1_per_group",
                                "parameters": {
                                    "n_group": n_g,
                                    "q": q,
                                    "split": "fixed at the expected share; not enumerated over random splits",
                                },
                                **{
                                    k: (round(v, 9) if isinstance(v, float) else v)
                                    for k, v in result.items()
                                },
                            }
                        )
    return rows


# --- analytic feasibility --------------------------------------------------------------------


def analytic(spec: dict) -> dict:
    alpha = spec["error_allocation"]["alpha_per_candidate_decision"]
    o1 = {}
    for q in spec["proposed_contracts_under_study"]["O1_harmful_disagreement_bound"]["q_grid"]:
        n_star = zero_event_requirement(q, alpha)
        o1[str(q)] = {
            "pairs_required_even_with_all_concordant_outcomes": n_star,
            "runs_required": REPRODUCTION_RUNS + 2 * n_star,
            "fits_in_32_pairs": n_star <= 32,
            "fits_in_67_runs": REPRODUCTION_RUNS + 2 * n_star <= 67,
        }
    o2 = {}
    beta = alpha / 4
    for eps in spec["proposed_contracts_under_study"]["O2_non_inferiority_of_success"][
        "epsilon_grid"
    ]:
        n_star = math.ceil(math.log(beta) / math.log(1 - eps))
        o2[str(eps)] = {
            "pairs_required_with_zero_disagreements_paired_binomial": n_star,
            "runs_required": REPRODUCTION_RUNS + 2 * n_star,
            "fits_in_67_runs": REPRODUCTION_RUNS + 2 * n_star <= 67,
            "source": "arXiv:2609.10873v1, rule-specific feasibility n >= log(beta)/log(1-epsilon) with beta = alpha/(4m)",
        }
    certified_by_32 = 1 - alpha ** (1 / CONDITIONS)
    return {
        "lower_bound_for_any_valid_test": {
            "statement": "Let T be any test of H0: p_minus >= q with erroneous-acceptance probability at most alpha, fixed-sample or sequential. If T accepts on the all-concordant record of length n, then under p_minus = q that record occurs with probability (1-q)^n and leads to acceptance, so alpha >= (1-q)^n, i.e. n >= log(alpha)/log(1-q). Acceptance with fewer pairs is impossible for every valid rule, whatever it does on other records.",
            "scope": "the all-concordant record is the most favourable evidence for acceptance; this bounds acceptance cost, not rejection cost; it is a standard likelihood argument, not a new result",
            "equality": "the fixed one-sided Clopper-Pearson rule and the point-alternative SPRT both accept at exactly this n on the all-concordant record, so neither can be improved for acceptance on the best path",
        },
        "O1_harmful_disagreement_bound": o1,
        "O2_non_inferiority": o2,
        "what_32_concordant_pairs_certify": {
            "one_sided_upper_bound_on_p_minus_at_1_minus_alpha": round(certified_by_32, 7),
            "reading": "under independent fresh draws with frozen candidate and reference, the existing 32-pair zero-regression outcome already implies p_minus <= 8.94% at 95%; the finite obligation itself claims nothing about unseen conditions",
        },
        "impossibility_within_the_current_budget": [
            f"q = 0.05 at alpha = {alpha}: {o1['0.05']['pairs_required_even_with_all_concordant_outcomes']} pairs = {o1['0.05']['runs_required']} runs > 67; not reachable with any valid rule under the current cap",
            "non-inferiority epsilon = 0.05 with the paired-binomial rule: 86 pairs = 175 runs > 67",
            "sequential rules cannot lower these acceptance costs; they lower rejection cost, which the finite obligation can also stop early once the record contract admits a cancellation status",
        ],
    }


# --- real records ---------------------------------------------------------------------------


def real_records(results_root: Path, spec: dict) -> dict:
    alpha = spec["error_allocation"]["alpha_per_candidate_decision"]
    root = results_root / "development-ablation-001"
    score_path = root / "comparison-score.json"
    expected = spec["real_record_check"]["selection"].split("digest ")[1].strip()
    if sha(score_path) != expected:
        raise SystemExit("the pinned development-ablation score digest differs")
    trials = []
    for case in (
        "D01-gripper-sign",
        "D02-cartesian-axis",
        "D03-observation-backlog",
        "D04-observation-hold",
        "D05-recurrent-carry",
        "D07-sign-and-backlog",
        "D09-action-suppression",
    ):
        for arm in ("A", "B"):
            folder = root / case / arm / "confirmation"
            if not (folder / "decision.json").is_file():
                continue
            decision = json.loads((folder / "decision.json").read_text())
            document = json.loads(gzip.open(folder / "execution" / "bundle.json.gz", "rt").read())
            started = {run["id"]: run["started_at"] for run in document["runs"]}
            pairs = [p for p in decision["confirmation"]["pairs"] if p["role"] != "reproduction"]
            ordered = sorted(pairs, key=lambda p: started.get(p["candidate_run_id"], ""))
            xs = []
            for p in ordered:
                ref, cand = (
                    p["reference_outcome"] == "completed",
                    p["candidate_outcome"] == "completed",
                )
                xs.append(1 if cand and not ref else -1 if ref and not cand else 0)
            n = len(xs)
            kp, km = xs.count(1), xs.count(-1)
            both_failed = sum(1 for p in ordered if p["verdict"] == "both_failed")
            entry = {
                "trial": f"{case}/{arm}",
                "finite_decision": decision["decision"],
                "finite_reasons": [r["code"] for r in decision["reasons"]],
                "fresh_pairs": n,
                "k_plus": kp,
                "k_minus": km,
                "both_failed": both_failed,
                "cp_upper_bound_on_p_minus": round(cp_upper(km, n, alpha), 7),
                "retrospective": {},
                "sequential_under_recorded_order": {},
            }
            for q in spec["proposed_contracts_under_study"]["O1_harmful_disagreement_bound"][
                "q_grid"
            ]:
                entry["retrospective"][f"F1_q_{q}"] = (
                    "accept"
                    if cp_upper(km, n, alpha) < q
                    else ("reject" if cp_lower(km, n, alpha) > q else "defer")
                )
                decide = sprt_o1(q, alpha)
                stop = next(
                    (
                        i + 1
                        for i in range(n)
                        if decide(i + 1, xs[: i + 1].count(1), xs[: i + 1].count(-1))
                    ),
                    None,
                )
                entry["sequential_under_recorded_order"][f"S1_q_{q}"] = {
                    "stops_at_pair": stop,
                    "decision": decide(stop, xs[:stop].count(1), xs[:stop].count(-1))
                    if stop
                    else "defer",
                    "runs_including_reproduction": REPRODUCTION_RUNS + 2 * (stop or n),
                }
            for eps in spec["proposed_contracts_under_study"]["O2_non_inferiority_of_success"][
                "epsilon_grid"
            ]:
                beta = alpha / 4
                lower = cp_lower(kp, n, beta) - cp_upper(km, n, beta)
                upper = cp_upper(kp, n, beta) - cp_lower(km, n, beta)
                entry["retrospective"][f"F2_epsilon_{eps}"] = {
                    "L": round(lower, 6),
                    "U": round(upper, 6),
                    "decision": "accept"
                    if lower >= -eps
                    else ("reject" if upper < -eps else "defer"),
                }
                for xi in (0.5, 0.75):
                    decide = betting_o2(eps, alpha, xi, min(xi, 1 / (1 + eps)))
                    stop = next(
                        (
                            i + 1
                            for i in range(n)
                            if decide(i + 1, xs[: i + 1].count(1), xs[: i + 1].count(-1))
                        ),
                        None,
                    )
                    entry["sequential_under_recorded_order"][f"S2_epsilon_{eps}_xi_{xi}"] = {
                        "stops_at_pair": stop,
                        "decision": decide(stop, xs[:stop].count(1), xs[:stop].count(-1))
                        if stop
                        else "defer",
                    }
            trials.append(entry)
    return {
        "source_digest": expected,
        "role": "applicability and retrospective calculation on already-exposed records; not fresh evidence, not independent incidents; the recorded order is one ordering and any permutation is descriptive",
        "trials": trials,
        "data_quality": "every trial carries 32 fresh pairs with valid measurements on both sides; both-failed pairs are concordant (X = 0) for the paired contracts and are retained as reference_failed_on_condition by the finite obligation",
    }


# --- assembly --------------------------------------------------------------------------------


EXPLORATORY_SCENARIOS = [
    {"id": "exploratory_harmful_at_boundary_q15", "p_plus": 0.0, "p_minus": 0.15},
    {"id": "exploratory_boundary_epsilon15_with_gains", "p_plus": 0.10, "p_minus": 0.25},
]
NULL_BOUNDARIES = {
    # scenario -> the rules for which it sits exactly on the null boundary
    "harmful_at_boundary_q05": {"O1": 0.05, "O2": 0.05},
    "harmful_at_boundary_q10": {"O1": 0.1, "O2": 0.1},
    "exploratory_harmful_at_boundary_q15": {"O1": 0.15, "O2": 0.15},
    "exploratory_boundary_epsilon15_with_gains": {"O2": 0.15},
}


def type1_summary(rows: list[dict]) -> list[dict]:
    """Erroneous-acceptance probability of every rule at the scenarios that sit exactly on
    its null boundary (p_minus = q for O1; p_minus - p_plus = epsilon for O2)."""
    out = []
    for row in rows:
        boundary = NULL_BOUNDARIES.get(row["scenario"])
        if not boundary:
            continue
        params = row["parameters"]
        if "q" in params and boundary.get("O1") == params["q"]:
            out.append(
                {
                    **{k: row[k] for k in ("scenario", "procedure", "parameters")},
                    "erroneous_acceptance": row["accept"],
                    "bound": 0.05,
                    "within_bound": row["accept"] <= 0.05 + 1e-12,
                }
            )
        if "epsilon" in params and boundary.get("O2") == params["epsilon"]:
            out.append(
                {
                    **{k: row[k] for k in ("scenario", "procedure", "parameters")},
                    "erroneous_acceptance": row["accept"],
                    "bound": 0.05,
                    "within_bound": row["accept"] <= 0.05 + 1e-12,
                }
            )
    return out


def wall_projection(results_root: Path | None) -> dict:
    """Per-run confirmation wall from the retained development comparison, arm A."""
    if results_root is None:
        return {"status": "no retained results root given"}
    score = json.loads(
        (results_root / "development-ablation-001" / "comparison-score.json").read_text()
    )
    arm = score["arms"]["A"]
    per_run = arm["costs"]["confirmation_wall"]["known_total"] / arm["confirmation_rollouts"]
    return {
        "per_run_confirmation_wall_s": round(per_run, 6),
        "source": "development-ablation-001 arm A: confirmation_wall / confirmation_rollouts",
        "67_runs_s": round(67 * per_run, 3),
        "status": "projection from retained per-run cost on this CPU stack; not measured end-to-end savings; excludes preparation, engineering effort, charges and energy",
    }


def qualification_matrix() -> dict:
    """Which procedure is qualified for which objective in this study; 'not_implemented'
    names the blocker that keeps a comparison-superiority conclusion open."""
    return {
        "objectives": {
            "O0": "finite conjunction (existing obligation)",
            "O1": "harmful-disagreement bound",
            "O2": "non-inferiority of paired success",
            "O3": "mean superiority",
        },
        "F0_finite_conjunction": {
            "O0": "qualified",
            "O1": "not_qualified: no population claim",
            "O2": "not_qualified",
            "O3": "not_qualified",
        },
        "F1_fixed_exact_binomial_O1": {
            "O0": "not_qualified: averages over conditions",
            "O1": "qualified",
            "O2": "not_qualified: ignores gains",
            "O3": "not_qualified",
        },
        "F2_fixed_paired_binomial_O2": {
            "O0": "not_qualified",
            "O1": "qualified with one tail (as F1)",
            "O2": "qualified",
            "O3": "not_qualified: margin rule, superiority needs q_0 = eta > 0 of the source paper",
        },
        "S1_sequential_sprt_O1": {
            "O0": "not_qualified",
            "O1": "qualified",
            "O2": "not_qualified",
            "O3": "not_qualified",
        },
        "S2_sequential_betting_O2": {
            "O0": "not_qualified",
            "O1": "not_qualified",
            "O2": "qualified (fixed predictable rate)",
            "O3": "qualified with epsilon = 0 (S3)",
        },
        "S3_sequential_betting_O3_superiority": {
            "O0": "not_qualified",
            "O1": "not_qualified",
            "O2": "not_qualified",
            "O3": "qualified on binary success; bounded progress not enumerated in this study",
        },
        "P1_peeking_fixed_interval": {
            "O0": "invalid",
            "O1": "invalid",
            "O2": "invalid",
            "O3": "invalid",
        },
        "STEP_faithful": {
            "O0": "not_qualified",
            "O1": "not_qualified",
            "O2": "not_qualified",
            "O3": "not_implemented: the method is the synthesized risk-budget policy for unpaired 2x2 tables; code is CC BY-NC 4.0 and was not imported; reimplementing the synthesis was outside this block",
        },
        "N_SCORE_optimized_rate": {
            "O0": "not_qualified",
            "O1": "not_qualified",
            "O2": "not_qualified: the paper states superiority only",
            "O3": "not_implemented: xi_n = g(F_n) optimization not reproduced; repository shows no license; S3 uses the equation-3 form with a fixed rate",
        },
    }


def repeated_attempts_control(rows: list[dict]) -> dict:
    """Changing the candidate during confirmation, or retrying a rejected one under the
    same alpha, is a second attempt: erroneous acceptance compounds unless each attempt
    has its own allocation."""
    boundary = next(
        r
        for r in rows
        if r["scenario"] == "exploratory_harmful_at_boundary_q15"
        and r["procedure"] == "S1_sequential_sprt_O1"
        and r["parameters"].get("q") == 0.15
        and r["parameters"].get("n_max") == 32
    )
    a = boundary["accept"]
    return {
        "single_attempt_erroneous_acceptance_at_boundary": round(a, 6),
        "two_attempts_same_alpha_best_of_two": round(1 - (1 - a) ** 2, 6),
        "three_attempts_same_alpha": round(1 - (1 - a) ** 3, 6),
        "bound": 0.05,
        "reading": "a frozen-candidate guarantee does not survive swapping the candidate or retrying under the same allocation; the source paper allocates alpha_t = 6 delta / (pi^2 t^2) per attempt so that the sum stays within delta",
    }


def procedure_catalogue() -> dict:
    return {
        "F0_finite_conjunction": {
            "objective": "the existing obligation: every declared condition and predicate",
            "answers": "whether the frozen candidate satisfied the declared finite conjunction",
            "cannot_answer": "any population claim",
            "assumptions": "none beyond valid measurements",
            "cost": "67 runs when accepted; early stop possible only with a cancellation status",
        },
        "F1_fixed_exact_binomial_O1": {
            "objective": "O1",
            "answers": "p_minus < q at level alpha after n pairs",
            "cannot_answer": "per-condition conjunction; non-inferiority of the mean",
            "assumptions": "independent fresh draws; frozen candidate, reference and scoring; within-pair dependence allowed",
            "validity": "exact binomial tail; no optional stopping",
        },
        "F2_fixed_paired_binomial_O2": {
            "objective": "O2",
            "answers": "g = p_plus - p_minus >= -epsilon at level alpha after n pairs",
            "cannot_answer": "a bound on p_minus alone; per-condition conjunction",
            "assumptions": "as F1; four tails at alpha/4 (arXiv:2609.10873v1 eq. 2)",
            "validity": "exact; fixed batch; no optional stopping",
        },
        "S1_sequential_sprt_O1": {
            "objective": "O1",
            "answers": "p_minus < q (accept) or a harmful disagreement observed (reject) at any stopping time",
            "cannot_answer": "non-inferiority; per-condition conjunction",
            "assumptions": "as F1 across pairs",
            "validity": "Wald likelihood ratio against the point alternative p_minus = 0; Ville's inequality; exactly valid under optional stopping",
        },
        "S2_sequential_betting_O2": {
            "objective": "O2",
            "answers": "g > -epsilon (accept) or g < -epsilon (reject) at any stopping time",
            "cannot_answer": "a bound on p_minus alone; per-condition conjunction",
            "assumptions": "as F1 across pairs; a fixed predictable rate",
            "validity": "nonnegative supermartingale under each null; Ville's inequality; the form of N-SCORE equation 3 with a margin, not its optimized rate nor its code",
        },
        "S3_sequential_betting_O3_superiority": {
            "objective": "O3",
            "answers": "E[S(candidate)] > E[S(reference)]",
            "cannot_answer": "non-inferiority, harmful-disagreement bounds, per-condition or per-group requirements",
            "assumptions": "as S2",
            "validity": "as S2 with epsilon = 0; on binary success only in this study",
        },
        "P1_peeking_fixed_interval": {
            "objective": "O1, invalidly",
            "answers": "nothing valid",
            "cannot_answer": "control of erroneous acceptance",
            "assumptions": "none hold",
            "validity": "invalid: a fixed-sample interval inspected after every pair",
        },
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--real-records", type=Path, default=None)
    args = parser.parse_args(argv[1:])
    started = time.perf_counter()
    spec = json.loads(args.spec.read_text())
    spec_digest = sha(args.spec)
    rows = run_grid(spec)
    exploratory_spec = {**spec, "scenario_grid": {"scenarios": EXPLORATORY_SCENARIOS}}
    exploratory_rows = run_grid(exploratory_spec)
    result = {
        "schema": SCHEMA,
        "study_id": spec["study_id"],
        "spec": {"path": str(args.spec), "sha256": spec_digest, "frozen_at": spec["frozen_at"]},
        "algorithm": ALGORITHM_VERSION,
        "script_sha256": sha(Path(__file__)),
        "computation": "exact lattice enumeration; no random trials; no physics; no model call",
        "procedures": procedure_catalogue(),
        "analytic_feasibility": analytic(spec),
        "grid_rows": rows,
        "exploratory_after_output": {
            "status": "added after the first output was inspected; the frozen grid lacked a scenario on the q = 0.15 and epsilon = 0.15 null boundaries, which are needed to read the error control of those rules and the inflation of the peeking comparator; the frozen grid above is unchanged",
            "scenarios": EXPLORATORY_SCENARIOS,
            "rows": exploratory_rows,
        },
        "type1_at_null_boundaries": type1_summary(rows + exploratory_rows),
        "qualification_matrix": qualification_matrix(),
        "repeated_attempts_control": repeated_attempts_control(exploratory_rows),
        "wall_projection": wall_projection(args.real_records),
    }
    if args.real_records:
        result["real_records"] = real_records(args.real_records, spec)
    result["cpu_seconds"] = round(time.perf_counter() - started, 3)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "feasibility.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result["analytic_feasibility"].items()
                if k in ("O1_harmful_disagreement_bound", "what_32_concordant_pairs_certify")
            },
            indent=1,
        )
    )
    print(f"grid rows: {len(rows)}; cpu {result['cpu_seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
