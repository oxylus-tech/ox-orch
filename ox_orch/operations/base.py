from abc import ABC, abstractmethod
import inspect
import logging
from typing import Callable, Generator, ClassVar, Sequence, Type
from uuid import uuid4, UUID

from pydantic import Field


from ox_orch.apps import Application
from ox_orch.core.contexts import RunContext
from ox_orch.core.pydantic import LazyTranslation, PolymorphicModel
from ox_orch.core.registry import register, DocumentedRegistry, DocumentedClass
from ox_orch.core.state import HistoryState, Status


__all__ = (
    "Status",  # re-export for convenience
    "OperationState",
    "Operation",
    "RunPython",
    "DelegateState",
    "DelegateOperation",
    "STATE_REGISTRY",
    "OPERATION_REGISTRY",
)


logger = logging.getLogger("ox-orch")


STATE_REGISTRY = DocumentedRegistry()
OPERATION_REGISTRY = DocumentedRegistry()


@register("operation")
class OperationState(HistoryState, PolymorphicModel, DocumentedClass):
    """
    Keep state informations of an operation.
    """

    __registry__ = STATE_REGISTRY

    _operation = None
    """ Actual operation instance.

    This is set at two places:

        - :py:meth:`Operation.create_state`
        - :py:meth:`Operation.validate_state`
    """
    operation_id: str = Field(default=None, description="ID of the related operation.")
    """ Operation id. """

    run_context: RunContext | None = Field(default=None, description="Run information, only set on the root state..")
    """ Run context of the operation, only set on the root state. """

    def __str__(self):
        return f"{type(self).__name__}@{self.operation_id} (status={self.status})"


