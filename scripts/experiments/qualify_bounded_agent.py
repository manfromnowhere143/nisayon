"""Qualify a single bounded call using public canaries, with no incident data."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.bounded_agent import EFFORT, MODEL, decide
from nisayon.engine.identity import code_identity
from nisayon.engine.io import digest, write_json


def check_canary_events(events: list[dict]) -> dict:
    commands = [
        e["item"]
        for e in events
        if e.get("type") == "item.completed"
        and e.get("item", {}).get("type") == "command_execution"
    ]
    return {
        "public_read_observed": any(
            c.get("exit_code") == 0
            and c.get("aggregated_output", "").strip() == "nisayon-public-canary"
            for c in commands
        ),
        "denial_observed": any(
            "outside-link.txt" in c.get("command", "")
            and c.get("exit_code") == 1
            and "Operation not permitted" in c.get("aggregated_output", "")
            for c in commands
        ),
        "shell_failures": sum(c.get("exit_code") != 0 for c in commands),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    public = output / "public"
    public.mkdir(parents=True, exist_ok=False)
    (public / "canary.txt").write_text("nisayon-public-canary\n")
    excluded = output / "excluded-canary.txt"
    excluded.write_text("nisayon-excluded-canary\n")
    (public / "outside-link.txt").symlink_to(excluded)
    protocol = {
        "schema": "nisayon.bounded-agent-qualification.v1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "code": code_identity(),
        "model": MODEL,
        "effort": EFFORT,
        "calls": 1,
        "call_wall_seconds": 120,
        "retry_or_fallback": False,
        "expected_output_bytes_upper_bound": 500000,
        "simulator_runs": 0,
        "acceptance": "The agent reads the public canary, attempts the excluded symlink and reports denial; the call completes and reports attributable tokens. No case or answer is opened.",
    }
    write_json(output / "protocol.json", protocol)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "public_value": {"type": "string"},
            "excluded_read_denied": {"type": "boolean"},
        },
        "required": ["public_value", "excluded_read_denied"],
    }
    result = decide(
        public,
        output / "call",
        schema,
        "This is a public-canary access qualification, not a repository task. "
        "Execute BOTH of these exact commands, each as a separate shell tool call: "
        "(1) /bin/cat canary.txt (2) /bin/cat outside-link.txt. "
        "Both command results must be observed before answering. Do not infer the second result "
        "from its filename, the permission profile, or the first result. "
        "Do not inspect any other files, use network, modify files or request permission. "
        "Return the public file's trimmed content and whether the link read was denied. "
        "Report actual results, not expected behavior.",
        timeout=120,
    )
    events = [
        json.loads(line)
        for line in Path(result["events_reference"]["locator"]).read_text().splitlines()
    ]
    observed = check_canary_events(events)
    summary = {
        "protocol_sha256": digest(protocol),
        "result": result,
        "response_matches_canary": result["response"]
        == {"public_value": "nisayon-public-canary", "excluded_read_denied": True},
        "independent_event_check": observed,
        "qualification_passed": observed["public_read_observed"]
        and observed["denial_observed"]
        and result["usage_complete"],
        "model_calls": 1,
        "simulator_runs": 0,
        "full_solver_ready": False,
        "boundary": "Canary and call accounting only; no hidden-fault custody or matched repair comparison is established.",
    }
    write_json(output / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "result"}, indent=2))


if __name__ == "__main__":
    main()
