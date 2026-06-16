import pytest

from ox_orch.hooks.base import ExecutorHook, RecordingHook, PersistStateHook
from ox_orch.core import MemoryStore
from ox_orch.operations import OperationState


class TestExecutorHook:
    def test_executor_hook_methods_are_noop(self, op, op_state):
        """
        ExecutorHook methods should not raise and should be no-ops by default.
        """
        hook = ExecutorHook()

        hook.before_apply(op, op_state, {})
        hook.after_apply(op, op_state, {})
        hook.apply_failed(op, op_state, RuntimeError("fail"))

        hook.before_rollback(op, op_state, {})
        hook.after_rollback(op, op_state, {})
        hook.rollback_failed(op, op_state, RuntimeError("fail"))

        hook.state_update(op_state)

        assert True  # just ensuring no exceptions


class TestRecordingHook:
    def test_before_apply_records_event(self, op, op_state):
        hook = RecordingHook()

        hook.before_apply(op, op_state, {})

        assert hook.events == [("before_apply", op_state.status)]

    def test_after_apply_records_event(self, op, op_state):
        hook = RecordingHook()

        hook.after_apply(op, op_state, {})

        assert hook.events == [("after_apply", op_state.status)]

    def test_apply_failed_records_error(self, op, op_state):
        hook = RecordingHook()

        hook.apply_failed(op, op_state, RuntimeError("boom"))

        assert hook.events == [("apply_failed", "boom")]

    def test_before_rollback_records_event(self, op, op_state):
        hook = RecordingHook()

        hook.before_rollback(op, op_state, {})

        assert hook.events == [("before_rollback", op_state.status)]

    def test_after_rollback_records_event(self, op, op_state):
        hook = RecordingHook()

        hook.after_rollback(op, op_state, {})

        assert hook.events == [("after_rollback", op_state.status)]

    def test_rollback_failed_records_error(self, op, op_state):
        hook = RecordingHook()

        hook.rollback_failed(op, op_state, RuntimeError("boom"))

        assert hook.events == [("rollback_failed", "boom")]

    def test_multiple_events_append_in_order(self, op, op_state):
        hook = RecordingHook()

        hook.before_apply(op, op_state, {})
        hook.after_apply(op, op_state, {})
        hook.before_rollback(op, op_state, {})

        assert len(hook.events) == 3
        assert hook.events[0][0] == "before_apply"
        assert hook.events[1][0] == "after_apply"
        assert hook.events[2][0] == "before_rollback"


class TestPersistStateHook:
    def test_state_update_saves_state(self, op_state):
        store = MemoryStore(OperationState)
        hook = PersistStateHook(store=store)

        op_state._source = "/tmp/state.yml"
        hook.state_update(op_state)
        assert len(store.data) == 1

    def test_state_update_requires_source(self, op_state):
        store = MemoryStore(OperationState)
        hook = PersistStateHook(store=store)
        hook.store = store

        op_state._source = None

        with pytest.raises(ValueError):
            hook.state_update(op_state)