class Operation(PolymorphicModel, DocumentedClass):
    """
    Abstract base class for all install operations.

    An operation applies modifications and is able to rollback it. Operation is
    provided a state to keep backend updated with current running operation
    status.

    The :py:meth:`apply` and :py:meth:`rollback` are the two main entry points
    for executing the operation. It handles state handling, rollback on failure
    (apply), and yield :py:class:`~ox_orch.core.state.base.OperationState` updates.

    Implementator will implement the actual operation calls inside :py:meth:`_apply`
    and :py:meth:`_rollback`. Those can be regular method or a OperationState generator.

    .. note::

        For the class to be serializable/deserializable, set :py:attr:`ox_orch.utils.PolymorphicModel`. The value is namespaced
        under ``op:``:

        .. code-block:: python

            class MyOp(Operation):
                # This is used as state.operation_id value
                __type_id__ = "op:my_op"

    """

    __registry__ = OPERATION_REGISTRY

    __state_class__: ClassVar[OperationState] = OperationState
    """ Class model to use as a state. """
    __apply_spec__: tuple[str] | dict[str, Type | Sequence[Type]] | None = None
    """ Specify context items to be used by the :py:meth:`_apply` method.

    In :py:meth:`apply`, those items will be fetched from the executor context
    if not already provided, and passed down as named parameters to the inner
    :py:meth:`_apply`.

    Three possible kind of values:

        - None: no requirement, the whole context will be passed down
        - a tuple or list of field name: only pass context items by key
        - a dict of string and type: same but validate the item type

    The item types will be checked again's ``isinstance``, meaning you can
    provide an sequence of types.

    """
    __rollback_spec__: tuple[str] | dict[str, Type] | None = None
    """ Specify context argument to be used by the :py:meth:`_rollback` method.

    Same than :py:attr:`__apply_spec__` but for rollback.
    """
    __full_context__: bool = False
    """
    When the __apply_spec__ or __rollback_spec__ is provided, by default
    all other values of the context are discarded.

    If you need to keep them (eg. for plan execution), you can set this
    attribute to True.
    """

    uuid: UUID = Field(default_factory=uuid4)
    _label: ClassVar[LazyTranslation] = ""
    """ Human readable text (can be Django lazy translation string) """
    _description: ClassVar[str] = ""
    """ Human description of this operation. """

    @property
    def id(self):
        return f"{self.__type_id__}:{str(self.uuid)[-6:]}"

    def create_state(self, **kwargs) -> OperationState:
        """Return a new initial operation state."""
        return self.__state_class__(
            operation_id=self.id,
            _operation=self,
            **kwargs,
        )

    def apply(self, state: OperationState, exec_ctx, **context) -> Generator[OperationState]:
        """
        Apply operation, ensuring state update.

        On failure, it will set state on failure if not yet rolled-back.

        :param state: state used for reporting this operation's status;
        :param exec_ctx: ExecutionContext
        :param **context: extra context arguments passed by the caller;
        """
        try:
            self.validate_state(state)
            context = self.get_context(state, exec_ctx=exec_ctx, **context)
            context = self._resolve_apply_context(context)

            if exec_ctx.run.dry_run:
                self.log("Apply in dry run mode")

            yield state.start()

            if inspect.isgeneratorfunction(self._apply):
                yield from self._apply(state, **context)
            else:
                self._apply(state, **context)

            yield state.finish()
        except Exception as exc:
            if state.status != Status.ROLLED_BACK:
                yield state.fail(exc)
            raise

    def rollback(self, state: OperationState, exec_ctx, **context) -> Generator[OperationState]:
        """
        Rollback operation, ensuring state update.

        :param state: state used for reporting this operation's status;
        :param exec_ctx: ExecutionContext
        :param **context: extra context arguments passed by the caller;
        """
        try:
            self.validate_state(state)
            context = self.get_context(state, exec_ctx=exec_ctx, **context)
            context = self._resolve_rollback_context(context)

            if exec_ctx.run.dry_run:
                self.log("Rollback in dry run mode")

            yield state.rolling_back()

            if inspect.isgeneratorfunction(self._rollback):
                yield from self._rollback(state, **context)
            else:
                self._rollback(state, **context)

            yield state.rolled_back()
        except Exception as exc:
            if state.status != Status.ROLLED_BACK:
                yield state.fail(exc)
            raise

    def validate_state(self, state: OperationState):
        """Validate provided state agains't this operation.

        It ensures that this state is related to this operation.
        It is used at :py:meth:`apply` and :py:meth:`rollback`.
        """
        if not isinstance(state, self.__state_class__):
            raise TypeError(
                f"Invalid type of state for this operation. Expected {self.__state_class__} "
                "but we've got {type(state)}"
            )
        if not state._operation and state.operation_id == self.id:
            state._operation = self
        elif state.operation_id != self.id:
            raise ValueError(f"Status `{state.operation_id}` does not matches the operation `{self.id}`.")

    def get_context(self, state, **context):
        """Return context to provide to _apply and _rollback methods."""
        if exec_ctx := context.get("exec_ctx"):
            context.setdefault("dry_run", exec_ctx.spec and exec_ctx.spec.dry_run)
        return context

    def _apply(self, state, exec_ctx, **context):
        """Where you put the actual code for applying the operation."""
        pass

    def _rollback(self, state, exec_ctx, **context):
        """Where you put the actual code for applying the operation's rollback."""
        pass

    def _resolve_apply_context(self, context: dict) -> dict:
        """
        Resolve and validate execution context for the apply phase.

        :param context: Global execution context provided by the executor.
        :return: Filtered context containing only required keys for apply.
        :raises KeyError: If a required key is missing.
        :raises TypeError: If typed specification is violated.
        """
        return self._resolve_context(
            context=context,
            spec=self.__apply_spec__,
            phase="apply",
        )

    def _resolve_rollback_context(self, context: dict) -> dict:
        """
        Resolve and validate execution context for the rollback phase.

        :param context: Global execution context provided by the executor.
        :return: Filtered context containing only required keys for rollback.
        :raises KeyError: If a required key is missing.
        :raises TypeError: If typed specification is violated.
        """
        return self._resolve_context(
            context=context,
            spec=self.__rollback_spec__,
            phase="rollback",
        )

    def _resolve_context(self, context: dict, spec, phase: str) -> dict:
        """
        Dispatch context resolution based on specification type.

        Supports:
        - None: return context as is
        - tuple/list: key presence validation only
        - dict: key presence + type validation

        :param context: Global execution context.
        :param spec: Context specification (tuple or dict).
        :param phase: Execution phase name ("apply" or "rollback").
        :return: Validated and filtered context dictionary.
        :raises TypeError: If spec format is unsupported.
        """
        match spec:
            case None:
                return context
            case dict():
                ctx = self._resolve_typed_context(context, spec, phase)
            case tuple() | list():
                ctx = self._resolve_simple_context(context, spec, phase)
            case _:
                raise TypeError(f"Invalid context spec type: {type(spec)}")

        if self.__full_context__:
            return context
        return ctx

    def _resolve_simple_context(self, context: dict, spec: tuple[str, ...], phase: str) -> dict:
        """
        Resolve context using a minimal required-key specification.

        Ensures all keys exist in the provided context without type validation.

        :param context: Global execution context.
        :param spec: Tuple of required keys.
        :param phase: Execution phase name.
        :return: Dictionary containing resolved context values.
        :raises KeyError: If a required key is missing.
        """
        resolved = {}

        for key in spec:
            if key not in context:
                raise KeyError(f"{self.__class__.__name__} requires '{key}' for {phase}")

            resolved[key] = context[key]

        return resolved

    def _resolve_typed_context(self, context: dict, spec: dict[str, type], phase: str) -> dict:
        """
        Resolve context using a typed specification.

        Validates both presence and type of each required key.

        :param context: Global execution context.
        :param spec: Mapping of key to expected type.
        :param phase: Execution phase name.
        :return: Dictionary containing validated context values.
        :raises KeyError: If a required key is missing.
        :raises TypeError: If a value does not match the expected type.
        """
        resolved = {}

        for key, expected_type in spec.items():
            if key not in context:
                raise KeyError(f"{self.__class__.__name__} requires '{key}' for {phase}")

            value = context[key]

            if not isinstance(value, expected_type):
                raise TypeError(
                    f"{self.__class__.__name__} context key '{key}' "
                    f"expected {expected_type}, got {type(value)} in {phase}"
                )

            resolved[key] = value

        return resolved

    def log(self, msg, type="info", *args, **kwargs):
        """Log message."""
        msg = f"\033[33m[{self.__type_id__}]\033[0m {msg}"
        getattr(logger, type)(msg, *args, **kwargs)


