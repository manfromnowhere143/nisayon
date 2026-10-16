`MCAPReader.read_all()` can attach an output to the wrong step. With three steps at 0.5, 1.0 and 1.5 ms and values `0, 1, 2`, it returns values `1, 2` and an empty final step. The per-node reader retains all three values.

The session reader selects the first step within one millisecond of each payload. Tightening that comparison to exact timestamps still merges distinct steps that share a timestamp.

This change reconstructs sessions using the boundaries already written by `MCAPWriter.write_step()`: step metadata followed by that step's payloads, in file order. It rejects orphaned, duplicate and timestamp-mismatched payloads instead of silently dropping or overwriting them. The writer, file format, per-node reader and replay scheduler are unchanged. Both documentation paths explain the boundary and the separate requirement to restore clocks for timing-sensitive replay.

Validation on Python 3.12.13/macOS, using the same tests against the base reader and correction:

```bash
python -m pytest tests/core/test_mcap_step_identity_rt.py \
  tests/core/test_pipeline_step_rt.py tests/core/test_buffer_engine_rt.py -q -rs
```

- Base: 28 passed, 11 failed, four skipped. Correction: 39 passed, four skipped. The skips require the optional Rerun package.
- The 15 new tests cover close and repeated timestamps, clock reversal, missing values, empty steps, chunk boundaries, input payloads and malformed records.
- Eight separate native `Pipeline.step()` recording controls improve from five to eight exact round-trips. All eight per-node checks pass before and after; recorded files are byte-identical.
- Broader `tests/core`: 335 passed, three failed, ten skipped. The same three failures occur with the base reader: absent Dora/Rerun imports and a test requiring Rerun availability. That broader run is not a clean suite result.

These checks qualify the recording boundary on constructed CPU cases. They do not establish asynchronous-backend, physical-robot or general replay guarantees.
