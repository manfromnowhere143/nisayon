# Serving evidence: assigned-input audit

26 November 2026. Starting revision:
`621bf054c616607d706f7c178ed643c155bc5595`.
This supplements the frozen serving intake; it does not revise that experiment.

Question: does the retained independent reader enforce the deterministic input
assignment, including state, or only consistency between selected camera inputs
and outputs? Source inspection suggests missing input checks. That is a
hypothesis until the counterexamples execute.

Test the old reader against the unchanged packet first. Then independently
replace accepted row 0's state with retained rejected row 51's NaN state. Check
that all other request arrays match and that row 51 records native request
refusal. Run the old full CLI on a separate mutated packet, refreshing its
self-declared payload digest. Also test state shape, dtype and finite-value
changes; a coordinated camera/output change; and boolean/integer ambiguity in
row identity and scalar metadata. Preserve every observed outcome.

Threat boundary: an externally pinned original bundle or payload digest detects
these changes. This tests a producer's internally consistent but misleading
record, not a hash collision, execution authenticity, or corruption of the
original execution. The original source, packet, freeze and native runs remain
unchanged. No native policy or physical task is rerun.

If a gap is reproduced, add a separate reader supplement with explicit input
reconstruction, typed comparisons and existing strict JSON semantics. Keep the
original reader and failed audit behavior. Verify the original packet, its ten
retained fault controls, the new counterexamples, optimized Python and portable
readback outside Git. Check ambiguous JSON and bounded numeric array loading
where the reader accepts external bytes. No new production qualification API.

Interpretation: passing readback supports declared finite software coverage;
it does not certify resized interpolation, learned actions, physical success,
owner acceptance, general hostile-code containment or economic benefit.
The existing 32-pair fresh task obligation remains unexecuted.

Resources: one CPU process at a time, command timeout at most 180 seconds,
additional retained artifacts below 50 MiB, free disk at least 5 GiB. Continue
within the intake's existing absolute stop of 15:25 UTC. Full effort and owner
costs remain unknown. Do not contact an owner or allocate paid resources.
