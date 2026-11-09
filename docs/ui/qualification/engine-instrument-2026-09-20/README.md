# Engine evidence instrument

20 September 2026. Completes the implementation slice identified by the
[engine exposure review](../engine-exposure-2026-09-20/README.md).

The **Study** control opens all 26 retained trial assignments, 660 assigned
condition pairs and 1,474 confirmation execution records. Six assignments have
no scheduled confirmation. Search and arm selection lead to decisions, pairs,
all executions including prefixes, diagnostic proposals, declaration chronology,
cost scopes and evidence continuity. External evidence, retrospective declaration
adjudication, the DC01 comparison and the retained recovery demonstration have
separate views. Each admits its immutable object before rendering and links its
exact source. These counts have different scopes from the six reconstructed
B-arm cases and their 286 retained runs. No new scientific result is implied.

The scene export now includes actual plan configurations and execution metadata,
model joints and actuator declarations, and per-frame qpos, qvel, ctrl and
controller goals. **Spatial → Joints & controller** reads the selected phase;
joint ranges, velocities, control limits and goal-to-grip distance preserve
native units. The native model declares seven torque controls (five ±80 N m,
two ±12 N m), a left finger position control in [0, 0.04] m and a mirrored right
finger control in [-0.04, 0] m. Force limits are not measured forces. Fork labels
the direction of the actual deployment-plan difference.

[Raw-source agreement](physical-source-agreement.json) compares 180 fields
directly with the six regression raw stores: first, step 30 and last rows,
before and after, for qpos/qvel/ctrl/goal_pos/goal_ori. All agree exactly.
[The export receipt](recorded-export.json) covers the six current scene cases.
No simulator step, policy invocation or experiment was performed. The richer
model metadata changed model hashes. The optional native visual package now
qualifies 98 additive model aliases by exact equality of every pre-existing
geometry field; old bindings remain valid. Meshes and physical geometry are
unchanged. Historical URLs remain addressable.

## Automatic publication

`tools/ui/publish_engine.py` consumes the canonical engine's committed
`confirmation-engine-001/retained-output-manifest.json`. It follows the sealed
export manifest only inside the configured producer artifact root and invokes
the engine's own `load_export` in its qualified interpreter. Source, metadata,
dependency and retained raw-artifact verification must return current.

The publisher projects allowlisted study objects, refreshes the inventory from
canonical engine source, and reuses a byte-qualified application package. It
does not build an application from a changing working tree. A deployment is
staged without assigning the public domain. Every newly admitted object is read
back over HTTPS; only then is it promoted. Changes in the producer before
promotion, failed admission or failed readback prevent promotion. A pending
promotion is distinguished from an established unchanged public deployment.

The scheduled one-shot job checks every 60 seconds. An unchanged sealed-source
fingerprint exits without revalidating large archives or creating a deployment.
The UI discovers publications every 15 seconds while visible, preserving the
admitted study until the operator chooses its update. `/api/publication.json`
records the source fingerprint, runtime revision and verification time. It
does not claim a live heartbeat or connected execution worker. Publication
requires the operator Mac, retained source stores, credentials and network.
New engine output must be sealed in that retained-output contract; arbitrary
in-progress files are not publishable evidence. New study evidence is automatic;
qualifying new robot geometries or changing the renderer is a separate release.

Local configuration and scheduler state live outside Git. Sanitized installation
and readback receipts accompany this report. Publisher code and the base package
are pinned; changing their bytes requires requalification.
Private main, raw archives, credentials and Git history are not deployed.

## Checks and limits

- TypeScript, 172 frontend tests and production build pass. These include
  historical locator continuity, new study membership/identity/corruption,
  physical dimensions/ranges, and modal selection in the study.
- The 73 existing UI export tests and five publisher transaction tests pass.
  Failure controls cover stale runtime, changed raw evidence, failed staged
  readback and a producer moving before promotion; unchanged input is idempotent.
- [Package verification](package-check.json) passes 201 checks before deployment.
  Lint, formatting and diff whitespace checks pass.
- Earlier check failures exposed the changed model binding, current-generation
  test expectations and the mirrored right-finger range; they were corrected.

The supplied installed-iPhone video shows a white native surface before the HTML
opening. Added native light/dark launch backgrounds cover the supplied 440 × 956
CSS-pixel device and other declared phone/tablet sizes in both orientations.
They contain no second wordmark or animation. The single HTML opening still
owns the mark and disappears after the qualified scene is ready. Actual iPhone
launch/resume, VoiceOver, visual rendering and GPU/frame timing are **not
accepted by these checks**: the approved browser runtime reports no available
browser. The real-device launch result remains to be measured.

Native launch configuration follows [Apple's web application guidance](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html).
Staging and promotion follow [Vercel's deployment workflow](https://vercel.com/docs/cli/deploying-from-cli).
Neither document establishes device performance or scientific acceptance.

The first staged readback encountered Vercel Authentication's login document
and correctly refused promotion. The application's bytes were unchanged.
Protected staging is now read through [Vercel's authenticated curl command](https://vercel.com/docs/cli/curl),
with exact byte comparison; the production domain is checked anonymously.
Deployment protection remains enabled and credentials remain outside the package.

## Release and scheduled operation

Runtime `bad2d2daa4bc58aea33bcec175b905617cb30647` is live at
<https://nisayon.danielwahnich.dev/> through deployment
`https://nisayon-8coe2ed6l-daniels-projects-ca65133a.vercel.app`.
The admitted study generation is
`93cbcf6a02cee67ac62b52505f8dc2c2c78b49a1a9508cd6d70ec15d718f35ea`.
It binds canonical engine `f27e858` and retained metadata `14e7805`.

[Production verification](production-check.json) passes 299 checks.
[Exact-byte readback](production-byte-match.json) compares 46 public files
(49,091,335 bytes), including every runtime chunk, native geometry and all six
diagnostic regression model/sample/frame objects. This is HTTP verification,
not a browser rendering or latency measurement.

The [installation receipt](scheduler-install.json) and
[scheduler readback](scheduler-readback.json) retain the 60-second user job,
successful exit, overlapping-job exclusion and repeated unchanged checks.
Publisher `91763707cea3ea639a16af9eed9d37247a15251a` also keeps its current check
status distinct from the previous publication status; the
[five transaction tests](publisher-check.txt) cover that distinction. This
local publisher correction does not change the qualified public application.

Historical ties, D05 progress rejection and DC01's absence of repair advantage
remain unchanged. Canonical main and the other worktrees remain untouched.
