# N034: preserve measured work when parent costs are unknown

Frozen 14 October 2026, 06:00 UTC, after source inspection and before the
probe or correction. Baseline: `335ac01de3a07ea11a83bb5c7648a437d20cd7ac`.

The execution ledger already counts a measured prefix when its parent's wall
cost is unknown. The evaluator currently excludes a child whenever its parent
record exists. Test whether this loses measured work, then correct only the
existing cost report. This is an exposed software check, not a new robot trial
or an independently held-out evaluation.

The falsifier is simple: a two-second prefix plus an unmeasured parent must
retain two known seconds and explicit missingness. A measured eight-second
inclusive parent must still report eight seconds, not ten. Test omitted parent
items, longer chains, a measured grandparent, an absent parent, independent
runs, multiple children and real zero measurements. Cyclic ancestry, negative
costs, incompatible units and a child larger than its inclusive ancestor must
not produce a usable numeric total. Keep the individual records available.

Compare the same cases before and after the change. Use the existing command
ledger as an additional comparator on valid, single-unit wall cases; it is not
an independent scientific evaluator. Read the already-exposed D05 diagnostic
bundle unchanged and a copy with one parent cost replaced by explicit
missingness. Never edit the retained bundle or rerun its simulator conditions.

Acceptance: all declared controls pass; the unchanged D05 known and nested
totals remain equal; the interrupted copy retains the measured prefix; outcome
assessments remain separate from cost validity. Add regressions through both
the aggregation function and the public evaluator. Run the repository checks.
Preserve failures, source identities, commands, timings and the pending-thread
readback. Recorded command durations do not measure complete human/agent cost.

Resources: existing frozen base environment, CPU-only local software. No new
dependencies, policy execution, training, simulator trials, hardware or cloud.
Cap this investigation within the standing four-hour intake allocation.
No generic importer, backend or selector is warranted by this check. N015's
owner decision and complete comparative-cost requirement remain open.
