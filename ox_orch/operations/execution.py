from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Generator

from pydantic import Field, field_validator

from ox_orch.operations import Operation, OperationState
from ox_orch.hooks import ExecutorHook, EXECUTOR_HOOK_REGISTRY
from ox_orch.core import ContextInput, ContextInputs, Context, RunContext, CONTEXT_INPUT_REGISTRY, register, State
from ox_orch.core.events import HookEmitter
from ox_orch.core.shell import ShellSpec, Shell


__all__ = ("ExecutionError", "ExecutionSpec", "Executor")


logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """
    Raised when an operation execution or rollback fails.
    """


# FIXME: later reuse the ContextInput mechanisms on the spec itself?
@register("execution")
class ExecutionSpec(ContextInput):
    """
    A full specification of an execution request.

    It is used by the :py:class:`Executor` to

    This is the single source of truth for:
    - operation
    - state
    - context
    - hooks
    - run metadata
    """

    operation: Operation
    """ Operation to run. """
    hooks: list[str] = Field(default_factory=list)
    """ Hook class paths to load dynamically. """
    trigger: str = "cli"
    """ CLI / API / daemon / test. """
    dry_run: bool = False
    """ Run in dry mode. """
    shell: ShellSpec | None = None
    """ Shell cmd_runtime configuration. """
    inputs: dict[str, ContextInput] = Field(default_factory=dict)
    """ User inputs arguments. """

    @field_validator("inputs", mode="before")
    @classmethod
    def _context_inputs_cls(cls, data):
        """
        Ensure inputs are initialized using the right ContextInput class.

        This allows convenient formatting, without having to provide the
        polymorphic serialization format.
        """
        if isinstance(data, dict):
            for key, values in data.items():
                if isinstance(values, dict):
                    input_cls = CONTEXT_INPUT_REGISTRY.get(key)
                    data[key] = input_cls.model_validate(values)
        return data

    def get_run_context(self) -> RunContext:
        """Return a new RunContext based on spec."""
        return RunContext(trigger=self.trigger, dry_run=self.dry_run)

    def build_context(self, context_inputs=None, run_context=None, **kwargs):
        """
        Return a new ExecutionContext from self.

        It does not create contexts for nested input contexts.
        """
        return ExecutionContext(
            run=run_context or self.get_run_context(),
            shell=Shell.from_spec(self.shell),
            spec=self,
        )


@dataclass
class ExecutionContext(Context):
    """
    Runtime-only orchestration data shared across all operations.

    This object is not persisted nor serialized.
    """

    run: RunContext = field(default_factory=RunContext)
    """ The current run context for operations. """
    spec: ExecutionSpec = None
    """ An execution specification. """
    shell: Shell | None = field(default_factory=lambda: Shell.from_spec())
    """ Shell backend used to run commands. """
    data: dict[str, Any] = field(default_factory=dict)
    """ Extra input data. """

    def get(self, key: str, default=None) -> Any:
        """Return data by key."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        """Set data to the context."""
        self.data[key] = value


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

    def apply(self, spec: ExecutionSpec, **contexts: dict[str, ContextInput]) -> Generator[State, State]:
        """
        Execute an operation using the provided configuration.

        :param spec: the configuration;
        :param inputs: extra context inputs;
        :returns: root state
        :raises ExecutionError: on failure
        """
        self.listen(spec.hooks, reset=True)

        run_context = spec.get_run_context()
        ctx = spec.build_context()

        contexts["exec_ctx"] = ctx
        context_inputs = ContextInputs(inputs=spec.inputs, contexts=contexts)
        context_inputs.build()
        operation = spec.operation
        state = operation.create_state(run_context=run_context)

        self.emit("before_apply", operation, state, ctx)

        # Run
        try:
            run_context.start()
            for state in operation.apply(state, **context_inputs.contexts):
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

    def rollback(
        self, spec: ExecutionSpec, state: OperationState, **contexts: dict[str, ContextInput]
    ) -> Generator[State, State]:
        """
        Rollback an operation.

        Rollback can be triggered manually, independently of automatic
        rollback performed after a failure.

        :param spec: execution configuration;
        :param state: operation state to rollback;
        :param inputs: extra context inputs;
        :returns: root state
        :raises ExecutionError: on failure
        """
        self.listen(spec.hooks, reset=True)

        ctx = spec.build_context(run=state.run_context)

        contexts["exec_ctx"] = ctx
        context_inputs = ContextInputs(inputs=spec.inputs, contexts=contexts)
        context_inputs.build()
        operation = spec.operation

        self.emit("before_rollback", operation, state, ctx)

        try:
            for state in operation.rollback(state, **context_inputs.contexts):
                self.emit("state_update", state=state)
                yield state

            self.emit("after_rollback", operation, state, ctx)
            return state

        except Exception as exc:
            import traceback

            traceback.print_exc()

            logger.exception(
                "Operation rollback failed",
                extra={"operation": operation.__type_id__},
            )
            self.emit("rollback_failed", operation, state, exc)
            raise ExecutionError(str(exc)) from exc

    def apply_sync(self, spec: ExecutionSpec, **inputs) -> State:
        """Apply and return the final state."""
        gen = self.apply(spec, **inputs)
        return self._consume_sync(gen)

    def rollback_sync(self, spec: ExecutionSpec, state: OperationState, **inputs) -> State:
        """Rollback and return the final state."""
        gen = self.rollback(spec, state, **inputs)
        return self._consume_sync(gen)

    def _consume_sync(self, gen) -> State:
        """Consume generator and return the result."""
        while True:
            try:
                next(gen)
            except StopIteration as exc:
                return exc.value
