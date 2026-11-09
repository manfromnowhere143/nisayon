"""Attack the admitted boundary with real D01 bytes and changed bindings."""

import copy
import gzip
import json
import shutil
from pathlib import Path

import pytest

from nisayon.ui_export.bytes import ExportError, canonical, inside, parse, sha256
from nisayon.ui_export.contract import json_schema
from nisayon.ui_export.selection import align
from nisayon.ui_export.source import admit_row
from nisayon.ui_export.validate import select, validate_generation

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "fixtures/ui/d01"
COMPACT = (
    ROOT
    / "docs/experiments/results/development-ablation-001/D01-gripper-sign/B/diagnostic/execution/bundle.json.gz"
)


@pytest.fixture(scope="module")
def generation():
    return validate_generation(EXAMPLE, strict_optional=True)


@pytest.fixture
def copied(tmp_path):
    shutil.copytree(EXAMPLE, tmp_path / "generation")
    return tmp_path / "generation"


def replace_object(root, kind, change):
    """Rebind changed bytes to test semantic checks beyond a digest mismatch."""
    discovery = parse((root / "evidence.json").read_bytes())
    manifest = parse((root / discovery["manifest"]["path"]).read_bytes())
    target = next(f for f in manifest["files"] if f["kind"] == kind)
    value = parse((root / target["path"]).read_bytes())
    change(value)
    old_path = target["path"]
    data = canonical(value) + b"\n"
    new = {
        **target,
        "sha256": sha256(data),
        "byte_length": len(data),
        "path": "objects/" + sha256(data) + ".json",
    }
    (root / new["path"]).write_bytes(data)
    replacements = {old_path: new}
    # All case refs point directly to sample/model/reconstruction/decision children.
    for case_ref in manifest["cases"]:
        original_ref = case_ref["object"]
        case = parse((root / original_ref["path"]).read_bytes())
        if kind == "case" and original_ref["path"] == old_path:
            case_ref["object"] = new
            continue

        def rewrite(node):
            if isinstance(node, dict):
                if node.get("path") in replacements:
                    return replacements[node["path"]]
                return {k: rewrite(v) for k, v in node.items()}
            if isinstance(node, list):
                return [rewrite(v) for v in node]
            return node

        case = rewrite(case)
        encoded = canonical(case) + b"\n"
        case_ref["object"] = {
            **original_ref,
            "sha256": sha256(encoded),
            "byte_length": len(encoded),
            "path": "objects/" + sha256(encoded) + ".json",
        }
        (root / case_ref["object"]["path"]).write_bytes(encoded)
        replacements[original_ref["path"]] = case_ref["object"]
    manifest["files"] = [replacements.get(ref["path"], ref) for ref in manifest["files"]]
    encoded = canonical(manifest) + b"\n"
    discovery["manifest"] = {
        **discovery["manifest"],
        "sha256": sha256(encoded),
        "byte_length": len(encoded),
        "path": "generations/" + sha256(encoded) + ".json",
    }
    (root / discovery["manifest"]["path"]).write_bytes(encoded)
    (root / "evidence.json").write_bytes(canonical(discovery))


def moment(generation, run=None, **changes):
    case = next(iter(generation["cases"].values()))
    return {
        "generation_sha256": generation["generation_sha256"],
        "case_key": case["case_key"],
        "run": run or case["runs"][1]["key"],
        "row_index": 0,
        "phase": "before",
        "clock": "simulation",
        **changes,
    }


def test_checked_real_d01_readings_frames_and_findings(generation):
    case = next(iter(generation["cases"].values()))
    assert sum(r["sample_count"] for r in case["runs"]) == 488
    assert [(f["code"], f["run"]["run_id"], f["step"]) for f in case["findings"]] == [
        ("gripper_transport_mismatch", "regression-0", 0)
    ]
    original = json.loads(gzip.decompress(COMPACT.read_bytes()))
    selected = select(generation, moment(generation))
    assert selected["sample"]["original"] == original["runs"][1]["trace"][0]
    assert selected["sample"]["memory"]["before"] == "initialized_none"
    assert selected["frame"]["stored_time_s"] == 0
    after = select(generation, moment(generation, phase="after"))
    assert after["frame"]["stored_time_s"] == original["runs"][1]["trace"][0]["next_sim_time_s"]
    assert after["frame"]["residuals"]["cube_height_difference_m"] == pytest.approx(
        0.0005579657636821667, abs=1e-15
    )
    assert after["frame"]["bodies"][23][2] != after["sample"]["original"]["cube_height_m"]
    assert case["confirmation"]["availability"] == "not_in_this_generation"
    assert generation["objects"][case["decisions"][0]["path"]]["decision"] == "unresolved"


