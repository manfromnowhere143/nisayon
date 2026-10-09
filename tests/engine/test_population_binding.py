import copy
import math

import pytest

from nisayon.engine.population_binding import (
    calculate_statistics,
    decide_population_binding,
    pool_episode_statistics,
)


def _stats(rows):
    return {
        key: value
        for key, value in calculate_statistics(rows).items()
        if key != "n" and key != "width"
    }


def _selection(statistics):
    import hashlib
    import json

    encoded = json.dumps(statistics, sort_keys=True, separators=(",", ":")).encode()
    evidence = "constructed observed invocation selected statistics\n"
    return {
        "kind": "observed_invocation",
        "observed": True,
        "selected_statistics_sha256": hashlib.sha256(encoded).hexdigest(),
        "evidence": {
            "source_text": evidence,
            "source_sha256": hashlib.sha256(evidence.encode()).hexdigest(),
            "required_markers": ["observed invocation", "selected statistics"],
        },
    }


def _current_case(rows=None):
    rows = rows or [[1.0, 2.0], [3.0, 4.0]]
    published = {"state": _stats(rows)}
    return {
        "id": "current",
        "label": "training_reference",
        "role_obligation": "current_population_summary",
        "role_evidence": {"current_obligation": True, "scope": "constructed_control"},
        "current_rows": {"state": rows},
        "published_statistics": published,
        "selection": _selection(published),
        "normalization_interpretation": {"status": "unresolved"},
    }


def test_statistics_use_population_variance_and_linear_quantiles():
    result = calculate_statistics([[0.0], [2.0], [4.0]])

    assert result["mean"] == [2.0]
    assert result["std"] == [math.sqrt(8.0 / 3.0)]
    assert result["q01"] == [0.04]
    assert result["q99"] == [3.96]


def test_intact_current_population_reuses_bound_statistics():
    result = decide_population_binding(_current_case())

    assert result["role"] == "current_population_summary"
    assert result["decision"]["selected_operation"] == "reuse"
    assert result["decision"]["status"] == "supported"


def test_changed_content_under_unchanged_label_recomputes():
    case = _current_case()
    case["published_statistics"]["state"]["mean"][0] += 1.0
    case["selection"] = _selection(case["published_statistics"])

    result = decide_population_binding(case)

    assert result["label"] == "training_reference"
    assert result["label_used_as_premise"] is False
    assert result["obligations"]["arithmetic"] == "rejected"
    assert result["decision"]["selected_operation"] == "recompute"
    assert result["decision"]["status"] == "rejected"
    assert result["decision"]["candidate_results"] == [
        {"operation": "reuse", "status": "rejected"},
        {"operation": "recompute", "status": "supported"},
    ]


def test_bound_external_reference_reuses_despite_subset_difference():
    published = {"state": _stats([[10.0], [20.0]])}
    formula = "(value - mean) / std"
    source = f"def normalize(value, mean, std): return {formula}\n"
    import hashlib

    case = {
        "id": "external",
        "label": "current",
        "role_obligation": "external_reference_normalizer",
        "published_statistics": published,
        "current_rows": {"state": [[0.0], [1.0]]},
        "external_reference": {
            "reference_rows": {"state": [[10.0], [20.0]]},
        },
        "selection": _selection(published),
        "normalization_interpretation": {
            "status": "supported",
            "formula": formula,
            "epsilon": 0.0,
            "constant_coordinate_behavior": "reject zero standard deviation",
            "evidence": {
                "source_text": source,
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "required_markers": ["def normalize", formula],
            },
        },
    }

    result = decide_population_binding(case)

    assert result["role"] == "external_reference_normalizer"
    assert result["decision"]["selected_operation"] == "reuse"
    assert result["decision"]["status"] == "supported"


