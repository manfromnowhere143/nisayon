"""Verify and atomically promote the prospectively bound A1 substitute dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import file_digest, write_json

STATUS = re.compile(r"^HTTP/\S+\s+(\d{3})(?:\s+(.*))?$")


class VerificationError(RuntimeError):
    """The acquired body does not satisfy the frozen custody contract."""


def parse_header_chain(path: Path) -> list[dict]:
    """Parse curl's retained header chain without discarding proxy tunnel records."""

    text = path.read_bytes().decode("iso-8859-1")
    responses = []
    for raw_block in re.split(r"\r?\n\r?\n", text):
        lines = [line.rstrip("\r") for line in raw_block.splitlines() if line.strip()]
        if not lines or not lines[0].startswith("HTTP/"):
            continue
        match = STATUS.match(lines[0])
        if match is None:
            raise VerificationError(f"malformed HTTP status line: {lines[0]!r}")
        headers: dict[str, list[str]] = {}
        for line in lines[1:]:
            if ":" not in line:
                raise VerificationError(f"malformed HTTP header line: {line!r}")
            name, value = line.split(":", 1)
            headers.setdefault(name.strip().lower(), []).append(value.strip())
        reason = (match.group(2) or "").strip()
        responses.append(
            {
                "status": int(match.group(1)),
                "reason": reason,
                "headers": headers,
                "transport_tunnel": reason.lower() == "connection established",
            }
        )
    if not responses:
        raise VerificationError("no HTTP response blocks retained")
    return responses


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_and_promote(
    *,
    partial: Path,
    destination: Path,
    headers: Path,
    expected_bytes: int,
    expected_sha256: str,
    response_limit: int,
) -> dict:
    """Verify the exact body and response chain, then rename without overwriting."""

    if partial.is_symlink() or not partial.is_file():
        raise VerificationError("partial acquisition is absent, non-regular, or a symlink")
    if destination.exists() or destination.is_symlink():
        raise VerificationError("destination already exists; overwrite is forbidden")
    if headers.is_symlink() or not headers.is_file():
        raise VerificationError("retained headers are absent, non-regular, or a symlink")

    responses = parse_header_chain(headers)
    application = [response for response in responses if not response["transport_tunnel"]]
    if len(application) > response_limit:
        raise VerificationError(
            f"HTTP response limit exceeded: {len(application)} > {response_limit}"
        )
    if not application or application[-1]["status"] != 200:
        raise VerificationError("the final application response is not HTTP 200")
    if any(response["status"] not in range(300, 400) for response in application[:-1]):
        raise VerificationError("a non-final application response is not a redirect")

    final_lengths = application[-1]["headers"].get("content-length", [])
    if len(final_lengths) != 1:
        raise VerificationError("the final response does not contain one Content-Length")
    try:
        content_length = int(final_lengths[0])
    except ValueError as error:
        raise VerificationError("the final Content-Length is not an integer") from error
    if content_length != expected_bytes:
        raise VerificationError(
            f"final Content-Length differs: {content_length} != {expected_bytes}"
        )

    actual_bytes = partial.stat().st_size
    actual_sha256 = sha256(partial)
    if actual_bytes != expected_bytes:
        raise VerificationError(f"body length differs: {actual_bytes} != {expected_bytes}")
    if actual_sha256 != expected_sha256:
        raise VerificationError(f"body sha256 differs: {actual_sha256} != {expected_sha256}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial.rename(destination)
    return {
        "accepted": True,
        "application_response_statuses": [response["status"] for response in application],
        "application_responses": len(application),
        "transport_tunnel_responses": len(responses) - len(application),
        "redirects": len(application) - 1,
        "final_content_length": content_length,
        "actual_bytes": destination.stat().st_size,
        "actual_sha256": file_digest(destination),
        "destination": str(destination),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partial", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--headers", type=Path, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--response-limit", type=int, required=True)
    parser.add_argument("--command-record-id", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--repository-path", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.out.exists() or args.out.is_symlink():
        raise SystemExit("refusing to overwrite an acquisition receipt")
    base = {
        "schema": "nisayon.a1-substitute-acquisition-receipt.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "command_record_id": args.command_record_id,
        "source": {
            "url": args.source_url,
            "revision": args.revision,
            "repository_path": args.repository_path,
        },
        "expected": {
            "bytes": args.expected_bytes,
            "sha256": args.expected_sha256,
            "maximum_application_responses": args.response_limit,
        },
        "headers": {
            "path": str(args.headers),
            "bytes": args.headers.stat().st_size if args.headers.is_file() else None,
            "sha256": file_digest(args.headers) if args.headers.is_file() else None,
        },
        "failure_policy": "leave the labelled partial in place and do not retry",
    }
    try:
        outcome = verify_and_promote(
            partial=args.partial,
            destination=args.destination,
            headers=args.headers,
            expected_bytes=args.expected_bytes,
            expected_sha256=args.expected_sha256,
            response_limit=args.response_limit,
        )
    except (OSError, VerificationError) as error:
        result = {**base, "accepted": False, "failure": f"{type(error).__name__}: {error}"}
        write_json(args.out, result)
        print(json.dumps(result, sort_keys=True))
        return 2

    result = {**base, **outcome}
    write_json(args.out, result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
