# Semantic reading: what the concrete normalizer selects, computes and saves

**21 September 2026 · evaluation lane · phase start 04:52:24 UTC.** Sources: the
coordinator's retained `processing_gr00t_n1d7.py` (`612558f7…`, Git blob `42a62395…`),
`state_action/state_action_processor.py` (`0151dd0b…`) and `data/utils.py`
(`fa765b24…`) at Isaac-GR00T `1a1837f2`, plus the previously retained loader
(`10eb986f…`), single-step dataset (`8d4cfeb4…`), mixture (`f452072c…`), demo
`modality.json` and `stats.json` (`8283e003…`). Every statement below is a static
reading of those bytes unless it says "computed"; nothing upstream was executed here.
The contract that follows from it: [`CONTRACT.md`](CONTRACT.md).

## 1. Population identity and the role of the parent summary (historical, closed)

The demo's `stats.json` is the 379-episode parent population's summary; the five files
are its episodes 0–4 (1,406 rows). That identity is a numeric fact and says nothing
about which statistics a processor consumes. This phase does not revisit it.

## 2. Which statistics the processor holds: initialization, `set_statistics`, override

`Gr00tN1d7Processor.__init__` builds a `StateActionProcessor` from the same
`modality_configs` and `statistics` it receives, and passes `use_percentiles`,
`clip_outliers`, `apply_sincos_state_encoding` and `use_relative_action` down. It
does not pass `use_mean_std`. The nested constructor calls `set_statistics(statistics)`
with the default `override=False` when statistics are given, so the nested
`statistics` dict holds them and `norm_params` is computed at once.

The outer object then sets its own `self.statistics = {}`, empty, whatever the
constructor received. So after construction with statistics, the outer mirror is empty
and the nested state is populated. Outer `set_statistics(new, override)` first updates
the mirror with the rule "key absent or override", then delegates the same call to the
nested processor, which applies the same rule to its own dict and recomputes every
embodiment's parameters. Consequences:

- Fresh processor plus one `set_statistics(S)` call: the nested state equals `S` for
  every embodiment, whatever the override value. The pinned training path does this
  with the merged dataset statistics.
- Processor constructed with `S0` (the `from_pretrained` path) plus
  `set_statistics(S1, override=False)`: the nested state keeps `S0` for embodiments
  already present and logs a warning; the outer mirror silently takes `S1` for those
  same keys, because it was empty. With `override=True` both take `S1`.
- `save_pretrained` writes `state_action_processor.statistics`, the nested state, not
  the mirror. The mirror never feeds a numeric operation in the retained sources.

Effective parameters on the pinned training path pass through
`merge_statistics` first. For one dataset with weight 1 the means, extremes and
quantiles are the identity, and the standard deviation is
`sqrt(std² + mean² − mean²)` in float64, which equals the shipped value exactly on all
fifteen LIBERO coordinates (computed). It is not the identity in general: a
standard deviation below about `1e-8·|mean|` collapses to zero and changes the
mean/std mask below.

## 3. What is computed: mode, formula, coordinate order, dtype

`_compute_normalization_parameters` reads, for every joint group of `state` and
`action`, `mean`, `std` and either `min`/`max` or `q01`/`q99` (`use_percentiles`),
each as `np.array(list)`. From JSON-origin lists these are float64. A floored range
`max(max − min, 1e-8)` is computed and discarded; only its length survives as `dim`.
No epsilon reaches the transform. All four keys are required for every group whatever
mode consumes them; a group lacking `std` fails even under min/max.

Per group, in `modality_keys` order, `apply_state` chooses:

1. sin/cos, if `apply_sincos_state_encoding` and the group is in the state config's
   `sin_cos_embedding_keys` (no statistics; dimension doubles; not invertible);
2. mean/std, if the state config's `mean_std_embedding_keys` is non-empty and names
   the group;
3. otherwise min/max, followed by `np.clip(·, −1, 1)` when `clip_outliers`.

`apply_action` chooses mean/std when the action config's `mean_std_embedding_keys`
names the group, otherwise min/max, and then clips when `clip_outliers` in both
branches. So a mean/std action group is clipped to one standard deviation while a
mean/std state group is never clipped. Relative actions replace a group's parameters
with `relative_action` statistics only when the action config says RELATIVE and
`use_relative_action` is set. The selector is the modality configuration; the outer
`use_mean_std` argument is stored, serialized and re-read by `from_pretrained`, and
nothing in the retained sources consumes it.

The formulas (`data/utils.py`), with `params` the float64 arrays above and `x` the
input array:

