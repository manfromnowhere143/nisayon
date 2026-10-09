"""Population-binding reference, conventional diagnostic, controls and the Parquet reader.

Every test runs on synthetic fixtures written by this checkout. One test reads the
coordinator's retained public packet when it exists on this machine and is skipped
otherwise; it asserts the identification facts of population-binding-001.
"""

from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.evaluation import parquet_reader as pq
from nisayon.evaluation import population_reference as ref
from nisayon.evaluation.conventional_population import diagnose
from nisayon.evaluation.population_controls import (
    CONTROLS,
    build_pbc03,
    run_population_controls,
)
from nisayon.evaluation.schema import Malformed

PACKET = Path(
    "/Users/danielwahnich/.codex/reports/nisayon-next-evidence-decision-2026-09-20-8i17bt5a/sources"
)
ENUMERATION = Path(
    "/Users/danielwahnich/workspace/nisayon-fable5/artifacts/population-binding-001/sources/groot-demo-episodes_stats-1a1837.jsonl"
)


def test_every_population_control_holds_for_both_workflows(tmp_path: Path) -> None:
    summary = run_population_controls(tmp_path)
    failures = {c["name"]: c["failures"] for c in summary["controls"] if c["failures"]}
    assert failures == {}
    assert summary["all_ok"] and len(CONTROLS) == 6
    outcomes = {
        case["case_id"]: (case["reference"]["operation"], case["reference"]["decision"])
        for c in summary["controls"]
        for case in c["cases"]
    }
    assert outcomes["PBC01-intact"] == ("reuse", "supported")
    assert outcomes["PBC02-mismatch-declared-current"] == ("recompute", "rejected")
    assert outcomes["PBC03-bound-parent"] == ("reuse", "supported")
    assert outcomes["PBC04-no-selection"] == ("abstain", "unresolved")
    assert outcomes["PBC05-parent-labelled-external"] == ("abstain", "unresolved")
    assert outcomes["PBC06-empty"] == ("invalid", "invalid")


def test_exact_and_pooled_arithmetic_agree_with_numpy_on_synthetic_rows() -> None:
    np = pytest.importorskip("numpy")
    rows = [
        [struct.unpack("<f", struct.pack("<f", math.sin(0.37 * i + k)))[0] for k in range(3)]
        for i in range(257)
    ]
    exact = ref.exact_statistics(rows, 3)
    array = np.asarray(rows, dtype=np.float64)
    assert np.allclose(exact["mean"], array.mean(0), rtol=0, atol=1e-12)
    assert np.allclose(exact["std"], array.std(0, ddof=0), rtol=0, atol=1e-12)
    assert np.allclose(exact["q01"], np.quantile(array, 0.01, 0), rtol=0, atol=1e-12)
    assert np.allclose(exact["q99"], np.quantile(array, 0.99, 0), rtol=0, atol=1e-12)
    # Pooling per-episode statistics reproduces the population moments and extremes.
    parts = [rows[:100], rows[100:180], rows[180:]]
    entries = []
    for part in parts:
        stats = ref.exact_statistics(part, 3)
        entries.append(
            {
                "count": [len(part)],
                "mean": stats["mean"],
                "std": stats["std"],
                "min": stats["min"],
                "max": stats["max"],
            }
        )
    pooled = ref.pool_episode_statistics(entries, 3)
    assert pooled["frames"] == 257
    assert pooled["min"] == exact["min"] and pooled["max"] == exact["max"]
    assert max(abs(a - b) for a, b in zip(pooled["mean"], exact["mean"], strict=True)) < 1e-12
    assert max(abs(a - b) for a, b in zip(pooled["std"], exact["std"], strict=True)) < 1e-9


