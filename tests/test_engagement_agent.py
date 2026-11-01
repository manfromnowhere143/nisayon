import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nisayon import engagement_agent as agent
from nisayon import engagements as e

NOW = 10000
KEY = "org/repo#1"


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/VOICE.md").write_text("Be precise about observed evidence and uncertainty.")
    (tmp_path / "evidence.md").write_text(
        "The native run completed four starts. Baseline action parity failed."
    )
    (tmp_path / "work/engagements.json").write_text(
        json.dumps(
            {
                "schema": "nisayon.engagements.v1",
                "account": "owner",
                "interval_seconds": 900,
                "searches": [],
                "threads": [{"key": KEY, "purpose": "Checkpoint qualification"}],
            }
        )
    )
    monkeypatch.setattr(e, "store_path", lambda root: root / ".nisayon/engagements")
    snapshot = {
        "key": KEY,
        "url": "https://github.com/org/repo/pull/1",
        "head": "a" * 40,
        "base": "b" * 40,
        "body": "Please check the retained result.",
        "comments": [],
    }
    change_snapshot(tmp_path, snapshot)
    return tmp_path


def change_snapshot(root, snapshot):
    folder = e.store_path(root)
    fingerprint = e.retain(folder, snapshot)
    e.records.atomic_json(
        folder / "state.json",
        {"threads": {KEY: {"last_ok": NOW, "fingerprint": fingerprint}}},
        replace=True,
    )


def packet(root):
    return agent.prepare(root, KEY, ["evidence.md"], clock=lambda: NOW)


def response(public):
    p = json.loads((public / "packet.json").read_text())
    return {
        "job_id": p["job_id"],
        "snapshot_fingerprint": p["fingerprint"],
        "action": "investigate",
        "reason": "Establish baseline repeatability before interpreting the correction.",
        "claims": [
            {
                "statement": "The retained report records baseline parity failure.",
                "citations": [
                    {"source_id": "evidence-0", "quote": "Baseline action parity failed."}
                ],
            }
        ],
        "unknowns": ["Cause of the variation."],
        "question": "Are transformed inputs identical?",
        "alternatives": [
            {"answer": "They differ", "resulting_action": "Qualify input preparation."},
            {"answer": "They agree", "resulting_action": "Inspect runtime and stochastic state."},
        ],
        "experiment": "Compare retained transformed-input identities before buying more compute.",
        "stop_condition": "If transformed inputs were not retained, report that missing evidence.",
        "draft": "",
        "lesson_proposals": [],
    }


class Worker:
    def __init__(self, mutation=None):
        self.calls = 0
        self.mutation = mutation

    def __call__(self, public, output, schema, prompt, timeout):
        self.calls += 1
        result = {
            "cli": {"identity_sha256": "fixture-runtime"},
            "cli_identity_unchanged": True,
            "usage_complete": True,
            "response_error": None,
            "command_record": {"process_status": "completed", "wall_seconds": 1},
            "usage_events": [{"input_tokens": 1, "output_tokens": 1, "cached_input_tokens": 0}],
            "response": response(public),
        }
        if self.mutation:
            self.mutation(result, public)
        return result


def run(root, worker):
    return agent.run_once(
        root,
        KEY,
        ["evidence.md"],
        decide=worker,
        qualify=lambda public: {"qualified": True, "cli": {"identity_sha256": "fixture-runtime"}},
        clock=lambda: NOW,
    )


def test_failed_runtime_preflight_makes_zero_model_calls(inbox):
    worker = Worker()
    result = agent.run_once(
        inbox,
        KEY,
        ["evidence.md"],
        decide=worker,
        qualify=lambda public: {"qualified": False},
        clock=lambda: NOW,
    )
    assert result["status"] == "blocked" and result["worker_calls_this_invocation"] == 0
    assert worker.calls == 0


