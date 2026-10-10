"""Pinned upstream concurrency witnesses; no model or robot execution."""

import importlib.util
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "rtc_snapshot_probe", ROOT / "scripts/experiments/probe_rtc_snapshot.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.mark.parametrize("name", tuple(probe.PINS))
def test_changed_upstream_bytes_are_rejected_before_extraction(tmp_path, name):
    for member in probe.PINS:
        shutil.copyfile(probe.SOURCES / member, tmp_path / member)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Source bytes differ"):
        probe.source_text(tmp_path)


@pytest.mark.parametrize("variant", ["upstream", "atomic_snapshot"])
@pytest.mark.parametrize("offset", [0, 2])
@pytest.mark.parametrize("ticks", [0, 1, 2])
def test_real_worker_interleaving_preserves_or_skips_the_next_echo(variant, offset, ticks):
    pytest.importorskip("torch", reason="source probe uses real CPU tensors")
    row = probe.run_schedule(probe.source_text(probe.SOURCES), variant, offset=offset, ticks=ticks)
    coherent_next = 100 + offset + ticks
    assert row["consumed"] == [float(100 + offset + i) for i in range(ticks)]
    assert row["index_read"] == offset
    prefix_shift = ticks if variant == "upstream" else 0
    assert row["policy_prefix"][0] == offset + prefix_shift
    assert row["actual_next_queued_action"] == coherent_next + prefix_shift
    assert row["matches_coherent_echo"] == (prefix_shift == 0)
    assert row["queue_progress_retained"] and not row["worker_error"]


@pytest.mark.parametrize("variant", ["upstream", "atomic_snapshot"])
def test_existing_reset_guard_rejects_work_from_before_reset(variant):
    pytest.importorskip("torch", reason="source probe uses real CPU tensors")
    row = probe.run_schedule(
        probe.source_text(probe.SOURCES), variant, offset=0, ticks=1, reset=True
    )
    assert row["actual_next_queued_action"] is None
    assert row["matches_coherent_echo"]
    assert not row["queue_progress_retained"] and not row["worker_error"]


def test_candidate_snapshot_keeps_both_action_representations_and_owns_its_copies():
    torch = pytest.importorskip("torch", reason="source probe uses real CPU tensors")
    module = probe.load(probe.candidate(probe.source_text(probe.SOURCES)), clock=None)
    queue = module["ActionQueue"](SimpleNamespace(enabled=True))
    original = torch.arange(8, dtype=torch.float32).reshape(-1, 1)
    queue.merge(original, original + 100, 0, task="different_coordinate_representations")
    queue.get()
    index, raw, processed = queue.get_inference_snapshot()
    assert index == 1
    assert raw[:, 0].tolist() == list(range(1, 8))
    assert processed[:, 0].tolist() == list(range(101, 108))
    raw.fill_(-999)
    processed.fill_(-999)
    assert queue.get_left_over()[0].item() == 1
    assert queue.get()[0].item() == 101


def test_probe_rejects_unsupported_interleavings_instead_of_extending_its_claim():
    with pytest.raises(ValueError, match="outside the reviewed"):
        probe.run_schedule(probe.source_text(probe.SOURCES), "upstream", offset=0, ticks=100)
