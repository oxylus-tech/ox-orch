import inspect
from typing import Callable, Generator, ClassVar

from django.utils.translation import gettext_lazy as _

from ox_installer.utils import CloneBaseModel, LazyTranslation, PolymorphicModel

from ..core.apps import AppMetadata
from ..core.state import State, Status


__all__ = (
    "Status",  # re-export for convenience
    "OperationState",
    "AbstractOperation",
    "RunPython",
)


class OperationState(State):
    """
    Keep state informations of an operation.
    """

    operation_id: str = None
    """ Operation id. """

    _operation = None
    """ Actual operation instance (set at Operation's state validation). """
    __type_id__ = "state:op"


class AbstractOperation(CloneBaseModel, PolymorphicModel):
    """
    Abstract base class for all install operations.

    An operation applies modifications and is able to rollback it. Operation is
    provided a state to keep backend updated with current running operation
    status.

    The :py:meth:`apply` and :py:meth:`rollback` are the two main entry points
    for executing the operation. It handles state handling, rollback on failure
    (apply), and yield :py:class:`~ox_installer.core.state.base.OperationState` updates.

    Implementator will implement the actual operation calls inside :py:meth:`_apply`
    and :py:meth:`_rollback`. Those can be regular method or a OperationState generator.

    .. note::

        For the class to be serializable/deserializable, set :py:attr:`ox_installer.utils.PolymorphicModel`. The value is namespaced
        under ``op:``:

        .. code-block:: python

            class MyOp(AbstractOperation):
                # This is used as state.operation_id value
                __type_id__ = "op:my_op"

    """

    label: ClassVar[LazyTranslation] = ""
    """ Human readable text (can be Django lazy translation string) """
    _state_class: ClassVar[State] = OperationState
    """ Class model to use as a state. """

    def create_state(self, **kwargs) -> OperationState:
        """Return a new initial operation state."""
        return self._state_class(
            operation_id=type(self).__type_id__,
            _operation=self,
            name=str(type(self).label or type(self).__type_id__),
            **kwargs,
        )

    def validate_state(self, state: OperationState):
        """Validate provided state agains't this operation.

        It ensures that this state is related to this operation.
        """
        if not isinstance(state, self._state_class):
            raise TypeError(
                f"Invalid type of state for this operation. Expected {self._state_class} " "but we've got {type(state)}"
            )
        if not state._operation and state.operation_id == type(self).__type_id__:
            state._operation = self
            state.name = str(type(self).label or type(self).__type_id__)
        elif state._operation != self:
            raise ValueError(f"Status `{state._operation}` does not matches the operation `{self}`.")

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
                yield from self._apply(**context)
            else:
                self._apply(**context)

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
            context = self.get_context(state, **context)
            self.validate_state(state)

            yield state.rolling_back()

            if inspect.isgeneratorfunction(self._rollback):
                yield from self._rollback(**context)
            else:
                self._rollback(**context)

            yield state.rolled_back()
        except Exception as exc:
            if state.status != Status.ROLLED_BACK:
                yield state.fail(exc)
            raise

    def get_context(self, state, **context):
        context["state"] = state
        return context

    def _apply(self, state, **context):
        """Where you put the actual code for applying the operation."""
        pass

    def _rollback(self, state, **context):
        """Where you put the actual code for applying the operation's rollback."""
        pass


class RunPython(AbstractOperation):
    """Run python code."""

    forward: Callable[(AppMetadata, AbstractOperation), None]
    backward: Callable[(AppMetadata, AbstractOperation), None]
    label = _("🐍 Run python code")
    __type_id__ = "op:run_python"

    def _apply(self, **context):
        self.forward(self, **context)

    def _rollback(self, **context):
        self.backward(self, **context)
