"""Deliberately failing falsification, kept separate from the passing controls."""

from habitat_probe import probe


def test_sanitized_failed_update_is_noop():
    observed = probe()
    assert observed["weights_finite"]
    assert observed["parameters_unchanged"], observed
    assert observed["optimizer_unchanged"], observed
    assert observed["next_update_matches_skipped_reference"], observed
