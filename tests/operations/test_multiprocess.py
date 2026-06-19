import pytest
from queue import Empty
from multiprocessing import Queue

from ox_orch.core import Status
from ox_orch.operations.multiprocess import BaseFork, ForkOperation, fork_entry
from ox_orch.operations.base import Operation, OperationState

from .conftest import apply, rollback


class DummyState(OperationState):
    step: int | None = None

    def with_step(self, step):
        return self.model_copy(update={"step": step})


class DummyApplyOperation(Operation):
    """Simple operation that yields states."""

    __state_class__ = DummyState

    def apply(self, state, *args, **kwargs):
        yield state.with_step(1)
        yield state.with_step(2)


class ErrorOperation(Operation):
    """Operation that raises an error during execution."""

    def apply(self, state, *args, **kwargs):
        raise RuntimeError("boom")


class TestForkEntry:
    def test_success_yields_states_and_done(self):
        queue = Queue()

        op = DummyApplyOperation()
        state = op.create_state()

        fork_entry(
            queue=queue,
            operation=op,
            method="apply",
            state=state,
            args=[],
            kwargs={},
        )

        results = []
        while True:
            try:
                msg = queue.get(True, 1)
                msg[1] and results.append(msg[1].step)
            except Empty:
                break

        assert results == [1, 2]

    def test_error_is_forwarded(self):
        queue = Queue()

        op = ErrorOperation()
        state = op.create_state()

        with pytest.raises(RuntimeError, match="boom"):
            fork_entry(
                queue=queue,
                operation=op,
                method="apply",
                state=state,
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


class TestBaseFork:
    def test_run_success_streams_states(self):
        runner = BaseFork(operation=DummyApplyOperation(), queue_max_size=10)

        state = DummyState()

        gen = runner.run(
            method="apply",
            state=state,
            args=[],
            kwargs={},
        )

        results = list(s.step for s in gen)

        assert results == [1, 2]

    def test_run_propagates_error(self):
        runner = BaseFork(operation=ErrorOperation(), queue_max_size=10)

        state = DummyState()

        gen = runner.run(
            method="apply",
            state=state,
            args=[],
            kwargs={},
        )

        with pytest.raises(RuntimeError, match="boom"):
            list(gen)


class TestForkOperation:
    @pytest.fixture
    @staticmethod
    def fork(plan):
        return ForkOperation(operation=plan, queue_max_size=10)

    def test_apply_and_rollback(self, fork):
        state = fork.create_state()
        states, exc = apply(fork, state)

        assert states[0]._operation == fork.operation

        states, exc = rollback(fork, state)

        assert states[0]._operation == fork.operation
        assert states[-1].status == Status.ROLLED_BACK
