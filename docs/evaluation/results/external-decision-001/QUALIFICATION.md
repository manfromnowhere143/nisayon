# Qualification: LeRobot issue 4415, normalization skipped after processor migration

**20 September 2026 · evaluation lane · block start 12:55:20 UTC.** Machine record:
[`qualification.json`](qualification.json). The frozen comparison is in
[`FROZEN_PLAN.md`](FROZEN_PLAN.md). Nothing below is a reproduced result yet.

## The incident as reported

A user loads `lerobot/smolvla_base` at its post-migration revision and calls the
postprocessor on a six-element action vector. The output equals the input. The
reporter attributes this to the migration having saved normalization statistics under
dataset-prefixed keys (`so100.buffer.action.mean`, `so100-blue.buffer.action.std`, …)
while the processor looks up the plain feature key `action`. A follow-up comment by the
same reporter says the preprocessor's statistics file carries no `observation.state`
keys at all, so state normalization has no statistics to use even if the key lookup were
repaired. A second user corroborated on 18 September that SmolVLA invoked through LeRobot
applies no normalization. The issue is open, labelled `policies`, `dataset`, `processor`,
`evaluation`, and proposes a suffix-match fallback that picks the first match when several
prefixed keys end with the feature name.

Everything in that paragraph is reporter-supplied. Both lanes have read it. Nothing in
this block is blind, prospective or an independent replication.

## What is verified without the reporter

Two tree listings of the model repository (3,022 bytes, retained under
`artifacts/external-decision-001/sources/` with digests and measured cost) establish:

- The later revision `c83c3163…` carries `policy_preprocessor.json` (1,872 B),
  `policy_postprocessor.json` (660 B), a 640-byte preprocessor normalizer state file and
  a 640-byte postprocessor unnormalizer state file. The two state files have the same
  LFS content hash, `490ab239…`. The preprocessor's statistics are therefore byte-identical
  to the postprocessor's, and the postprocessor only ever handles `action`. This is
  consistent with the reporter's claim that no state statistics were migrated. It is not
  yet a reading of the bytes.
- The earlier revision `3326b100…` has no processor files. Its `model.safetensors` is
  7,488 bytes larger than the later one. That is consistent with small buffers having been
  removed; the count and names are not derivable from size.
- The pinned `normalize_processor.py` at LeRobot `5aa74557…` (sha256 `f0cd88be…`) contains
  the mechanism the reporter describes. `load_state_dict` (lines 226–234) splits each flat
  key on its last dot, so `so100.buffer.action.mean` becomes feature key `so100.buffer.action`
  and stat `mean`. `_normalize_action` (line 299) always looks up the constant `action`.
  `_apply_transform` (lines 329–331) returns the tensor unchanged when the mode is IDENTITY
  or the key is absent. Observation features are looked up by their feature name
  (lines 278–284). The same file documents an explicit-statistics override that
  `load_state_dict` preserves (lines 50–72, 218–224) and `hotswap_stats` (559–584).
- torch 2.5.1 and numpy 1.26.4 are installed in the locked environment; `lerobot`,
  `safetensors` and `huggingface_hub` are not. The safetensors container is an
  8-byte length, a JSON header and raw bytes, readable without a dependency.

What remains reporter-supplied: the key names and dataset count in the 640-byte file,
the absence of state keys, the transcribed pre-migration so100 state statistics (two
decimals, twelve numbers), and the reproduction script. The reporter's LeRobot version is
not stated. The pre-migration checkpoint that held the original state buffers is out of
scope for this block: no weights and no range extraction. So the original state
statistics can only enter this work as a labelled, unverifiable transcription.

## Classification

This is a library-and-artifact defect at a migration boundary, not a loader misuse. The
migrated artifact stores statistics under names the pinned processor cannot resolve, and it
omits one statistics group entirely. It is not a corrected historical issue: the issue is
open, the pinned current main still has the exact lookup, and the later model revision
still ships the 640-byte file. The reporter's remedy is a candidate, not a specification:
its suffix match resolves an ambiguous name by iteration order, which is not a semantic
property of the deployment.

## Scope verdict: reduced mechanism only

There is no recorded working/changed robot deployment pair and no robot outcome. The
software mechanism can be reproduced faithfully: the processor step runs on the pinned
source with the actual configuration and statistics bytes, small arrays and installed torch,
with the `lerobot` imports replaced by minimal stand-ins whose recipe and boundary are
retained. The `make_pre_post_processors` loader is read from the JSON configuration, not
executed. A supported software correction here says nothing about a recovered grasp or a
safe policy, and one exposed incident supports no population claim.

## The decision

Under the pinned code and the later revision's artifacts, which candidate restores both
normalization obligations without an arbitrary statistics binding, and what remains
unresolved for deploying the base model?

Obligations, derived from the processor contract and the policy configuration rather than
from any Nisayon output (premises P1–P4 in the machine record await the bytes):

- **O1 (preprocess, state).** `observation.state` is transformed forward with MEAN_STD
  statistics bound to exactly one dataset.
- **O2 (postprocess, action).** The policy's action is transformed inversely with MEAN_STD
  statistics bound to exactly one dataset.
