from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agent.nodes.appointments import (
    appointment_router_node,
    confirm_appointment_action_node,
    execute_appointment_action_node,
    search_availability_node,
)
from agent.nodes.escalation import escalation_node
from agent.nodes.faq import faq_search_node
from agent.nodes.finalize import (
    closing_decision_node,
    finalize_call_node,
    wrap_up_node,
)
from agent.nodes.greeting import greeting_node
from agent.nodes.identity import identity_check_node
from agent.nodes.intake import (
    confirm_intake_node,
    previsit_intake_node,
    review_intake_node,
    store_intake_node,
)
from agent.nodes.intent import (
    _looks_like_faq,
    classify_intent_node,
)
from agent.nodes.safety import safety_gate_node
from agent.state import CallState
from observability.tracing import trace_node

# =========================================================
# ROUTING FUNCTIONS
# =========================================================


def route_from_start(
    state: CallState,
) -> str:
    """
    Every caller utterance after the greeting enters
    the safety gate first.
    """

    if not state.get(
        "greeted",
        False,
    ):
        return "greeting"

    return "safety"


def route_after_safety(
    state: CallState,
) -> str:

    # 1. Safety
    if state.get(
        "escalation_required",
        False,
    ):
        return "escalation"

    # 2. Closing
    if state.get(
        "awaiting_more_help",
        False,
    ):
        return "closing_decision"

    # 3. Incomplete identity
    identity_status = state.get(
        "identity_status"
    )

    if (
        state.get(
            "verified_patient_id"
        )
        is None
        and identity_status
        in {
            "needs_identifiers",
            "needs_phone_last4",
            "needs_member_id",
            "failed_retry",
        }
    ):
        return "identity"

    # 4. Explicit confirmation
    pending = (
        state.get(
            "pending_confirmation"
        )
        or {}
    )

    if state.get(
        "confirmation_required",
        False,
    ):
        if (
            pending.get("action")
            == "confirm_intake"
        ):
            return "intake_confirmation"

        return "appointment_confirmation"

    # =================================================
    # 5. FAQ INTERRUPTION
    # =================================================

    caller_text = state.get(
        "caller_text",
        "",
    )

    if _looks_like_faq(
        caller_text
    ):
        print(
            "FAQ INTERRUPTS WORKFLOW:",
            state.get(
                "active_workflow"
            ),
        )

        return "faq"

    # =================================================
    # 6. Existing workflows
    # =================================================

    active_workflow = state.get(
        "active_workflow"
    )

    if active_workflow == "appointment":
        return "appointment"

    if (
        active_workflow
        == "previsit_intake"
    ):
        if state.get(
            "intake_review_required",
            False,
        ):
            return "review_intake"

        return "intake"

    return "classify_intent"


def route_after_store_intake(
    state: CallState,
) -> str:
    """
    Only enter wrap-up if intake storage actually succeeded.
    """

    if state.get(
        "escalation_required",
        False,
    ):
        return "escalation"

    tool_results = (
        state.get(
            "tool_results",
            [],
        )
        or []
    )

    stored = any(
        result.get("tool")
        == "store_previsit_intake"
        and result.get("success")
        is True
        for result in tool_results
    )

    if stored:
        return "wrap_up"

    return "error"

def route_after_closing_decision(
    state: CallState,
) -> str:
    """
    Either finish the call or process another request.
    """

    if state.get(
        "call_ended",
        False,
    ):
        return "end"

    return "continue"


def route_after_identity(
    state: CallState,
) -> str:
    status = state.get(
        "identity_status"
    )

    if status == "failed_max":
        return "escalation"

    if status != "verified":
        return "wait"

    intent = state.get(
        "intent"
    )

    if intent == "appointment":
        return "appointment"

    if intent == "previsit_intake":
        return "intake"

    return "done"


def route_after_intent(
    state: CallState,
) -> str:
    intent = state.get(
        "intent"
    )

    # -----------------------------------------
    # Appointment
    # -----------------------------------------

    if intent == "appointment":
        if (
            state.get(
                "verified_patient_id"
            )
            is not None
        ):
            return "appointment"

        return "identity"

    # -----------------------------------------
    # Intake
    # -----------------------------------------

    if intent == "previsit_intake":
        if (
            state.get(
                "verified_patient_id"
            )
            is not None
        ):
            return "intake"

        return "identity"

    # -----------------------------------------
    # FAQ
    # -----------------------------------------

    if intent == "faq":
        return "faq"

    return "done"


