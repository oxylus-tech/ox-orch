from __future__ import annotations
from enum import Enum, IntEnum, IntFlag, auto
from dataclasses import dataclass
import inspect
import logging
from typing import Any, Generator, ClassVar, Sequence, Type
from uuid import uuid4, UUID

from pydantic import Field

from .contexts import RunContext
from .pydantic import LazyTranslation, PolymorphicModel
from .registry import register, DocumentedRegistry, DocumentedClass
from .state import HistoryState, Status


__all__ = (
    "Status",  # re-export for convenience
    "STATE_REGISTRY",
    "OPERATION_REGISTRY",
    "POLICY_REGISTRY",
    "Action",
    "OperationCapabilities",
    "InspectResult",
    "OperationPhase",
    "Policy",
    "OperationContext",
    "OperationState",
    "Operation",
    "DefaultPolicy",
)


logger = logging.getLogger("ox-orch")


STATE_REGISTRY = DocumentedRegistry("Operation States")
POLICY_REGISTRY = DocumentedRegistry("Operation Policies")
OPERATION_REGISTRY = DocumentedRegistry("Operations")


class OperationCapabilities(IntFlag):
    """Declare the behavioral and execution characteristics of an operation.

    Flags describe the operation's contract. The executor may use them
    to select execution, retry, locking, preview, and reporting policies.

    A missing flag means that the corresponding characteristic is not
    declared; it does not necessarily prove the opposite.
    """

    NONE = 0

    # Effects and recovery
    SIDE_EFFECT = auto()
    IDEMPOTENT = auto()
    REVERSIBLE = auto()
    COMPENSATABLE = auto()
    RETRY_SAFE = auto()

    # State and reproducibility
    STATE_AWARE = auto()
    DETERMINISTIC = auto()

    # Resource scope and coordination
    LOCAL = auto()
    EXTERNAL = auto()
    EXCLUSIVE = auto()
    CONCURRENCY_SAFE = auto()

    # Execution capabilities
    OBSERVABLE = auto()
    PREVIEWABLE = auto()
    ASYNC = auto()


@dataclass
class InspectResult:
    """
    Result of the :py:meth:`Operation.inspect` method.
    """

    class Type(IntEnum):
        SATISFIED = auto()
        """ Required state already reached. """
        NOT_SATISFIED = auto()
        """ Required state not reached, action still required. """
        UNKNOWN = auto()
        """ Impossible to determine current state. """
        BLOCKED = auto()
        """ Operation is blocked. """

    type: Type
    operation: Operation
    state: OperationState
    message: str | None = None

    @classmethod
    def satisfied(cls, *args, **kwargs):
        return cls(cls.SATISFIED, *args, **kwargs)

    @classmethod
    def not_satisfied(cls, *args, **kwargs):
        return cls(cls.NOT_SATISFIED, *args, **kwargs)

    @classmethod
    def unknown(cls, *args, **kwargs):
        return cls(cls.UNKNOWN, *args, **kwargs)

    @classmethod
    def blocked(cls, *args, **kwargs):
        return cls(cls.BLOCKED, *args, **kwargs)

    @property
    def is_satisfied(self):
        return self.type == self.Type.SATISFIED

    @property
    def is_not_satisfied(self):
        return self.type == self.Type.NOT_SATISFIED

    @property
    def is_unknown(self):
        return self.type == self.Type.UNKNOWN

    @property
    def is_blocked(self):
        return self.type == self.Type.BLOCKED


class Action(IntEnum):
    """Action sent by the server to the operation after an inspection result is yielded."""

    ACCEPT = auto()
    APPLY = auto()
    ABORT = auto()


class OperationPhase(Enum):
    """Execution phase requested for an operation."""

    APPLY = "apply"
    ROLLBACK = "rollback"


class Policy(DocumentedClass):
    """
    Interface for deciding how an operation should proceed.

    It is used to determine what to do depending on the :py:meth:`Operation.inspect` result.
    """

    __registry__ = POLICY_REGISTRY

    def decide(self, operation: Operation, result: InspectResult, phase: OperationPhase) -> Action | None:
        """Decide which action should follow an inspection.

        :param operation: Operation being evaluated.
        :param result: Result of inspecting the current state.
        :param phase: Requested execution phase.
        :returns: The action to perform, or None when external input is required.
        """
        ...


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


