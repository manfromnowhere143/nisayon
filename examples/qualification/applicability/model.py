"""One reviewed normalization dependency definition, shared with the native arm."""


def definition():
    descriptions = {
        "code": ("code", "Exact unmodified OpenPI loader and controlled wrapper bytes"),
        "calibration": ("data", "Complete norm_stats.json bytes"),
        "diagnostics": ("data", "Complete exposed diagnostic vectors"),
        "runtime": (
            "runtime",
            "Python executable, platform, package versions and RECORD identities",
        ),
        "reset": ("state", "Fresh subprocess per batch; trusted stateless loader and wrapper"),
        "scoring": ("scoring", "Numerical tolerance and shared scoring implementation identity"),
        "population": ("population", "Only the explicitly supplied software vector domain"),
        "confirmation_inputs": ("data", "New explicit confirmation vectors for each decision"),
        "procedure": (
            "protocol",
            "Frozen driver, worker, model, native selector and SDK identities",
        ),
    }
    execution = ["code", "calibration", "runtime", "reset", "procedure"]
    return {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "openpi-normalization-applicability",
        "scope": "Exposed CPU software normalization controls; no learned policy or robot acceptance",
        "inputs": {
            key: {"kind": kind, "description": text} for key, (kind, text) in descriptions.items()
        },
        "checks": {
            "observe": {
                "kind": "observation",
                "depends_on": execution + ["diagnostics"],
                "refresh": "on_change",
            },
            "score": {
                "kind": "analysis",
                "depends_on": ["observe", "scoring"],
                "refresh": "on_change",
            },
            "confirm": {
                "kind": "confirmation",
                "depends_on": execution + ["scoring", "population", "confirmation_inputs"],
                "refresh": "always",
            },
            "review": {
                "kind": "review",
                "depends_on": ["score", "confirm", "population"],
                "refresh": "always",
            },
        },
        "decisions": {
            "software_adoption": {
                "depends_on": ["review"],
                "description": "Numerical agreement with the independent fixed reference; deployment unresolved",
            }
        },
        "review": None,
    }
