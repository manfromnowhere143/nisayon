# Acceptance criteria for the A1 feasibility pilot

**21 September 2026 · evaluation lane · frozen before any pilot output.** Machine form:
[`pilot-acceptance.v1.json`](pilot-acceptance.v1.json). State at freeze: main, execution
and evaluation all at `42d2756`; seven screened candidates, zero qualified tasks and zero
assigned or executed trials preserved from task-qualification-001.

## Scope

A1 trains a controlled experimental policy, a Lift PH low-dim BC-RNN with observation
normalization, so that a keep/replace decision on bound statistics can later be
adjudicated on an executable task. It does not reproduce an independently discovered
deployment failure; that objective stays outstanding whatever the pilot shows. The pilot
answers one question: can the execution lane acquire the dataset lawfully, train under
CPU-only bounded resources with normalization actually applied, and seal a checkpoint
whose statistics and replay capability are established, within measured costs?

## Authorization

Daniel's assignment names the pilot and gives acquisition and training to the execution
lane. No committed record yet states the numeric limits. The pilot is acceptable only if
a record naming the dataset byte limit, the training step or CPU budget, the storage bound
and the rollout prohibition is committed before the first acquisition or training command.
This lane makes no request and reads the execution lane's packet by digest.

## Checklist

Each item separates what the configuration says from what the execution shows.

1. **Rights and compatibility.** Dataset URL, bytes, digest and retained license terms
   permitting local research use and training; the dataset's environment arguments match
   the locked robosuite 1.4.1 executor without conversion.
2. **Membership and population.** The demo keys and frame counts the dataset iterated,
   and statistics computed over exactly that population (robomimic: float32 mean and
   population std plus 1e-3, merged per trajectory). This lane recomputes them from the
   retained rows within float32 tolerance, or marks the item unresolved.
3. **Effective normalization.** `hdf5_normalize_obs` true is a declaration; acceptance
   needs a batch-level or call-level witness (a harness hook that records the first
   batch's per-key mean and std after `postprocess_batch_for_training`, without altering
   training) plus the same statistics saved in the checkpoint.
4. **Workload and device.** Executed gradient steps against the declared budget, per-step
   wall times as min, median and max, initialization and data-loading time, CPU only.
5. **No automatic rollouts.** Rollouts disabled in configuration and absent from the log;
   any rollout turns the pilot into a development execution and must be declared.
6. **Checkpoint identity.** Bytes and digest, the statistics inside the checkpoint, and a
   witnessed load through `policy_from_checkpoint` without a rollout. Replay capability is
   declared, not demonstrated, until a rollout is authorized.
7. **Costs and failures.** Outer wall, process CPU, disk, download and temporary bytes in
   distinct scopes, never added across nesting; every failure retained; unknowns named.

## Possible conclusions

Executability, custody and resource feasibility are each feasible, infeasible or
unresolved. A training loss, one completed epoch or a saved checkpoint establishes
executability only. The pilot cannot establish task competence, any keep/replace
decision, comparative value, or that the original objective is satisfied. A continuation
estimate uses the median and maximum per-step times plus initialization, loading and
checkpoint writing, multiplied by the epoch budget, with its uncertainty stated; the
fastest batch is never the basis.

## Predeclared for task evaluation, not activated

If the pilot is feasible and full training is authorized: the trained policy qualifies as
the working deployment only with at least 8 of 10 successes on development seeds 200–209,
budgeted outside the contract; the checkpoint is the final epoch or a predeclared one,
never chosen by rollout success on a contract seed; seeds 200–209 develop, 0–9 screen,
100–109 confirm; the float32-faithful conventional workflow is extended to robomimic's
normalization order; the endpoint is decision quality at an equal rollout budget, then
complete cost. The sixty-rollout contract stays unassigned; a ceiling of seventy would be
an amendment recorded before any outcome. Nisayon's candidate contributions, a
population-identity check, the dtype-faithful map comparison with the four-level
distinction, and automatic retention, are stated now; both arms read the same packet, and
parity is reported as parity.
