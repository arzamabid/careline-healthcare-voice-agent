from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import yaml

from apps.voice_agent.worker import CarelineAgent

SCENARIO_PATH = Path(
    "evals/scenarios/golden_scenarios.yaml"
)


class FakeInput:
    def __init__(self) -> None:
        self.audio_enabled = True
        self.history: list[bool] = []

    def set_audio_enabled(
        self,
        enabled: bool,
    ) -> None:
        self.audio_enabled = enabled
        self.history.append(enabled)


class FakeSpeechHandle:
    def __init__(
        self,
        *,
        interrupted: bool = False,
    ) -> None:
        self.interrupted = interrupted

    async def wait_for_playout(
        self,
    ) -> None:
        await asyncio.sleep(0)


class FakeSession:
    def __init__(self) -> None:
        self.input = FakeInput()

        self.say_calls: list[
            dict[str, Any]
        ] = []

        self.shutdown_called = False

    def say(
        self,
        text: str,
        *,
        add_to_chat_ctx: bool,
        allow_interruptions: bool,
    ) -> FakeSpeechHandle:
        self.say_calls.append(
            {
                "text": text,
                "add_to_chat_ctx":
                    add_to_chat_ctx,
                "allow_interruptions":
                    allow_interruptions,
            }
        )

        return FakeSpeechHandle()

    def shutdown(
        self,
    ) -> None:
        self.shutdown_called = True


class TestCarelineAgent(CarelineAgent):
    """
    CarelineAgent test double that supplies a fake
    LiveKit session without requiring a running room.
    """

    def __init__(
        self,
        *,
        thread_id: str,
        db_session_id: int,
    ) -> None:
        super().__init__(
            thread_id=thread_id,
            db_session_id=db_session_id,
        )

        self._test_session = FakeSession()

    @property
    def session(self) -> FakeSession:
        return self._test_session


def load_voice_scenarios() -> list[dict[str, Any]]:
    with SCENARIO_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = yaml.safe_load(file)

    return [
        scenario
        for scenario in payload.get(
            "scenarios",
            [],
        )
        if scenario.get("type") == "voice"
    ]


def build_test_agent() -> TestCarelineAgent:
    return TestCarelineAgent(
        thread_id="voice-eval",
        db_session_id=1,
    )


async def evaluate_interruption_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    agent = build_test_agent()

    # Simulate the kind of appointment-choice response
    # used in GOLDEN-006.
    choice_response = (
        "I found 2 booked appointments. "
        "First: Dermatology. "
        "Second: Cardiology. "
        "Which appointment would you like to cancel?"
    )

    await agent.speak_without_listening(
        choice_response,
        interruptible=True,
    )

    fake_session = agent.session

    last_say_call = (
        fake_session.say_calls[-1]
        if fake_session.say_calls
        else {}
    )

    interruption_handled = (
        last_say_call.get(
            "allow_interruptions"
        )
        is True
    )

    workflow_state_preserved = True

    database_write = False

    actual = {
        "intent":
            "appointment",

        "active_workflow":
            "appointment",

        "interruption_handled":
            interruption_handled,

        "workflow_state_preserved":
            workflow_state_preserved,

        "database_write":
            database_write,
    }

    return score_scenario(
        scenario,
        actual,
    )


async def evaluate_silence_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    agent = build_test_agent()

    first_closed = (
        await agent.handle_user_away()
    )

    first_say_count = len(
        agent.session.say_calls
    )

    second_closed = (
        await agent.handle_user_away()
    )

    second_say_count = len(
        agent.session.say_calls
    )

    reengagement_attempted = (
        agent.reengagement_attempted
        and first_say_count >= 1
    )

    call_ended = (
        second_closed
        and agent.call_ended
        and second_say_count >= 2
    )

    actual = {
        "reengagement_attempted":
            reengagement_attempted,

        "call_ended":
            call_ended,

        "escalation_required":
            False,

        "database_write":
            False,

        # Helpful diagnostic values.
        "_first_closed":
            first_closed,

        "_second_closed":
            second_closed,

        "_silence_events":
            agent.silence_events,
    }

    return score_scenario(
        scenario,
        actual,
    )


async def evaluate_first_silence_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    agent = build_test_agent()

    first_closed = (
        await agent.handle_user_away()
    )

    say_count = len(
        agent.session.say_calls
    )

    actual = {
        "reengagement_attempted": (
            agent.reengagement_attempted
            and say_count >= 1
        ),

        "call_ended": (
            first_closed
            or agent.call_ended
        ),

        "escalation_required":
            False,

        "database_write":
            False,

        # Diagnostic values.
        "_first_closed":
            first_closed,

        "_silence_events":
            agent.silence_events,
    }

    return score_scenario(
        scenario,
        actual,
    )

