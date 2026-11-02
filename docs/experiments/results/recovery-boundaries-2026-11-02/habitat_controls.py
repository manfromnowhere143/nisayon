"""Qualification controls for a local refusal; not a distributed trainer patch."""

import io

import pytest
import torch
from habitat_probe import (
    SOURCES,
    Fixture,
    advance,
    equal,
    finite_grads,
    methods,
    probe,
    restore,
    snapshot,
)


def refuse_nonfinite(model):
    # Rank-local refusal could strand peers in collectives. Explicitly out of scope.
    if torch.distributed.is_initialized():
        raise NotImplementedError("This local experiment does not implement rank consensus")
    if any(
        p.grad is not None and not bool(torch.isfinite(p.grad).all()) for p in model.parameters()
    ):
        raise FloatingPointError("Nonfinite gradient: optimizer step not authorized")


@pytest.mark.parametrize("fault", ["nan", "inf", "-inf"])
@pytest.mark.parametrize("group", ["policy", "auxiliary", "coefficient"])
def test_bad_update_refused_before_parameters_or_optimizer_change(fault, group):
    row = probe(fault=fault, group=group, guard=refuse_nonfinite)
    for key in (
        "refused",
        "weights_finite",
        "parameters_unchanged",
        "optimizer_unchanged",
        "next_update_matches_skipped_reference",
    ):
        assert row[key], row


@pytest.mark.parametrize("scale", [0.1, 10.0])
def test_finite_path_matches_original_clipping_and_adam(scale):
    baseline, candidate = Fixture("base"), Fixture("candidate")
    for _ in range(4):
        for model in (baseline, candidate):
            finite_grads(model, scale)
        refuse_nonfinite(candidate)
        assert advance(baseline) == advance(candidate)
        assert equal(snapshot(baseline), snapshot(candidate))


def test_absent_gradients_leave_warm_state_unchanged():
    model = Fixture()
    finite_grads(model)
    advance(model)
    before = snapshot(model)
    model.optimizer.zero_grad(set_to_none=True)
    refuse_nonfinite(model)
    advance(model)
    assert equal(before, snapshot(model))


def test_checkpoint_round_trip_and_refusal_then_next_step():
    model = Fixture()
    for _ in range(3):
        finite_grads(model)
        advance(model)
    before = snapshot(model)
    buffer = io.BytesIO()
    torch.save(before, buffer)
    buffer.seek(0)
    restored = Fixture()
    restore(restored, torch.load(buffer, weights_only=True))
    assert equal(before, snapshot(restored))
    finite_grads(model)
    model.actor_critic.policy.grad[0] = float("nan")
    with pytest.raises(FloatingPointError):
        refuse_nonfinite(model)
        advance(model)
    assert equal(snapshot(model), snapshot(restored))
    for branch in (model, restored):
        finite_grads(branch, 0.7)
        advance(branch)
    assert equal(snapshot(model), snapshot(restored))


def test_distributed_path_explicitly_unsupported(monkeypatch):
    monkeypatch.setattr(torch.distributed, "is_initialized", lambda: True)
    with pytest.raises(NotImplementedError):
        refuse_nonfinite(Fixture())


def test_known_sgd_control_does_not_generalize_to_warm_adam():
    sgd = probe(optimizer="sgd", warm=False)
    adam = probe()
    assert sgd["parameters_unchanged"] and sgd["optimizer_unchanged"]
    assert adam["weights_finite"]
    assert not adam["parameters_unchanged"] and not adam["optimizer_unchanged"]


def test_changed_source_is_not_silently_reused(tmp_path):
    altered = tmp_path / SOURCES["candidate"].name
    altered.write_bytes(SOURCES["candidate"].read_bytes() + b"\n# altered\n")
    with pytest.raises(ValueError, match="source bytes"):
        methods(altered)


def test_nonfinite_delta_is_not_reported_as_a_finite_maximum():
    assert probe(source="base")["max_parameter_delta"] == "nonfinite"