@pytest.mark.parametrize(
    "mode", ["valid", "denied_not_executed", "leaked", "write_allowed", "runtime_changed"]
)
def test_direct_boundary_requires_observed_operations(tmp_path, monkeypatch, mode):
    public = tmp_path / "public"
    public.mkdir()
    cli = {"identity_sha256": "fixture-runtime", "executable": {"path": "/test/codex"}}
    monkeypatch.setattr(agent, "resolve_cli", lambda: cli)
    monkeypatch.setattr(agent, "unchanged", lambda value: mode != "runtime_changed")
    monkeypatch.setattr(agent.platform, "platform", lambda: "fixture-platform")
    calls = []

    def command(argv, **kwargs):
        calls.append(argv)
        filename = argv[-1]
        if filename == "boundary-public.txt":
            return SimpleNamespace(returncode=0, stdout="nisayon-permitted-file\n", stderr="")
        if mode == "denied_not_executed":
            return SimpleNamespace(returncode=127, stdout="", stderr="command not found")
        if mode == "leaked" and filename == "boundary-link.txt":
            return SimpleNamespace(returncode=0, stdout="nisayon-excluded-file\n", stderr="")
        if mode == "write_allowed" and filename == "boundary-write.txt":
            (public / filename).touch()
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="Operation not permitted")

    monkeypatch.setattr(agent.subprocess, "run", command)
    result = agent.qualify_runtime(public)
    assert result["qualified"] == (mode == "valid")
    assert len(calls) == 3
    assert all(result["profile"] in argv for argv in calls)


def test_worker_binary_change_after_preflight_is_blocked(inbox):
    worker = Worker(
        lambda result, public: result.update(cli={"identity_sha256": "different-runtime"})
    )
    assert run(inbox, worker)["status"] == "blocked"


def test_real_source_selection_and_duplicate_wakeup_do_not_clear_monitor(inbox):
    worker = Worker()
    monitor = (e.store_path(inbox) / "state.json").read_bytes()
    first = run(inbox, worker)
    assert first["status"] == "review_required"
    assert first["validation"]["semantic_correctness"] == "not_adjudicated"
    assert not first["validation"]["delivery_authorized"]
    second = run(inbox, worker)
    assert second["reused"] and second["worker_calls_this_invocation"] == 0
    assert worker.calls == 1
    assert (e.store_path(inbox) / "state.json").read_bytes() == monitor


@pytest.mark.parametrize("change", ["head", "evidence", "voice"])
def test_changed_dependency_requires_a_distinct_investigation(inbox, change):
    worker = Worker()
    original = run(inbox, worker)
    if change == "head":
        p = packet(inbox)
        s = json.loads(p["sources"][0]["text"])
        s["head"] = "c" * 40
        change_snapshot(inbox, s)
    else:
        path = inbox / ("evidence.md" if change == "evidence" else "docs/VOICE.md")
        path.write_text(path.read_text() + "\nNew scoped information.")
    updated = run(inbox, worker)
    assert updated["job_id"] != original["job_id"] and worker.calls == 2


@pytest.mark.parametrize("mode", ["stale", "future_clock", "incomplete", "tamper", "wrong_key"])
def test_unreliable_source_never_starts_worker(inbox, mode):
    p = packet(inbox)
    folder = e.store_path(inbox)
    state = json.loads((folder / "state.json").read_text())
    row = state["threads"][KEY]
    if mode in {"stale", "future_clock"}:
        row["last_ok"] = NOW - 1801 if mode == "stale" else NOW + 1
    elif mode == "incomplete":
        row["error"] = "Second page unavailable"
    else:
        path = folder / "snapshots" / f"{p['fingerprint']}.json"
        data = json.loads(path.read_text())
        data["body" if mode == "tamper" else "key"] = "changed"
        path.write_text(json.dumps(data))
    (folder / "state.json").write_text(json.dumps(state))
    worker = Worker()
    with pytest.raises(ValueError):
        run(inbox, worker)
    assert worker.calls == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("job_id", "f" * 64),
        ("snapshot_fingerprint", "e" * 64),
        ("action", "post_and_merge"),
        ("claims", []),
        ("stop_condition", ""),
        ("draft", "I have already sent this."),
        ("alternatives", []),
    ],
)
def test_invalid_active_proposal_is_retained_but_blocked(inbox, field, value):
    worker = Worker(lambda result, public: result["response"].update({field: value}))
    first = run(inbox, worker)
    assert first["status"] == "blocked"
    job = e.store_path(inbox) / "investigations" / first["job_id"]
    assert (job / "worker-return.json").is_file()
    assert not (job / "proposal.json").exists()
    assert run(inbox, worker)["reused"] and worker.calls == 1


