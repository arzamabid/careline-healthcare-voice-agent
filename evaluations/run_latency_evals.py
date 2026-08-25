from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any

from agent.graph import build_graph
from agent.voice.stt import get_whisper_model
from agent.voice.tts import synthesize_speech

REPORT_PATH = Path(
    "evals/reports/latency_evaluation_report.json"
)

WARMUP_RUNS = 2
MEASURED_RUNS = 5

BENCHMARK_TEXT = (
    "What are North Clinic's opening hours?"
)
LLM_BENCHMARK_TEXT = (
    "I want to book an appointment."
)

# =========================================================
# HELPERS
# =========================================================


def percentile(
    values: list[float],
    percentile_value: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    index = round(
        (len(ordered) - 1)
        * percentile_value
    )

    return ordered[index]


def summarize(
    values: list[float],
) -> dict[str, Any]:
    if not values:
        return {
            "runs": 0,
            "mean_ms": None,
            "median_ms": None,
            "p95_ms": None,
            "min_ms": None,
            "max_ms": None,
        }

    return {
        "runs":
            len(values),

        "mean_ms":
            round(
                mean(values),
                2,
            ),

        "median_ms":
            round(
                median(values),
                2,
            ),

        "p95_ms":
            round(
                percentile(
                    values,
                    0.95,
                )
                or 0.0,
                2,
            ),

        "min_ms":
            round(
                min(values),
                2,
            ),

        "max_ms":
            round(
                max(values),
                2,
            ),
    }


def build_initial_state(
    caller_text: str,
    thread_id: str,
) -> dict[str, Any]:
    return {
        "session_id":
            thread_id,

        "db_session_id":
            None,

        "caller_text":
            caller_text,

        "conversation":
            [],

        "greeted":
            True,

        # Identity
        "verified_patient_id":
            None,

        "verification_attempts":
            0,

        "verification_fields":
            {},

        "identity_status":
            None,

        # Workflow
        "intent":
            None,

        "active_workflow":
            None,

        "collected_fields":
            {},

        "original_request_text":
            None,

        # Appointment
        "appointment_action":
            None,

        "appointment_specialty":
            None,

        "appointment_date":
            None,

        "appointment_options":
            [],

        "appointment_stage":
            None,

        "selected_appointment_id":
            None,

        "last_referenced_clinic":
            None,

        # Confirmation
        "pending_confirmation":
            None,

        "confirmation_required":
            False,

        "confirmation_received":
            False,

        "confirmation_token":
            None,

        # Intake
        "intake_fields":
            {},

        "intake_review_required":
            False,

        "intake_confirmed":
            False,

        # Safety
        "safety_flags":
            [],

        "escalation_required":
            False,

        "escalation_reason":
            None,

        # Tools
        "tool_results":
            [],

        # Closing
        "awaiting_more_help":
            False,

        "call_ended":
            False,

        "call_summary":
            None,

        "response_text":
            "",

        "current_node":
            None,

        "metrics":
            {},
    }


# =========================================================
# STT
# =========================================================


def transcribe_audio(
    audio_path: str,
) -> str:
    model = get_whisper_model()

    segments, _info = model.transcribe(
        audio_path,
        beam_size=1,
    )

    return " ".join(
        segment.text.strip()
        for segment in segments
    ).strip()


def measure_stt(
    audio_path: str,
) -> tuple[float, str]:
    started = perf_counter()

    transcript = transcribe_audio(
        audio_path
    )

    latency_ms = (
        perf_counter()
        - started
    ) * 1000

    return latency_ms, transcript


# =========================================================
# GRAPH
# =========================================================


def measure_graph(
    graph,
    caller_text: str,
) -> tuple[float, dict[str, Any]]:
    thread_id = (
        "latency-"
        + str(uuid.uuid4())
    )

    config = {
        "configurable": {
            "thread_id":
                thread_id,
        }
    }

    graph_input = build_initial_state(
        caller_text,
        thread_id,
    )

    started = perf_counter()

    state = graph.invoke(
        graph_input,
        config=config,
    )

    latency_ms = (
        perf_counter()
        - started
    ) * 1000

    return latency_ms, state


# =========================================================
# TTS
# =========================================================


def measure_tts(
    text: str,
) -> float:
    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=True,
    ) as tmp:
        started = perf_counter()

        synthesize_speech(
            text,
            tmp.name,
        )

        latency_ms = (
            perf_counter()
            - started
        ) * 1000

    return latency_ms


