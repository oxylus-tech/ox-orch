import pytest

from ox_orch.core.state import Status
from ox_orch.operations.execution import Executor, ExecutionError, ExecutionSpec
from ox_orch.operations import Operation

from ..conftest import ContextStrInput


class FakeOperation(Operation):
    """
    Minimal operation used to test Executor behavior.
    """

    __type_id__ = "op:test:fake"

    applied: bool = False
    rolled_back: bool = False
    fail_apply: bool = False
    fail_rollback: bool = False

    def _apply(self, state, exec_ctx, **context):
        if self.fail_apply:
            raise RuntimeError("apply failed")
        self.applied = True
        yield state

    def _rollback(self, state, exec_ctx, **context):
        if self.fail_rollback:
            raise RuntimeError("rollback failed")
        self.rolled_back = True
        yield state


@pytest.fixture
def operation():
    return FakeOperation()


@pytest.fixture
def state(operation):
    return operation.create_state()


@pytest.fixture
def a_input():
    return ContextStrInput(value="a")


@pytest.fixture
def executor():
    return Executor()


class TestExecutor:
    def test_apply_success(self, executor, operation, state):
        spec = ExecutionSpec(operation=operation)

        result = executor.apply_sync(spec)

        assert result.status == Status.COMPLETED
        assert operation.applied is True
        assert result.run_context is not None

    def test_apply_with_inputs(self, executor, operation, state, a_input):
        def _apply(self, state, ctx=None, test_a_input=None, **_):
            state._value = test_a_input.value
            yield state

        operation._apply = _apply.__get__(operation, FakeOperation)
        spec = ExecutionSpec(operation=operation)

        inputs = {"test_a_input": a_input}
        state = executor.apply_sync(spec, inputs=inputs)
        assert state._value == "a"

    def test_apply_failure(self, executor, operation, state):
        operation.fail_apply = True

        spec = ExecutionSpec(operation=operation, state=state)

        with pytest.raises(ExecutionError):
            executor.apply_sync(spec)

    def test_rollback_success(self, executor, operation, state):
        operation.applied = True
        spec = ExecutionSpec(operation=operation)
        state.status = Status.FAILED

        result = executor.rollback_sync(spec, state)

        assert result is state
        assert operation.rolled_back is True

    def test_rollback_failure(self, executor, operation, state):
        operation.fail_rollback = True
        spec = ExecutionSpec(operation=operation)

        with pytest.raises(ExecutionError):
            executor.rollback_sync(spec, state)

    def test_run_executor_apply(self, executor, operation, state):
        spec = ExecutionSpec(operation=operation)

        result = executor.apply_sync(spec)

        assert result.status == Status.COMPLETED
        assert operation.applied is True

    def test_run_executor_rollback(self, executor, operation, state):
        spec = ExecutionSpec(operation=operation)
        state.status = Status.FAILED
        result = executor.rollback_sync(spec, state)

        assert result is state
        assert operation.rolled_back is True


class TestExecutionSpec:
    def test_create_spec(self, operation):
        spec = ExecutionSpec(operation=operation)
        assert spec.operation is operation
        assert spec.dry_run is False