# def route_after_appointment_router(
#     state: CallState,
# ) -> str:
#     action = state.get(
#         "appointment_action"
#     )
#
#     # For now, cancellation and rescheduling are handled
#     # by the appointment router itself and should wait
#     # for the next caller turn.
#     #
#     # Do NOT return "cancel" or "reschedule" until
#     # dedicated graph nodes exist.
#     if action in {
#         "cancel",
#         "reschedule",
#     }:
#         return "wait"
#
#     if action != "book":
#         return "wait"
#
#     if state.get(
#         "appointment_specialty"
#     ) is None:
#         return "wait"
#
#     if state.get(
#         "appointment_date"
#     ) is None:
#         return "wait"
#
#     return "search"


def route_after_appointment_router(
    state: CallState,
) -> str:
    action = state.get(
        "appointment_action"
    )

    # -----------------------------------------
    # Cancel
    #
    # appointment_router itself finds the
    # booked appointment and asks confirmation.
    # -----------------------------------------

    if action == "cancel":
        return "wait"

    # -----------------------------------------
    # Reschedule
    #
    # Once specialty + new date + old
    # appointment are known, search for a new
    # available slot.
    # -----------------------------------------

    if action == "reschedule":
        if (
            state.get(
                "appointment_specialty"
            )
            is None
        ):
            return "wait"

        if (
            state.get(
                "appointment_date"
            )
            is None
        ):
            return "wait"

        if (
            state.get(
                "selected_appointment_id"
            )
            is None
        ):
            return "wait"

        return "search"

    # -----------------------------------------
    # Book
    # -----------------------------------------

    if action != "book":
        return "wait"

    if (
        state.get(
            "appointment_specialty"
        )
        is None
    ):
        return "wait"

    if (
        state.get(
            "appointment_date"
        )
        is None
    ):
        return "wait"

    return "search"


def route_after_confirmation(
    state: CallState,
) -> str:
    if state.get(
        "confirmation_received",
        False,
    ):
        return "execute"

    return "wait"


def route_after_intake(
    state: CallState,
) -> str:
    if state.get(
        "intake_review_required",
        False,
    ):
        return "review"

    return "wait"


def route_after_intake_confirmation(
    state: CallState,
) -> str:
    if state.get(
        "intake_confirmed",
        False,
    ):
        return "store_intake"

    if state.get(
        "confirmation_required",
        False,
    ):
        return "wait"

    return "done"

# =========================================================
# GRAPH
# =========================================================


