import json
import subprocess

import pytest

from nisayon import workspace as ws


def test_identity_does_not_cross_a_nested_repository(workspace):
    assert ws.project_root(workspace / "docs") == workspace
    nested = workspace / "another-project"
    nested.mkdir()
    subprocess.run(["git", "init", "-q", str(nested)], check=True)
    with pytest.raises(ValueError, match="Not a Nisayon"):
        ws.project_root(nested)


def test_marker_cannot_override_git_identity(workspace):
    (workspace / "nisayon.json").write_text(
        json.dumps({"project": "reiyah", "schema": "nisayon.workspace.v1"})
    )
    with pytest.raises(ValueError, match="Invalid Nisayon"):
        ws.project_root(workspace)


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", ".env", ".git/config"])
def test_reader_rejects_non_source_paths(workspace, path):
    with pytest.raises(ValueError):
        ws.read_file(workspace, path)


def test_reader_rejects_symlink_escape_and_credential_alias(workspace, tmp_path):
    (tmp_path / "outside.txt").write_text("not project content")
    (workspace / "alias").symlink_to(tmp_path / "outside.txt")
    with pytest.raises(ValueError, match="escapes"):
        ws.read_file(workspace, "alias")
    (workspace / ".env").write_text("test fixture only")
    (workspace / "alias").unlink()
    (workspace / "alias").symlink_to(workspace / ".env")
    with pytest.raises(ValueError, match="credentials"):
        ws.read_file(workspace, "alias")


def test_bounded_read_and_literal_search(workspace):
    (workspace / "sample.md").write_text("a.b\nAxB\na.b\n")
    (workspace / ".env").write_text("a.b secret fixture")
    result = ws.read_file(workspace, "sample.md", start_line=2, limit=1)
    assert result["content"] == "2: AxB"
    assert result["truncated"] is True
    matches = ws.search(workspace, "a.b")["matches"]
    assert len(matches) == 2
    assert all(row["path"] == "./sample.md" for row in matches)


def test_doctor_reports_missing_configuration(workspace):
    result = ws.doctor(workspace)
    assert result["ok"] is False
    assert {row["check"] for row in result["checks"] if not row["ok"]} >= {
        ".codex/config.toml",
        ".mcp.json",
        "uv.lock",
    }
