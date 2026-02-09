from abc import ABC, abstractmethod
import inspect
from typing import Any, Callable, Generator, Type, ClassVar

from django.utils.translation import gettext_lazy as _

from django_installer.utils import CloneBaseModel, LazyTranslation

from ..apps import AppMetadata
from ..state import State, Status


__all__ = (
    # re-export for convenience
    "OperationState",
    "Status",
    "AbstractOperation",
    "RunPython",
    "register_operation",
    "get_operation_class",
)


_OPERATION_REGISTRY: dict[str, Type["AbstractOperation"]] = {}


def register_operation(cls):
    """
    Register an operation to allow it to be serializable, using :py:meth:`name`.
    """
    op_id = cls.operation_id
    if registered_cl := _OPERATION_REGISTRY.get(op_id):
        if _OPERATION_REGISTRY[op_id] is not cls:
            raise ValueError(f"An operation is already registered for {op_id} ({registered_cl}")
    else:
        _OPERATION_REGISTRY[op_id] = cls
    return cls


def get_operation_class(op_id: str):
    """Get operation class by name."""
    try:
        return _OPERATION_REGISTRY[op_id]
    except KeyError:
        raise ValueError(f"Unknown operation type: {op_id}")


class OperationState(State):
    """
    Keep state informations of an operation.
    """

    operation_id: str = None
    """ Operation id. """

    _operation = None
    """ Actual operation instance (set at Operation's state validation). """


class AbstractOperation(CloneBaseModel, ABC):
    """
    Abstract base class for all install operations.

    An operation applies modifications and is able to rollback it. Operation is
    provided a state to keep backend updated with current running operation
    status.

    The :py:meth:`apply` and :py:meth:`rollback` are the two main entry points
    for executing the operation. It handles state handling, rollback on failure
    (apply), and yield :py:class:`~django_installer.core.state.base.OperationState` updates.

    Implementator will implement the actual operation calls inside :py:meth:`_apply`
    and :py:meth:`_rollback`. Those can be regular method or a OperationState generator.
    """

    operation_id: ClassVar[str]
    label: ClassVar[LazyTranslation] = ""

    def create_state(self, **kwargs) -> OperationState:
        return OperationState(
            operation_id=type(self).operation_id,
            _operation=self,
            name=str(type(self).label or type(self).operation_id),
            **kwargs,
        )

    def validate_state(self, state: OperationState, recurse: bool = False):
        if not state._operation and state.operation_id == type(self).operation_id:
            state._operation = self
            state.name = str(type(self).label or type(self).operation_id)
        elif state._operation != self:
            raise ValueError(f"Status `{state._operation}` does not matches the operation `{self}`.")

    def apply(self, state: OperationState, **kwargs) -> Generator[OperationState]:
        """
        Apply operation, ensuring state update.

        On failure, it will set state on failure if not yet rolled-back.

        :param state: state used for reporting this operation's status;
        :param **kwargs: extra kwargs arguments passed by the caller;
        """
        try:
            self.validate_state(state)
            yield state.start()
            if inspect.isgeneratorfunction(self._apply):
                yield from self._apply(state=state, **kwargs)
            else:
                self._apply(state=state, **kwargs)
            yield state.finish()
        except Exception as exc:
            if state.status != Status.ROLLED_BACK:
                yield state.fail(exc)
            raise

    def rollback(self, state: OperationState, **kwargs) -> Generator[OperationState]:
        """
        Rollback operation, ensuring state update.

        :param state: state used for reporting this operation's status;
        :param **kwargs: extra kwargs arguments passed by the caller;
        """
        try:
            self.validate_state(state)
            yield state.rolling_back()
            if inspect.isgeneratorfunction(self._rollback):
                yield from self._rollback(state=state, **kwargs)
            else:
                self._rollback(state=state, **kwargs)
            yield state.rolled_back()
        except Exception as exc:
            if state.status != Status.ROLLED_BACK:
                yield state.fail(exc)
            raise

    @abstractmethod
    def _apply(self, state, **kwargs):
        """Where you put the actual code for applying the operation."""
        pass

    @abstractmethod
    def _rollback(self, state, **kwargs):
        """Where you put the actual code for applying the operation's rollback."""
        pass

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """
        Custom dump format.

        Example: ``{ type: "migrations", config: {...} }``
        """
        return {
            "operation_id": self.operation_id,
            "config": super().model_dump(**kwargs),
        }

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Dispatch to correct subclass based on `operation_id`."""
        if not isinstance(obj, dict):
            raise TypeError("Operation must be a dict")

        op_id = obj.get("operation_id")
        config = obj.get("config", {})

        op_cls = get_operation_class(op_id)
        return op_cls(**config)


@register_operation
class RunPython(AbstractOperation):
    """Run python code."""

    forward: Callable[(AppMetadata, AbstractOperation), None]
    backward: Callable[(AppMetadata, AbstractOperation), None]
    label = _("🐍 Run python code")
    operation_id = "run_python"

    def _apply(self, **kwargs):
        self.forward(self, **kwargs)

    def _rollback(self, **kwargs):
        self.backward(self, **kwargs)
