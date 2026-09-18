# Lift policy and CPU backend

The first case uses the public robomimic Lift proficient-human BC-RNN checkpoint.
The [model zoo](https://robomimic.github.io/docs/model_zoo/robomimic_v0.1.html)
requires robomimic v0.1 and robosuite's `offline_study` branch for its original
reported results. Those depend on an older simulator binding. We will measure
the checkpoint on the explicitly pinned modern stack; we do not import the
published success rate or claim reproduction of the original study.

The [download identity](../../src/nisayon/engine/assets.py) pins the HTTPS URL and
SHA-256. Loading rejects changed bytes. Weights remain in ignored local storage.
The model-zoo page does not specify a separate checkpoint license. The
[robomimic code license](https://github.com/ARISE-Initiative/robomimic/blob/v0.3.0/LICENSE)
and [robosuite code license](https://github.com/ARISE-Initiative/robosuite/blob/v1.4.1/LICENSE)
are MIT; MuJoCo uses Apache-2.0. Package assets retain their upstream notices.
No training dataset is downloaded and no model is trained locally.

The intended stack is robomimic 0.3.0 (policy only), robosuite 1.4.1, MuJoCo
3.2.7, Torch 2.5.1, NumPy 1.26.4 and Python 3.12.13. Exact transitive packages
are in `uv.lock`. The adapter uses robosuite directly because robomimic 0.3.0's
environment wrapper imports `mujoco_py`. This is an explicit adapter boundary,
not a silent package patch. Low-dimensional observations need no renderer.

Initial machine: macOS 14.4, arm64, 10 logical CPUs, 16 GiB RAM. Inference uses
one Torch CPU thread. Other machines and simulator versions need qualification.

The first installation failed building the unused EGL GPU helper without CMake.
Command `7dade053b93342eb84eefebc5f113292` retained the failure and 7.658049 s
wall cost. The dependency override excludes EGL probing on macOS; the CPU
adapter does not call it. Policy download command
`e18f8191243b44c08dfdcc7ed8a0ac29` took 9.655600 s. Later setup, probe and
execution costs will be retained with the measured case.

The dependency retry took 510.615301 s. The first policy probe failed on a
missing transformer configuration field (48.955294 s); the next failed on the
older shape-metadata key (9.221820 s). The explicit translation supplies disabled
transformer and construction-only optimizer defaults without changing original
values or trained weights. Observation keys come from the recorded `all_shapes`.
Robomimic also applies its own documented-in-code old encoder translation.

A subsequent probe completed Lift in 43 steps. The instrumented adapter bounds
normalized input explicitly and completed its reference/correction in 44 steps.
The [retained exploration](results/lift-exploration.json) contains two identical
44-step reference traces and failed 400-step regression/suppression traces.
These observations qualify this particular executable stack for the development
case; they do not reproduce the original model-zoo study or prove full state
capture for continuation.
