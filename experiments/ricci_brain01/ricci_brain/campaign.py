"""Local, sequential campaign with a nominal gate and frozen held-out comparison."""

import json
from pathlib import Path

from .analysis import analyze, prefix_agreement, read_rows
from .episode import HERE, IMPORTED_SOURCES, digest, dump, run


def experiment(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    definition = json.loads((HERE / "campaign.json").read_text())
    dump(output / "definition.json", definition)
    records = []

    def trial(group, family, case, arm, **config):
        relative = f"{group}/{family}-{case:02d}-{arm}"
        result = run(output / relative, arm=arm, **config)
        record = {
            "group": group,
            "family": family,
            "case": case,
            "arm": arm,
            "path": relative,
            "result": result,
            "config": config,
        }
        records.append(record)
        dump(output / "index.json", records)
        print(
            json.dumps(
                {"episode": relative, "outcome": result["outcome"], "censored": result["censored"]}
            ),
            flush=True,
        )
        return record

    for i, values in enumerate(definition["nominal_development"]):
        trial(
            "nominal_gate",
            "nominal",
            i,
            "baseline",
            **dict(zip(definition["nominal_columns"], values, strict=True)),
        )
    nominal_pass = all(r["result"]["completed"] for r in records)
    dump(
        output / "nominal-gate.json",
        {
            "passed": nominal_pass,
            "required": 8,
            "completed": sum(r["result"]["completed"] for r in records),
        },
    )
    if not nominal_pass:
        result = {
            "status": "blocked_nominal",
            "reason": "Recovery comparison not run: nominal gate failed.",
        }
        dump(output / "summary.json", result)
        return result

    selection = definition["development_selection"]
    actions = definition["shared_actions"]
    scores = []
    for i, action in enumerate(actions):
        group = []
        for scenario in selection["scenarios"]:
            group.append(
                trial(
                    "selection",
                    scenario,
                    i,
                    "baseline",
                    scenario=scenario,
                    shared_action=action,
                    onset=selection["onset"],
                    slip_friction=selection["slip_friction"],
                )["result"]
            )
        score = (
            sum(r["completed"] for r in group),
            -sum(r["fall"] or r["drop"] for r in group),
            -sum(bool(r["constraint_violations"]) for r in group),
            -sum(r["censored"] for r in group),
            -i,
        )
        scores.append(score)
    selected = actions[max(range(len(actions)), key=lambda i: scores[i])]
    for family in selection["scenarios"]:
        group = [r for r in records if r["group"] == "selection" and r["family"] == family]
        reference = read_rows(output, group[0])
        if not all(prefix_agreement(reference, read_rows(output, r))["matched"] for r in group[1:]):
            raise RuntimeError(
                "Development selection has unmatched pre-decision histories; held-out evaluation refused"
            )

    sweep = definition["delay_sweep"]
    for scenario, mu in sweep["fixtures"]:
        family = f"{scenario}-mu{round(mu * 100):02d}"
        trial("delay", family, 0, "none", scenario=scenario, slip_friction=mu, onset=sweep["onset"])
        for j, action in enumerate(sweep["actions"]):
            for k, delay in enumerate(sweep["delays_s"]):
                trial(
                    "delay",
                    family,
                    j * len(sweep["delays_s"]) + k + 1,
                    "fixed",
                    scenario=scenario,
                    slip_friction=mu,
                    onset=sweep["onset"],
                    shared_action=action,
                    privileged_delay=delay,
                )

    frozen = {
        "status": "frozen_before_heldout",
        "shared_action": selected,
        "development_scores": dict(zip(actions, scores, strict=True)),
        "source_sha256": IMPORTED_SOURCES,
        "protocol_sha256": digest(HERE / "protocol.json"),
        "definition_sha256": digest(HERE / "campaign.json"),
        "privileged_mapping": {"slip": "plant_foot", "load": "track", "compound": "shared"},
        "privileged_limit": "Fixed inspectable selector; exhaustive tested action/delay diagnostics are separate. No optimal action-oracle claim.",
    }
    dump(output / "frozen-comparison.json", frozen)
    heldout = definition["heldout"]
    for i, values in enumerate(heldout["configurations"]):
        base = dict(zip(heldout["columns"], values, strict=True))
        for j, family in enumerate(heldout["families"]):
            config = {**base, "scenario": family, "shared_action": selected}
            if family == "shared_slip":
                config.update(scenario="slip", slip_friction=heldout["shared_slip_friction"][i])
            if family == "wrist_dropout":
                config["dropout_duration"] = 1.0
            arms = heldout["arms"][1:]
            rotation = (i + j) % len(arms)
            for arm in ["none", *arms[rotation:], *arms[:rotation]]:
                trial("heldout", family, i, arm, **config)

    for i, variant in enumerate(definition["stress"]["variants"]):
        for scenario in definition["stress"]["scenarios"]:
            for arm in definition["stress"]["arms"]:
                trial(
                    "stress",
                    scenario,
                    i,
                    arm,
                    scenario=scenario,
                    onset=4.5,
                    slip_friction=0.12,
                    shared_action=selected,
                    **variant,
                )
    result = analyze(output)
    dump(output / "summary.json", result)
    dump(
        output / "campaign-manifest.json",
        {
            "schema": "ricci-brain01.campaign-manifest.v1",
            "files": [
                {"path": str(p.relative_to(output)), "sha256": digest(p), "bytes": p.stat().st_size}
                for p in sorted(output.rglob("manifest.json"))
            ]
            + [
                {
                    "path": name,
                    "sha256": digest(output / name),
                    "bytes": (output / name).stat().st_size,
                }
                for name in [
                    "definition.json",
                    "index.json",
                    "nominal-gate.json",
                    "frozen-comparison.json",
                    "summary.json",
                ]
            ],
        },
    )
    return result
