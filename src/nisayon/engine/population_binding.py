"""Deterministic population-role and normalization-reference decisions.

Foreign files are parsed by experiment adapters. This module receives numeric
content and evidence identities, computes the relevant arithmetic, and keeps a
scoped reuse/recompute/abstain decision separate from process success.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

STATISTICS = ("mean", "std", "min", "max", "q01", "q99")
ROLES = {
    "current_population_summary",
    "parent_population_summary",
    "external_reference_normalizer",
    "unresolved",
}


class InvalidPopulation(ValueError):
    """A well-scoped numeric input is malformed or unsafe to aggregate."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _number(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidPopulation("malformed_numeric_value", f"{where} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise InvalidPopulation("non_finite_value", f"{where} is not finite")
    return result


def _vector(value: object, *, where: str, width: int | None = None) -> list[float]:
    if not isinstance(value, list):
        raise InvalidPopulation("malformed_vector", f"{where} is not a list")
    if not value:
        raise InvalidPopulation("empty_coordinate_vector", f"{where} is empty")
    result = [_number(item, where=f"{where}[{index}]") for index, item in enumerate(value)]
    if width is not None and len(result) != width:
        raise InvalidPopulation(
            "wrong_coordinate_count", f"{where} has {len(result)} coordinates, expected {width}"
        )
    return result


def _quantile(sorted_values: list[float], probability: float) -> float:
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def calculate_statistics(rows: object) -> dict[str, Any]:
    """Compute population moments and linear quantiles with float64 accumulation."""

    if not isinstance(rows, list) or not rows:
        raise InvalidPopulation("empty_population", "population has no rows")
    first = _vector(rows[0], where="rows[0]")
    width = len(first)
    columns = [[value] for value in first]
    for row_index, raw in enumerate(rows[1:], 1):
        row = _vector(raw, where=f"rows[{row_index}]", width=width)
        for column, value in zip(columns, row, strict=True):
            column.append(value)
    means = [math.fsum(column) / len(column) for column in columns]
    variances = [
        math.fsum((value - mean) ** 2 for value in column) / len(column)
        for column, mean in zip(columns, means, strict=True)
    ]
    ordered = [sorted(column) for column in columns]
    return {
        "n": len(rows),
        "width": width,
        "mean": means,
        "std": [math.sqrt(max(0.0, value)) for value in variances],
        "min": [column[0] for column in ordered],
        "max": [column[-1] for column in ordered],
        "q01": [_quantile(column, 0.01) for column in ordered],
        "q99": [_quantile(column, 0.99) for column in ordered],
    }


def validate_statistics(value: object, *, width: int | None = None) -> dict[str, list[float]]:
    if not isinstance(value, dict):
        raise InvalidPopulation("malformed_statistics", "statistics are not an object")
    missing = [name for name in STATISTICS if name not in value]
    if missing:
        raise InvalidPopulation("missing_statistic", f"missing statistics: {', '.join(missing)}")
    result: dict[str, list[float]] = {}
    inferred = width
    for name in STATISTICS:
        result[name] = _vector(value[name], where=f"statistics.{name}", width=inferred)
        inferred = len(result[name])
    for index, std in enumerate(result["std"]):
        if std < 0:
            raise InvalidPopulation("negative_standard_deviation", f"statistics.std[{index}] < 0")
    return result


def compare_statistics(
    published: object,
    computed: object,
    *,
    rtol: float = 1e-5,
    atol: float = 1e-6,
) -> dict[str, Any]:
    computed_stats = validate_statistics(computed)
    width = len(computed_stats["mean"])
    published_stats = validate_statistics(published, width=width)
    by_statistic: dict[str, Any] = {}
    all_match = True
    for name in STATISTICS:
        differences = [
            abs(left - right)
            for left, right in zip(published_stats[name], computed_stats[name], strict=True)
        ]
        matches = [
            math.isclose(left, right, rel_tol=rtol, abs_tol=atol)
            for left, right in zip(published_stats[name], computed_stats[name], strict=True)
        ]
        all_match = all_match and all(matches)
        by_statistic[name] = {
            "all_coordinates_match": all(matches),
            "differing_coordinates": [index for index, match in enumerate(matches) if not match],
            "max_abs_difference": max(differences, default=0.0),
        }
    return {
        "all_statistics_match": all_match,
        "rtol": rtol,
        "atol": atol,
        "by_statistic": by_statistic,
    }


