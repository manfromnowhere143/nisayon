from copy import deepcopy

import pytest

from nisayon.qualification import summarize_monitoring


def rows(successes, failures, *, success_score=0.9, failure_score=0.9):
    return [
        {
            "episode_id": f"episode-{i}",
            "task_id": "place-object",
            "policy_id": "policy-a",
            "session_id": "session-a",
            "outcome": "success" if i < successes else "failure",
            "score": success_score if i < successes else failure_score,
        }
        for i in range(successes + failures)
    ]


def audit(records, **kwargs):
    return summarize_monitoring(
        records,
        evaluator_id="frozen-judge",
        reference_id="declared-labels",
        input_protocol="ten-frames",
        **kwargs,
    )


def value(result, metric):
    return result["rates"][metric]["value"]


def test_fewer_failures_does_not_certify_detection():
    before = audit(rows(50, 50))
    after = audit(rows(99, 1))
    assert value(after, "reference_success") > value(before, "reference_success")
    assert value(after, "confirmed_misses_per_episode") < value(
        before, "confirmed_misses_per_episode"
    )
    assert value(before, "conditional_miss") == value(after, "conditional_miss") == 1
    assert after["deployment_decision"] == "unresolved"


def test_rejecting_everything_keeps_success_loss_visible():
    result = audit(rows(90, 10, success_score=0, failure_score=0))
    assert value(result, "conditional_miss") == 0
    assert value(result, "valid_success_retention") == 0
    assert result["matrix"]["success"]["rejected"] == 90


def test_absolute_misses_can_fall_while_remaining_failures_are_harder_to_detect():
    earlier = rows(80, 20, failure_score=0)
    later = rows(98, 2, failure_score=0)
    for record in earlier[-5:] + later[-1:]:
        record["score"] = 1
    before, after = audit(earlier), audit(later)
    assert value(before, "confirmed_misses_per_episode") == 0.05
    assert value(after, "confirmed_misses_per_episode") == 0.01
    assert value(before, "conditional_miss") == 0.25
    assert value(after, "conditional_miss") == 0.5
    assert value(before, "valid_success_retention") == value(after, "valid_success_retention") == 1


def test_zero_failures_is_unmeasured_not_perfect_monitoring():
    result = audit(rows(10, 0))
    assert value(result, "conditional_miss") is None
    assert result["missing_prediction_bounds"]["conditional_miss"]["upper"] is None
    assert value(result, "confirmed_misses_per_episode") == 0
    empty = audit([])
    assert all(metric["value"] is None for metric in empty["rates"].values())


def test_missing_labels_and_predictions_do_not_disappear():
    records = rows(2, 3, failure_score=0)
    records[0]["score"] = None
    records[2]["score"] = 0.5
    records[3]["score"] = None
    for i, outcome in enumerate(("unclear", "unmeasured", "invalid"), 5):
        records.append(dict(records[2], episode_id=f"episode-{i}", outcome=outcome))
    result = audit(records)
    assert result["counts"]["episodes"] == 8
    assert value(result, "reference_label_coverage") == 5 / 8
    assert value(result, "joint_binary_coverage") == 3 / 8
    assert value(result, "conditional_miss") == 1 / 2
    assert value(result, "valid_success_retention") == 1
    assert result["missing_prediction_bounds"]["conditional_miss"] == {
        "lower": 1 / 3,
        "upper": 2 / 3,
        "denominator": 3,
        "missing_predictions": 1,
    }
    assert result["missing_prediction_bounds"]["valid_success_retention"]["lower"] == 1 / 2
    assert all(
        result["matrix"][outcome]["accepted"] == 1
        for outcome in ("unclear", "unmeasured", "invalid")
    )


def test_only_missing_predictions_produces_full_bounds():
    result = audit(rows(1, 1, success_score=None, failure_score=None))
    assert value(result, "conditional_miss") is None
    assert value(result, "valid_success_retention") is None
    for bound in result["missing_prediction_bounds"].values():
        assert (bound["lower"], bound["upper"]) == (0, 1)


@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), -0.01, 1.01, "0.5", []])
def test_invalid_score_never_returns_partial_counts(bad):
    records = rows(2, 1)
    records[-1]["score"] = bad
    with pytest.raises(ValueError):
        audit(records)


@pytest.mark.parametrize("bad", [True, None, float("nan"), float("inf"), -1, 2])
def test_invalid_threshold_rejected(bad):
    with pytest.raises(ValueError):
        audit(rows(1, 1), threshold=bad)


def test_duplicates_and_incomplete_bindings_rejected():
    records = rows(1, 1)
    with pytest.raises(ValueError, match="Duplicate"):
        audit(records + [deepcopy(records[0])])
    for field in records[0]:
        broken = deepcopy(records)
        del broken[0][field]
        with pytest.raises(ValueError):
            audit(broken)
    for field in ("task_id", "episode_id", "outcome"):
        broken = deepcopy(records)
        broken[0][field] = None
        with pytest.raises(ValueError):
            audit(broken)


def test_identity_is_bound_without_claiming_independence():
    records = rows(1, 1)
    original = deepcopy(records)
    baseline = audit(records)
    assert records == original
    assert audit(list(reversed(records))) == baseline
    for field in ("episode_id", "task_id", "policy_id", "session_id"):
        changed = deepcopy(records)
        changed[0][field] += "-changed"
        result = audit(changed)
        assert result["input_sha256"] != baseline["input_sha256"]
        assert result["rates"] == baseline["rates"]
    records[0]["policy_id"] = records[0]["session_id"] = None
    result = audit(records)
    assert result["counts"]["policy_identified"] == result["counts"]["session_identified"] == 1


def test_boundary_and_failure_decomposition_on_complete_panel():
    records = rows(6, 4, success_score=0.5, failure_score=0.49)
    records[-1]["score"] = 1
    result = audit(records)
    assert value(result, "valid_success_retention") == 1
    assert value(result, "confirmed_misses_per_episode") == pytest.approx(
        (1 - value(result, "reference_success")) * value(result, "conditional_miss")
    )
