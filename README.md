# CareLine Healthcare Voice Agent

A local-first, production-style AI voice agent for healthcare patient services.

CareLine demonstrates how a healthcare organization can automate common
administrative phone workflows while keeping safety-critical decisions
deterministic and avoiding paid cloud AI services.

> This project uses synthetic data only.
> It is not a diagnostic or clinical decision-support system.

---

## Overview

CareLine is a realtime healthcare patient-services voice agent that can:

- Verify a synthetic patient using two identifiers
- Search appointment availability
- Book appointments
- Cancel appointments
- Reschedule appointments
- Answer approved clinic FAQs
- Collect pre-visit intake information
- Detect emergency and clinical-advice requests
- Escalate unsafe requests to human assistance
- Handle caller interruptions
- Handle caller inactivity and re-engagement
- Persist call/session information
- Produce structured traces and evaluation reports

The project is designed as a production-style portfolio system rather than
a simple chatbot demo.

---

## Quick Start

```bash
git clone <repository-url>
cd careline-healthcare-voice-agent

python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env

ollama pull qwen3:4b-instruct

make db-up
make db-migrate
make db-seed
make run
```

Run the development checks:

```bash
make check
```

Run the complete evaluation suite:

```bash
make eval
```

## Safety Boundary

CareLine is intentionally restricted to administrative healthcare tasks.

The agent must not:

- Diagnose a patient
- Recommend treatment
- Interpret symptoms clinically
- Recommend medication
- Recommend medication dosage
- Advise a patient to start or stop medication
- Invent healthcare policies
- Expose another patient's information

Requests involving emergencies or clinical advice are routed to the
escalation workflow.

Appointment mutations require explicit caller confirmation before any
database write occurs.

---

## Architecture

```text
Caller
  |
  v
LiveKit
  |
  v
Silero VAD
  |
  v
faster-whisper STT
  |
  v
LangGraph
  |
  +--> Safety Gate
  |
  +--> Intent Classification
  |
  +--> Identity Verification
  |
  +--> Appointment Workflow
  |
  +--> FAQ Workflow
  |
  +--> Pre-Visit Intake
  |
  +--> Human Escalation
  |
  v
Deterministic Tools / PostgreSQL
  |
  v
Kokoro TTS
  |
  v
Caller
````

The architecture deliberately separates:

* Probabilistic LLM reasoning
* Deterministic workflow state
* Deterministic healthcare business rules
* Database mutations
* Explicit confirmation
* Safety routing

---

## Technology Stack

### Voice

* LiveKit Server
* LiveKit Agents SDK
* Silero VAD
* faster-whisper
* Kokoro TTS

### AI / Orchestration

* LangGraph
* LangChain integrations
* Ollama
* Qwen3 4B Instruct

Configured Ollama model:

```text
qwen3:4b-instruct
```

### Backend

* Python 3.11+
* FastAPI
* Uvicorn
* SQLAlchemy
* PostgreSQL
* Alembic

### Infrastructure

* Docker
* Docker Compose

### Observability

* Structured application traces
* Node latency tracing
* Tool latency tracing
* Call/session persistence
* Operational metrics

### Evaluation

* Deterministic graph evaluation
* Integration evaluation
* Voice-control evaluation
* STT Word Error Rate evaluation
* Local latency benchmark

---

## Why LangGraph?

Healthcare administrative workflows are stateful.

For example, appointment booking requires:

```text
Request
  ↓
Identity verification
  ↓
Collect specialty
  ↓
Collect date
  ↓
Search availability
  ↓
Present appointment
  ↓
Explicit confirmation
  ↓
Database mutation
  ↓
Wrap-up
```

Using a state graph makes workflow transitions explicit and testable.

The application does not rely on an LLM to decide whether a confirmed
database write is allowed.

---

## Healthcare Workflows

### Appointment Booking

The caller can request an appointment by specialty and date.

Example:

```text
Caller:
I want a Dermatology appointment tomorrow.

Agent:
I found Dermatology with Dr. Amal Rahman at 09:00 AM.
Would you like me to book this appointment?

Caller:
Yes.

