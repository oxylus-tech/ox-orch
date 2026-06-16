""" Provide hooks that can be reused with the executor. """

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from ox_orch.core.events import Hook
from ox_orch.core.stores import Store
from ox_orch.core.registry import Registry, RegisteredClass, register


__all__ = ("ExecutorHook", "RecordingHook", "PersistStateHook")


EXECUTOR_HOOK_REGISTRY = Registry()


class ExecutorHook(Hook, RegisteredClass):
    """
    Base hook class used by the runtime executor.

    Hooks can be registered on the executor to observe execution,
    persist states, report progress, emit logs, send notifications,
    expose API events, etc.
    """

    __registry__ = EXECUTOR_HOOK_REGISTRY

    def before_apply(self, operation, state, context):
        """
        Called before an operation execution starts.

        :param operation: operation being executed
        :param state: root operation state
        :param context: execution context
        """
        pass

    def after_apply(self, operation, state, context):
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

    def before_rollback(self, operation, state, context):
        """
        Called before rollback starts.

        :param operation: operation being rolled back
        :param state: root operation state
        """
        pass

    def after_rollback(self, operation, state, context):
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


@register("recording")
class RecordingHook(ExecutorHook):
    """Record every call into :py:attr:`events`."""

    events: list[tuple[str, Any]]
    """ Recorded events. """

    def __init__(self):
        self.events = []

    def before_apply(self, operation, state, context):
        self.events.append(("before_apply", state.status))

    def after_apply(self, operation, state, context):
        self.events.append(("after_apply", state.status))

    def apply_failed(self, operation, state, error):
        self.events.append(("apply_failed", str(error)))

    def before_rollback(self, operation, state, context):
        self.events.append(("before_rollback", state.status))

    def after_rollback(self, operation, state, context):
        self.events.append(("after_rollback", state.status))

    def rollback_failed(self, operation, state, error):
        self.events.append(("rollback_failed", str(error)))


@register("persist-state")
@dataclass
class PersistStateHook(ExecutorHook):
    """Persist state to the specified file."""

    store: Store
    auto_save: bool = False

    def state_update(self, state):
        if not state._source:
            raise ValueError("State `_source` must be set to the target file path.")
        self.store.commit([state])

        if self.auto_save:
            if not hasattr(self.store, "save"):
                raise ValueError("Store misses save() method.")
            self.store.save()
