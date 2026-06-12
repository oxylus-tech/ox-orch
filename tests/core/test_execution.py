import pytest

from ox_orch.core.execution import Executor, ExecutionError, ExecutionSpec, run_executor
from ox_orch.core.state import Status
from ox_orch.operations import AbstractOperation
from ox_orch.operations.base import RunContext


class FakeOperation(AbstractOperation):
    """
    Minimal operation used to test Executor behavior.
    """

    __type_id__ = "op:test:fake"

    applied: bool = False
    rolled_back: bool = False
    fail_apply: bool = False
    fail_rollback: bool = False

    def _apply(self, state, **context):
        if self.fail_apply:
            raise RuntimeError("apply failed")
        self.applied = True
        yield state

    def _rollback(self, state, **context):
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
def executor():
    return Executor()


class TestExecutor:
    def test_apply_success(self, executor, operation, state):
        run_context = RunContext()
        result = executor.apply(operation, run_context, state=state)

        assert result is state
        assert operation.applied is True
        assert state.run_context is not None
        assert state.status.name == "COMPLETED"

    def test_apply_with_context(self, executor, operation, state):
        def _apply(self, state, value=None, **_):
            state._value = value
            yield state

        operation._apply = _apply.__get__(operation, FakeOperation)

        run_context = RunContext()
        executor.apply(operation, run_context, state=state, context={"value": 42})

        assert state._value == 42

    def test_apply_failure(self, executor, operation, state):
        operation.fail_apply = True

        run_context = RunContext()
        with pytest.raises(ExecutionError):
            executor.apply(operation, run_context, state=state)

        assert state.status.name == "FAILED"

    def test_rollback_success(self, executor, operation, state):
        state.status = Status.COMPLETED

        result = executor.rollback(operation, state)

        assert result is state
        assert operation.rolled_back is True

    def test_rollback_failure(self, executor, operation, state):
        operation.fail_rollback = True
        state.status = Status.COMPLETED

        with pytest.raises(ExecutionError):
            executor.rollback(operation, state)

        assert state.status.name == "FAILED"

    def test_consume_result_non_iterable(self, executor):
        # should not raise
        executor._consume_result(None)
        executor._consume_result("string")
        executor._consume_result(123)


class TestExecutionSpec:
    def test_create_spec(self, operation):
        spec = ExecutionSpec(operation=operation)

        assert spec.operation is operation
        assert spec.dry_run is False
        assert isinstance(spec.context, dict)

    def test_spec_context_storage(self, operation):
        spec = ExecutionSpec(operation=operation, context={"a": 1})

        assert spec.context["a"] == 1


class TestRunExecutor:
    def test_run_executor_apply(self, operation, state):
        spec = ExecutionSpec(operation=operation, state=state)

        result = run_executor(spec, action="apply")

        assert result is state
        assert operation.applied is True

    def test_run_executor_rollback(self, operation, state):
        state.status = Status.COMPLETED

        spec = ExecutionSpec(operation=operation, state=state)

        result = run_executor(spec, action="rollback")

        assert result is state
        assert operation.rolled_back is True

    def test_run_executor_missing_state_on_rollback(self, operation):
        spec = ExecutionSpec(operation=operation, state=None)

        with pytest.raises(ValueError):
            run_executor(spec, action="rollback")

    def test_run_executor_invalid_action(self, operation):
        spec = ExecutionSpec(operation=operation)

        with pytest.raises(ValueError):
            run_executor(spec, action="invalid")
