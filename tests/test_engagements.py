import copy
import json
import time

import pytest

from nisayon import engagements as e


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    config = {
        "schema": "nisayon.engagements.v1",
        "account": "owner",
        "interval_seconds": 900,
        "searches": [],
        "threads": [{"key": "org/repo#1", "purpose": "Current contract"}],
    }
    (tmp_path / "work/engagements.json").write_text(json.dumps(config))
    monkeypatch.setattr(e, "store_path", lambda root: root / ".nisayon/engagements")
    return tmp_path


class Server:
    def __init__(self):
        self.calls = []
        self.responses = {
            "user": {"login": "owner"},
            "repos/org/repo/issues/1": {
                "html_url": "https://github.com/org/repo/pull/1",
                "title": "Question",
                "body": "Body",
                "state": "open",
                "user": {"login": "author"},
                "pull_request": {},
            },
            "repos/org/repo/issues/1/comments?per_page=100": [],
            "repos/org/repo/pulls/1": {
                "head": {"sha": "a" * 40},
                "base": {"sha": "b" * 40},
                "state": "open",
                "draft": False,
                "merged": False,
            },
            "repos/org/repo/pulls/1/comments?per_page=100": [],
            "repos/org/repo/pulls/1/reviews?per_page=100": [],
        }
        self.responses["repos/org/repo/issues/1"]["pull_request"] = {"url": "present"}
        self.fail = {}
        self.headers = {}

    def request(self, endpoint, etag):
        self.calls.append((endpoint, etag))
        if endpoint in self.fail:
            return self.fail[endpoint]
        data = copy.deepcopy(self.responses[endpoint])
        tag = e.digest(data)
        if tag == etag:
            return 304, {}, ""
        return 200, {"etag": tag, **self.headers.get(endpoint, {})}, json.dumps(data)

    def reader(self, folder):
        return e.GitHubReader(folder, request=self.request)


def again(inbox):
    path = e.store_path(inbox) / "state.json"
    state = json.loads(path.read_text())
    state["next_scan_at"] = 0
    e.records.atomic_json(path, state, replace=True)


def acknowledge(inbox):
    row = e.status(inbox)["threads"][0]
    return e.review(
        inbox,
        row["key"],
        row["fingerprint"],
        "awaiting_owner",
        "Checked at current source",
        "retained-result.json",
    )


def comment(body="Please check", identifier=1):
    return {
        "id": identifier,
        "body": body,
        "user": {"login": "author"},
        "html_url": f"https://github.com/org/repo/pull/1#issuecomment-{identifier}",
        "created_at": "2026-10-21T00:00:00Z",
    }


def test_no_snapshot_cannot_be_called_handled(inbox):
    assert e.status(inbox)["needs_review"] == 1
    assert e.status(inbox)["stale"] == 1
    with pytest.raises(ValueError, match="stale"):
        e.review(inbox, "org/repo#1", "", "watch", "Read", "source")


def test_duplicate_scan_is_quiet_and_history_survives_restart(inbox):
    server = Server()
    first = e.scan(inbox, reader_factory=server.reader)
    assert first["changed"] == ["org/repo#1"]
    receipt = acknowledge(inbox)
    retained = set((e.store_path(inbox) / "snapshots").glob("*.json"))
    count = len(server.calls)
    assert e.scan(inbox, reader_factory=server.reader)["status"] == "not_due"
    assert len(server.calls) == count
    again(inbox)
    assert e.scan(inbox, reader_factory=server.reader)["changed"] == []
    assert e.status(inbox)["needs_review"] == 0
    assert e.status(inbox)["threads"][0]["review"] == receipt
    assert set((e.store_path(inbox) / "snapshots").glob("*.json")) == retained
    assert any(etag for _, etag in server.calls)


