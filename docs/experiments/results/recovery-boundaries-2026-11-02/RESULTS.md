# Recovery-boundary results

These are two exposed, constructed software investigations. They are not two
independent samples from a population, an A/B/C agent trial or a robot deployment.
The process recorder retains failed commands alongside successful execution.

## Habitat: finite weights and a skipped update are different contracts

Meta's base is `0fb6f43ffe806a8088a171b036336c093bcf604e`; PR #2230 is
`0f69759da48e76705c9247845d9dabff851e7b5f`. `habitat_probe.py` compiles the
unchanged AST nodes for `PPO.before_step` and `_create_optimizer`, after checking
their source digest. The surrounding tiny module supplies policy, auxiliary and
coefficient parameters. It uses the source's actual Adam construction and real
PyTorch 2.9.0 CPU operations on explicitly constructed float64 parameters. It does not import the full Habitat package or run
a scene, rollout, distributed collective, mixed-precision scaler or scheduler.
MIT source and Meta attribution are retained in `records/`.

After three finite updates, inject NaN, +Inf or -Inf into one gradient in each
of those three parameter groups. Other gradients are zero. Compare the result
with a deep-copied checkpoint that receives no failed optimizer step, then give
both branches the same fresh valid gradients. Tensor/optimizer equality is the
reference; the test does not obtain its expected values from Adam's formula.

| Variant / observation | Result |
| --- | --- |
| Author's original surrogate tests, unmodified | 5 pass; they use fresh SGD without momentum |
| Original source, nine warm-Adam fault conditions | Nonfinite weights in all nine |
| Proposed source, same nine conditions | Finite weights in all nine; parameters and optimizer state change in all nine |
| Proposed source, next clean update | Differs from the skipped-step reference in all nine |
| Fresh SGD, all other gradients zero | Parameters/state unchanged; this control does not transfer to warm Adam |
| Local nonfinite-gradient refusal | All nine rejected before optimizer mutation; next clean step matches reference |
| Additional refusal controls | Finite path below/above clipping threshold, absent gradients, checkpoint round trip, explicit distributed refusal and changed-source rejection pass |

For the policy-NaN case, the largest parameter change is
`0.008130051304138963`; Adam counters advance from 3 to 4. The returned policy
gradient norm remains `nan`. These values describe this fixture, not training
quality or a universal error bound. The original failing assertion is retained
in `habitat_noop_red.py` and `raw/habitat-noop-red/`; it remains intentionally red.

The first refusal suite passes 15/15 in two fresh processes. Source-drift
protection adds one control; that suite passes 16/16. A final measurement-regression control brings the
completed suite to 17/17. This is an ordinary
conservative guard in the experiment, not a shipped Habitat recovery patch.
A rank-local exception before collectives can strand other ranks, so the guard
explicitly refuses distributed use. It assumes the pre-existing parameters and
optimizer state are finite. It does not restore corrupt checkpoints, qualify
finite-but-overflowing norm calculations or promise unchanged learning behavior.

The issue's proposed no-op interpretation is contradicted under this warm-Adam
fixture. The PR's narrower finite-weight objective is supported in these nine
conditions. Conflating those two claims would overstate the finding.

## OpenAI: acknowledgement and committed effect are separate observations

Native source: Agents Python main `e355d69152d4f4730dfb03b63dbce53e8d9f5d8c`,
version string 0.24.0, with MCP 2.3.0 and protocol `2026-07-28`. The release tag
v0.24.0 points elsewhere (`17d994bd`); this result binds the main source, not
an asserted release equivalence. The final probe checks loaded `server.py`
bytes. The complete observed dependency versions are in `mcp-requirements.lock`.

`mcp_effect_probe.py` starts a real loopback MCP HTTP server and native SDK
client. Its tool appends and fsyncs a separate synthetic effect journal.
An ASGI fault proxy either returns HTTP 503 before forwarding the first tool
request or collects the completed server response and substitutes HTTP 503.
The latter is controlled acknowledgement loss, not a tested TCP reset.
The advertised tool has `idempotentHint=False`. No LLM, credential, Responses
API, hosted MCP service or external side effect is involved; tracing is disabled.

| Fault on first request | Retry budget | Client observation | Requests | Journaled effects |
| --- | ---: | --- | ---: | ---: |
| None | 0 / 1 | Acknowledged | 1 | 1 |
| Before effect | 0 | MCPError | 1 | 0 |
| Before effect | 1 | Acknowledged | 2 | 1 |
| After effect | 0 | MCPError | 1 | 1 |
| After effect | 1 | Acknowledged | 2 | 2 |
| After effect; operation-key deduplication | 1 | Acknowledged | 2 | 1 |

