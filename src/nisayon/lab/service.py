"""Loopback-only, single-job service for registered protocols, never arbitrary code."""

from __future__ import annotations

import io
import secrets
import shutil
import threading
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from nisayon.engine.io import canonical_bytes, decode_json

from .contact import execute, inspect_packet
from .protocol import capabilities, experiment, validate_experiment


class Laboratory:
    def __init__(self, output: Path):
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()

    def submit(self, specification: dict, expected_id: str) -> dict:
        specification = validate_experiment(specification)
        if specification["experiment_id"] != expected_id:
            raise ValueError("validated identity changed; validate again before execution")
        with self.lock:
            if any(j["status"] in {"queued", "running"} for j in self.jobs.values()):
                raise ValueError("one execution at a time; cancel or finish the active run")
            if len(self.jobs) >= 32:
                raise ValueError(
                    "session budget of 32 runs exhausted; retained evidence is preserved"
                )
            if shutil.disk_usage(self.output).free < 256 * 1024**2:
                raise ValueError("insufficient free disk for bounded execution")
            run = uuid.uuid4().hex
            stop = threading.Event()
            self.jobs[run] = {
                "id": run,
                "experiment_id": expected_id,
                "status": "queued",
                "progress": None,
                "result": None,
                "error": None,
                "stop": stop,
            }

        def progress(value):
            with self.lock:
                self.jobs[run]["progress"] = value

        def work():
            with self.lock:
                self.jobs[run]["status"] = "running"
            try:
                result = execute(
                    specification, self.output / run, cancel=stop.is_set, progress=progress
                )
                # Do not offer a sealed result until readback recomputes it.
                inspect_packet(self.output / run, expected_sha256=result["packet_sha256"])
                with self.lock:
                    self.jobs[run].update(status=result["status"], result=result)
            except Exception as error:
                with self.lock:
                    self.jobs[run].update(status="failed", error=f"{type(error).__name__}: {error}")

        threading.Thread(target=work, name="nisayon-contact", daemon=True).start()
        return self.read(run)

    def read(self, run: str) -> dict:
        with self.lock:
            if run not in self.jobs:
                raise KeyError("unknown execution")
            return {key: value for key, value in self.jobs[run].items() if key != "stop"}

    def cancel(self, run: str) -> dict:
        with self.lock:
            if run not in self.jobs:
                raise KeyError("unknown execution")
            if self.jobs[run]["status"] in {"queued", "running"}:
                self.jobs[run]["stop"].set()
        return self.read(run)

    def packet(self, run: str) -> dict:
        state = self.read(run)
        if state["result"] is None:
            raise ValueError("execution has no sealed packet yet")
        return inspect_packet(self.output / run, expected_sha256=state["result"]["packet_sha256"])

    def export(self, run: str) -> bytes:
        self.packet(run)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((self.output / run).iterdir()):
                archive.writestr(path.name, path.read_bytes())
        return stream.getvalue()


