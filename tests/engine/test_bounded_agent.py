import importlib
from pathlib import Path


def test_command_not_found_does_not_prove_a_read_boundary(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/experiments"))
    check = importlib.import_module("qualify_bounded_agent").check_canary_events

    def event(command, code, output):
        return {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": command,
                "exit_code": code,
                "aggregated_output": output,
            },
        }

    events = [
        event("cat outside-link.txt", 127, "command not found: cat"),
        event("/bin/cat canary.txt", 0, "nisayon-public-canary\n"),
    ]
    assert not check(events)["denial_observed"]
    assert check(events)["public_read_observed"]
    events.append(event("/bin/cat outside-link.txt", 1, "Operation not permitted"))
    assert check(events)["denial_observed"]
