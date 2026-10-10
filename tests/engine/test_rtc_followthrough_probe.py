"""Discriminating relative-prefix and observation/queue controls on pinned bodies."""

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "rtc_followthrough_probe", ROOT / "scripts/experiments/probe_rtc_followthrough.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.mark.parametrize("variant", probe.VARIANTS)
@pytest.mark.parametrize("schedule", probe.schedules())
def test_relative_worker_preserves_actions_and_exposes_distinct_snapshot_boundaries(
    variant, schedule
):
    pytest.importorskip("torch", reason="source probe uses real CPU tensors")
    row = probe.run_schedule(variant, **schedule)
    assert not row["worker_error"]
    assert row["dispatched_tasks"] == ["fixture_task"] * row["ticks"]
    for i, action in enumerate(row["consumed"], row["offset"]):
        assert action == pytest.approx([100 + i, 200 + 2 * i, 0.2 + 0.1 * i], abs=1e-5)
    coherent = row["boundary"] != "observation_queue" or variant == "observation_snapshot"
    assert row["pair_existed_before_merge"] == coherent
    frame = 1 if row["boundary"] == "observation_queue" and variant == "observation_snapshot" else 0
    assert row["policy_observation_id"] == frame
    assert row["normalized_policy_state"][0] == pytest.approx(
        [(25 + frame - 5) / 2, (37 + frame - 7) / 3, (700 + frame - 9) / 5], abs=1e-5
    )
    if row["reset"]:
        assert row["actual_next_action"] is None
        assert row["next_action_matches"] and not row["queue_progress_retained"]
        assert row["observed_pre_merge_memory_states"][-1] == {"observation_id": None, "index": 0}
        return
    skipped_again = (
        row["ticks"] if variant == "upstream" and row["boundary"] != "observation_queue" else 0
    )
    i = row["offset"] + row["ticks"] + skipped_again
    assert row["actual_next_action"] == pytest.approx(
        [100 + i, 200 + 2 * i, 0.2 + 0.1 * i], abs=1e-5
    )
    assert row["next_action_matches"] == (skipped_again == 0)
    assert row["prefix_matches_snapshot"] == (skipped_again == 0)
    assert row["queue_progress_retained"]


@pytest.mark.parametrize("target", ["manifest.json", "relative.py.txt"])
def test_processor_identity_changes_are_rejected_before_execution(tmp_path, target):
    for path in probe.SOURCES.iterdir():
        shutil.copyfile(path, tmp_path / path.name)
    path = tmp_path / target
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="differs|differ"):
        probe.source_text(tmp_path)


def test_unsupported_boundary_does_not_become_an_implicit_qualification():
    with pytest.raises(ValueError, match="Unknown snapshot boundary"):
        probe.run_schedule("upstream", boundary="sensor_synchronization", offset=0, ticks=1)
