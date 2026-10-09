# Relative-time fixture proposal

**Proposed; not applied to the evaluation owner's files.**

The [patch](proposed.patch) replaces the failing test's absolute future and past
decision stamps with one day after/before its actual first decision. All existing
assertions and the evaluator implementation remain unchanged. The
[proposal record](proposal.json) binds the original and proposed file bytes and
the isolated real-record fixture copies.

The original test file at evaluation commit
`6f294891bb9b5bf7a4167aad68c50ba637a1dcec` matches the proposal base exactly.
`git apply --check` passes. The changed test passes in a temporary directory
outside Git: command `d4fdd0eaad6c4c3c847b552e48910a34`, 2.883675 s,
one passed and twelve deselected. Both the future-history exclusion and earlier
consumption assertions ran. The live evaluation source, tests and lane were
verified unchanged from the startup revision.

The full live tree still has the failure until the owner integrates a named
ready correction. This isolated proposal check is not a passing full-suite claim
and does not authorize changing the prospective endpoint contract.