def test_external_role_flags_and_digests_cannot_promote_a_decision():
    published = {"state": _stats([[10.0], [20.0]])}
    case = {
        "id": "declared-only",
        "label": "verified_training_reference",
        "role_obligation": "external_reference_normalizer",
        "published_statistics": published,
        "external_reference": {
            "reference_sha256": _selection(published)["selected_statistics_sha256"],
            "statistics_valid": True,
        },
        "selection": {
            "observed": True,
            "selected_statistics_sha256": _selection(published)["selected_statistics_sha256"],
            "invocation_sha256": "a" * 64,
        },
        "normalization_interpretation": {
            "status": "supported",
            "evidence_sha256": "b" * 64,
        },
    }

    result = decide_population_binding(case)

    assert result["role"] == "unresolved"
    assert result["obligations"]["selection_binding"] == "unresolved"
    assert result["obligations"]["normalization_interpretation"] == "unresolved"
    assert result["decision"]["selected_operation"] == "abstain"
    assert result["decision"]["status"] == "unresolved"


def test_current_summary_does_not_need_a_separate_selection_record():
    case = _current_case()
    case["selection"] = None

    result = decide_population_binding(case)

    assert result["decision"]["selected_operation"] == "reuse"
    assert result["decision"]["status"] == "supported"
    assert result["obligations"]["selection_binding"] == "unresolved"
    assert result["decision"]["missing"] == []


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda case: case["current_rows"].__setitem__("state", []), "empty_population"),
        (
            lambda case: case["current_rows"].__setitem__("state", [[1.0, float("nan")]]),
            "non_finite_value",
        ),
        (
            lambda case: case["current_rows"].__setitem__("state", [[1.0], [2.0, 3.0]]),
            "wrong_coordinate_count",
        ),
        (
            lambda case: case["published_statistics"]["state"].pop("std"),
            "missing_statistic",
        ),
    ],
)
def test_invalid_inputs_remain_distinct(mutate, reason):
    case = _current_case()
    mutate(case)

    result = decide_population_binding(case)

    assert result["decision"]["selected_operation"] == "invalid"
    assert result["decision"]["reason"] == reason


def test_parent_population_is_pooled_and_reused():
    episodes = [
        {
            "episode_index": 0,
            "stats": {
                "observation.state": {
                    "count": [2],
                    "mean": [1.0],
                    "std": [1.0],
                    "min": [0.0],
                    "max": [2.0],
                },
                "action": {
                    "count": [2],
                    "mean": [2.0],
                    "std": [1.0],
                    "min": [1.0],
                    "max": [3.0],
                },
            },
        },
        {
            "episode_index": 1,
            "stats": {
                "observation.state": {
                    "count": [2],
                    "mean": [5.0],
                    "std": [1.0],
                    "min": [4.0],
                    "max": [6.0],
                },
                "action": {
                    "count": [2],
                    "mean": [6.0],
                    "std": [1.0],
                    "min": [5.0],
                    "max": [7.0],
                },
            },
        },
    ]
    published = {}
    for feature in ("observation.state", "action"):
        pooled = pool_episode_statistics(episodes, feature)
        published[feature] = {
            "mean": pooled["mean"],
            "std": pooled["std"],
            "min": pooled["min"],
            "max": pooled["max"],
            "q01": pooled["min"],
            "q99": pooled["max"],
        }
    subset = [
        {
            "episode_index": 0,
            "max_abs_difference": {
                feature: {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0, "count": 2}
                for feature in ("observation.state", "action")
            },
        }
    ]
    case = {
        "id": "parent",
        "label": "current",
        "role_obligation": "parent_population_summary",
        "published_statistics": published,
        "parent_episode_statistics": episodes,
        "subset_observations": subset,
        "subset_members": 1,
        "selection": _selection(published),
        "normalization_interpretation": {"status": "unresolved"},
    }

    result = decide_population_binding(case)

    assert result["observations"]["parent_population"]["strict_superset"] is True
    assert result["observations"]["parent_population"]["extremes_exact"] is True
    assert result["decision"]["selected_operation"] == "reuse"
    assert result["decision"]["status"] == "supported"


def test_role_label_cannot_promote_missing_evidence():
    case = _current_case()
    case["role_evidence"] = {"current_obligation": False}
    case["label"] = "verified_training_reference"

    result = decide_population_binding(copy.deepcopy(case))

    assert result["role"] == "unresolved"
    assert result["decision"]["selected_operation"] == "abstain"