def test_schema_checked_in_matches_wire_types():
    assert json.loads((ROOT / "schemas/ui/generation-v1.schema.json").read_text()) == json_schema()


def test_source_distinguishes_compressed_exact_and_canonical_bytes(generation):
    data = COMPACT.read_bytes()
    decoded = gzip.decompress(data)
    by_hash = {s["sha256"]: s for s in generation["manifest"]["sources"]}
    assert by_hash[sha256(data)]["encoding"] == "gzip-json"
    assert by_hash[sha256(decoded)]["encoding"] == "json"
    assert by_hash[sha256(decoded)]["canonical_json_sha256"] != sha256(decoded)
    assert b"/Users/" not in canonical(generation["manifest"])
    for obj in generation["objects"].values():
        assert b"/Users/" not in canonical(obj)


def test_changed_required_child_bytes_fail(copied, generation):
    ref = next(f for f in generation["manifest"]["files"] if f["kind"] == "samples")
    path = copied / ref["path"]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ExportError, match="byte length mismatch"):
        validate_generation(copied)


def test_wrong_pinned_root_fails():
    with pytest.raises(ExportError, match="pinned generation"):
        validate_generation(EXAMPLE, expected_sha256="0" * 64)


def test_missing_optional_scene_keeps_exact_readings(copied, generation):
    case = next(iter(generation["cases"].values()))
    ref = case["runs"][1]["reconstruction"]
    (copied / ref["path"]).unlink()
    partial = validate_generation(copied)
    chosen = select(partial, moment(partial))
    assert chosen["frame"] is None
    assert chosen["sample"]["original"]["executed_action"][6] == 1
    assert ref["path"] in partial["unavailable"]
    with pytest.raises(ExportError):
        validate_generation(copied, strict_optional=True)


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda o: o["run"].update(bundle_sha256="0" * 64), "sample bundle/run"),
        (lambda o: o["rows"][0].update(row_index=1), "sample row"),
        (lambda o: o["rows"][0]["source"].update(pointer="/runs/99/trace/0"), "source locator"),
        (lambda o: o["rows"][0]["memory"].update(before="unavailable"), "memory availability"),
        (lambda o: o["rows"][0]["original"].update(intended_action=[0, 0]), "action dimension"),
    ],
)
def test_rebound_sample_corruptions(copied, change, match):
    replace_object(copied, "samples", change)
    with pytest.raises(ExportError, match=match):
        validate_generation(copied)


def test_rebound_frame_phase_cannot_be_displayed(copied):
    replace_object(copied, "reconstruction", lambda o: o["frames"][0].update(phase="after"))
    partial = validate_generation(copied)
    assert any("frame row/phase" in message for message in partial["unavailable"].values())
    with pytest.raises(ExportError, match="frame row/phase"):
        validate_generation(copied, strict_optional=True)


def test_duplicate_run_identity_fails(copied):
    replace_object(copied, "case", lambda o: o["runs"].append(copy.deepcopy(o["runs"][0])))
    with pytest.raises(ExportError, match="duplicate run identity"):
        validate_generation(copied)


@pytest.mark.parametrize(
    "changes",
    [
        {"row_index": -1},
        {"row_index": 400},
        {"row_index": 1.5},
        {"row_index": True},
        {"phase": "during"},
        {"clock": "host"},
        {"generation_sha256": "0" * 64},
        {"run": {"bundle_sha256": "0" * 64, "run_id": "regression-0"}},
    ],
)
def test_invalid_selection_never_falls_back(generation, changes):
    with pytest.raises(ExportError):
        select(generation, moment(generation, **changes))


@pytest.mark.parametrize(
    "data", [b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'{"x":1,"x":2}']
)
def test_invalid_json_numbers_and_duplicate_keys_fail(data):
    with pytest.raises(ExportError):
        parse(data)


@pytest.mark.parametrize(
    "path", ["../escape", "/tmp/escape", "a/../escape", "a//b", "https://x", "%2e%2e/x", "a\\b"]
)
def test_paths_cannot_leave_generation(tmp_path, path):
    with pytest.raises(ExportError):
        inside(tmp_path, path)


