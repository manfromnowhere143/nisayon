# Historical qualification record

`owner-reads-v1` is the sealed original run from the 24 October 2026 controlled
OpenPI statistics-input experiment, produced by the qualification implementation
whose bytes match public commit `54a45573389931254e5ad6b39cc1956072b94043`.
The data dependency was intentionally omitted. Its old software assessment is
valid only under that version's declared-completeness premise. It is retained
to test historical reading and prevent silent promotion to v2 read coverage.
The reader does not need the historical owner path or native dependencies.
Do not edit files inside the sealed directory.

`external-reads-v1` is a sealed, exposed normalization control executed on
9 November 2026 at `cf8a5846ec8e2feb9a840dba3db59b661e5031d3`. Its candidate
reads an external calibration file absent from the declared sources. The old
owner-only witness counts that open but allows the matching software result.
The current reader preserves this historical scope and refuses to promote it
to `cpython_bound_reads_v2`. The generating probe and before/after observations
are retained under `work/experiments/external-read-boundary-2026-11-09/`.
