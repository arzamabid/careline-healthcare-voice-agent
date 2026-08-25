# from typing import Any, TypedDict
#
#
# class CallState(TypedDict, total=False):
#     session_id: str
#
#     caller_text: str
#     conversation: list[dict[str, str]]
#
#     greeted: bool
#
#     verified_patient_id: int | None
#     verification_attempts: int
#     verification_fields: dict[str, Any]
#     identity_status: str | None
#     appointment_action: str | None
#     appointment_specialty: str | None
#     appointment_date: str | None
#     selected_appointment_id: int | None
#     confirmation_required: bool
#     confirmation_received: bool
#     confirmation_token: str | None
#
#     intake_index: int
#     intake_answers: dict[str, str]
#     intake_review_required: bool
#     intake_confirmed: bool
#
#     awaiting_more_help: bool
#
#     db_session_id: int | None
#
#     intent: str | None
#     active_workflow: str | None
#
#     collected_fields: dict[str, Any]
#     pending_confirmation: dict[str, Any] | None
#
#     tool_results: list[dict[str, Any]]
#
#     safety_flags: list[str]
#     escalation_required: bool
#
#     call_summary: dict[str, Any] | None
#
#     metrics: dict[str, Any]
#
#     current_node: str
#     response_text: str
#
#


from typing import Any, TypedDict


class CallState(TypedDict, total=False):
    # -------------------------
    # Session
    # -------------------------
    session_id: str

    # PostgreSQL CallSession ID.
    # Different from the LangGraph thread/session ID.
    db_session_id: int | None

    # -------------------------
    # Conversation
    # -------------------------
    caller_text: str
    conversation: list[dict[str, str]]
    greeted: bool
    response_text: str
    current_node: str

    # -------------------------
    # Identity
    # -------------------------
    verified_patient_id: int | None
    verification_attempts: int
    verification_fields: dict[str, Any]
    identity_status: str | None

    # -------------------------
    # Intent / workflow
    # -------------------------
    intent: str | None
    active_workflow: str | None
    collected_fields: dict[str, Any]

    # -------------------------
    # Confirmation
    # -------------------------
    pending_confirmation: dict[str, Any] | None
    confirmation_required: bool
    confirmation_received: bool
    confirmation_token: str | None

    # -------------------------
    # Appointment
    # -------------------------
    appointment_action: str | None
    appointment_specialty: str | None
    appointment_date: str | None
    selected_appointment_id: int | None

    # Clinic currently being discussed
    last_referenced_clinic: str | None

    original_request_text: str | None

    appointment_options: list[dict[str, Any]] | None
    appointment_stage: str | None

    # -------------------------
    # Intake
    # -------------------------
    intake_index: int
    intake_answers: dict[str, str]
    intake_review_required: bool
    intake_confirmed: bool

    # -------------------------
    # Safety / escalation
    # -------------------------
    safety_flags: list[str]
    escalation_required: bool

    # -------------------------
    # Tool results
    # -------------------------
    tool_results: list[dict[str, Any]]

    # -------------------------
    # Closing / finalization
    # -------------------------
    awaiting_more_help: bool
    call_ended: bool
    call_summary: dict[str, Any] | None

    # -------------------------
    # Metrics
    # -------------------------
    metrics: dict[str, Any]

