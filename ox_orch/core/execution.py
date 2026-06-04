from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..operations import AbstractOperation, RunContext
from ..hooks import ExecutorHook
from .events import HookEmitter
from .state import State


__all__ = ("ExecutionError", "Executor")


logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """
    Raised when an operation execution or rollback fails.
    """


class ExecutionSpec(BaseModel):
    """
    Full description of an execution request.

    This is the single source of truth for:
    - operation
    - state
    - context
    - hooks
    - run metadata
    """

    operation: str
    """ Operation import path or __type_id__ reference. """
    state_path: str | None = None
    """ Optional persisted state file. """
    context: dict[str, Any] = Field(default_factory=dict)
    """ Execution context injected into operations. """
    hooks: list[str] = Field(default_factory=list)
    """ Hook class paths to load dynamically. """
    run_trigger: str = "cli"
    """ CLI / API / daemon / test. """


class Executor(HookEmitter):
    """
    Runtime execution engine.

    Responsibilities:

    - initialize root execution context
    - invoke operation apply/rollback entrypoints
    - emit execution hooks
    - expose state updates emitted by operations

    Responsibilities intentionally NOT handled here:

    - operation recursion
    - plan traversal
    - rollback orchestration
    - context resolution

    Those concerns belong to the operation layer itself.
    """

    hook_class = ExecutorHook

    def apply(
        self,
        operation: AbstractOperation,
        *,
        state: State | None = None,
        context: dict[str, Any] | None = None,
        run_context: RunContext | None = None,
    ) -> State:
        """
        Execute an operation.

        :param operation: operation to execute
        :param state: optional pre-existing state
        :param context: execution context
        :param run_context: execution metadata
        :returns: root state
        :raises ExecutionError: on failure
        """
        context = context or {}

        if state is None:
            state = operation.create_state()

        run_context = run_context or RunContext()

        if run_context.started_at is None:
            run_context.started_at = datetime.utcnow()

        state.run_context = run_context

        self.emit("before_apply", operation=operation, state=state, context=context)

        try:
            result = operation.apply(state=state, **context)

            self._consume_result(result)

            run_context.finished_at = datetime.utcnow()

            self.emit(
                "after_apply",
                operation=operation,
                state=state,
            )

            return state

        except Exception as exc:
            logger.exception(
                "Operation execution failed",
                extra={
                    "operation": operation.__type_id__,
                },
            )

            self.emit(
                "apply_failed",
                operation=operation,
                state=state,
                error=exc,
            )

            raise ExecutionError(str(exc)) from exc

    def rollback(
        self,
        operation: AbstractOperation,
        state: State,
        *,
        context: dict[str, Any] | None = None,
    ) -> State:
        """
        Rollback an operation.

        Rollback can be triggered manually, independently of automatic
        rollback performed after a failure.

        :param operation: operation to rollback
        :param state: operation state
        :param context: execution context
        :returns: root state
        :raises ExecutionError: on failure
        """
        context = context or {}

        self.emit(
            "before_rollback",
            operation=operation,
            state=state,
        )

        try:
            result = operation.rollback(
                state=state,
                **context,
            )

            self._consume_result(result)

            self.emit(
                "after_rollback",
                operation=operation,
                state=state,
            )

            return state

        except Exception as exc:
            logger.exception(
                "Operation rollback failed",
                extra={
                    "operation": operation.__type_id__,
                },
            )
            self.emit(
                "rollback_failed",
                operation=operation,
                state=state,
                error=exc,
            )

            raise ExecutionError(str(exc)) from exc

    def _consume_result(self, result):
        """
        Consume operation yielded states.

        Operations and plans may yield state updates during execution.
        Each yielded state is forwarded to registered hooks.

        :param result: operation result
        """
        if result is None:
            return

        if isinstance(result, (str, bytes)):
            return

        try:
            iterator = iter(result)
        except TypeError:
            return

        for state in iterator:
            self.emit(
                "state_update",
                state=state,
            )