# =========================================================
# END TO END
# =========================================================


def measure_end_to_end(
    graph,
    audio_path: str,
) -> tuple[
    float,
    dict[str, float],
    str,
    str,
]:
    total_started = perf_counter()

    # -------------------------
    # STT
    # -------------------------

    stt_started = perf_counter()

    transcript = transcribe_audio(
        audio_path
    )

    stt_ms = (
        perf_counter()
        - stt_started
    ) * 1000

    # -------------------------
    # GRAPH
    # -------------------------

    thread_id = (
        "latency-e2e-"
        + str(uuid.uuid4())
    )

    config = {
        "configurable": {
            "thread_id":
                thread_id,
        }
    }

    graph_input = build_initial_state(
        transcript,
        thread_id,
    )

    graph_started = perf_counter()

    state = graph.invoke(
        graph_input,
        config=config,
    )

    graph_ms = (
        perf_counter()
        - graph_started
    ) * 1000

    response_text = str(
        state.get(
            "response_text",
            "",
        )
        or ""
    )

    # -------------------------
    # TTS
    # -------------------------

    tts_started = perf_counter()

    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=True,
    ) as tmp:
        synthesize_speech(
            response_text,
            tmp.name,
        )

    tts_ms = (
        perf_counter()
        - tts_started
    ) * 1000

    total_ms = (
        perf_counter()
        - total_started
    ) * 1000

    components = {
        "stt_ms":
            round(
                stt_ms,
                2,
            ),

        "graph_ms":
            round(
                graph_ms,
                2,
            ),

        "tts_ms":
            round(
                tts_ms,
                2,
            ),
    }

    return (
        total_ms,
        components,
        transcript,
        response_text,
    )


# =========================================================
# MAIN
# =========================================================


