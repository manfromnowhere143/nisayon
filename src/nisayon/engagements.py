"""Read-only GitHub monitoring and revision-bound local review receipts.

Remote content is evidence to inspect, never executable instructions. This
module cannot post, approve, merge, start an agent, or promote a lesson.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import re
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from . import records, workspace

DISPOSITIONS = {"awaiting_owner", "awaiting_maintainer", "author_action", "watch", "closed"}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def registry(root: Path) -> dict:
    value = json.loads((root / "work/engagements.json").read_text())
    threads = value["threads"]
    if value.get("schema") != "nisayon.engagements.v1" or not 1 <= len(threads) <= 80:
        raise ValueError("Invalid or unbounded engagement registry")
    seen = set()
    for row in threads:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+#[1-9][0-9]*", row["key"]):
            raise ValueError("Invalid GitHub thread identity")
        if row["key"].casefold() in seen or not row.get("purpose"):
            raise ValueError("Duplicate thread or missing purpose")
        seen.add(row["key"].casefold())
    if not 300 <= value["interval_seconds"] <= 86400 or len(value["searches"]) > 4:
        raise ValueError("Invalid scan bounds")
    return value


def store_path(root: Path) -> Path:
    # All same-repository worktrees see one local inbox. Branch-local research
    # notes remain separate and still require deliberate integration.
    common = workspace.git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        raise ValueError("Cannot locate repository-owned engagement state")
    return Path(common).resolve().parent / ".nisayon/engagements"


def read_json(path: Path, default: dict) -> dict:
    return json.loads(path.read_text()) if path.exists() else default


@contextmanager
def locked(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "writer.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Engagement scan/review already has a writer") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class ReadFailure(RuntimeError):
    def __init__(self, message: str, retry_at: float = 0):
        super().__init__(message)
        self.retry_at = retry_at


def gh_request(endpoint: str, etag: str | None) -> tuple[int, dict, str]:
    parsed = urlsplit(endpoint)
    if parsed.scheme and (parsed.scheme != "https" or parsed.netloc != "api.github.com"):
        raise ValueError("GitHub pagination escaped the API host")
    if endpoint.startswith("-") or (
        not parsed.scheme and not endpoint.startswith(("repos/", "search/", "user"))
    ):
        raise ValueError("Unsupported read endpoint")
    command = ["gh", "api", "--hostname", "github.com", "--method", "GET", "--include", endpoint]
    if etag:
        command += ["--header", f"If-None-Match: {etag}"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
    except subprocess.TimeoutExpired as error:
        raise ReadFailure("GitHub GET timed out") from error
    header, separator, body = result.stdout.partition("\n\n")
    if not separator or not header.startswith("HTTP/"):
        raise ReadFailure("GitHub GET failed without a valid HTTP receipt")
    status = int(header.splitlines()[0].split()[1])
    headers = {
        k.strip().lower(): v.strip()
        for line in header.splitlines()[1:]
        if ":" in line
        for k, v in [line.split(":", 1)]
    }
    return status, headers, body


class GitHubReader:
    def __init__(self, folder: Path, request=gh_request, clock=time.time):
        self.folder = folder
        self.request = request
        self.clock = clock
        self.requests = 0

    def get(self, endpoint: str, *, conditional: bool = True) -> tuple[object, dict]:
        self.requests += 1
        if self.requests > 500:
            raise ReadFailure("Per-scan request bound reached")
        path = self.folder / "http" / f"{digest(endpoint)}.json"
        old = read_json(path, {})
        status, headers, body = self.request(endpoint, old.get("etag") if conditional else None)
        if status == 304:
            if "data" not in old:
                raise ReadFailure("304 response without retained data")
            return old["data"], old["headers"]
        if status != 200:
            retry_at = 0.0
            if status in (403, 429):
                retry_at = self.clock() + 60
                retry = headers.get("retry-after", "")
                if retry.isdigit():
                    retry_at = max(retry_at, self.clock() + int(retry))
                elif retry:
                    try:
                        retry_at = max(retry_at, parsedate_to_datetime(retry).timestamp())
                    except (ValueError, TypeError):
                        pass
                if headers.get("x-ratelimit-remaining") == "0":
                    retry_at = max(retry_at, float(headers.get("x-ratelimit-reset", retry_at)))
            raise ReadFailure(f"GitHub GET returned HTTP {status}", retry_at)
        data = json.loads(body)
        records.atomic_json(
            path,
            {
                "endpoint": endpoint,
                "etag": headers.get("etag"),
                "headers": {
                    k: v
                    for k, v in headers.items()
                    if k in {"link", "last-modified", "x-poll-interval"}
                },
                "data": data,
            },
            replace=True,
        )
        return data, headers

    def pages(self, endpoint: str) -> list:
        rows, seen = [], set()
        for _ in range(20):
            if endpoint in seen:
                raise ReadFailure("Repeated pagination link")
            seen.add(endpoint)
            # Fetch list pages afresh: a new tail page must be discovered even
            # if the first page's rows are unchanged. Object reads use ETags.
            data, headers = self.get(endpoint, conditional=False)
            if not isinstance(data, list):
                raise ReadFailure("Expected a paginated list")
            rows.extend(data)
            match = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("link", ""))
            if not match:
                return rows
            endpoint = match[1]
        raise ReadFailure("Pagination bound reached; thread is incomplete")


def snapshot(reader: GitHubReader, key: str) -> dict:
    repo, number = key.split("#")
    issue, _ = reader.get(f"repos/{repo}/issues/{number}")
    streams = {"comment": reader.pages(f"repos/{repo}/issues/{number}/comments?per_page=100")}
    result = {
        "key": key,
        "url": issue["html_url"],
        "title": issue["title"],
        "body": issue.get("body") or "",
        "state": issue["state"],
        "author": issue["user"]["login"],
        "state_reason": issue.get("state_reason"),
    }
    if issue.get("pull_request"):
        pr, _ = reader.get(f"repos/{repo}/pulls/{number}")
        streams["inline"] = reader.pages(f"repos/{repo}/pulls/{number}/comments?per_page=100")
        streams["review"] = reader.pages(f"repos/{repo}/pulls/{number}/reviews?per_page=100")
        again, _ = reader.get(f"repos/{repo}/pulls/{number}")

        def identity(row):
            return (row["head"]["sha"], row["base"]["sha"], row["state"], row["draft"])

        if identity(pr) != identity(again):
            raise ReadFailure("PR changed during read; recheck next scan")
        result.update(
            head=pr["head"]["sha"], base=pr["base"]["sha"], draft=pr["draft"], merged=pr["merged"]
        )
    comments = {}
    for stream, rows in streams.items():
        for row in rows:
            value = {
                "stream": stream,
                "id": row["id"],
                "author": (row.get("user") or {}).get("login"),
                "body": row.get("body") or "",
                "url": row.get("html_url"),
                "updated_at": row.get("updated_at")
                or row.get("submitted_at")
                or row.get("created_at"),
                "state": row.get("state"),
                "commit_id": row.get("commit_id"),
                "path": row.get("path"),
                "line": row.get("line"),
            }
            identity = (stream, row["id"])
            if identity in comments and comments[identity] != value:
                raise ReadFailure("Comment changed across pages")
            comments[identity] = value
    result["comments"] = sorted(comments.values(), key=lambda row: (row["stream"], row["id"]))
    return result


def retain(folder: Path, value: dict) -> str:
    fingerprint = digest(value)
    path = folder / "snapshots" / f"{fingerprint}.json"
    if path.exists():
        if digest(read_json(path, {})) != fingerprint:
            raise ValueError("Retained snapshot digest mismatch")
    else:
        records.atomic_json(path, value)
    return fingerprint


def scan(root: Path, *, reader_factory=GitHubReader, clock=time.time) -> dict:
    config, folder = registry(root), store_path(root)
    with locked(folder):
        state = read_json(folder / "state.json", {"threads": {}})
        if clock() < state.get("next_scan_at", 0):
            return {"status": "not_due", "next_scan_at": state["next_scan_at"]}
        reader = reader_factory(folder)
        started = clock()
        state.update(last_attempt=started, next_scan_at=started + config["interval_seconds"])

        def save():
            records.atomic_json(folder / "state.json", state, replace=True)

        save()  # A crash cannot cause immediate repeated network work.
        changed, errors = [], []
        try:
            user, _ = reader.get("user")
            if user.get("login") != config["account"]:
                raise ReadFailure("Authenticated GitHub account differs from registry")
            state.pop("error", None)
            for target in config["threads"]:
                key = target["key"]
                row = state["threads"].setdefault(key, {})
                row["last_attempt"] = clock()
                try:
                    if clock() - started > 600:
                        raise ReadFailure("Per-scan time bound reached")
                    value = snapshot(reader, key)
                    fingerprint = retain(folder, value)
                    if row.get("fingerprint") != fingerprint:
                        changed.append(key)
                    row.update(fingerprint=fingerprint, last_ok=clock())
                    row.pop("error", None)
                except (ReadFailure, ValueError, KeyError, OSError) as error:
                    row["error"] = str(error)
                    errors.append(key)
                    if isinstance(error, ReadFailure) and error.retry_at:
                        raise
                save()
            if clock() >= state.get("next_discovery_at", 0):
                since = (datetime.fromtimestamp(clock(), UTC) - timedelta(days=7)).date()
                discoveries = []
                for query in config["searches"]:
                    query = query.replace("{since}", str(since))
                    data, _ = reader.get(
                        "search/issues?"
                        + urlencode(
                            {"q": query, "sort": "updated", "order": "desc", "per_page": 30}
                        )
                    )
                    discoveries.append(
                        {
                            "query": query,
                            "total_count": data["total_count"],
                            "incomplete_results": data["incomplete_results"],
                            "items": [
                                {
                                    "url": x["html_url"],
                                    "title": x["title"],
                                    "updated_at": x["updated_at"],
                                    "author": x["user"]["login"],
                                }
                                for x in data["items"]
                            ],
                        }
                    )
                state["discovery"] = retain(
                    folder, {"kind": "bounded_discovery", "queries": discoveries}
                )
                state["discovery_checked_at"] = clock()
                state["next_discovery_at"] = clock() + 21600
                state.pop("discovery_error", None)
            state["last_finished"] = clock()
        except (ReadFailure, ValueError, KeyError, OSError) as error:
            state["error"] = str(error)
            if isinstance(error, ReadFailure):
                state["next_scan_at"] = max(state["next_scan_at"], error.retry_at)
        save()
        return {
            "status": "incomplete" if errors or state.get("error") else "completed",
            "changed": changed,
            "errors": errors,
            "error": state.get("error"),
            "requests": reader.requests,
            "next_scan_at": state["next_scan_at"],
        }


def status(root: Path, *, clock=time.time) -> dict:
    config, folder = registry(root), store_path(root)
    state = read_json(folder / "state.json", {"threads": {}})
    rows = []
    for target in config["threads"]:
        row = state["threads"].get(target["key"], {})
        reviewed = row.get("review", {}).get("fingerprint") == row.get("fingerprint") and bool(
            row.get("fingerprint")
        )
        rows.append(
            {
                "key": target["key"],
                "purpose": target["purpose"],
                "fingerprint": row.get("fingerprint"),
                "needs_review": not reviewed or bool(row.get("error")),
                "stale": clock() - row.get("last_ok", 0) > 2 * config["interval_seconds"],
                "error": row.get("error"),
                "review": row.get("review"),
            }
        )
    return {
        "store": str(folder),
        "last_attempt": state.get("last_attempt"),
        "last_finished": state.get("last_finished"),
        "error": state.get("error"),
        "next_scan_at": state.get("next_scan_at"),
        "threads": rows,
        "needs_review": sum(x["needs_review"] for x in rows),
        "stale": sum(x["stale"] for x in rows),
        "discovery": state.get("discovery"),
        "discovery_checked_at": state.get("discovery_checked_at"),
        "scope": "Local read-only monitoring; review receipts are judgments, not proof of technical resolution. No automatic replies or learning promotion.",
    }


def review(
    root: Path, key: str, fingerprint: str, disposition: str, note: str, reference: str
) -> dict:
    if disposition not in DISPOSITIONS or not note.strip() or not reference.strip():
        raise ValueError("Review needs a disposition, rationale and evidence reference")
    if key not in {x["key"] for x in registry(root)["threads"]}:
        raise ValueError("Thread is outside the registry")
    folder = store_path(root)
    with locked(folder):
        state = read_json(folder / "state.json", {"threads": {}})
        row = state["threads"].get(key, {})
        if state.get("error"):
            raise ValueError("Latest scan has an unresolved error")
        if not fingerprint or row.get("fingerprint") != fingerprint or row.get("error"):
            raise ValueError("Review is stale or the latest read is incomplete")
        if time.time() - row.get("last_ok", 0) > 2 * registry(root)["interval_seconds"]:
            raise ValueError("Thread read is stale; scan before reviewing")
        source = read_json(folder / "snapshots" / f"{fingerprint}.json", {})
        if digest(source) != fingerprint:
            raise ValueError("Snapshot does not match its fingerprint")
        receipt = {
            "id": uuid.uuid4().hex,
            "at": records.now(),
            "key": key,
            "fingerprint": fingerprint,
            "disposition": disposition,
            "note": note,
            "reference": reference,
        }
        records.atomic_json(folder / "reviews" / f"{receipt['id']}.json", receipt)
        row["review"] = receipt
        records.atomic_json(folder / "state.json", state, replace=True)
        return receipt
