""" Provide hooks that can be reused with the executor. """

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from ox_orch.core.execution import ExecutorHook, EXECUTOR_HOOK_REGISTRY
from ox_orch.core.stores import Store
from ox_orch.core.registry import register


__all__ = ("EXECUTOR_HOOK_REGISTRY", "ExecutorHook", "RecordingHook", "PersistStateHook")


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
