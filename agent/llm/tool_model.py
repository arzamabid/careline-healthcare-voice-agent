from agent.llm.ollama import get_ollama_model
from agent.tools.llm_tools import (
    search_appointment_availability,
    search_clinic_faq,
)
from agent.tools.write_requests import (
    request_book_appointment,
    request_cancel_appointment,
    request_reschedule_appointment,
)

TOOLS = [
    # Read tools
    search_appointment_availability,
    search_clinic_faq,

    # Write REQUEST tools
    request_book_appointment,
    request_cancel_appointment,
    request_reschedule_appointment,
]


def get_tool_model():
    model = get_ollama_model()

    return model.bind_tools(TOOLS)