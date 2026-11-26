# Preparation correction before the completed matrix

The first native matrix failed before recording any row. The harness omitted
FeatureSpec.semantics, which the pinned upstream schema requires. This is our
preparation defect, not a failure of the proposed correction. The original
matrix.py, freeze.json, empty rows prefix and exact command error are retained.

matrix_v2.py adds explicit descriptions of the synthetic RGB test arrays and
state vector. Physical state units remain unbound and action inference is unused.
It binds this amendment and the acquired checkpoint metadata. The matrix,
expected decisions, candidate implementations and numerical comparisons do not
change. Freeze-v2 precedes the next run; native-01 is never overwritten.

Runtime preparation also retained three unsuccessful native imports. The final
CPU stack uses existing Torch 2.11.0 and an isolated overlay with Transformers
5.22.0, NumPy 2.2.6 and TorchVision 0.26.0, the pair documented by PyTorch at
https://pytorch.org/get-started/previous-versions/ . The old environments were
not modified. A read-only fallback supplies otherwise missing dependencies;
this is a declared composite research environment, not a hermetic installation
or a qualified full LeRobot deployment. Exact effective versions are frozen.
