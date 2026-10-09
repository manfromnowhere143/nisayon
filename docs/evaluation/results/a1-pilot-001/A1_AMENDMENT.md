# Prospective A1 amendment: a rights-qualified artifact and a corrected training path

**21 September 2026 · evaluation lane · frozen before any acquisition or training under it.**
Machine form: [`a1-amendment.v1.json`](a1-amendment.v1.json). Scope correction of the
earlier verdict: [`pilot-verdict-003.json`](pilot-verdict-003.json). Discriminating
control: [`normalization-batch-control-001.json`](normalization-batch-control-001.json),
script [`normalization_batch_control.py`](normalization_batch_control.py).

## Scope correction

The stopped pilot's result stands under its original protocol: custody unresolved,
nothing executed. Two statements are corrected. Different verified lengths establish
that the Stanford object and the official object are not the same byte sequence; no
payload was downloaded and no digest of the Stanford object was computed or compared, so
the earlier "SHA-256 identity impossible" is withdrawn in favour of plain non-identity.
And only the byte-identity route to the repository's MIT declaration is closed; permission
for the Stanford object is unresolved, not refused, and the repository declaration is not
extended to it. Identity, permission, offline-training compatibility, simulator
compatibility and measured feasibility are kept apart, and headroom does not establish
an unexecuted pilot's feasibility.

## One acquisition decision

No retained record names an official terms source for the Stanford artifact, so no
lookup is requested and the explicit alternative is bound: `robomimic/robomimic_datasets`
at revision `74fa0184`, path `v1.5/lift/ph/low_dim_v15.hdf5`, publisher size 21,084,088
bytes, publisher LFS digest `2067777c…`, MIT on the card at that revision, evidenced by the
already retained repository metadata. These are publisher values, not a receipt: the
execution lane makes one reserved GET at that revision and path, checks the length before
the body, and verifies the size and digest after. The download keeps the phase within the
32 MiB new-dependency cap and brings the cumulative known source bytes to about 42.7 MB
of 64 MiB.

## A finding that changes the pilot

Before spending any update, a control ran the pinned robomimic 0.3.0 training path with
observation statistics and no dataset: `postprocess_batch_for_training` raises
`shape length mismatch in @normalize_obs` for every BC-RNN sequence batch, at batch sizes
100, 2 and 1, because `normalize_obs` only accepts inputs whose shape equals the
statistics' shape or drops one leading dimension. The rollout shapes pass. So the held
implementation cannot train the normalized BC-RNN family as configured; the first update
would fail. The smallest concrete amendment is a training-only override of that function
that broadcasts the `(1, D)` statistics over leading batch and time dimensions, declared
as a substituted boundary, digest-bound, and shown equal to the elementwise formula on
four shapes and bit-identical to the unchanged function on the rollout shapes. The
dataset-side statistics and the inference path stay unchanged. A robomimic upgrade or a
batch-size-one non-sequence model would change the held stack or the family and are not
chosen.

## Executable contract

Exactly 100 Adam updates in total, including any smoke test or retry: one epoch of 100
batches in the pinned entry point. BC-RNN GMM, LSTM two layers of 400, horizon 10, batch
100, sequence 10, learning rate 1e-4, seed 1, CPU with the two threads the entry point
sets, cache mode all, no data workers. Membership is every demo in the file's data group,
which is also the statistics population; any mask keys are recorded but unused;
validation, rollouts, rendering, video and remote logging off. Statistics come from the
unchanged dataset code (float32 per-trajectory merge, population std plus 1e-3, so a
constant coordinate divides by 1e-3). One checkpoint after epoch 1, never selected by
loss or rollout: an inference checkpoint of about 8.0 MB (about 1.99 million float32
parameters, matching the held zoo checkpoint's size) without optimizer or random-number
state, so not resumable. Checkpoint and telemetry stay within 16 MiB durable; the dataset
is a source body. Start, load, statistics, all 100 update times, save, total wall and CPU
are measured. An interrupted run keeps its log, declares its update count, claims no
checkpoint and does not restart beyond the remaining updates.

## Acceptance checks, frozen

Q1 size and digest against the publisher metadata and the card's declaration. Q2 keys,
dims, order, dtype, action range and membership read from the file, the override control
passed beforehand, no environment construction in the log. Q3 the checkpoint's statistics
against this lane's own recomputation from the rows within float32 tolerance, and a
recorded first batch whose normalized values this lane recomputes; a flag is not evidence.
Q4 100 finite per-update losses and timestamps and a parameter change between the first
and last update. Q5 a load through `policy_from_checkpoint` that binds the statistics,
without a rollout. Q6 costs in distinct scopes and a continuation estimate from the median
and maximum update times plus fixed costs. Q7 every failure and disclosed call retained.
The pilot can answer A for the substitute artifact, B, and, if it completes, C, D and E. It
cannot answer simulator compatibility, competence, any intervention or comparative value,
and it does not touch the original external-incident objective.

## Amendment v1.1 (10:25 UTC): the transformation must be applied exactly once

The independent statistics reference ([`statistics-reference-control-001.json`](statistics-reference-control-001.json),
script [`statistics_reference_control.py`](statistics_reference_control.py)) reproduces
robomimic's bound statistics bit for bit on a synthetic file and agrees with the exact
float64 computation within 6.3e-7 on means. Its executed witnesses add a second finding
([`findings-001.json`](findings-001.json)): the dataset's own `get_item` also calls
`normalize_obs`, so sequence items fail at dataset construction, and where the shape
checks pass (sequence length one, batch size one) the learner receives a double
normalization, because `train.py` normalizes items in the dataset and again in
`postprocess_batch_for_training`. [`a1-amendment.v1.1.json`](a1-amendment.v1.1.json)
therefore requires, before any update, both the broadcasting override and a
Nisayon-owned driver that reproduces the pinned loop but passes no statistics to
`run_epoch`, so normalization happens once in `get_item` while `save_model` still
receives the statistics; the first-batch hook must prove a single application. A
constant coordinate's float32 std is 0.001000013 rather than exactly the 1e-3 offset,
a rounding fact the reference reproduces. Nothing under either version has run.

## Amendment v1.2 (wording only)

The execution lane's integration finding is right: v1.1 said a constant coordinate
divides by exactly `1e-3` and maps to exactly zero, while the retained control measures
`0.001000012969598174` under float32 accumulation. [`a1-amendment.v1.2.json`](a1-amendment.v1.2.json)
states it as measured: a constant coordinate's bound std lies within float32 rounding of
the offset and its normalized values within about `1e-5` of zero. No formula, tolerance,
check, limit or expectation changes.
