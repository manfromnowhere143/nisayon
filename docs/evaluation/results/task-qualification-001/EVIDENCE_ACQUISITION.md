# Evidence acquisition result for task-qualification-001

**21 September 2026 · evaluation lane.** Machine records:
[`screening-002.json`](screening-002.json) (superseding [`screening-001.json`](screening-001.json) on C1), [`evidence-acquisition-002.json`](evidence-acquisition-002.json);
selection rule frozen first: [`SELECTION_RULE.md`](SELECTION_RULE.md).

## What is held, and why nothing qualifies

The read-only inventory of five roots found one executable policy task on this
machine: the public robomimic BC-RNN Lift PH low-dim checkpoint
(`lift_ph_low_dim_epoch_1000_succ_100.pth`, `3ee222ca…`), with robosuite 1.4.1,
MuJoCo 3.2.7 and torch 2.5.1 locked in the simulation extra and a deterministic
executor that already reproduces seed-0 trajectories on this host. Its checkpoint was
inspected after digest verification: `hdf5_normalize_obs` is false,
`obs_normalization_stats` is null and there are no action statistics. robomimic
binds normalization only when the checkpoint carries statistics, and refuses them
otherwise. So the working deployment binds no statistics, and a changed deployment
that "differs only in the bound statistics" would bind statistics the policy never
consumed: a manufactured regression, which the rule excludes. Four of seven criteria pass:
the weights carry no stated license, so C1 is unresolved, and the statistics path and the
intervention fail. The first record marked C1 as a pass with that caveat; the execution
lane pointed out that the frozen criterion does not allow it, and `screening-002.json`
corrects the mark without relaxing anything.

Every other held asset is not a policy task: torchvision detection checkpoints, a GPT-2
cache and leaderboard datasets, an Isaac Lab demonstration record without a simulator,
two Docker images. The GR00T N1.7 policy on LIBERO, whose normalizer the previous phase
bound numerically, is not held: no weights, no simulator, no GPU, and its acquisition
exceeds every cap. The LeRobot SmolVLA phase retained only processor statistics.

## The smallest acquisition that yields a qualifying case

Path A1: a Lift PH low-dim BC-RNN trained locally with `hdf5_normalize_obs` true. That
needs the public Lift PH low-dim dataset, whose exact file, size and license the
execution lane can verify with one request against the 32 MiB new-dependency cap, a
bounded CPU training run, which the current assignment does not authorize, license
evidence for whatever checkpoint is executed, and a telemetry plan that keeps sixty
rollouts inside the 16 MiB durable cap (the full profile cost about 77 MiB for 69 runs). The rest of
the chain exists. After acquisition the study is an exposed intervention: the trained
checkpoint with its own statistics against the same checkpoint with candidate statistics
bound, everything else fixed, both arms deciding before fresh confirmation seeds. The
conditional contract is frozen in [`TASK_CONTRACT.md`](TASK_CONTRACT.md).

Path B, GR00T on LIBERO, is not feasible under existing authority or on this host. Path
A2, binding statistics to the held checkpoint at deployment, is listed only so that no
one re-derives it as a shortcut; it manufactures the incident.

## Next execution action

Daniel decides whether to authorize A1 with a declared dataset and training budget. If
authorized, the execution lane verifies and acquires the dataset within the caps and runs
a measured one-epoch pilot before committing an epoch budget. If not, this line returns
unresolved and stops; no metadata work changes that.
