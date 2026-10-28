# A scoring-code change need not repeat observation execution

28 October 2026. Optional `CheckImplementation` bindings let the check executor
reuse unaffected observations after a separately declared scoring source changes.
The existing conservative mode remains the default. Shared dependencies, the
SDK, and each handler's whole source file remain bound; no automatic dependency
inference or function slicing is introduced.

In one internal comparison on the already exposed camera case, conservative
bindings execute four native processes across two scoring questions. Scoped
bindings execute three, with the same two software decisions. The second scoped
run reuses the original observation, recomputes the score and executes
confirmation again. This establishes the bounded execution difference; it does
not demonstrate an advantage over a competent owner's workflow.

| Scoring implementation | Conservative native processes | Scoped native processes | Decision in both modes |
| --- | ---: | ---: | --- |
| Preserve configured camera budget | 2 | 2 | Adopt: 704/704 rows match |
| Retain all configured camera slots | 2 | 1 | Reject: 632/704 rows match |

These are different acceptance questions on LeRobot PR #5129 at
`52d44203ed5bd5442dfd85d88ab78f7e91e54d77`. Its missing-camera behavior and both
contract alternatives were previously exposed in the
[camera qualification](../camera-slot-qualification-2026-10-28/README.md).
The candidate code and inputs do not change; only the copied scoring module
changes. A rejected alternative contract is not a new policy regression.

Seven native processes perform 2,464 finite preprocessing condition calls across
six unchanged native methods. They construct no policy checkpoint and run no
robot. Confirmation uses a new process at previously exposed seed 67. It remains
an exposed software execution, not independent behavioral confirmation or an
untouched incident. All deployment decisions remain unresolved.

## Implementation and controls

Every check directly depends on its own bound code input and transitively on the
shared procedure. Other declared implementation dependencies may be shared or
linked explicitly through the graph. Files shared by two handlers invalidate
both; an SDK/shared-source change remains conservative. A scoring-code edit can
reuse observation bytes but cannot inherit an old score or decision. A check
marked `refresh="always"` still executes.

Twenty new regression controls pass with 46 existing executor/bundle controls.
They cover changed observation/shared/runtime/data inputs, stale observations,
unknown populations, incomplete bindings, handler-symbol changes, shared handler
files and code inputs, mutation during execution, frozen-manifest corruption and
portable review after handlers are removed. The initial test harness omitted
required population/scoring declarations and used a create-only writer for an
intended fixture mutation; those failures were retained and the harness corrected.
No dependency guard or acceptance criterion was weakened.

The [repository validation](validation.json) passes 1,843 tests with 88 skips.
Its initial documentation check found two private links in the public guide;
restoring that guide's public links resolves both. The corrected documentation,
lint and formatting checks pass, with no implementation change after the suite.

The [source freeze](source-freeze.json) binds the unchanged executed SDK and
example files to [public source `9415968b`](https://github.com/manfromnowhere143/nisayon/tree/9415968b95ff852099c4ad2b81fb62518d88e81a).
The read-only domain reviewer was added after execution. It recomputes diagnostic
and confirmation scores from original native observations/reference records,
then compares the saved claims. This is consistency checking against the declared
software oracle, not independent ground truth or execution attestation.

A [separately installed source wheel](installed-review.json) outside Git also
reconstructs all four decisions. A Python audit hook refuses access to both
original checkouts and subprocess execution during that review. This exercises
portability without the native environment; it is a software control, not an OS
sandbox or independent adjudication. The earlier five camera bundles still pass
their existing read-only verifier with this SDK addition.

## Costs and limits

The [measurements](measurements.json) retain whole comparison-arm observations
of 51.16 seconds conservative and 31.74 seconds scoped. These include immediate
adapter preparation, environment checks, native execution, scoring, export and
review. Nested check/native timers must not be added again. One fixed
conservative-then-scoped order cannot estimate a timing advantage; no speedup
percentage or owner-cost ratio is inferred.

The pinned native environment and source acquisition were reused from the prior
camera study. Research, implementation, complete preparation, active human work,
provider charges, adoption and maintenance are not fully measured. A competent
native workflow can use the same dependency knowledge. Complete economic value,
independent-owner acceptance, physical effects and untouched reuse remain unknown.
No release tag, published wheel, paid resource or upstream message changed.

## Recompute the retained result

The [archive](evidence.tar.gz) contains four original portable bundles and the
original comparison/readback records. The [manifest](evidence-manifest.json)
records exact member bytes and SHA-256 identities. Use the matching SDK source
above when revisiting these implementation-bound check records.

```sh
uv sync --frozen
mkdir artifacts/scoped-code-review
tar -xzf docs/experiments/results/scoped-check-code-2026-10-28/evidence.tar.gz \
  -C artifacts/scoped-code-review
uv run --frozen python examples/qualification/scoped_checks/review.py \
  artifacts/scoped-code-review
```

No native sources, native environment, weights or owner code execute during this
review. The [runnable example](../../../../examples/qualification/scoped_checks/README.md)
gives a new execution recipe for the separately qualified macOS CPU environment.
The tagged v0.2.0 wheel is unchanged; this is a current-source SDK addition.
