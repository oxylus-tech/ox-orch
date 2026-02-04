import pytest

from django_installer.core.operations import RunPython
from django_installer.core.state import State


@pytest.fixture
def op_state(op):
    return op.create_state()


@pytest.fixture
def pyop():
    return RunPython(
        name="test",
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

    def test_validate_state_invalid_name(self, op, op_state):
        with pytest.raises(ValueError):
            op_state.name = "wrong name"
            op.validate_state(op_state)

    def test_apply(self, op, op_state):
        op.apply(op_state)
        assert op.applied
        assert op_state.state == State.DONE

    def test_apply_fail(self, op, op_state):
        exc = RuntimeError("test")
        with pytest.raises(RuntimeError):
            op.apply(op_state, exc=exc)

        assert op_state.state == State.FAILED
        assert op_state.error == str(exc)

    def test_rollback(self, op, op_state):
        op.rollback(op_state)
        assert op.rollbacked
        assert op_state.state == State.ROLLED_BACK

    def test_rollback_fail(self, op, op_state):
        exc = RuntimeError("test")
        with pytest.raises(RuntimeError):
            op.rollback(op_state, rexc=exc)

        assert op_state.state == State.FAILED
        assert op_state.error == str(exc)


class TestRunPython:
    def test__apply(self, pyop, pyop_state):
        pyop.apply(pyop_state)
        assert pyop_state.state == State.DONE

    def test__rollback(self, pyop, pyop_state):
        pyop.rollback(pyop_state)
        assert pyop_state.state == State.ROLLED_BACK
