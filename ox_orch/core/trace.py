from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ox_orch.core.files import FileBackend


__all__ = ("TraceEvent", "ReplayState", "ExecutionReplay")


class TraceEvent(BaseModel):
    """
    Single execution trace event emitted by the executor.
    """

    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    phase: str
    """ apply | rollback | hook | state_update | error """

    operation: str
    state_id: str | None = None
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ReplayState(BaseModel):
    """
    Reconstructed state of an execution run.
    """

    run_id: str
    operations: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    """ phase history per operation """

    errors: list[dict[str, Any]] = Field(default_factory=list)
    """ captured errors """

    order: list[dict[str, Any]] = Field(default_factory=list)
    """ global chronological event log """


class ExecutionReplay:
    """
    Reconstructs an execution run from persisted trace events.

    This component is strictly READ-ONLY:
    - does not execute operations
    - does not mutate external systems
    - does not invoke hooks

    It transforms a trace log into a structured execution timeline.
    """

    def __init__(self, backend: FileBackend):
        """
        :param backend: FileBackend used to read trace data (JSON/YAML/JSONL etc.)
        """
        self.backend = backend

    def replay(self, trace_path: Path) -> ReplayState:
        """
        Replay a full execution run from a trace file.

        :param trace_path: Path to stored trace file
        :return: reconstructed execution state
        """
        events = self._load(trace_path)
        return self._replay_events(events)

    def _load(self, path: Path) -> list[TraceEvent]:
        """
        Load trace events from backend storage.

        :param path: trace file path
        :return: list of TraceEvent objects
        """
        raw = self.backend.load(path)
        return [TraceEvent.model_validate(item) for item in raw]

    def _replay_events(self, events: list[TraceEvent]) -> ReplayState:
        """
        Build execution state from ordered events.

        :param events: trace events
        :return: ReplayState
        """
        if not events:
            raise ValueError("Cannot replay empty trace")

        events = sorted(events, key=lambda e: e.timestamp)
        state = ReplayState(run_id=events[0].run_id)

        for event in events:
            self._apply_event(state, event)

        return state

    def _apply_event(self, state: ReplayState, event: TraceEvent):
        """
        Apply a single trace event into the replay state.
        """

        state.order.append(event.model_dump())

        op_bucket = state.operations.setdefault(event.operation, [])
        op_bucket.append(
            {
                "phase": event.phase,
                "timestamp": event.timestamp,
                "state_id": event.state_id,
                "message": event.message,
                "data": event.data,
            }
        )

        if event.phase in ("error", "apply_failed", "rollback_failed"):
            state.errors.append(
                {
                    "operation": event.operation,
                    "message": event.message,
                    "timestamp": event.timestamp,
                }
            )