OperationMessage = OperationState | InspectResult
Message = OperationMessage | Action
OperationContext = dict[str, Any]


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

    Inspect & Policy
    ----------------

    We can't trust only the input state to run an operation; eg. after a failure or
    interruption, we can't be sure state is right.

    The :py:meth:`inspect` is used to determine the real current state of an operation
    to apply. This allows safer decision making depending on what is actually applied
    or not on the target environment.

    The resulting :py:class:`InspectResult` is passed down to the :py:class:`Policy`,
    allowing it to take an actual decision: either proceed, skip, abort or ask upstream
    (end-user, executor) what to do.

    Capabilities
    ------------

    An operation declares its :py:attr:`capabilities` (see :py:class:`Capabilities`), allowing a :py:class:`Policy`
    to decide which action to take depending on the current state inspection.

    Polymorphism
    ------------

    Operations must be serializable, as they can be retrieved from a description file/input. As such, they are :py:class:`~ox_orch.core.pydantic.PolymorphicModel`
    and use the :py:mod:`~ox_orch.core.registry` mechanisms.
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
    _default_inspect_type: ClassVar[InspectResult.Type] = InspectResult.Type.UNKNOWN
    """ Inspect method result used by default. """
    capabilities: ClassVar[OperationCapabilities] = OperationCapabilities.NONE
    """ Operation capabilities. """

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

    def inspect(self, state: OperationState, context) -> InspectResult:
        return InspectResult(self._default_inspect_type, self, state)

    def apply(self, state: OperationState, context: OperationContext) -> Generator[OperationMessage]:
        """
        Apply operation, ensuring state update.

        On failure, it will set state on failure if not yet rolled-back.

        :param state: state used for reporting this operation's status;
        :param execution: ExecutionContext
        :param **context: extra context arguments passed by the caller;
        """
        try:
            self.validate_state(state)
            policy = self._get_policy(context)
            result = self.inspect(state, context)
            action = self._decide(result, OperationPhase.APPLY, policy)

            match action:
                case Action.ACCEPT:
                    yield state.finish(force=True)
                    return
                case Action.ABORT:
                    raise RuntimeError("Operation apply aborted")
                case Action.APPLY:
                    pass

            context = self.get_context(state, **context)
            context.setdefault("policy", policy)
            context = self._resolve_apply_context(context)

            if context.get("dry_run"):
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

    def rollback(self, state: OperationState, context: OperationContext) -> Generator[OperationMessage]:
        """
        Rollback operation, ensuring state update.

        :param state: state used for reporting this operation's status;
        :param execution: ExecutionContext
        :param **context: extra context arguments passed by the caller;
        """
        try:
            self.validate_state(state)

            policy = self._get_policy(context)
            result = self.inspect(state, context)
            action = self._decide(result, OperationPhase.ROLLBACK, policy)

            match action:
                case Action.ACCEPT:
                    yield state.rolled_back(force=True)
                    return
                case Action.ABORT:
                    raise RuntimeError("Operation rollback aborted")
                case Action.APPLY:
                    pass

            context = self.get_context(state, **context)
            context.setdefault("policy", policy)
            context = self._resolve_rollback_context(context)

            if context.get("dry_run"):
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

    def get_context(self, state, **context) -> OperationContext:
        """Return context to provide to _apply and _rollback methods."""
        if execution := context.get("execution"):
            context.setdefault("dry_run", execution.spec and execution.spec.dry_run)
        return context

    def _get_policy(self, context: OperationContext) -> Policy:
        """Retrieve execution policy from the context."""
        return context.get("policy") or DefaultPolicy()

    def _decide(
        self, result: InspectResult, phase: OperationPhase, policy: Policy
    ) -> Generator[InspectResult, Action, Action]:
        action = policy.decide(self, result, phase)
        if action is None:
            action = yield result

        if not isinstance(action, Action):
            raise TypeError(f"Invalid operation action: {action}")

        return action

    def _apply(self, state, execution, **context):
        """Where you put the actual code for applying the operation."""
        pass

    def _rollback(self, state, execution, **context):
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


@register("default")
class DefaultPolicy(Policy):
    """Default policy for applying and rolling back operations."""

    _label = "Default"
    _description = "Default policy for applying and rolling back operations."

    def decide(
        self,
        operation: Operation,
        result: InspectResult,
        phase: OperationPhase,
    ) -> Action | None:
        """Choose an action based on the inspection result and capabilities.

        Returns:

        - ACCEPT if the requested state is already achieved,
        - APPLY if execution should proceed,
        - ABORT if execution is unsafe or blocked,
        - or None if an external decision is required.

        :param operation: Operation being evaluated.
        :param result: Result of inspecting the current state.
        :param phase: Requested execution phase.

        """
        if result.type == InspectResult.Type.BLOCKED:
            return Action.ABORT

        capabilities = operation.capabilities
        state_aware = bool(capabilities & OperationCapabilities.STATE_AWARE)

        if phase == OperationPhase.APPLY:
            return self._decide_apply(result, state_aware)

        return self._decide_rollback(
            result,
            state_aware,
            reversible=bool(capabilities & OperationCapabilities.REVERSIBLE),
        )

    def _decide_apply(self, result: InspectResult, state_aware: bool) -> Action | None:
        """Choose an action for the apply phase."""
        match result.type:
            case InspectResult.Type.SATISFIED:
                return Action.ACCEPT
            case InspectResult.Type.NOT_SATISFIED:
                return Action.APPLY
            case InspectResult.Type.UNKNOWN:
                return None if state_aware else Action.APPLY
            case InspectResult.Type.BLOCKED:
                return Action.ABORT

        raise ValueError(f"Unsupported inspection result: {result.type!r}")

    def _decide_rollback(self, result: InspectResult, state_aware: bool, reversible: bool) -> Action | None:
        """Choose an action for the rollback phase."""
        match result.type:
            case InspectResult.Type.NOT_SATISFIED:
                return Action.ACCEPT
            case InspectResult.Type.SATISFIED:
                return Action.APPLY if reversible else Action.ABORT
            case InspectResult.Type.UNKNOWN:
                if state_aware:
                    return None
                return Action.APPLY if reversible else Action.ABORT
            case InspectResult.Type.BLOCKED:
                return Action.ABORT

        raise ValueError(f"Unsupported inspection result: {result.type!r}")
