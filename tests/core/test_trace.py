import pytest
from datetime import datetime, timedelta
from pydantic import BaseModel

from ox_orch.core.trace import TraceEvent, ExecutionReplay, ReplayState
from ox_orch.core.files import JSONBackend


# ----------------------------------------------------------------------
# Dummy backend model (must be a BaseModel)
# ----------------------------------------------------------------------


class DummyTraceModel(BaseModel):
    """
    Minimal model to satisfy FileBackend contract.
    """

    data: list[dict] = []


class DummyBackend(JSONBackend):
    """
    Backend used only for testing ExecutionReplay.
    """

    def __init__(self):
        super().__init__(model_class=DummyTraceModel, as_list=False)


@pytest.fixture
def backend():
    """
    Provides a trace backend for replay tests.
    """
    return DummyBackend()


@pytest.fixture
def replay(backend):
    """
    ExecutionReplay instance under test.
    """
    return ExecutionReplay(backend)


@pytest.fixture
def base_time():
    return datetime.utcnow()


@pytest.fixture
def make_event(base_time):
    """
    Factory fixture for deterministic trace events.
    """

    def _make(run_id: str, op: str, phase: str, offset: int = 0, message=None):
        return TraceEvent(
            run_id=run_id,
            operation=op,
            phase=phase,
            message=message,
            timestamp=base_time + timedelta(seconds=offset),
            state_id=f"{op}-state",
            data={"i": offset},
        )

    return _make


class TestTraceEvent:
    def test_model_dump(self, make_event):
        event = make_event("r1", "op", "apply")

        dumped = event.model_dump()

        assert dumped["run_id"] == "r1"
        assert dumped["operation"] == "op"
        assert dumped["phase"] == "apply"


class TestExecutionReplay:
    def test_load_events(self, replay, backend, make_event):
        raw = [
            make_event("r1", "op", "apply").model_dump(),
            make_event("r1", "op", "apply").model_dump(),
        ]

        backend.load = lambda _: raw  # isolate IO

        events = replay._load("fake-path")

        assert len(events) == 2
        assert all(isinstance(e, TraceEvent) for e in events)

    def test_events_sorted_by_timestamp(self, replay, make_event):
        events = [
            make_event("r1", "op", "apply", 3),
            make_event("r1", "op", "apply", 1),
            make_event("r1", "op", "apply", 2),
        ]

        state = replay._replay_events(events)

        timestamps = [e["timestamp"] for e in state.order]
        assert timestamps == sorted(timestamps)

    def test_grouping_by_operation(self, replay, make_event):
        events = [
            make_event("r1", "op-a", "apply"),
            make_event("r1", "op-a", "apply"),
            make_event("r1", "op-b", "rollback"),
        ]

        state = replay._replay_events(events)

        assert set(state.operations.keys()) == {"op-a", "op-b"}
        assert len(state.operations["op-a"]) == 2
        assert len(state.operations["op-b"]) == 1

    def test_error_collection(self, replay, make_event):
        events = [
            make_event("r1", "op-a", "apply"),
            make_event("r1", "op-a", "error", message="boom"),
            make_event("r1", "op-b", "rollback_failed", message="fail"),
        ]

        state = replay._replay_events(events)

        assert len(state.errors) == 2
        assert state.errors[0]["message"] == "boom"
        assert state.errors[1]["message"] == "fail"

    def test_full_replay_flow(self, replay, make_event):
        events = [
            make_event("run-99", "install", "apply", 1),
            make_event("run-99", "install", "apply", 2),
            make_event("run-99", "install", "rollback", 3),
            make_event("run-99", "cleanup", "apply", 4),
        ]

        state = replay._replay_events(events)

        assert isinstance(state, ReplayState)
        assert state.run_id == "run-99"
        assert len(state.order) == 4

        assert "install" in state.operations
        assert "cleanup" in state.operations

        phases = [e["phase"] for e in state.operations["install"]]
        assert phases == ["apply", "apply", "rollback"]

    def test_empty_events_raise(self, replay):
        with pytest.raises(ValueError):
            replay._replay_events([])