Agent:
Your appointment has been booked successfully.
```

No appointment is booked until explicit confirmation is received.

---

### Appointment Cancellation

The system:

1. Verifies the caller
2. Retrieves the caller's booked appointments
3. Lets the caller identify the correct appointment
4. Reads the appointment back
5. Requests confirmation
6. Performs the cancellation only after confirmation

---

### Appointment Rescheduling

Rescheduling safely handles both the original and replacement appointment.

The old appointment is released and the new appointment is booked within
the same controlled workflow.

---

### Identity Verification

Protected patient workflows require two identifiers.

Synthetic example:

```text
Member ID: CARE-00001
Phone last four digits: 1001
```

The caller may provide identifiers together or across separate turns.

The system supports common speech-to-text variations such as:

```text
care zero zero zero zero one
```

Verification is limited to three failed attempts before escalation.

---

### FAQ

FAQ responses are restricted to approved information.

Examples include:

* Clinic opening hours
* Clinic addresses
* Arrival instructions
* Administrative clinic information

Unsupported questions return a deterministic fallback rather than an
invented answer.

---

### Pre-Visit Intake

The agent collects structured non-diagnostic information one question at a
time.

Example fields include:

* Reason for visit
* Allergies
* Current medications
* Previous conditions
* Recent procedures
* Mobility support
* Interpreter requirement
* Contact preference
* Transportation support
* Additional notes

The complete intake is reviewed with the caller before storage.

---

## Safety and Escalation

The safety gate runs before normal workflow processing.

Examples that trigger escalation include:

```text
"What disease do I have?"

"What medication should I take?"

"What dose should I take?"

"Should I stop taking my blood pressure medicine?"

"I am having severe chest pain."
```

The agent does not generate clinical advice in these situations.

---

## Explicit Confirmation

Database-changing operations are protected by explicit confirmation.

Protected actions:

* Book appointment
* Cancel appointment
* Reschedule appointment
* Store confirmed pre-visit intake

Ambiguous responses such as:

```text
Maybe.
I suppose so.
Probably.
```

do not authorize a write.

---

## Idempotency

Appointment mutation paths include idempotency protection.

Repeated confirmation cannot create duplicate bookings for the same
confirmed action.

---

## Voice Behavior

The voice worker supports:

* Realtime LiveKit sessions
* Local STT
* Local TTS
* Caller interruption during appointment option playback
* Microphone echo protection
* Inactivity detection
* One re-engagement attempt
* Automatic call closing after repeated inactivity

---

## Local Setup

### Requirements

Install:

* Python 3.11+
* Docker
* Docker Compose
* Ollama

Create the environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Install the project and development dependencies:

```bash
pip install -e ".[dev]"
```

---

## Ollama Model

Pull the local model:

```bash
ollama pull qwen3:4b-instruct
```

Verify:

```bash
ollama list
```

The application configuration uses:

```env
OLLAMA_MODEL=qwen3:4b-instruct
```

---

## Environment Configuration

Copy:

```bash
cp .env.example .env
```

Example local development configuration:

```env
DATABASE_URL=postgresql+psycopg://careline:careline@localhost:5433/careline
OLLAMA_MODEL=qwen3:4b-instruct
```

Only synthetic data should be used with this repository.

---

## Database

Start PostgreSQL:

```bash
make db-up
```

Apply migrations:

```bash
make db-migrate
```

Seed synthetic data:

```bash
make db-seed
```

The seed data includes:

* 30 synthetic patients
* 5 clinicians
* 3 clinics
* 30 FAQ entries
* 280 appointment availability records

---

## Run the API

```bash
make run
```

Equivalent:

```bash
uvicorn apps.api.main:app --reload
```

Health endpoint:

```text
GET /health
```

---

## Appointment APIs

The project contains administrative appointment operations including:

```text
GET  /appointments/availability
POST /appointments/book
POST /appointments/reschedule
POST /appointments/cancel
```

The LangGraph workflow adds identity verification and explicit confirmation
before protected mutations are executed.

---

## Development Checks

Run linting:

```bash
make lint
```

Run tests:

```bash
make test
```

Run both:

```bash
make check
```

Current regression suite:

```text
38 tests passing
```

---

## Evaluation

Evaluation is treated as a first-class part of the project.

The project includes:

* Graph-level scenarios
* Integration scenarios
* Voice-control scenarios
* Safety scenarios
* Privacy scenarios
* Confirmation scenarios
* Appointment mutation tests
* FAQ grounding tests
* ASR-corruption tests
* STT WER measurement
* Latency benchmarking

---

## Golden Evaluation Suite

Run:

```bash
make eval-core
```

Current result:

```text
Graph:        24 / 24 passed
Integration:  22 / 22 passed
Voice:         4 / 4 passed

