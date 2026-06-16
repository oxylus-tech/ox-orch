import pytest

from ox_orch.operations import RunPython
from ox_orch.core.state import Status

from .conftest import apply, rollback, assert_states


@pytest.fixture
def op_state(op):
    return op.create_state()


@pytest.fixture
def pyop():
    return RunPython(
        operation_id="test",
        forward=lambda obj, *_, **__: obj.__dict__.update({"forwarded": True}),
        backward=lambda obj, *_, **__: obj.__dict__.update({"backwarded": True}),
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
        assert_states(states, [(op.id, Status.RUNNING), (op.id, Status.COMPLETED)])

    def test_apply_fail(self, op, op_state):
        exc = RuntimeError("test")
        states, exc_ = apply(op, op_state, exc=exc)

        assert exc_ is exc
        assert op_state.status == Status.FAILED
        assert op_state.error == str(exc)
        assert_states(
            states,
            [
                (op.id, Status.RUNNING),
                (op.id, Status.FAILED, str(exc)),
            ],
        )

    def test_rollback(self, op, op_state):
        op_state.status = Status.COMPLETED
        states, _ = rollback(op, op_state)

        assert op.rollbacked
        assert op_state.status == Status.ROLLED_BACK
        assert_states(states, [(op.id, Status.ROLLING_BACK), (op.id, Status.ROLLED_BACK)])

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
                (op.id, Status.ROLLING_BACK),
                (op.id, Status.FAILED, str(exc)),
            ],
        )

    # ---- Test context passthrough
    def test_context_passthrough_when_spec_none(self, op):
        context = {"a": 1, "b": 2, "c": 3}

        resolved = op._resolve_inputs(context, None, phase="apply")

        assert resolved == context

    def test_context_tuple_filters_keys(self, op):
        context = {"a": 1, "b": 2, "c": 3}

        op.__apply_spec__ = ("a", "c")

        resolved = op._resolve_inputs(context, op.__apply_spec__, phase="apply")

        assert resolved == {"a": 1, "c": 3}

    def test_context_tuple_missing_key_raises(self, op):
        context = {"a": 1}

        op.__apply_spec__ = ("a", "missing")

        with pytest.raises(KeyError):
            op._resolve_inputs(context, op.__apply_spec__, phase="apply")

    def test_context_typed_validation_success(self, op):
        context = {"registry": {"ok": True}, "apps": [1, 2, 3]}

        op.__apply_spec__ = {
            "registry": dict,
            "apps": list,
        }

        resolved = op._resolve_inputs(context, op.__apply_spec__, phase="apply")

        assert resolved == context

    def test_context_typed_validation_type_error(self, op):
        context = {"registry": "invalid"}

        op.__apply_spec__ = {
            "registry": dict,
        }

        with pytest.raises(TypeError):
            op._resolve_inputs(context, op.__apply_spec__, phase="apply")

    def test_context_rollback_spec_isolated(self, op):
        apply_context = {"registry": {"x": 1}, "apps": [1]}
        rollback_context = {"registry": {"x": 1}}

        op.__apply_spec__ = ("registry", "apps")
        op.__rollback_spec__ = ("registry",)

        apply_resolved = op._resolve_inputs(apply_context, op.__apply_spec__, phase="apply")
        rollback_resolved = op._resolve_inputs(rollback_context, op.__rollback_spec__, phase="rollback")

        assert "apps" in apply_resolved
        assert "apps" not in rollback_resolved
        assert "registry" in rollback_resolved


class TestRunPython:
    def test__apply(self, pyop, pyop_state):
        apply(pyop, pyop_state)
        assert pyop_state.status == Status.COMPLETED

    def test__rollback(self, pyop, pyop_state):
        pyop_state.status = Status.COMPLETED
        rollback(pyop, pyop_state)
        assert pyop_state.status == Status.ROLLED_BACK
