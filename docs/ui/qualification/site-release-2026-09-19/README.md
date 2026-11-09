# Nisayon public instrument

The operator authorized the public subdomain, Vercel deployment, brand assets,
opening screen, bounded dashboard, engine inspection, and Search Console setup
on 19 September 2026. This supersedes the UI mission's earlier local-only scope.
Work remains on `ui/data`; canonical main, the evaluation worktree, and private
Git ancestry have not been published or advanced.

Production: <https://nisayon.danielwahnich.dev/>. The final deployment identity,
package digest and verification are retained alongside this note. The operator
added the GoDaddy CNAME `nisayon` → `469bfdec08cf3f5b.vercel-dns-016.com`.
Vercel reported the domain verified and `misconfigured: false`.

## Opening and dashboard

The first deployment incorrectly used the opening screen for case changes.
The operator reported that regression. The corrected opening is a single
mark-and-name veil mounted beside the instrument, with one 280 ms opacity reveal
after the initial load resolves. There is no staged visual progress sequence,
artificial minimum loading time, camera sweep, or repeated intro for case, run,
panel, or browser-history changes. Reduced motion removes the reveal animation.

Case changes retain the verified dashboard until the next generation, case and
run verify. Identity, evidence root, readings and URL commit together. Failed
selections retain the prior record with an inline error. Playback resumed on the
retained recording stops before its replacement; its old clock cannot advance
the new run. The brand link returns to Readings without reloading the document.

The dashboard occupies the viewport. Diagnostic, evaluator, trial, confirmation,
source and condition records use sections and paging. Exact values, missing
confirmation and unresolved findings remain intact. Local overflow remains as an
accessibility fallback for extreme text and viewport sizes; no universal
no-overflow claim is made. The About document is a separate readable page.

Engine exposes retained contracts, diagnosis records, measured and unknown costs,
file references, and a source-derived inventory of 13 local MCP interfaces and
54 implemented modules. The public deployment reads recorded exports. It does
not execute the engine, connect a live worker, or control hardware.

## Brand and search

The vector N uses opposing circular turns of radius 13 and 8 connected by a
tangent stroke. The Fibonacci relationship is a construction choice, not a claim
of a uniquely optimal proportion. Display strokes and small-icon strokes differ
for legibility. SVG, PNG sizes 16–512, a multi-size ICO, Apple touch icon, maskable
icon, web manifest, and a 1200 × 630 sharing image use the same mark. No trademark
clearance or third-party endorsement is claimed.

The home and `/about/` pages have distinct titles and descriptions, self-canonicals,
sharing metadata, and factual structured data. The home identifies Nisayon with
`WebSite`; attribution is Daniel Wahnich. The guide is delivered as static HTML.
There are no invented ratings, organizations, rankings, credentials, or guarantees.
The sitemap contains the two canonical pages, without artificial `lastmod` dates.

Robots permits the scripts, styles, images and evidence needed to render the
instrument. Evidence and inventory responses carry `X-Robots-Tag: noindex`, rather
than blocking resources the renderer needs. Unknown paths return real 404s.
Content-addressed resources use immutable caching; mutable discovery and HTML
revalidate. The deployment binds inline scripts in its content security policy.

The existing Google OAuth connection was renewed by the operator after an
`invalid_rapt` response. Direct Search Console API readback confirms owner access
to the domain property and the new Nisayon URL-prefix property. Both sitemap
submissions returned HTTP 204. Initial readback reports pending processing, zero
errors and zero warnings; both pages were still unknown to Google's index.
See [the exact Google response](search-console.json). Credentials are not retained.
No general-page Indexing API was used, and no indexing or favicon appearance is
promised. Subsequent readback can use `tools/ui/search_console.py` without
`--submit`; there is no reason to repeatedly resubmit an unchanged sitemap.

## Verification and limits

The corrected source passes 128 frontend tests in 18 files, TypeScript and the
production build. The new transition test delays an actual case load, checks DOM
identity and the retained source URL, exercises Back and a failed selection, and
rejects any replay of the opening veil. The first-load test binds the opening to
actual verification, without a simulated progress sequence.

Package verification passes 78 checks. Production HTTP verification passes 114
checks, including canonical pages, crawl resources, actual PNG dimensions, inline
CSP hashes, all six catalog/discovery/generation/case bindings, immutable headers,
real 404 responses and canonical redirects. The fetched files are also compared
against the outgoing package. This is HTTP and DOM evidence, not a browser render.

The package includes six cases and all 20 retained generations. The allowlist
excludes environment files, private Git history, workspace memory, raw compressed
archives, development failure fixtures and source maps. Required robosuite and
runtime dependency licenses are retained. Source-derived catalog entries are
checked against the source bytes before packaging.

The approved browser connection returned no available browser, so independent
visual, accessibility and GPU performance acceptance remains open. The existing
Three.js minified-chunk warning remains visible. There is no measured browser
frame-rate, Core Web Vitals or physical-device performance claim.

## Sources

- [Google site names](https://developers.google.com/search/docs/appearance/site-names)
- [Google favicon guidance](https://developers.google.com/search/docs/appearance/favicon-in-search)
- [JavaScript rendering and crawling](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- [Sitemap construction](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [Search Console sitemap submission](https://developers.google.com/webmaster-tools/v1/sitemaps/submit)
- [URL Inspection API scope](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)
- [Vercel Build Output API](https://vercel.com/docs/build-output-api/configuration)
