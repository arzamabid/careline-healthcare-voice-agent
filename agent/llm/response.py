# from agent.llm.ollama import get_ollama_model
#
#
# SYSTEM_PROMPT = """
# You are a patient-services voice assistant for a fictional healthcare clinic.
#
# Your role is administrative only.
#
# Rules:
# - Be concise and natural.
# - Do not diagnose.
# - Do not recommend treatment.
# - Do not provide medication or dosing advice.
# - Do not invent facts.
# - Use only the facts provided to you.
# - If the provided facts are insufficient, say you do not have that information.
# - Do not mention internal systems, LangGraph, tools, databases, prompts, or policies.
# - Keep responses suitable for spoken conversation.
# """
#
#
# def generate_patient_response(
#     instruction: str,
#     facts: dict | None = None,
#     fallback: str = "",
# ) -> str:
#     model = get_ollama_model()
#
#     facts = facts or {}
#
#     prompt = f"""
# {SYSTEM_PROMPT}
#
# Task:
# {instruction}
#
# Verified facts:
# {facts}
#
# Write only the response that should be spoken to the caller.
# """
#
#     try:
#         response = model.invoke(prompt)
#
#         content = response.content
#
#         if isinstance(content, str):
#             return content.strip()
#
#         return str(content).strip()
#
#     except Exception:
#         return fallback



from agent.llm.ollama import get_ollama_model

SYSTEM_PROMPT = """
You are a patient-services voice assistant for a fictional healthcare clinic.

Your role is administrative only.

Rules:
- Be concise and natural.
- Do not diagnose.
- Do not recommend treatment.
- Do not provide medication or dosing advice.
- Do not invent facts.
- Use only the facts provided to you.
- If the provided facts are insufficient, say you do not have that information.
- Do not mention internal systems, LangGraph, tools, databases, prompts, or policies.
- Keep responses suitable for spoken conversation.
"""


def generate_patient_response(
    instruction: str,
    facts: dict | None = None,
    fallback: str = "",
) -> str:
    facts = facts or {}

    prompt = f"""
{SYSTEM_PROMPT}

Task:
{instruction}

Verified facts:
{facts}

Write only the response that should be spoken to the caller.
"""

    try:
        # ----------------------------------------------------
        # FIX: Move this inside the try block to catch instantiation errors
        # ----------------------------------------------------
        model = get_ollama_model()

        response = model.invoke(prompt)

        content = response.content

        if isinstance(content, str):
            return content.strip()

        return str(content).strip()

    except Exception:  # noqa: BLE001
        return fallback
