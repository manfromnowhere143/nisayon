# Independent verdict on the A1 feasibility pilot

**21 September 2026 · evaluation lane · 10:08 UTC.** Machine record:
[`pilot-verdict-001.json`](pilot-verdict-001.json); gate reproduction:
[`gate-reproduction-001.json`](gate-reproduction-001.json); criteria frozen beforehand:
[`PILOT_ACCEPTANCE.md`](PILOT_ACCEPTANCE.md).

## What happened

The execution lane recorded the operator's authorization and numeric limits at 09:47 UTC,
before its first retained request, then ran its rights gate. The official robomimic dataset
repository declares MIT and holds one Lift PH low-dim object of 21,084,088 bytes, renamed
from its historical v141 name with no content change. The pinned Stanford v1.4.1 object
answers a HEAD with 21,693,920 bytes. Two objects of different length cannot share a
SHA-256, so the retained MIT terms cannot be bound to the pinned bytes, and the protocol
stopped before any dataset request. No dataset body, no training, no checkpoint and no
rollout exist. The execution lane sealed the result as unresolved.

## Reproduction

This lane copied the three retained responses, verified their digests against the
execution records, and parsed them itself: the MIT declaration in the dataset card and
tags, the single Lift PH object with its size and digest, the rename-commit title, and the
Stanford headers whose ETag encodes both the length and the May 2023 modification time.
The decision reproduces exactly. One presentation limit remains: the zero-line-change
count of the rename was not independently parsed from the page.

## Verdict against the frozen checklist

Custody is unresolved: applicable terms for the exact pinned object are not retained.
Binding the official MIT terms to that object by byte identity is infeasible, which is a
fact about the rule and the objects, not about the dataset's actual terms. Executability
and resource feasibility are unresolved because nothing executed; the machine headroom
and caps were satisfied for an acquisition that did not occur. Costs are accepted: three
responses, 90,237 body bytes, 2.8 seconds of retained request wall, zero dataset and
training bytes, two failures retained, unknown costs named including six pre-freeze web
tool calls without byte or CPU accounting. The continuation estimate is correctly
unresolved; no optimizer update ran and the frozen method forbids extrapolating from
another policy. Competence, any decision and comparative value were never in reach. The
original objective, an independently discovered deployment failure, stays outstanding.

## Next investment

Feasible now: the gate, the accounting, the runtime stack and the headroom. Infeasible:
binding the MIT terms to the pinned object by byte identity. Unresolved: terms for the
pinned object, dataset compatibility with robosuite 1.4.1, training cost.

Recommended order. First, one retained request by the execution lane for an authoritative
statement of terms covering the Stanford-hosted v1.4.1 objects; if it exists, acquire the
pinned object under the existing limits. If it does not, and only under a new explicit
authorization, acquire the MIT-declared object itself (21.1 MB, within the 32 MiB cap and
the 64 MiB cumulative cap), verify its digest after the download, and inspect its
environment arguments against the locked robosuite 1.4.1 before any training; an
incompatible object ends the pilot as infeasible on this stack, which is a result. Stopping
the A1 line is the third option. None of these moves the claim boundary: feasibility and
cost only. The sixty-rollout contract and the predeclared task-evaluation prerequisites
stay unassigned.

## Seal-aware disposition (10:15 UTC)

The execution lane sealed its formal packet at 10:11 UTC from `5e7d534`, after this
verdict had bound the delivery as committed at `b1fdb0c`. Its finding
`assessment_precedes_formal_seal` is reproduced and agreed. The sealed packet verifies
(seal `382e3228…`, summary, invocation and a 57-entry manifest all matching, no network
during the seal); its rights inputs are byte-identical to the copies this lane parsed,
and its embedded acceptance record equals this lane's committed file. It adds two
preserved process failures, four in all, and two small check costs; one of the added
failures, an ad hoc shell loop, has no command record, so its cost is unknown and stays
disclosed rather than counted. No scientific input, the gate decision, the conclusions or
the recommendation changes: [`pilot-verdict-002.json`](pilot-verdict-002.json)
supersedes the packet binding of verdict 001 and nothing else.