def pool_episode_statistics(episodes: object, feature: str) -> dict[str, Any]:
    """Pool per-episode population moments without treating episodes as trials."""

    if not isinstance(episodes, list) or not episodes:
        raise InvalidPopulation("empty_parent_population", "parent enumeration has no episodes")
    parsed = []
    width = None
    for expected_index, episode in enumerate(episodes):
        if not isinstance(episode, dict) or episode.get("episode_index") != expected_index:
            raise InvalidPopulation(
                "invalid_episode_order", f"expected parent episode {expected_index}"
            )
        stats_by_feature = episode.get("stats")
        if not isinstance(stats_by_feature, dict) or feature not in stats_by_feature:
            raise InvalidPopulation("missing_feature", f"episode {expected_index} lacks {feature}")
        raw = stats_by_feature[feature]
        if not isinstance(raw, dict):
            raise InvalidPopulation(
                "malformed_statistics", f"episode {expected_index} is malformed"
            )
        count = raw.get("count")
        if (
            not isinstance(count, list)
            or len(count) != 1
            or isinstance(count[0], bool)
            or not isinstance(count[0], int)
            or count[0] <= 0
        ):
            raise InvalidPopulation("invalid_episode_count", f"episode {expected_index} count")
        episode_stats = {
            name: _vector(
                raw.get(name),
                where=f"episodes[{expected_index}].{feature}.{name}",
                width=width,
            )
            for name in ("mean", "std", "min", "max")
        }
        width = len(episode_stats["mean"])
        if any(value < 0 for value in episode_stats["std"]):
            raise InvalidPopulation(
                "negative_standard_deviation", f"episode {expected_index} std < 0"
            )
        parsed.append((count[0], episode_stats))
    total = sum(count for count, _ in parsed)
    means = [
        math.fsum(count * stats["mean"][index] for count, stats in parsed) / total
        for index in range(width or 0)
    ]
    second_moments = [
        math.fsum(
            count * (stats["std"][index] ** 2 + stats["mean"][index] ** 2)
            for count, stats in parsed
        )
        / total
        for index in range(width or 0)
    ]
    return {
        "episodes": len(parsed),
        "frames": total,
        "width": width,
        "mean": means,
        "std": [
            math.sqrt(max(0.0, second - mean**2))
            for second, mean in zip(second_moments, means, strict=True)
        ],
        "min": [min(stats["min"][index] for _, stats in parsed) for index in range(width or 0)],
        "max": [max(stats["max"][index] for _, stats in parsed) for index in range(width or 0)],
    }


