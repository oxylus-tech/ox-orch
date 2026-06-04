from __future__ import annotations

from collections import Counter

from ..core.state import State
from .base import ExecutorHook


__all__ = ("ProgressHook",)


class ProgressHook(ExecutorHook):
    """
    Collect execution progress information.

    This hook maintains simple counters that can be exposed through
    CLI progress bars, APIs, SSE streams, WebSockets, dashboards, etc.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Reset all counters.
        """
        self.total_updates = 0
        self.statuses = Counter()
        self.last_state = None

    @property
    def progress(self) -> dict:
        """
        Return current progress information.

        :returns: Progress snapshot.
        """
        return {
            "updates": self.total_updates,
            "statuses": dict(self.statuses),
            "last_state": self.last_state,
        }

    def before_apply(self, operation, state, context):
        """
        Reset progress for a new execution.
        """
        self.reset()

    def state_update(self, state: State):
        """
        Record a state update.

        :param state: Updated state.
        """
        self.total_updates += 1
        self.statuses[str(state.status)] += 1

        self.last_state = {
            "operation_id": getattr(state, "operation_id", None),
            "state_type": state.__type_id__,
            "name": state.name,
            "status": str(state.status),
        }

    def after_apply(self, operation, state):
        """
        Record final state.
        """
        self.state_update(state)

    def after_rollback(self, operation, state):
        """
        Record final rollback state.
        """
        self.state_update(state)
