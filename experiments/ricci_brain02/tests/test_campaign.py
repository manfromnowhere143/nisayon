import json
from copy import deepcopy
from pathlib import Path

import pytest

from experiments.ricci_brain02.campaign import validate_definition


def definition():
    return json.loads((Path(__file__).parents[1] / "protocol.json").read_text())


def test_frozen_campaign_inside_bounds():
    validate_definition(definition())


@pytest.mark.parametrize("name", ["../escape", "/absolute", "", "two/names"])
def test_unsafe_episode_names_refused(name):
    value = definition()
    value["episodes"][0]["id"] = name
    with pytest.raises(ValueError, match="identity"):
        validate_definition(value)


@pytest.mark.parametrize("mutation", ["duplicate", "count", "nan", "bool", "duration", "bytes"])
def test_invalid_resource_limits_refused_before_execution(mutation):
    value = deepcopy(definition())
    if mutation == "duplicate":
        value["episodes"][1]["id"] = value["episodes"][0]["id"]
    elif mutation == "count":
        value["limits"]["max_episodes"] = 1
    elif mutation in ("nan", "bool"):
        value["episodes"][0]["config"]["timestep"] = float("nan") if mutation == "nan" else True
    elif mutation == "duration":
        value["episodes"][0]["config"]["duration"] = 1000
    else:
        value["limits"]["max_artifact_bytes"] = 1
    with pytest.raises(ValueError):
        validate_definition(value)
