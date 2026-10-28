# Verification must cover the declared camera study

28 October 2026. Review of the reader published with the
[camera-contract study](../camera-slot-qualification-2026-10-28/README.md).
The original evidence still reproduces all five decisions. This correction
addresses ways the reader could accept incomplete or contradictory copies of
that evidence; it does not invalidate the original native results.

## Demonstrated failures

The original reader used Python assertions for its verification checks. Python
removes those checks under `-O`, `-OO` or the corresponding optimization
environment setting. [Python's assertion semantics](https://docs.python.org/3.12/reference/simple_stmts.html#the-assert-statement).

In a copied packet, changing the outer summary's first decision to `adopt`
left the original SDK bundle reporting `reject`. Optimized execution nevertheless
printed `adopt` and exited successfully. A separate completeness problem did
not require optimization: the reader checked the records it encountered without
enforcing the full frozen assignment.

| Constructed alteration | Original reader | Corrected reader |
|---|---|---|
| Change summary decision while retaining the rejecting SDK bundle | Refused normally; printed `adopt` under `-O` | Refuses in both modes |
| Remove every portable readback entry | Exited successfully with zero reviews | Refuses missing coverage |
| Replace one portable entry with a duplicate of another | Reported five reviews while checking only four distinct cases | Refuses duplicate case identity |
| Remove every row from one native panel and update its saved counts | Still reported eight verified native reports | Refuses the missing assigned rows |

Copies were repacked with matching outer hashes so that these controls reached
the semantic checks. The original archive and its manifest were never edited.
The [verification record](verification.json) retains the before/after outcomes.

## What the reader now checks

Validation uses explicit exceptions that remain active under optimization.
The reader requires the 38 declared archive members, all eight source/seed
panels, all 352 condition IDs per panel, both contracts, all six policy groups
and exactly five distinct portable cases. It recomputes each count from rows
joined by their declared identities. Reordering those finite rows preserves
the decision; duplicates and omissions fail.

Each SDK bundle is reassessed and joined to the corresponding case ID, exact
contract, seed inputs and reference rows. An equally labelled decision from a
different case cannot stand in for the required evidence. JSON decoding rejects
duplicate keys and nonfinite values; comparisons preserve the distinction
between booleans, integers and floating-point values. Archive and decompression
limits remain active before member data is consumed.

The read-only verifier supports ordinary Python, `-O`, `-OO` and
`PYTHONOPTIMIZE`. The native acquisition, preparation and execution helpers now
refuse optimized Python before source access or native imports because the
retained native harness uses assertions. A new execution needs its own fresh
preparation/freeze; the historical freeze remains unchanged.

## Validation and reproduction

All 46 focused tests pass. They exercise the actual retained SDK bundles,
the malformed-record controls, archive boundaries, case substitution and
optimization settings. The unchanged packet's printed output matches the old
reader byte for byte in normal and optimized Python, including all five decisions.

In the already qualified Torch 2.7.1 / NumPy 2.2.6 environment, eight reference
helper calls reproduce all 2,176 assigned rows exactly across the two seeds,
two contract modes and two policy scopes. This checks preservation of the
reference helper after adding its optimization guard. It does not rerun the
upstream policy methods, produce fresh robot outcomes or establish independence.

```sh
uv run --frozen python -m pytest tests/qualification/test_camera_evidence.py
uv run --frozen python -O examples/qualification/camera_slots/verify_evidence.py \
  docs/experiments/results/camera-slot-qualification-2026-10-28
```

The original 3,843,934-byte evidence archive keeps SHA256
`a6a0b2f6a0a1c04156f45b2e45a359d4df05d373a605b762210be7d4e0c24670`.
The verifier establishes internal consistency and complete coverage of this
declared software study. Hashes and agreement do not prove authenticity,
physical task truth, policy improvement or complete-cost advantage. All
deployment decisions remain unresolved.
