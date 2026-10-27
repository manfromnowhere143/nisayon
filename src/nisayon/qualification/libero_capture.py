"""Bounded, reversible collection around actual LIBERO success calls.

Install between control steps on a single, nonconcurrent native environment.
The frozen frame plan must name every observed step/call. No policy, controller
or success semantics are replaced. Simulator stepping retains its native type,
arguments and result. Unsupported or incomplete collection is left unsealed.
"""

from contextlib import contextmanager

from .native_measurements import _require, _runtime, _state


@contextmanager
def capture_libero_success(native_env, recorder, *, episode):
    """Record both reward and termination calls, with their geometry's origin.

    On supported Euler stepping, derived positions/contacts precede the updated
    integration state. Retain the actual pre-step state so offline verification
    must reconstruct the intervening transition before using those observations.
    The caller explicitly finalizes only after its planned collection completes.
    """
    mj, np = _runtime()
    sim = native_env.sim
    model, data = sim.model._model, sim.data._data
    original_success, original_step, original_forward = (
        native_env._check_success,
        sim.step,
        sim.forward,
    )
    _require(model is recorder.model, "collector_model_mismatch")
    _require(original_success == recorder.producer, "collector_producer_mismatch")
    _require(model.opt.integrator == mj.mjtIntegrator.mjINT_EULER, "collector_requires_euler")
    _require(not recorder.closed and recorder.index == 0, "collector_requires_new_recorder")
    _require(
        recorder.protocol["frames"][0]["episode"] == episode
        and recorder.protocol["frames"][0]["step"] == native_env.timestep + 1,
        "collector_requires_next_control_step",
    )
    origin = None
    calls = {}
    missing = object()
    originals = [
        (obj, name, obj.__dict__.get(name, missing))
        for obj, name in [(sim, "step"), (sim, "forward"), (native_env, "_check_success")]
    ]

    def check_context():
        valid = (
            native_env.sim is sim
            and sim.model._model is model
            and sim.data._data is data
            and data.model is model
            and recorder.model is model
            and recorder.producer == original_success
        )
        if not valid:
            recorder.failed = True
        _require(valid, "collector_context_changed")

    def step(*args, **kwargs):
        nonlocal origin
        try:
            check_context()
            before = _state(mj, np, model, data)
            result = original_step(*args, **kwargs)
            check_context()
            origin = before
            return result
        except BaseException:
            recorder.failed = True
            raise

    def forward(*args, **kwargs):
        nonlocal origin
        try:
            check_context()
            result = original_forward(*args, **kwargs)
            check_context()
            origin = None
            return result
        except BaseException:
            recorder.failed = True
            raise

    def success():
        step_index = native_env.timestep
        call = calls.get(step_index, 0)
        result = recorder.native_call(
            data,
            episode=episode,
            step=step_index,
            call=call,
            observation_state=origin,
            _context_check=check_context,
        )
        calls[step_index] = call + 1
        return result

    try:
        sim.step, sim.forward, native_env._check_success = step, forward, success
        yield recorder
    except BaseException:
        recorder.failed = True
        raise
    finally:
        for obj, name, original in reversed(originals):
            if original is missing:
                delattr(obj, name)
            else:
                setattr(obj, name, original)