def build_graph():
    builder = StateGraph(
        CallState
    )

    # =====================================================
    # NODES
    # =====================================================

    builder.add_node(
        "greeting",
        trace_node(
            "greeting",
            greeting_node,
        ),
    )

    builder.add_node(
        "safety_gate",
        trace_node(
            "safety_gate",
            safety_gate_node,
        ),
    )

    builder.add_node(
        "classify_intent",
        trace_node(
            "classify_intent",
            classify_intent_node,
        ),
    )

    builder.add_node(
        "identity_check",
        trace_node(
            "identity_check",
            identity_check_node,
        ),
    )

    builder.add_node(
        "escalation",
        trace_node(
            "escalation",
            escalation_node,
        ),
    )

    # -------------------------
    # Appointment
    # -------------------------

    builder.add_node(
        "appointment_router",
        trace_node(
            "appointment_router",
            appointment_router_node,
        ),
    )

    builder.add_node(
        "search_availability",
        trace_node(
            "search_availability",
            search_availability_node,
        ),
    )

    builder.add_node(
        "confirm_appointment_action",
        trace_node(
            "confirm_appointment_action",
            confirm_appointment_action_node,
        ),
    )

    builder.add_node(
        "execute_appointment_action",
        trace_node(
            "execute_appointment_action",
            execute_appointment_action_node,
        ),
    )

    # -------------------------
    # FAQ
    # -------------------------

    builder.add_node(
        "faq_search",
        trace_node(
            "faq_search",
            faq_search_node,
        ),
    )

    # -------------------------
    # Intake
    # -------------------------

    builder.add_node(
        "previsit_intake",
        trace_node(
            "previsit_intake",
            previsit_intake_node,
        ),
    )

    builder.add_node(
        "review_intake",
        trace_node(
            "review_intake",
            review_intake_node,
        ),
    )

    builder.add_node(
        "confirm_intake",
        trace_node(
            "confirm_intake",
            confirm_intake_node,
        ),
    )

    builder.add_node(
        "store_intake",
        trace_node(
            "store_intake",
            store_intake_node,
        ),
    )

    # -------------------------
    # Closing / finalization
    # -------------------------

    builder.add_node(
        "wrap_up",
        trace_node(
            "wrap_up",
            wrap_up_node,
        ),
    )

    builder.add_node(
        "closing_decision",
        trace_node(
            "closing_decision",
            closing_decision_node,
        ),
    )

    builder.add_node(
        "finalize_call",
        trace_node(
            "finalize_call",
            finalize_call_node,
        ),
    )

    # =====================================================
    # START
    # =====================================================

    builder.add_conditional_edges(
        START,
        route_from_start,
        {
            "greeting": "greeting",
            "safety": "safety_gate",
        },
    )


    builder.add_edge(
        "greeting",
        "safety_gate",
    )

    # =====================================================
    # SAFETY
    # =====================================================

    builder.add_conditional_edges(
        "safety_gate",
        route_after_safety,
        {

            "escalation":
                "escalation",

            "closing_decision":
                "closing_decision",

            "identity": "identity_check",

            "faq": "faq_search",

            "classify_intent":
                "classify_intent",

            "appointment":
                "appointment_router",

            "appointment_confirmation":
                "confirm_appointment_action",

            "intake":
                "previsit_intake",

            "review_intake":
                "review_intake",

            "intake_confirmation":
                "confirm_intake",
        },
    )

    builder.add_edge(
        "escalation",
        END,
    )

    # =====================================================
    # CLOSING
    # =====================================================

    builder.add_conditional_edges(
        "closing_decision",
        route_after_closing_decision,
        {
            # A closing response gets finalized.
            "end": "finalize_call",

            # Another request gets reclassified.
            "continue": "classify_intent",
        },
    )

    builder.add_edge(
        "finalize_call",
        END,
    )

    # =====================================================
    # INTENT
    # =====================================================

    builder.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "identity":
                "identity_check",

            "appointment":
                "appointment_router",

            "intake":
                "previsit_intake",

            "faq":
                "faq_search",

            "done":
                END,
        },
    )

    # =====================================================
    # IDENTITY
    # =====================================================

    builder.add_conditional_edges(
        "identity_check",
        route_after_identity,
        {
            "appointment":
                "appointment_router",

            "intake":
                "previsit_intake",

            "escalation":
                "escalation",

            "wait":
                END,

            "done":
                END,
        },
    )

    # =====================================================
    # APPOINTMENT
    # =====================================================

    builder.add_conditional_edges(
        "appointment_router",
        route_after_appointment_router,
        {
            "search":
                "search_availability",

            "wait":
                END,
        },
    )

    # Search shows the available appointment and
    # requests explicit caller confirmation.
    builder.add_edge(
        "search_availability",
        END,
    )

    builder.add_conditional_edges(
        "confirm_appointment_action",
        route_after_confirmation,
        {
            "execute":
                "execute_appointment_action",

            "wait":
                END,
        },
    )

    # Database mutation happens first.
    # Only after success do we enter wrap-up.
    builder.add_edge(
        "execute_appointment_action",
        "wrap_up",
    )

    # =====================================================
    # FAQ
    # =====================================================

    builder.add_edge(
        "faq_search",
        END,
    )

    # =====================================================
    # PRE-VISIT INTAKE
    # =====================================================

    builder.add_conditional_edges(
        "previsit_intake",
        route_after_intake,
        {
            "review":
                "review_intake",

            "wait":
                END,
        },
    )

    # Review asks for confirmation and waits for
    # another caller turn.
    builder.add_edge(
        "review_intake",
        END,
    )

    builder.add_conditional_edges(
        "confirm_intake",
        route_after_intake_confirmation,
        {
            "store_intake":
                "store_intake",

            "wait":
                END,

            "done":
                END,
        },
    )

    # Save first, then say that the action completed.
    builder.add_conditional_edges(
        "store_intake",
        route_after_store_intake,
        {
            "wrap_up":
                "wrap_up",

            "escalation":
                "escalation",

            "error":
                END,
        },
    )

    # =====================================================
    # WRAP-UP
    # =====================================================

    # wrap_up asks:
    #
    # "Is there anything else I can help you with?"
    #
    # Then waits for another caller turn.
    builder.add_edge(
        "wrap_up",
        END,
    )

    # =====================================================
    # CHECKPOINTER
    # =====================================================

    checkpointer = InMemorySaver()

    return builder.compile(
        checkpointer=checkpointer,
    )


graph = build_graph()