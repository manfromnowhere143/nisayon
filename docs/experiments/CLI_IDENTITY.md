# Observed CLI identity and permission canaries

On 19 September 2026, the installed native executable reported
`codex-cli 0.155.1`. Its SHA-256 was
`8eaf1ad12fe6bf89b1710330f58900014322c7c5af677e43be116d8ac5fc0a9e`.
The npm launcher, launcher package, Darwin ARM64 package and native binary are
bound separately in the [retained protocol](results/cli-01551-boundary-001/protocol.json).
The earlier 0.154.0 experiment records remain unchanged.

`bounded_agent.decide` now resolves and invokes the observed native binary,
checks its bytes again afterward, and retains the command, schema, prompt,
requested model (`gpt-6-astra`) and reasoning effort (`medium`). An unsupported
wrapper or disagreeing native/package version fails instead of silently choosing
another provider. Local executable identity does not attest provider weights.

The [actual tool requests and responses](results/cli-01551-boundary-001/result.json)
show a public canary read succeeding. Both a direct excluded path and a symlink
to it returned exit 1 with `Operation not permitted` and empty stdout. The profile
denied the root, allowed minimal system reads and public-packet reads, and disabled
network access. No model or simulator was invoked. The measured outer command
cost was 0.540872 s; the nested probe cost of 0.140891 s is not added again.

Reproduce against the currently installed CLI, using a new output directory:

```sh
.venv/bin/nisayon run --label cli-permission-canaries --timeout 100 -- \
  .venv/bin/python scripts/experiments/probe_agent_boundary.py \
  --output artifacts/cli-canaries-new
```

This qualifies the observed `command/exec` canaries only. It does not qualify
model-issued tool behavior, an equal provider budget, independently authored
cases, a custodian boundary or resistance to a developer with full filesystem
access. The reserved screen remains unopened and unrun; `agent_adapter_ready`
remains false. Provider charges, human effort and energy are unmeasured.

The controller's opt-in study interface requires an explicit declaration.
Selecting a candidate without one cannot use v1 confirmation as a fallback.
Explicit nonclaims retain their disposition and do not schedule confirmation.
Claims remain recorded after a terminal or budget veto. Incomplete calls retain
known token components even when complete attributable usage is unavailable.
Twenty focused controller, service, recovery and identity tests passed in
command `f4a25a590c5145d4af0c1f60070555ed`; fixtures made no model or physics calls.
