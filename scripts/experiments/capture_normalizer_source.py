"""Execute one precommitted normalizer source request and retain its receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.normalizer_execution import validate_source_counter

REVISION = "1a1837f20538b7d7e21f977a11a5aee14f99803c"
PHASE_MAX_RESPONSES = 12
PHASE_MAX_BODY_BYTES = 2 * 1024**2
PREPARATION_RESPONSES = 4
PREPARATION_BODY_BYTES = 85_703


class RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """Count the response but never create an unreserved follow-up request."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        return None


def _read(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("Source request must be a JSON object")
    return value


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()


def _prior_usage(receipt_path: Path) -> tuple[int, int]:
    responses = PREPARATION_RESPONSES
    body_bytes = PREPARATION_BODY_BYTES
    for path in receipt_path.parent.glob("receipt-*.json"):
        if path == receipt_path:
            continue
        receipt = _read(path)
        responses += int(receipt.get("response_count", 0))
        body_bytes += int(receipt.get("body_bytes", 0))
    return responses, body_bytes


def capture(request_path: Path, output: Path, receipt_path: Path) -> dict:
    if output.exists() or receipt_path.exists():
        raise FileExistsError("Source or receipt already exists; refusing repeat acquisition")
    request_bytes = request_path.read_bytes()
    request = _read(request_path)
    if (
        request.get("schema") != "nisayon.normalizer-source-request.v1"
        or request.get("status") != "reserved_before_dispatch"
        or request.get("reserved_response_count") != 1
    ):
        raise ValueError("Source request is not a single pre-dispatch reservation")
    url = request.get("url")
    if not isinstance(url, str) or REVISION not in url:
        raise ValueError("Source request is not pinned to the required revision")
    maximum_body = request.get("maximum_response_body_bytes")
    if type(maximum_body) is not int or maximum_body <= 0:
        raise ValueError("Source request lacks a positive body limit")
    previous_responses, previous_body_bytes = _prior_usage(receipt_path)
    validate_source_counter(used=previous_responses, requested=1, maximum=PHASE_MAX_RESPONSES)

    started = datetime.now(UTC).isoformat()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    opener = urllib.request.build_opener(RefuseRedirect())
    transport = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "nisayon-normalizer-source-capture/1",
        },
    )
    try:
        response = opener.open(transport, timeout=30)
    except urllib.error.HTTPError as error:
        # Redirects and failures are responses and consume this reservation. The
        # exception is preserved for the caller; no retry occurs here.
        failure = {
            "schema": "nisayon.normalizer-source-receipt.v1",
            "request_id": request["request_id"],
            "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
            "started_at": started,
            "ended_at": datetime.now(UTC).isoformat(),
            "status": "response_failed_no_retry",
            "http_status": error.code,
            "response_count": 1,
            "body_bytes": 0,
            "location": error.headers.get("Location"),
            "wall_seconds": time.perf_counter() - wall_start,
            "process_cpu_seconds": time.process_time() - cpu_start,
        }
        write_json(receipt_path, failure)
        raise

    with response:
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) > maximum_body:
            raise ValueError("Declared response body exceeds the committed request limit")
        payload = response.read(maximum_body + 1)
        if len(payload) > maximum_body:
            raise ValueError("Response body exceeds the committed request limit")
        if previous_body_bytes + len(payload) > PHASE_MAX_BODY_BYTES:
            raise ValueError("Joint normalizer source body ceiling exceeded")
        status = response.status
        final_url = response.geturl()
        headers = {
            key: response.headers[key]
            for key in ("Content-Length", "Content-Type", "ETag", "Date", "Last-Modified")
            if response.headers.get(key) is not None
        }
    if final_url != url:
        raise ValueError("Transport followed an uncounted redirect")
    _write_once(output, payload)
    receipt = {
        "schema": "nisayon.normalizer-source-receipt.v1",
        "request_id": request["request_id"],
        "request_path": str(request_path),
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "started_at": started,
        "ended_at": datetime.now(UTC).isoformat(),
        "status": "captured",
        "url": url,
        "final_url": final_url,
        "http_status": status,
        "headers": headers,
        "response_count": 1,
        "body_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "git_blob_sha1": hashlib.sha1(
            b"blob " + str(len(payload)).encode() + b"\0" + payload
        ).hexdigest(),
        "output": str(output.resolve()),
        "output_sha256_verified": file_digest(output),
        "phase_cumulative_responses": previous_responses + 1,
        "phase_cumulative_body_bytes": previous_body_bytes + len(payload),
        "phase_max_responses": PHASE_MAX_RESPONSES,
        "phase_max_body_bytes": PHASE_MAX_BODY_BYTES,
        "wall_seconds": time.perf_counter() - wall_start,
        "process_cpu_seconds": time.process_time() - cpu_start,
        "network_overhead_bytes": None,
        "rights": "Private retained research source; upstream Apache-2.0 notice must be preserved; redistribution is not authorized by this receipt.",
    }
    write_json(receipt_path, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.request, args.output, args.receipt), sort_keys=True))


if __name__ == "__main__":
    main()
