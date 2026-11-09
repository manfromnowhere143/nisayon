# Lighting experiment removed from production

20 September 2026. Daniel authorized deployment of the local correction and
asked to leave the unsuccessful lighting experiment aside. Production now uses
UI runtime `deb1415e956b16589ce0bc3a51e5cf5034c6bac1` at
[nisayon.danielwahnich.dev](https://nisayon.danielwahnich.dev/).

The failed still-rendering mode has no application entry point, control,
diagnostic activation or renderer import. The built runtime contains neither
its path-tracing chunk nor its BVH worker. Experimental source and dependencies
remain disconnected for diagnosis. This release removes the failure; it does
not claim a replacement lighting improvement.

The deployed correction had already passed 210 frontend tests, TypeScript and
the production build. See the [retained failure and local qualification](../lighting-stall-2026-09-20/README.md).

## Release method and evidence preservation

The automatic publisher correctly refused the available engine export after
its adapter/evaluation dependencies changed. It reported
`adapter_or_evaluation_dependency_changed`. No current engine result was
accepted, re-evaluated or reclassified to bypass this failure.

The correction was packaged over the previously qualified public snapshot.
Preflight checked the old runtime receipt and implementation pins, and matched
its live index, engine inventory, publication status and Study discovery bytes.
The new package replaced application assets and `index.html`, updated only the
instrument commit in the engine inventory, and described retained publication
in `api/publication.json`. Its 1,252 evidence files are byte-identical to the
prior package. The evidence verification date is still
`2026-09-20T16:17:49.367530+00:00`; its engine commit remains `8869e50f…`.

Study generation remains `97427d05f72a63e7b1ef8e89eadf4bce1903f598ac61a7a572c36d162aaeb487`.
The site-package receipt was rebuilt from actual static bytes and configuration.
[Release record](release.json) lists every changed path and the receipt digest.

With the publisher's exclusive lock held, the release staged a prebuilt
production deployment without assigning the public domain. Thirteen files were
read back exactly before promotion and again from the public domain afterward:
the app shell, engine/publication responses, Study discovery/generation,
application assets, workers and served geometry assets. Only then were the
private publisher configuration and last-success record advanced to the
corrected, frozen runtime package. The old configuration was backed up outside
Git. Future valid engine publication will use the corrected UI runtime.

## Verification and limits

- [Package verification](package-check.json): 203 checks passed.
- [Deployment/readback receipt](deployment.json): staged and public bytes match;
  promoted at `2026-09-20T19:16:41.003609+00:00`.
- [Public verification](public-check.json): 305 checks passed, covering served
  assets, evidence references, headers and crawl resources.
- The [next automatic publisher cycle](publisher-followup.json) still refused the incompatible engine
  export, while the corrected runtime pin and last-success release remained
  intact. The UI release does not resolve that separate engine-publication issue.

These are build, integrity and HTTP checks. Browser discovery was unavailable;
there is no fresh rendered Chrome/iPhone/PWA result in this release. The narrow
correction restores the existing real-time rendering path rather than adding
another unqualified rendering mode. No engine source, result, Reiyah file or
Git remote was changed.

The separate [layout plan](../../no-inner-scroll-2026-09-20/PLAN.md) covers fitted
evidence pages and removal of the mobile scene overlays. It is not part of this
deployed runtime.
