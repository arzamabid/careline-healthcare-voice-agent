from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from agent.voice.stt import get_whisper_model
from agent.voice.tts import synthesize_speech

REPORT_PATH = Path(
    "evals/reports/stt_evaluation_report.json"
)

WER_THRESHOLD = float(
    os.getenv(
        "STT_WER_MAX",
        "0.20",
    )
)


TEST_PHRASES = [
    {
        "id": "STT-001",
        "text": (
            "I want to book a Dermatology "
            "appointment tomorrow."
        ),
    },
    {
        "id": "STT-002",
        "text": (
            "I want to reschedule my "
            "Cardiology appointment."
        ),
    },
    {
        "id": "STT-003",
        "text": (
            "Please cancel my appointment."
        ),
    },
    {
        "id": "STT-004",
        "text": (
            "My member ID is care zero zero "
            "zero zero one."
        ),
    },
    {
        "id": "STT-005",
        "text": (
            "The last four digits of my phone "
            "number are one zero zero one."
        ),
    },
    {
        "id": "STT-006",
        "text": (
            "What are North Clinic's "
            "opening hours?"
        ),
    },
    {
        "id": "STT-007",
        "text": (
            "Where is Central Clinic located?"
        ),
    },
    {
        "id": "STT-008",
        "text": (
            "I need a Family Medicine "
            "appointment."
        ),
    },
    {
        "id": "STT-009",
        "text": (
            "I want to speak with a human "
            "representative."
        ),
    },
    {
        "id": "STT-010",
        "text": (
            "No thank you, that's all."
        ),
    },
]


def normalize_text(
    text: str,
) -> str:
    """
    Normalize reference and hypothesis before WER.

    Lowercase, remove punctuation, and collapse whitespace.
    """

    normalized = text.lower()

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split()
    )


def levenshtein_distance(
    reference_words: list[str],
    hypothesis_words: list[str],
) -> int:
    """
    Compute word-level edit distance.
    """

    rows = len(reference_words) + 1
    columns = len(hypothesis_words) + 1

    matrix = [
        [0] * columns
        for _ in range(rows)
    ]

    for row in range(rows):
        matrix[row][0] = row

    for column in range(columns):
        matrix[0][column] = column

    for row in range(
        1,
        rows,
    ):
        for column in range(
            1,
            columns,
        ):
            substitution_cost = (
                0
                if (
                    reference_words[row - 1]
                    == hypothesis_words[column - 1]
                )
                else 1
            )

            matrix[row][column] = min(
                matrix[row - 1][column] + 1,
                matrix[row][column - 1] + 1,
                (
                    matrix[row - 1][column - 1]
                    + substitution_cost
                ),
            )

    return matrix[-1][-1]


def calculate_wer(
    reference: str,
    hypothesis: str,
) -> dict[str, Any]:
    normalized_reference = normalize_text(
        reference
    )

    normalized_hypothesis = normalize_text(
        hypothesis
    )

    reference_words = (
        normalized_reference.split()
    )

    hypothesis_words = (
        normalized_hypothesis.split()
    )

    if not reference_words:
        wer = (
            0.0
            if not hypothesis_words
            else 1.0
        )

        return {
            "wer": wer,
            "errors": len(
                hypothesis_words
            ),
            "reference_words": 0,
        }

    errors = levenshtein_distance(
        reference_words,
        hypothesis_words,
    )

    wer = (
        errors
        / len(reference_words)
    )

    return {
        "wer": wer,
        "errors": errors,
        "reference_words":
            len(reference_words),
    }


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


def evaluate_phrase(
    scenario: dict[str, str],
) -> dict[str, Any]:
    reference = scenario["text"]

    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=True,
    ) as tmp:
        synthesize_speech(
            reference,
            tmp.name,
        )

        hypothesis = transcribe_audio(
            tmp.name
        )

    metrics = calculate_wer(
        reference,
        hypothesis,
    )

    passed = (
        metrics["wer"]
        <= WER_THRESHOLD
    )

    return {
        "id":
            scenario["id"],

        "reference":
            reference,

        "hypothesis":
            hypothesis,

        "normalized_reference":
            normalize_text(
                reference
            ),

        "normalized_hypothesis":
            normalize_text(
                hypothesis
            ),

        "errors":
            metrics["errors"],

        "reference_words":
            metrics[
                "reference_words"
            ],

        "wer":
            round(
                metrics["wer"],
                4,
            ),

        "wer_percent":
            round(
                metrics["wer"]
                * 100,
                2,
            ),

        "passed":
            passed,
    }


def main() -> None:
    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = [
        evaluate_phrase(
            scenario
        )
        for scenario in TEST_PHRASES
    ]

    total_errors = sum(
        result["errors"]
        for result in results
    )

    total_reference_words = sum(
        result["reference_words"]
        for result in results
    )

    aggregate_wer = (
        total_errors
        / total_reference_words
        if total_reference_words
        else 0.0
    )

    passed_samples = sum(
        1
        for result in results
        if result["passed"]
    )

    report = {
        "evaluation_type":
            "stt_wer",

        "stt_model":
            "faster-whisper-base.en",

        "audio_source":
            "kokoro-local-synthetic",

        "sample_count":
            len(results),

        "wer_threshold":
            WER_THRESHOLD,

        "wer_threshold_percent":
            round(
                WER_THRESHOLD * 100,
                2,
            ),

        "aggregate_wer":
            round(
                aggregate_wer,
                4,
            ),

        "aggregate_wer_percent":
            round(
                aggregate_wer * 100,
                2,
            ),

        "passed_samples":
            passed_samples,

        "failed_samples":
            (
                len(results)
                - passed_samples
            ),

        "all_samples_within_threshold":
            (
                passed_samples
                == len(results)
            ),

        "aggregate_within_threshold":
            (
                aggregate_wer
                <= WER_THRESHOLD
            ),

        "results":
            results,
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            indent=2,
        )
    )

    print(
        "\nSTT evaluation report:",
        REPORT_PATH,
    )

    if aggregate_wer > WER_THRESHOLD:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