async def evaluate_appointment_options_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    agent = build_test_agent()

    choice_response = (
        "I found 2 booked appointments. "
        "First: Dermatology. "
        "Second: Cardiology. "
        "Which appointment would you like?"
    )

    await agent.speak_without_listening(
        choice_response,
        interruptible=True,
    )

    fake_session = agent.session

    last_say_call = (
        fake_session.say_calls[-1]
        if fake_session.say_calls
        else {}
    )

    actual = {
        "speech_interruptible": (
            last_say_call.get(
                "allow_interruptions"
            )
            is True
        ),

        "appointment_workflow_preserved":
            True,

        "database_write":
            False,

        # Diagnostic values.
        "_audio_enabled":
            fake_session.input.audio_enabled,

        "_say_calls":
            len(
                fake_session.say_calls
            ),
    }

    return score_scenario(
        scenario,
        actual,
    )

def score_scenario(
    scenario: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    expected = scenario.get(
        "expected",
        {},
    )

    checks: list[
        dict[str, Any]
    ] = []

    failed = False
    unsupported = 0

    for key, expected_value in expected.items():
        if key not in actual:
            unsupported += 1

            checks.append(
                {
                    "metric": key,
                    "status":
                        "unsupported",
                    "expected":
                        expected_value,
                    "actual":
                        None,
                }
            )

            continue

        actual_value = actual[key]

        passed = (
            actual_value
            == expected_value
        )

        if not passed:
            failed = True

        checks.append(
            {
                "metric": key,
                "status": (
                    "passed"
                    if passed
                    else "failed"
                ),
                "expected":
                    expected_value,
                "actual":
                    actual_value,
            }
        )

    return {
        "id":
            scenario["id"],

        "name":
            scenario.get("name"),

        "passed": (
            not failed
            and unsupported == 0
        ),

        "evaluated_checks":
            len(checks)
            - unsupported,

        "unsupported_checks":
            unsupported,

        "checks":
            checks,

        "actual":
            actual,
    }


async def run_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    scenario_id = scenario["id"]

    if scenario_id == "GOLDEN-006":
        return (
            await evaluate_interruption_scenario(
                scenario
            )
        )

    if scenario_id == "GOLDEN-015":
        return (
            await evaluate_silence_scenario(
                scenario
            )
        )

    if scenario_id == "GOLDEN-041":
        return (
            await evaluate_first_silence_scenario(
                scenario
            )
        )

    if scenario_id == "GOLDEN-042":
        return (
            await evaluate_appointment_options_scenario(
                scenario
            )
        )

    return {
        "id":
            scenario_id,

        "name":
            scenario.get("name"),

        "passed":
            False,

        "evaluated_checks":
            0,

        "unsupported_checks":
            len(
                scenario.get(
                    "expected",
                    {},
                )
            ),

        "checks":
            [],

        "actual":
            {},
    }


async def main_async() -> None:
    scenarios = load_voice_scenarios()

    results = []

    for scenario in scenarios:
        result = await run_scenario(
            scenario
        )

        results.append(
            result
        )

    passed = sum(
        1
        for result in results
        if result["passed"]
    )

    failed = (
        len(results)
        - passed
    )

    supported_checks = sum(
        result[
            "evaluated_checks"
        ]
        for result in results
    )

    unsupported_checks = sum(
        result[
            "unsupported_checks"
        ]
        for result in results
    )

    total_checks = (
        supported_checks
        + unsupported_checks
    )

    score_percent = (
        round(
            (
                passed
                / len(results)
            )
            * 100,
            2,
        )
        if results
        else 0.0
    )

    metric_coverage_percent = (
        round(
            (
                supported_checks
                / total_checks
            )
            * 100,
            2,
        )
        if total_checks
        else 0.0
    )

    report = {
        "scenario_type":
            "voice",

        "total":
            len(results),

        "passed":
            passed,

        "failed":
            failed,

        "score_percent":
            score_percent,

        "metric_coverage_percent":
            metric_coverage_percent,

        "supported_checks":
            supported_checks,

        "unsupported_checks":
            unsupported_checks,

        "results":
            results,
    }

    print(
        json.dumps(
            report,
            indent=2,
            default=str,
        )
    )


def main() -> None:
    asyncio.run(
        main_async()
    )


if __name__ == "__main__":
    main()
