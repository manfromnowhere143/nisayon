# Full-suite temporary storage exceeded the bound

The full check at `7751783bf47efee8af45c6a2a3dc8853e855af6d` passed 435 tests
and failed the unchanged evaluation date fixture. Pytest retained
1,733,797,932 bytes of temporary files in that run's `pytest-229` directory.
Combined measured new payload was about 1.78 GiB, above this continuation's
1 GiB artifact bound. The earlier in-progress measurement was smaller; it did
not establish a peak or guarantee that the completed suite would fit.

The failed resource check is command `29113d51060d4e2eb04de823a86475a8`.
The [inventory](before-inventory.json) preserves the path, size and SHA-256 of
every regular file in the identified completed run. The
[cleanup record](cleanup.json) documents removal of only its passing-test
temporary copies, leaving all five failed-test files (27,227,225 bytes) intact.
Their digests were checked again after cleanup. Original retained evidence,
other pytest roots and other-session files were not changed. The cleanup command
is `93a916e4e25a4377995d6eee91d9ccc3`.

The post-cleanup observation, command `6df327d72fe147eeb3a05f5f93698691`, measures
204,938,213 bytes of retained non-environment payload and 33,494,761,472 bytes free.
It is a current retained-size observation. Cleanup does not erase the overrun.

The project now sets pytest's `tmp_path_retention_policy` to `failed`, so passing
test bodies release their temporary copies during the run. The installed pytest
implementation was inspected: failed test bodies keep their files; this option
does not promise retention for every setup or teardown failure. All command logs
remain retained.

The [measured full check](monitored-full-check.json) at clean
`54660e58078039b569d22031bbf3094ed2d80f91` used a fresh `PYTEST_DEBUG_TEMPROOT`,
with a 512 MiB stop bound for new temporary files and a 5 GiB minimum free-disk
guard. Across 660 samples, observed temporary payload peaked at 182,322,467 bytes
(173.88 MiB). Adding the prior retained-payload observation gives 387,260,680 bytes
(369.32 MiB), below 1 GiB; no guard fired. Discrete samples can miss peaks between
observations, and small subsequent metadata writes are outside that baseline.

The run retained 27,232,440 bytes on completion, including the failed test's files.
It again passed lint, formatting and 435 tests and failed the same evaluation
date fixture. Command `ede42a2cb38143d0adbe6a1ac4e0c604` took 171.914724 s; nested
test and monitor walls are not charged again. The changed retention behavior is
observed; the complete suite remains failing. No new simulator execution or
model call occurred.

The final observation `694cb4d0d4ac468aa8a213652b1520c3` includes that isolated
run's retained files: 232,324,774 bytes of known retained payload and
33,448,321,024 bytes free. Subsequent small documentation and command-record
writes are outside that point-in-time measurement.
