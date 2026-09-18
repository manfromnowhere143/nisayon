import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_hooks_recover_context_without_transcript_or_stop_loop(workspace):
    script = REPO / "scripts/session_hook.py"
    payload = {"cwd": str(workspace), "session_id": "test", "hook_event_name": "SessionStart"}
    start = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(start.stdout)
    assert "qualify reset" in output["hookSpecificOutput"]["additionalContext"]
    payload["hook_event_name"] = "Stop"
    stop = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )
    assert stop.stdout == ""
    assert len(list((workspace / ".nisayon/sessions").glob("*.json"))) == 2
    malformed = subprocess.run(
        [sys.executable, str(script)], input="not json", capture_output=True, text=True
    )
    assert malformed.returncode == 0
    assert "Nisayon context hook" in malformed.stderr


def script_module(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_launchers(root):
    (root / "scripts").mkdir(exist_ok=True)
    for name in ["entry.py", "launch.py"]:
        shutil.copy2(REPO / "scripts" / name, root / "scripts" / name)


def test_installation_preserves_configuration_and_is_idempotent(workspace, tmp_path):
    copy_launchers(workspace)
    user_dir = tmp_path / "user"
    (user_dir / ".codex").mkdir(parents=True)
    original = 'model = "test-model"\n[mcp_servers.existing]\ncommand = "existing"\n'
    (user_dir / ".codex/config.toml").write_text(original)
    (user_dir / ".codex/AGENTS.md").write_text("Existing instructions\n")
    (user_dir / ".claude.json").write_text(
        json.dumps(
            {"unrelated_setting": "preserve", "projects": {"/other/project": {"keep": True}}}
        )
    )
    installer = script_module("install_local")
    first = installer.install(workspace, user_dir)
    config = tomllib.loads((user_dir / ".codex/config.toml").read_text())
    assert config["model"] == "test-model"
    assert config["mcp_servers"]["existing"]["command"] == "existing"
    assert config["projects"][str(workspace)]["trust_level"] == "trusted"
    backup = Path(first["backup_directory"]) / ".codex/config.toml"
    assert backup.read_text() == original
    assert backup.stat().st_mode & 0o777 == 0o600
    assert (user_dir / ".codex/AGENTS.md").read_text().startswith("Existing instructions")
    claude_state = json.loads((user_dir / ".claude.json").read_text())
    assert claude_state["unrelated_setting"] == "preserve"
    assert claude_state["projects"]["/other/project"] == {"keep": True}
    assert claude_state["projects"][str(workspace)]["hasTrustDialogAccepted"] is True
    assert (user_dir / ".local/bin/nisayoncodes").resolve() == workspace / "scripts/launch.py"
    assert installer.install(workspace, user_dir)["changed"] == []


def test_installer_refuses_unrelated_command_collision(workspace, tmp_path):
    user_dir = tmp_path / "user"
    binary = user_dir / ".local/bin/nisayoncodes"
    binary.parent.mkdir(parents=True)
    binary.write_text("unrelated")
    with pytest.raises(ValueError, match="another installation"):
        script_module("install_local").install(workspace, user_dir)
    assert binary.read_text() == "unrelated"
    assert not (user_dir / ".codex").exists()


def launch(root, fake_bin, client, *args):
    env = {**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
    return subprocess.run(
        [sys.executable, str(root / "scripts/launch.py"), client, "--print-config", *args],
        cwd=root.parent,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def fake_clients(tmp_path):
    folder = tmp_path / "clients"
    folder.mkdir()
    for name in ["codex", "claude"]:
        path = folder / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    return folder


def test_launchers_bind_root_and_preserve_arguments(workspace, fake_clients):
    copy_launchers(workspace)
    prompt = "a prompt with spaces; $(not-a-command)"
    codex = launch(workspace, fake_clients, "codex", "resume", "--last", prompt)
    assert codex.returncode == 0, codex.stderr
    config = json.loads(codex.stdout)
    assert config["cwd"] == str(workspace)
    assert config["argv"][-3:] == ["resume", "--last", prompt]
    assert "--dangerously-bypass-approvals-and-sandbox" in config["argv"]
    claude = launch(workspace, fake_clients, "claude", "--model", "chosen-model", "--continue")
    args = json.loads(claude.stdout)["argv"]
    assert args.count("--model") == 1
    assert "fable" not in args
    assert "--dangerously-skip-permissions" in args


def test_launcher_accepts_own_worktree_and_rejects_unrelated_repo(
    workspace, fake_clients, tmp_path
):
    copy_launchers(workspace)
    subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "test fixture",
        ],
        check=True,
    )
    worktree = tmp_path / "parallel"
    subprocess.run(
        ["git", "-C", str(workspace), "worktree", "add", "-q", "-b", "parallel", str(worktree)],
        check=True,
    )
    try:
        accepted = launch(workspace, fake_clients, "codex", "--workspace", str(worktree))
        assert accepted.returncode == 0, accepted.stderr
        assert json.loads(accepted.stdout)["cwd"] == str(worktree)
        other = tmp_path / "unrelated"
        subprocess.run(["git", "clone", "-q", str(workspace), str(other)], check=True)
        rejected = launch(workspace, fake_clients, "codex", "--workspace", str(other))
        assert rejected.returncode != 0
        assert "one of its Git worktrees" in rejected.stderr
    finally:
        subprocess.run(
            ["git", "-C", str(workspace), "worktree", "remove", "--force", str(worktree)],
            check=True,
        )