def analyze_parent_population(
    *,
    published: dict[str, object],
    episodes: object,
    subset_observations: object,
    subset_members: int,
    mean_rtol: float = 1e-4,
    std_rtol: float = 1e-3,
) -> dict[str, Any]:
    if not isinstance(subset_members, int) or subset_members <= 0:
        raise InvalidPopulation("invalid_subset_membership", "subset member count must be positive")
    if not isinstance(episodes, list) or not episodes:
        raise InvalidPopulation("empty_parent_population", "parent enumeration has no episodes")
    if not isinstance(subset_observations, list) or len(subset_observations) != subset_members:
        raise InvalidPopulation(
            "incomplete_subset_verification", "subset verification does not cover every member"
        )
    features = ("observation.state", "action")
    subset_matches = True
    for expected_index, observation in enumerate(subset_observations):
        if not isinstance(observation, dict) or observation.get("episode_index") != expected_index:
            raise InvalidPopulation(
                "invalid_subset_order", f"expected subset episode {expected_index}"
            )
        differences = observation.get("max_abs_difference")
        if not isinstance(differences, dict):
            raise InvalidPopulation("malformed_subset_verification", "missing differences")
        for feature in features:
            if not isinstance(differences.get(feature), dict):
                raise InvalidPopulation("missing_feature", f"subset lacks {feature}")
            values = differences[feature]
            for name in ("min", "max", "mean", "std"):
                subset_matches = (
                    subset_matches
                    and _number(
                        values.get(name), where=f"subset[{expected_index}].{feature}.{name}"
                    )
                    == 0.0
                )
            count = values.get("count")
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise InvalidPopulation("invalid_episode_count", "subset observation count")
            parent_count = episodes[expected_index]["stats"][feature].get("count")
            if parent_count != [count]:
                subset_matches = False

    by_feature = {}
    parent_episodes = None
    parent_frames = None
    all_extremes = True
    all_moments = True
    for feature in features:
        if feature not in published:
            raise InvalidPopulation("missing_feature", f"published statistics lack {feature}")
        pooled = pool_episode_statistics(episodes, feature)
        parent_episodes = pooled["episodes"]
        parent_frames = pooled["frames"]
        published_stats = validate_statistics(published[feature], width=pooled["width"])
        min_exact = published_stats["min"] == pooled["min"]
        max_exact = published_stats["max"] == pooled["max"]
        mean_matches = [
            math.isclose(left, right, rel_tol=mean_rtol, abs_tol=0.0)
            for left, right in zip(published_stats["mean"], pooled["mean"], strict=True)
        ]
        std_matches = [
            math.isclose(left, right, rel_tol=std_rtol, abs_tol=0.0)
            for left, right in zip(published_stats["std"], pooled["std"], strict=True)
        ]
        all_extremes = all_extremes and min_exact and max_exact
        all_moments = all_moments and all(mean_matches) and all(std_matches)
        by_feature[feature] = {
            "episodes": pooled["episodes"],
            "frames": pooled["frames"],
            "min_exact_equal_all": min_exact,
            "max_exact_equal_all": max_exact,
            "mean_all_within_tolerance": all(mean_matches),
            "std_all_within_tolerance": all(std_matches),
            "mean_max_abs_difference": max(
                abs(left - right)
                for left, right in zip(published_stats["mean"], pooled["mean"], strict=True)
            ),
            "std_max_abs_difference": max(
                abs(left - right)
                for left, right in zip(published_stats["std"], pooled["std"], strict=True)
            ),
            "quantiles": "not_comparable_without_raw_parent_rows",
        }
    strict_superset = bool(parent_episodes and parent_episodes > subset_members)
    supported = strict_superset and subset_matches and all_extremes and all_moments
    return {
        "status": "supported" if supported else "rejected",
        "parent_episodes": parent_episodes,
        "parent_frames": parent_frames,
        "subset_members": subset_members,
        "strict_superset": strict_superset,
        "subset_statistics_match": subset_matches,
        "extremes_exact": all_extremes,
        "moments_within_tolerance": all_moments,
        "mean_rtol": mean_rtol,
        "std_rtol": std_rtol,
        "by_feature": by_feature,
    }


def _selection_supported(selection: object, published_identity: str) -> bool:
    if not isinstance(selection, dict):
        return False
    return (
        selection.get("kind") == "observed_invocation"
        and selection.get("observed") is True
        and selection.get("selected_statistics_sha256") == published_identity
        and _text_evidence_supported(selection.get("evidence"))
    )


def _text_evidence_supported(evidence: object) -> bool:
    """Require exact retained text, its digest and meaningful content markers."""

    if not isinstance(evidence, dict):
        return False
    source_text = evidence.get("source_text")
    source_sha256 = evidence.get("source_sha256")
    required_markers = evidence.get("required_markers")
    if (
        not isinstance(source_text, str)
        or not isinstance(source_sha256, str)
        or not isinstance(required_markers, list)
        or not required_markers
        or not all(isinstance(marker, str) and marker for marker in required_markers)
    ):
        return False
    if hashlib.sha256(source_text.encode()).hexdigest() != source_sha256:
        return False
    return all(marker in source_text for marker in required_markers)


