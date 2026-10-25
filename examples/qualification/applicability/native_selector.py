"""Competent fixed native workflow with the same reviewed dependency knowledge.

No Nisayon import. It may reuse observations AND scores and always confirms.
The caller verifies retained artifact bytes before supplying availability.
"""


def required(previous, proposed, available):
    changed = {
        key for key in proposed if previous.get(key) != proposed[key] or proposed[key] is None
    }
    observe = (
        bool(changed & {"code", "calibration", "runtime", "reset", "diagnostics", "procedure"})
        or "observe" not in available
    )
    score = observe or "scoring" in changed or "score" not in available
    return {
        "observe": "run" if observe else "reuse",
        "score": "run" if score else "reuse",
        "confirm": "run",
        "review": "run",
    }
