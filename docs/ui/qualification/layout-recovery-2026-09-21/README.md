# Fitted evidence layout: startup recovery and release

Published at [nisayon.danielwahnich.dev](https://nisayon.danielwahnich.dev/) on
21 September 2026, final runtime `7db3f07f21f4f653314fca26d47019644c2eee5c`.
The layout release is `c42fc53`; the [About-page follow-up](about-legibility/README.md)
completes white text in the separate public stylesheet without changing any
application JavaScript, worker or main stylesheet bytes.

The new local evidence layout left Chrome on the opening
screen; the previously deployed version remained usable. The pre-correction
startup trace reaches the run-loading stage without a rendered-frame callback.
The failure is retained in [startup observations](startup-observations.json).

The correction makes the evidence viewport a size-contained layout boundary,
positions its content independently of intrinsic parent sizing, and enables
columns only when the available height is at least 100 pixels. Full-workspace
reading restores normal document layout. It preserves fitted pagination, exact
record access, the native robot meshes, rendering quality and recorded motion.
It does not dismiss the opening screen on a timer or disable scene features.

Thirteen subsequent local navigations reached the first rendered frame in
719.5–1,079.9 ms. Daniel confirmed the page was responsive again, reviewed the
white text and active indicators, and explicitly authorized deployment. These
are development-build observations with uncontrolled cache/device conditions;
they do not establish production or phone performance. The exact native
Chromium stack responsible for the earlier stall was not recovered. The
successful response to the sizing correction supports a layout regression;
it is not a claim that every possible startup failure has been eliminated.

Dark-mode text uses opaque white across labels, evidence and Study cards,
chart annotations and disabled controls. Hierarchy uses size, spacing and
weight. The five scene tools indicate active state with an underline, retaining
their touch targets and keyboard focus indication. Light-mode text is unchanged.

[Frontend checks](frontend-checks.json) retain 219 passing tests in 36 files,
TypeScript and the optimized build. Temporary startup probes and the local
logging endpoint were removed before building. DOM tests use mocked geometry;
operator review supplies the local rendered recovery observation. Automated
browser discovery remained unavailable, and no fresh phone/PWA review is
claimed. Two successful local pages later logged a MetaMask connection error;
those events remain in the observations and are not concealed as a clean console.

The release preserves all 1,252 already verified public evidence files exactly,
including the original verification timestamp and Study generation. Only the
application shell/assets and interface runtime provenance changed. The separate
engine-publication refusal was not bypassed; no new engine result was accepted.

The [release record](release.json) binds the package and changed files.
[Package verification](package-check.json) passed 203 checks. With the publisher
lock held, the release staged without assigning the domain, compared 16 served
files exactly, promoted, repeated those comparisons publicly, and passed
[305 public checks](public-check.json). The [deployment receipt](deployment.json)
retains the URL and time. The automatic publisher's frozen package/runtime pins
were advanced only after those public checks. Its previous configuration and
publication receipt remain backed up outside Git.

[Release method](release-method.json) records the helper digest and the initial
lock deferral; it was retried after the scheduled publisher released its lock.
No publisher process was disabled. These integrity and HTTP checks do not
replace the device and rendering limits stated above.

The final follow-up repeated package verification, staged and public readback
of 17 files, and all 305 public checks before advancing the publisher pins.
Its [deployment receipt](about-legibility/deployment.json) is the current
production pointer; the parent receipt preserves the first layout deployment.
