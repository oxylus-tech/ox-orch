from abc import ABC, abstractmethod
import inspect
from typing import Any, Callable, Generator, Type, ClassVar

from django.utils.translation import gettext_lazy as _

from pydantic import BaseModel
from django_installer.utils import LazyTranslation
from ..apps import AppMetadata
from ..state import State, Status


__all__ = ("AbstractOperation", "RunPython", "register_operation", "get_operation_class")


_OPERATION_REGISTRY: dict[str, Type["AbstractOperation"]] = {}


def register_operation(cls):
    """
    Register an operation to allow it to be serializable, using :py:meth:`name`.
    """
    op_name = cls.name
    if registered_cl := _OPERATION_REGISTRY.get(op_name):
        if _OPERATION_REGISTRY[op_name] is not cls:
            raise ValueError(f"An operation is already registered for {op_name} ({registered_cl}")
    else:
        _OPERATION_REGISTRY[op_name] = cls
    return cls


def get_operation_class(op_name: str):
    """Get operation class by name."""
    try:
        return _OPERATION_REGISTRY[op_name]
    except KeyError:
        raise ValueError(f"Unknown operation type: {op_name}")


class AbstractOperation(BaseModel, ABC):
    """
    Abstract base class for all install operations.

    An operation applies modifications and is able to rollback it. Operation is
    provided a state to keep backend updated with current running operation
    status.

    The :py:meth:`apply` and :py:meth:`rollback` are the two main entry points
    for executing the operation. It handles state handling, rollback on failure
    (apply), and yield :py:class:`~django_installer.core.state.base.State` updates.

    Implementator will implement the actual operation calls inside :py:meth:`_apply`
    and :py:meth:`_rollback`. Those can be regular method or a State generator.
    """

    name: ClassVar[str]
    label: LazyTranslation = ""

    def create_state(self, **kwargs) -> State:
        return State(name=type(self).name, _operation=self, **kwargs)

    def validate_state(self, state: State, recurse: bool = False):
        if not state._operation and state.name == type(self).name:
            state._operation = self
        elif state._operation != self:
            raise ValueError(f"Status `{state._operation}` does not matches the operation `{self}`.")

    def apply(self, state: State, **kwargs) -> Generator[State]:
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

    def rollback(self, state: State, **kwargs) -> Generator[State]:
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
            "name": self.name,
            "config": super().model_dump(**kwargs),
        }

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Dispatch to correct subclass based on `name`."""
        if not isinstance(obj, dict):
            raise TypeError("Operation must be a dict")

        op_name = obj.get("name")
        config = obj.get("config", {})

        op_cls = get_operation_class(op_name)
        return op_cls(**config)

    def clone(self, **kwargs):
        """Clone node overriding values using ``**kwargs``.

        Note that the values will be validated using ``model_validate``.
        """
        data = self.model_dump(mode="json")
        data.update(kwargs)
        return type(self).model_validate(data)


@register_operation
class RunPython(AbstractOperation):
    """Run python code."""

    forward: Callable[(AppMetadata, AbstractOperation), None]
    backward: Callable[(AppMetadata, AbstractOperation), None]
    label: LazyTranslation = _("Run python code")
    name = "run_python"

    def _apply(self, **kwargs):
        self.forward(self, **kwargs)

    def _rollback(self, **kwargs):
        self.backward(self, **kwargs)
