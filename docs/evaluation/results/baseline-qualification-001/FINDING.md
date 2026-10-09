# Finding: a provenance label alone promoted the deployment binding

**20 September 2026 · evaluation lane · block start 15:59:21 UTC.** Machine record:
[`finding-001.json`](finding-001.json). Before-assessments: [`before/`](before/).

## What was observed

The processor reference at commit `25637ab` (`processor_reference.py` sha256
`2779e423…`, the file at private main `34bda84`) decides `deployment_binding` from the
set of `stats_provenance` labels on a candidate's explicit-override rows. Three labelled
copies of the original arm A record `conventional-a-v1.json` (sha256 `33bc318b…`,
unchanged) were assessed with the public `processor` command against the same five
digest-verified inputs:

| Copy | Only change | C2 outcome | C2 binding |
|---|---|---|---|
| `original` | none | supported software correction | unresolved |
| `provenance-label-only` | three labels set to `verified_training_statistics` | supported software correction | **supported** |
| `artifact-label-only` | one label set to `artifact` | supported software correction | **artifact_bound** |

No statistic, input, output, source byte or selector evidence changed. The coordinator
first observed the first promotion (two calls, 0.216 s wall, 0.169 s child CPU, counted
once in combined costs); this lane reproduced it and the second path under its recorder
(commands `e5b4f475`, `6cd84a2c`, `66ba1f8f`).

## Scope

This is a defect of the public flat-record path and of the adapters that build such
records. No sealed store was altered. No retained historical assessment claimed a
supported binding; the original C2 binding was, and remains, unresolved. Nothing here
concerns a robot outcome.

## Why it is wrong

A record may say its statistics were verified. The evaluator's job is to distinguish that
assertion from what its own inputs establish. The current contract lets the evaluator
establish, at most, that a transform matches its declared statistics and that a
statistics set was read from, or equals, bytes in a digest-verified artifact. It carries
nothing that establishes which model, dataset and feature semantics the statistics belong
to, or which statistics the target deployment actually selected. A label cannot supply
those facts, so a label must not decide the binding.

## The correction

Rule `external-decision-001/v2`, assessment schema
`nisayon.processor-reference.assessment.v2`. Version-1 assessments stay retained and are
marked historical where they are superseded. Under version 2:

- `stats_provenance` is a declaration: retained, reported and compared with what the
  evaluator established; never a premise.
- Four facts are reported separately per candidate and feature: numeric agreement, byte
  provenance, interpretation and selection.
- Byte provenance is established by the evaluator for `as_is` and `suffix_match` (the
  bound statistics were read from the verified state file) and, for an explicit override,
  only for a feature whose override values equal a statistics set read from the verified
  artifact. Interpretation and selection are not carried by the contract and are reported
  as not established.
- Supported binding is therefore unreachable under the current contract, and the
  assessment says so with the missing inputs named. The supported software correction and
  the unresolved deployment conclusion are preserved. A label the evaluator cannot
  establish is a named finding, not a process failure.

Request to the execution lane, carried in `work/lanes/fable5.md`: unsupported provenance
annotations must not become a binding premise in the new baseline either.
