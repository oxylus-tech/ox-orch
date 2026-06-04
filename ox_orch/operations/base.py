from datetime import datetime
import inspect
from typing import Callable, Generator, ClassVar, Sequence, Type
from uuid import uuid4

from django.utils.translation import gettext_lazy as _
from pydantic import BaseModel, Field

from ox_orch.utils import CloneBaseModel, LazyTranslation, PolymorphicModel

from ..core.apps import AppMetadata
from ..core.state import TreeState, HistoryState, Status


__all__ = (
    "Status",  # re-export for convenience
    "OperationState",
    "AbstractOperation",
    "RunPython",
)


class RunContext(BaseModel):
    """Running context of operations, only assigned to the root state."""

    run_id: str = Field(default_factory=str(uuid4()))
    """ Run id. """
    started_at: datetime | None = None
    """ Run execution start. """
    finished_at: datetime | None = None
    """ Run execution end. """
    trigger: str | None
    """ What triggered this execution, as cli, api, scheduler,... """


class OperationState(TreeState, HistoryState):
    """
    Keep state informations of an operation.
    """

    _operation = None
    """ Actual operation instance.

    This is set at two places:

        - :py:meth:`AbstractOperation.create_state`
        - :py:meth:`AbstractOperation.validate_state`
    """
    __type_id__ = "state:op"

    operation_id: str = None
    """ Operation id. """


class AbstractOperation(CloneBaseModel, PolymorphicModel):
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

            class MyOp(AbstractOperation):
                # This is used as state.operation_id value
                __type_id__ = "op:my_op"

    """

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

    label: ClassVar[LazyTranslation] = ""
    """ Human readable text (can be Django lazy translation string) """

    def create_state(self, **kwargs) -> OperationState:
        """Return a new initial operation state."""
        return self.__state_class__(
            operation_id=type(self).__type_id__,
            _operation=self,
            name=str(type(self).label or type(self).__type_id__),
            **kwargs,
        )

    def apply(self, state: OperationState, **context) -> Generator[OperationState]:
        """
        Apply operation, ensuring state update.

        On failure, it will set state on failure if not yet rolled-back.

        :param state: state used for reporting this operation's status;
        :param **context: extra context arguments passed by the caller;
        """
        try:
            context = self.get_context(state, **context)
            self.validate_state(state)

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

    def rollback(self, state: OperationState, **context) -> Generator[OperationState]:
        """
        Rollback operation, ensuring state update.

        :param state: state used for reporting this operation's status;
        :param **context: extra context arguments passed by the caller;
        """
        try:
            self.validate_state(state)
            context = self.get_context(state, **context)
            context = self._resolve_apply_context(context)

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
        if not state._operation and state.operation_id == type(self).__type_id__:
            state._operation = self
            state.name = str(type(self).label or type(self).__type_id__)
        elif state._operation != self:
            raise ValueError(f"Status `{state._operation}` does not matches the operation `{self}`.")

    def get_context(self, state, **context):
        return context

    def _apply(self, state, **context):
        """Where you put the actual code for applying the operation."""
        pass

    def _rollback(self, state, **context):
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
                return self._resolve_typed_context(context, spec, phase)
            case tuple() | list():
                return self._resolve_simple_context(context, spec, phase)
            case _:
                raise TypeError(f"Invalid context spec type: {type(spec)}")

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


class RunPython(AbstractOperation):
    """Run python code."""

    forward: Callable[(AppMetadata, AbstractOperation), None]
    backward: Callable[(AppMetadata, AbstractOperation), None]
    label = _("🐍 Run python code")
    __type_id__ = "op:run_python"

    def _apply(self, *args, **context):
        self.forward(self, *args, **context)

    def _rollback(self, *args, **context):
        self.backward(self, *args, **context)
