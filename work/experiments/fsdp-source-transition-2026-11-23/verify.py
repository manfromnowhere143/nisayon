"""Offline readback of frozen evidence. Executes no upstream code or native tests."""

import hashlib
import importlib.util
import json
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    start = time.perf_counter()
    protocol = json.loads((ROOT / "protocol.json").read_text())
    for name, identity in protocol["frozen_files"].items():
        assert sha(ROOT / name) == identity["sha256"], name
    candidate = ROOT / "candidate/src/accelerate/utils/fsdp_utils.py"
    identity = json.loads((ROOT / "candidate-identity.json").read_text())
    assert sha(candidate) == identity["candidate_sha256"]
    for name in ("current", "published"):
        raw = (ROOT / f"sources/{name}-fsdp_utils.py.txt").read_bytes()
        blob = json.loads((ROOT / f"sources/{name}-blob.json").read_text())["file"]
        assert (
            hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob["sha"]
        )
    spec = importlib.util.spec_from_file_location("frozen_scorer", ROOT / "score.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    outcomes = {}
    expected = {
        "base-development": (20, "unresolved", 0),
        "base-development-ipv4": (20, "rejected", 16),
        "base-confirmation": (8, "rejected", 8),
        "candidate-development": (20, "supported_cpu_loader_contract", 0),
        "candidate-confirmation": (8, "supported_cpu_loader_contract", 0),
        "late-clear-development": (20, "rejected", 16),
        "published-composition": (1, "unresolved", 0),
    }
    total = 0
    for name, (cases, status, failures) in expected.items():
        run = ROOT / "runs" / name
        execution = json.loads((run / "execution.json").read_text())
        result = scorer.score(run, cases, execution["source_sha256"], execution["probe_sha256"])
        assert result["status"] == status and len(result["failures"]) == failures, name
        assert result["observations"] == execution["result"]["observations"], name
        if status == "supported_cpu_loader_contract":
            assert execution["exit_code"] == 0 and execution["budget_stop"] is None
        total += execution["total_seconds"]
        outcomes[name] = {
            "status": status,
            "failure_observations": failures,
            "rank_observations": result["rank_observations"],
            "seconds": execution["total_seconds"],
        }
    native = ROOT / "runs/candidate-development"
    wrong_source = scorer.score(
        native, 20, "0" * 64, protocol["frozen_files"]["probe.py"]["sha256"]
    )
    assert wrong_source["status"] == "unresolved"
    with tempfile.TemporaryDirectory(prefix="nisayon-transition-reader-") as tmp:
        p = Path(tmp)
        (p / "rank-0.json").write_bytes((native / "rank-0.json").read_bytes())
        missing_rank = scorer.score(p, 20)
        assert missing_rank["status"] == "unresolved"
    comparison = json.loads((ROOT / "applicability/comparison.json").read_text())
    assert all(c["selection_equivalent"] and c["sdk"] == c["native"] for c in comparison["cells"])
    assert all(c["sdk"]["confirm"] == "run" for c in comparison["cells"])
    print(
        json.dumps(
            {
                "readback": "verified",
                "outcomes": outcomes,
                "native_stage_wall_seconds_including_failed_launcher": total,
                "wrong_source_and_missing_rank_refused": True,
                "fresh_confirmation_preserved_in_prospective_plans": True,
                "readback_seconds": time.perf_counter() - start,
                "new_native_execution": False,
                "gpu_memory_claim": "unqualified",
                "full_integration": "unqualified",
                "human_review_and_complete_cost": "unknown",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
