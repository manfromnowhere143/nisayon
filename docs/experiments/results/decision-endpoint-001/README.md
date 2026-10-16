# Success criteria can reverse a policy choice

**12 October 2026 · N027 · recorded-analysis reproduction complete.**

The same saved PushCube trajectories favor different policy–controller pipelines
under two success definitions. Nisayon reproduced this published finding across
the full fixed comparison, using the authors' analyzer first. The useful next
requirement is an explicit owner objective and sampling model. This result does
not establish a new ranking method or justify a general analysis backend.

[Decision and alternatives](DECISION.md) · [frozen protocol](protocol.json) ·
[executed readback](result.json) · [costs and failures](cost.json)

## What was checked

The [public v2.0.0 release](https://zenodo.org/records/22960588) of
[benchmark-ranking-determinacy](https://github.com/Jun-Jason-Ji/benchmark-ranking-determinacy/tree/f7d608c0b2674ea140970d549b144b666c4d5228)
provides 80 cells: two tasks, two fixed pipelines, five arm settings and four
batches of 256 scenes. We downloaded only the selected 135-file confirmation
packet and necessary provenance. All 20,480 rollouts were already recorded by
the authors; **Nisayon ran zero new policy or robot trials**.

- The unchanged portable analyzer reproduces the archived result structure,
  counts and nonfloating values exactly; the largest float difference is
  `2.23e-16` or less. It ran on a copy; original inputs remain unchanged.
- A separate reader reproduces all 20 primary contrasts and four envelopes.
  Alternative SciPy exact-binomial calculations agree within `4.90e-13`, below
  the frozen `1e-10` tolerance. This is a second calculation of exposed evidence.
- All **40,960** step-50/step-100 labels agree with the success predicates
  recomputed from saved states. The three required ManiSkill 3.0.1 source files
  match the recorded runtime hashes. The Panda configuration comes from the
  same official tag; its original installed-file hash was not recorded.
- Full initial-state dictionaries and per-slot states match across the ten
  pipeline/setting cells of each batch. Each task has 1,024 distinct projected
  initial states, with no overlap in the retained exploratory references.
  Checkpoint hashes agree with freshly fetched metadata at the pinned upstream
  dataset revision; weights were neither downloaded nor executed.
- The original 256-episode technical repeat has identical states, observations
  and sequences. It contributes no additional independent evidence.

The four nominal comparisons below each use 1,024 paired scenes. Intervals are
the published union-bound exact-discordance envelopes across five settings,
conditional on the independent, identically distributed scene sampling model.
The 20-comparison family uses alpha 0.05 and component tail probability 0.000625.

| Task | Success definition | Joint successes | Cartesian successes | Five-setting difference envelope |
|---|---|---:|---:|---:|
| PickCube | At least once by step 50 | 994 | 659 | [+0.241, +0.439] |
| PickCube | At step 50 | 985 | 648 | [+0.247, +0.441] |
| PushCube | At least once by step 50 | 1,024 | 824 | [+0.123, +0.369] |
| PushCube | At step 50 | 18 | 323 | [−0.440, −0.154] |

Every batch has the corresponding sign across all five settings. That does not
prove independence. The predeclared sensitivity instead treats four batches as
independent bounded observations. Its simultaneous Hoeffding radius is 1.828,
versus 0.114 under 1,024 independent scenes, yielding **[−1, +1]** throughout.
This conservative calculation is uninformative; it neither refutes the authors'
scene model nor establishes equal pipeline performance.

Actions continued after first success. Deadline success does not establish
sustained holding, and these records cannot tell us what an early-stop controller
would have done. Changing that behavior requires new trajectories. Different
checkpoints accompany the two controllers, so the comparison cannot isolate a
controller-only causal effect.

## Implication for Nisayon

Fresh research on flow-policy uncertainty and IndustrialVLA-Bench is retained in
the [decision packet](DECISION.md), including implementation and comparison
limits. Neither an uncertainty model nor more samples determines which objective
an owner should choose. The released ranking analyzer already supplies the
central calculation; reproducing it supplies no competitive advantage.

N015 must specify the consequential choice, outcome predicate, time window,
stopping/continuation behavior, target population, independent sampling unit and
physical pairing. Keep the full owner-cost comparison open. An ambiguous objective
means an unresolved decision even when its component scores are precise.

This readback checks arithmetic and consistency in authors' retained simulation
records. It does not rerun their Windows/GPU runtime, validate physics, establish
physical reliability, test unseen conditions or qualify commercial value. The
original runtime-dependent `audit_saved_evidence.py` was read, not executed.
Published results were known before selection. The upstream local plan and
timestamped files are not evidence of external preregistration or peer review.

## Reproduction and retained failures

[Reproduction commands](REPRODUCE.md) bind Python 3.11.16, NumPy 1.26.4 and
SciPy 1.12.0 in a separate hash-locked CPU environment. Existing research
environments remain unchanged. [Source receipts](packet-sources.json) bind all
135 packet files by Git blob and SHA-256; [validation](validation.json) binds the
final scripts, original evidence and required checks.

Nine recorded acquisition/setup/analysis commands total **96.342 seconds**.
They do not include all research, downloads, engineering or review time and are
not a workflow speed comparison. Two invalid attempts remain: the local installer
lacked the exact Python version, and the first reader tried parsing unrelated
robot configuration expressions as literals. The latter reached zero raw cells;
its [script and failure](invalid-readback-001/result.json) are preserved. A verified
standalone interpreter and a Panda-only configuration read resolved them without
changing the frozen protocol, source data or acceptance rule.

The user-requested [GitHub check](reply-readback.json) identified the screenshot
as the earlier Arisole 0.1.2 announcement. Our 0.1.3 verification remains the latest
written comment. XPolicyLab has no reply at that check. No new message was sent;
the nine other pending requests were not repolled.

Credit: the experiment, recorded outcomes and original analysis are the work of
the benchmark-ranking-determinacy authors. Their [license](UPSTREAM_LICENSE.txt)
and [notice](UPSTREAM_NOTICE.txt), plus ManiSkill's
[license](MANISKILL_LICENSE.txt) and [third-party notices](MANISKILL_LICENSE_3RD_PARTY.txt),
are retained. Upstream terms govern their material; Nisayon does not claim the
underlying robot experiments as its own.
