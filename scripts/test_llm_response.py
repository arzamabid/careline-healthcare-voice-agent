from agent.llm.response import generate_patient_response


def main() -> None:
    response = generate_patient_response(
        instruction=(
            "Tell the caller that their appointment "
            "was successfully booked."
        ),
        facts={
            "specialty": "Dermatology",
            "date": "2026-08-25",
            "time": "10:30",
        },
        fallback=(
            "Your appointment was successfully booked."
        ),
    )

    print(response)


if __name__ == "__main__":
    main()