from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

from django.db.models import TextChoices
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _
from pydantic import BaseModel


__all__ = ("State", "OperationState")


class State(TextChoices):
    """The state of an operation.

    It is derived from Django's ``TextChoices``, providing labels
    for each choice.
    """

    PENDING = "pending", _("Pending")
    RUNNING = "running", _("Running")
    DONE = "done", _("Done")
    FAILED = "failed", _("Failed")
    ROLLED_BACK = "rolled_back", _("Rolled back")


class OperationState(BaseModel):
    """
    Keep state informations of an operation.
    """

    name: str = None
    """ Operation id. """
    state: State = State.PENDING
    """ Current state. """
    started_at: Optional[datetime] = None
    """ Datetime of starting state. """
    finished_at: Optional[datetime] = None
    """ Datetime of ending state. """
    error: Optional[str] = None
    """ Error (on finished/rolled_back). """
    states: Optional[list[State]] = None
    """ Sub states (when Operation is a plan). """
    _operation = None
    """ Actual operation instance (set at Operation's state validation). """

    class Config:
        arbitrary_types_allowed = True

    def any(self, *states) -> bool:
        return self.state in states

    def start(self):
        """Mark state as started."""
        self.state = State.RUNNING
        self.started_at = tz.now()
        self.error = None

    def finish(self, state=State.DONE, exc: Exception | None = None):
        """Mark state as finished."""
        self.state = state
        self.finished_at = tz.now()
        self.error = exc and str(exc) or None

    def rolled_back(self, exc: Exception = None):
        """Mark state as rolled back."""
        self.finish(State.ROLLED_BACK, exc=exc)

    def fail(self, exc: Exception):
        """Mark state as failed."""
        self.finish(State.FAILED, exc=exc)

    def summary(self) -> str:
        """Return a summary of the state (and substates)."""
        if not self.states:
            return str(self)
        lines = [f"{self}:"] + ["- " + str(state).replace("\n", "\n  ") for state in self.states]
        return "\n".join(lines)

    def save(self, path: str | Path):
        """Save state to YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(mode="json"), f)

    @classmethod
    def load(cls, path: str | Path) -> State:
        """Load state from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def __str__(self):
        name = ""
        if self._operation:
            name = self._operation.label
        else:
            name = self.name
        return f"{name} (status={self.state})"