def test_missing_bound_state_is_rejected():
    compact = json.loads(gzip.decompress(COMPACT.read_bytes()))["runs"][0]["trace"][0]
    with pytest.raises(ExportError, match="missing source field"):
        admit_row({"step": compact["step"]}, compact)


@pytest.mark.parametrize(
    "change",
    [
        lambda o: o["rows"][0]["original"].update(step=False),
        lambda o: o["rows"][0]["original"].update(cube_height_m="0.84"),
        lambda o: o["rows"][0]["original"].update(task_success=1),
        lambda o: o["rows"][0]["original"].pop("policy_state_sha256"),
        lambda o: o["rows"][0]["memory"].update(episode_reset=False),
        lambda o: o["rows"][0]["original"].update(state_before_sha256=None),
        lambda o: o["rows"][0].update(raw_source=None),
        lambda o: o["rows"][0]["observations"]["observation"]["robot0_eef_pos"].__setitem__(0, 999),
    ],
)
def test_malformed_or_changed_original_readings_fail(copied, change):
    replace_object(copied, "samples", change)
    with pytest.raises(ExportError):
        validate_generation(copied)


def test_unsupported_schema_fails_after_valid_digest(copied):
    replace_object(copied, "samples", lambda o: o.update(schema="nisayon.ui-samples.v999"))
    with pytest.raises(ExportError, match="tag"):
        validate_generation(copied)


def test_partial_required_object_fails(copied):
    replace_object(copied, "samples", lambda o: o.pop("rows"))
    with pytest.raises(ExportError, match="Field required"):
        validate_generation(copied)


def test_symlink_cannot_escape_even_when_bytes_match(copied, generation):
    ref = next(f for f in generation["manifest"]["files"] if f["kind"] == "samples")
    path = copied / ref["path"]
    path.unlink()
    path.symlink_to(EXAMPLE / ref["path"])
    with pytest.raises(ExportError, match="escapes"):
        validate_generation(copied)


def test_browser_inexact_integer_is_rejected():
    with pytest.raises(ExportError, match="JavaScript range"):
        parse(b'{"value":9007199254740993}')


def test_comparison_uses_phase_time_and_does_not_extend_recording(generation):
    case = next(iter(generation["cases"].values()))
    target = case["runs"][0]["key"]
    mapped = align(generation, moment(generation, row_index=20, phase="after"), target)
    assert mapped["status"] == "recorded"
    result = select(generation, mapped["moment"])
    assert result["sample"]["row_index"] == 20
    assert result["frame"]["phase"] == "after"
    ended = align(generation, moment(generation, row_index=399, phase="after"), target)
    assert ended["status"] == "recording_ended" and ended["moment"] is None


def test_optional_model_bad_ancestry_keeps_readings(copied):
    replace_object(copied, "model", lambda o: o["bodies"][1].update(parent_id=1))
    result = validate_generation(copied)
    assert any("body ancestry" in message for message in result["unavailable"].values())
    assert select(result, moment(result))["sample"]["step"] == 0
    assert select(result, moment(result))["frame"] is None


@pytest.mark.parametrize("pointer", [None, "/runs/-1", "/runs/0/trace/0", "/runs/01"])
def test_invalid_run_source_pointer_is_rejected(copied, pointer):
    replace_object(copied, "case", lambda c: c["runs"][0]["source"].update(pointer=pointer))
    with pytest.raises(ExportError, match="source pointer"):
        validate_generation(copied)


def test_declared_end_time_must_match_the_last_reading(copied):
    replace_object(copied, "case", lambda c: c["runs"][0].update(last_next_sim_time_s=99.0))
    with pytest.raises(ExportError, match="end time mismatch"):
        validate_generation(copied)


def test_pinned_generation_survives_new_discovery(copied, generation):
    replace_object(copied, "case", lambda c: c["limitations"].append("New display generation"))
    current = validate_generation(copied)
    assert current["generation_sha256"] != generation["generation_sha256"]
    retained = validate_generation(copied, expected_sha256=generation["generation_sha256"])
    assert retained["generation_sha256"] == generation["generation_sha256"]
    assert (
        select(retained, moment(retained))["sample"]
        == select(generation, moment(generation))["sample"]
    )


def test_pinned_generation_does_not_need_discovery(copied, generation):
    (copied / "evidence.json").unlink()
    retained = validate_generation(copied, expected_sha256=generation["generation_sha256"])
    assert retained["generation_sha256"] == generation["generation_sha256"]
