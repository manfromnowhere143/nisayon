"""Cross-object bindings. These checks never choose an experiment decision."""

from .bytes import ExportError


def require(condition, message):
    if not condition:
        raise ExportError(message)


def check_context(case, sources, objects):
    decisions = [objects[ref["path"]] for ref in case["decisions"]]
    by_bundle = {}
    for decision in decisions:
        bundle = decision.get("execution_bundle_sha256") or decision["bundle_sha256"]
        require(bundle not in by_bundle, "duplicate evaluator scope")
        by_bundle[bundle] = decision
    runs = {(run["key"]["bundle_sha256"], run["key"]["run_id"]): run for run in case["runs"]}
    for key, run in runs.items():
        decision = by_bundle.get(key[0])
        require(decision is not None, "run has no bound evaluator record")
        evaluated = decision["runs"].get(key[1])
        require(run["evaluator"] == evaluated, "run/evaluator projection mismatch")
        require(run["stage"] == decision["stage"], "run/evaluator stage mismatch")
        require(
            evaluated is not None and evaluated["condition_id"] == run["condition_id"],
            "run/evaluator condition mismatch",
        )
        # The retained evaluator groups executed prefix context under its probe
        # role. Keep the producer label and evaluator label as separate fields.
        require(
            evaluated["role"] == run["role"]
            or (run["role"], evaluated["role"]) == ("executed_prefix_context", "probe"),
            "run/evaluator role mismatch",
        )
        require(
            evaluated["outcome"]["claimed"] == run["task_outcome"], "claimed task outcome mismatch"
        )
        # Producer measurement status may be valid while evaluator measurement is
        # unresolved (D10). Those fields intentionally are NOT equated here.
        visited = {key}
        parent = run.get("cost_parent_run_id")
        while parent:
            parent_key = (key[0], parent)
            require(parent_key in runs and parent_key not in visited, "invalid nested cost parent")
            visited.add(parent_key)
            parent = runs[parent_key].get("cost_parent_run_id")
    trial = case.get("trial")
    if not trial:
        return
    require(trial["source"]["source_id"] in sources, "trial source missing")
    require(
        trial["case_id"] == case["case_id"] and trial["arm"] == case["arm"], "trial scope mismatch"
    )
    final = decisions[-1]
    require(trial["decision"]["decision"] == final["decision"], "trial/evaluator decision mismatch")
    require(
        trial["decision"]["sha256"] == sources[final["source"]["source_id"]]["sha256"],
        "trial/evaluator byte identity mismatch",
    )
    for control in trial.get("derived_controls", []):
        require(
            control["executed"] is False and control["available_as_recorded_run"] is False,
            "proposal represented as executed",
        )
        source = sources.get(control["source"]["source_id"])
        require(
            source is not None and source["sha256"] == final["bundle_sha256"],
            "proposal decision source mismatch",
        )
        require(
            (control["execution_bundle_sha256"], control["run_id"]) not in runs,
            "proposal has a recorded future",
        )
    confirmation = case["confirmation"]
    if confirmation["availability"] != "recorded":
        return
    bundle = confirmation["bundle_sha256"]
    require(
        bundle in by_bundle and by_bundle[bundle]["stage"] == "confirmation",
        "confirmation evaluator scope mismatch",
    )
    for field in ["source", "protocol_source", "joint_freeze_source"]:
        require(confirmation[field]["source_id"] in sources, "confirmation source missing")
    require(
        confirmation["result"]["status"] == trial["status"], "trial/confirmation status mismatch"
    )
    require(
        confirmation["result"]["decision"]["decision"] == by_bundle[bundle]["decision"],
        "confirmation decision mismatch",
    )
    identities = [(p["role"], p["condition_id"]) for p in confirmation["pairs"]]
    require(len(identities) == len(set(identities)), "duplicate confirmation condition")
    fresh = [p["condition_id"] for p in confirmation["pairs"] if p["role"] == "fresh"]
    require(
        fresh == confirmation["fresh_condition_ids"], "confirmation condition coverage mismatch"
    )
    require(len(fresh) == confirmation["summary"]["fresh_declared"], "confirmation count mismatch")
    for pair in confirmation["pairs"]:
        for role in ["reference", "candidate"]:
            key = pair[role + "_run"]
            require(
                key == {"bundle_sha256": bundle, "run_id": pair[role + "_run_id"]},
                "paired run key mismatch",
            )
            run = runs.get((key["bundle_sha256"], key["run_id"]))
            require(
                run is not None and run["condition_id"] == pair["condition_id"],
                "paired condition/run mismatch",
            )
            require(
                run["evaluator"]["outcome"]["observed"] == pair[role + "_outcome"],
                "paired outcome mismatch",
            )
            require(
                run["evaluator"]["measurement"] == pair[role + "_measurement"],
                "paired measurement mismatch",
            )