def test_subset_relation_and_role_from_extremes() -> None:
    subset = {
        "mean": [0.0, 0.0],
        "std": [1.0, 1.0],
        "min": [-1.0, -2.0],
        "max": [1.0, 2.0],
        "q01": [-0.9, -1.9],
        "q99": [0.9, 1.9],
    }
    wider = {
        "mean": [0.1, 0.0],
        "std": [1.2, 1.0],
        "min": [-1.5, -2.0],
        "max": [1.0, 2.5],
        "q01": [-1.2, -1.9],
        "q99": [0.9, 2.2],
    }
    relation = ref.subset_relation(wider, subset, 2)
    assert relation["brackets_subset"] and relation["coordinates_outside_subset"] == 2
    role = ref.evaluate_role(wider, subset, 2, None)
    assert (
        role["role"] == "unresolved"
        and role["population_binding"] == "rejected_for_current_population"
    )
    same = ref.evaluate_role(dict(subset), subset, 2, None)
    assert same["role"] == "current_population_summary"
    narrower = {**subset, "min": [-0.5, -2.0]}
    assert ref.subset_relation(narrower, subset, 2)["brackets_subset"] is False


def test_labels_never_move_the_operation(tmp_path: Path) -> None:
    role = {"role": "parent_population_summary", "population_binding": "supported", "reason": "x"}
    labelled = ref.expected_operation(
        role,
        declared_role="external_reference_normalizer",
        selection={"kind": "label_only", "label": "verified_training_reference"},
        interpretation=None,
    )
    assert labelled["operation"] == "abstain" and labelled["decision"] == "unresolved"
    assert any(m.startswith("selection") for m in labelled["missing"])
    unretained = ref.expected_operation(
        role,
        declared_role=None,
        selection={
            "kind": "observed_invocation",
            "source_path": "tests/x.py",
            "source_sha256": "ab" * 32,
            "symbol": "check_stats_validity",
            "revision": "r",
        },
        interpretation=None,
    )
    assert unretained["operation"] == "abstain" and "not retained" in unretained["selection_detail"]
    source = tmp_path / "caller.py"
    source.write_text("assert check_stats_validity(path, features)\n")
    digest = ref.hashlib.sha256(source.read_bytes()).hexdigest()
    wrong_digest = ref.expected_operation(
        role,
        declared_role=None,
        selection={
            "kind": "observed_invocation",
            "source_path": "caller.py",
            "source_sha256": "0" * 64,
            "symbol": "check_stats_validity",
        },
        interpretation=None,
        root=tmp_path,
    )
    assert wrong_digest["operation"] == "abstain" and "differs" in wrong_digest["selection_detail"]
    wrong_symbol = ref.expected_operation(
        role,
        declared_role=None,
        selection={
            "kind": "observed_invocation",
            "source_path": "caller.py",
            "source_sha256": digest,
            "symbol": "generate_rel_stats",
        },
        interpretation=None,
        root=tmp_path,
    )
    assert (
        wrong_symbol["operation"] == "abstain" and "not found" in wrong_symbol["selection_detail"]
    )
    observed = ref.expected_operation(
        role,
        declared_role=None,
        selection={
            "kind": "observed_invocation",
            "source_path": "caller.py",
            "source_sha256": digest,
            "symbol": "check_stats_validity",
            "revision": "r",
        },
        interpretation=None,
        root=tmp_path,
    )
    assert observed["operation"] == "reuse" and observed["decision"] == "supported"
    assert observed["intent_note"]
    unresolved = {
        "role": "unresolved",
        "population_binding": "rejected_for_current_population",
        "reason": "y",
    }
    assert (
        ref.expected_operation(
            unresolved,
            declared_role="current_population_summary",
            selection=None,
            interpretation=None,
        )["operation"]
        == "recompute"
    )
    assert (
        ref.expected_operation(
            unresolved,
            declared_role="external_reference_normalizer",
            selection=None,
            interpretation=None,
        )["operation"]
        == "abstain"
    )


def test_conventional_diagnostic_is_content_driven_and_caches(tmp_path: Path) -> None:
    cases = build_pbc03(tmp_path)
    case = cases[0]
    cache: dict = {}
    first = diagnose(case, cache=cache)
    second = diagnose(case, cache=cache)
    assert first["decision"]["selected_operation"] == "reuse"
    assert first["observations"]["cache_behavior"]["cache_hit"] is False
    assert second["observations"]["cache_behavior"]["cache_hit"] is True
    assert second["decision"] == first["decision"] | {"reason": first["decision"]["reason"]}
    # Renaming the case and relabelling the role changes nothing.
    renamed = json.loads(json.dumps(case))
    renamed["case_id"] = "opaque-zeta"
    renamed["declared_role"] = "current_population_summary"
    third = diagnose(renamed)
    assert (
        third["decision"]["selected_operation"] == "reuse"
        and third["decision"]["declared_role_ignored"]
    )
    # Removing the enumeration removes the evidence and the reuse.
    without = json.loads(json.dumps(case))
    without["episodes_stats"] = None
    assert diagnose(without)["decision"]["selected_operation"] == "abstain"


