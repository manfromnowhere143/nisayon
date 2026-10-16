# Amendment before candidate execution

The original protocol and first probe remain unchanged as PROTOCOL.md and
probe-initial.py. The first native run correctly reports REVIEW/0 for valid
comparisons because optional trajectory channels are absent. Ten positive-control
expectations incorrectly required PASS. Correct those expectations to REVIEW;
the incomplete-identity requirement stays cannot_compare and BLOCK/1. Inputs,
thresholds, acceptance obligations and source patch are unchanged.

# Identity inference must cover the records it labels

**N038 · 15 October 2026 · frozen before software execution.** Source inspection
suggests that Arisole 0.1.5's unanimous-identity inference ignores absent fields.
This is an exposed, source-derived software check, not blind fault discovery.

Decision: may we rely on the newly released identity inference when comparing
existing deployment records? The release claims to copy observed identity
without inventing values. Infer a run-wide task or suite from records only when
all relevant entries supply the same nonempty string. Explicit run metadata
and attributed operator overrides remain declarations, with their existing
precedence. They do not become independently verified facts.

Compare three explanations: the inference really requires complete agreement;
it silently discards unknown identity; or package/fixture differences explain
the apparent discrepancy. Bind published wheel and sdist hashes before execution.
Use the normal parser, normalization, comparison, gate and local CLI. No policy,
simulator, network upload or hardware execution. Disable optional telemetry.

## Frozen control families

Use 30 unique seed-labelled, successful constructed records where applicable;
these are software fixtures, not real or statistically independent trials.

- Complete uniform task groups and complete uniform episode task names infer
  the declared identity. Known disagreements and absent identities do not.
- A task group missing on one entry, explicitly null, blank or whitespace-only
  must not establish a run-wide suite. A malformed entry must not disappear
  from the evidence needed for a unanimity claim.
- A task name missing on one episode, explicitly null, blank or whitespace-only
  must not establish a run-wide task. Neither does a malformed episode entry.
- Supply an explicit environment with incomplete episode tasks to isolate task
  inference. Supply no metadata with incomplete task groups to test the full
  comparison boundary. Both must return cannot_compare and default BLOCK/1,
  rather than REVIEW/0. This is the reporter's incompatibility rule, not evidence
  that a robot failed.
- Explicit run metadata and CLI overrides must retain precedence and attributed
  sources. A complete, seedless multi-task input remains unpaired and cannot
  receive a paired-success verdict.
- Reorder entries: inference and gate disposition must not depend on which
  incomplete entry is last. Do not redesign seed-pairing in this check.

Run unchanged 0.1.5 first, retain all outputs, then apply only an inference
coverage correction in a separate source tree and run the identical inputs.
Run all original sdist tests against both package variants. Preserve all setup
and test failures. Verify package and input hashes and show the source diff.
Acceptance requires all declared controls, original tests, and preservation of
explicit precedence, complete inference and seedless behavior. A failure keeps
the release unqualified for the affected path.

Boundaries: one source module, local CPU, one isolated environment pinned to the
previous reporter dependencies, no new runtime integration. Cap new package and
source downloads at 100 MiB and each subprocess at 120 seconds. Preserve all
retained environments. Execution clocks measure software cost only; human effort,
agent charges, owner adoption and maintenance remain unknown. Even a corrected
software gate does not prove physical pairing, fresh confirmation, comparative
cost savings or correctness of arbitrary user metadata.

If this check exposes a defect, retain a minimal patch and executable controls.
No new reminder or duplicate request is needed. Any technical follow-through
must describe the tested scope and preserve the existing pending threads.
