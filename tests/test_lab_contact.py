"""Native vertical slice, refusal paths, retained failures and local HTTP boundary."""

import copy
import hashlib
import http.client
import json
import threading
import time

import pytest

from nisayon.engine.io import canonical_bytes, decode_json, digest
from nisayon.lab import capabilities, execute, experiment, inspect_packet
from nisayon.lab.protocol import validate_experiment
from nisayon.lab.service import make_server


def reseal(path, name, mutate):
    value = decode_json((path / name).read_bytes())
    mutate(value)
    raw = canonical_bytes(value)
    (path / name).write_bytes(raw)
    manifest = decode_json((path / "manifest.json").read_bytes())
    for entry in manifest["files"]:
        if entry["path"] == name:
            entry.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (path / "manifest.json").write_bytes(canonical_bytes(manifest))


def test_native_contact_and_exact_reproduction(tmp_path):
    declaration = experiment()
    first = execute(declaration, tmp_path / "first")
    second = execute(declaration, tmp_path / "second")
    a = inspect_packet(tmp_path / "first", expected_sha256=first["packet_sha256"])
    b = inspect_packet(tmp_path / "second", expected_sha256=second["packet_sha256"])
    assert a["traces"] == b["traces"]
    assert first["measurements"] == 244
    assert first["qualification"]["verdict"] == "rejected"
    assert first["qualification"]["deployment_decision"] == "unresolved"
    assert {t["initial_state_sha256"] for t in a["traces"]}.__len__() == 1
    for role, friction in (("reference", 0.3), ("candidate", 0.45)):
        fit = a["analysis"]["estimates"][role]
        assert fit["gain"] == pytest.approx(1, abs=0.01)
        assert fit["effective_friction"] == pytest.approx(friction, abs=0.02)
    with pytest.raises(FileExistsError):
        execute(declaration, tmp_path / "first")


def test_equivalence_uses_existing_kernel(tmp_path):
    params = experiment()["spec"]["parameters"]
    params["candidate_friction"] = params["reference_friction"]
    result = execute(experiment(params), tmp_path / "equal")
    assert result["qualification"]["verdict"] == "supported"
    assert result["qualification"]["deployment_decision"] == "unresolved"


@pytest.mark.parametrize(
    "key,value",
    [
        ("mass_kg", True),
        ("mass_kg", float("nan")),
        ("duration_s", 0.102),
        ("low_force_n", 9),
        ("candidate_gain", -1),
    ],
)
def test_parameters_refuse_unsupported_values(key, value):
    params = experiment()["spec"]["parameters"]
    params[key] = value
    with pytest.raises(ValueError):
        experiment(params)


def test_semantic_identity_and_stale_source():
    value = experiment()
    assert experiment() == value
    changed = copy.deepcopy(value)
    changed["spec"]["parameters"]["candidate_friction"] = 0.5
    with pytest.raises(ValueError, match="identity"):
        validate_experiment(changed)
    changed["experiment_id"] = digest(changed["spec"])
    assert validate_experiment(changed)["experiment_id"] != value["experiment_id"]
    changed["spec"]["producer"]["contact.py"] = "0" * 64
    changed["experiment_id"] = digest(changed["spec"])
    with pytest.raises(ValueError, match="source"):
        validate_experiment(changed)


@pytest.mark.parametrize("partial", [False, True])
def test_cancellation_retains_partial_packet_and_unresolved(tmp_path, partial):
    stopped = threading.Event()
    if not partial:
        stopped.set()
    result = execute(
        experiment(), tmp_path / "cancel", cancel=stopped.is_set, progress=lambda _: stopped.set()
    )
    assert result["status"] == "cancelled"
    assert result["qualification"]["verdict"] == "unresolved"
    packet = inspect_packet(tmp_path / "cancel")
    assert bool(packet["traces"]) is partial
    assert all(v["status"] == "unresolved" for v in packet["analysis"]["estimates"].values())


def test_native_failure_is_retained(tmp_path, monkeypatch):
    import mujoco

    monkeypatch.setattr(
        mujoco, "mj_step", lambda *_: (_ for _ in ()).throw(RuntimeError("injected native failure"))
    )
    result = execute(experiment(), tmp_path / "failure")
    assert result["status"] == "failed"
    assert (
        inspect_packet(tmp_path / "failure")["result"]["qualification"]["verdict"] == "unresolved"
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "corrupt", "schema", "timestamp", "force", "initial", "decision"]
)
def test_corruption_and_semantic_forgery_refused(tmp_path, mutation):
    path = tmp_path / "packet"
    execute(experiment(), path)
    if mutation == "missing":
        (path / "traces.json").unlink()
    elif mutation == "corrupt":
        (path / "traces.json").write_bytes(b"[]")
    elif mutation == "schema":
        reseal(path, "experiment.json", lambda x: x["spec"].update(schema="future"))
    elif mutation == "timestamp":
        reseal(path, "traces.json", lambda x: x[0]["rows"][1].update(t_s=0.006))
    elif mutation == "force":
        reseal(path, "traces.json", lambda x: x[0]["rows"][1].update(applied_n=7))
    elif mutation == "initial":
        reseal(path, "initial-state.json", lambda x: x["values"].__setitem__(1, 5))
    else:
        reseal(path, "result.json", lambda x: x["qualification"].update(verdict="supported"))
    with pytest.raises(ValueError):
        inspect_packet(path)


