# task-qualification-001 · evaluation lane report

**21 September 2026 · phase start 06:12:30 UTC.** Selection rule frozen at 06:14 UTC
before the inventory; screening of seven candidates; evidence-acquisition result;
conditional task contract. Commands under [`commands/`](commands/index.json).

## Result

No executable policy task held on this machine qualifies. The only one held, the robomimic
Lift PH BC-RNN with its simulator and executor, carries no stated weights license and
consumes no normalization statistics (`hdf5_normalize_obs` false, `obs_normalization_stats`
null), so a deployment differing only in bound statistics cannot be observed there
without manufacturing it. Nothing else held is
a policy task, and the GR00T policy on LIBERO is neither held nor runnable here. The rule
was applied without a network request, in about four CPU seconds, and every candidate's
first failed criterion is retained in [`screening-002.json`](screening-002.json), which
corrects the first record's C1 mark for the Lift checkpoint after the execution lane's
review.

## What would qualify

A Lift PH low-dim policy trained with observation normalization (path A1): one dataset
acquisition by the execution lane within the caps and a bounded local training run, both
outside the current authority. The contract for that study is frozen now, before any
comparative answer, with thresholds set from the task's controller and horizon:
[`TASK_CONTRACT.md`](TASK_CONTRACT.md). Binding statistics to the held checkpoint at
deployment is excluded as a manufactured incident.

## Also in this delivery

The three normalizer record gaps and two control instantiation differences are
dispositioned in [`../normalizer-execution-001/gap-disposition-001.json`](../normalizer-execution-001/gap-disposition-001.json):
none changes a conclusion; the adapter's expectation table was corrected (contract
amendment A2) and the sealed store re-assessed with zero mismatches. The conventional arm
gained a float32-faithful version 2 that decides every control as the reference does,
including NX5d; version 1 is retained as the historical float64 transcription.