Total:        50 / 50 passed
Score:        100%
Coverage:     100%
Supported checks: 203
Unsupported checks: 0
```

Report:

```text
evals/reports/combined_evaluation_report.json
```

The suite explicitly tests critical behaviors such as:

* Emergency escalation
* Clinical-advice refusal
* Medication advice refusal
* No unauthorized database writes
* Explicit appointment confirmation
* Duplicate confirmation safety
* Identity failure limits
* Cross-patient access protection
* FAQ grounding
* Prompt-injection resistance
* Workflow interruption
* Inactivity handling
* Spoken identifier normalization
* Ambiguous ASR input
* Clean call closing
* No hallucinated appointment specialty

---

## STT Evaluation

Run:

```bash
make eval-stt
```

STT model:

```text
faster-whisper-base.en
```

Audio source:

```text
Kokoro-generated clean synthetic healthcare speech
```

Measured result:

```text
Samples:                  10
Aggregate WER:            12.16%
Pass threshold:           20%
Samples within threshold: 8 / 10
Aggregate result:         PASS
```

Most errors were concentrated in spoken numeric identifiers.

Examples:

```text
zero zero zero zero one
→
0 0 0 0 1
```

and:

```text
one zero zero one
→
1.001
```

The reported WER is intentionally left as raw WER rather than modifying the
metric to hide numeric formatting differences.

### WER Limitation

This benchmark uses clean synthetic speech.

The 12.16% value should not be interpreted as real-world healthcare
call-center WER.

A production deployment should additionally evaluate:

* Real microphones
* Telephone codecs
* Background noise
* Regional accents
* Interruptions
* Packet loss
* Real caller speech

---

## Latency Evaluation

Run:

```bash
make eval-latency
```

The benchmark performs warm-up runs before measured runs.

Current local steady-state measurements:

| Component               |    Mean |  Median |     P95 |
|-------------------------|--------:|--------:|--------:|
| STT                     |  589 ms |  581 ms |  615 ms |
| Deterministic FAQ graph |  8.7 ms |  8.5 ms | 10.2 ms |
| LLM-backed graph turn   | 1466 ms |  486 ms | 5416 ms |
| TTS                     | 1891 ms | 1899 ms | 1982 ms |
| STT → Graph → TTS       | 2693 ms | 2518 ms | 3127 ms |

Report:

```text
evals/reports/latency_evaluation_report.json
```

### Interpretation

TTS is currently the largest steady-state processing component.

The LLM-backed path also shows occasional local inference variance. Its
median is substantially lower than its mean because one measured run was
significantly slower.

The deterministic FAQ route avoids the LLM and completes graph processing
in only a few milliseconds.

---

## Latency Limitations

The end-to-end benchmark measures local processing:

```text
STT
  ↓
LangGraph / tools / local LLM
  ↓