@pytest.mark.parametrize(
    "change", ["head", "base", "body", "edit", "delete", "review", "inline", "merged"]
)
def test_changed_evidence_reopens_review(inbox, change):
    server = Server()
    comments = server.responses["repos/org/repo/issues/1/comments?per_page=100"]
    comments.append(comment())
    e.scan(inbox, reader_factory=server.reader)
    old = acknowledge(inbox)["fingerprint"]
    pr = server.responses["repos/org/repo/pulls/1"]
    if change in {"head", "base"}:
        pr[change]["sha"] = "c" * 40
    elif change == "body":
        server.responses["repos/org/repo/issues/1"]["body"] = "New question"
    elif change == "edit":
        comments[0]["body"] = "Changed request"
    elif change == "delete":
        comments.clear()
    elif change == "review":
        server.responses["repos/org/repo/pulls/1/reviews?per_page=100"].append(
            {**comment(), "state": "CHANGES_REQUESTED"}
        )
    elif change == "inline":
        server.responses["repos/org/repo/pulls/1/comments?per_page=100"].append(
            {**comment(), "path": "model.py", "line": 20}
        )
    else:
        pr.update(merged=True, state="closed")
    again(inbox)
    assert e.scan(inbox, reader_factory=server.reader)["changed"] == ["org/repo#1"]
    assert e.status(inbox)["needs_review"] == 1
    with pytest.raises(ValueError, match="stale"):
        e.review(inbox, "org/repo#1", old, "closed", "Done", "old-result")


def test_failed_page_preserves_prior_evidence_but_never_clears_error(inbox):
    server = Server()
    e.scan(inbox, reader_factory=server.reader)
    old = acknowledge(inbox)["fingerprint"]
    endpoint = "repos/org/repo/pulls/1/comments?per_page=100"
    server.fail[endpoint] = (500, {}, "")
    again(inbox)
    assert e.scan(inbox, reader_factory=server.reader)["status"] == "incomplete"
    row = e.status(inbox)["threads"][0]
    assert row["fingerprint"] == old and row["error"]
    assert row["needs_review"]
    with pytest.raises(ValueError, match="incomplete"):
        acknowledge(inbox)


def test_paginated_duplicate_ids_are_deduplicated_but_conflicts_reject(inbox):
    server = Server()
    first = "repos/org/repo/issues/1/comments?per_page=100"
    second = "https://api.github.com/repos/org/repo/issues/1/comments?page=2"
    server.responses[first] = [comment(identifier=i) for i in range(1, 101)]
    server.headers[first] = {"link": f'<{second}>; rel="next"'}
    server.responses[second] = [comment(identifier=100), comment(identifier=101)]
    reader = server.reader(e.store_path(inbox))
    result = e.snapshot(reader, "org/repo#1")
    assert len(result["comments"]) == 101
    # Collections are fetched afresh, even when their first page is unchanged.
    assert len(e.snapshot(reader, "org/repo#1")["comments"]) == 101
    server.responses[second][0]["body"] = "edited mid-pagination"
    with pytest.raises(e.ReadFailure, match="changed across pages"):
        e.snapshot(reader, "org/repo#1")


def test_pagination_cycle_and_missing_cache_are_incomplete(inbox):
    server = Server()
    endpoint = "repos/org/repo/issues/1/comments?per_page=100"
    server.headers[endpoint] = {"link": f'<{endpoint}>; rel="next"'}
    reader = server.reader(e.store_path(inbox))
    with pytest.raises(e.ReadFailure, match="Repeated"):
        reader.pages(endpoint)
    server.fail["missing"] = (304, {}, "")
    with pytest.raises(e.ReadFailure, match="without retained"):
        reader.get("missing")


def test_rate_limit_survives_restart_and_prevents_more_reads(inbox):
    server = Server()
    server.fail["user"] = (429, {"retry-after": "3600"}, "")
    before = time.time()
    assert e.scan(inbox, reader_factory=server.reader)["status"] == "incomplete"
    result = e.scan(inbox, reader_factory=server.reader)
    assert result["status"] == "not_due" and result["next_scan_at"] >= before + 3600
    assert len(server.calls) == 1
    assert e.status(inbox)["needs_review"] == 1


def test_wrong_account_never_reads_project_threads(inbox):
    server = Server()
    server.responses["user"] = {"login": "different-user"}
    assert e.scan(inbox, reader_factory=server.reader)["status"] == "incomplete"
    assert len(server.calls) == 1


