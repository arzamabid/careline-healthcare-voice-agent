# CareLine Project Requirements

## Purpose

CareLine is a local-first, browser-based healthcare patient-services
voice assistant using synthetic data only.

The system behaves like a patient-services call-center representative.
It is not a clinician.

## Supported capabilities

CareLine supports:

1. Synthetic patient identity verification.
2. Appointment availability search.
3. Appointment booking.
4. Appointment rescheduling.
5. Appointment cancellation.
6. Clinic and policy FAQ questions.
7. Pre-visit intake.
8. Human escalation.
9. Structured call summaries.

## Explicit non-goals

CareLine does not provide:

- Diagnosis.
- Treatment recommendations.
- Medication dosing.
- Clinical interpretation.
- Real patient or EHR integration.
- Autonomous access to real hospitals, insurers, pharmacies, or EHRs.
- Emergency medical advice beyond directing the caller to emergency
  services or qualified clinical staff.

## Data policy

Only deterministic synthetic healthcare records may be used in
development, testing, demonstrations, and evaluation.

No real patient information may be added to the repository.

## Architecture principle

LiveKit owns realtime audio/session mechanics.

LangGraph owns business workflow state, routing, confirmations,
safety gates, retries, and escalation.

FastAPI exposes deterministic backend tools.

Critical authorization and safety decisions must be implemented in
Python rather than delegated exclusively to an LLM.
