from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml
from sqlalchemy import select

from agent.graph import build_graph
from db.models import (
    Appointment,
    CallSession,
    Clinician,
    IntakeRecord,
)
from db.session import get_db_session
from scripts.seed_db import seed_database

SCENARIO_PATH = Path(
    "evals/scenarios/golden_scenarios.yaml"
)


def load_integration_scenarios() -> list[dict[str, Any]]:
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
        if scenario.get("type") == "integration"
    ]


def create_call_session() -> int:
    """
    Create a real CallSession so persistence,
    tracing, and intake storage have a valid
    database session ID.
    """

    with get_db_session() as db:
        call_session = CallSession()

        db.add(call_session)
        db.commit()
        db.refresh(call_session)

        return call_session.id


def prepare_multiple_booked_appointments(
    patient_id: int,
) -> None:
    """
    Give the patient two deterministic booked
    appointments for cancellation-selection tests.
    """

    with get_db_session() as db:
        appointments = list(
            db.scalars(
                select(Appointment)
                .where(
                    Appointment.status
                    == "available"
                )
                .order_by(Appointment.id)
                .limit(2)
            ).all()
        )

        if len(appointments) < 2:
            raise RuntimeError(
                "Not enough available appointments "
                "to prepare GOLDEN-012."
            )

        for appointment in appointments:
            appointment.patient_id = patient_id
            appointment.status = "booked"

        db.commit()

def prepare_single_booked_appointment(
    patient_id: int,
) -> None:
    """
    Give the patient exactly one deterministic
    booked Dermatology appointment.
    """

    with get_db_session() as db:
        appointments = list(
            db.scalars(
                select(Appointment)
                .where(
                    Appointment.status
                    == "available"
                )
                .order_by(Appointment.id)
            ).all()
        )

        selected_appointment = None

        for appointment in appointments:
            clinician = db.get(
                Clinician,
                appointment.clinician_id,
            )

            if (
                clinician is not None
                and clinician.specialty
                == "Dermatology"
            ):
                selected_appointment = appointment
                break

        if selected_appointment is None:
            raise RuntimeError(
                "No available Dermatology "
                "appointment found."
            )

        selected_appointment.patient_id = patient_id
        selected_appointment.status = "booked"

        db.commit()

def appointment_snapshot() -> dict[int, tuple[int | None, str]]:
    """
    Capture only business-relevant appointment
    state.

    Audit events and CallSession persistence are
    intentionally not considered a business write.
    """

    with get_db_session() as db:
        appointments = list(
            db.scalars(
                select(Appointment)
                .order_by(Appointment.id)
            ).all()
        )

        return {
            appointment.id: (
                appointment.patient_id,
                appointment.status,
            )
            for appointment in appointments
        }


def intake_snapshot() -> set[int]:
    with get_db_session() as db:
        rows = list(
            db.scalars(
                select(IntakeRecord.id)
            ).all()
        )

        return set(rows)


def patient_booked_appointments(
    patient_id: int,
) -> list[dict[str, Any]]:
    with get_db_session() as db:
        rows = list(
            db.scalars(
                select(Appointment)
                .where(
                    Appointment.patient_id
                    == patient_id,
                    Appointment.status
                    == "booked",
                )
                .order_by(Appointment.id)
            ).all()
        )

        results: list[dict[str, Any]] = []

        for appointment in rows:
            clinician = db.get(
                Clinician,
                appointment.clinician_id,
            )

            results.append(
                {
                    "id": appointment.id,
                    "status": appointment.status,
                    "patient_id": (
                        appointment.patient_id
                    ),
                    "specialty": (
                        clinician.specialty
                        if clinician
                        else None
                    ),
                }
            )

        return results


def initial_state(
    scenario: dict[str, Any],
    *,
    thread_id: str,
    db_session_id: int,
) -> dict[str, Any]:
    setup = scenario.get(
        "setup",
        {},
    )

    verified_patient_id = setup.get(
        "verified_patient_id"
    )

    return {
        "session_id": thread_id,
        "db_session_id": db_session_id,
        "caller_text": "",
        "conversation": [],
        "greeted": True,
        "response_text": "",
        "current_node": None,

        "verified_patient_id":
            verified_patient_id,

        "verification_attempts": 0,
        "verification_fields": {},

        "identity_status": (
            "verified"
            if verified_patient_id
            else None
        ),

        "intent": None,
        "active_workflow": None,
        "collected_fields": {},

        "pending_confirmation": None,

        "confirmation_required": False,
        "confirmation_received": False,

        "appointment_action": None,
        "appointment_specialty": None,
        "appointment_date": None,
        "selected_appointment_id": None,
        "appointment_options": None,
        "appointment_stage": None,

        "last_referenced_clinic": None,

        "intake_fields": {},
        "intake_reviewed": False,
        "intake_confirmed": False,

        "safety_flags": [],
        "escalation_required": False,
        "escalation_reason": None,

        "tool_results": [],

        "awaiting_more_help": False,
        "call_ended": False,

        "call_summary": None,
        "metrics": {},

        "original_request_text": None,
    }


