from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

GOLDEN_FILE = Path(
    "evals/scenarios/golden_scenarios.yaml"
)


def load_scenarios() -> list[dict[str, Any]]:
    if not GOLDEN_FILE.exists():
        raise FileNotFoundError(
            f"Golden scenario file not found: "
            f"{GOLDEN_FILE}"
        )

    with GOLDEN_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    # Support:
    #
    # scenarios:
    #   - id: ...
    #   - id: ...
    #
    if isinstance(data, dict):
        scenarios = data.get(
            "scenarios"
        )

        if not isinstance(
            scenarios,
            list,
        ):
            raise TypeError(
                "Golden scenario YAML must contain "
                "a 'scenarios' list."
            )

        return scenarios

    # Also support a raw YAML list.
    if isinstance(data, list):
        return data

    raise TypeError(
        "Golden scenario file must contain "
        "either a list or a 'scenarios' list."
    )

def evaluate_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    scenario_id = scenario.get(
        "id"
    )

    turns = scenario.get(
        "turns"
    )

    expected_behavior = scenario.get(
        "expected_behavior"
    )

    expected = scenario.get(
        "expected"
    )

    scenario_type = scenario.get(
        "type"
    )

    checks = {
        "has_id":
            bool(scenario_id),

        "has_name":
            bool(
                scenario.get("name")
            ),

        "has_type":
            scenario_type
            in {
                "graph",
                "integration",
                "voice",
            },

        "has_turns":
            isinstance(turns, list)
            and len(turns) > 0,

        "has_expected_behavior":
            bool(expected_behavior),

        "has_machine_expectations":
            isinstance(expected, dict)
            and len(expected) > 0,
    }

    passed = all(
        checks.values()
    )

    return {
        "id":
            scenario_id,

        "type":
            scenario_type,

        "passed":
            passed,

        "checks":
            checks,
    }


def run_evaluations() -> dict[str, Any]:
    scenarios = load_scenarios()

    results = [
        evaluate_scenario(
            scenario
        )
        for scenario in scenarios
    ]

    passed = sum(
        1
        for result in results
        if result["passed"]
    )

    total = len(results)

    score = (
        round(
            passed / total * 100,
            2,
        )
        if total
        else 0.0
    )

    return {
        "total":
            total,

        "passed":
            passed,

        "failed":
            total - passed,

        "score_percent":
            score,

        "results":
            results,
    }


def main() -> None:
    report = run_evaluations()

    print(
        json.dumps(
            report,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()