"""A real upstream parent/fix and an ordinary remedy must preserve useful dispatch."""

import shutil

import pytest

from nisayon.engine.temporal_source import DEFAULT_SOURCES, QualifiedSource, reproduce


@pytest.mark.parametrize("counts", [(1, 1), (3, 3)])
def test_actual_caller_and_act_queue_expose_only_undrained_cross_episode_actions(counts):
    source = QualifiedSource(DEFAULT_SOURCES)
    affected = reproduce(source, "affected", action_counts=counts)
    fixed = reproduce(source, "upstream_fix", action_counts=counts)
    ordinary = reproduce(source, "conventional_reset", action_counts=counts)
    assert affected["measurements"]["origin_episode_mismatches"] == (1 if counts == (1, 1) else 0)
    for result in (affected, fixed, ordinary):
        assert result["measurements"]["software_dispatches"] == sum(counts)
        assert result["measurements"]["make_policy_calls"] == 1
        assert result["provenance"]["learned_inference_calls"] == 0
        assert result["provenance"]["robot_task_outcome"] == "unmeasured"
    for result in (fixed, ordinary):
        assert result["measurements"]["origin_episode_mismatches"] == 0
        assert result["measurements"]["scripted_forward_calls"] == 2
    fixed_actions = [r["action"] for r in fixed["events"] if r["kind"] == "action_dispatched"]
    ordinary_actions = [r["action"] for r in ordinary["events"] if r["kind"] == "action_dispatched"]
    assert fixed_actions == ordinary_actions
    assert {row["qualified_name"] for row in source.extractions} >= {
        "record",
        "record_episode",
        "control_loop",
        "ACTPolicy.reset",
        "ACTPolicy.select_action",
    }
    assert all(not row["body_changed"] for row in source.extractions)


def test_changed_source_between_verification_and_extraction_is_not_executed(tmp_path):
    copied = tmp_path / "sources"
    shutil.copytree(DEFAULT_SOURCES, copied)
    source = QualifiedSource(copied)
    path = copied / "fixed-control.txt"
    path.write_text(path.read_text().replace("policy.reset()", "raise RuntimeError('mutated')"))
    with pytest.raises(ValueError, match="changed before extraction"):
        reproduce(source, "upstream_fix")


def test_missing_upstream_member_stays_missing_instead_of_using_a_constructed_replacement(tmp_path):
    copied = tmp_path / "sources"
    shutil.copytree(DEFAULT_SOURCES, copied)
    (copied / "parent-control.txt").unlink()
    with pytest.raises(FileNotFoundError):
        QualifiedSource(copied)
