from agent.tools.llm_tools import (
    search_appointment_availability,
    search_clinic_faq,
)


def main() -> None:
    print("APPOINTMENT TOOL:")
    print(search_appointment_availability.args_schema.model_json_schema())

    print()

    print("FAQ TOOL:")
    print(search_clinic_faq.args_schema.model_json_schema())


if __name__ == "__main__":
    main()
