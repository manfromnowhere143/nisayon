# Preserve explicit task names in complete multi-task records

**Before expanded candidate execution.** This extends [v2](PROTOCOL-v2.md) by
four source-derived control families, each in both orders: complete unanimous
`per_task[].task` without task_group, partial task names, conflicting task names
and malformed task entries. An explicit environment is supplied. The complete
case retains its valid inferred task and REVIEW/0; others remain cannot_compare
and BLOCK/1. Require truthful per_task provenance on the complete candidate.

The first correction passed all 48 v2 controls. Further source review showed
that restricting the fallback to single-task input would also discard complete
explicit per-task names. Preserve that valid behavior in a second source copy
before the expanded check. The first candidate and its outputs remain retained.
The final suite has 28 families in two orders: 56 software controls. All other
resource limits and acceptance boundaries remain unchanged.
