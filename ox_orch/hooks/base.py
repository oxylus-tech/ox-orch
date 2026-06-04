""" Provide hooks that can be reused with the executor. """

from __future__ import annotations
from typing import Any

from ..core.events import Hook
from ..core.state import StateBackend


__all__ = ("ExecutorHook", "RecordingHook", "PersistStateHook")


class ExecutorHook(Hook):
    """
    Base hook class used by the runtime executor.

    Hooks can be registered on the executor to observe execution,
    persist states, report progress, emit logs, send notifications,
    expose API events, etc.
    """

    def before_apply(self, operation, state, context):
        """
        Called before an operation execution starts.

        :param operation: operation being executed
        :param state: root operation state
        :param context: execution context
        """
        pass

    def after_apply(self, operation, state):
        """
        Called after a successful execution.

        :param operation: executed operation
        :param state: root operation state
        """
        pass

    def apply_failed(self, operation, state, error):
        """
        Called when execution fails.

        :param operation: executed operation
        :param state: root operation state
        :param error: raised exception
        """
        pass

    def before_rollback(self, operation, state):
        """
        Called before rollback starts.

        :param operation: operation being rolled back
        :param state: root operation state
        """
        pass

    def after_rollback(self, operation, state):
        """
        Called after a successful rollback.

        :param operation: rolled back operation
        :param state: root operation state
        """
        pass

    def rollback_failed(self, operation, state, error):
        """
        Called when rollback fails.

        :param operation: rolled back operation
        :param state: root operation state
        :param error: raised exception
        """
        pass

    def state_update(self, state):
        """
        Called whenever an operation yields a state update.

        This includes nested operations executed by plans.

        :param state: yielded state
        """
        pass


class RecordingHook(ExecutorHook):
    """Record every call into :py:attr:`events`."""

    events: list[tuple[str, Any]]
    """ Recorded events. """

    def __init__(self):
        self.events = []

    def before_apply(self, operation, state, context):
        self.events.append(("before_apply", state.status))

    def after_apply(self, operation, state):
        self.events.append(("after_apply", state.status))

    def apply_failed(self, operation, state, error):
        self.events.append(("apply_failed", str(error)))

    def before_rollback(self, operation, state):
        self.events.append(("before_rollback", state.status))

    def after_rollback(self, operation, state):
        self.events.append(("after_rollback", state.status))

    def rollback_failed(self, operation, state, error):
        self.events.append(("rollback_failed", str(error)))


class PersistStateHook(ExecutorHook):
    """Persist state to the specified file."""

    backend: StateBackend

    def state_update(self, state):
        if not state._source:
            raise ValueError("State `_source` must be set to the target file path.")
        self.backend.save(state)
