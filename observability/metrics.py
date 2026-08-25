from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import select

from db.models import AuditEvent, CallSession
from db.session import get_db_session


def _percentile(
    values: list[float],
    percentile: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    index = round(
            (len(ordered) - 1)
            * percentile
        )

    return round(
        ordered[index],
        2,
    )


def get_node_metrics() -> list[dict[str, Any]]:
    """
    Aggregate successful node execution latency.
    """

    with get_db_session() as db:
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.event_type
                    == "node_completed"
                )
            ).all()
        )

    grouped: dict[str, list[float]] = (
        defaultdict(list)
    )

    for event in events:
        if (
            event.node
            and event.latency_ms
            is not None
        ):
            grouped[event.node].append(
                float(event.latency_ms)
            )

    results = []

    for node_name, latencies in grouped.items():
        results.append(
            {
                "node":
                    node_name,

                "executions":
                    len(latencies),

                "avg_latency_ms":
                    round(
                        mean(latencies),
                        2,
                    ),

                "p95_latency_ms":
                    _percentile(
                        latencies,
                        0.95,
                    ),

                "max_latency_ms":
                    round(
                        max(latencies),
                        2,
                    ),
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["avg_latency_ms"]
        ),
        reverse=True,
    )


def get_node_failure_metrics() -> dict[str, Any]:
    """
    Count graph-node failures.
    """

    with get_db_session() as db:
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.event_type
                    == "node_failed"
                )
            ).all()
        )

    failures = Counter(
        event.node or "unknown"
        for event in events
    )

    return {
        "total_failures":
            len(events),

        "failures_by_node":
            dict(failures),
    }


def get_call_metrics() -> dict[str, Any]:
    """
    Aggregate call-level operational metrics.
    """

    with get_db_session() as db:
        sessions = list(
            db.scalars(
                select(CallSession)
            ).all()
        )

    total_calls = len(sessions)

    completed_sessions = [
        session
        for session in sessions
        if session.ended_at is not None
    ]

    escalated_calls = sum(
        1
        for session in sessions
        if session.escalated
    )

    verified_calls = sum(
        1
        for session in sessions
        if session.verified
    )

    outcomes = Counter(
        session.outcome or "unfinished"
        for session in sessions
    )

    intents = Counter(
        session.intent or "unknown"
        for session in sessions
    )

    durations_seconds: list[float] = []

    for session in completed_sessions:
        if (
            session.started_at
            and session.ended_at
        ):
            duration = (
                session.ended_at
                - session.started_at
            ).total_seconds()

            if duration >= 0:
                durations_seconds.append(
                    duration
                )

    average_duration = (
        round(
            mean(durations_seconds),
            2,
        )
        if durations_seconds
        else None
    )

    escalation_rate = (
        round(
            (
                escalated_calls
                / total_calls
            )
            * 100,
            2,
        )
        if total_calls
        else 0.0
    )

    verification_rate = (
        round(
            (
                verified_calls
                / total_calls
            )
            * 100,
            2,
        )
        if total_calls
        else 0.0
    )

    completion_rate = (
        round(
            (
                len(completed_sessions)
                / total_calls
            )
            * 100,
            2,
        )
        if total_calls
        else 0.0
    )

    return {
        "total_calls":
            total_calls,

        "completed_calls":
            len(
                completed_sessions
            ),

        "completion_rate_percent":
            completion_rate,

        "verified_calls":
            verified_calls,

        "verification_rate_percent":
            verification_rate,

        "escalated_calls":
            escalated_calls,

        "escalation_rate_percent":
            escalation_rate,

        "average_call_duration_seconds":
            average_duration,

        "p95_call_duration_seconds":
            _percentile(
                durations_seconds,
                0.95,
            ),

        "outcomes":
            dict(outcomes),

        "intents":
            dict(intents),
    }

def get_tool_metrics() -> list[dict[str, Any]]:
    """
    Aggregate successful backend/tool latency.
    """

    with get_db_session() as db:
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.event_type
                    == "tool_completed"
                )
            ).all()
        )

    grouped: dict[str, list[float]] = (
        defaultdict(list)
    )

    for event in events:
        if (
            event.tool_name
            and event.latency_ms
            is not None
        ):
            grouped[
                event.tool_name
            ].append(
                float(
                    event.latency_ms
                )
            )

    results: list[
        dict[str, Any]
    ] = []

    for tool_name, latencies in grouped.items():
        results.append(
            {
                "tool":
                    tool_name,

                "executions":
                    len(latencies),

                "avg_latency_ms":
                    round(
                        mean(latencies),
                        2,
                    ),

                "p95_latency_ms":
                    _percentile(
                        latencies,
                        0.95,
                    ),

                "max_latency_ms":
                    round(
                        max(latencies),
                        2,
                    ),
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["avg_latency_ms"]
        ),
        reverse=True,
    )


def get_tool_failure_metrics() -> dict[str, Any]:
    """
    Count backend/tool failures.
    """

    with get_db_session() as db:
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.event_type
                    == "tool_failed"
                )
            ).all()
        )

    failures = Counter(
        event.tool_name
        or "unknown"
        for event in events
    )

    return {
        "total_failures":
            len(events),

        "failures_by_tool":
            dict(failures),
    }


def build_observability_report() -> dict[str, Any]:
    """
    Build the complete operational report.
    """

    return {
        "calls":
            get_call_metrics(),

        "nodes":
            get_node_metrics(),

        "tools":
            get_tool_metrics(),

        "failures": {
            "nodes":
                get_node_failure_metrics(),

            "tools":
                get_tool_failure_metrics(),
        },
    }