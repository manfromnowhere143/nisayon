import json
from pathlib import Path

from nisayon.engine import bounded_agent, cli_identity
from nisayon.engine.io import file_digest, write_json


def identity(root):
    executable = root / "public-test-executable"
    executable.write_text("labelled test bytes, never executed")
    member = {
        "path": str(executable),
        "sha256": file_digest(executable),
        "bytes": executable.stat().st_size,
    }
    return {
        "schema": "nisayon.cli-identity.v1",
        "launcher": member,
        "executable": member,
        "version": "codex-cli labelled-test",
        "package": None,
    }


def test_cli_identity_detects_changed_executable_bytes(tmp_path):
    observed = identity(tmp_path)
    assert cli_identity.unchanged(observed)
    Path(observed["executable"]["path"]).write_text("different bytes")
    assert not cli_identity.unchanged(observed)


def test_new_invocation_binds_cli_settings_and_preserves_usage_when_identity_changes(
    tmp_path, monkeypatch
):
    observed = identity(tmp_path)
    public = tmp_path / "packet"
    public.mkdir()
    write_json(public / "packet.json", {"labelled_test": True})
    monkeypatch.setattr(bounded_agent, "resolve_cli", lambda: observed)
    monkeypatch.setattr(bounded_agent, "project_root", lambda: tmp_path)

    def run(root, argv, label, **kwargs):
        assert argv[0] == observed["executable"]["path"]
        final = Path(argv[argv.index("--output-last-message") + 1])
        write_json(final, {"action": "abstain"})
        folder = root / ".nisayon/runs/labelled-test"
        folder.mkdir(parents=True)
        (folder / "stdout.log").write_text(
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 100, "output_tokens": 7, "cached_input_tokens": 20},
                }
            )
            + "\n"
        )
        Path(observed["executable"]["path"]).write_text("changed after call began")
        return {"id": "labelled-test", "process_status": "completed", "wall_seconds": 0.1}

    monkeypatch.setattr(bounded_agent, "run_command", run)
    output = tmp_path / "call"
    result = bounded_agent.decide(public, output, {"type": "object"}, "labelled test prompt")
    invocation = json.loads((output / "invocation.json").read_text())
    assert invocation["schema"] == "nisayon.bounded-agent-invocation.v2"
    assert invocation["cli"] == observed
    assert invocation["model"] == bounded_agent.MODEL
    assert invocation["reasoning_effort"] == bounded_agent.EFFORT
    assert invocation["response_schema_sha256"] == file_digest(output / "response-schema.json")
    assert not result["cli_identity_unchanged"] and not result["usage_complete"]
    assert result["usage_events"][0]["input_tokens"] == 100
    assert result["usage_events"][0]["output_tokens"] == 7
