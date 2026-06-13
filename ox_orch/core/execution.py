from __future__ import annotations

import logging
from typing import Any, Generator

from pydantic import BaseModel, Field

from ..operations import AbstractOperation, OperationState
from ..hooks import ExecutorHook, EXECUTOR_HOOK_REGISTRY
from .contexts import RunContext, ExecutionContext
from .events import HookEmitter
from .shell import ShellSpec, Shell
from .state import State


__all__ = ("ExecutionError", "ExecutionSpec", "Executor")


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
    hooks: list[str] = Field(default_factory=list)
    """ Hook class paths to load dynamically. """
    trigger: str = "cli"
    """ CLI / API / daemon / test. """
    dry_run: bool = False
    """ Run in dry mode. """
    shell: ShellSpec | None = None
    """ Subprocess cmd_runtime configuration. """
    inputs: dict[str, Any] = Field(default_factory=dict)
    """ User inputs injected into operations. """

    def get_run_context(self) -> RunContext:
        """Return a new RunContext based on spec."""
        return RunContext(trigger=self.trigger, dry_run=self.dry_run)


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
    hook_registry = EXECUTOR_HOOK_REGISTRY

    def apply(self, spec: ExecutionSpec) -> Generator[State, State]:
        """
        Execute an operation using the provided configuration.

        :param spec: the configuration;
        :returns: root state
        :raises ExecutionError: on failure
        """
        self.listen(spec.hooks, reset=True)

        run_context = spec.get_run_context()
        ctx = ExecutionContext(
            run=run_context,
            shell=Shell.from_spec(spec.shell),
            # data=spec.context
        )
        inputs = spec.inputs
        operation = spec.operation
        state = operation.create_state(run_context=run_context)

        self.emit("before_apply", operation, state, ctx)

        # Run
        try:
            run_context.start()
            for state in operation.apply(state, ctx, **inputs):
                self.emit("state_update", state=state)
                yield state

            run_context.finish()
            self.emit("after_apply", operation, state, ctx)
            return state

        except Exception as exc:
            logger.exception(
                "Operation execution failed",
                extra={"operation": operation.__type_id__},
            )
            self.emit("apply_failed", operation, state, exc)
            raise ExecutionError(str(exc)) from exc

    def rollback(self, spec: ExecutionSpec, state: OperationState) -> Generator[State, State]:
        """
        Rollback an operation.

        Rollback can be triggered manually, independently of automatic
        rollback performed after a failure.

        :param spec: execution configuration;
        :param state: operation state to rollback;
        :returns: root state
        :raises ExecutionError: on failure
        """
        self.listen(spec.hooks, reset=True)

        ctx = ExecutionContext(
            run=state.run_context or spec.get_run_context(),
            shell=Shell.from_spec(spec.shell),
        )
        operation = spec.operation

        self.emit("before_rollback", operation, state, ctx)

        try:
            for state in operation.rollback(state, ctx):
                self.emit("state_update", state=state)
                yield state

            self.emit("after_rollback", operation, state, ctx)
            return state

        except Exception as exc:
            logger.exception(
                "Operation rollback failed",
                extra={"operation": operation.__type_id__},
            )
            self.emit("rollback_failed", operation, state, exc)
            raise ExecutionError(str(exc)) from exc

    def apply_sync(self, spec: ExecutionSpec) -> State:
        """Apply and return the final state."""
        gen = self.apply(spec)
        return self._consume_sync(gen)

    def rollback_sync(self, spec: ExecutionSpec, state: OperationState) -> State:
        """Rollback and return the final state."""
        gen = self.rollback(spec, state)
        return self._consume_sync(gen)

    def _consume_sync(self, gen) -> State:
        """Consume generator and return the result."""
        while True:
            try:
                next(gen)
            except StopIteration as exc:
                return exc.value
