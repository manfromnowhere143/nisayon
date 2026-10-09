import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/experiments/acquire_a1_wheel_range.py")
SPEC = importlib.util.spec_from_file_location("acquire_a1_wheel_range", SCRIPT)
acquire = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = acquire
SPEC.loader.exec_module(acquire)
STRONG_ETAG = '"synthetic-object-v1"'


class FakeResponse:
    def __init__(self, *, status=206, reason="Partial Content", headers=(), body=b""):
        self.status = status
        self.reason = reason
        self._headers = list(headers)
        self._body = body
        self._offset = 0
        self.closed = False

    def getheaders(self):
        return self._headers

    def read(self, amount=None):
        if amount is None:
            amount = len(self._body) - self._offset
        result = self._body[self._offset : self._offset + amount]
        self._offset += len(result)
        return result

    def close(self):
        self.closed = True


class FakeConnection:
    response = None
    failure = None
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.request_call = None
        self.closed = False
        type(self).instances.append(self)

    def request(self, method, url, body=None, headers=None):
        self.request_call = (method, url, body, headers)

    def getresponse(self):
        if self.failure is not None:
            raise self.failure
        return self.response

    def close(self):
        self.closed = True


class FailingResponse(FakeResponse):
    def read(self, amount=None):
        if self._offset:
            raise OSError("synthetic interrupted body")
        return super().read(2)


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeConnection.response = None
    FakeConnection.failure = None
    FakeConnection.instances = []


def _call(tmp_path, *, method="GET", start=3, end=5, body=True):
    return acquire.acquire_once(
        method=method,
        url=acquire.PINNED_WHEEL_URL,
        receipt=tmp_path / "receipt.json",
        body=tmp_path / "body.bin" if body else None,
        range_start=start if method == "GET" else None,
        range_end=end if method == "GET" else None,
        timeout_seconds=5,
        recorded_at="2026-09-21T00:00:00Z",
        source_commit="a" * 40,
        expected_etag=STRONG_ETAG if method == "GET" else None,
        connection_factory=FakeConnection,
    )


def test_exact_range_passes_and_retains_the_body(tmp_path):
    FakeConnection.response = FakeResponse(
        headers=[
            ("Content-Range", f"bytes 3-5/{acquire.PINNED_ARCHIVE_BYTES}"),
            ("Content-Length", "3"),
            ("ETag", STRONG_ETAG),
        ],
        body=b"abc",
    )

    record, passed = _call(tmp_path)

    assert passed is True
    assert (tmp_path / "body.bin").read_bytes() == b"abc"
    assert record["accounting"] == {
        "application_responses": 1,
        "response_body_bytes": 3,
        "network_protocol_overhead_bytes": None,
    }
    assert record["response"]["strong_etag"] == STRONG_ETAG
    instance = FakeConnection.instances[0]
    assert instance.host == "files.pythonhosted.org"
    assert instance.request_call[0] == "GET"
    assert instance.request_call[3]["Range"] == "bytes=3-5"
    assert instance.request_call[3]["If-Match"] == STRONG_ETAG


def test_exact_head_passes_without_a_body_path(tmp_path):
    FakeConnection.response = FakeResponse(
        status=200,
        reason="OK",
        headers=[
            ("Content-Length", str(acquire.PINNED_ARCHIVE_BYTES)),
            ("Accept-Ranges", "bytes"),
            ("ETag", STRONG_ETAG),
        ],
    )

    record, passed = _call(tmp_path, method="HEAD", body=False)

    assert passed is True
    assert record["accounting"]["application_responses"] == 1
    assert record["accounting"]["response_body_bytes"] == 0
    assert record["response"]["strong_etag"] == STRONG_ETAG


def test_server_ignoring_range_is_retained_and_rejected(tmp_path):
    FakeConnection.response = FakeResponse(
        status=200,
        reason="OK",
        headers=[("Content-Length", "4")],
        body=b"abcd",
    )

    record, passed = _call(tmp_path)

    assert passed is False
    assert record["response"]["body_bytes_read"] == 4
    assert record["response"]["body_complete_within_limit"] is False
    assert any("status is 200" in error for error in record["validation"]["errors"])
    assert any("exceeded the read limit" in error for error in record["validation"]["errors"])


@pytest.mark.parametrize(
    "headers,expected",
    [
        ([("Content-Length", "3"), ("ETag", STRONG_ETAG)], "omitted Content-Range"),
        (
            [
                ("Content-Range", f"bytes 3-6/{acquire.PINNED_ARCHIVE_BYTES}"),
                ("Content-Length", "3"),
                ("ETag", STRONG_ETAG),
            ],
            "Content-Range differs",
        ),
        (
            [
                ("Content-Range", f"bytes 3-5/{acquire.PINNED_ARCHIVE_BYTES}"),
                ("Content-Length", "3"),
                ("Content-Encoding", "gzip"),
                ("ETag", STRONG_ETAG),
            ],
            "Content-Encoding",
        ),
    ],
)
def test_range_metadata_mismatch_fails_closed(tmp_path, headers, expected):
    FakeConnection.response = FakeResponse(headers=headers, body=b"abc")

    record, passed = _call(tmp_path)

    assert passed is False
    assert any(expected in error for error in record["validation"]["errors"])