Both values of the SDK serialization flag produce this table: fourteen assigned
conditions. The first and second fresh processes produce byte-identical result
JSON. The final run adds explicit loaded-source admission and reproduces the
same fourteen outcomes. These are 42 executions of 14 related conditions, not
42 independent incidents. The single-call probe does not reproduce or challenge
the reporter's four-call concurrency timing claim.

The ordinary deduplication comparator wins on effect count in this fixture.
Its operation-key cache is local and volatile; it establishes no exactly-once
transaction across crashes, restarts, distributed servers or storage failure.
Zero retries prevents this automated duplicate but leaves post-commit failure
unresolved. The existing SDK default is zero; retry behavior is documented.
This is a qualification example and possible documentation supplement, not
evidence of an undisclosed at-most-once guarantee being violated.

`audit_mcp.py` reconstructs coverage and counts from request/effect journals.
Six audit controls pass, including five rejections of altered/missing evidence:
missing assignment, duplicate assignment, altered effect, absent request log,
and a false zero count. Integrity and internal consistency do not establish
authenticity. The oracle does not use model self-scoring, but the investigator
controls the fixture; independent external adjudication remains absent.

## Reproduction and accounting

Exact local command arrays, working directories, process times, exit codes and
log digests are retained under `raw/*/receipt.json`. Python in the recorder
header is the host recorder (3.14.2); test logs and result metadata identify the
executed environments as Python 3.12.13. Do not confuse those identities.

Core commands, from the owning worktree after the retained environments exist:

```sh
artifacts/frontier-targets/torch-env/bin/python -m pytest -v work/research/frontier-targets-2026-11-02-v1/habitat_controls.py
artifacts/frontier-targets/torch-env/bin/python -m pytest -v work/research/frontier-targets-2026-11-02-v1/habitat_noop_red.py
artifacts/frontier-targets/mcp-env/bin/python work/research/frontier-targets-2026-11-02-v1/mcp_effect_probe.py artifacts/fresh-mcp-effects
python3 work/research/frontier-targets-2026-11-02-v1/audit_mcp.py artifacts/fresh-mcp-effects
artifacts/frontier-targets/mcp-env/bin/python -m pytest -v work/research/frontier-targets-2026-11-02-v1/audit_controls.py
```

The second command is expected to fail; the probe refuses to overwrite an output
directory. The public packet supplies fresh-environment instructions. Dependency
locks capture observed versions; they do not authenticate package publishers.

`costs.json` totals only recorded command wall time, not complete engineering
effort or parallel critical-path time. Source discovery, analysis, initial Torch
setup, environment/clone setup, edits and review were not all timed. Tokens,
charges, human review and maintenance remain unknown. No paid model call, rented
GPU or cloud instance was launched. The complete-cost ratio is null.

Preparation failures retained in the research narrative: one guessed fork URL
returned 404; an organization API endpoint was unsupported; a Mobileye org query
returned 422; a guessed research repository returned 404. Missing FastMCP paths
were corrected after inspecting MCP 2's actual low-level API. A missing output
directory and shell glob were corrected. One patch application failed on an
unmatched context without changing source. Initial lint found two import-order
issues and an explicit-zip-strictness omission; these were corrected. None of
those failures is counted as a passing experiment or negative upstream result.
The private repository-wide documentation check also finds five pre-existing
broken links in an unrelated XPolicy source copy; those files were preserved.

Review found and falsified a defect in this probe's own delta reporting: Python's
`max` could return a finite number when another parameter delta was NaN. The
original failing measurement test is retained in `raw/measurement-red/`. The
corrected probe reports `nonfinite` whenever any delta is nonfinite; the final
measurements are in `raw/habitat-measurement-corrected/`. Treat the original base
maximum-delta field as invalid, not a finite bound. The independently checked
finiteness, state equality and all candidate deltas remain unchanged.

## Decision

Retain and share the bounded probes through Nisayon's public research history.
Offer the Habitat contract clarification for review only under correspondence
authority. Do not build transactional middleware, distributed recovery or a
learned selector on these results. A competent engineer can implement both
controls with ordinary tools. Nisayon's comparative benefit must be tested with
those controls available to the baseline, in a real owner decision followed by
an independently selected untouched change.
