from __future__ import annotations


from ox_orch.core.registry import register
from ox_orch.core.files import FileBackend
from ox_orch.core.trace import TraceEvent
from .base import ExecutorHook


__all__ = ("TraceHook",)


@register("trace")
class TraceHook(ExecutorHook):
    """
    Hook that records execution traces and optionally persists them.

    This replaces a dedicated trace subsystem.
    """

    def __init__(self, backend: FileBackend | None = None):
        self.backend = backend
        self.buffer: list[TraceEvent] = []

    def before_apply(self, operation, state, context):
        self._record(state, operation, "before_apply")

    def after_apply(self, operation, state):
        self._record(state, operation, "after_apply")

    def apply_failed(self, operation, state, error):
        self._record(state, operation, "apply_failed", str(error))

    def before_rollback(self, operation, state):
        self._record(state, operation, "before_rollback")

    def after_rollback(self, operation, state):
        self._record(state, operation, "after_rollback")

    def rollback_failed(self, operation, state, error):
        self._record(state, operation, "rollback_failed", str(error))

    def state_update(self, state):
        self._record(state, getattr(state, "_operation", None), "state_update")

    def _record(self, state, operation, phase: str, message: str | None = None, data=None):
        run_id = getattr(getattr(state, "run_context", None), "run_id", "unknown")

        event = TraceEvent(
            run_id=run_id,
            phase=phase,
            operation=getattr(operation, "__type_id__", str(operation)),
            state_id=getattr(state, "id", None),
            message=message,
            data=data or {},
        )

        self.buffer.append(event)

        if self.backend:
            self.backend.save(self.backend_path, self.buffer)
