# Questions that could change the next engineering decision

**10 October 2026 · two questions posted, exact readback verified.** Daniel
instructed us to proceed after the research review. Both messages were posted
under `manfromnowhere143`; the [receipt](outreach.json) retains their exact text,
body hashes, public URLs and the tested reproducer's output. This is outreach,
not evidence of a relationship or permission to access private data. Ask for
existing, sanitized artifacts before asking anyone to collect new data.

The existing [OpenPI #1060 request](https://github.com/Physical-Intelligence/openpi/issues/1060#issuecomment-6082970232)
remains latest among four comments at the 06:05 UTC check. No response or new
artifact was present. Do not duplicate any of these requests.

## GR00T #785: separate deployment behavior from recovery learning

[Posted at 06:08:48 UTC](https://github.com/NVIDIA/Isaac-GR00T/issues/785#issuecomment-6094509123)
on Lukas-Kozel's existing report, after reading its one earlier reply. The request
builds on that reply's timing checks rather than claiming a new diagnosis. It
asks whether jitter and failed recovery are the same incident; requests existing
revisions, control settings, executed horizon and numeric traces with acquisition
and dispatch clock information; and asks which engineering decision is live.
No new robot run, weights, images or training are requested.

Follow-up only if the owner engages: which change is currently under consideration,
how often does this incident recur, and how much engineer/robot time did the last
investigation consume? These determine whether a collaboration is useful.

## RoboRecover: clarify a specific summary field

[Posted as issue #2 at 06:08:34 UTC](https://github.com/RUCKBReasoning/RoboRecover/issues/2):
**Clarify success fields when prefix replay completes the task.** The live
default branch still matched inspected commit
`089b9420e8b7c303e2338a8212a8b6c27c26a79b`; existing issue #1 concerned broader
provenance metadata and did not cover this field behavior.

The question asks whether summary success means environment completion or recovery
evaluation, and where the canonical equal-scenario analysis lives. It retains the
`failed_files` and nonzero exit evidence, distinguishes trial pooling from equal
scenario weighting, and makes no inference about the paper's actual outcomes.

The message contains a self-contained, standard-library reproducer and observed
output. The exact posted code was tested on Python 3.12.13: four terminal-state
controls and one unequal-repeat control pass. It fetches hash-checked upstream
source, extracts two unmodified definitions, and uses constructed records without
simulator, model or dataset execution. Lint and formatting pass. The
[original probe and recorded outcomes](../recovery-summary-audit-001/README.md)
are preserved; the new reproducibility check is retained in the outreach receipt.

Next, assess the maintainers' intended semantics and any canonical analysis they
identify. A reporting clarification alone does not justify extending Nisayon's
production engine.

## A prospective decision owner

Ask about the last failed deployment, not opinions about Nisayon:

1. What changed between the working and failed versions, and which deployment
   decision is still unresolved?
2. Which ordinary checks and remedies have already been tried? Which result would
   change the next action?
3. What existing records can be shared, and what would it cost to obtain the
   missing observation or run one meaningful confirmation?
4. Would a supported correction, a justified refusal, or a targeted request for
   missing evidence have saved real work on that incident? How would we measure it?

These answers determine the next interface to implement. They do not require a
new general architecture, a training run, or a promise of autonomy.
