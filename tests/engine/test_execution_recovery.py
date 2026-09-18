import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nisayon.engine.configuration import Deployment
from nisayon.engine.development_cases import load_suite
from nisayon.engine.execution_store import ExecutionStore
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.recovery import inspect_execution


def test_attempt_survives_interruption_and_cannot_be_overwritten(tmp_path):
    folder = tmp_path / "execution"

    class InterruptedExecutor:
        invocation = {"id": "synthetic-test-invocation"}

        def configuration_for(self, mode, **kwargs):
            return {"deployment": kwargs["deployment"].record()}

        def run(self, **kwargs):
            assert (folder / "attempts/changed.json").is_file()
            (folder / "changed.jsonl.gz").write_bytes(b"deliberately partial gzip")
            raise KeyboardInterrupt

    header = {"case": {"id": "synthetic-recovery-test"}, "assignments": []}
    store = ExecutionStore(folder, header, InterruptedExecutor(), {"measured": None})
    with pytest.raises(KeyboardInterrupt):
        store.run(
            mode="regression",
            seed=0,
            run_id="changed",
            role="diagnostic",
            deployment=Deployment(transport_gripper_sign=-1),
        )
    before = {str(p.relative_to(folder)): file_digest(p) for p in folder.rglob("*") if p.is_file()}
    report = inspect_execution(folder)
    assert report["status"] == "incomplete_or_unstable"
    assert report["assigned_count"] == 1
    row = report["assignments"][0]
    assert row["retention_status"] == "partial_artifacts_without_run_record"
    assert row["task_outcome"] == "unknown"
    assert row["cost_records"] is None
    assert before == {
        str(p.relative_to(folder)): file_digest(p) for p in folder.rglob("*") if p.is_file()
    }
    with pytest.raises(ValueError, match="already attempted"):
        store.run(
            mode="regression", seed=0, run_id="changed", role="diagnostic", deployment=Deployment()
        )


def test_recovery_keeps_assigned_but_unretained_conditions_in_the_denominator(tmp_path):
    assignment = {
        "run_id": "never-retained",
        "mode": "reference",
        "seed": 7,
        "role": "fresh_development_confirmation",
    }
    write_json(
        tmp_path / "bundle-header.json", {"assignments": [assignment], "case": {"id": "synthetic"}}
    )
    report = inspect_execution(tmp_path)
    assert report["assigned_count"] == 1
    assert report["run_records_present"] == 0
    assert report["assignments"][0]["retention_status"] == "assigned_without_retained_attempt"
    assert "Unchanged" in report["condition_reservations"]


def test_attempt_cannot_redirect_writes_outside_the_store(tmp_path):
    executor = SimpleNamespace(invocation={"id": "synthetic"})
    store = ExecutionStore(tmp_path / "source", {"case": {"id": "synthetic"}}, executor, {})
    with pytest.raises(ValueError, match="simple artifact"):
        store._intent({"run_id": "../outside"}, {})
    assert not (tmp_path / "outside.json").exists()


def test_changed_frozen_assignment_rejects_before_running(tmp_path):
    assignment = {
        "run_id": "reference",
        "mode": "reference",
        "seed": 7,
        "role": "reproduction",
        "candidate_sha256": digest(Deployment().record()),
    }
    executor = SimpleNamespace(invocation={"id": "synthetic"})
    store = ExecutionStore(
        tmp_path / "source",
        {"case": {"id": "synthetic"}, "assignments": [assignment]},
        executor,
        {},
    )
    with pytest.raises(ValueError, match="frozen assignment"):
        store._intent({**assignment, "seed": 8}, {})
    assert not (store.root / "attempts").exists()


def test_development_case_loader_retains_unsupported_and_unresolved_assignments(tmp_path):
    source = Path(__file__).resolve().parents[2] / "work/development/incidents-proposed-v1.json"
    raw, cases, _ = load_suite(source)
    assert len(cases) == 10
    assert cases[2].failure_obligation == "timing"
    assert cases[5].changed.policy_reset == "every_action"
    assert cases[9].telemetry_profile == "policy_state_unavailable"
    raw["cases"] = raw["cases"][:-1]
    path = tmp_path / "dropped-case.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="ten distinct"):
        load_suite(path)