def test_reader_decodes_snappy_and_hybrid_runs_and_refuses_bad_footers() -> None:
    # Snappy: literal "abcd" then a copy of 4 bytes from offset 4 -> "abcdabcd".
    stream = bytes([8]) + bytes([0x0C]) + b"abcd" + bytes([(0 << 2) | 1 | (0 << 5), 4])
    assert pq.snappy_decompress(stream) == b"abcdabcd"
    with pytest.raises(Malformed):
        pq.snappy_decompress(bytes([3]) + bytes([0x0C]) + b"abcd")
    # Hybrid: an RLE run of five 2s (bit width 2) followed by one bit-packed group.
    rle = bytes([5 << 1, 2])
    packed = bytes([(1 << 1) | 1]) + (0b11100100).to_bytes(2, "little")
    values = pq.read_hybrid(pq._Cursor(rle + packed), 2, 13)
    assert values[:5] == [2, 2, 2, 2, 2] and values[5:9] == [0, 1, 2, 3]
    with pytest.raises(Malformed):
        pq.read_metadata(b"PAR1" + b"\x00" * 10 + b"PAR1")
    with pytest.raises(Malformed):
        pq.read_metadata(b"NOPE" + b"\x00" * 20)


def test_cli_population_commands(tmp_path: Path) -> None:
    out = tmp_path / "controls"
    done = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "population-controls", "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith("all ok")
    case_path = out / "PBC03-bound-external-reference" / "PBC03-bound-parent.case.json"
    record = tmp_path / "conventional.json"
    produced = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "population-conventional",
            str(case_path),
            "--out",
            str(record),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert produced.returncode == 0, produced.stderr
    assessed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "population",
            str(case_path),
            "--producer",
            str(record),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert assessed.returncode == 0, assessed.stderr
    assessment = json.loads(assessed.stdout)
    assert assessment["schema"] == ref.ASSESSMENT_SCHEMA
    assert assessment["operation"]["operation"] == "reuse"
    assert assessment["producer_comparison"]["agrees"]
    broken = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "population", str(tmp_path / "missing.json")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert broken.returncode == 2


@pytest.mark.skipif(
    not (PACKET.exists() and ENUMERATION.exists()),
    reason="retained public packet not present on this machine",
)
def test_retained_demo_identification_facts() -> None:
    episodes = [
        json.loads(line) for line in (PACKET / "groot-demo-episodes.jsonl").read_text().splitlines()
    ]
    case = {
        "schema": ref.CASE_SCHEMA,
        "case_id": "test-original",
        "root": str(PACKET),
        "files": [
            {
                "path": f"groot-episode-{e['episode_index']:06d}.parquet",
                "episode_index": e["episode_index"],
                "declared_length": e["length"],
            }
            for e in episodes
        ],
        "info": "groot-demo-info.json",
        "published_statistics": "groot-demo-stats.json",
        "features": ["observation.state", "action"],
        "episodes_stats": str(ENUMERATION),
        "declared_role": None,
        "selection_evidence": None,
    }
    assessment = ref.assess_case(case)
    assert assessment["membership"]["valid"]
    for name in ("observation.state", "action"):
        feature = assessment["features"][name]
        assert feature["n"] == 1406
        assert feature["pooled"]["episodes"] == 379 and feature["pooled"]["frames"] == 101469
        assert feature["role"]["pooled"]["extremes_exact"]
        assert feature["role"]["subset_relation"]["coordinates_outside_subset"] > 0
        assert all(
            e["listed"] and e["count_matches"] and max(e["max_abs_difference"].values()) == 0
            for e in feature["per_episode_versus_enumeration"]
        )
    assert assessment["role"]["role"] == "parent_population_summary"
    assert assessment["operation"]["operation"] == "abstain"  # no selection evidence given here
