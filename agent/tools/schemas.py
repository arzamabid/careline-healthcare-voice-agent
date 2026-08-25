from pydantic import BaseModel, Field


class SearchAvailabilityArgs(BaseModel):
    specialty: str = Field(
        description="Requested medical specialty."
    )
    date: str = Field(
        description="Requested appointment date in YYYY-MM-DD format."
    )


class BookAppointmentArgs(BaseModel):
    appointment_id: int = Field(
        description="Existing available appointment slot ID."
    )
    patient_id: int = Field(
        description="Verified patient ID."
    )


class SearchFAQArgs(BaseModel):
    query: str = Field(
        description="Administrative clinic information question."
    )


class SaveIntakeArgs(BaseModel):
    patient_id: int = Field(
        description="Verified patient ID."
    )
    session_id: int = Field(
        description="Database call-session ID."
    )
    answers: dict[str, str] = Field(
        description="Confirmed pre-visit intake responses."
    )
