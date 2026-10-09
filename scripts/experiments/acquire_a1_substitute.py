"""Perform the one prospectively reserved A1 substitute-dataset GET."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from pathlib import Path

ALLOWED_HOST_SUFFIXES = ("huggingface.co", "hf.co")


def allowed_https_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == suffix or host.endswith(f".{suffix}") for suffix in ALLOWED_HOST_SUFFIXES
    )


def response_record(code: int, reason: str, headers: Message) -> dict:
    return {
        "status": int(code),
        "reason": str(reason or ""),
        "headers": [(name, value) for name, value in headers.items()],
    }


def render_header_chain(responses: list[dict]) -> bytes:
    blocks = []
    for response in responses:
        lines = [f"HTTP/1.1 {response['status']} {response['reason']}".rstrip()]
        lines.extend(f"{name}: {value}" for name, value in response["headers"])
        blocks.append("\r\n".join(lines))
    return ("\r\n\r\n".join(blocks) + "\r\n\r\n").encode("iso-8859-1")


class RecordingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, responses: list[dict], maximum_responses: int):
        super().__init__()
        self.responses = responses
        self.maximum_responses = maximum_responses

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_https_url(newurl):
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                f"redirect left the frozen HTTPS publisher allowlist: {newurl}",
                headers,
                fp,
            )
        if len(self.responses) >= self.maximum_responses:
            raise urllib.error.HTTPError(
                req.full_url, code, "reserved HTTP response count exhausted", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)

    def http_error_302(self, req, fp, code, msg, headers):
        self.responses.append(response_record(code, msg, headers))
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def acquire(
    *,
    url: str,
    partial: Path,
    headers_path: Path,
    expected_bytes: int,
    expected_sha256: str,
    maximum_responses: int,
    socket_timeout_seconds: float,
) -> dict:
    if not allowed_https_url(url) or urllib.parse.urlsplit(url).hostname != "huggingface.co":
        raise ValueError("the initial URL is not the frozen huggingface.co HTTPS endpoint")
    if partial.exists() or partial.is_symlink():
        raise FileExistsError(f"refusing to overwrite partial path {partial}")
    if headers_path.exists() or headers_path.is_symlink():
        raise FileExistsError(f"refusing to overwrite header path {headers_path}")
    if maximum_responses < 1:
        raise ValueError("maximum_responses must be positive")

    partial.parent.mkdir(parents=True, exist_ok=True)
    headers_path.parent.mkdir(parents=True, exist_ok=True)
    responses: list[dict] = []
    handler = RecordingRedirectHandler(responses, maximum_responses)
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "Nisayon-A1-evidence-acquisition/1.0",
        },
        method="GET",
    )
    started = time.monotonic()
    stream = None
    try:
        stream = opener.open(request, timeout=socket_timeout_seconds)
        responses.append(response_record(stream.status, stream.reason, stream.headers))
        if len(responses) > maximum_responses:
            raise RuntimeError("reserved HTTP response count exhausted")
        if stream.status != 200:
            raise RuntimeError(f"final HTTP status is {stream.status}, not 200")
        content_length = stream.headers.get("Content-Length")
        if content_length is None:
            raise RuntimeError("final response omitted Content-Length; body was not read")
        try:
            reported_bytes = int(content_length)
        except ValueError as error:
            raise RuntimeError(
                "final Content-Length is not an integer; body was not read"
            ) from error
        if reported_bytes != expected_bytes:
            raise RuntimeError(
                f"final Content-Length differs: {reported_bytes} != {expected_bytes}; body was not read"
            )

        digest = hashlib.sha256()
        body_bytes = 0
        with partial.open("xb") as output:
            while chunk := stream.read(1024 * 1024):
                body_bytes += len(chunk)
                if body_bytes > expected_bytes:
                    raise RuntimeError("response body exceeded the frozen byte count")
                digest.update(chunk)
                output.write(chunk)
        body_sha256 = digest.hexdigest()
        if body_bytes != expected_bytes:
            raise RuntimeError(f"response body length differs: {body_bytes} != {expected_bytes}")
        if body_sha256 != expected_sha256:
            raise RuntimeError(f"response body sha256 differs: {body_sha256} != {expected_sha256}")
        return {
            "status": "downloaded_and_locally_matched",
            "application_response_statuses": [response["status"] for response in responses],
            "application_responses": len(responses),
            "redirects": len(responses) - 1,
            "reported_bytes": reported_bytes,
            "body_bytes": body_bytes,
            "body_sha256": body_sha256,
            "wall_seconds": time.monotonic() - started,
            "partial": str(partial),
        }
    finally:
        if stream is not None:
            stream.close()
        if responses and not headers_path.exists():
            headers_path.write_bytes(render_header_chain(responses))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--partial", type=Path, required=True)
    parser.add_argument("--headers", type=Path, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--maximum-responses", type=int, required=True)
    parser.add_argument("--socket-timeout-seconds", type=float, required=True)
    args = parser.parse_args()
    try:
        result = acquire(
            url=args.url,
            partial=args.partial,
            headers_path=args.headers,
            expected_bytes=args.expected_bytes,
            expected_sha256=args.expected_sha256,
            maximum_responses=args.maximum_responses,
            socket_timeout_seconds=args.socket_timeout_seconds,
        )
    except Exception as error:  # noqa: BLE001 - retain an exact failed acquisition outcome.
        print(
            json.dumps(
                {
                    "status": "failed_no_retry",
                    "failure": f"{type(error).__name__}: {error}",
                    "partial_exists": args.partial.is_file(),
                    "partial_bytes": args.partial.stat().st_size if args.partial.is_file() else 0,
                    "headers_retained": args.headers.is_file(),
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
