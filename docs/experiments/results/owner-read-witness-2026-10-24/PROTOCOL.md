# Can unchanged code conceal changed normalization data?

24 October 2026. Prospective engineering experiment, selected by the implementer.
This is an exposed dependency-omission control, not an untouched owner decision.

The current SDK hashes declared files and loaded owner Python modules. Ordinary
data reads remain a declared-completeness premise. Test that boundary with the
unmodified OpenPI normalization loader at
`215abfb217dbac7d5f1273282331b9b1866c0479`, a small JSON statistics file and a
transparent wrapper. No model, policy training, simulator or hardware is needed.

1. Preserve SDK `756c7a510b913dfceb490303b79f68cc870c38a2`. Run a reference,
   sign-error control and candidate with the statistics deliberately omitted
   from declared dependencies. Retain the run, mutate only the statistics and
   compare reuse applicability with a fresh execution under the original oracle.
2. If the omitted dependency remains invisible, add a bounded CPython file-open
   witness around native import and execution. Observe owner-file read attempts;
   never silently add undeclared dependencies. Require a complete witness for
   new plans, while keeping historical evidence readable under its old scope.
3. Require omitted data to prevent acceptance. Declare it explicitly and require
   correct behavior to pass, the sign control to fail and data changes to make
   old evidence inapplicable. Confirm on different numerical inputs after the
   implementation is frozen. These are fresh inputs, not independently hidden
   answers.
4. Test missing/edited witnesses, import-time reads, aliases, native-environment
   exclusions, read/write modes, unsupported descriptors and bounded overflow.
   Retain failures and reruns. Run the existing qualification regressions.

The witness is not a sandbox or a complete dependency detector. Native C file
access, environment variables, remote state, subprocesses, devices and semantic
adequacy remain outside its scope. Record limitations encountered in the native
experiment instead of weakening a failed gate to manufacture acceptance.

Record commands, elapsed machine time and setup failures. Human setup, review,
historical research and total engineering cost remain unknown unless measured.
No twofold saving, owner adoption, competitive superiority or physical acceptance
follows from this experiment.
