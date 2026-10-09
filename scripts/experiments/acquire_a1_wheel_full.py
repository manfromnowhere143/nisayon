"""Acquire the one pinned A1 robosuite wheel with no redirect or retry."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import time
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

PINNED_WHEEL_FILENAME = "robosuite-1.5.1-py3-none-any.whl"
PINNED_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/f4/15/"
    "82093cadf23811463d0b52ec6745949356b66badf6e25bee64ec82aa8689/"
    "robosuite-1.5.1-py3-none-any.whl"
)
PINNED_WHEEL_BYTES = 152_011_410
PINNED_WHEEL_SHA256 = "39810a9e9f193455fcb13a9b4846424abef77481ac3091892c2077c88dcdc153"
PINNED_PUBLISHER_RECORD_SHA256 = "5a4ade478dbe844b74fb1d63dd861243c790c29618a433e4e510fbb666a76a23"
WHEEL_ALLOWANCE_BYTES = 167_772_160
TEMPORARY_RESERVATION_BYTES = 201_326_592
ISOLATED_ENVIRONMENT_AND_CACHE_BYTES = 1_610_612_736
MINIMUM_FREE_DISK_BYTES = 5_368_709_120
MAX_SOCKET_TIMEOUT_SECONDS = 1_200
GIT_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
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
    """The immutable acquisition preflight is invalid."""


def _header_values(headers: list[tuple[str, str]], name: str) -> list[str]:
    return [value.strip() for key, value in headers if key.lower() == name.lower()]


def _single_header(headers: list[tuple[str, str]], name: str) -> tuple[str | None, str | None]:
    values = _header_values(headers, name)
    if not values:
        return None, None
    if len(values) != 1:
        return None, f"response has {len(values)} {name} headers"
    return values[0], None


def _parse_recorded_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AcquisitionError("recorded_at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise AcquisitionError("recorded_at must include a UTC offset")
    return value


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


def verify_publisher_record(path: Path) -> dict:
    """Bind the executable pin to the retained publisher-metadata delivery."""

    payload = path.read_bytes()
    record_sha256 = hashlib.sha256(payload).hexdigest()
    if record_sha256 != PINNED_PUBLISHER_RECORD_SHA256:
        raise AcquisitionError(
            f"publisher record sha256 differs: {record_sha256} != {PINNED_PUBLISHER_RECORD_SHA256}"
        )
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError("publisher record is not valid UTF-8 JSON") from error
    if document.get("schema") != "nisayon.a1-runtime-source-delivery.v1":
        raise AcquisitionError("publisher record schema differs")
    if document.get("case") != "a1-runtime-001":
        raise AcquisitionError("publisher record case differs")
    archives = document.get("release", {}).get("archives")
    if not isinstance(archives, list):
        raise AcquisitionError("publisher record archives are missing")
    matches = [
        item
        for item in archives
        if isinstance(item, dict) and item.get("filename") == PINNED_WHEEL_FILENAME
    ]
    if len(matches) != 1:
        raise AcquisitionError("publisher record does not bind exactly one pinned wheel")
    expected = {
        "filename": PINNED_WHEEL_FILENAME,
        "url": PINNED_WHEEL_URL,
        "bytes": PINNED_WHEEL_BYTES,
        "sha256": PINNED_WHEEL_SHA256,
    }
    observed = {key: matches[0].get(key) for key in expected}
    if observed != expected:
        raise AcquisitionError(f"publisher wheel identity differs: {observed!r} != {expected!r}")
    return {
        "record_path": str(path),
        "record_sha256": record_sha256,
        "wheel": expected,
    }


def _validate_response_headers(
    *, status: int, headers: list[tuple[str, str]]
) -> tuple[list[str], int | None]:
    errors: list[str] = []
    if status != 200:
        errors.append(f"full-wheel status is {status}, not 200")
    length, error = _single_header(headers, "Content-Length")
    parsed_length = None
    if error:
        errors.append(error)
    elif length is None:
        errors.append("full-wheel response omitted Content-Length")
    else:
        try:
            parsed_length = int(length)
        except ValueError:
            errors.append("full-wheel Content-Length is not an integer")
        else:
            if parsed_length < 0:
                errors.append("full-wheel Content-Length is negative")
            elif parsed_length > WHEEL_ALLOWANCE_BYTES:
                errors.append(
                    "full-wheel Content-Length exceeds the wheel-only allowance: "
                    f"{parsed_length} > {WHEEL_ALLOWANCE_BYTES}"
                )
            elif parsed_length != PINNED_WHEEL_BYTES:
                errors.append(
                    f"full-wheel Content-Length differs: {parsed_length} != {PINNED_WHEEL_BYTES}"
                )
    encoding, error = _single_header(headers, "Content-Encoding")
    if error:
        errors.append(error)
    elif encoding is not None and encoding.lower() != "identity":
        errors.append(f"full-wheel response uses Content-Encoding {encoding!r}")
    transfer_encoding, error = _single_header(headers, "Transfer-Encoding")
    if error:
        errors.append(error)
    elif transfer_encoding is not None:
        errors.append(f"full-wheel response uses Transfer-Encoding {transfer_encoding!r}")
    content_range, error = _single_header(headers, "Content-Range")
    if error:
        errors.append(error)
    elif content_range is not None:
        errors.append(f"full-wheel response unexpectedly declares Content-Range {content_range!r}")
    return errors, parsed_length


def _write_json_create_only(path: Path, document: dict) -> tuple[int, str]:
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
    return len(payload), hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            byte_count += len(chunk)
            digest.update(chunk)
    return byte_count, digest.hexdigest()


def _failure(stage: str, error: Exception) -> dict[str, str]:
    return {
        "stage": stage,
        "type": type(error).__name__,
        "message": str(error),
    }


def _resource_guard(
    body: Path,
    *,
    disk_usage_factory: Callable[[Path], object] = shutil.disk_usage,
) -> dict:
    anchor = body.parent.resolve(strict=False)
    while not anchor.exists():
        if anchor == anchor.parent:
            raise AcquisitionError("no existing storage ancestor for response body")
        anchor = anchor.parent
    usage = disk_usage_factory(anchor)
    try:
        total = int(usage.total)
        used = int(usage.used)
        free = int(usage.free)
    except (AttributeError, TypeError, ValueError) as error:
        raise AcquisitionError("disk usage result is malformed") from error
    if min(total, used, free) < 0:
        raise AcquisitionError("disk usage result contains a negative value")
    reserved = (
        PINNED_WHEEL_BYTES + TEMPORARY_RESERVATION_BYTES + ISOLATED_ENVIRONMENT_AND_CACHE_BYTES
    )
    projected_free = free - reserved
    if projected_free < MINIMUM_FREE_DISK_BYTES:
        raise AcquisitionError(
            "free disk would cross the frozen floor after the wheel, temporary and "
            f"environment reservations: {projected_free} < {MINIMUM_FREE_DISK_BYTES}"
        )
    return {
        "volume_anchor": str(anchor),
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "wheel_bytes": PINNED_WHEEL_BYTES,
        "temporary_reservation_bytes": TEMPORARY_RESERVATION_BYTES,
        "isolated_environment_and_cache_bytes": ISOLATED_ENVIRONMENT_AND_CACHE_BYTES,
        "projected_free_bytes": projected_free,
        "minimum_free_disk_bytes": MINIMUM_FREE_DISK_BYTES,
        "passed": True,
        "scope_limit": (
            "this immediate volume guard does not replace the separately retained "
            "project-payload and shared-temporary projection"
        ),
    }


def acquire_once(
    *,
    url: str,
    publisher_record: Path,
    receipt: Path,
    body: Path,
    socket_timeout_seconds: float,
    recorded_at: str,
    source_commit: str,
    connection_factory: Callable[..., ConnectionLike] = http.client.HTTPSConnection,
    disk_usage_factory: Callable[[Path], object] = shutil.disk_usage,
) -> tuple[dict, bool]:
    """Issue exactly one full-body request and retain its counted outcome."""

    parsed = _validate_url(url)
    publisher_identity = verify_publisher_record(publisher_record)
    _parse_recorded_at(recorded_at)
    if not GIT_SHA1.fullmatch(source_commit):
        raise AcquisitionError("source_commit must be one lowercase 40-hex Git object name")
    if not 0 < socket_timeout_seconds <= MAX_SOCKET_TIMEOUT_SECONDS:
        raise AcquisitionError(
            f"socket_timeout_seconds must be in (0, {MAX_SOCKET_TIMEOUT_SECONDS}]"
        )
    if receipt.exists() or receipt.is_symlink():
        raise FileExistsError(f"refusing to overwrite receipt {receipt}")
    if body.exists() or body.is_symlink():
        raise FileExistsError(f"refusing to overwrite response body {body}")
    if body.resolve(strict=False) == receipt.resolve(strict=False):
        raise AcquisitionError("response body and receipt paths must differ")
    resource_guard = _resource_guard(body, disk_usage_factory=disk_usage_factory)

    request_headers = {
        "Accept": "application/octet-stream",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "User-Agent": "Nisayon-A1-runtime-evidence/1.0",
    }
    target = parsed.path
    started_at = datetime.now(UTC).isoformat()
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    response_received = False
    response_status = None
    response_reason = None
    response_headers: list[tuple[str, str]] = []
    reported_content_length = None
    response_strong_etag = None
    body_bytes = 0
    digest = hashlib.sha256()
    body_complete = False
    body_read_started = False
    body_file_created = False
    failure_events: list[dict[str, str]] = []
    header_errors: list[str] = []
    connection = None
    response = None
    output = None
    stage = "connection_construction"
    try:
        connection = connection_factory(
            parsed.hostname, parsed.port or 443, timeout=socket_timeout_seconds
        )
        stage = "request_send"
        connection.request("GET", target, headers=request_headers)
        stage = "response_receive"
        response = connection.getresponse()
        response_received = True
        response_status = int(response.status)
        response_reason = str(response.reason or "")
        response_headers = [(str(key), str(value)) for key, value in response.getheaders()]
        etag, etag_error = _single_header(response_headers, "ETag")
        if etag_error is None and etag is not None and STRONG_ETAG.fullmatch(etag):
            response_strong_etag = etag
        header_errors, reported_content_length = _validate_response_headers(
            status=response_status,
            headers=response_headers,
        )
        if not header_errors:
            stage = "body_file_open"
            body.parent.mkdir(parents=True, exist_ok=True)
            output = body.open("xb")
            body_file_created = True
            body_read_started = True
            stage = "body_read_and_write"
            while body_bytes < WHEEL_ALLOWANCE_BYTES:
                remaining = WHEEL_ALLOWANCE_BYTES - body_bytes
                chunk = response.read(min(1024 * 1024, remaining))
                if not chunk:
                    body_complete = True
                    break
                body_bytes += len(chunk)
                digest.update(chunk)
                written = output.write(chunk)
                if written != len(chunk):
                    raise OSError(f"short body write: {written} != {len(chunk)}")
    except Exception as error:  # noqa: BLE001 - the failed request is retained evidence.
        failure_events.append(_failure(stage, error))
    finally:
        if output is not None:
            try:
                output.flush()
                os.fsync(output.fileno())
            except Exception as error:  # noqa: BLE001 - finalization is evidence.
                failure_events.append(_failure("body_file_sync", error))
            try:
                output.close()
            except Exception as error:  # noqa: BLE001 - finalization is evidence.
                failure_events.append(_failure("body_file_close", error))
        if response is not None:
            try:
                response.close()
            except Exception as error:  # noqa: BLE001 - finalization is evidence.
                failure_events.append(_failure("response_close", error))
        if connection is not None:
            try:
                connection.close()
            except Exception as error:  # noqa: BLE001 - finalization is evidence.
                failure_events.append(_failure("connection_close", error))

    body_sha256 = digest.hexdigest()
    retained_body_bytes = 0
    retained_body_sha256 = None
    if body_file_created:
        try:
            retained_body_bytes, retained_body_sha256 = _sha256_file(body)
        except Exception as error:  # noqa: BLE001 - retained-file inspection is evidence.
            failure_events.append(_failure("retained_body_verification", error))
    retained_body_matches_received = (
        body_file_created
        and retained_body_bytes == body_bytes
        and retained_body_sha256 == body_sha256
    )
    validation_errors = list(header_errors)
    if failure_events:
        validation_errors.extend(
            f"{event['stage']}: {event['type']}: {event['message']}" for event in failure_events
        )
    elif not response_received or response_status is None:
        validation_errors.append("no HTTP response was received")
    elif not header_errors:
        if not body_complete:
            validation_errors.append(
                f"response did not end within the {WHEEL_ALLOWANCE_BYTES}-byte allowance"
            )
        if body_bytes != PINNED_WHEEL_BYTES:
            validation_errors.append(
                f"full-wheel body length differs: {body_bytes} != {PINNED_WHEEL_BYTES}"
            )
        if body_sha256 != PINNED_WHEEL_SHA256:
            validation_errors.append(
                f"full-wheel body sha256 differs: {body_sha256} != {PINNED_WHEEL_SHA256}"
            )
        if not retained_body_matches_received:
            validation_errors.append("retained body differs from the received body stream")

    ended_at = datetime.now(UTC).isoformat()
    record = {
        "schema": "nisayon.a1-runtime-full-wheel-response.v1",
        "case": "a1-runtime-001",
        "recorded_at": recorded_at,
        "source_commit": source_commit,
        "publisher_identity": publisher_identity,
        "resource_guard": resource_guard,
        "request": {
            "method": "GET",
            "url": url,
            "target": target,
            "headers": sorted(request_headers.items()),
            "automatic_redirects": 0,
            "automatic_retries": 0,
            "socket_timeout_seconds": socket_timeout_seconds,
        },
        "response": {
            "received": response_received,
            "status": response_status,
            "reason": response_reason,
            "headers": response_headers,
            "reported_content_length": reported_content_length,
            "strong_etag": response_strong_etag,
            "body_path": str(body),
            "body_file_created": body_file_created,
            "body_read_started": body_read_started,
            "body_complete_within_allowance": body_complete,
            "body_bytes_read": body_bytes,
            "body_sha256": body_sha256,
            "retained_body_bytes": retained_body_bytes,
            "retained_body_sha256": retained_body_sha256,
            "retained_body_matches_received": retained_body_matches_received,
            "transport_failure": (
                f"{failure_events[0]['type']}: {failure_events[0]['message']}"
                if failure_events
                else None
            ),
            "failure_events": failure_events,
            "unread_response_body_bytes": (
                "unknown" if response_received and not body_read_started else 0
            ),
        },
        "validation": {
            "passed": not validation_errors,
            "errors": validation_errors,
            "identity_rule": (
                "the retained publisher record, requested URL, reported length, received "
                "length and complete received-body SHA-256 must all match the frozen pin"
            ),
        },
        "accounting": {
            "application_responses": 1 if response_received else 0,
            "response_body_bytes_read": body_bytes,
            "wheel_allowance_bytes": WHEEL_ALLOWANCE_BYTES,
            "network_protocol_and_unread_body_bytes": None,
        },
        "timing": {
            "started_at": started_at,
            "ended_at": ended_at,
            "wall_seconds": time.perf_counter() - start_wall,
            "process_cpu_seconds": time.process_time() - start_cpu,
        },
        "operations": {
            "package_installations": 0,
            "environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
            "attempt_slots_consumed": 0,
        },
        "boundary": (
            "one direct request only; redirects and invalid headers stop before body read; "
            "there is no retry; installation and archive inspection are separate operations"
        ),
        "publication": "private; no push or publication",
    }
    return record, not validation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--publisher-record", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--body", type=Path, required=True)
    parser.add_argument("--socket-timeout-seconds", type=float, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    record, passed = acquire_once(
        url=args.url,
        publisher_record=args.publisher_record,
        receipt=args.receipt,
        body=args.body,
        socket_timeout_seconds=args.socket_timeout_seconds,
        recorded_at=args.recorded_at,
        source_commit=args.source_commit,
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
                "response_body_bytes_read": record["accounting"]["response_body_bytes_read"],
                "body_sha256": record["response"]["body_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
