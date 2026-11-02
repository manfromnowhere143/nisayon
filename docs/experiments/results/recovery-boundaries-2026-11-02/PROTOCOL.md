# Target discovery and two bounded qualification probes

2 November 2026. Nisayon source `a0ecf1524c1af94f4081d7514c5b8429b4a69925`.
This is investigator-selected development work. Every inspected issue is exposed
and excluded from the future untouched owner study. No agent-comparison or
economic-superiority claim is being tested here.

## Selection rule

Prefer an unresolved, consequential, source-accessible question with a small
independent outcome reference, a competent existing comparator and an identifiable
owner/review route. Complexity or company size alone is not value. Check live
discussion, linked fixes and retained Nisayon records before adding an intervention.
Do not implement a duplicate fix. Record unavailable/private systems explicitly.

Discovery includes NVIDIA, OpenAI, Physical Intelligence, DeepMind, Meta Habitat,
Drake, ROS2, Cognition, Mobileye and SpaceX. An Intel implementation of a Mobileye
model is not Mobileye's current production stack. A community launch API is not
SpaceX flight software. Official ownership and active maintenance are separate gates.

## Habitat optimizer-state probe

Compare exact base `0fb6f43ffe806a8088a171b036336c093bcf604e` and proposed
`0f69759da48e76705c9247845d9dabff851e7b5f` from Habitat PR #2230. Execute its
unmodified source-extracted `before_step` and `_create_optimizer` methods on
real PyTorch 2.9.0 CPU. This isolates those methods; it is not a Habitat scene,
PPO rollout or full distributed trainer execution. Preserve Meta's source credit.

Question: does gradient sanitation preserve a failed update as a no-op after
Adam state exists? Distinguish finite weights, identical parameters, identical
optimizer state, a valid next update and explicit refusal. The issue proposes
no-op semantics; the PR's narrower finite-weight claim is scored separately.

Before injecting NaN/+Inf/-Inf into one policy gradient, execute three valid
updates to populate moments. Keep learning rate, epsilon, initial state and
remaining gradients matched. Compare with the identical snapshot that receives
no optimizer step. Independent reference: byte/tensor equality of parameters
and optimizer state plus the next clean update from that saved snapshot.

Controls: ordinary finite update; fresh SGD with no momentum; warm Adam;
policy/auxiliary/coefficient parameters; absent gradients; repeated fresh process;
checkpoint round trip. A conservative local guard may refuse a nonfinite update
before calling the native method. It must preserve the clean path exactly and
must not be described as autonomous recovery or a production distributed patch.
First retain the candidate's original tests and the failing stronger check, then
evaluate a guard. No physical task or learning quality is measured.

## OpenAI MCP replay probe

Inspect current Agents SDK source and the live #5474 discussion before execution.
Its concurrency finding and proposed version-gated lock change belong to the
reporter; another contributor has already offered to implement it. No competing
implementation is planned.

Question: when a tool commits an effect but its response is lost, what can a
caller legitimately infer or retry? Run a real local MCP HTTP tool and SDK client,
with a separate append-only server effect journal. No model API, credential,
paid service or real external side effect is needed. Controlled local state is
the oracle; process success and a missing response are not outcome labels.

Discriminate no execution, committed-but-unacknowledged execution, duplicate
execution after retry, explicit failure and successful recovery. Check ordinary
success, a failure before the effect, a failure after the effect, retry disabled
and enabled, and exact repeatability. Inspect existing docs/tests first: if this
is already documented semantics, retain that result rather than label it a new
bug. Do not infer an at-most-once guarantee from successful retries or a transport
lock. Any observed contrast remains a transport-boundary result, not a robotics
deployment or general agent benchmark.

## MCP scope contract, before execution

The reviewed surface is the Python Agents SDK's public MCP HTTP wrapper at
`e355d69152d4f4730dfb03b63dbce53e8d9f5d8c`, version string 0.24.0. Remote tag
`v0.24.0` points to `17d994bd3045dae71acda676a4ef4762ed8ecd94`; the experiment
pins the stated main commit, not the release. Required observation: distinguish
attempted requests, server effects and acknowledged results across one injected
HTTP 503. Compatibility: no SDK/API or wire changes. Unsupported: API-hosted MCP,
model execution, real external side effects, distributed transactions, and an
at-most-once guarantee across server restarts. Existing alternatives: zero retries
and server-managed operation-key deduplication. A local deduplicating control is
an ordinary engineering baseline, not a Nisayon algorithm. The exact source's
`docs/mcp.md` documents configurable automatic retries and defaults to zero in
the constructor. This investigation tests consequences, not an undocumented
assumption that all retries are safe. Upstream final implementation review is
not invoked because this is report-only assessment with external local probes.

## Resource and stop rules

CPU only, local synthetic data; no GPU, paid inference, hardware, outreach or new
upstream PR. Initial execution estimate: under ten CPU-process minutes per probe
after dependencies, with a 120-second per-process cap and no unattended retries.
Dependency setup gets at most ten minutes and 1 GB additional downloads per
environment. Human/coordinator effort and charges not observed remain unknown.
Stop an intake if source fidelity, independent observability or useful additional
evidence cannot be established. Preserve failures and source/drift boundaries.