TTS
```

It does not include:

* Caller speech duration
* VAD waiting time
* LiveKit network transport
* Telephony network latency
* Internet jitter
* Audio-device latency

Therefore these results are described as:

```text
local synthetic processing latency
```

rather than real-world phone-call latency.

---

## Run All Evaluations

Run:

```bash
make eval
```

This executes:

```text
50-scenario functional/safety suite
+
STT WER benchmark
+
Latency benchmark
```

Generated reports are stored under:

```text
evals/reports/
```

---

## Repository Structure

```text
careline-healthcare-voice-agent/
├── agent/
│   ├── graph.py
│   ├── state.py
│   ├── llm/
│   │   ├── base.py
│   │   ├── fake.py
│   │   ├── intent.py
│   │   ├── ollama.py
│   │   ├── response.py
│   │   ├── schemas.py
│   │   └── tool_model.py
│   ├── nodes/
│   │   ├── appointments.py
│   │   ├── escalation.py
│   │   ├── faq.py
│   │   ├── finalize.py
│   │   ├── greeting.py
│   │   ├── identity.py
│   │   ├── intake.py
│   │   ├── intent.py
│   │   └── safety.py
│   ├── policies/
│   │   ├── healthcare_sops.yaml
│   │   ├── loader.py
│   │   └── models.py
│   ├── tools/
│   │   ├── appointments.py
│   │   ├── booked_appointments.py
│   │   ├── confirmation.py
│   │   ├── dispatcher.py
│   │   ├── identity.py
│   │   ├── intake.py
│   │   ├── llm_tools.py
│   │   ├── registry.py
│   │   ├── schemas.py
│   │   ├── write_guard.py
│   │   └── write_requests.py
│   └── voice/
│       ├── livekit_stt.py
│       ├── livekit_tts.py
│       ├── stt.py
│       ├── tts.py
│       └── vad.py
│
├── apps/
│   ├── api/
│   │   ├── config.py
│   │   ├── confirmation.py
│   │   ├── dependencies.py
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── routes/
│   │   │   ├── appointments.py
│   │   │   ├── dev.py
│   │   │   ├── escalations.py
│   │   │   ├── faq.py
│   │   │   ├── intake.py
│   │   │   ├── metrics.py
│   │   │   ├── patients.py
│   │   │   └── sessions.py
│   │   └── services/
│   │       ├── appointments.py
│   │       ├── faq.py
│   │       └── patients.py
│   └── voice_agent/
│       └── worker.py
│
├── data/
│   ├── audio/
│   ├── faq/
│   └── seed/
│
├── db/
│   ├── base.py
│   ├── models.py
│   ├── session.py
│   └── migrations/
│       ├── env.py
│       └── versions/
│
├── docs/
│   ├── architecture.md
│   ├── evaluation.md
│   ├── requirements.md
│   └── sops.md
│
├── evals/
│   ├── datasets/
│   ├── reports/
│   │   ├── combined_evaluation_report.json
│   │   ├── latency_evaluation_report.json
│   │   └── stt_evaluation_report.json
│   ├── scenarios/
│   │   └── golden_scenarios.yaml
│   └── scorers/
│
├── evaluations/
│   ├── run_all_evals.py
│   ├── run_golden_evals.py
│   ├── run_graph_evals.py
│   ├── run_integration_evals.py
│   ├── run_latency_evals.py
│   ├── run_stt_evals.py
│   └── run_voice_evals.py
│
├── observability/
│   ├── metrics.py
│   ├── session_persistence.py
│   └── tracing.py
│
├── scripts/
│   ├── observability_report.py
│   ├── run_appointment_demo.py
│   ├── run_graph_demo.py
│   ├── run_identity_demo.py
│   ├── run_intake_demo.py
│   ├── seed_db.py
│   ├── test_llm_intent.py
│   ├── test_llm_response.py
│   ├── test_llm_tools.py
│   ├── test_ollama.py
│   ├── test_stt.py
│   ├── test_tool_dispatcher.py
│   ├── test_tool_schemas.py
│   ├── test_tts.py
│   └── test_vad.py
│
├── tests/
│   ├── conversation/
│   ├── integration/
│   │   ├── test_appointment_authorization.py
│   │   ├── test_graph_appointment.py
│   │   ├── test_graph_faq.py
│   │   ├── test_graph_identity.py
│   │   ├── test_ollama_smoke.py
│   │   └── test_patient_verification.py
│   ├── load/
│   └── unit/
│       ├── test_database_models.py
│       ├── test_fake_llm.py
│       ├── test_golden_scenarios.py
│       ├── test_graph_basic.py
│       ├── test_graph_persistence.py
│       ├── test_graph_safety.py
│       ├── test_health.py
│       ├── test_llm_response_fallback.py
│       ├── test_seed_data.py
│       ├── test_sops.py
│       ├── test_tool_dispatcher.py
│       └── test_write_guard.py
│
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── livekit.yaml
├── Makefile
├── pyproject.toml
└── README.md
```

---

## Design Principles

### Deterministic Where Safety Matters

The LLM assists with language understanding, but protected operations use
explicit workflow state and deterministic rules.

### Single-Agent Orchestration

The system uses a single stateful agent rather than unnecessary multi-agent
coordination.

This reduces:

* Complexity
* Latency
* Cost
* Failure modes

### Local-First

The project is designed around free/open-source components that can run
locally.

### Evaluation Before Claims

Project claims are backed by repeatable evaluation rather than qualitative
statements alone.

---

## Known Limitations

This repository is a portfolio/reference implementation.

It does not represent a certified clinical system.

Current limitations include:

* Synthetic patient data only
* English-only STT benchmark
* Local development infrastructure
* No production telephony provider integration benchmark
* Small clean synthetic WER dataset
* Limited latency sample count
* No real hospital EHR integration
* No real patient identity provider
* No clinical diagnosis or treatment capabilities

---

## Future Improvements

Potential extensions include:

* Larger noisy-audio STT benchmark
* Accent-specific evaluation
* Streaming STT
* Streaming TTS
* Lower-latency local TTS model
* Expanded FAQ retrieval / RAG
* RAGAS evaluation if RAG is enabled
* Self-hosted Langfuse dashboards
* OpenTelemetry export
* Production secrets management
* Kubernetes deployment
* Load testing
* Real telephony integration
* Larger safety red-team dataset

---

## Disclaimer

CareLine is a software engineering and AI portfolio project.

It uses synthetic healthcare data and must not be used for diagnosis,
clinical treatment, medication decisions, or emergency medical guidance.

