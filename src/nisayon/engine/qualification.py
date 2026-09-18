"""Declared execution premises shared by the measured development families."""

from .telemetry import configuration


def execution_qualification(telemetry_profile: str = "full") -> dict:
    telemetry = configuration(telemetry_profile)
    captured = [
        "qpos",
        "qvel",
        "act",
        "ctrl",
        "qacc_warmstart",
        "mocap",
        "userdata",
        "controller goals and gains",
        "gripper command",
        "reset RNGs",
        "model XML",
    ]
    omitted = [
        "MuJoCo internal solver caches",
        "all observable internal buffers",
        "full controller object",
        "OS scheduling",
        "hardware floating point state",
    ]
    if telemetry_profile == "full":
        captured.append("policy LSTM state and counter")
    else:
        omitted.append("policy LSTM state and counter: " + telemetry["missing_reason"])
    return {
        "reset": "New environment/controller and Python/NumPy/Torch seeds; policy reset event and any executed prefix are recorded per run",
        "captured_state": captured,
        "omitted_state": omitted,
        "continuation_supported": False,
        "clocks": {
            "simulation": "MuJoCo data.time, s",
            "host": "perf_counter, s since executor construction",
        },
        "action_boundary": "Normalized seven-dimensional env.step input; final actuator ctrl retained",
        "queue": "No action queue or action chunks; one action per control step. Observation history starts empty at each environment reset and retains actual acquisitions.",
        "policy_recurrence": "Frozen BC-RNN LSTM; policy's own ten-step hidden-state reset is unchanged",
        "telemetry": telemetry,
        "scope": "Pinned CPU simulator and policy; full reruns only. These declared premises do not constitute independent measurement attestation.",
    }
