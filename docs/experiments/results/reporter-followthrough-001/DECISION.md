# Verify the shipped correction

**12 October 2026 · N025, before execution.**

Arisole's maintainer reports reproducing N024, adopting the label-coverage
correction and publishing `arisole-eval==0.1.3`. They explicitly request our
verification. This changes the next step from searching for another incident
to checking the distributed release. Their public statement is evidence of
reported adoption; installed behavior remains to be verified.

Install the PyPI wheel in a new, hashed environment with the same dependency
versions as N024. Reuse its exact 12 exposed controls, changing only the declared
package version and distribution hashes. Inspect the source delta and run the
original 0.1.3 sdist tests. Preserve missing-fixture failures separately. Do not
modify either retained 0.1.2 installation or Nisayon's existing environment.

The maintainer also supplies a newly public LeBoard reproducibility bundle.
Check one native comparison: `clean-c0-h264-s0` against `clean-c0-h264-s1`, the
first two clean training seeds. Fetch only their existing evaluation outputs
and run metadata from the pinned dataset revision; verify the published hashes.
Independently count the raw Boolean outcomes and compare both package versions'
CLI reports. Lack of per-episode identity must remain explicit: no fabricated
paired transitions or affirmative paired gate. These are third-party simulation
records, not new experiments or a replication of their policy results.

Accept release verification only if all 12 retained controls pass, the new
matched/comparable/unknown counts agree with their input labels, and original
tests show no newly explained-by-code regression. Report incomplete upstream
test qualification rather than supplying invented configurations. The native
readback must preserve every input byte and match its independently counted
successes and sample counts. A mismatch falsifies the respective claim and
must be reported before endorsing the release.

Use local CPU commands and one public packet within the existing four-hour
inspection cap. No policy, training, GPU, physics or hardware execution. Record
command costs, package identities, source receipts and all outcomes. Reusing
exposed controls verifies a new release; it is not independent confirmation.

If supported, send one concise verification reply under the standing technical
follow-through authority, with exact readback. Record upstream software adoption
separately from adoption of Nisayon as a product. N015's complete-cost owner
comparison remains open; no generic reporter, selector or backend is warranted.

[Maintainer response](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6127308467)
· [Verification request](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6127361745)
· [Original result](../reporter-gate-001/README.md)
