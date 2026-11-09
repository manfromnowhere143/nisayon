# Compact evidence access correction

Status: published on Daniel's explicit instruction; source/DOM and public-file
checks pass. Rendered phone verification remains pending.

Daniel reported that the deployed Study could not be scrolled on his phone,
leaving Decision, Witnesses, Obligations, Comparison and Scope inaccessible.
That operator report supersedes any implication that the preceding desktop
review qualified the no-inner-scroll redesign for mobile.

The source imposed a fixed-height dialog, multiple clipped descendants and a
size-contained evidence viewport with absolutely positioned columns. The
non-shrinking publication, selection and report controls consumed its height.
Pagination and the full-reading escape were themselves below those controls.
The DOM tests supplied artificial rectangles; they did not establish that the
escape controls fitted the real phone viewport. The exact failed device layout
has not been captured by browser automation and is not claimed as reproduced.

## Correction

At widths through 1,023 CSS pixels or heights through 620 CSS pixels, Study has
one native reading surface under a persistent header. Its records, disclosures,
section decks and reports grow in normal flow. Cards have no separate scroll
container. Close, Copy link and the disconnected execution status remain above
the reading surface. Changing instrument, trial or trial section returns that
document to its start. Expanding evidence or selecting a sample preserves its
position.

The same compact mode applies to the main Evidence and Inspector workspaces,
including Inspect this moment. EvidenceFlow bypasses column measurement and
does not translate, hide or make overflowing records inert in that mode. The
same React nodes retain field and disclosure state across viewport changes.
Larger workspaces retain the existing fitted pagination and its containment
boundary; the prior startup recovery is not undone.

This distinguishes a single full-workspace document from scrolling inside each
card. `overflow: clip` cannot provide scrolling, and size containment excludes
children from intrinsic sizing; both were inappropriate for a growing compact
document. [Overflow reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/overflow),
[containment reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/contain).

No retained value, evaluator meaning, asset, lighting setting, playback,
acquisition stamp or evidence-validation rule changes. White dark-theme text
and underlined scene controls remain intact.

## Evidence and release limit

[Frontend checks](frontend-checks.json) bind the build and record 222 passing
tests in 36 files, TypeScript and the optimized build. Added tests cover phone
mode without a measurable content rectangle, resizing without replacement,
every processor section, the final witness, all frozen obligations and the
Study exit outside its reading surface. These are DOM/state checks, not touch
or rendered layout measurements. The first new section-selection test failed
because its lookup included the selected option's check mark; the corrected
label lookup and complete suite pass. No application failure was hidden by
relaxing that assertion.

Chrome remains unavailable through the supported browser client after the
operator-approved profile window was opened. Plugin reinstall was requested.
The candidate was first held for phone review. Daniel subsequently explicitly
[authorized production deployment](authorization.json); that instruction
supersedes the release hold without establishing device qualification.
Outstanding rendered checks: phone portrait and landscape, small viewport and
enlarged text, final witness and expanded obligations, all Study reports and
trial sections, main Decision/Conditions/Engine/Inspector/Inspect moment,
disclosures and selector changes, reachable exit, and return to the lab.
Check Safari/PWA separately from desktop emulation. A preview receipt may prove
the served bytes; it cannot establish those interactions.

## Review candidate

Runtime `7090fdcad72f761bc74b1d9a8ea951bcc6493470` is available as an isolated
[preview deployment](https://nisayon-l5329lktc-daniels-projects-ca65133a.vercel.app/).
The initial preview left production and the automatic publisher on
`7db3f07f21f4f653314fca26d47019644c2eee5c`. Its receipt records that historical
state; the subsequent production release is recorded below.

[Package verification](package-check.json) passes 203 checks and the
[release record](release.json) binds all 1,252 unchanged evidence files.
[Preview readback](preview-readback.json) matches the HTML, Study discovery,
runtime manifest and all five application/worker/style assets, eight files in
total. A 48-hour deployment-scoped share link was delivered to Daniel for
phone review; its access secret is stored outside Git and memory. Vercel's
[shareable link API](https://vercel.com/docs/rest-api/aliases/update-the-protection-bypass-for-a-url)
was used without changing project-wide protection, production aliases or the
publisher. No phone or browser review has yet been recorded.

## Production release

The exact frozen package was staged as a production deployment with domain
assignment skipped, verified and then promoted to
[nisayon.danielwahnich.dev](https://nisayon.danielwahnich.dev/).
[Deployment receipt](deployment.json) binds runtime
`7090fdcad72f761bc74b1d9a8ea951bcc6493470` and records 17 matching staged/public
file readbacks. [Public verification](public-check.json) passes 305 checks.
The automatic publisher was updated to this package only after those checks
succeeded. Its source-admission rules are unchanged; no new engine result was
accepted. All 1,252 evidence files and their prior verification date remain exact.

These checks establish the served release bytes and covered DOM/state behavior.
They do not establish phone touch interaction, Safari/PWA layout or rendering
performance. The outstanding device checks above remain open after publication.
