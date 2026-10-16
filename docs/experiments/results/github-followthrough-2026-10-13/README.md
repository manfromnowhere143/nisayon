# Two new responses, checked and answered

**13 October 2026 · N032 · bounded software follow-through.**

The GitHub readback found two new responses since the preceding checkpoint.
Both warranted verification. The [frozen protocol](protocol.json) selected
their concrete corrections over more outreach or engine expansion.

## LeRobot: make the regression fixture portable

[JonnyFaeth's report](https://github.com/huggingface/lerobot/pull/4943#issuecomment-6133164059)
identifies a fixture error in our PR: `forkserver` is unavailable on Windows.
The contributor reports **17 failures and 31 passes** at `5166b725`, then
**48 passes** after selecting `spawn` when `forkserver` is unavailable. Their
environment was Windows x64, Python 3.12.14, Torch 2.11.0+cpu and Gymnasium 1.3.0.
This is an attributed external report, without a repeated base-versus-patch
comparison or attached raw test log.

The [Python 3.12 contract](https://docs.python.org/3.12/library/multiprocessing.html#contexts-and-start-methods)
supports that diagnosis. We adopted the suggested fixture change and credited
the contributor in commit `0f5d98875af5c7bd98c2b6804cba96119b2ef12b`.
The production evaluator is byte-identical to `5166b725`; the test assertions,
scripted policy and environment definitions are unchanged.

| Local check | Result |
| --- | --- |
| Original 48 selected tests, normal macOS context selection | 48 pass, zero skips |
| All 17 async cases, forcing the fixture's available-method list to `spawn` | 17 pass, zero skips |
| Real worker contexts observed | 34 forkserver workers; 34 spawn workers |
| Full upstream pre-commit | All 19 hooks pass, including mypy |

The fallback check uses the [retained probe](worker_context_probe.py). Only the
fixture's available-method list is controlled; Gym, multiprocessing and the
evaluator run normally. This establishes fallback behavior on macOS, not our
own Windows execution. Python 3.12.13 and all 71 installed distributions remain
unchanged from N031. The [case results](lerobot-verification.json) and exact
commands under `runs/` preserve the boundary.

The existing PR branch was advanced by one commit. Both published source files,
the parent, human commit identity and exact PR body were checked. The
[reply](https://github.com/huggingface/lerobot/pull/4943#issuecomment-6140580937)
credits the Windows report and distinguishes the local check. See the
[publication receipt](lerobot-publication.json). At the
[CI readback](upstream-ci.json), only labeling has passed; maintainer review,
merge and LinCanNerd's offered Thor test remain pending.

## Arisole: verify the repaired source distribution

[The maintainer reports](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6134928238)
that 0.1.4 addresses the three missing-configuration failures reported during
N025. We downloaded the published wheel and sdist and verified their PyPI
SHA-256 values. The release includes both YAML configurations under
`tests/fixtures/configs`; affected tests resolve those packaged paths.

| Check | Result |
| --- | --- |
| Unmodified extracted sdist, outside Arisole's development repository | 32 pass, zero skips |
| Same original tests with the installed wheel preloaded | 32 pass, zero skips |
| N025's 12 retained CLI controls against the wheel | 12 pass |
| Matched/comparable/incomparable counts against input labels | 12 pass |

These are two executions of the same 32 tests, not 64 distinct controls.
The new environment uses Python 3.12.13 and the same dependency versions as
0.1.3. All 86 extracted files remained unchanged; all 35 installed package files
match the wheel. The original sparse-label case remains `INSUFFICIENT_DATA`,
exit 2. The [verification receipt](arisole-verification.json),
[controls](reporter-controls-result.json), [coverage counts](coverage-counts.json)
and [lock](requirements.lock) retain the evidence.

The first suite invocation was invalid: the Nisayon command recorder anchors
the working directory at its repository root, so relative `tests` selected
Nisayon in the reporter environment. It produced 90 collection errors and two
skips, with no qualified Arisole result. Its logs and XML are retained. Explicit
child-directory selection corrected the execution; a separate wheel-bound
invocation preserves the prior N025 comparison boundary. The
[addendum](protocol-addendum.json) and [setup notes](setup-notes.json) record this
and the readback/metadata mistakes without removing their history.

The [verification reply](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6140509718)
was sent and read back exactly. This resolves the packaging limit for **0.1.4**;
N025's original 0.1.3 failures remain historical evidence. Arisole's licenses and
notices are retained under `upstream-notices/`.

## Coverage and decision boundary

The [readback manifest](readback-manifest.json) records paginated issue comments,
PR reviews, inline comments and timelines for 15 tracked Nisayon threads,
including #4450, #4927, #4932 and #4943. The account notification feed was read
for routing; unrelated project content remains in ignored local artifacts.
The [compressed thread snapshot](threads.json.gz) retains relevant responses,
including edited-comment timestamps. No other new response was found. Neither
the nine older requests nor the unanswered XPolicyLab/DREAM reports was reposted.

The falsifiers were a failing or skipped declared check, dependence on files
outside the release, or a changed production/test contract. The accepted scope
is the checked fixture portability and release reproducibility. Resources were
local CPU software checks and one new isolated environment; no policy training,
learned checkpoint, physics, GPU, cloud or robot execution was added. Recorded
command times exclude engineering, correspondence and adoption costs.

No robot-performance improvement, Nisayon product adoption or comparative cost
advantage follows. N015 still requires a consequential owner decision and
complete comparative costs. Resume on concrete review/Thor evidence, or assess
the already frozen N030 candidate; preserve terminal reward accounting and all
earlier failures. Do not expand the platform or repeat unchanged outreach.
