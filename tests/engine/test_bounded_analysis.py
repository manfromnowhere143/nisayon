import copy
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def analysis(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/experiments"))
    return importlib.import_module("analyze_bounded_comparison")


def test_equal_information_projection_keeps_remedy_hints_and_budgets(analysis):
    left = {"available_actions": {"execute": "rerun"}, "observations": ["failed"], "tokens": 10}
    right = copy.deepcopy(left)
    right["available_actions"]["audit"] = "additional B check"
    assert analysis.common_packet(left) == analysis.common_packet(right)
    right["hint"] = "use the known remedy"
    assert analysis.common_packet(left) != analysis.common_packet(right)
    del right["hint"]
    right["tokens"] = 11
    assert analysis.common_packet(left) != analysis.common_packet(right)


def test_model_command_is_nested_not_an_extra_phase_cost(analysis):
    parts = {"diagnostic_simulator_s": 3, "diagnostic_unpartitioned_s": 9, "check_s": 2}
    result = analysis.split_model_cost(parts, 8)
    assert sum(result.values()) == 14
    assert result["diagnostic_other_unpartitioned_s"] == 1
    assert parts["diagnostic_unpartitioned_s"] == 9
    with pytest.raises(ValueError, match="overlaps"):
        analysis.split_model_cost(parts, 11)