@register("python")
class RunPython(Operation):
    """Run python code."""

    forward: Callable[(Application, Operation), None]
    backward: Callable[(Application, Operation), None]
    _label = "🐍 Run python code"
    _description = "Run python code. Internal usage only: you can't use it from specification file or API."

    def _apply(self, *args, **context):
        self.forward(self, *args, **context)

    def _rollback(self, *args, **context):
        self.backward(self, *args, **context)


class DelegateState(OperationState):
    """
    Operation state for a :py:class:`ParentOperation`.
    The nested operation state resides in :py:attr:`child`.
    """

    child: OperationState | None = Field(description="Nested operation state.")


class DelegateOperation(Operation, ABC):
    """
    An abstract class for operation that requires to run a nested one.
    """

    __state_class__ = DelegateState

    operation: Operation = Field(description="The operation to run inside this one.")

    def _apply(self, state, *args, **kwargs):
        if state.child is None:
            state.child = self.operation.create_state()
        for child_st in self.child_apply(state, *args, **kwargs):
            state.child = child_st
            yield child_st
            yield state

    def _rollback(self, state, *args, **kwargs):
        for child_st in self.child_rollback(state, *args, **kwargs):
            state.child = child_st
            yield child_st
            yield state

    @abstractmethod
    def child_apply(self, state: DelegateState, *args, **kwargs) -> Generator[OperationState, None]:
        pass

    @abstractmethod
    def child_rollback(self, state: DelegateState, *args, **kwargs) -> Generator[OperationState, None]:
        pass
