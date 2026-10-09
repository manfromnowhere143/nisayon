from __future__ import annotations

import hashlib
import importlib.util
import resource
import time
from pathlib import Path

SCRIPT = Path("scripts/experiments/inventory_policy_tasks.py")
SPEC = importlib.util.spec_from_file_location("inventory_policy_tasks", SCRIPT)
inventory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(inventory)


def reset_meter() -> None:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    inventory._START_CHILDREN = (usage.ru_utime, usage.ru_stime)
    inventory._START_SELF = time.process_time()


def test_walk_is_depth_bounded_and_prunes_internal_directories(tmp_path):
    (tmp_path / "model.pth").write_bytes(b"root")
    (tmp_path / "one").mkdir()
    (tmp_path / "one/model.safetensors").write_bytes(b"one")
    (tmp_path / "one/two").mkdir()
    (tmp_path / "one/two/deep.ckpt").write_bytes(b"deep")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/hidden.pt").write_bytes(b"hidden")
    reset_meter()

    paths, record = inventory._walk_files(tmp_path, max_depth=1)

    assert {path.relative_to(tmp_path).as_posix() for path in paths} == {
        "model.pth",
        "one/model.safetensors",
    }
    assert record["errors"] == []
    assert record["visited_directories"] == 2


def test_identity_hashes_small_files_and_refuses_large_hash(monkeypatch, tmp_path):
    small = tmp_path / "small.pth"
    small.write_bytes(b"policy")
    large = tmp_path / "large.pth"
    large.write_bytes(b"1234")
    monkeypatch.setattr(inventory, "MAX_HASH_BYTES", 3)

    small_identity = inventory._identity(small, hash_large=True)
    large_identity = inventory._identity(large)

    assert small_identity["sha256"] == hashlib.sha256(b"policy").hexdigest()
    assert large_identity["sha256"] is None
    assert "exceed 3" in large_identity["digest_status"]


def test_candidate_order_prefers_the_qualified_lift_filename():
    paths = [
        Path("cache/gpt2/model.safetensors"),
        Path("artifacts/assets/lift_ph_low_dim_epoch_1000_succ_100.pth"),
        Path("cache/robot-policy/model.bin"),
    ]

    assert sorted(paths, key=inventory._candidate_priority) == [paths[1], paths[2], paths[0]]
