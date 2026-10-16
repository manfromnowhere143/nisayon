# Missing labels cannot qualify a comparison

**12 October 2026 · N024 complete, bounded software correction.**

Continue the deployment-change qualification mission. Its main bottleneck is
still an owner's consequential decision with measurable avoidable work. The
engine can execute bounded corrections and retain evidence; a cheaper supported
decision than a capable conventional workflow remains unproved. The
[decision packet](DECISION.md) was frozen before this experiment.

## What changed

The newly published [Arisole Eval 0.1.2](https://pypi.org/project/arisole-eval/0.1.2/)
already compares native LeRobot evaluation outputs. Testing this available
alternative exposed a gate defect: 30 shared seeds with only one fully labeled
pair produce `REVIEW`, exit **0**, under defaults requiring 20 comparable
episodes. This is not an overall `PASS`. Missing trajectory data cause `REVIEW`,
and the default configuration does not fail CI on that outcome.

The [one-module patch](labelled-pair-gate.patch) counts observed transitions for
gate eligibility and the known regression fraction. It retains unknown pairs
and adds an insufficient-data reason. It does not alter comparison rows,
comparison metrics, thresholds or LeRobot. No reporting backend was added to
Nisayon. The upstream implementation and license remain Arisole's; retained
[notices](upstream/NOTICE) and [license](upstream/LICENSE) accompany the patch.

| Frozen software controls | Published wheel | Correction |
|---|---:|---:|
| Complete-data controls, including insufficient count and known regression | 4/4 | 4/4 |
| Missing-label controls | 0/8 | 8/8 |
| Total | **4/12** | **12/12** |

Seven incomplete controls incorrectly return `REVIEW`/0. The eighth returns
insufficient data but reports a zero regression rate with no observed pairs.
In another control, six observed regressions, 24 observed non-regressions and
30 unknown pairs yield 6/60 before correction and **6/30** afterward. The latter
describes observed pairs only; unknown outcomes still prevent affirmative
acceptance. All comparison summaries, rows, metrics, compatibility and status
remain identical between variants.

Both variants pass **20 original sdist tests**. Three others fail because the
release omits two required YAML configuration files. Those six executions remain
unqualified; no substitute configuration was invented. The release's bundled
sample is exercised by the passing original tests. The exact review reproduction
also returns `REVIEW`/0 before and `INSUFFICIENT_DATA`/2 after correction.

The patch and reproduction were delivered in one
[technical review](https://github.com/huggingface/lerobot/pull/4927#pullrequestreview-5492083067).
[Readback](review.json) verifies the author, source revision and exact body.
Delivery is established; maintainer acceptance and use remain unknown.

**Follow-through, 12 October:** the maintainer subsequently reported reproducing
this finding and adopting the correction in 0.1.3. [N025](../reporter-followthrough-001/README.md)
verified the published wheel against these same controls and returned the result.
The original N024 receipts and limits above remain unchanged.

## System verdict and research

The [inspection](inspection.json) reconciles all 93 source files against the
retained whole-system inventory: 92 unchanged, one previously recorded change
to interval-premise wording. Nine component paths were read again. Seven retained
terminal evidence files still match their recorded hashes. This is a component
assessment and drift check, not an exhaustive line audit or independent replay.

- **Demonstrated:** bounded CPU execution, fresh state after changed actions,
  retained regressions and native software checks. B2's known correction remains
  9/10 versus 0/10; A1 remains rejected at 1/10 against 8/10 required. Both
  completed development comparisons tied their conventional arm.
- **Modeled:** constructed transport schedules, virtual clocks and scripted
  adapters exercise software contracts. They do not establish physical behavior.
- **Proposed:** a general intervention compiler, adaptive selector and broad
  autonomous diagnosis. The broader physical-AI product remains an ambition.

Fresh primary research considered active factor evaluation and SCAPE; methods,
limitations and release availability are in the [packet](DECISION.md), with
[source receipts](sources.json). Neither supplies missing target observations
or establishes complete-cost superiority. The released reporter made an
executable alternative available and removed the rationale for adding a generic
reporter here. This conclusion is specific to the current decision.

## Evidence and reproduction

[Protocol](protocol.json), [baseline](baseline-result.json),
[candidate](candidate-result.json), [patch identities](patch-identity.json),
[installation isolation](candidate-installation.json) and
[evidence manifest](evidence.json) retain the before/after result. The manifest
binds 270 local raw files and command records. Dependency versions and hashes are
in [requirements.lock](requirements.lock). Nisayon's existing environments were
not synchronized or modified.

[Repository checks](validation.json) pass: lint, 511 formatting checks and
163 documentation checks. The retained patch reproduces the tested candidate
bytes. Nisayon production source is unchanged; its full engine suite was not rerun.

Resource deviation: the packet named one local CPU environment. Two isolated
copies of the same Python and dependency lock preserved the unchanged baseline.
No package version, test allocation or acceptance rule changed.

From the repository root, choose a fresh output directory:

```sh
uv venv --python 3.12 artifacts/reporter-reproduction/venv
uv pip sync docs/experiments/results/reporter-gate-001/requirements.lock \
  --python artifacts/reporter-reproduction/venv/bin/python --require-hashes --link-mode copy
artifacts/reporter-reproduction/venv/bin/python -B scripts/experiments/probe_reporter_gate.py \
  --python artifacts/reporter-reproduction/venv/bin/python \
  --protocol docs/experiments/results/reporter-gate-001/protocol.json \
  --out artifacts/reporter-reproduction/baseline
```

The baseline probe intentionally exits 1 with eight failed contracts. To test the
correction, apply `labelled-pair-gate.patch` with `patch -p1` in that new
environment's `site-packages` directory, then run the same probe with a fresh
`--out artifacts/reporter-reproduction/candidate`. It should pass 12/12. Do not
patch a retained historical environment. The copy install above avoids modifying
shared package-cache files.

Only software metadata and local CPU commands were executed. Recorded command
wall times are execution costs, not engineering savings; preparation, review,
adoption and maintenance costs are unmeasured. These exposed controls are not
independent confirmation, robot trials or evidence of diagnostic superiority.

## Next dependency

N015 still needs an existing source-bound packet and an owner's live decision.
Use conventional checks first, freeze quality and cost rules, then test whether
an added check changes the correct decision or avoids repeated work. Count setup,
review, adoption and maintenance. Repeat a positive result on a separate
untouched decision before expansion. The nine pending requests were unchanged
at the [14:03 UTC intake](intake.json); none was reposted. Resume this reporter
work on maintainer evidence or changed source, without repeating these controls
as fresh scientific confirmation.
