import inspect
import logging
from typing import Callable, Generator, ClassVar, Sequence, Type
from uuid import uuid4, UUID

from pydantic import Field


from ox_orch.apps import Application
from ox_orch.core.contexts import RunContext, ExecutionContext
from ox_orch.core.pydantic import LazyTranslation, PolymorphicModel
from ox_orch.core.registry import register, Registry
from ox_orch.core.state import HistoryState, Status


__all__ = (
    "Status",  # re-export for convenience
    "RunContext",
    "OperationState",
    "Operation",
    "RunPython",
    "STATE_REGISTRY",
    "OPERATION_REGISTRY",
)


logger = logging.getLogger("ox-orch")


STATE_REGISTRY = Registry()
OPERATION_REGISTRY = Registry()


@register("operation")
class OperationState(HistoryState, PolymorphicModel):
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
    operation_id: str = None
    """ Operation id. """

    run_context: RunContext | None = None
    """ Run context of the operation, only set on the root state. """

    def __str__(self):
        return f"{type(self).__name__}@{self.operation_id} (status={self.status})"


class Operation(PolymorphicModel):
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
    __full_inputs__: bool = False
    """
    When the __apply_spec__ or __rollback_spec__ is provided, by default
    all other values of the context are discarded.

    If you need to keep them (eg. for plan execution), you can set this
    attribute to True.
    """

    uuid: UUID = Field(default_factory=uuid4)
    label: ClassVar[LazyTranslation] = ""
    """ Human readable text (can be Django lazy translation string) """

    @property
    def id(self):
        return f"{self.__type_id__}:{self.uuid}"

    def create_state(self, **kwargs) -> OperationState:
        """Return a new initial operation state."""
        return self.__state_class__(
            operation_id=self.id,
            _operation=self,
            **kwargs,
        )

    def apply(self, state: OperationState, ctx: ExecutionContext, **inputs) -> Generator[OperationState]:
        """
        Apply operation, ensuring state update.

        On failure, it will set state on failure if not yet rolled-back.

        :param state: state used for reporting this operation's status;
        :param **inputs: extra inputs arguments passed by the caller;
        """
        try:
            # We enforce run inputs usage.
            inputs = self.get_inputs(state, **inputs)
            inputs = self._resolve_apply_inputs(inputs)
            self.validate_state(state)

            if ctx.run.dry_run:
                self.log("Apply in dry run mode")

            yield state.start()

            if inspect.isgeneratorfunction(self._apply):
                yield from self._apply(state, ctx, **inputs)
            else:
                self._apply(state, ctx, **inputs)

            yield state.finish()
        except Exception as exc:
            if state.status != Status.ROLLED_BACK:
                yield state.fail(exc)
            raise

    def rollback(self, state: OperationState, ctx: ExecutionContext, **inputs) -> Generator[OperationState]:
        """
        Rollback operation, ensuring state update.

        :param state: state used for reporting this operation's status;
        :param **inputs: extra inputs arguments passed by the caller;
        """
        try:
            self.validate_state(state)
            inputs = self.get_inputs(state, **inputs)
            inputs = self._resolve_rollback_inputs(inputs)

            if ctx.run.dry_run:
                self.log("Rollback in dry run mode")

            yield state.rolling_back()

            if inspect.isgeneratorfunction(self._rollback):
                yield from self._rollback(state, ctx, **inputs)
            else:
                self._rollback(state, ctx, **inputs)

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
        elif state._operation != self:
            raise ValueError(f"Status `{state._operation}` does not matches the operation `{self}`.")

    def get_inputs(self, state, **inputs):
        """Return inputs to provide to _apply and _rollback methods."""
        if spec := inputs.get("spec"):
            inputs.setdefault("dry_run", spec.dry_run)
        return inputs

    def _apply(self, state, ctx, **context):
        """Where you put the actual code for applying the operation."""
        pass

    def _rollback(self, state, ctx, **context):
        """Where you put the actual code for applying the operation's rollback."""
        pass

    def _resolve_apply_inputs(self, inputs: dict) -> dict:
        """
        Resolve and validate execution inputs for the apply phase.

        :param inputs: Global execution inputs provided by the executor.
        :return: Filtered inputs containing only required keys for apply.
        :raises KeyError: If a required key is missing.
        :raises TypeError: If typed specification is violated.
        """
        return self._resolve_inputs(
            inputs=inputs,
            spec=self.__apply_spec__,
            phase="apply",
        )

    def _resolve_rollback_inputs(self, inputs: dict) -> dict:
        """
        Resolve and validate execution inputs for the rollback phase.

        :param inputs: Global execution inputs provided by the executor.
        :return: Filtered inputs containing only required keys for rollback.
        :raises KeyError: If a required key is missing.
        :raises TypeError: If typed specification is violated.
        """
        return self._resolve_inputs(
            inputs=inputs,
            spec=self.__rollback_spec__,
            phase="rollback",
        )

    def _resolve_inputs(self, inputs: dict, spec, phase: str) -> dict:
        """
        Dispatch inputs resolution based on specification type.

        Supports:
        - None: return inputs as is
        - tuple/list: key presence validation only
        - dict: key presence + type validation

        :param inputs: Global execution inputs.
        :param spec: Context specification (tuple or dict).
        :param phase: Execution phase name ("apply" or "rollback").
        :return: Validated and filtered inputs dictionary.
        :raises TypeError: If spec format is unsupported.
        """
        match spec:
            case None:
                return inputs
            case dict():
                ctx = self._resolve_typed_inputs(inputs, spec, phase)
            case tuple() | list():
                ctx = self._resolve_simple_inputs(inputs, spec, phase)
            case _:
                raise TypeError(f"Invalid inputs spec type: {type(spec)}")

        if self.__full_inputs__:
            return inputs
        return ctx

    def _resolve_simple_inputs(self, inputs: dict, spec: tuple[str, ...], phase: str) -> dict:
        """
        Resolve inputs using a minimal required-key specification.

        Ensures all keys exist in the provided inputs without type validation.

        :param inputs: Global execution inputs.
        :param spec: Tuple of required keys.
        :param phase: Execution phase name.
        :return: Dictionary containing resolved inputs values.
        :raises KeyError: If a required key is missing.
        """
        resolved = {}

        for key in spec:
            if key not in inputs:
                raise KeyError(f"{self.__class__.__name__} requires '{key}' for {phase}")

            resolved[key] = inputs[key]

        return resolved

    def _resolve_typed_inputs(self, inputs: dict, spec: dict[str, type], phase: str) -> dict:
        """
        Resolve inputs using a typed specification.

        Validates both presence and type of each required key.

        :param inputs: Global execution inputs.
        :param spec: Mapping of key to expected type.
        :param phase: Execution phase name.
        :return: Dictionary containing validated inputs values.
        :raises KeyError: If a required key is missing.
        :raises TypeError: If a value does not match the expected type.
        """
        resolved = {}

        for key, expected_type in spec.items():
            if key not in inputs:
                raise KeyError(f"{self.__class__.__name__} requires '{key}' for {phase}")

            value = inputs[key]

            if not isinstance(value, expected_type):
                raise TypeError(
                    f"{self.__class__.__name__} inputs key '{key}' "
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
    label = "🐍 Run python code"

    def _apply(self, *args, **context):
        self.forward(self, *args, **context)

    def _rollback(self, *args, **context):
        self.backward(self, *args, **context)