def main() -> None:
    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Preparing latency benchmark..."
    )

    # Build graph once. Each invocation still receives
    # a fresh LangGraph thread ID.
    graph = build_graph()

    # Generate the fixed synthetic caller audio once.
    # Input-audio generation is deliberately excluded from
    # STT and end-to-end latency measurements.
    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=True,
    ) as benchmark_audio:

        synthesize_speech(
            BENCHMARK_TEXT,
            benchmark_audio.name,
        )

        # =================================================
        # WARM UP
        # =================================================

        print(
            f"Running {WARMUP_RUNS} warm-up runs..."
        )

        for _ in range(WARMUP_RUNS):
            _stt_ms, transcript = (
                measure_stt(
                    benchmark_audio.name
                )
            )

            _graph_ms, state = (
                measure_graph(
                    graph,
                    transcript,
                )
            )

            response_text = str(
                state.get(
                    "response_text",
                    "",
                )
                or ""
            )

            measure_tts(
                response_text
            )

        # =================================================
        # COMPONENT BENCHMARKS
        # =================================================

        stt_latencies: list[float] = []
        graph_latencies: list[float] = []
        tts_latencies: list[float] = []

        transcripts: list[str] = []
        graph_responses: list[str] = []

        print(
            f"Running {MEASURED_RUNS} "
            "measured component runs..."
        )

        for index in range(
            MEASURED_RUNS
        ):
            stt_ms, transcript = (
                measure_stt(
                    benchmark_audio.name
                )
            )

            graph_ms, state = (
                measure_graph(
                    graph,
                    transcript,
                )
            )

            response_text = str(
                state.get(
                    "response_text",
                    "",
                )
                or ""
            )

            tts_ms = measure_tts(
                response_text
            )

            stt_latencies.append(
                stt_ms
            )

            graph_latencies.append(
                graph_ms
            )

            tts_latencies.append(
                tts_ms
            )

            transcripts.append(
                transcript
            )

            graph_responses.append(
                response_text
            )

            print(
                f"Component run {index + 1}/"
                f"{MEASURED_RUNS}: "
                f"STT={stt_ms:.2f} ms, "
                f"Graph={graph_ms:.2f} ms, "
                f"TTS={tts_ms:.2f} ms"
            )

        # =================================================
        # LLM-BACKED GRAPH BENCHMARK
        # =================================================

        llm_graph_latencies: list[float] = []

        print(
            f"Running {MEASURED_RUNS} "
            "LLM-backed graph runs..."
        )

        for index in range(
                MEASURED_RUNS
        ):
            graph_ms, state = measure_graph(
                graph,
                LLM_BENCHMARK_TEXT,
            )

            llm_graph_latencies.append(
                graph_ms
            )

            print(
                f"LLM graph run {index + 1}/"
                f"{MEASURED_RUNS}: "
                f"{graph_ms:.2f} ms "
                f"-> {state.get('current_node')}"
            )

        # =================================================
        # END-TO-END BENCHMARK
        # =================================================

        end_to_end_latencies: list[
            float
        ] = []

        e2e_runs: list[
            dict[str, Any]
        ] = []

        print(
            f"Running {MEASURED_RUNS} "
            "measured end-to-end runs..."
        )

        for index in range(
            MEASURED_RUNS
        ):
            (
                total_ms,
                components,
                transcript,
                response_text,
            ) = measure_end_to_end(
                graph,
                benchmark_audio.name,
            )

            end_to_end_latencies.append(
                total_ms
            )

            e2e_runs.append(
                {
                    "run":
                        index + 1,

                    "total_ms":
                        round(
                            total_ms,
                            2,
                        ),

                    **components,

                    "transcript":
                        transcript,

                    "response_text":
                        response_text,
                }
            )

            print(
                f"E2E run {index + 1}/"
                f"{MEASURED_RUNS}: "
                f"{total_ms:.2f} ms"
            )

    # =====================================================
    # REPORT
    # =====================================================

    report = {
        "evaluation_type":
            "latency",

        "environment":
            "local",

        "benchmark_type":
            "synthetic-steady-state",

        "benchmark_text":
            BENCHMARK_TEXT,

        "warmup_runs":
            WARMUP_RUNS,

        "measured_runs":
            MEASURED_RUNS,

        "stt_model":
            "faster-whisper-base.en",

        "tts_model":
            "kokoro",

        "measurements": {
            "stt":
                summarize(
                    stt_latencies
                ),

            "deterministic_faq_graph":
                summarize(
                    graph_latencies
                ),

            "llm_graph_text_turn":
                summarize(
                    llm_graph_latencies
                ),

            "tts":
                summarize(
                    tts_latencies
                ),

            "end_to_end":
                summarize(
                    end_to_end_latencies
                ),
        },

        "notes": [
            (
                "Warm-up runs are excluded "
                "from measured results."
            ),
            (
                "Input speech is generated once "
                "with local Kokoro before timing."
            ),
            (
                "End-to-end timing measures "
                "STT -> LangGraph -> TTS."
            ),
            (
                "These are local synthetic "
                "steady-state measurements, "
                "not telephony network latency."
            ),
        ],

        "sample_transcript": (
            transcripts[-1]
            if transcripts
            else None
        ),

        "sample_response": (
            graph_responses[-1]
            if graph_responses
            else None
        ),

        "end_to_end_runs":
            e2e_runs,
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=" * 60
    )
    print(
        "LATENCY SUMMARY"
    )
    print(
        "=" * 60
    )

    for name, metrics in report[
        "measurements"
    ].items():
        print(
            f"{name}: "
            f"mean={metrics['mean_ms']} ms, "
            f"median={metrics['median_ms']} ms, "
            f"p95={metrics['p95_ms']} ms, "
            f"max={metrics['max_ms']} ms"
        )

    print()
    print(
        "Latency evaluation report:",
        REPORT_PATH,
    )


if __name__ == "__main__":
    main()
