import pytest
from queue import Empty
from multiprocessing import Queue

from ox_orch.operations.multiprocess import ForkOperation, fork_entry
from ox_orch.operations.base import Operation, OperationState


class DummyState(OperationState):
    pass


class DummyApplyOperation(Operation):
    """Simple operation that yields states."""

    def apply(self, state, *args, **kwargs):
        yield {"step": 1}
        yield {"step": 2}


class ErrorOperation(Operation):
    """Operation that raises an error during execution."""

    def apply(self, state, *args, **kwargs):
        raise RuntimeError("boom")


class TestForkEntry:
    def test_success_yields_states_and_done(self):
        queue = Queue()

        op = DummyApplyOperation()

        fork_entry(
            queue=queue,
            operation=op,
            method="apply",
            state=None,
            args=[],
            kwargs={},
        )

        results = []
        while True:
            try:
                msg = queue.get(True, 1)
                results.append(msg)
            except Empty:
                break

        assert results == [("state", {"step": 1}), ("state", {"step": 2}), ("done", None)]

    def test_error_is_forwarded(self):
        queue = Queue()

        op = ErrorOperation()

        with pytest.raises(RuntimeError, match="boom"):
            fork_entry(
                queue=queue,
                operation=op,
                method="apply",
                state=None,
                args=[],
                kwargs={},
            )

        # ensure error message is in queue
        items = []
        while True:
            try:
                items.append(queue.get(True, 0.1))
            except Empty:
                break

        assert ("error", "boom") in items
        assert ("done", None) in items


class TestForkOperation:
    def test_run_success_streams_states(self):
        runner = ForkOperation(operation=DummyApplyOperation(), queue_max_size=10)

        state = DummyState()

        gen = runner.run(
            method="apply",
            state=state,
            args=[],
            kwargs={},
        )

        results = list(gen)

        assert results == [{"step": 1}, {"step": 2}]

    def test_run_propagates_error(self):
        runner = ForkOperation(operation=ErrorOperation(), queue_max_size=10)

        state = DummyState()

        gen = runner.run(
            method="apply",
            state=state,
            args=[],
            kwargs={},
        )

        with pytest.raises(RuntimeError, match="boom"):
            list(gen)