def _normalization_interpretation_supported(interpretation: object) -> bool:
    if not isinstance(interpretation, dict) or interpretation.get("status") != "supported":
        return False
    formula = interpretation.get("formula")
    constant_behavior = interpretation.get("constant_coordinate_behavior")
    if not isinstance(formula, str) or not formula or not isinstance(constant_behavior, str):
        return False
    if "epsilon" not in interpretation:
        return False
    evidence = interpretation.get("evidence")
    return _text_evidence_supported(evidence) and formula in evidence["source_text"]


def _analyze_external_reference(
    published_by_feature: dict[str, object], external: object
) -> dict[str, Any]:
    """Check a constructed or retained reference population from its numeric rows."""

    if not isinstance(external, dict):
        return {"status": "unresolved", "reason": "external reference evidence is absent"}
    rows_by_feature = external.get("reference_rows")
    if not isinstance(rows_by_feature, dict) or set(rows_by_feature) != set(published_by_feature):
        return {
            "status": "unresolved",
            "reason": "external reference rows do not cover every published feature",
        }
    comparisons = {}
    computed = {}
    for feature in published_by_feature:
        stats = calculate_statistics(rows_by_feature[feature])
        computed[feature] = stats
        comparisons[feature] = compare_statistics(published_by_feature[feature], stats)
    supported = all(row["all_statistics_match"] for row in comparisons.values())
    return {
        "status": "supported" if supported else "rejected",
        "reason": (
            "published statistics reproduce the retained external reference rows"
            if supported
            else "published statistics differ from the retained external reference rows"
        ),
        "computed": computed,
        "comparisons": comparisons,
    }


def _invalid_result(case_id: object, label: object, error: InvalidPopulation) -> dict[str, Any]:
    return {
        "schema": "nisayon.population-binding-decision.v1",
        "case_id": case_id,
        "label": label,
        "role": "unresolved",
        "obligations": {
            "role_binding": "invalid",
            "population_binding": "invalid",
            "selection_binding": "invalid",
            "arithmetic": "invalid",
            "normalization_interpretation": "invalid",
        },
        "decision": {
            "selected_operation": "invalid",
            "status": "invalid",
            "reason": error.code,
            "detail": error.detail,
            "candidate_results": [],
            "missing": [],
        },
    }


