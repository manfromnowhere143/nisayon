"""Acquire one exact A1 wheel HEAD or byte range with no redirect and no retry."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import time
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

PINNED_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/f4/15/"
    "82093cadf23811463d0b52ec6745949356b66badf6e25bee64ec82aa8689/"
    "robosuite-1.5.1-py3-none-any.whl"
)
PINNED_ARCHIVE_BYTES = 152_011_410
CONTENT_RANGE = re.compile(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)\Z")
STRONG_ETAG = re.compile(r'"[\x21\x23-\x7e\x80-\xff]*"\Z')


class ResponseLike(Protocol):
    status: int
    reason: str

    def getheaders(self) -> list[tuple[str, str]]: ...

    def read(self, amount: int | None = None) -> bytes: ...

    def close(self) -> None: ...


class ConnectionLike(Protocol):
    def request(
        self, method: str, url: str, body: bytes | None = None, headers: dict | None = None
    ) -> None: ...

    def getresponse(self) -> ResponseLike: ...

    def close(self) -> None: ...


class AcquisitionError(RuntimeError):
    """The immutable request preflight is invalid."""


def _header_values(headers: list[tuple[str, str]], name: str) -> list[str]:
    return [value.strip() for key, value in headers if key.lower() == name.lower()]


def _single_header(headers: list[tuple[str, str]], name: str) -> tuple[str | None, str | None]:
    values = _header_values(headers, name)
    if not values:
        return None, None
    if len(values) != 1:
        return None, f"response has {len(values)} {name} headers"
    return values[0], None


def _validate_strong_etag(value: str) -> bool:
    return STRONG_ETAG.fullmatch(value) is not None


def _validate_head(*, status: int, headers: list[tuple[str, str]], body_bytes: int) -> list[str]:
    errors = []
    if status != 200:
        errors.append(f"HEAD status is {status}, not 200")
    length, error = _single_header(headers, "Content-Length")
    if error:
        errors.append(error)
    elif length is None:
        errors.append("HEAD omitted Content-Length")
    else:
        try:
            parsed_length = int(length)
        except ValueError:
            errors.append("HEAD Content-Length is not an integer")
        else:
            if parsed_length != PINNED_ARCHIVE_BYTES:
                errors.append(
                    f"HEAD Content-Length differs: {parsed_length} != {PINNED_ARCHIVE_BYTES}"
                )
    accept_ranges, error = _single_header(headers, "Accept-Ranges")
    if error:
        errors.append(error)
    elif accept_ranges is None or accept_ranges.lower() != "bytes":
        errors.append("HEAD does not declare Accept-Ranges: bytes")
    etag, error = _single_header(headers, "ETag")
    if error:
        errors.append(error)
    elif etag is None or not _validate_strong_etag(etag):
        errors.append("HEAD does not declare one syntactically valid strong ETag")
    if body_bytes != 0:
        errors.append(f"HEAD returned {body_bytes} body bytes")
    return errors


def _validate_range(
    *,
    status: int,
    headers: list[tuple[str, str]],
    body_bytes: int,
    start: int,
    end: int,
    expected_etag: str,
) -> list[str]:
    errors = []
    expected_bytes = end - start + 1
    if status != 206:
        errors.append(f"Range status is {status}, not 206")
    content_range, error = _single_header(headers, "Content-Range")
    if error:
        errors.append(error)
    elif content_range is None:
        errors.append("Range response omitted Content-Range")
    else:
        match = CONTENT_RANGE.fullmatch(content_range)
        if match is None:
            errors.append(f"Content-Range is malformed: {content_range!r}")
        else:
            actual = tuple(int(value) for value in match.groups())
            expected = (start, end, PINNED_ARCHIVE_BYTES)
            if actual != expected:
                errors.append(f"Content-Range differs: {actual} != {expected}")
    length, error = _single_header(headers, "Content-Length")
    if error:
        errors.append(error)
    elif length is None:
        errors.append("Range response omitted Content-Length")
    else:
        try:
            parsed_length = int(length)
        except ValueError:
            errors.append("Range Content-Length is not an integer")
        else:
            if parsed_length != expected_bytes:
                errors.append(f"Range Content-Length differs: {parsed_length} != {expected_bytes}")
    encoding, error = _single_header(headers, "Content-Encoding")
    if error:
        errors.append(error)
    elif encoding is not None and encoding.lower() != "identity":
        errors.append(f"Range response uses Content-Encoding {encoding!r}")
    etag, error = _single_header(headers, "ETag")
    if error:
        errors.append(error)
    elif etag != expected_etag:
        errors.append(f"Range ETag differs: {etag!r} != {expected_etag!r}")
    if body_bytes != expected_bytes:
        errors.append(f"Range body length differs: {body_bytes} != {expected_bytes}")
    return errors


def _validate_url(url: str) -> urllib.parse.SplitResult:
    if url != PINNED_WHEEL_URL:
        raise AcquisitionError("URL differs from the pinned robosuite 1.5.1 wheel")
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "files.pythonhosted.org"
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AcquisitionError("pinned URL has an unexpected transport component")
    return parsed


def _write_json_create_only(path: Path, document: dict) -> tuple[int, str]:
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
    return len(payload), hashlib.sha256(payload).hexdigest()


def acquire_once(
    *,
    method: str,
    url: str,
    receipt: Path,
    body: Path | None,
    range_start: int | None,
    range_end: int | None,
    timeout_seconds: float,
    recorded_at: str,
    source_commit: str,
    expected_etag: str | None,
    connection_factory: Callable[..., ConnectionLike] = http.client.HTTPSConnection,
) -> tuple[dict, bool]:
    """Issue exactly one HTTP request and retain enough evidence to count its response."""

    parsed = _validate_url(url)
    method = method.upper()
    if method not in {"HEAD", "GET"}:
        raise AcquisitionError("method must be HEAD or GET")
    if timeout_seconds <= 0:
        raise AcquisitionError("timeout_seconds must be positive")
    if receipt.exists() or receipt.is_symlink():
        raise FileExistsError(f"refusing to overwrite receipt {receipt}")
    if method == "HEAD":
        if (
            body is not None
            or range_start is not None
            or range_end is not None
            or expected_etag is not None
        ):
            raise AcquisitionError("HEAD cannot have a body path, byte range, or expected ETag")
        read_limit = 0
    else:
        if body is None:
            raise AcquisitionError("GET requires a retained body path")
        if body.resolve(strict=False) == receipt.resolve(strict=False):
            raise AcquisitionError("response body and receipt paths must differ")
        if body.exists() or body.is_symlink():
            raise FileExistsError(f"refusing to overwrite response body {body}")
        if range_start is None or range_end is None:
            raise AcquisitionError("GET requires both range endpoints")
        if expected_etag is None or not _validate_strong_etag(expected_etag):
            raise AcquisitionError("GET requires one syntactically valid strong expected ETag")
        if range_start < 0 or range_end < range_start or range_end >= PINNED_ARCHIVE_BYTES:
            raise AcquisitionError("GET byte range lies outside the pinned archive")
        read_limit = range_end - range_start + 1

    request_headers = {
        "Accept": "application/octet-stream",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "User-Agent": "Nisayon-A1-runtime-evidence/1.0",
    }
    if method == "GET":
        request_headers["Range"] = f"bytes={range_start}-{range_end}"
        request_headers["If-Match"] = expected_etag
    target = parsed.path
    started = datetime.now(UTC).isoformat()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    response_received = False
    response_status = None
    response_reason = None
    response_headers: list[tuple[str, str]] = []
    response_strong_etag = None
    body_bytes = 0
    body_sha256 = hashlib.sha256(b"").hexdigest()
    body_complete = False
    transport_failure = None
    connection = None
    response = None
    output = None
    digest = hashlib.sha256()
    try:
        connection = connection_factory(
            parsed.hostname, parsed.port or 443, timeout=timeout_seconds
        )
        connection.request(method, target, headers=request_headers)
        response = connection.getresponse()
        response_received = True
        response_status = int(response.status)
        response_reason = str(response.reason or "")
        response_headers = [(str(key), str(value)) for key, value in response.getheaders()]
        etag, etag_error = _single_header(response_headers, "ETag")
        if etag_error is None and etag is not None and _validate_strong_etag(etag):
            response_strong_etag = etag
        if body is not None:
            body.parent.mkdir(parents=True, exist_ok=True)
            output = body.open("xb")
        while True:
            remaining = read_limit + 1 - body_bytes
            if remaining <= 0:
                break
            chunk = response.read(min(1024 * 1024, remaining))
            if not chunk:
                body_complete = True
                break
            body_bytes += len(chunk)
            digest.update(chunk)
            if output is not None:
                output.write(chunk)
    except Exception as error:  # noqa: BLE001 - the exact failed request is evidence.
        transport_failure = f"{type(error).__name__}: {error}"
    finally:
        if output is not None:
            output.flush()
            output.close()
        if response is not None:
            response.close()
        if connection is not None:
            connection.close()
    body_sha256 = digest.hexdigest()

    validation_errors: list[str] = []
    if transport_failure is not None:
        validation_errors.append(transport_failure)
    elif not response_received or response_status is None:
        validation_errors.append("no HTTP response was received")
    elif not body_complete:
        validation_errors.append(f"response exceeded the read limit of {read_limit} bytes")
    if response_received and response_status is not None:
        if method == "HEAD":
            validation_errors.extend(
                _validate_head(
                    status=response_status,
                    headers=response_headers,
                    body_bytes=body_bytes,
                )
            )
        else:
            assert range_start is not None and range_end is not None
            validation_errors.extend(
                _validate_range(
                    status=response_status,
                    headers=response_headers,
                    body_bytes=body_bytes,
                    start=range_start,
                    end=range_end,
                    expected_etag=expected_etag,
                )
            )

    ended = datetime.now(UTC).isoformat()
    record = {
        "schema": "nisayon.a1-runtime-http-response.v1",
        "case": "a1-runtime-001",
        "recorded_at": recorded_at,
        "source_commit": source_commit,
        "request": {
            "method": method,
            "url": url,
            "target": target,
            "headers": sorted(request_headers.items()),
            "range_start": range_start,
            "range_end": range_end,
            "expected_strong_etag": expected_etag,
            "automatic_redirects": 0,
            "automatic_retries": 0,
        },
        "response": {
            "received": response_received,
            "status": response_status,
            "reason": response_reason,
            "headers": response_headers,
            "strong_etag": response_strong_etag,
            "body_path": str(body) if body is not None else None,
            "body_bytes_read": body_bytes,
            "body_sha256": body_sha256,
            "body_complete_within_limit": body_complete,
            "transport_failure": transport_failure,
        },
        "validation": {
            "passed": not validation_errors,
            "errors": validation_errors,
        },
        "accounting": {
            "application_responses": 1 if response_received else 0,
            "response_body_bytes": body_bytes,
            "network_protocol_overhead_bytes": None,
        },
        "timing": {
            "started_at": started,
            "ended_at": ended,
            "wall_seconds": time.perf_counter() - start_wall,
            "process_cpu_seconds": time.process_time() - start_cpu,
        },
        "operations": {
            "environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
            "attempt_slots_consumed": 0,
        },
        "boundary": (
            "one request only; redirects are retained as failures and are never followed; "
            "a later request requires its own prospective reservation"
        ),
        "publication": "private; no push or publication",
    }
    return record, not validation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("HEAD", "GET"), required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--body", type=Path)
    parser.add_argument("--range-start", type=int)
    parser.add_argument("--range-end", type=int)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--expected-etag")
    args = parser.parse_args()
    record, passed = acquire_once(
        method=args.method,
        url=args.url,
        receipt=args.receipt,
        body=args.body,
        range_start=args.range_start,
        range_end=args.range_end,
        timeout_seconds=args.timeout_seconds,
        recorded_at=args.recorded_at,
        source_commit=args.source_commit,
        expected_etag=args.expected_etag,
    )
    receipt_bytes, receipt_sha256 = _write_json_create_only(args.receipt, record)
    print(
        json.dumps(
            {
                "passed": passed,
                "receipt": str(args.receipt),
                "receipt_bytes": receipt_bytes,
                "receipt_sha256": receipt_sha256,
                "application_responses": record["accounting"]["application_responses"],
                "response_body_bytes": record["accounting"]["response_body_bytes"],
                "response_strong_etag": record["response"]["strong_etag"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
