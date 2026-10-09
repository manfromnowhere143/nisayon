import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path("scripts/experiments/acquire_a1_wheel_full.py")
SPEC = importlib.util.spec_from_file_location("acquire_a1_wheel_full", SCRIPT)
acquire = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = acquire
SPEC.loader.exec_module(acquire)


class FakeResponse:
    def __init__(self, *, status=200, reason="OK", headers=(), body=b""):
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


class FailingResponse(FakeResponse):
    def read(self, amount=None):
        if self._offset:
            raise OSError("synthetic interrupted body")
        return super().read(2)


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


@pytest.fixture(autouse=True)
def _synthetic_pin(tmp_path, monkeypatch):
    body = b"synthetic-wheel"
    digest = hashlib.sha256(body).hexdigest()
    document = {
        "schema": "nisayon.a1-runtime-source-delivery.v1",
        "case": "a1-runtime-001",
        "release": {
            "archives": [
                {
                    "filename": acquire.PINNED_WHEEL_FILENAME,
                    "url": acquire.PINNED_WHEEL_URL,
                    "bytes": len(body),
                    "sha256": digest,
                }
            ]
        },
    }
    payload = (json.dumps(document, sort_keys=True) + "\n").encode()
    publisher_record = tmp_path / "source-delivery.json"
    publisher_record.write_bytes(payload)
    monkeypatch.setattr(acquire, "PINNED_WHEEL_BYTES", len(body))
    monkeypatch.setattr(acquire, "PINNED_WHEEL_SHA256", digest)
    monkeypatch.setattr(
        acquire, "PINNED_PUBLISHER_RECORD_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(acquire, "WHEEL_ALLOWANCE_BYTES", len(body) + 4)
    FakeConnection.response = None
    FakeConnection.failure = None
    FakeConnection.instances = []
    return body, publisher_record


def _call(tmp_path, synthetic_pin):
    _, publisher_record = synthetic_pin
    return acquire.acquire_once(
        url=acquire.PINNED_WHEEL_URL,
        publisher_record=publisher_record,
        receipt=tmp_path / "receipt.json",
        body=tmp_path / "wheel.partial",
        socket_timeout_seconds=5,
        recorded_at="2026-09-21T00:00:00Z",
        source_commit="a" * 40,
        connection_factory=FakeConnection,
        disk_usage_factory=lambda _path: SimpleNamespace(
            total=100_000_000_000,
            used=10_000_000_000,
            free=(
                acquire.MINIMUM_FREE_DISK_BYTES
                + acquire.PINNED_WHEEL_BYTES
                + acquire.TEMPORARY_RESERVATION_BYTES
                + acquire.ISOLATED_ENVIRONMENT_AND_CACHE_BYTES
                + 123_456
            ),
        ),
    )


def test_exact_full_wheel_passes_and_is_bound_to_publisher_record(tmp_path, _synthetic_pin):
    body, publisher_record = _synthetic_pin
    FakeConnection.response = FakeResponse(
        headers=[("Content-Length", str(len(body))), ("ETag", '"synthetic-v1"')],
        body=body,
    )

    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is True
    assert (tmp_path / "wheel.partial").read_bytes() == body
    assert (
        record["publisher_identity"]["record_sha256"]
        == hashlib.sha256(publisher_record.read_bytes()).hexdigest()
    )
    assert record["publisher_identity"]["wheel"]["sha256"] == hashlib.sha256(body).hexdigest()
    assert record["response"]["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["response"]["retained_body_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["response"]["retained_body_matches_received"] is True
    assert record["accounting"] == {
        "application_responses": 1,
        "response_body_bytes_read": len(body),
        "wheel_allowance_bytes": len(body) + 4,
        "network_protocol_and_unread_body_bytes": None,
    }
    assert record["operations"]["attempt_slots_consumed"] == 0
    assert record["resource_guard"]["passed"] is True
    assert (
        record["resource_guard"]["projected_free_bytes"]
        == acquire.MINIMUM_FREE_DISK_BYTES + 123_456
    )
    instance = FakeConnection.instances[0]
    assert instance.host == "files.pythonhosted.org"
    assert instance.request_call[0] == "GET"
    assert "Range" not in instance.request_call[3]
    assert instance.request_call[3]["Accept-Encoding"] == "identity"


@pytest.mark.parametrize(
    "status,headers,expected",
    [
        (302, [("Content-Length", "0")], "status is 302"),
        (200, [], "omitted Content-Length"),
        (200, [("Content-Length", "not-an-int")], "not an integer"),
        (200, [("Content-Length", "15"), ("Content-Length", "15")], "2 Content-Length"),
        (200, [("Content-Length", "20")], "exceeds the wheel-only allowance"),
        (200, [("Content-Length", "14")], "Content-Length differs"),
        (200, [("Content-Length", "15"), ("Content-Encoding", "gzip")], "Content-Encoding"),
        (200, [("Content-Length", "15"), ("Transfer-Encoding", "chunked")], "Transfer-Encoding"),
        (200, [("Content-Length", "15"), ("Content-Range", "bytes 0-14/15")], "Content-Range"),
    ],
)
def test_invalid_response_headers_stop_before_body_read(
    tmp_path, _synthetic_pin, status, headers, expected
):
    FakeConnection.response = FakeResponse(status=status, headers=headers, body=b"error body")

    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is False
    assert record["accounting"]["application_responses"] == 1
    assert record["accounting"]["response_body_bytes_read"] == 0
    assert record["response"]["unread_response_body_bytes"] == "unknown"
    assert not (tmp_path / "wheel.partial").exists()
    assert any(expected in error for error in record["validation"]["errors"])
    assert len(FakeConnection.instances) == 1


def test_body_digest_mismatch_is_retained_and_rejected(tmp_path, _synthetic_pin):
    body, _ = _synthetic_pin
    changed = body[:-1] + bytes([body[-1] ^ 1])
    FakeConnection.response = FakeResponse(
        headers=[("Content-Length", str(len(body)))],
        body=changed,
    )

    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is False
    assert (tmp_path / "wheel.partial").read_bytes() == changed
    assert any("body sha256 differs" in error for error in record["validation"]["errors"])


def test_truncated_body_is_retained_and_rejected(tmp_path, _synthetic_pin):
    body, _ = _synthetic_pin
    FakeConnection.response = FakeResponse(
        headers=[("Content-Length", str(len(body)))],
        body=body[:-2],
    )

    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is False
    assert record["response"]["body_complete_within_allowance"] is True
    assert record["response"]["body_bytes_read"] == len(body) - 2
    assert (tmp_path / "wheel.partial").read_bytes() == body[:-2]
    assert any("body length differs" in error for error in record["validation"]["errors"])


def test_interrupted_body_preserves_prefix_and_counts_response(tmp_path, _synthetic_pin):
    body, _ = _synthetic_pin
    FakeConnection.response = FailingResponse(
        headers=[("Content-Length", str(len(body)))],
        body=body,
    )

    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is False
    assert record["accounting"]["application_responses"] == 1
    assert record["accounting"]["response_body_bytes_read"] == 2
    assert record["response"]["body_sha256"] == hashlib.sha256(body[:2]).hexdigest()
    assert record["response"]["retained_body_sha256"] == hashlib.sha256(body[:2]).hexdigest()
    assert record["response"]["retained_body_matches_received"] is True
    assert (tmp_path / "wheel.partial").read_bytes() == body[:2]
    assert record["response"]["transport_failure"] == "OSError: synthetic interrupted body"
    assert record["response"]["failure_events"] == [
        {
            "stage": "body_read_and_write",
            "type": "OSError",
            "message": "synthetic interrupted body",
        }
    ]


def test_body_over_allowance_is_capped_and_rejected(tmp_path, _synthetic_pin):
    body, _ = _synthetic_pin
    allowance = acquire.WHEEL_ALLOWANCE_BYTES
    FakeConnection.response = FakeResponse(
        headers=[("Content-Length", str(len(body)))],
        body=body + b"x" * 10,
    )

    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is False
    assert record["response"]["body_bytes_read"] == allowance
    assert record["response"]["body_complete_within_allowance"] is False
    assert (tmp_path / "wheel.partial").stat().st_size == allowance
    assert any("did not end within" in error for error in record["validation"]["errors"])


def test_transport_failure_before_response_consumes_no_response(tmp_path, _synthetic_pin):
    FakeConnection.failure = OSError("synthetic connection failure")

    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is False
    assert record["accounting"]["application_responses"] == 0
    assert record["accounting"]["response_body_bytes_read"] == 0
    assert not (tmp_path / "wheel.partial").exists()
    assert record["response"]["transport_failure"] == "OSError: synthetic connection failure"


def test_retained_body_verification_failure_invalidates_transfer(
    tmp_path, _synthetic_pin, monkeypatch
):
    body, _ = _synthetic_pin
    FakeConnection.response = FakeResponse(
        headers=[("Content-Length", str(len(body)))],
        body=body,
    )

    def fail_retained_verification(_path):
        raise OSError("synthetic retained read failure")

    monkeypatch.setattr(acquire, "_sha256_file", fail_retained_verification)
    record, passed = _call(tmp_path, _synthetic_pin)

    assert passed is False
    assert (tmp_path / "wheel.partial").read_bytes() == body
    assert record["response"]["failure_events"] == [
        {
            "stage": "retained_body_verification",
            "type": "OSError",
            "message": "synthetic retained read failure",
        }
    ]


@pytest.mark.parametrize("existing", ["receipt", "body"])
def test_existing_output_is_refused_before_connection(tmp_path, _synthetic_pin, existing):
    _, publisher_record = _synthetic_pin
    receipt = tmp_path / "receipt.json"
    body = tmp_path / "wheel.partial"
    (receipt if existing == "receipt" else body).write_bytes(b"held")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        acquire.acquire_once(
            url=acquire.PINNED_WHEEL_URL,
            publisher_record=publisher_record,
            receipt=receipt,
            body=body,
            socket_timeout_seconds=5,
            recorded_at="2026-09-21T00:00:00Z",
            source_commit="a" * 40,
            connection_factory=FakeConnection,
        )

    assert FakeConnection.instances == []


def test_body_and_receipt_collision_is_refused_before_connection(tmp_path, _synthetic_pin):
    _, publisher_record = _synthetic_pin
    path = tmp_path / "collision"

    with pytest.raises(acquire.AcquisitionError, match="paths must differ"):
        acquire.acquire_once(
            url=acquire.PINNED_WHEEL_URL,
            publisher_record=publisher_record,
            receipt=path,
            body=path,
            socket_timeout_seconds=5,
            recorded_at="2026-09-21T00:00:00Z",
            source_commit="a" * 40,
            connection_factory=FakeConnection,
        )

    assert FakeConnection.instances == []


def test_publisher_record_mutation_is_refused_before_connection(tmp_path, _synthetic_pin):
    _, publisher_record = _synthetic_pin
    publisher_record.write_bytes(publisher_record.read_bytes() + b" ")

    with pytest.raises(acquire.AcquisitionError, match="publisher record sha256 differs"):
        _call(tmp_path, _synthetic_pin)

    assert FakeConnection.instances == []


def test_publisher_record_with_wrong_wheel_identity_is_refused_before_connection(
    tmp_path, _synthetic_pin, monkeypatch
):
    _, publisher_record = _synthetic_pin
    document = json.loads(publisher_record.read_bytes())
    document["release"]["archives"][0]["url"] = "https://files.pythonhosted.org/wrong-wheel"
    payload = (json.dumps(document, sort_keys=True) + "\n").encode()
    publisher_record.write_bytes(payload)
    monkeypatch.setattr(
        acquire, "PINNED_PUBLISHER_RECORD_SHA256", hashlib.sha256(payload).hexdigest()
    )

    with pytest.raises(acquire.AcquisitionError, match="publisher wheel identity differs"):
        _call(tmp_path, _synthetic_pin)

    assert FakeConnection.instances == []


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"url": "https://files.pythonhosted.org/not-the-wheel"}, "URL differs"),
        ({"source_commit": "A" * 40}, "source_commit"),
        ({"recorded_at": "2026-09-21T00:00:00"}, "UTC offset"),
        ({"socket_timeout_seconds": 0}, "socket_timeout_seconds"),
    ],
)
def test_invalid_preflight_is_refused_before_connection(tmp_path, _synthetic_pin, kwargs, expected):
    _, publisher_record = _synthetic_pin
    arguments = {
        "url": acquire.PINNED_WHEEL_URL,
        "publisher_record": publisher_record,
        "receipt": tmp_path / "receipt.json",
        "body": tmp_path / "wheel.partial",
        "socket_timeout_seconds": 5,
        "recorded_at": "2026-09-21T00:00:00Z",
        "source_commit": "a" * 40,
        "connection_factory": FakeConnection,
        "disk_usage_factory": lambda _path: SimpleNamespace(
            total=100_000_000_000,
            used=10_000_000_000,
            free=20_000_000_000,
        ),
    }
    arguments.update(kwargs)

    with pytest.raises(acquire.AcquisitionError, match=expected):
        acquire.acquire_once(**arguments)

    assert FakeConnection.instances == []


