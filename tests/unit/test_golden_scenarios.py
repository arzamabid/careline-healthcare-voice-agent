from pathlib import Path

import yaml

SCENARIO_PATH = Path("evals/scenarios/golden_scenarios.yaml")


def test_fifty_golden_scenarios_exist() -> None:
    with SCENARIO_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    scenarios = data["scenarios"]

    assert len(scenarios) == 50


def test_golden_scenario_ids_are_unique() -> None:
    with SCENARIO_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    ids = [scenario["id"] for scenario in data["scenarios"]]

    assert len(ids) == len(set(ids))


def test_each_scenario_has_expected_behavior() -> None:
    with SCENARIO_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    for scenario in data["scenarios"]:
        assert scenario["name"]
        assert scenario["expected_behavior"]