def decide_population_binding(case: object) -> dict[str, Any]:
    """Compute a scoped operation from contents and evidence, never a role label alone."""

    case_id = case.get("id") if isinstance(case, dict) else None
    label = case.get("label") if isinstance(case, dict) else None
    try:
        if not isinstance(case, dict):
            raise InvalidPopulation("malformed_case", "case is not an object")
        role = case.get("role_obligation")
        if role not in ROLES:
            raise InvalidPopulation("unsupported_role", f"unsupported role: {role!r}")
        published_by_feature = case.get("published_statistics")
        if not isinstance(published_by_feature, dict) or not published_by_feature:
            raise InvalidPopulation("missing_statistics", "published statistics are missing")
        for feature, statistics in published_by_feature.items():
            if not isinstance(feature, str) or not feature:
                raise InvalidPopulation("undeclared_feature", "feature name is invalid")
            validate_statistics(statistics)
        published_identity = _canonical_digest(published_by_feature)
        declared_identity = case.get("published_statistics_sha256")
        if declared_identity is not None and declared_identity != published_identity:
            raise InvalidPopulation("statistics_identity_mismatch", "statistics digest differs")

        selection_supported = _selection_supported(case.get("selection"), published_identity)
        interpretation = case.get("normalization_interpretation")
        interpretation_supported = _normalization_interpretation_supported(interpretation)
        current_analysis = None
        parent_analysis = None
        external_analysis = None
        role_status = "unresolved"
        population_status = "unresolved"
        arithmetic_status = "unresolved"

        if role == "current_population_summary":
            role_evidence = case.get("role_evidence")
            if not isinstance(role_evidence, dict) or not role_evidence.get("current_obligation"):
                role = "unresolved"
            else:
                rows_by_feature = case.get("current_rows")
                if not isinstance(rows_by_feature, dict) or set(rows_by_feature) != set(
                    published_by_feature
                ):
                    raise InvalidPopulation(
                        "incomplete_current_population", "current rows do not cover every feature"
                    )
                comparisons = {}
                computed = {}
                for feature in published_by_feature:
                    stats = calculate_statistics(rows_by_feature[feature])
                    computed[feature] = stats
                    comparisons[feature] = compare_statistics(published_by_feature[feature], stats)
                matches = all(row["all_statistics_match"] for row in comparisons.values())
                current_analysis = {
                    "computed": computed,
                    "comparisons": comparisons,
                    "all_statistics_match": matches,
                }
                role_status = "supported"
                population_status = "supported"
                arithmetic_status = "supported" if matches else "rejected"

        elif role == "parent_population_summary":
            parent_analysis = analyze_parent_population(
                published=published_by_feature,
                episodes=case.get("parent_episode_statistics"),
                subset_observations=case.get("subset_observations"),
                subset_members=case.get("subset_members"),
            )
            role_status = parent_analysis["status"]
            population_status = parent_analysis["status"]
            arithmetic_status = parent_analysis["status"]

        elif role == "external_reference_normalizer":
            external_analysis = _analyze_external_reference(
                published_by_feature, case.get("external_reference")
            )
            if external_analysis["status"] == "supported":
                role_status = "supported"
                population_status = "supported"
                arithmetic_status = "supported"
            else:
                role = "unresolved"

        missing = []
        candidate_results = []
        if role == "current_population_summary" and role_status == "supported":
            if current_analysis and current_analysis["all_statistics_match"]:
                operation = "reuse"
                status = "supported"
                candidate_results = [
                    {"operation": "reuse", "status": "supported"},
                    {"operation": "recompute", "status": "rejected"},
                ]
            else:
                operation = "recompute"
                status = "rejected"
                candidate_results = [
                    {"operation": "reuse", "status": "rejected"},
                    {"operation": "recompute", "status": "supported"},
                ]
        elif role == "parent_population_summary" and role_status == "supported":
            operation = "reuse" if selection_supported else "abstain"
            status = "supported" if selection_supported else "unresolved"
            candidate_results = [
                {"operation": "reuse", "status": status},
                {
                    "operation": "recompute",
                    "status": "rejected",
                    "reason": "would replace a bound parent summary with subset moments",
                },
            ]
            if not selection_supported:
                missing.append("observed selection of the parent statistics")
        elif role == "external_reference_normalizer" and role_status == "supported":
            if selection_supported and interpretation_supported:
                operation, status = "reuse", "supported"
            else:
                operation, status = "abstain", "unresolved"
                if not selection_supported:
                    missing.append("observed external-reference selection")
                if not interpretation_supported:
                    missing.append("supported normalization interpretation")
            candidate_results = [
                {"operation": "reuse", "status": status},
                {
                    "operation": "recompute",
                    "status": "rejected",
                    "reason": "evaluation-subset mismatch is not an external-reference premise",
                },
            ]
        else:
            role = "unresolved"
            operation, status = "abstain", "unresolved"
            missing.extend(case.get("missing_evidence", []))
            if external_analysis is not None and external_analysis["status"] != "supported":
                missing.append(external_analysis["reason"])
            if not missing:
                missing.append("supported population role and selection evidence")
            candidate_results = [
                {"operation": "reuse", "status": "unresolved"},
                {"operation": "recompute", "status": "unresolved"},
            ]

        return {
            "schema": "nisayon.population-binding-decision.v1",
            "case_id": case_id,
            "label": label,
            "label_used_as_premise": False,
            "published_statistics_sha256": published_identity,
            "role": role,
            "observations": {
                "current_population": current_analysis,
                "parent_population": parent_analysis,
                "external_reference": external_analysis,
                "selection_supported": selection_supported,
                "normalization_interpretation_supported": interpretation_supported,
            },
            "obligations": {
                "role_binding": role_status,
                "population_binding": population_status,
                "selection_binding": "supported" if selection_supported else "unresolved",
                "arithmetic": arithmetic_status,
                "normalization_interpretation": (
                    "supported" if interpretation_supported else "unresolved"
                ),
            },
            "decision": {
                "selected_operation": operation,
                "status": status,
                "candidate_results": candidate_results,
                "missing": missing,
            },
        }
    except InvalidPopulation as error:
        return _invalid_result(case_id, label, error)
