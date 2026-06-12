from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..operations import AbstractOperation, RunContext, OperationState
from ..hooks import ExecutorHook, EXECUTOR_HOOK_REGISTRY
from .events import HookEmitter
from .shell import ShellSpec, Shell, LocalShell, SHELL_REGISTRY
from .state import State


__all__ = ("ExecutionError", "ExecutionSpec", "Executor", "run_executor")


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

    operation: AbstractOperation
    """ Operation import path or __type_id__ reference. """
    state: OperationState | None = None
    """ Optional persisted state file. """
    context: dict[str, Any] = Field(default_factory=dict)
    """ Execution context injected into operations. """
    hooks: list[str] = Field(default_factory=list)
    """ Hook class paths to load dynamically. """
    trigger: str = "cli"
    """ CLI / API / daemon / test. """
    dry_run: bool = False
    """ Run in dry mode. """
    shell: ShellSpec | None = None
    """ Subprocess cmd_runtime configuration. """


class Executor(HookEmitter):
    """
    Runtime execution engine.

    Responsibilities:

    - initialize root execution context
    - invoke operation apply/rollback entrypoints
    - emit execution hooks
    - expose state updates emitted by operations
    """

    hook_class = ExecutorHook

    def __init__(self, hooks=None):
        self.hooks = []
        hooks and self.listen(*hooks)

    def apply(
        self,
        operation: AbstractOperation,
        run_context: RunContext,
        *,
        state: State | None = None,
        context: dict[str, Any] | None = None,
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

        # Inits & context
        context = context or {}
        if state is None:
            state = operation.create_state()

        # Run context
        run_context = run_context or RunContext()
        if run_context.started_at is None:
            run_context.started_at = datetime.utcnow()
        state.run_context = run_context

        self.emit("before_apply", operation=operation, state=state, context=context)

        # Run
        try:
            result = operation.apply(state=state, **context)
            self._consume_result(result)
            run_context.finished_at = datetime.utcnow()
            self.emit("after_apply", operation=operation, state=state)
            return state

        except Exception as exc:
            logger.exception(
                "Operation execution failed",
                extra={"operation": operation.__type_id__},
            )
            self.emit("apply_failed", operation=operation, state=state, error=exc)
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
        # Init & context
        context = context or {}
        # Run
        self.emit("before_rollback", operation=operation, state=state)

        try:
            context.setdefault("run_context", state.run_context)
            result = operation.rollback(state=state, **context)
            self._consume_result(result)
            self.emit("after_rollback", operation=operation, state=state)
            return state

        except Exception as exc:
            logger.exception(
                "Operation rollback failed",
                extra={"operation": operation.__type_id__},
            )
            self.emit("rollback_failed", operation=operation, state=state, error=exc)
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
            self.emit("state_update", state=state)


def run_executor(
    spec: ExecutionSpec,
    action: Literal["apply", "rollback"] = "apply",
) -> State:
    """
    Execute an operation according to the provided specification.

    This helper is intended to be the main entrypoint used by cli, api, daemon
    and scheduler.

    It is responsible for:

    - hook resolution
    - executor creation
    - run context creation
    - dispatching apply/rollback execution

    :param spec: execution specification
    :param action: execution action
    :returns: root state
    """
    hooks = [EXECUTOR_HOOK_REGISTRY.get(name)() for name in spec.hooks]

    executor = Executor(hooks=hooks)
    context = dict(spec.context)
    context["shell"] = _resolve_cmd_runtime(spec)

    match action:
        case "apply":
            if spec.operation is None:
                raise ValueError("Operation is required for apply.")

            run_context = RunContext(trigger=spec.trigger, dry_run=spec.dry_run)
            return executor.apply(
                spec.operation,
                state=spec.state,
                context=context,
                run_context=run_context,
            )
        case "rollback":
            if spec.operation is None:
                raise ValueError("Operation is required for rollback.")

            if spec.state is None:
                raise ValueError("State is required for rollback.")

            if spec.state and spec.state.run_context:
                spec.state.run_context = spec.state.run_context.model_copy(update={"dry_run": spec.dry_run})

            return executor.rollback(
                spec.operation,
                spec.state,
                context=context,
            )
        case _:
            raise ValueError(f"Unsupported action '{action}'.")


def _resolve_cmd_runtime(spec: ExecutionSpec) -> Shell:
    """From provided execution spec, return the cmd_runtime runtime to use."""
    if spec.shell is None:
        return LocalShell(ShellSpec())

    backend = SHELL_REGISTRY.get(spec.shell.backend)
    if backend is None:
        raise ValueError(f"Unknown cmd_runtime backend: {spec.cmd_runtime.backend}")
    return backend(spec.shell)
