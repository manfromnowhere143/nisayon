# Published research release

[Nisayon 0.1.0](https://github.com/manfromnowhere143/nisayon/releases/tag/v0.1.0)
is public under Apache-2.0. Public `main` and the annotated `v0.1.0` tag resolve
to `886710e819c218b89b61ea7a4899ef01d2f2cd24`. The [publication receipt](publication.json)
binds the repository, tag, release notes and downloaded validation asset. Its
bytes match the uploaded receipt. Private development ancestors and separately
obtained policy weights are outside this distribution.

The [license review](../../../licensing-review.json) records the four requested
precedents: Sentinel, Telos, Inbar and Odeya use Apache-2.0. Nisayon carries the
unmodified license, its own NOTICE, package license metadata and a documented
third-party boundary. Daniel delegated the choice; no license decision remains
pending.

## Checked source and presentation

The exact published commit passed all 377 local tests, lint, formatting and
58-document checks. Clean Linux and macOS CI each passed 359 tests with 14
optional-simulation skips. Those CI results concern the base environment;
the CPU simulator was qualified on the recorded macOS arm64 stack. The
[validation receipt](validation.json) separates these scopes and binds the
package contents, history review and original reproduction commands.

Both historical scorers reproduce the retained negative comparisons: 6/10
scripted incidents accepted per arm, and 3/3 paired repetitions of one known
incident accepted per arm. The five-run example reproduces reference/correction
completion, regression/suppression failure and invalid-replay rejection. It
remains unresolved for acceptance without fresh confirmation. Its executable
sources and the scientific records are unchanged between the initial checked
snapshot and this release.

The README now leads from the integration problem to both results and the
reproduction commands. Three Mermaid diagrams were rendered and visually
inspected in light and dark themes; citation metadata validates against the
official CFF 1.2.0 schema. GitHub's rendered README contains the expected
navigation, results, license and Mermaid container. Live browser screenshot
review was unavailable because the documented runtime had no registered browser.

## Retained failures

- A disk-full interruption prevented finalizing command `e784945`. Its original
  record and logs remain; final duration and test summary are unknown. Only two
  verified completed temporary test copies were removed to recover space.
- An in-worktree pytest temporary directory inherited synthetic reservations.
  Command `07de5d8` failed. The unchanged tests pass with their temporary directory
  outside Git; the reservations and failed fixtures remain.
- The first GitHub run, [35388427950](https://github.com/manfromnowhere143/nisayon/actions/runs/35388427950),
  failed because both runners lacked `ripgrep`. The failure was reproduced
  locally. CI now installs the prerequisite documented for users; no test or
  acceptance obligation was weakened.
- A one-off archive inspection selected uv's `.gitignore` as an archive. The
  corrected inspection requires exactly the wheel and source archive and checks
  their license contents. [The failed attempt is retained](package-inspection-correction.json).

## Accounting and continuation

[Command costs](cost-summary.json) separate these release costs from both scored
experiments. Each outer command is counted once. Nested test, renderer and
simulator durations are not added again. Concurrent command-wall totals are
resource measurements, not active engineering time. GitHub job timestamps are
retained separately. Human effort, provider charges, energy, unrecorded commands
and the disk-full command's final duration remain unknown.

The original mission start remains `2026-09-17T21:30:41Z`; no claim of ten active
hours is made. No further known-D07 run is justified. The next scientific step
needs a separately authored ambiguous decision and enough avoidable work for
an additional experiment to repay its cost. The later reset qualification is
retained on the evaluation branch after this release's freeze; it establishes
no accepted repair or matched cost opportunity under the current rule.

The standing voice and authorship policy is in `AGENTS.md`, `CLAUDE.md`,
`docs/VOICE.md` and `memory/INDEX.md`, with notes `321be0e8` and `c0a59c06`.
Policy commit `b1cc0c3` and the `5e3d191` elaboration are verified on canonical
main at `f8dd43d` in the [readback](canonical-policy-readback-f8dd43d.json).
Daniel Wahnich's configured author and committer identity is preserved.
