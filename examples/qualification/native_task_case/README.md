# Retained native bowl-placement comparison

These 20 files are an unmodified subset of the
[published N100 observations](https://gist.github.com/manfromnowhere143/d76ce08ce521b36bcf4c15383d71a6f3/67283ffad2d72ccb42b73096b3daac4401646dcb).
[SOURCE.json](SOURCE.json) records every original byte identity and source path.
The selected pilot groups are `matched-baseline-01/libero_spatial` and
`matched-evaluation-01/float32-libero_spatial`: five pairs, with 390 reference and
376 candidate native steps. Every recorded episode succeeds. This does not
demonstrate a training-quality improvement or population non-inferiority.

`float32` is the retained arm name; effective inference dtype/settings are in
the original policy records. Do not infer dtype from the directory name.

[protocol.json](protocol.json) declares the reader's exact task/population and
format. [The native task guide](../../../docs/NATIVE_TASK_OUTCOMES.md) gives the
execution, export and reassessment commands. Original paths in native invocation,
checkpoint and video metadata are retained as text; the reader never follows
them or executes the listed command.
