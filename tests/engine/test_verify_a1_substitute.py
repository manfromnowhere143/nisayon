import hashlib
import importlib.util
from pathlib import Path

import pytest

VERIFY_SCRIPT = Path("scripts/experiments/verify_a1_substitute.py")
SPEC = importlib.util.spec_from_file_location("verify_a1_substitute", VERIFY_SCRIPT)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)
VerificationError = verifier.VerificationError
parse_header_chain = verifier.parse_header_chain
verify_and_promote = verifier.verify_and_promote


def _headers(path: Path, *, length: int, redirects: int = 1) -> Path:
    blocks = []
    for index in range(redirects):
        blocks.append(f"HTTP/2 302 Found\r\nlocation: https://storage.example/{index}\r\n")
    blocks.append(f"HTTP/2 200 OK\r\ncontent-length: {length}\r\n")
    path.write_text("\r\n".join(blocks) + "\r\n")
    return path


def test_parse_header_chain_keeps_but_excludes_transport_tunnel(tmp_path):
    headers = tmp_path / "headers"
    headers.write_text(
        "HTTP/1.1 200 Connection established\r\n\r\nHTTP/2 200 OK\r\ncontent-length: 7\r\n\r\n"
    )

    parsed = parse_header_chain(headers)

    assert [item["status"] for item in parsed] == [200, 200]
    assert [item["transport_tunnel"] for item in parsed] == [True, False]


def test_verify_promotes_exact_body_without_overwrite(tmp_path):
    body = b"payload"
    partial = tmp_path / "payload.partial"
    partial.write_bytes(body)
    destination = tmp_path / "payload.hdf5"

    result = verify_and_promote(
        partial=partial,
        destination=destination,
        headers=_headers(tmp_path / "headers", length=len(body)),
        expected_bytes=len(body),
        expected_sha256=hashlib.sha256(body).hexdigest(),
        response_limit=3,
    )

    assert result["accepted"] is True
    assert result["application_response_statuses"] == [302, 200]
    assert not partial.exists()
    assert destination.read_bytes() == body


@pytest.mark.parametrize("failure", ["length", "digest", "responses", "destination"])
def test_verify_preserves_partial_on_failure(tmp_path, failure):
    body = b"payload"
    partial = tmp_path / "payload.partial"
    partial.write_bytes(body)
    destination = tmp_path / "payload.hdf5"
    expected_bytes = len(body)
    expected_sha256 = hashlib.sha256(body).hexdigest()
    redirects = 1
    if failure == "length":
        expected_bytes += 1
    elif failure == "digest":
        expected_sha256 = "0" * 64
    elif failure == "responses":
        redirects = 3
    elif failure == "destination":
        destination.write_bytes(b"held")

    with pytest.raises(VerificationError):
        verify_and_promote(
            partial=partial,
            destination=destination,
            headers=_headers(tmp_path / "headers", length=len(body), redirects=redirects),
            expected_bytes=expected_bytes,
            expected_sha256=expected_sha256,
            response_limit=3,
        )

    assert partial.read_bytes() == body
    if failure == "destination":
        assert destination.read_bytes() == b"held"
