from langchain_core.tools import BaseTool

from agent.tools.llm_tools import (
    search_appointment_availability,
    search_clinic_faq,
)

READ_ONLY_TOOL_REGISTRY: dict[str, BaseTool] = {
    search_appointment_availability.name:
        search_appointment_availability,
    search_clinic_faq.name:
        search_clinic_faq,
}
