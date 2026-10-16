#!/usr/bin/env python3
"""Qualify a pinned vla.cpp envelope collision using native CPU transport.

Requires an isolated source tree and existing clang++, pkg-config and libzmq.
Does not download, install, load a model, or run the full inference server.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import platform
import shlex
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

REVISION = "42b7ed874567cb753df19de3d726d51b5d99ae63"
SOURCES = {
    "VinRobotics/vla.cpp/src/serving/server.cpp": "0f1d0b2331f85f323d9e54c0698c9384a014d581fe634a63b6985933721bd5a8",
    "VinRobotics/vla.cpp/src/serving/request_queue.h": "19fc76d6808c63bb669fd9d24e12fe0018ef01c367a1f7b35813e61031916ffa",
    "VinRobotics/vla.cpp/tests/test_request_queue.cpp": "8aaa5cb92ddf2bf6f3716a79c11d5e7164377caf9c6ac3c1b4177a42926879fa",
    "VinRobotics/vla.cpp/LICENSE.md": "471fe2b35c9507ca4f80b21315667dd22bcd5a4816fb4eaea0524c86fe01475a",
    "zeromq/cppzmq/zmq.hpp": "1f8b641161dcf12641ae4951c2c49552de425be88d66c988ec5e85046f1320f6",
    "zeromq/cppzmq/LICENSE": "7e6db90e2e805c72b3daa77849d1cb5f1f92da0e69750c8a4aa1d86d70704748",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc() -> str:
    return datetime.now(UTC).isoformat()


def extract(source: str, signature: str) -> str:
    """Pinned functions have their outer closing brace alone in column zero."""
    if source.count(signature) != 1:
        raise ValueError(f"ambiguous function signature: {signature}")
    start = source.index(signature)
    return source[start : source.index("\n}", start) + 2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    harness = Path(__file__).with_name("vla_routing_controls.cpp").resolve()
    report: dict = {
        "schema": "nisayon.native-routing-qualification.v1",
        "started_at": utc(),
        "upstream_revision": REVISION,
        "platform": platform.platform(),
        "scope": "CPU extracted transport and unchanged native queue; no inference or robot",
        "driver_sha256": sha256(Path(__file__).read_bytes()),
        "harness_sha256": sha256(harness.read_bytes()),
        "commands": [],
        "source_sha256": {},
        "extractions": {},
        "complete_effort": {
            "comparative_effort_established": False,
            "human_labor_seconds": None,
            "provider_cost": None,
            "owner_effort_seconds": None,
        },
    }
    started = time.monotonic()

    def run(name: str, argv: list[str], timeout: int = 60) -> dict:
        before = time.monotonic()
        entry = {"name": name, "argv": argv, "started_at": utc()}
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            entry.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
        except subprocess.TimeoutExpired as exc:

            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""

            entry.update(
                exit_code=None,
                error="timeout",
                stdout=decoded(exc.stdout),
                stderr=decoded(exc.stderr),
            )
        entry["wall_seconds"] = time.monotonic() - before
        report["commands"].append(entry)
        (output / f"{name}.stdout.log").write_text(entry["stdout"])
        (output / f"{name}.stderr.log").write_text(entry["stderr"])
        return entry

    def checked(name: str, argv: list[str]) -> dict:
        entry = run(name, argv)
        if entry["exit_code"] != 0:
            raise RuntimeError(f"{name} did not complete successfully")
        return entry

    try:
        for name, expected in SOURCES.items():
            actual = sha256((source_dir / name).read_bytes())
            report["source_sha256"][name] = actual
            if actual != expected:
                raise ValueError(f"pinned source hash mismatch: {name}")
        compiler = shutil.which("clang++")
        if not compiler:
            raise RuntimeError("clang++ not available")
        checked("compiler-version", [compiler, "--version"])
        checked("libzmq-version", ["pkg-config", "--modversion", "libzmq"])
        flags = shlex.split(
            checked("libzmq-flags", ["pkg-config", "--cflags", "--libs", "libzmq"])["stdout"]
        )
        server = (source_dir / "VinRobotics/vla.cpp/src/serving/server.cpp").read_text()
        functions = []
        for signature in (
            "bool send_multipart(",
            "bool recv_multipart(",
            "std::string envelope_key(",
        ):
            function = extract(server, signature)
            report["extractions"][signature] = {
                "sha256": sha256(function.encode()),
                "line": server[: server.index(signature)].count("\n") + 1,
                "bytes": len(function.encode()),
            }
            functions.append(function)
        original_key = functions[-1]
        old = "        key.append(static_cast<const char*>(f.data()), f.size());\n        key.push_back('\\0');"
        new = (
            "        // Length framing preserves binary frame boundaries.\n"
            "        key.append(std::to_string(f.size()));\n"
            "        key.push_back(':');\n"
            "        key.append(static_cast<const char*>(f.data()), f.size());"
        )
        if original_key.count(old) != 1:
            raise ValueError("pinned key body no longer matches the proposed correction")
        corrected_key = original_key.replace(old, new)
        corrected_server = server.replace(original_key, corrected_key)
        (output / "envelope-key.patch").write_text(
            "".join(
                difflib.unified_diff(
                    server.splitlines(keepends=True),
                    corrected_server.splitlines(keepends=True),
                    fromfile="a/src/serving/server.cpp",
                    tofile="b/src/serving/server.cpp",
                )
            )
        )
        include = source_dir / "VinRobotics/vla.cpp/src"
        native_bin = output / "native-queue"
        checked(
            "compile-native-queue",
            [
                compiler,
                "-std=c++17",
                "-pthread",
                "-I",
                str(include),
                str(source_dir / "VinRobotics/vla.cpp/tests/test_request_queue.cpp"),
                "-o",
                str(native_bin),
            ],
        )
        checked("native-queue", [str(native_bin)])
        report["variants"] = {}
        license_header = server[: server.index("#include")]
        for name, key in (("original", original_key), ("corrected", corrected_key)):
            directory = output / name
            directory.mkdir()
            body = license_header + "\n\n".join(functions[:-1] + [key]) + "\n"
            (directory / "routing_functions.inc").write_text(body)
            binary = directory / "routing-controls"
            checked(
                f"compile-{name}",
                [
                    compiler,
                    "-std=c++17",
                    "-pthread",
                    "-I",
                    str(include),
                    "-I",
                    str(source_dir / "zeromq/cppzmq"),
                    "-I",
                    str(directory),
                    str(harness),
                    "-o",
                    str(binary),
                ]
                + flags,
            )
            command = run(name, [str(binary)])
            if command["exit_code"] not in (0, 1):
                raise RuntimeError(f"{name} harness execution failed")
            result = json.loads(command["stdout"])
            result["process_exit_code"] = command["exit_code"]
            result["extracted_source_sha256"] = sha256(body.encode())
            report["variants"][name] = result
        original = report["variants"]["original"]
        corrected = report["variants"]["corrected"]
        failed_names = [c["name"] for c in original["transport_cases"] if not c["passed"]]
        report["source_defect_reproduced"] = failed_names == [
            "latest_dealer_then_req",
            "latest_req_then_dealer",
        ]
        report["bounded_correction_supported"] = (
            report["source_defect_reproduced"]
            and corrected["process_exit_code"] == 0
            and corrected["transport_passed"] == 5
            and corrected["finite_injectivity"]["passed"]
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        report["finished_at"] = utc()
        report["driver_wall_seconds"] = time.monotonic() - started
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report.get(key)
                for key in (
                    "source_defect_reproduced",
                    "bounded_correction_supported",
                    "error",
                    "driver_wall_seconds",
                )
            },
            indent=2,
        )
    )
    return 0 if report.get("bounded_correction_supported") else 1


if __name__ == "__main__":
    raise SystemExit(main())