def test_insufficient_excitation_and_stiction_are_unresolved(tmp_path):
    params = experiment()["spec"]["parameters"]
    params["high_force_n"] = params["low_force_n"] + 0.001
    execute(experiment(params), tmp_path / "weak")
    assert all(
        v["status"] == "unresolved"
        for v in inspect_packet(tmp_path / "weak")["analysis"]["estimates"].values()
    )
    params.update(
        reference_friction=1.0,
        candidate_friction=1.0,
        mass_kg=1.0,
        low_force_n=1.0,
        high_force_n=2.0,
    )
    execute(experiment(params), tmp_path / "stiction")
    assert all(
        v["status"] == "unresolved"
        for v in inspect_packet(tmp_path / "stiction")["analysis"]["estimates"].values()
    )


def test_loopback_service_validates_identity_and_refuses_cross_origin(tmp_path):
    server = make_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    def request(method, path, data=None, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        client.request(
            method,
            path,
            body=None if data is None else canonical_bytes(data),
            headers=headers or {},
        )
        response = client.getresponse()
        raw = response.read()
        status = response.status
        client.close()
        return status, json.loads(raw)

    try:
        status, caps = request("GET", "/api/lab/capabilities")
        assert status == 200 and caps["instruments"][0]["executable"]
        token = caps["session"]
        headers = {"Content-Type": "application/json", "X-Nisayon-Session": token}
        params = caps["instruments"][0]["default"]["spec"]["parameters"]
        assert (
            request("POST", "/api/lab/validate", params, {"Content-Type": "application/json"})[0]
            == 403
        )
        assert (
            request(
                "POST", "/api/lab/validate", params, {**headers, "Origin": "https://evil.example"}
            )[0]
            == 403
        )
        assert request("GET", "/api/lab/capabilities", headers={"Host": "evil.example"})[0] == 403
        status, value = request("POST", "/api/lab/validate", params, headers)
        assert status == 200
        assert (
            request(
                "POST", "/api/lab/runs", {"parameters": params, "expected_id": "0" * 64}, headers
            )[0]
            == 400
        )
        status, run = request(
            "POST",
            "/api/lab/runs",
            {
                "parameters": {
                    k: int(v) if float(v).is_integer() else v for k, v in params.items()
                },
                "expected_id": value["experiment_id"],
            },
            headers,
        )
        assert status == 202
        for _ in range(100):
            status, run = request("GET", "/api/lab/runs/" + run["id"])
            if run["status"] not in {"queued", "running"}:
                break
            time.sleep(0.01)
        assert run["status"] == "complete"
        status, packet = request("GET", "/api/lab/runs/" + run["id"] + "/packet")
        assert status == 200 and packet["integrity"] == "verified"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_no_public_or_arbitrary_execution_origin(tmp_path):
    assert capabilities()["execution"] == "local_registered_protocols"
    with pytest.raises(ValueError, match="loopback"):
        make_server(tmp_path, allow_origin="https://customer.example")


def test_historical_presentation_revision_is_readable_not_executable():
    from nisayon.lab.protocol import PREVIOUS_PROTOCOL

    value = experiment()
    value["spec"]["protocol"] = copy.deepcopy(PREVIOUS_PROTOCOL)
    value["spec"]["protocol_sha256"] = digest(PREVIOUS_PROTOCOL)
    value["experiment_id"] = digest(value["spec"])
    assert validate_experiment(value, executable=False) == value
    with pytest.raises(ValueError, match="unsupported protocol"):
        validate_experiment(value)


def test_published_envelope_schemas_match_runtime():
    from pathlib import Path

    import jsonschema

    root = Path(__file__).resolve().parents[1] / "schemas/lab"
    for name, value in (("experiment", experiment()), ("capabilities", capabilities())):
        schema = decode_json((root / f"{name}.v1.json").read_bytes())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(value, schema)
    invalid = experiment()
    invalid["spec"]["parameters"]["mass_kg"] = "0.4"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, decode_json((root / "experiment.v1.json").read_bytes()))
