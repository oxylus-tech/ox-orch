from abc import ABC, abstractmethod
from typing import Callable

from django.utils.translation import gettext_lazy as _

from pydantic import BaseModel
from django_installer.utils import LazyTranslation
from ..apps import AppMetadata
from ..state import OperationState, State


__all__ = ("AbstractOperation", "RunPython")


class AbstractOperation(BaseModel, ABC):
    """Base class for all install operations."""

    name: str
    label: LazyTranslation = ""

    def create_state(self, **kwargs) -> OperationState:
        return OperationState(name=self.name, _operation=self, **kwargs)

    def validate_state(self, state: OperationState, recurse: bool = False):
        if not state._operation and state.name == self.name:
            state._operation = self
        elif state._operation != self:
            raise ValueError(f"State `{state._operation}` does not matches the operation `{self}`.")

    def apply(self, state: OperationState, **kwargs):
        """Apply operation, ensuring state update."""
        try:
            self.validate_state(state)
            state.start()
            self._apply(state=state, **kwargs)
            state.finish()
        except Exception as exc:
            if state.state != State.ROLLED_BACK:
                state.fail(exc)
            raise

    def rollback(self, state: OperationState, **kwargs):
        """Rollback the operation, ensuring state update."""
        try:
            self.validate_state(state)
            self._rollback(state=state, **kwargs)
            state.rolled_back()
        except Exception as exc:
            if state.state != State.ROLLED_BACK:
                state.fail(exc)
            raise

    @abstractmethod
    def _apply(self, state, **kwargs):
        pass

    @abstractmethod
    def _rollback(self, state, **kwargs):
        pass


class RunPython(AbstractOperation):
    """Run python code."""

    forward: Callable[(AppMetadata, AbstractOperation), None]
    backward: Callable[(AppMetadata, AbstractOperation), None]
    label: LazyTranslation = _("Run python code")
    name: str = "run_python"

    def _apply(self, **kwargs):
        self.forward(self, **kwargs)

    def _rollback(self, **kwargs):
        self.backward(self, **kwargs)
