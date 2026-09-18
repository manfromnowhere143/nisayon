import gzip
import json
import subprocess

import pytest

from nisayon.engine.conditions import (
    HISTORY_PATH,
    consumed_history,
    reserve_fresh,
    verify_reservation,
)
from nisayon.engine.io import file_digest, write_json


def test_aborted_assignment_cannot_be_silently_reused_as_fresh(tmp_path):
    write_json(tmp_path / HISTORY_PATH, {"schema": "nisayon.consumed-conditions.v1", "entries": []})
    reserve_fresh(tmp_path, "public-development", [100, 101], "protocol-one", "invocation-one")
    with pytest.raises(ValueError, match="already reserved"):
        reserve_fresh(tmp_path, "public-development", [101, 102], "protocol-two", "invocation-two")
    # No result is needed to spend a reserved condition. Failure is conservative.
    assert reserve_fresh(
        tmp_path, "public-development", [102, 103], "protocol-two", "invocation-two"
    )["seeds"] == [102, 103]


def test_committed_history_blocks_reuse_without_local_reservations_and_checks_evidence(tmp_path):
    evidence = tmp_path / "retained-result.json"
    write_json(
        evidence,
        {
            "schema": "nisayon.development-condition.v1",
            "evidence_origin": "synthetic_condition_history_test",
            "namespace": "synthetic",
            "seed": 3000,
        },
    )
    write_json(
        tmp_path / HISTORY_PATH,
        {
            "schema": "nisayon.consumed-conditions.v1",
            "entries": [
                {
                    "namespace": "synthetic",
                    "seeds": [3000],
                    "evidence": {"path": evidence.name, "sha256": file_digest(evidence)},
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="consumed in committed"):
        reserve_fresh(tmp_path, "synthetic", [3000], "new-case-name", "new-invocation")
    assert not (tmp_path / ".nisayon").exists()
    evidence.write_text("changed evidence")
    with pytest.raises(ValueError, match="evidence digest mismatch"):
        consumed_history(tmp_path, "synthetic")


def test_seed_index_must_match_the_artifact_even_when_its_digest_is_correct(tmp_path):
    evidence = tmp_path / "retained-result.json"
    write_json(
        evidence,
        {"schema": "nisayon.development-condition.v1", "namespace": "synthetic", "seed": 777},
    )
    write_json(
        tmp_path / HISTORY_PATH,
        {
            "schema": "nisayon.consumed-conditions.v1",
            "entries": [
                {
                    "namespace": "synthetic",
                    "seeds": [888],
                    "evidence": {"path": evidence.name, "sha256": file_digest(evidence)},
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="absent from their bound evidence"):
        reserve_fresh(tmp_path, "synthetic", [777], "new-name", "new-invocation")
    assert not (tmp_path / ".nisayon").exists()


def test_unindexed_archives_block_reuse_across_renamed_cases_and_unused_assignments(tmp_path):
    write_json(tmp_path / HISTORY_PATH, {"schema": "nisayon.consumed-conditions.v1", "entries": []})
    archive = tmp_path / "docs/experiments/results/new-case/bundle.json.gz"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "schema": "nisayon.first_case.v1",
                    "evidence_origin": "synthetic_condition_history_test",
                    "case": {"id": "old-case", "policy": {"sha256": "synthetic-policy"}},
                    "runs": [{"id": "failed", "seed": 777}],
                    "assignments": [{"run_id": "unexecuted", "seed": 778}],
                }
            ).encode()
        )
    )
    namespace = "panda-lift:synthetic-policy"
    result = consumed_history(tmp_path, namespace)
    assert result["seeds"] == [777, 778]
    assert len(result["discovered_unindexed_evidence"]) == 1
    for seed in [777, 778]:
        with pytest.raises(ValueError, match="consumed in committed"):
            reserve_fresh(tmp_path, namespace, [seed], "renamed-case", "new-invocation")
    assert consumed_history(tmp_path, "panda-lift:other-policy")["seeds"] == []
    (tmp_path / HISTORY_PATH).unlink()
    # Allowing an absent index for a caller does not erase retained execution.
    with pytest.raises(ValueError, match="consumed in committed"):
        reserve_fresh(
            tmp_path, namespace, [777], "renamed-case", "new-invocation", history_required=False
        )


def test_unexecuted_suite_assignments_are_consumed_from_their_frozen_evidence(tmp_path):
    write_json(tmp_path / HISTORY_PATH, {"schema": "nisayon.consumed-conditions.v1", "entries": []})
    write_json(
        tmp_path / "docs/experiments/results/partial-comparison/frozen-suite.json",
        {
            "schema": "nisayon.development.frozen-suite.v1",
            "asset": {"sha256": "synthetic-policy"},
            "condition_seeds": {"old-case": [900, 901]},
        },
    )
    with pytest.raises(ValueError, match="consumed in committed"):
        reserve_fresh(
            tmp_path, "panda-lift:synthetic-policy", [901], "renamed-case", "new-invocation"
        )


def test_missing_required_history_is_not_treated_as_no_prior_observations(tmp_path):
    with pytest.raises(ValueError, match="history is missing"):
        reserve_fresh(tmp_path, "synthetic", [1], "protocol", "invocation")


def test_git_worktrees_share_exclusive_reservations(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repository, check=True, capture_output=True)

    git("init", "-q")
    write_json(
        repository / HISTORY_PATH, {"schema": "nisayon.consumed-conditions.v1", "entries": []}
    )
    git("add", HISTORY_PATH)
    git(
        "-c",
        "user.name=Local test fixture",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "Synthetic reservation test",
    )
    worktree = tmp_path / "other-worktree"
    git("worktree", "add", "--detach", str(worktree))
    first = reserve_fresh(repository, "synthetic", [42], "protocol-A", "invocation-A")
    assert "/.git/nisayon/conditions/" in first["reservation_store_locator"]
    with pytest.raises(ValueError, match="already reserved"):
        reserve_fresh(worktree, "synthetic", [42], "protocol-B", "invocation-B")
    assert reserve_fresh(worktree, "synthetic", [43], "protocol-B", "invocation-B")["seeds"] == [43]
    assert verify_reservation(worktree, "synthetic", [42], "protocol-A", "invocation-A")["records"]
    with pytest.raises(ValueError, match="different protocol or invocation"):
        verify_reservation(worktree, "synthetic", [42], "protocol-B", "invocation-B")
    with pytest.raises(ValueError, match="no pre-execution reservation"):
        verify_reservation(worktree, "synthetic", [44], "protocol-B", "invocation-B")
