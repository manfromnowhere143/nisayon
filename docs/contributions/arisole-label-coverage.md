# Keeping missing outcomes out of an evaluation gate

**External contribution · 12 October 2026**

A constructed comparison in `arisole-eval==0.1.2` had 30 seed-matched episode
pairs, but only one pair had success labels for both runs. The reporter retained
the other 29 as `INCOMPARABLE`. Its gate nevertheless counted all 30 toward the
evidence threshold and returned `REVIEW`, exit **0**.

The finding came from Nisayon's evaluation work. Arisole's maintainer reproduced
the case, adopted the proposed correction, added explicit coverage fields and
regression tests, and published **0.1.3**. We then verified the released wheel.

## The defect and correction

Matching records establishes a correspondence. It does not establish that both
outcomes were observed. In this case, the default minimum of 20 comparable pairs
was satisfied using the match count despite there being only one observed pair.
`REVIEW` was not an overall `PASS`. A CI check relying on the default exit code
would not flag this missing evidence as a failure.

The correction keeps every matched row while counting fully labelled transitions
for evidence thresholds and the observed regression fraction. Missing labels
remain explicit. Version 0.1.3 distinguishes matched, comparable and incomparable
counts. Under defaults, the original case returns `INSUFFICIENT_DATA`, exit **2**.

An additional control has six observed regressions among 30 labelled pairs, plus
30 unknown pairs. Its observed regression fraction is **6/30**, not **6/60**.
Incomplete coverage still prevents an affirmative acceptance in that control.
Clear observed regressions can still produce `BLOCK`; the correction does not
discard available failure evidence merely because other labels are missing.

## Published evidence

| Record | What a reader can inspect |
|---|---|
| [Original report, executable reproducer and proposed patch](https://github.com/huggingface/lerobot/pull/4927#pullrequestreview-5492083067) | Constructed inputs, the 0.1.2 result, the bounded correction and its controls |
| [Maintainer reproduction and adoption](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6127308467) | Confirmation of the defect, released behavior, coverage fields and added tests |
| [Published 0.1.3 package](https://pypi.org/project/arisole-eval/0.1.3/) | The wheel and source distribution |
| [Verification of the published wheel](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6127847035) | Retained controls, coverage checks and the remaining source-distribution limitation |

The linked reproducer runs on constructed metadata in an environment containing
the selected package version. It does not execute a robot or policy. Use separate
environments to compare 0.1.2 and 0.1.3; retain the package and dependency versions.

## Verification and limits

The published 0.1.3 wheel passes all **12 retained CLI controls**, compared with
four passes for unmodified 0.1.2. Its new coverage counts agree with the input
labels in every case. Complete-data controls keep their expected outcomes.
These are reused software controls, not fresh robot trials or an independent
performance study.

Running the original 0.1.3 source-distribution tests against the installed wheel
gave **29 passed and 3 failed**. All nine new label-coverage tests passed. The
three failures require configuration files omitted from the source archive;
they remain unqualified. The maintainer's reported 32 passes concern their own
environment. The published verification keeps that difference explicit.

Verified wheel SHA-256:
`188a794498eeeabbad78f876cdf16b8bed0d4eef5e97a27d59f17af41bb31317`.

This establishes adoption of one bounded software correction. It does not
establish robot reliability, improved task performance, lower engineering cost
or adoption of Nisayon as a product. The finding concerns Arisole's external
reporter; the discussion's location in LeRobot does not imply a Hugging Face
partnership or endorsement.

Arisole authored the reporter and shipped the release. Daniel Wahnich's Nisayon
work supplied the constructed case, proposed correction and release verification.
The maintainer's careful reproduction and follow-through made the contribution
useful beyond the original investigation.
