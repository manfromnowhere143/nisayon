"""An integrated source checkout must not inventory an unrelated sibling tree."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "tools/ui/build_system_catalog.py"
SPEC = importlib.util.spec_from_file_location("system_catalog_controls", SOURCE)
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


def engine_at(root, label):
    package = root / "src/nisayon"
    (package / "engine").mkdir(parents=True)
    (package / "engine/confirmation_view.py").write_text(f'"""{label}"""\n')
    raw = f'@mcp.tool()\ndef inspect():\n    """{label}"""\n'.encode()
    (package / "mcp_server.py").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "checkout-with-any-name"
    root.mkdir()
    monkeypatch.setattr(catalog, "ROOT", root)
    monkeypatch.setattr(catalog.subprocess, "check_output", lambda *a, **kw: "a" * 40)
    return root


def test_integrated_source_wins_over_an_existing_sibling(workspace):
    expected = engine_at(workspace, "current integrated engine")
    engine_at(workspace.parent / "nisayon", "unrelated older sibling")
    result = catalog.build()
    assert result["interfaces"][0]["source"]["sha256"] == expected
    assert result["interfaces"][0]["description"] == "current integrated engine"
    assert result["execution_connected"] is False
    assert result["provenance"]["engine_source"] == "selected engine checkout"


def test_instrument_only_tree_preserves_legacy_sibling_resolution(workspace):
    expected = engine_at(workspace.parent / "nisayon", "legacy sibling engine")
    assert catalog.build()["interfaces"][0]["source"]["sha256"] == expected


def test_explicit_engine_remains_authoritative(workspace):
    engine_at(workspace, "integrated engine")
    external = workspace.parent / "selected-engine"
    expected = engine_at(external, "explicitly selected engine")
    assert catalog.build(external)["interfaces"][0]["source"]["sha256"] == expected


def test_missing_explicit_engine_does_not_fall_back(workspace):
    engine_at(workspace, "integrated engine")
    with pytest.raises(ValueError, match="engine source"):
        catalog.build(workspace.parent / "missing-engine")
