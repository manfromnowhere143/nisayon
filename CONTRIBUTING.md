# Working on Nisayon

Read [the handoff](docs/SESSION_HANDOFF.md), run `uv run nisayon start`, and choose
the next bounded task in `work/queue.json`. Development commands and memory
conventions are in [development](docs/DEVELOPMENT.md).

A useful change explains the problem, implements the smallest complete slice,
and checks the failure path that matters. Preserve unrelated work. Prefer one
clear source of truth to duplicated configuration or prose.

Before handing off:

1. Run `make check` and any experiment-specific check the change requires.
2. Inspect the diff and record material limitations.
3. Save a checkpoint with the next action; update the handoff if state changed.

Research results need conditions, comparator, denominator, complete costs and
retained evidence. A green software test is a software result. See the
[research plan](docs/RESEARCH_PLAN.md) for the product's first experiment.

Use the configured human Git identity. Keep credentials, datasets, videos and
model weights outside Git. Nisayon uses [Apache-2.0](LICENSE). Submit only work
you have the right to contribute; intentionally submitted contributions follow
section 5 of that license unless explicitly stated otherwise or covered by a
separate agreement. Preserve third-party notices. See [licensing scope](docs/LICENSING.md).
