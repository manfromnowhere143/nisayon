# Explicit investigation designs · 2 November 2026

A proposal with correct quotations could previously say “Run more tests.” without
predictions, an oracle or a cost boundary. The existing investigation worker now
requires one versioned experiment design for an investigation and an empty design
for a wait or reply. Historical v1 records remain readable with missing checks
marked `not_checked_legacy`.

A v2 design binds predicted observations to alternative answers, names the minimum
execution and the oracle's measurement, identity, independence and limitations,
and records eight resource estimates with a basis or an explicit unknown. The
checker rejects incomplete fields and malformed estimates. It does not validate
causal interpretation, oracle truth or source completeness. Execution, delivery
and lesson promotion remain unauthorized by the proposal.

## Exposed comparison and limits

The retained 22-case component comparison admits 19 incomplete plans under v1.
V2 and an ordinary JSON Schema plus direct checklist both match all 22 finite
completeness labels. Neither blocks the two reviewable cases; one deliberately
contains a correct quote used for a wrong causal conclusion. Semantic correctness
remains unadjudicated. These are investigator-authored development fixtures,
not independent deployment outcomes or evidence of statistical generalization.
The original data and result are retained beside this file.

Twenty-four added software controls cover malformed designs, explicit unknowns,
legacy readback, nonfinite costs, repeated execution and the semantic/authority
boundary. The twelve separate `review-fixtures.json` cases expose unsupported
causes, stale evidence, omitted completed work, compression, maintainer intent,
retry costs, invalid reuse, premature delivery and unjustified refusal. They
specify reviewer obligations; the checker does not detect those semantic errors.

A separate known-case agent feasibility pilot did not complete its A/B/C
comparison. Its ordinary-agent arm used 148,429 input tokens (106,368 cached)
and 1,765 output tokens, triggering the frozen post-call stop at 150,000 combined
tokens. Its response failed exact-quotation/action-shape validation. B/C did not
run. No selective-retrieval, semantic-correctness or complete-cost advantage can
be estimated. Charges and full engineering effort remain unknown. The twofold
complete-cost target is unchanged and unproved.

## Reproduce

Run from the repository root; choose a new output directory. The comparator
reads the original public v1 worker at `0727ba6cde880b1432f591aabd7b2f230f493f08`
from Git, and the installed current worker. It refuses to overwrite results.

```sh
uv sync --frozen
uv run --frozen pytest tests/test_engagement_agent.py tests/test_engagements.py
uv run --frozen python docs/experiments/results/investigation-design-2026-11-02/compare_contracts.py --out /tmp/nisayon-design-comparison-new
```

The public comparator changes only the source-history locator and output-path
selection from the retained development script. Its fresh public-checkout result
is recorded in `public-comparison.json`; the source manifest binds both versions.
No model, GPU, owner data or external correspondence is needed for this replay.
See [the worker contract](../../../ENGAGEMENT_INVESTIGATIONS.md) and
[the owner comparison](../../../OWNER_COMPARISON.md). An actual owner decision,
independent outcome reference and untouched transfer remain prerequisites for
stronger claims.
