import logging

from ox_orch.hooks.logging import LoggingHook


class TestLoggingHook:
    def test_before_apply(self, caplog, op, op_state):
        hook = LoggingHook()

        with caplog.at_level(logging.INFO):
            hook.before_apply(op, op_state, {})

        assert "Starting operation" in caplog.text

    def test_after_apply(self, caplog, op, op_state):
        hook = LoggingHook()

        with caplog.at_level(logging.INFO):
            hook.after_apply(op, op_state)

        assert "Operation completed" in caplog.text

    def test_before_rollback(self, caplog, op, op_state):
        hook = LoggingHook()

        with caplog.at_level(logging.INFO):
            hook.before_rollback(op, op_state)

        assert "Starting rollback" in caplog.text

    def test_after_rollback(self, caplog, op, op_state):
        hook = LoggingHook()

        with caplog.at_level(logging.INFO):
            hook.after_rollback(op, op_state)

        assert "Rollback completed" in caplog.text

    def test_apply_failed(self, caplog, op, op_state):
        hook = LoggingHook()

        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            with caplog.at_level(logging.ERROR):
                hook.apply_failed(op, op_state, exc)

        assert "Operation failed" in caplog.text

    def test_rollback_failed(self, caplog, op, op_state):
        hook = LoggingHook()

        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            with caplog.at_level(logging.ERROR):
                hook.rollback_failed(op, op_state, exc)

        assert "Rollback failed" in caplog.text

    def test_state_update(self, caplog, op_state):
        hook = LoggingHook()

        with caplog.at_level(logging.DEBUG):
            hook.state_update(op_state)

        assert "State updated" in caplog.text
