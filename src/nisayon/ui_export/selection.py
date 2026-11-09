"""Exact recorded-time comparison. No interpolation, clamping or future extension."""

from .bytes import ExportError
from .validate import select


def align(generation, anchor, target_key):
    source = select(generation, anchor)
    case = generation["cases"][anchor["case_key"]]
    target = next((r for r in case["runs"] if r["key"] == target_key), None)
    if target is None:
        raise ExportError("unknown comparison run")
    if source["run"]["condition_id"] != target["condition_id"]:
        return {"status": "different_condition", "moment": None}
    rows = generation["objects"][target["samples"]["path"]]["rows"]
    if not rows:
        return {"status": "no_recorded_samples", "moment": None}
    field = "action_sim_time_s" if anchor["phase"] == "before" else "next_sim_time_s"
    time = source["sample"][field]
    index = next((i for i, row in enumerate(rows) if row[field] == time), None)
    if index is not None:
        return {
            "status": "recorded",
            "moment": {**anchor, "run": target_key, "row_index": index},
            "alignment": "Equal simulation seconds and phase from distinct recorded resets; not equal state.",
        }
    if time > rows[-1]["next_sim_time_s"]:
        status = "recording_ended"
    elif time < rows[0]["action_sim_time_s"]:
        status = "recording_not_started"
    else:
        status = "no_exact_sample_at_phase"
    return {
        "status": status,
        "moment": None,
        "recorded_start_s": rows[0]["action_sim_time_s"],
        "recorded_end_s": rows[-1]["next_sim_time_s"],
    }