def test_concurrent_writer_cannot_scan_or_clear_review(inbox):
    server = Server()
    e.scan(inbox, reader_factory=server.reader)
    with e.locked(e.store_path(inbox)):
        with pytest.raises(RuntimeError, match="writer"):
            e.scan(inbox, reader_factory=server.reader)
        with pytest.raises(RuntimeError, match="writer"):
            acknowledge(inbox)


def test_tampered_snapshot_cannot_be_reviewed(inbox):
    server = Server()
    e.scan(inbox, reader_factory=server.reader)
    fingerprint = e.status(inbox)["threads"][0]["fingerprint"]
    (e.store_path(inbox) / "snapshots" / f"{fingerprint}.json").write_text("{}")
    with pytest.raises(ValueError, match="fingerprint"):
        acknowledge(inbox)


def test_snapshot_not_published_when_pr_changes_during_read(inbox):
    server = Server()
    request = server.request
    calls = 0

    def changing(endpoint, etag):
        nonlocal calls
        if endpoint == "repos/org/repo/pulls/1":
            calls += 1
            if calls == 2:
                server.responses[endpoint]["head"]["sha"] = "changed"
        return request(endpoint, etag)

    reader = e.GitHubReader(e.store_path(inbox), request=changing)
    with pytest.raises(e.ReadFailure, match="changed during read"):
        e.snapshot(reader, "org/repo#1")


def test_new_tail_page_is_detected_when_first_page_body_is_unchanged(inbox):
    server = Server()
    endpoint = "repos/org/repo/issues/1/comments?per_page=100"
    server.responses[endpoint] = [comment(identifier=i) for i in range(1, 101)]
    reader = server.reader(e.store_path(inbox))
    assert len(e.snapshot(reader, "org/repo#1")["comments"]) == 100
    second = "https://api.github.com/repos/org/repo/issues/1/comments?page=2"
    server.headers[endpoint] = {"link": f'<{second}>; rel="next"'}
    server.responses[second] = [comment(identifier=101)]
    assert len(e.snapshot(reader, "org/repo#1")["comments"]) == 101


def test_crash_between_snapshot_and_pointer_keeps_work_unreviewed(inbox, monkeypatch):
    server = Server()
    write = e.records.atomic_json
    writes = 0

    def crash(path, data, **kwargs):
        nonlocal writes
        if path.name == "state.json":
            writes += 1
            if writes == 2:
                raise KeyboardInterrupt
        return write(path, data, **kwargs)

    monkeypatch.setattr(e.records, "atomic_json", crash)
    with pytest.raises(KeyboardInterrupt):
        e.scan(inbox, reader_factory=server.reader)
    assert e.status(inbox)["needs_review"] == 1
    monkeypatch.setattr(e.records, "atomic_json", write)
    again(inbox)
    assert e.scan(inbox, reader_factory=server.reader)["status"] == "completed"
    assert e.status(inbox)["needs_review"] == 1
    acknowledge(inbox)


def test_old_read_cannot_accept_a_review(inbox):
    server = Server()
    e.scan(inbox, reader_factory=server.reader)
    path = e.store_path(inbox) / "state.json"
    state = json.loads(path.read_text())
    state["threads"]["org/repo#1"]["last_ok"] = time.time() - 1801
    e.records.atomic_json(path, state, replace=True)
    assert e.status(inbox)["stale"] == 1
    with pytest.raises(ValueError, match="stale"):
        acknowledge(inbox)


def test_own_comment_does_not_automatically_discharge_an_obligation(inbox):
    server = Server()
    e.scan(inbox, reader_factory=server.reader)
    acknowledge(inbox)
    server.responses["repos/org/repo/issues/1/comments?per_page=100"] = [
        {**comment(), "user": {"login": "owner"}}
    ]
    again(inbox)
    e.scan(inbox, reader_factory=server.reader)
    assert e.status(inbox)["needs_review"] == 1


@pytest.mark.parametrize(
    "endpoint",
    ["https://evil.example/user", "http://api.github.com/user", "--input", "actions/dispatch"],
)
def test_transport_rejects_unscoped_requests(endpoint):
    with pytest.raises(ValueError):
        e.gh_request(endpoint, None)
