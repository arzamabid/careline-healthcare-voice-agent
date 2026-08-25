from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPORT_DIR = Path("evals/reports")
REPORT_PATH = REPORT_DIR / "combined_evaluation_report.json"

EVALUATORS = (
    (
        "graph",
        "evaluations.run_graph_evals",
    ),
    (
        "integration",
        "evaluations.run_integration_evals",
    ),
    (
        "voice",
        "evaluations.run_voice_evals",
    ),
)


def extract_json_report(
    output: str,
) -> dict[str, Any]:
    """
    Extract the final evaluator JSON object from stdout.

    Individual evaluators also print debugging information,
    so stdout is not guaranteed to contain only JSON.
    """

    decoder = json.JSONDecoder()

    reports: list[dict[str, Any]] = []

    for index, character in enumerate(output):
        if character != "{":
            continue

        try:
            value, _end = decoder.raw_decode(
                output[index:]
            )
        except json.JSONDecodeError:
            continue

        if (
            isinstance(value, dict)
            and "scenario_type" in value
            and "total" in value
            and "results" in value
        ):
            reports.append(value)

    if not reports:
        raise RuntimeError(
            "Could not find an evaluation JSON report "
            "in evaluator output."
        )

    return reports[-1]


def run_evaluator(
    *,
    name: str,
    module: str,
) -> dict[str, Any]:
    print(
        f"\n{'=' * 60}"
    )
    print(
        f"RUNNING {name.upper()} EVALUATION"
    )
    print(
        f"{'=' * 60}"
    )

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode != 0:
        print(
            process.stdout
        )

        if process.stderr:
            print(
                process.stderr,
                file=sys.stderr,
            )

        raise RuntimeError(
            f"{name} evaluator failed "
            f"with exit code "
            f"{process.returncode}."
        )

    report = extract_json_report(
        process.stdout
    )

    print(
        f"{name.capitalize()}: "
        f"{report['passed']}/"
        f"{report['total']} passed "
        f"({report['score_percent']}%)"
    )

    return report


def build_combined_report(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    total = sum(
        int(report.get("total", 0))
        for report in reports
    )

    passed = sum(
        int(report.get("passed", 0))
        for report in reports
    )

    failed = sum(
        int(report.get("failed", 0))
        for report in reports
    )

    supported_checks = sum(
        int(
            report.get(
                "supported_checks",
                0,
            )
        )
        for report in reports
    )

    unsupported_checks = sum(
        int(
            report.get(
                "unsupported_checks",
                0,
            )
        )
        for report in reports
    )

    total_checks = (
        supported_checks
        + unsupported_checks
    )

    score_percent = (
        round(
            passed / total * 100,
            2,
        )
        if total
        else 0.0
    )

    metric_coverage_percent = (
        round(
            supported_checks
            / total_checks
            * 100,
            2,
        )
        if total_checks
        else 0.0
    )

    all_passed = (
        failed == 0
        and unsupported_checks == 0
    )

    breakdown = {
        report["scenario_type"]: {
            "total":
                report.get("total", 0),
            "passed":
                report.get("passed", 0),
            "failed":
                report.get("failed", 0),
            "score_percent":
                report.get(
                    "score_percent",
                    0.0,
                ),
            "metric_coverage_percent":
                report.get(
                    "metric_coverage_percent",
                    0.0,
                ),
        }
        for report in reports
    }

    return {
        "evaluation_suite":
            "careline_golden_baseline",

        "all_passed":
            all_passed,

        "total":
            total,

        "passed":
            passed,

        "failed":
            failed,

        "score_percent":
            score_percent,

        "metric_coverage_percent":
            metric_coverage_percent,

        "supported_checks":
            supported_checks,

        "unsupported_checks":
            unsupported_checks,

        "breakdown":
            breakdown,

        "reports":
            reports,
    }


def main() -> None:
    reports: list[
        dict[str, Any]
    ] = []

    for name, module in EVALUATORS:
        report = run_evaluator(
            name=name,
            module=module,
        )

        reports.append(
            report
        )

    combined = build_combined_report(
        reports
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(
            combined,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"\n{'=' * 60}"
    )
    print(
        "COMBINED EVALUATION"
    )
    print(
        f"{'=' * 60}"
    )

    print(
        json.dumps(
            {
                "total":
                    combined["total"],

                "passed":
                    combined["passed"],

                "failed":
                    combined["failed"],

                "score_percent":
                    combined[
                        "score_percent"
                    ],

                "metric_coverage_percent":
                    combined[
                        "metric_coverage_percent"
                    ],

                "supported_checks":
                    combined[
                        "supported_checks"
                    ],

                "unsupported_checks":
                    combined[
                        "unsupported_checks"
                    ],

                "all_passed":
                    combined[
                        "all_passed"
                    ],

                "report_path":
                    str(REPORT_PATH),
            },
            indent=2,
        )
    )

    if not combined["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