def make_server(
    output: Path, *, port: int = 8787, frontend: Path | None = None, allow_origin: str | None = None
) -> HTTPServer:
    """Only explicit loopback UI origins may use CORS. Public origins are refused."""
    if allow_origin is not None:
        parsed = urlsplit(allow_origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("development origin must be an explicit http loopback origin")
    lab = Laboratory(output)
    frontend = frontend.resolve() if frontend is not None else None

    class Handler(BaseHTTPRequestHandler):
        server_version = "NisayonLocal/1"

        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *_):
            # No request bodies, session tokens or local artifact paths in logs.
            pass

        def boundary(self, mutation=False):
            port = self.server.server_address[1]
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in hosts:
                raise PermissionError("loopback Host required")
            origins = {"http://" + host for host in hosts}
            if allow_origin:
                origins.add(allow_origin)
            origin = self.headers.get("Origin")
            if origin is not None and origin not in origins:
                raise PermissionError("origin refused")
            if mutation and not secrets.compare_digest(
                self.headers.get("X-Nisayon-Session", ""), lab.token
            ):
                raise PermissionError("local session token required")

        def respond(self, status, payload, content_type="application/json", download=None):
            raw = canonical_bytes(payload) if content_type == "application/json" else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if self.headers.get("Origin") == allow_origin and allow_origin:
                self.send_header("Access-Control-Allow-Origin", allow_origin)
                self.send_header("Vary", "Origin")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(raw)

        def fail(self, error):
            status = (
                403
                if isinstance(error, PermissionError)
                else 404
                if isinstance(error, KeyError)
                else 400
            )
            self.respond(status, {"error": str(error)})

        def do_OPTIONS(self):
            try:
                self.boundary()
                self.send_response(204)
                if self.headers.get("Origin") == allow_origin and allow_origin:
                    self.send_header("Access-Control-Allow-Origin", allow_origin)
                    self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, POST")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Nisayon-Session")
                self.send_header("Content-Length", "0")
                self.end_headers()
            except (ValueError, PermissionError) as error:
                self.fail(error)

        def do_GET(self):
            try:
                self.boundary()
                path = urlsplit(self.path).path
                if path == "/api/lab/capabilities":
                    self.respond(200, {**capabilities(), "session": lab.token})
                    return
                parts = path.strip("/").split("/")
                if parts[:3] == ["api", "lab", "runs"] and 4 <= len(parts) <= 5:
                    run = parts[3]
                    if len(parts) == 4:
                        self.respond(200, lab.read(run))
                    elif parts[4] == "packet":
                        self.respond(200, lab.packet(run))
                    elif parts[4] == "export":
                        self.respond(
                            200, lab.export(run), "application/zip", f"nisayon-contact-{run}.zip"
                        )
                    else:
                        raise KeyError("unknown operation")
                    return
                if frontend is None or path.startswith("/api/"):
                    raise KeyError("not found; this service executes registered local instruments")
                candidate = (frontend / (unquote(path).lstrip("/") or "index.html")).resolve()
                if (
                    not candidate.is_relative_to(frontend)
                    or not candidate.is_file()
                    or candidate.stat().st_size > 64 * 1024**2
                ):
                    raise KeyError("file not found")
                import mimetypes

                self.respond(
                    200,
                    candidate.read_bytes(),
                    mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
                )
            except (ValueError, TypeError, KeyError, PermissionError, OSError) as error:
                self.fail(error)

        def do_POST(self):
            try:
                self.boundary(mutation=True)
                if (
                    self.headers.get("Transfer-Encoding")
                    or self.headers.get("Content-Type") != "application/json"
                ):
                    raise ValueError("bounded application/json body required")
                size = int(self.headers.get("Content-Length", "-1"))
                if not 0 < size <= 32_000:
                    raise ValueError("request byte budget exceeded")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("incomplete request")
                data = decode_json(raw)
                path = urlsplit(self.path).path
                if path == "/api/lab/validate":
                    self.respond(200, experiment(data))
                elif path == "/api/lab/runs":
                    if not isinstance(data, dict) or set(data) != {"parameters", "expected_id"}:
                        raise ValueError("parameters and validated expected_id required")
                    # Reconstruct the registered specification at the authority
                    # boundary. JSON clients may serialize 1.0 as 1; parameters
                    # normalize before hashing. Never accept a client-rewritten
                    # protocol, producer identity or authoritative decision.
                    self.respond(202, lab.submit(experiment(data["parameters"]), data["expected_id"]))
                elif path.startswith("/api/lab/runs/") and path.endswith("/cancel"):
                    parts = path.strip("/").split("/")
                    if len(parts) != 5 or data != {}:
                        raise ValueError("invalid cancellation")
                    self.respond(200, lab.cancel(parts[3]))
                else:
                    raise KeyError("unknown operation")
            except (ValueError, TypeError, KeyError, PermissionError, OSError) as error:
                self.fail(error)

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.lab = lab
    return server
