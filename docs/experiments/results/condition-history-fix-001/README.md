# Correct condition-history receipt identity

**9 October 2026 · software correction qualified; incident request posted.**

`consumed_history()` reused its index-path variable while discovering result
bundles. It returned the history index's name with the last discovered bundle's
hash. Even a bundle from another policy namespace could cause that mismatch;
an optional absent index could be incorrectly reported as present.

The three-line correction keeps the discovered path separate. Six regression
cases cover present, absent and indexed history with matching and foreign
namespaces. All six fail on the previous implementation and pass with the fix.
The production bytes match the separate delivery `d92b10f`; that branch remains
intact. This execution lane qualifies the same correction with its own controls.

The [real-history readback](real-history-readback.json) changes only the returned
`sha256`. All **101 evidence references and 599 recovered seeds** are identical.
The original receipt remains unchanged. This fixes future receipt metadata; it
does not retrospectively validate the delay screen's invalid primary assessment
or replace its separately labelled, retrospective null result.

The first full run passed 1,170 tests and failed one monitor test when `os.killpg`
returned `PermissionError`. That test intended to inspect retained temporary
files after child exit, but could also enter live termination. Its final-sample
control now waits for a real child to finish; a separate control checks that a
real live child is stopped after exceeding its temporary limit. The production
monitor and its guards are unchanged. A retained [owned-process probe](owned-signal-probe.json)
also successfully sent SIGTERM. The kernel cause of the earlier error is not
established; neither the original failure nor its uncertainty is discarded.

All **1,172 tests now pass, with zero skips**, plus lint and formatting. The
[validation record](validation.json) retains failed and passing command identities,
log hashes, costs, source hashes and outreach readback. Tests use labelled local
fixtures; no new robot episode or scientific condition was allocated.

With Daniel's explicit approval, the exact prepared request was
[posted to OpenPI #1060](https://github.com/Physical-Intelligence/openpi/issues/1060#issuecomment-6082970232)
as `manfromnowhere143`. Direct API readback matches its approved text byte for
byte. The request asks for existing configurations and short rollout traces,
and the decision the owner is currently trying to make. At the retained
14:41 UTC check, no later comment was present. The earlier pending-send status
is historical; do not send a duplicate.

The next value investigation needs those incident artifacts or another already
executable, consequential case. Start with ordinary CPU reconstruction and an
equally informed conventional workflow. This correction and the data request
establish no diagnostic or economic advantage for Nisayon.
