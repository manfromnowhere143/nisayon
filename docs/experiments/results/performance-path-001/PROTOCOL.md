# N028: qualify a route to a performance comparison

12 October 2026. This is a source and installation-readiness check, selected
after reading the papers and code. It is not a blinded scientific experiment.

The current task asks how to obtain new robot performance and comparative value.
Nisayon's known B2 correction and adopted reporter fix do not establish either
a new recovery method or diagnostic superiority. Preserve N015 and its pending
owner decisions. Do not reopen spent conditions or allocate robot, model,
training, GPU or reserved executions.

Selected comparator: DREAM-Chunk Kinetix at
`0aae0757ca63895daf95dd60acfd3a562fd097a0`. The inspected source declares a local
`third_party/kinetix` dependency that the recursive Git tree does not contain.
Its evaluator also needs matching policy and world-model checkpoints. Test the
installation prerequisite before spending resources on a performance comparison.

1. Retrieve the archive at that exact commit. Verify every regular file against
   the Git tree's blob identity; reject unexpected paths or nonregular members.
2. In that separate copy, run native `uv lock --offline --no-build` with an
   existing interpreter, a separate cache and a 30-second timeout. No training
   or evaluator execution. Preserve command, tool version, exit status and logs.
3. Compare the diagnostic with the declared local path and repository tree.
   An expected missing-path failure supports only a release-readiness blocker.
   A different failure is unresolved, not evidence for that explanation.
4. Check the repository's release and issue listings. If the blocker remains
   unreported, use Daniel's standing targeted-outreach authority for one concise
   reproduction and a request for the intended dependency revision and minimal
   frozen evaluation bundle. Verify the posted author, body and URL.

New execution allocation: one archive, two repository metadata responses, one
native resolver attempt, at most 60 command-wall seconds and 32 MiB of additional
retained artifacts. Earlier exploratory reads are retained separately; their
total engineering cost is unmeasured. No dependency installation or cloud cost.

Accept this readiness check only with source identity, the native diagnostic,
explicit missing inputs, a retained decision and verified delivery if posted.
It cannot accept a performance improvement, a policy comparison, an installation
fix, general hardware compatibility or commercial value.