- **O3 (identity legitimacy).** Features whose mode is IDENTITY (visual inputs) stay
  unchanged, and unchanged output there is correct, not a defect.
- **O4 (binding).** The bound dataset is selected explicitly; a binding that changes with
  dictionary order is not a binding.

Candidates, frozen before any scored output:

| Candidate | Description | Expected under the premises |
|---|---|---|
| C0 as-is | load the later revision unchanged | rejected: O1 and O2 skipped |
| C1 suffix match | reporter's `_resolve_stats_key` fallback | rejected: O1 has nothing to match; O2 resolves to several datasets by order |
| C2 explicit override | documented upstream override with complete `action` and `observation.state` statistics | supported software correction of the mechanism, conditional on the supplied statistics; O4 for the base model unresolved because the only state statistics are a transcription |
| C3 re-migration | re-extract selector-bound statistics including state from the earlier checkpoint | the upstream repair; not executable here |

The "expected" column is a hypothesis table. If the bytes disagree, the bytes win and the
table is revised in a new version with the old one retained.

## Oracle premises

The reference is computed from the processor configuration and the statistics bytes,
never from the producer's answer function. For each feature and direction it classifies
the expected behaviour as one of: `identity_mode`, `skipped_no_stats`, `transformed`,
`ambiguous` (candidate resolves to more than one key), or `error` (a required statistic
such as `std` is missing, where the pinned code raises rather than skips).

Arithmetic: the upstream path is float32 with `eps = 1e-8`. Expected values are computed
in exact rational arithmetic from the float32 statistics and the float32 input, forward
`(x − mean) / (std + eps)` and inverse `x · std + mean`, and compared to the observed float32
output with a tolerance of four float32 units in the last place of the expected value plus
an absolute floor of 1e-6. A separate bit-level float32 emulation is reported alongside;
it is informative, not the acceptance rule. The tolerance covers the `eps` absorbed by
float32 addition at ordinary standard deviations and one rounding per elementwise
operation.

**Tolerance correction, version 2 (commit `2c82266`, 13:18:44Z, before the first
incident output was scored at 13:21:14Z).** The output-only rule above was wrong near a
fixed point: the rounded float32 product `x · std` is far larger than the output there,
and a correct torch result sat 16 ulp of the output away from the exact value. The
tolerance is now four times the sum of the float32 units in the last place of every
rounded intermediate and of the result, plus the 1e-6 floor; the contract in
[`PROCESSOR_REFERENCE.md`](../../PROCESSOR_REFERENCE.md) is the binding text. The
version-1 wording is retained here; no observation was scored under it.

A witness must be non-vacuous. For a `transformed` expectation, at least one element of
the expected output must differ from the input by more than the tolerance; an input at the
transform's fixed point (`x = mean / (1 − std)` elementwise for the inverse) cannot
distinguish a working transform from a skipped one and is reported as such. A forward
followed by inverse round trip with the same statistics is close to identity whatever the
statistics are, so a round trip is never evidence that the statistics are right.

## Challenge set

Constructed controls with labelled synthetic statistics; they are not incidents and do not
enter any incident count. Each asks one question the decision needs:

1. `identity_mode_visual`: an IDENTITY visual feature left unchanged is correct.
2. `fixed_point_witness`: an input at the inverse transform's fixed point is vacuous.
3. `prefixed_keys_exact_lookup`: prefixed keys with a plain feature key are skipped.
4. `suffix_match_ambiguous`: three prefixed datasets give three matches, and reordering
   the same statistics changes the candidate's output.
5. `suffix_match_partial`: a unique prefixed dataset repairs `action` while
   `observation.state`, with no statistics, stays skipped.
6. `explicit_override_complete`: explicit `action` and `observation.state` statistics
   transform both directions.
7. `round_trip_cancels_wrong_stats`: normalize then unnormalize with wrong statistics
   returns the input, while the normalized value disagrees with the reference.
8. `missing_std_error`: MEAN_STD with `mean` but no `std` is a raised error in the pinned
   code, not a silent skip.

## Readback against the bytes (added after the execution lane's capture)

Premises P1–P4 were verified from the actual configuration and statistics bytes in
[`premises-readback-001.json`](premises-readback-001.json): three datasets (`so100`,
`so100-blue`, `so100-red`), action statistics only, no `observation.state` key, the same
`norm_map` in both processors and in `config.json`. The hypothesis table above is
unchanged; the scored outcomes are in [`VERDICT.md`](VERDICT.md). One fact outside the
decision is retained: the preprocessor's visual feature names differ from the policy
config's, with an empty rename map.

## Alternate leads, for the record

Issue 3863 (relative actions assume a prefix-aligned state) is a feature request with a
linked PR 4111 and an explicit warning that a checkpoint trained on the wrong layout may
need retraining; a software layout check is feasible but cannot claim a repaired policy.
Issue 2702 is closed: the reporter's own comments trace the failure to a second
`from_pretrained` call resetting `to_transition`, and restoring the converter resolved it.
Neither is opened in this block unless the first lead fails qualification, which it has not.
