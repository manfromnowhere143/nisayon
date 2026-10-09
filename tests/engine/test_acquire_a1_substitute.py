import importlib.util
from email.message import Message
from pathlib import Path

import pytest

ACQUIRE_SCRIPT = Path("scripts/experiments/acquire_a1_substitute.py")
SPEC = importlib.util.spec_from_file_location("acquire_a1_substitute", ACQUIRE_SCRIPT)
acquirer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquirer)


def test_allowed_https_url_is_fail_closed():
    assert acquirer.allowed_https_url("https://huggingface.co/a")
    assert acquirer.allowed_https_url("https://cas-bridge.xethub.hf.co/a")
    assert not acquirer.allowed_https_url("http://huggingface.co/a")
    assert not acquirer.allowed_https_url("https://huggingface.co.example/a")


def test_rendered_header_chain_is_parsed_by_independent_verifier(tmp_path):
    verifier_spec = importlib.util.spec_from_file_location(
        "verify_a1_substitute", Path("scripts/experiments/verify_a1_substitute.py")
    )
    verifier = importlib.util.module_from_spec(verifier_spec)
    verifier_spec.loader.exec_module(verifier)
    redirect_headers = Message()
    redirect_headers["Location"] = "https://cdn-lfs.huggingface.co/body"
    final_headers = Message()
    final_headers["Content-Length"] = "7"
    path = tmp_path / "headers"
    path.write_bytes(
        acquirer.render_header_chain(
            [
                acquirer.response_record(302, "Found", redirect_headers),
                acquirer.response_record(200, "OK", final_headers),
            ]
        )
    )

    parsed = verifier.parse_header_chain(path)

    assert [response["status"] for response in parsed] == [302, 200]
    assert parsed[-1]["headers"]["content-length"] == ["7"]


def test_redirect_handler_rejects_unknown_host_and_exhausted_reservation():
    message = Message()
    handler = acquirer.RecordingRedirectHandler([], 3)
    request = type("Request", (), {"full_url": "https://huggingface.co/start"})()
    with pytest.raises(Exception, match="left the frozen HTTPS publisher allowlist"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            message,
            "https://example.com/body",
        )

    handler.responses.extend([{}, {}, {}])
    with pytest.raises(Exception, match="reserved HTTP response count exhausted"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            message,
            "https://cdn-lfs.huggingface.co/body",
        )