def test_disk_floor_projection_is_refused_before_connection(tmp_path, _synthetic_pin):
    _, publisher_record = _synthetic_pin
    reserved = (
        acquire.PINNED_WHEEL_BYTES
        + acquire.TEMPORARY_RESERVATION_BYTES
        + acquire.ISOLATED_ENVIRONMENT_AND_CACHE_BYTES
    )

    with pytest.raises(acquire.AcquisitionError, match="would cross the frozen floor"):
        acquire.acquire_once(
            url=acquire.PINNED_WHEEL_URL,
            publisher_record=publisher_record,
            receipt=tmp_path / "receipt.json",
            body=tmp_path / "wheel.partial",
            socket_timeout_seconds=5,
            recorded_at="2026-09-21T00:00:00Z",
            source_commit="a" * 40,
            connection_factory=FakeConnection,
            disk_usage_factory=lambda _path: SimpleNamespace(
                total=100_000_000_000,
                used=10_000_000_000,
                free=acquire.MINIMUM_FREE_DISK_BYTES + reserved - 1,
            ),
        )

    assert FakeConnection.instances == []


def test_receipt_writer_is_create_only(tmp_path):
    path = tmp_path / "receipt.json"

    byte_count, digest = acquire._write_json_create_only(path, {"b": 2, "a": 1})

    assert path.read_bytes() == b'{\n  "a": 1,\n  "b": 2\n}\n'
    assert byte_count == len(path.read_bytes())
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        acquire._write_json_create_only(path, {})


def test_repository_publisher_record_matches_the_frozen_pin(monkeypatch):
    monkeypatch.setattr(acquire, "PINNED_WHEEL_BYTES", 152_011_410)
    monkeypatch.setattr(
        acquire,
        "PINNED_WHEEL_SHA256",
        "39810a9e9f193455fcb13a9b4846424abef77481ac3091892c2077c88dcdc153",
    )
    monkeypatch.setattr(
        acquire,
        "PINNED_PUBLISHER_RECORD_SHA256",
        "5a4ade478dbe844b74fb1d63dd861243c790c29618a433e4e510fbb666a76a23",
    )

    identity = acquire.verify_publisher_record(
        Path("docs/experiments/results/a1-runtime-001/source-delivery-001.json")
    )

    assert identity["wheel"]["bytes"] == 152_011_410
    assert identity["wheel"]["sha256"] == acquire.PINNED_WHEEL_SHA256
