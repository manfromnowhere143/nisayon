"""Boundary regressions for the reusable example, without installing Torch."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "examples/qualification/kornia_mix"
SPEC = importlib.util.spec_from_file_location("mix_scope", PACKAGE / "scope.py")
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)


@pytest.fixture
def conditions():
    return scope.read(PACKAGE / "inputs.json")


def test_exposed_conditions_remain_in_scope(conditions):
    scope.validate_conditions(conditions)


@pytest.mark.parametrize(
    "change",
    [
        {"beta": 0},
        {"beta": True},
        {"beta": [0.37]},
        {"beta": float("inf")},
        {"beta": 1e6},
        {"dtype": "float8_e4m3fn"},
        {"device": "cuda"},
        {"shape": [1, 1, 0, 4]},
        {"shape": [64, 64, 64, 64]},
        {"shape": [True, 1, 1, 1]},
        {"seed": -1},
        {"seed": 1.5},
        {"same_on_batch": "false"},
        {"move": "compile"},
        {"num_mix": 0},
        {"cut_size": [0.8, 0.1]},
        {"patch_size": 1},
        {"labels": [1, 2, 3]},
    ],
)
def test_unqualified_domain_cannot_inherit_contract(conditions, change):
    conditions[0].update(change)
    with pytest.raises(ValueError):
        scope.validate_conditions(conditions)


def test_missing_or_duplicate_conditions_cannot_weaken_check(conditions):
    with pytest.raises(ValueError, match="coverage"):
        scope.validate_conditions([row for row in conditions if row["dtype"] != "float32"])
    conditions[-1]["id"] = conditions[0]["id"]
    with pytest.raises(ValueError, match="unique"):
        scope.validate_conditions(conditions)


def test_nonrepresentable_classes_cannot_silently_round(conditions):
    row = next(row for row in conditions if row["kind"] == "module")
    row["labels"] = [2**24 + 1] * row["shape"][0]
    with pytest.raises(ValueError, match="representable"):
        scope.validate_conditions(conditions)


@pytest.mark.parametrize("body", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":[1e999]}'])
def test_ambiguous_or_nonfinite_json_is_rejected(tmp_path, body):
    path = tmp_path / "input.json"
    path.write_text(body)
    with pytest.raises(ValueError):
        scope.read(path)


def test_same_version_changed_installation_invalidates_environment():
    expected = scope.read(PACKAGE / "contract.json")["environment"]
    actual = copy.deepcopy(expected)
    actual["distribution_records"]["torch"] = "0" * 64
    with pytest.raises(ValueError, match="Environment changed"):
        scope.check_environment(actual, expected)


def test_snapshot_detects_added_files_and_rejects_links(tmp_path):
    package = tmp_path / "kornia"
    package.mkdir()
    (package / "__init__.py").write_text("# fixture\n")
    before = scope.native_files(tmp_path)
    (package / "shadow.py").write_text("# new import\n")
    assert scope.native_files(tmp_path) != before
    (package / "alias.py").symlink_to(package / "shadow.py")
    with pytest.raises(ValueError, match="Symlinks"):
        scope.native_files(tmp_path)


def test_existing_evidence_is_never_overwritten(tmp_path):
    path = tmp_path / "record.json"
    scope.write(path, {"status": "failed"})
    with pytest.raises(FileExistsError):
        scope.write(path, {"status": "supported"})
    assert json.loads(path.read_text()) == {"status": "failed"}


def test_added_module_cannot_shadow_a_bound_dependency(tmp_path, conditions, monkeypatch):
    # A new torch.py beside the entry point changes import resolution without
    # modifying any previously recorded file or installed distribution RECORD.
    monkeypatch.setitem(__import__("sys").modules, "scope", scope)
    spec = importlib.util.spec_from_file_location("mix_qualify", PACKAGE / "qualify.py")
    qualify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qualify)
    monkeypatch.setattr(qualify, "verify_package", lambda: "fixture-package")
    native = {}
    for role in ("baseline", "candidate"):
        package = tmp_path / role / "kornia"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("# bounded fixture\n")
        native[role] = scope.native_files(tmp_path / role)
    scope.write(tmp_path / "inputs.json", conditions)
    files = {
        str(p.relative_to(tmp_path)): scope.file_digest(p)
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    scope.write(
        tmp_path / "binding.json",
        {"package_sha256": "fixture-package", "files": files, "native": native},
    )
    qualify.verify_binding(tmp_path)
    (tmp_path / "torch.py").write_text("raise RuntimeError('import shadow')\n")
    with pytest.raises(ValueError, match="file set"):
        qualify.verify_binding(tmp_path)
