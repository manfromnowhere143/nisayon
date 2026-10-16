# Publish usable cost reports

**14 October 2026 · N036.** Public Nisayon still contained the measured-prefix
defect already corrected in N034. We exported that correction through public
history, then fixed a remaining integration gap: the default text report omitted
cost validity and invalid reasons. The task verdict and cost validity now remain
separate in both structured and text output.

The [public source](https://github.com/manfromnowhere143/nisayon/commit/736db9ddea280fd8c8ec439f539e68d12eaef654)
contains three reviewed descendants of `cd07dd5`. All 15 changed remote files,
commit messages, human author/committer identities and the unchanged `v0.1.0`
tag were read back. Private development ancestry was not published. The
[publication receipt](publication.json) binds those observations.

## Evidence and checks

- The identical 15 exposed controls pass **7/15 on the public parent and 15/15
  after correction**, in both input orders. The original D05 input, costs,
  measurements and task decision are preserved. Its constructed interrupted
  copy restores 0.709904042 seconds of known work. This repeats the supported
  correction on public source; it is not a new robot result or discovery.
- The same 22 accounting/report regressions give **19 passes and three missing
  text-status failures** with the earlier renderer, then **22 passes** after
  correction. Legacy records without status fields still render without an
  invented status. The [installed CLI](cli-readback.json) shows accepted fixture
  tasks with partial or invalid costs; exit 0 is not approval of a cost comparison.
- The final public clone passes **1,199 tests with 80 explicit skips**, lint,
  482 formatting checks and 145 document checks. All 22 cost regressions run.
  Its Git object store contains exactly public ancestry, but it shares the host.
  The [hosted checks](ci.json) independently run the public checkout on Linux
  and macOS: **1,179 passed, 100 explicit skips per runner**, lint, 482 formatting
  checks and 145 documents. The [exact workflow](https://github.com/manfromnowhere143/nisayon/actions/runs/38555553007)
  succeeds on both platforms. These are software checks, not independent
  scientific confirmation.
- The first clean-clone check passed 1,198 with 80 skips before the text change.
  It is preserved. Two new assertion failures expected integer-formatted text
  where numeric totals render as floats. One baseline invocation resolved the
  venv symlink to a base interpreter without pytest. Corrected attempts preserve
  the accounting inputs and expectations; invalid setup attempts supply no
  comparative evidence.

The [protocol and amendment](protocol.json), [command records](commands.json),
[public validation](public-validation.json) and [comparison](public-comparison.json)
retain scope, exact sources and results. Full test logs and XML are compressed
alongside them. The accounting implementation is byte-identical to N034; the
text implementation and extended regressions are source `1703079`.

## Decision and remaining dependency

The [17-thread readback](threads.json.gz) found no new or edited message, PR-body
change, head revision or merge. Two GitHub test-merge hashes changed; those are
not replies. The [bounded intake](intake.json) also found no new Kinetix/SureSim
bundle. An inspected pose-composition proposal already has an owner, opt-in
compatibility design and an author-run performance comparison. No duplicate
fix or outreach was added.

Shipping the supported correction and making its result visible was better
supported than another runtime, selector or proxy grid. No new dependency,
policy trial, simulator allocation, hardware operation or cloud spending was
introduced. A partial subtotal is still not complete economic cost, and no
competitive advantage or customer commitment is established.

[N015 and the frontier decision](../../../FRONTIER_DECISION_2026-10-14.md) remain:
one source-bound, consequential owner choice between a deployment correction,
more training/data or a different policy. Use a capable conventional workflow
with the same information, freeze fresh confirmation and count complete costs.
Equal or greater total work for the same accepted answer rejects the value
claim on that case. A positive case must earn separate untouched repeat use
before expansion. Initial intake remains one incident/four engineering hours.