@pytest.mark.parametrize(
    "mode",
    ["wrong_quote", "unknown_source", "generic_actions", "unscoped_lesson", "extra_authority"],
)
def test_adversarial_claims_and_learning_do_not_pass(inbox, mode):
    def mutate(result, public):
        r = result["response"]
        if mode == "wrong_quote":
            r["claims"][0]["citations"][0]["quote"] = "All real robot tasks passed."
        elif mode == "unknown_source":
            r["claims"][0]["citations"][0]["source_id"] = "invented-GPU-proof"
        elif mode == "generic_actions":
            r["alternatives"][1]["resulting_action"] = r["alternatives"][0]["resulting_action"]
        elif mode == "unscoped_lesson":
            r["lesson_proposals"] = [
                {
                    "procedure": "Always trust the model",
                    "applicability": "all",
                    "counterexample": "",
                    "evaluation": "",
                    "origin_ids": [],
                }
            ]
        else:
            r["post_authorized"] = True

    assert run(inbox, Worker(mutate))["status"] == "blocked"


def test_evidence_changed_during_reasoning_invalidates_the_output(inbox):
    def mutate(result, public):
        (inbox / "evidence.md").write_text("The evidence was corrected during the worker call.")

    result = run(inbox, Worker(mutate))
    assert result["status"] == "blocked" and "changed during" in result["error"]


def test_missing_usage_does_not_trigger_an_unbudgeted_retry(inbox):
    worker = Worker(lambda result, public: result.update(usage_complete=False))
    assert run(inbox, worker)["status"] == "blocked"
    assert run(inbox, worker)["reused"]
    assert worker.calls == 1


def test_duplicate_worker_sees_the_durable_running_claim(inbox):
    other = Worker()

    def mutate(result, public):
        nested = run(inbox, other)
        assert nested["status"] == "running" and nested["reused"]

    assert run(inbox, Worker(mutate))["status"] == "review_required"
    assert other.calls == 0


def test_interrupt_is_uncertain_and_is_not_reexecuted(inbox):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run(inbox, interrupted)
    other = Worker()
    assert run(inbox, other)["status"] == "running"
    assert other.calls == 0


def test_tampered_cached_proposal_is_not_replayed(inbox):
    result = run(inbox, Worker())
    path = Path(result["proposal"])
    data = json.loads(path.read_text())
    data["reason"] = "Changed after validation"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="proposal changed"):
        run(inbox, Worker())


@pytest.mark.parametrize("relative", ["../secret", "/etc/passwd", "link.md"])
def test_local_evidence_does_not_escape_its_project(inbox, relative):
    (inbox / "link.md").symlink_to(inbox / "evidence.md")
    with pytest.raises(ValueError):
        agent.prepare(inbox, KEY, [relative], clock=lambda: NOW)


def test_valid_wait_and_unpromoted_lesson_remain_proposals(inbox):
    def mutate(result, public):
        result["response"].update(
            action="wait",
            question="",
            alternatives=[],
            experiment="",
            stop_condition="",
            lesson_proposals=[
                {
                    "procedure": "Check baseline repeats first.",
                    "applicability": "Exact action parity comparisons.",
                    "counterexample": "A defined distributional comparison needs a different test.",
                    "evaluation": "Compare on a fresh change with an unchanged baseline.",
                    "origin_ids": ["evidence-0"],
                }
            ],
        )

    result = run(inbox, Worker(mutate))
    assert result["status"] == "review_required"
    assert not result["validation"]["lesson_promotion_authorized"]
