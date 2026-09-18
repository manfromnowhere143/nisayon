"""Measure local agent capabilities without a model call or reserved-case access.

Only generated public canaries are read. A successful sandbox probe is not
qualification of an end-to-end solver, model identity, token ceiling or custody.
"""

from __future__ import annotations

import argparse
import json
import selectors
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.identity import code_identity
from nisayon.engine.io import digest, write_json


def probe(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    public, excluded = output / "public", output / "excluded"
    public.mkdir()
    excluded.mkdir()
    (public / "canary.txt").write_text("nisayon-public-canary\n")
    (excluded / "canary.txt").write_text("nisayon-excluded-canary\n")
    (public / "outside-link.txt").symlink_to(excluded / "canary.txt")
    binary = shutil.which("codex")
    if binary is None:
        raise RuntimeError("No local Codex CLI; no substitute provider selected")
    version = subprocess.check_output([binary, "--version"], text=True).strip()
    # CLI 0.154 rejects the older readOnly.access shape still shown on the
    # app-server page. Use its generated schema and named permission profiles.
    profile_name = "nisayon_canary_probe"
    policy = {
        "filesystem": {":root": "deny", ":minimal": "read", str(public): "read"},
        "network": {"enabled": False},
    }
    filesystem_toml = ",".join(
        json.dumps(k) + '="' + v + '"' for k, v in policy["filesystem"].items()
    )
    profile_override = (
        f"permissions.{profile_name}={{filesystem={{{filesystem_toml}}},network={{enabled=false}}}}"
    )
    protocol = {
        "schema": "nisayon.agent-boundary-probe.v2",
        "frozen_at": datetime.now(UTC).isoformat(),
        "code": code_identity(),
        "cli": {"path": binary, "version": version},
        "permission_profile": {"id": profile_name, "rules": policy},
        "steps": ["initialize", "model/list", "read_public", "deny_excluded", "deny_symlink"],
        "budgets": {"request_wall_s": 20, "model_calls": 0, "simulator_runs": 0},
        "expected_new_output_bytes_upper_bound": 200000,
        "acceptance": "Public canary readable; excluded canary and symlink target denied. No model/solver qualification inferred.",
        "source": "https://learn.chatgpt.com/docs/permissions",
    }
    write_json(output / "protocol.json", protocol)
    result = {
        "protocol_sha256": digest(protocol),
        "steps": [],
        "model_calls": 0,
        "simulator_runs": 0,
        "agent_adapter_ready": False,
        "provider_charges": None,
        "human_time_s": None,
    }
    start = time.perf_counter()
    with (output / "server.stderr.log").open("x") as log:
        process = subprocess.Popen(
            [
                binary,
                "app-server",
                "--stdio",
                "-c",
                profile_override,
                "-c",
                f'default_permissions="{profile_name}"',
            ],
            cwd=public,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            bufsize=1,
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        counter = 0

        def send(message):
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()

        def request(method, params):
            nonlocal counter
            counter += 1
            send({"id": counter, "method": method, "params": params})
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if not selector.select(max(0, deadline - time.monotonic())):
                    break
                line = process.stdout.readline()
                if not line:
                    raise RuntimeError("Local app server exited before replying")
                message = json.loads(line)
                if message.get("id") == counter:
                    return message
            raise TimeoutError("Local app-server request: " + method)

        try:
            result["steps"].append(
                {
                    "name": "initialize",
                    "response": request(
                        "initialize",
                        {
                            "clientInfo": {"name": "nisayon_boundary_probe", "version": "0.1.0"},
                            "capabilities": {"experimentalApi": True},
                        },
                    ),
                }
            )
            send({"method": "initialized"})
            listed = request("model/list", {"limit": 100, "includeHidden": False})
            # Model IDs/capabilities only; never request or retain auth material.
            result["steps"].append({"name": "model/list", "response": listed})
            for name, path in (
                ("read_public", public / "canary.txt"),
                ("deny_excluded", excluded / "canary.txt"),
                ("deny_symlink", public / "outside-link.txt"),
            ):
                response = request(
                    "command/exec",
                    {
                        "command": ["/bin/cat", str(path)],
                        "cwd": str(public),
                        "permissionProfile": profile_name,
                        "timeoutMs": 10000,
                    },
                )
                result["steps"].append({"name": name, "response": response})
            by_name = {s["name"]: s["response"].get("result", {}) for s in result["steps"]}
            result["restricted_reads_demonstrated"] = (
                by_name["read_public"].get("exitCode") == 0
                and by_name["read_public"].get("stdout") == "nisayon-public-canary\n"
                and all(
                    by_name[name].get("exitCode") not in (None, 0)
                    and "nisayon-excluded-canary" not in by_name[name].get("stdout", "")
                    for name in ("deny_excluded", "deny_symlink")
                )
            )
        except (OSError, ValueError, RuntimeError, TimeoutError) as error:
            result["error"] = f"{type(error).__name__}: {error}"
            result["restricted_reads_demonstrated"] = False
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            selector.close()
    result["measured_probe_wall_s"] = time.perf_counter() - start
    write_json(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
