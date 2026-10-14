from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Generator, Callable

from pydantic import Field, model_validator

from ox_orch.utils import load_modules

from .contexts import ContextInput, ContextInputs, Context, RunContext, RawContextInputs
from .operation import (
    Operation,
    OperationState,
    OperationPhase,
    InspectResult,
    Action,
    Policy,
    DefaultPolicy,
    POLICY_REGISTRY,
)
from .registry import register, DocumentedRegistry, DocumentedClass
from .state import State
from .events import HookEmitter, Hook
from .shell import ShellSpec, Shell


__all__ = ("ExecutionError", "EXECUTOR_HOOK_REGISTRY", "ExecutorHook", "ExecutionContext", "ExecutionSpec", "Executor")


logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """
    Raised when an operation execution or rollback fails.
    """


EXECUTOR_HOOK_REGISTRY = DocumentedRegistry("Hooks", description="Hooks called on workflow execution.")

DecisionCallback = Callable[[InspectResult, OperationPhase], Action]
"""
Callback used by the executor to decide which action to take when operation yields
an inspect result.
"""


class ExecutorHook(Hook, DocumentedClass):
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


@register("execution")
class ExecutionSpec(ContextInput):
    """
    A full specification of an execution request.

    This is used to provide the :py:class:`Executor` all required information
    about operation to run. It is mapped into an :py:class:`ExecutionContext`
    that is passed down to the operations.

    This is the single source of truth for:

    - operation
    - state
    - context
    - hooks
    - run metadata
    """

    name: str = Field(default="", description="Workflow name")
    """ Spec's name (informative purpose). """
    description: str = Field(default="", description="A brief description of what it does")
    """ Spec's description (informative purpose). """

    operation: Operation = Field(description="The operation to execute.")
    """ Operation to run. """
    hooks: list[str] = Field(default_factory=list, description="A list of hooks.")
    """ Hook class paths to load dynamically. """
    trigger: str = Field(default="cli", description="What triggered the operation.")
    """ CLI / API / daemon / test. """
    dry_run: bool = Field(default=False, description="Run in dry mode. Nothing shall be affected.")
    """ Run in dry mode. """
    shell: ShellSpec | None = Field(default=None, description="Specify a shell environment.")
    """ Shell cmd_runtime configuration. """
    modules: list[str] = Field(
        default_factory=list, description="A list of module path to load (allows operation and hooks registration."
    )
    """ List of python modules to load before model is validated. """
    policy: str = Field(default="default")
    """ Operations' policy to use. """

    @model_validator(mode="before")
    @classmethod
    def _load_modules(cls, data):
        if modules := data.get("modules"):
            # TODO: modules validation
            load_modules(modules)
        return data

    def build_context(self, context_inputs=None, run_context=None, policy: Policy | None = None, **kwargs):
        """
        Return a new ExecutionContext from self.

        It does not create contexts for nested input contexts.
        """
        return ExecutionContext(
            run=run_context or self.get_run_context(),
            shell=Shell.from_spec(self.shell),
            spec=self,
            policy=policy or POLICY_REGISTRY.get(self.policy),
        )

    def get_run_context(self) -> RunContext:
        """Return a new RunContext based on spec."""
        return RunContext(trigger=self.trigger, dry_run=self.dry_run)


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
    policy: Policy = field(default_factory=DefaultPolicy)


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

    # TODO: later make "spec" optional as it may be provided through inputs
    def apply(
        self,
        spec: ExecutionSpec,
        inputs: RawContextInputs | None = None,
        *,
        policy: Policy | None = None,
        decide: DecisionCallback | None = None,
        **contexts: dict[str, ContextInput],
    ) -> Generator[State, State]:
        """
        Execute an operation using the provided configuration.

        :param spec: the configuration;
        :param inputs: extra context inputs;
        :returns: root state
        :raises ExecutionError: on failure
        """
        self.listen(spec.hooks, reset=True)

        run_context = spec.get_run_context()
        ctx = spec.build_context(policy=policy)

        contexts["execution"] = ctx
        context_inputs = ContextInputs(inputs=inputs, contexts=contexts)
        context_inputs.build()
        operation = spec.operation
        state = operation.create_state(run_context=run_context)

        self.emit("before_apply", operation, state, ctx)

        # Run
        try:
            run_context.start()
            gen = operation.apply(state, context_inputs.contexts)
            yield from self._drive(gen, decide, OperationPhase.APPLY)

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
        self,
        spec: ExecutionSpec,
        state: OperationState,
        inputs: RawContextInputs | None = None,
        *,
        policy: Policy | None = None,
        decide: DecisionCallback | None = None,
        **contexts: dict[str, ContextInput],
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

        ctx = spec.build_context(run=state.run_context, policy=policy)

        contexts["execution"] = ctx
        context_inputs = ContextInputs(inputs=inputs, contexts=contexts)
        context_inputs.build()
        operation = spec.operation

        self.emit("before_rollback", operation, state, ctx)

        try:
            gen = operation.rollback(state, context_inputs.contexts)
            yield from self._drive(gen, decide, OperationPhase.APPLY)

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

    def _drive(
        self,
        generator,
        decide: DecisionCallback | None = None,
        phase: OperationPhase = OperationPhase.APPLY,
    ) -> Generator[State | InspectResult, Action, State]:
        """
        Drive an operation generator and handle inspection decisions.

        :param generator: Operation generator to drive.
        :param decide: Optional callback for inspection decisions.
        :param phase: Execution phase.
        :yields: State updates and inspection results requiring a decision.
        :returns: Final operation state.
        """
        response = None
        waiting_for_action = False

        while True:
            try:
                if waiting_for_action:
                    item = generator.send(response)
                    waiting_for_action = False
                else:
                    item = next(generator)
            except StopIteration as exc:
                return exc.value

            if isinstance(item, InspectResult):
                response = decide(item, phase) if decide else None

                if response is None:
                    response = yield item

                if not isinstance(response, Action):
                    raise TypeError(f"Expected Action, got {response!r}")

                waiting_for_action = True
            else:
                self.emit("state_update", state=item)
                yield item

    def apply_sync(self, *args, **kwargs) -> State:
        """Apply and return the final state.

        All parameters are forwarded to :py:meth:`apply`.
        """
        gen = self.apply(*args, **kwargs)
        return self._consume_sync(gen)

    def rollback_sync(self, *args, **kwargs) -> State:
        """Rollback and return the final state.

        All parameters are forwarded to :py:meth:`rollback`.
        """
        gen = self.rollback(*args, **kwargs)
        return self._consume_sync(gen)

    def _consume_sync(self, generator) -> State:
        """Consume an execution generator without unresolved decisions.

        :param generator: Generator returned by apply or rollback.
        :returns: Final operation state.
        :raises RuntimeError: If a decision requires input and no callback resolved it.
        """
        while True:
            try:
                item = next(generator)
            except StopIteration as exc:
                return exc.value

            if isinstance(item, InspectResult):
                generator.close()
                raise RuntimeError(
                    "Execution requires a decision. " "Provide a decision callback or use the generator API."
                )