- min/max: `mask = ~isclose(max, min)` (numpy defaults, so a coordinate counts as
  constant when `|max − min| ≤ 1e-8 + 1e-5·|min|`); `out = zeros_like(x)`;
  `out[mask] = (x − min)/(max − min)`; `out[mask] = 2·out[mask] − 1`. Constant and
  near-constant coordinates map to 0.
- mean/std: `mask = std != 0` (exact); `out[mask] = (x − mean)/std`;
  `out[~mask] = x` (raw value passes through). A tiny non-zero `std` is divided by.
- inverse min/max: `(clip(y, −1, 1) + 1)/2·(max − min) + min`, no mask, no floor;
  inverse mean/std: `y·std + mean` on the mask, passthrough elsewhere.

`out = zeros_like(x)` fixes the output dtype to the input dtype. On the pinned path
the single-step dataset builds every state and action group with
`np.vstack([... .astype(np.float32)])`, so `x` is float32, the subtraction and division
are evaluated in float64 (float32 with float64 parameters promotes) and rounded to
float32 on assignment, and `2·out − 1` is then a float32 operation. The outer
`__call__` concatenates groups in `modality_keys` order, zero-pads to
`max_state_dim`/`max_action_dim` and converts to torch's default dtype. Integer inputs
would be truncated by the same `zeros_like`; NaN inputs propagate silently.

## 4. Saving and reloading

`save_pretrained` writes `processor_config.json` (the modality configs through
`to_json_serializable`, the flags, including the inert `use_mean_std`) and
`statistics.json` from the nested state via `.tolist()` and `json.dump`. Float64
values survive that round trip exactly. `from_pretrained` reads both files, backfills
`clip_outliers=True`, and calls the full constructor, which also builds the VLM
processor, image transforms and collator; the numeric path is rebuilt from the JSON
statistics through the same `set_statistics`. Behavioral equivalence after a round
trip therefore holds exactly on any domain when the pre-save parameters were already
float64 from lists, which is the pinned case; parameters held as float32 arrays would
reload as float64 and can change float32 outputs by an ulp. This equivalence is a
statement about `apply`, not about `unapply(apply(x)) = x`: min/max loses inputs
outside `[min, max]` (clipped) and on near-constant coordinates (mapped to 0, inverted
to the midpoint), and mean/std action groups lose `|z| > 1` when clipped.

## 5. What is known about a historical model or inference invocation

Nothing retained shows a training run or checkpoint for LIBERO: no
`processor_config.json`, no checkpoint `statistics.json`, no recorded
`override_pretraining_statistics` value, no inference call. `from_pretrained` reads a
checkpoint's statistics into the nested state, and `process_observation`/`unapply`
then use them; whether a released checkpoint's LIBERO statistics equal the shipped
file is unknown here and stays unresolved. A local invocation declared in this phase
proves its own execution only.

## 6. Software validity, decision correctness, comparative value

The numeric obligation for a declared local invocation is fully determined by the
sources above: statistics, mode selectors, flags, coordinate order and input dtype
give one expected output per row. The reference implements that operation
independently and grades executed outputs against it. A keep/replace decision is
graded by effective-map equivalence on the declared domain against the contract's
reference statistics, never by parameter equality or by labels. The concrete
`libero_sim` modality configuration is not retained (`embodiment_configs.py` is the
direct import that holds it), so the real-row invocation in this phase is a declared
local configuration unless the execution lane retains that file; the request is in
the lane record. Whatever this phase shows about executed behavior, it says nothing
about robot outcomes, and parity with a competent ordinary workflow remains the
expected comparative result until shown otherwise.

## Addendum, 05:12 UTC: the pinned LIBERO configuration is now retained

The execution lane captured `gr00t/configs/data/embodiment_configs.py` (`4c762642…`,
12,231 B) and `gr00t/data/types.py` (`329acd11…`, 4,970 B) as phase responses 5 and 6;
read here from its private capture by digest. `ModalityConfig` defaults
`sin_cos_embedding_keys`, `mean_std_embedding_keys` and `action_configs` to `None` and
has no `exclude_state` field. The `libero_sim` entry names state and action groups
`x, y, z, roll, pitch, yaw, gripper` in that order, state `delta_indices=[0]`, action
`delta_indices=range(16)`, and sets none of the three selectors. So every LIBERO group
takes min/max, no relative conversion applies, and edge 1 moves from constructed to
statically inferred for the pinned revision; the contract's declared configuration is
the pinned one. The historical checkpoint's `processor_config.json`, its statistics and
any training or inference invocation remain unretained and unresolved.

