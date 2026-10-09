# Recheck the Lift transfer repair

The B2 correction completed nine of ten paired tasks; unchanged inputs completed
none. Its retained packet includes every raw observation, declared policy input,
actual network input and executed action. `nisayon verify-lift-transfer` now
recomputes the result from that packet without loading a policy or simulator.

This is a reader for one sealed experiment. It does not run new conditions,
select a correction or extend the five-field agent repair interface. The
[original B2 report](results/b2-semantic-transfer-001/README.md) retains the
failure, protocol and scientific limits.

## Run the reader

Use the locked `records` extra in a separate environment. Do not synchronize
either of the frozen experiment environments to prepare this check.

```sh
UV_PROJECT_ENVIRONMENT=/tmp/nisayon-reader-venv \
  uv sync --frozen --no-default-groups --extra records --no-editable

/tmp/nisayon-reader-venv/bin/nisayon verify-lift-transfer \
  --packet /absolute/path/to/b2-semantic-transfer-001 \
  --protocol /absolute/path/to/protocol.json \
  --out /absolute/path/to/new-inspection.json
```

The packet is the private raw artifact directory containing
`artifact-manifest.json`, not the compact report directory in Git. The protocol
is the original [frozen protocol](results/b2-semantic-transfer-001/protocol.json).
The installed command works outside Git. It reads the supplied paths; it does
not follow the protocol's old workspace or runtime paths. The output is optional,
must be outside the raw packet and cannot overwrite a previous result.

## What the command checks

The implementation pins the original protocol and manifest SHA-256 values.
Every declared member must match its size and digest before numeric inspection.
Missing files yield `integrity: incomplete`; changed or inconsistent evidence
yields `integrity: invalid`. Both keep the decision `unresolved`.

The reader separately recomputes:

- All twenty assigned outcomes from cube height, backend success and reward,
  including the full-horizon corrected failure on seed 180104.
- The source relative-position convention, the three-coordinate correction,
  unchanged remaining inputs, and exact float32 network-input bytes.
- Intended-to-clipped-action agreement, control clocks, captured initial-state,
  observation, model and controller bindings, and equality within each pair.
- The paired gate, trace-derived control counts, contract-counted substeps and
  equality of the recorded parameter digests. Producer summaries must agree.

The reader does not import the producer's verdict function or observation
adapter. This separates implementations; it does not establish independent
review. It loads NumPy arrays with object deserialization disabled and bounded
expanded archive sizes. It rejects aliased member paths, symlinks and duplicate
JSON/archive keys.

Exit code zero means the evidence readback completed with verified integrity.
Read `decision` for the scoped scientific result; process completion alone does
not grant support. Exit code one means incomplete or invalid evidence, and two
means a command/output error. JSON output retains the reason.

## Boundary

Byte integrity identifies this retained record. It does not prove physical truth,
authentic recording, independent custody or complete simulator state. The command
does not reload weights, rehash runtime installations, verify the whole resource
monitor, or execute fresh policy feedback. Those historical checks remain in
the B2 packet. Fixed arm order, the remaining task failure and historical
action-replay discrepancy remain limitations.

The [software qualification](results/transfer-evidence-001/README.md) records
relocation and negative controls separately from the original twenty episodes.
Neither this reader nor its runtime establishes a diagnosis or cost advantage.