def test_transport_failure_records_zero_responses(tmp_path):
    FakeConnection.failure = OSError("synthetic transport failure")

    record, passed = _call(tmp_path)

    assert passed is False
    assert record["accounting"]["application_responses"] == 0
    assert record["response"]["transport_failure"] == "OSError: synthetic transport failure"
    assert not (tmp_path / "body.bin").exists()


def test_interrupted_body_counts_and_hashes_the_retained_prefix(tmp_path):
    FakeConnection.response = FailingResponse(
        headers=[
            ("Content-Range", f"bytes 3-5/{acquire.PINNED_ARCHIVE_BYTES}"),
            ("Content-Length", "3"),
            ("ETag", STRONG_ETAG),
        ],
        body=b"abc",
    )

    record, passed = _call(tmp_path)

    assert passed is False
    assert record["accounting"]["application_responses"] == 1
    assert record["accounting"]["response_body_bytes"] == 2
    assert record["response"]["body_sha256"] == hashlib.sha256(b"ab").hexdigest()
    assert (tmp_path / "body.bin").read_bytes() == b"ab"


def test_preflight_refuses_an_existing_output_before_connection(tmp_path):
    body = tmp_path / "body.bin"
    body.write_bytes(b"held")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        acquire.acquire_once(
            method="GET",
            url=acquire.PINNED_WHEEL_URL,
            receipt=tmp_path / "receipt.json",
            body=body,
            range_start=0,
            range_end=0,
            timeout_seconds=5,
            recorded_at="2026-09-21T00:00:00Z",
            source_commit="a" * 40,
            expected_etag=STRONG_ETAG,
            connection_factory=FakeConnection,
        )

    assert FakeConnection.instances == []


def test_preflight_refuses_one_path_for_body_and_receipt(tmp_path):
    path = tmp_path / "collision.json"

    with pytest.raises(acquire.AcquisitionError, match="paths must differ"):
        acquire.acquire_once(
            method="GET",
            url=acquire.PINNED_WHEEL_URL,
            receipt=path,
            body=path,
            range_start=0,
            range_end=0,
            timeout_seconds=5,
            recorded_at="2026-09-21T00:00:00Z",
            source_commit="a" * 40,
            expected_etag=STRONG_ETAG,
            connection_factory=FakeConnection,
        )

    assert FakeConnection.instances == []


@pytest.mark.parametrize("expected_etag", [None, "unquoted", 'W/"weak"', '"bad value"'])
def test_get_refuses_a_missing_or_non_strong_expected_etag_before_connection(
    tmp_path, expected_etag
):
    with pytest.raises(acquire.AcquisitionError, match="strong expected ETag"):
        acquire.acquire_once(
            method="GET",
            url=acquire.PINNED_WHEEL_URL,
            receipt=tmp_path / "receipt.json",
            body=tmp_path / "body.bin",
            range_start=0,
            range_end=0,
            timeout_seconds=5,
            recorded_at="2026-09-21T00:00:00Z",
            source_commit="a" * 40,
            expected_etag=expected_etag,
            connection_factory=FakeConnection,
        )

    assert FakeConnection.instances == []


def test_range_rejects_an_entity_change(tmp_path):
    FakeConnection.response = FakeResponse(
        headers=[
            ("Content-Range", f"bytes 3-5/{acquire.PINNED_ARCHIVE_BYTES}"),
            ("Content-Length", "3"),
            ("ETag", '"synthetic-object-v2"'),
        ],
        body=b"abc",
    )

    record, passed = _call(tmp_path)

    assert passed is False
    assert any("Range ETag differs" in error for error in record["validation"]["errors"])


@pytest.mark.parametrize("etag", [None, 'W/"weak"', "unquoted"])
def test_head_rejects_a_missing_or_non_strong_etag(tmp_path, etag):
    headers = [
        ("Content-Length", str(acquire.PINNED_ARCHIVE_BYTES)),
        ("Accept-Ranges", "bytes"),
    ]
    if etag is not None:
        headers.append(("ETag", etag))
    FakeConnection.response = FakeResponse(status=200, reason="OK", headers=headers)

    record, passed = _call(tmp_path, method="HEAD", body=False)

    assert passed is False
    assert any("strong ETag" in error for error in record["validation"]["errors"])
