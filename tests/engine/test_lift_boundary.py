import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("robomimic")
pytest.importorskip("robosuite")

from nisayon.engine.configuration import Deployment  # noqa: E402
from nisayon.engine.lift import LiftExecutor, candidate, execute_action  # noqa: E402


def test_unpinned_checkpoint_rejected_before_deserialization(tmp_path):
    path = tmp_path / "untrusted.pth"
    path.write_bytes(b"This is not the published checkpoint")
    with pytest.raises(ValueError, match="frozen checkpoint"):
        LiftExecutor(path)


def test_correction_undoes_transport_regression_without_mutating_policy_intention():
    intention = np.array([0.1, -0.2, 0.3, 0.4, -0.5, 0.6, 1.0])
    original = intention.copy()
    changed = execute_action(intention, candidate("regression"))
    corrected = execute_action(intention, candidate("correction"))
    assert changed[-1] == -original[-1]
    np.testing.assert_array_equal(corrected, original)
    np.testing.assert_array_equal(intention, original)


@pytest.mark.parametrize("action", [np.zeros(6), np.full(7, np.nan)])
def test_malformed_policy_actions_never_reach_the_simulator(action):
    with pytest.raises(ValueError, match="seven finite"):
        execute_action(action, candidate("reference"))


def test_axis_cycle_requires_the_inverse_at_the_actual_action_boundary():
    intended = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, -1.0])
    changed = Deployment(transport_translation_order=(1, 2, 0))
    corrected = Deployment(
        transport_translation_order=(1, 2, 0), repair_translation_order=(2, 0, 1)
    )
    np.testing.assert_array_equal(execute_action(intended, changed.record())[:3], [0.2, 0.3, 0.1])
    np.testing.assert_array_equal(execute_action(intended, corrected.record()), intended)