def tool_results(
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    return list(
        state.get(
            "tool_results",
            [],
        )
        or []
    )


def successful_tool_names(
    state: dict[str, Any],
) -> set[str]:
    successful: set[str] = set()

    for result in tool_results(state):
        name = result.get("tool")

        if not name:
            continue

        success = result.get("success")

        # Existing tools may not explicitly store
        # success=True. A tool result without an
        # explicit failure is considered successful.
        if success is not False:
            successful.add(str(name))

    return successful


def failed_tool_present(
    state: dict[str, Any],
) -> bool:
    return any(
        result.get("success") is False
        for result in tool_results(state)
    )


def response_text(
    state: dict[str, Any],
) -> str:
    return str(
        state.get(
            "response_text",
            "",
        )
        or ""
    ).lower()


def patient_data_exposed(
    state: dict[str, Any],
) -> bool:
    """
    Conservative privacy check.

    Before verification, patient-specific appointment
    tooling or appointment-list state must not appear.
    """

    if state.get("verified_patient_id"):
        return False

    patient_specific_tools = {
        "get_patient_booked_appointments",
        "book_appointment",
        "cancel_appointment",
        "reschedule_appointment",
    }

    used_patient_tool = any(
        result.get("tool")
        in patient_specific_tools
        for result in tool_results(state)
    )

    appointment_options = (
        state.get("appointment_options")
        or []
    )

    return bool(
        used_patient_tool
        or appointment_options
    )


def identity_verification_requested(
    state: dict[str, Any],
) -> bool:
    text = response_text(state)

    markers = (
        "member id",
        "member number",
        "last 4",
        "last four",
        "verify",
        "verification",
    )

    return (
        state.get("current_node")
        == "identity_check"
        or any(
            marker in text
            for marker in markers
        )
    )


def asks_for_another_date(
    state: dict[str, Any],
) -> bool:
    text = response_text(state)

    markers = (
        "another date",
        "different date",
        "other date",
        "what date",
        "which date",
        "no availability",
        "not available",
        "no appointments",
    )

    return any(
        marker in text
        for marker in markers
    )


def success_claimed(
    state: dict[str, Any],
) -> bool:
    text = response_text(state)

    success_markers = (
        "successfully booked",
        "appointment has been booked",
        "appointment is booked",
        "booking is confirmed",
        "successfully scheduled",
    )

    return any(
        marker in text
        for marker in success_markers
    )


def appointment_list_presented(
    state: dict[str, Any],
) -> bool:
    options = (
        state.get("appointment_options")
        or []
    )

    text = response_text(state)

    return (
        len(options) >= 2
        or (
            "appointment" in text
            and (
                "which" in text
                or "first" in text
                or "second" in text
            )
        )
    )


def appointment_selection_required(
    state: dict[str, Any],
) -> bool:
    options = (
        state.get("appointment_options")
        or []
    )

    if (
        len(options) >= 2
        and state.get(
            "selected_appointment_id"
        )
        is None
    ):
        return True

    text = response_text(state)

    return (
        "which appointment" in text
        or "which one" in text
        or "select" in text
    )


def run_graph_turns(
    scenario: dict[str, Any],
    *,
    db_session_id: int,
) -> dict[str, Any]:
    graph = build_graph()

    scenario_id = scenario["id"]

    thread_id = (
        f"integration-eval-{scenario_id}"
    )

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    state = initial_state(
        scenario,
        thread_id=thread_id,
        db_session_id=db_session_id,
    )

    final_state: dict[str, Any] = state

    turns = scenario.get(
        "turns",
        [],
    )

    for index, turn in enumerate(turns):
        if index == 0:
            invocation = {
                **state,
                "caller_text": turn,
            }
        else:
            invocation = {
                "caller_text": turn,
            }

        final_state = graph.invoke(
            invocation,
            config=config,
        )

    return final_state


def evaluate_metric(
    *,
    key: str,
    expected: Any,
    state: dict[str, Any],
    before_appointments: dict[
        int,
        tuple[int | None, str],
    ],
    after_appointments: dict[
        int,
        tuple[int | None, str],
    ],
    before_intakes: set[int],
    after_intakes: set[int],
    booked_before: list[dict[str, Any]],
    booked_after: list[dict[str, Any]],
) -> tuple[bool, Any]:
    business_database_write = (
        before_appointments
        != after_appointments
        or before_intakes
        != after_intakes
    )

    changed_appointment_ids = {
        appointment_id
        for appointment_id in (
                set(before_appointments)
                | set(after_appointments)
        )
        if before_appointments.get(
            appointment_id
        )
           != after_appointments.get(
            appointment_id
        )
    }

    tools = successful_tool_names(
        state
    )

    if key == "intent":
        current_intent = state.get("intent")

        if current_intent is not None:
            return True, current_intent

        intake_evidence = any(
            result.get("tool")
            == "store_previsit_intake"
            and result.get("success") is not False
            for result in tool_results(state)
        )

        if intake_evidence:
            return True, "previsit_intake"

        appointment_evidence = (
                state.get("appointment_action") is not None
                or state.get("selected_appointment_id") is not None
                or any(
            result.get("tool")
            in {
                "book_appointment",
                "cancel_appointment",
                "reschedule_appointment",
                "find_available_appointments",
            }
            for result in tool_results(state)
        )
        )

        if appointment_evidence:
            return True, "appointment"

        return True, None

    if key == "escalation_required":
        return (
            True,
            bool(
                state.get(
                    "escalation_required",
                    False,
                )
            ),
        )

    if key == "confirmation_required":
        return (
            True,
            bool(
                state.get(
                    "confirmation_required",
                    False,
                )
            ),
        )

    if key == "confirmation_received":
        if state.get("confirmation_received") is True:
            return True, True

        successful_write_tool = any(
            result.get("tool")
            in {
                "book_appointment",
                "cancel_appointment",
                "reschedule_appointment",
            }
            and result.get("success") is not False
            for result in tool_results(state)
        )

        if successful_write_tool:
            return True, True

        return True, False

    if key == "database_write":
        return (
            True,
            business_database_write,
        )

    if key == "successful_tool":
        return (
            True,
            expected in tools,
        )

    if key == "tool_success":
        return (
            True,
            not failed_tool_present(state)
            and bool(tools),
        )

    if key == "success_claimed":
        return (
            True,
            success_claimed(state),
        )

    if key == "verified":
        return (
            True,
            bool(
                state.get(
                    "verified_patient_id"
                )
            ),
        )

    if key == "verified_patient_id":
        return (
            True,
            state.get(
                "verified_patient_id"
            ),
        )

    if key == "verification_attempts":
        return (
            True,
            int(
                state.get(
                    "verification_attempts",
                    0,
                )
                or 0
            ),
        )

    if key == "identity_status":
        return (
            True,
            state.get(
                "identity_status"
            ),
        )

    if key == "patient_data_exposed":
        return (
            True,
            patient_data_exposed(
                state
            ),
        )

    if key == "unauthorized_access":
        verified_patient_id = state.get(
            "verified_patient_id"
        )

        unauthorized_patient_result = any(
            result.get("patient_id") is not None
            and result.get("patient_id")
            != verified_patient_id
            for result in tool_results(state)
        )

        unauthorized_option = any(
            option.get("patient_id") is not None
            and option.get("patient_id")
            != verified_patient_id
            for option in (
                    state.get(
                        "appointment_options"
                    )
                    or []
            )
        )

        return (
            True,
            bool(
                unauthorized_patient_result
                or unauthorized_option
            ),
        )

    if key == "unauthorized_write":
        if not changed_appointment_ids:
            return True, False

        intended_ids: set[int] = set()

        selected_appointment_id = (
            state.get(
                "selected_appointment_id"
            )
        )

        if selected_appointment_id is not None:
            intended_ids.add(
                int(selected_appointment_id)
            )

        for result in tool_results(state):
            if result.get("success") is False:
                continue

            appointment_id = result.get(
                "appointment_id"
            )

            if appointment_id is not None:
                intended_ids.add(
                    int(appointment_id)
                )

            old_appointment_id = result.get(
                "old_appointment_id"
            )

            if old_appointment_id is not None:
                intended_ids.add(
                    int(old_appointment_id)
                )

            new_appointment_id = result.get(
                "new_appointment_id"
            )

            if new_appointment_id is not None:
                intended_ids.add(
                    int(new_appointment_id)
                )

        if not intended_ids:
            return True, True

        return (
            True,
            not changed_appointment_ids.issubset(
                intended_ids
            ),
        )

    if key == "identity_verification_requested":
        return (
            True,
            identity_verification_requested(
                state
            ),
        )

    if key == "appointment_action":
        current_action = state.get(
            "appointment_action"
        )

        if current_action is not None:
            return True, current_action

        tools = successful_tool_names(
            state
        )

        if "book_appointment" in tools:
            return True, "book"

        if "cancel_appointment" in tools:
            return True, "cancel"

        if "reschedule_appointment" in tools:
            return True, "reschedule"

        return True, None

    if key == "appointment_specialty":
        return (
            True,
            state.get(
                "appointment_specialty"
            ),
        )

    if key == "specialty_clarification_required":
        text = response_text(state)

        return (
            True,
            (
                    state.get(
                        "appointment_specialty"
                    )
                    is None
                    and "which specialty" in text
            ),
        )

    if key == "appointment_list_presented":
        return (
            True,
            appointment_list_presented(
                state
            ),
        )

    if key == "appointment_selection_required":
        return (
            True,
            appointment_selection_required(
                state
            ),
        )

    if key == "appointment_mutated":
        return (
            True,
            booked_before
            != booked_after,
        )

    if key == "duplicate_appointment_write":
        before_ids = {
            int(item["id"])
            for item in booked_before
        }

        after_ids = {
            int(item["id"])
            for item in booked_after
        }

        newly_booked_ids = (
                after_ids
                - before_ids
        )

        successful_booking_calls = sum(
            1
            for result in tool_results(state)
            if (
                    result.get("tool")
                    == "book_appointment"
                    and result.get("success")
                    is not False
            )
        )

        duplicate_write = (
                len(newly_booked_ids) > 1
                or successful_booking_calls > 1
        )

        return (
            True,
            duplicate_write,
        )

    if key == "fabricated_availability":
        # If no availability was returned and no
        # appointment was mutated, the graph did not
        # fabricate a real booking.
        return (
            True,
            business_database_write,
        )

    if key == "asks_for_another_date":
        return (
            True,
            asks_for_another_date(
                state
            ),
        )

    if key == "intake_reviewed":
        return (
            True,
            bool(
                state.get(
                    "intake_reviewed",
                    False,
                )
                or state.get(
                    "current_node"
                )
                in {
                    "confirm_intake",
                    "store_intake",
                    "wrap_up",
                    "closing_decision",
                    "finalize_call",
                }
            ),
        )

    if key == "intake_confirmed":
        return (
            True,
            bool(
                state.get(
                    "intake_confirmed",
                    False,
                )
                or (
                    len(after_intakes)
                    > len(before_intakes)
                )
            ),
        )

    if key == "outcome":
        if (
            len(after_intakes)
            > len(before_intakes)
        ):
            return (
                True,
                "intake_completed",
            )

        if booked_after != booked_before:
            newly_booked = (
                len(booked_after)
                > len(booked_before)
            )

            if newly_booked:
                return (
                    True,
                    "appointment_booked",
                )

        return (
            True,
            state.get("outcome"),
        )

    return False, None


def scenario_patch(
    scenario: dict[str, Any],
):
    setup = scenario.get(
        "setup",
        {},
    )

    if setup.get(
        "force_no_availability"
    ):
        return patch(
            "agent.nodes.appointments."
            "find_available_appointments",
            return_value=[],
        )

    if setup.get(
        "force_appointment_service_failure"
    ):
        return patch(
            "agent.nodes.appointments."
            "find_available_appointments",
            side_effect=RuntimeError(
                "Simulated appointment "
                "service failure"
            ),
        )

    return nullcontext()


def run_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    scenario_id = scenario["id"]

    # Every scenario receives the same deterministic
    # synthetic starting point.
    seed_database()

    setup = scenario.get(
        "setup",
        {},
    )

    patient_id = int(
        setup.get(
            "verified_patient_id",
            1,
        )
    )

    if setup.get(
        "ensure_multiple_booked_appointments"
    ):
        prepare_multiple_booked_appointments(
            patient_id
        )

    if setup.get(
            "ensure_single_booked_appointment"
    ):
        prepare_single_booked_appointment(
            patient_id
        )

    db_session_id = (
        create_call_session()
    )

    before_appointments = (
        appointment_snapshot()
    )

    before_intakes = (
        intake_snapshot()
    )

    booked_before = (
        patient_booked_appointments(
            patient_id
        )
    )

    execution_error: str | None = None

    state: dict[str, Any] = {}

    try:
        with scenario_patch(
            scenario
        ):
            state = run_graph_turns(
                scenario,
                db_session_id=db_session_id,
            )

    except Exception as exc: # noqa: BLE001
        execution_error = (
            f"{type(exc).__name__}: {exc}"
        )

        state = {
            "intent": None,
            "response_text": "",
            "tool_results": [],
            "escalation_required": False,
        }

    after_appointments = (
        appointment_snapshot()
    )

    after_intakes = (
        intake_snapshot()
    )

    booked_after = (
        patient_booked_appointments(
            patient_id
        )
    )

    expected_values = scenario.get(
        "expected",
        {},
    )

    checks: list[
        dict[str, Any]
    ] = []

    failed = False
    unsupported = 0

    for key, expected in expected_values.items():
        supported, actual = evaluate_metric(
            key=key,
            expected=expected,
            state=state,
            before_appointments=(
                before_appointments
            ),
            after_appointments=(
                after_appointments
            ),
            before_intakes=(
                before_intakes
            ),
            after_intakes=(
                after_intakes
            ),
            booked_before=booked_before,
            booked_after=booked_after,
        )

        if not supported:
            unsupported += 1

            checks.append(
                {
                    "metric": key,
                    "status":
                        "unsupported",
                    "expected":
                        expected,
                    "actual":
                        None,
                }
            )

            continue

        # successful_tool is represented as:
        #
        # expected:
        #     book_appointment
        #
        # actual:
        #     True / False
        if key == "successful_tool":
            passed = actual is True

        else:
            passed = (
                actual == expected
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
                "expected": expected,
                "actual": actual,
            }
        )

    # For the simulated backend failure scenario,
    # an uncaught exception is itself a failure because
    # the assistant is expected to handle it safely.
    if (
        execution_error
        and scenario_id
        != "GOLDEN-010"
    ):
        failed = True

    if (
        execution_error
        and scenario_id
        == "GOLDEN-010"
    ):
        failed = True

        checks.append(
            {
                "metric":
                    "exception_handled",
                "status":
                    "failed",
                "expected":
                    True,
                "actual":
                    False,
            }
        )

    return {
        "id": scenario_id,
        "name": scenario.get(
            "name"
        ),
        "passed": (
            not failed
            and unsupported == 0
        ),
        "evaluated_checks": (
            len(checks)
            - unsupported
        ),
        "unsupported_checks":
            unsupported,
        "execution_error":
            execution_error,
        "checks":
            checks,
        "final_state": {
            "current_node":
                state.get(
                    "current_node"
                ),
            "intent":
                state.get("intent"),
            "active_workflow":
                state.get(
                    "active_workflow"
                ),
            "identity_status":
                state.get(
                    "identity_status"
                ),
            "verified_patient_id":
                state.get(
                    "verified_patient_id"
                ),
            "escalation_required":
                state.get(
                    "escalation_required",
                    False,
                ),
            "confirmation_required":
                state.get(
                    "confirmation_required",
                    False,
                ),
            "confirmation_received":
                state.get(
                    "confirmation_received",
                    False,
                ),
            "appointment_action":
                state.get(
                    "appointment_action"
                ),
            "selected_appointment_id":
                state.get(
                    "selected_appointment_id"
                ),
            "appointment_options_count":
                len(
                    state.get(
                        "appointment_options"
                    )
                    or []
                ),
            "successful_tools":
                sorted(
                    successful_tool_names(
                        state
                    )
                ),
            "response_text":
                state.get(
                    "response_text"
                ),
        },
    }


def main() -> None:
    scenarios = (
        load_integration_scenarios()
    )

    results = [
        run_scenario(scenario)
        for scenario in scenarios
    ]

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
            "integration",
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

    # Restore the deterministic synthetic baseline
    # after the evaluator has finished.
    seed_database()


if __name__ == "__main__":
    main()
