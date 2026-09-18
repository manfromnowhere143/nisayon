"""A finite JSON decision call for a development experiment, not a general planner.

The parent owns execution and acceptance. The model can inspect only its public
packet using a restricted CLI permission profile. Native integrations, inherited
shell credentials, project instructions and host skill discovery are disabled.
Each call has its own command record; tokens come only from that call's events.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nisayon.runs import run_command

from .identity import project_root
from .io import file_digest, write_json

MODEL = "gpt-6-astra"
EFFORT = "medium"
DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "image_generation",
    "view_image",
    "multi_agent",
    "hooks",
    "in_app_browser",
    "skill_search",
    "memories",
    "remote_plugin",
    "plugins",
    "shell_snapshot",
    "in_app_local_automation",
    "in_app_chat",
    "goals",
    "sleep_tool",
    "default_mode_request_user_input",
)


def arguments(public: Path, output: Path, schema: Path, prompt: str) -> list[str]:
    binary = shutil.which("codex")
    if binary is None:
        raise RuntimeError("Pinned local Codex CLI unavailable; no provider substitution")
    public = public.resolve(strict=True)
    profile = (
        'permissions.nisayon_decision={filesystem={":root"="deny",":minimal"="read",'
        + json.dumps(str(public))
        + '="read"},network={enabled=false}}'
    )
    args = [
        binary,
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--json",
        "--color",
        "never",
        "--skip-git-repo-check",
        "--cd",
        str(public),
        "--model",
        MODEL,
        "--output-schema",
        str(schema.resolve()),
        "--output-last-message",
        str(output.resolve()),
    ]
    configs = [
        profile,
        'default_permissions="nisayon_decision"',
        'approval_policy="never"',
        f'model_reasoning_effort="{EFFORT}"',
        'web_search="disabled"',
        "project_doc_max_bytes=0",
        'shell_environment_policy.inherit="none"',
        'shell_environment_policy.set={PATH="/usr/bin:/bin:/usr/sbin:/sbin"}',
    ]
    for config in configs:
        args.extend(["-c", config])
    for name in DISABLED_FEATURES:
        args.extend(["--disable", name])
    args.extend(["--enable", "skip_host_skill_discovery", prompt])
    return args


def decide(public: Path, output: Path, schema: dict, prompt: str, *, timeout: int = 120) -> dict:
    """One decision, no retry or fallback; errors and missing usage remain explicit."""
    output.mkdir(parents=True, exist_ok=False)
    schema_path = output / "response-schema.json"
    write_json(schema_path, schema)
    final = output / "response.json"
    argv = arguments(public, final, schema_path, prompt)
    packet_files = {
        str(p.relative_to(public)): file_digest(p)
        for p in public.rglob("*")
        if p.is_file() and not p.is_symlink()
    }
    write_json(
        output / "invocation.json",
        {
            "model": MODEL,
            "reasoning_effort": EFFORT,
            "command": argv,
            "public_packet": packet_files,
            "timeout_seconds": timeout,
            "provider_model_substitution_permitted": False,
        },
    )
    record = run_command(project_root(), argv, "bounded-agent-decision", timeout=timeout)
    write_json(output / "command-record.json", record)
    directory = project_root() / ".nisayon/runs" / record["id"]
    events = []
    unparsed = []
    for line in (directory / "stdout.log").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            unparsed.append(line)
    usage = [
        event["usage"]
        for event in events
        if event.get("type") == "turn.completed" and "usage" in event
    ]
    response, response_error = None, None
    if final.is_file():
        try:
            response = json.loads(final.read_text())
        except ValueError as error:
            response_error = f"Invalid structured response: {error}"
    result = {
        "schema": "nisayon.bounded-agent-decision.v1",
        "model": MODEL,
        "effort": EFFORT,
        "command_record": record,
        "response": response,
        "response_error": response_error,
        "usage_events": usage,
        "usage_complete": len(usage) == 1
        and record["process_status"] == "completed"
        and all(
            type(usage[0].get(key)) is int and usage[0][key] >= 0
            for key in ("input_tokens", "output_tokens", "cached_input_tokens")
        ),
        "unparsed_stdout": unparsed,
        "events_reference": {
            "locator": str(directory / "stdout.log"),
            "sha256": file_digest(directory / "stdout.log"),
        },
        "provider_charge_usd": None,
        "model_binding": "Pinned requested CLI model ID; provider-side weight/version attestation is unavailable",
        "scope": "Client-reported per-call tokens and command wall. Provider invoices and human time unknown; a model ID does not attest backend weights.",
    }
    write_json(output / "result.json", result)
    return result
