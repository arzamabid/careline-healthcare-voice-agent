from agent.state import CallState
from apps.api.services.faq import (
    get_clinic_information,
    search_approved_faq,
)
from db.session import get_db_session


def _build_faq_response(
    answer: str,
    faq_interrupted_intake: bool,
) -> tuple[str, str | None, bool]:
    """
    Build the correct conversational response.

    Returns:
        response_text
        active_workflow
        awaiting_more_help
    """

    if faq_interrupted_intake:
        return (
            (
                f"{answer} "
                "Now, returning to your pre-visit intake, "
                "let's continue where we left off."
            ),
            "previsit_intake",
            False,
        )

    return (
        (
            f"{answer} "
            "Is there anything else "
            "I can help you with?"
        ),
        None,
        True,
    )


def faq_search_node(
    state: CallState,
) -> CallState:
    # -------------------------------------------------
    # Preserve workflow if FAQ interrupted one.
    # -------------------------------------------------

    interrupted_workflow = state.get(
        "active_workflow"
    )

    faq_interrupted_workflow = (
        interrupted_workflow
        in {
            "appointment",
            "previsit_intake",
        }
    )

    preserved_workflow = (
        interrupted_workflow
        if faq_interrupted_workflow
        else None
    )

    caller_text = state.get(
        "caller_text",
        "",
    )

    # -------------------------------------------------
    # Determine whether FAQ interrupted intake.
    # -------------------------------------------------

    faq_interrupted_intake = (
        interrupted_workflow
        == "previsit_intake"
    )

    # Normal FAQ:
    #     intent = faq
    #
    # FAQ during another workflow:
    #     preserve original workflow intent.
    faq_intent = (
        state.get("intent")
        if faq_interrupted_workflow
        else "faq"
    )

    print(
        "FAQ QUERY:",
        repr(caller_text),
    )

    print(
        "FAQ INTERRUPTED INTAKE:",
        faq_interrupted_intake,
    )

    print(
        "FAQ RETURN INTENT:",
        faq_intent,
    )

    appointment_id = state.get(
        "selected_appointment_id"
    )

    patient_id = state.get(
        "verified_patient_id"
    )

    last_referenced_clinic = state.get(
        "last_referenced_clinic"
    )

    print(
        "FAQ APPOINTMENT ID:",
        appointment_id,
    )

    print(
        "FAQ PATIENT ID:",
        patient_id,
    )

    print(
        "LAST REFERENCED CLINIC:",
        last_referenced_clinic,
    )

    with get_db_session() as db:

        # =================================================
        # 1. STRUCTURED CLINIC INFORMATION
        # =================================================

        clinic_result = get_clinic_information(
            db=db,
            query=caller_text,
            appointment_id=appointment_id,
            patient_id=patient_id,
            last_referenced_clinic=(
                last_referenced_clinic
            ),
        )

        # Only use structured clinic information when
        # the caller is actually asking for clinic
        # location/hours information.
        clinic_info_terms = {
            "opening",
            "open",
            "hours",
            "closing",
            "close",
            "closed",
            "address",
            "location",
            "located",
            "where is",
        }

        clinic_info_requested = any(
            term in caller_text.lower()
            for term in clinic_info_terms
        )

        if (
            clinic_result
            and clinic_info_requested
        ):
            clinic_answer, clinic_name = (
                clinic_result
            )

            print(
                "CLINIC INFO MATCH:",
                clinic_answer,
            )

            print(
                "CLINIC CONTEXT NOW:",
                clinic_name,
            )

            tool_results = list(
                state.get(
                    "tool_results",
                    [],
                )
                or []
            )

            tool_results.append(
                {
                    "tool":
                        "clinic_information",

                    "query":
                        caller_text,

                    "clinic":
                        clinic_name,

                    "answer":
                        clinic_answer,
                }
            )

            (
                response_text,
                _,
                awaiting_more_help,
            ) = _build_faq_response(
                clinic_answer,
                faq_interrupted_intake,
            )

            return {
                "intent":
                    faq_intent,

                "active_workflow":
                    preserved_workflow,

                "response_text":
                    response_text,

                "awaiting_more_help":
                    awaiting_more_help,

                "last_referenced_clinic":
                    clinic_name,

                "tool_results":
                    tool_results,

                "current_node":
                    "faq_search",
            }

        # =================================================
        # 2. APPROVED FAQ KNOWLEDGE
        # =================================================

        results = search_approved_faq(
            db=db,
            query=caller_text,
            limit=5,
        )

        # =================================================
        # 3. NO APPROVED ANSWER
        # =================================================

        if not results:
            fallback_answer = (
                "I don't have verified information "
                "for that in the approved clinic "
                "knowledge base."
            )

            (
                response_text,
                next_workflow,
                awaiting_more_help,
            ) = _build_faq_response(
                fallback_answer,
                faq_interrupted_intake,
            )

            return {
                "intent":
                    faq_intent,

                "response_text":
                    response_text,

                "active_workflow": (
                    preserved_workflow
                    if faq_interrupted_workflow
                    else next_workflow
                ),

                "awaiting_more_help":
                    awaiting_more_help,

                "current_node":
                    "faq_search",
            }

        # =================================================
        # 4. BEST APPROVED FAQ MATCH
        # =================================================

        best_match = results[0]

        answer = (
            best_match.approved_answer
        )

        question = (
            best_match.question
        )

    # =====================================================
    # 5. RECORD FAQ TOOL RESULT
    # =====================================================

    tool_results = list(
        state.get(
            "tool_results",
            [],
        )
        or []
    )

    tool_results.append(
        {
            "tool":
                "faq_search",

            "query":
                caller_text,

            "matched_question":
                question,

            "approved_answer":
                answer,
        }
    )

    (
        response_text,
        next_workflow,
        awaiting_more_help,
    ) = _build_faq_response(
        answer,
        faq_interrupted_intake,
    )

    return {
        "intent":
            faq_intent,

        "response_text":
            response_text,

        "active_workflow": (
            preserved_workflow
            if faq_interrupted_workflow
            else next_workflow
        ),

        "awaiting_more_help":
            awaiting_more_help,

        "tool_results":
            tool_results,

        "current_node":
            "faq_search",
    }