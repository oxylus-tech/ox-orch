import pytest

from django_installer.core.operations import RunPython
from django_installer.core.state import Status

from .conftest import apply, rollback, assert_states


@pytest.fixture
def op_state(op):
    return op.create_state()


@pytest.fixture
def pyop():
    return RunPython(
        operation_id="test",
        forward=lambda obj, **kw: obj.__dict__.update({"forwarded": True}),
        backward=lambda obj, **kw: obj.__dict__.update({"backwarded": True}),
    )


@pytest.fixture
def pyop_state(pyop):
    return pyop.create_state()


class TestAbstractOperation:
    def test_create_state(self, op):
        state = op.create_state()
        op.validate_state(state)

    def test_validate_state_no_op(self, op, op_state):
        op.validate_state(op_state)
        assert op_state._operation == op

    def test_validate_state_invalid_operation_id(self, op, op_state):
        with pytest.raises(ValueError):
            op_state.operation_id = "wrong operation_id"
            op.validate_state(op_state)

    def test_apply(self, op, op_state):
        states, _ = apply(op, op_state)

        assert op.applied
        assert op_state.status == Status.COMPLETED
        assert_states(states, [(op.operation_id, Status.RUNNING), (op.operation_id, Status.COMPLETED)])

    def test_apply_fail(self, op, op_state):
        exc = RuntimeError("test")
        states, exc_ = apply(op, op_state, exc=exc)

        assert exc_ is exc
        assert op_state.status == Status.FAILED
        assert op_state.error == str(exc)
        assert_states(
            states,
            [
                (op.operation_id, Status.RUNNING),
                (op.operation_id, Status.FAILED, str(exc)),
            ],
        )

    def test_rollback(self, op, op_state):
        op_state.status = Status.COMPLETED
        states, _ = rollback(op, op_state)

        assert op.rollbacked
        assert op_state.status == Status.ROLLED_BACK
        assert_states(states, [(op.operation_id, Status.ROLLING_BACK), (op.operation_id, Status.ROLLED_BACK)])

    def test_rollback_fail(self, op, op_state):
        op_state.status = Status.COMPLETED
        exc = RuntimeError("test")
        states, exc_ = rollback(op, op_state, rexc=exc)

        assert exc_ is exc
        assert op_state.status == Status.FAILED
        assert op_state.error == str(exc)
        assert_states(
            states,
            [
                (op.operation_id, Status.ROLLING_BACK),
                (op.operation_id, Status.FAILED, str(exc)),
            ],
        )


class TestRunPython:
    def test__apply(self, pyop, pyop_state):
        apply(pyop, pyop_state)
        assert pyop_state.status == Status.COMPLETED

    def test__rollback(self, pyop, pyop_state):
        pyop_state.status = Status.COMPLETED
        rollback(pyop, pyop_state)
        assert pyop_state.status == Status.ROLLED_BACK
