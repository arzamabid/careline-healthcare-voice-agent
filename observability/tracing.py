from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from inspect import iscoroutinefunction
from time import perf_counter
from typing import Any

from db.models import AuditEvent
from db.session import get_db_session

# =========================================================
# TRACE EVENT
# =========================================================


def trace_event(
    *,
    session_id: int | None,
    event_type: str,
    node: str | None = None,
    tool_name: str | None = None,
    success: bool = True,
    latency_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Persist one structured observability event.

    Tracing must never crash the main voice workflow.
    If tracing itself fails, log locally and continue.
    """

    if session_id is None:
        return

    try:
        with get_db_session() as db:
            event = AuditEvent(
                session_id=session_id,
                event_type=event_type,
                node=node,
                tool_name=tool_name,
                latency_ms=(
                    round(latency_ms, 2)
                    if latency_ms is not None
                    else None
                ),
                success=success,
                metadata_json=metadata or {},
            )

            db.add(event)
            db.commit()

    except Exception as exc: # noqa: BLE001
        print(
            "TRACE EVENT FAILED:",
            type(exc).__name__,
            str(exc),
        )


# =========================================================
# TIMER
# =========================================================


class TraceTimer:
    """
    Small helper for measuring node/tool latency.

    Example:

        timer = TraceTimer()

        ... do work ...

        trace_event(
            ...,
            latency_ms=timer.elapsed_ms(),
        )
    """

    def __init__(self) -> None:
        self.started_at = perf_counter()

    def elapsed_ms(self) -> float:
        return (
            perf_counter()
            - self.started_at
        ) * 1000


# =========================================================
# SAFE METADATA
# =========================================================


def build_trace_metadata(
    **values: Any,
) -> dict[str, Any]:
    """
    Build trace metadata while removing None values.

    Do not put full member IDs, phone numbers,
    transcripts containing sensitive information,
    or hidden prompts into trace metadata.
    """

    return {
        key: value
        for key, value in values.items()
        if value is not None
    }


# =========================================================
# UTC TIMESTAMP
# =========================================================


def utc_now_iso() -> str:
    return datetime.now(
        UTC
    ).isoformat()


def trace_node(
    node_name: str,
    node_function: Callable,
) -> Callable:
    """
    Wrap a LangGraph node and automatically record:
    - node start
    - node completion
    - latency
    - failure

    The wrapped node's behavior is unchanged.
    """

    def wrapped(state):
        timer = TraceTimer()

        db_session_id = state.get(
            "db_session_id"
        )

        trace_event(
            session_id=db_session_id,
            event_type="node_started",
            node=node_name,
            success=True,
            metadata=build_trace_metadata(
                intent=state.get("intent"),
                active_workflow=state.get(
                    "active_workflow"
                ),
            ),
        )

        try:
            result = node_function(state)

            trace_event(
                session_id=db_session_id,
                event_type="node_completed",
                node=node_name,
                success=True,
                latency_ms=timer.elapsed_ms(),
                metadata=build_trace_metadata(
                    resulting_node=(
                        result.get("current_node")
                        if isinstance(result, dict)
                        else None
                    ),
                ),
            )

            return result

        except Exception as exc:
            trace_event(
                session_id=db_session_id,
                event_type="node_failed",
                node=node_name,
                success=False,
                latency_ms=timer.elapsed_ms(),
                metadata=build_trace_metadata(
                    error_type=type(exc).__name__,
                ),
            )

            raise

    return wrapped


def trace_tool(
    tool_name: str,
):
    """
    Decorator for tracing backend/tool execution.

    Records:
    - tool_started
    - tool_completed
    - tool_failed
    - execution latency

    The wrapped function must receive either:
    - db_session_id
    - session_id
    as a keyword argument if persistence is required.
    """

    def decorator(function):
        if iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(
                *args,
                **kwargs,
            ):
                timer = TraceTimer()

                session_id = (
                    kwargs.get(
                        "db_session_id"
                    )
                    or kwargs.get(
                        "session_id"
                    )
                )

                trace_event(
                    session_id=session_id,
                    event_type="tool_started",
                    tool_name=tool_name,
                    success=True,
                )

                try:
                    result = await function(
                        *args,
                        **kwargs,
                    )

                    trace_event(
                        session_id=session_id,
                        event_type="tool_completed",
                        tool_name=tool_name,
                        success=True,
                        latency_ms=timer.elapsed_ms(),
                    )

                    return result

                except Exception as exc:
                    trace_event(
                        session_id=session_id,
                        event_type="tool_failed",
                        tool_name=tool_name,
                        success=False,
                        latency_ms=timer.elapsed_ms(),
                        metadata=build_trace_metadata(
                            error_type=(
                                type(exc).__name__
                            ),
                        ),
                    )

                    raise

            return async_wrapper

        @wraps(function)
        def sync_wrapper(
            *args,
            **kwargs,
        ):
            timer = TraceTimer()

            session_id = (
                kwargs.get(
                    "db_session_id"
                )
                or kwargs.get(
                    "session_id"
                )
            )

            trace_event(
                session_id=session_id,
                event_type="tool_started",
                tool_name=tool_name,
                success=True,
            )

            try:
                result = function(
                    *args,
                    **kwargs,
                )

                trace_event(
                    session_id=session_id,
                    event_type="tool_completed",
                    tool_name=tool_name,
                    success=True,
                    latency_ms=timer.elapsed_ms(),
                )

                return result

            except Exception as exc:
                trace_event(
                    session_id=session_id,
                    event_type="tool_failed",
                    tool_name=tool_name,
                    success=False,
                    latency_ms=timer.elapsed_ms(),
                    metadata=build_trace_metadata(
                        error_type=(
                            type(exc).__name__
                        ),
                    ),
                )

                raise

        return sync_wrapper

    return decorator
