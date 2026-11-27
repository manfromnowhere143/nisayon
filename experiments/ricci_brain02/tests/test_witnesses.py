import numpy as np
import pytest

from experiments.ricci_brain02.witnesses import maximum_violation


def test_independently_calculated_constraint_residuals():
    A = np.array([[1.0, 2.0], [0.0, 1.0]])
    lo, hi, tol = np.array([3.0, 0.0]), np.array([3.0, 2.0]), np.array([0.1, 0.2])
    assert maximum_violation(A, lo, hi, tol, np.array([1.0, 1.0])) == 0
    assert maximum_violation(A, lo, hi, tol, np.array([2.0, 1.0])) == 10


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_solution_is_not_a_witness(bad):
    with pytest.raises(ValueError):
        maximum_violation(np.eye(1), np.zeros(1), np.ones(1), np.ones(1), np.array([bad]))


def test_zero_tolerance_refused():
    with pytest.raises(ValueError):
        maximum_violation(np.eye(1), np.zeros(1), np.ones(1), np.zeros(1), np.zeros(1))
