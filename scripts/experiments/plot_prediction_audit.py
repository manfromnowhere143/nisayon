#!/usr/bin/env python3
"""Render the retained constructed confirmation tradeoff; no new experiment."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence
    original = json.loads((root / "results.json").read_text())
    challenge = json.loads((root / "challenge.json").read_text())
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none"})
    fig, (left, right) = plt.subplots(1, 2, figsize=(12.6, 6.7), layout="constrained")
    styles = {
        ("native_full", "perfect"): ("Conventional sequential", "#24558b"),
        ("native_half", "perfect"): ("Random half sampling", "#64748b"),
        ("prediction_audit", "perfect"): ("Audit: perfect predictor", "#087e73"),
        ("prediction_audit", "noisy"): ("Audit: noisy predictor", "#b65c08"),
        ("prediction_audit", "positive"): ("Audit: always positive", "#873d9c"),
        ("prediction_audit", "inverted"): ("Audit: inverted predictor", "#b6323c"),
    }
    for cell in original["cells"]:
        if cell["truth"] != "19/20":
            continue
        label, color = styles[cell["method"], cell["channel"]]
        left.plot(
            [r["expected_acquisitions"]["decimal"] for r in cell["curves"]],
            [r["support"]["decimal"] for r in cell["curves"]],
            label=label,
            color=color,
            linewidth=2,
        )
    for cell in challenge["decision_preserving"]:
        if cell["truth"] == "19/20":
            color = styles[cell["method"], "perfect"][1]
            left.scatter(
                cell["expected_acquisitions"]["decimal"],
                cell["support"]["decimal"],
                marker="D",
                color=color,
                edgecolor="white",
                zorder=5,
                s=65,
            )
    best = challenge["best_binomial"]
    left.scatter(
        best["expected_acquisitions"]["decimal"],
        best["support"]["decimal"],
        color="#111827",
        marker="s",
        s=45,
        label="Best fixed binomial + early stop",
    )
    left.axhline(0.8, color="#667085", linewidth=1, linestyle=":")
    left.set(
        xlabel="Expected fresh acquisitions through stop or cap",
        ylabel="Probability of supporting the alternative",
        title="Same endpoint and 5% false-support limit",
        ylim=(0, 1.02),
        xlim=(0, 40),
    )
    left.plot(
        [], [], marker="D", color="#475569", linewidth=0, label="Diamonds: added futility stopping"
    )
    left.legend(loc="upper left", bbox_to_anchor=(0, -0.19), fontsize=8, ncol=2)
    left.set_title(
        "95% success vs null ≤80%; false-support limit 5%\nCurves show caps 1–80", fontsize=10
    )
    cost = challenge["cost_model"]
    saving = cost["acquisition_saving_in_execution_cost_units"]["decimal"]
    extra = cost["extra_contexts"]["decimal"]
    cutoff = cost["common_context_cost_break_even_relative_to_execution"]["decimal"]
    xs = [i / 200 for i in range(121)]
    ys = [saving - extra * x for x in xs]
    right.plot(xs, ys, color="#087e73", linewidth=2.5)
    right.axhline(0, color="#111827", linewidth=1)
    right.axvline(cutoff, color="#64748b", linestyle=":", linewidth=1)
    right.fill_between(xs, ys, 0, where=[y < 0 for y in ys], color="#fee2e2")
    right.text(cutoff + 0.012, 1.0, f"Break-even: {cutoff:.3f}", fontsize=9)
    right.text(
        0.025,
        0.97,
        f"Perfect predictor, after stronger native stopping\n"
        f"Maximum remaining allowance: {saving:.2f} executions",
        transform=right.transAxes,
        va="top",
        fontsize=9,
    )
    right.set(
        xlabel="Common context/reset cost ÷ fresh execution cost",
        ylabel="Allowance for all extra work (execution cost units)",
        title="Extra contexts can consume the acquisition saving",
        xlim=(0, 0.6),
        ylim=(-6, 6),
    )
    for ax in (left, right):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.15)
    fig.suptitle(
        "Prediction audits: a conditional opportunity, bounded by complete cost", fontsize=13
    )
    fig.savefig(root / "cost-tradeoff.svg")
    svg = root / "cost-tradeoff.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(root / "cost-tradeoff.png", dpi=180)
    print(
        json.dumps(
            {
                "matplotlib": matplotlib.__version__,
                "figure": "cost-tradeoff",
                "extra_experiment": False,
            }
        )
    )


if __name__ == "__main__":
    main()
