from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.db.models import TextChoices
from django.utils import timezone as tz
from django.utils.translation import gettext_lazy as _
from pydantic import BaseModel, Field


__all__ = ("Status", "StateInfo", "State")


class Status(TextChoices):
    """The state of an operation.

    It is derived from Django's ``TextChoices``, providing labels
    for each choice.
    """

    PENDING = "pending", _("Pending")
    """ Operation is awaiting for execution. """
    RUNNING = "running", _("Running")
    """ Operation is running. """
    ROLLING_BACK = "rolling_back", _("Rolling back")
    """ Rolling back is running. """
    COMPLETED = "completed", _("Completed")
    """ Operation was successfully completed. """
    FAILED = "failed", _("Failed")
    """ Operation failed. """
    ROLLED_BACK = "rolled_back", _("Rolled back")
    """ Operation was successfully rolled-back. """


class StateInfo(BaseModel):
    status: Status
    updated: Optional[datetime] = Field(default_factory=tz.now)
    error: Optional[str] = None


class State(StateInfo):
    """
    Keep state informations of an operation.
    """

    name: str = None
    """ Operation id. """
    status: Status = Status.PENDING
    """ Current state. """
    states: Optional[list[State]] = None
    """ Sub states (when Operation is a plan). """
    history: list[StateInfo] = Field(default_factory=list)
    """ History of all state transitions. """

    _operation = None
    """ Actual operation instance (set at Operation's state validation). """

    class Config:
        arbitrary_types_allowed = True

    # ---- Status get
    def is_any(self, *states: list[Status]) -> bool:
        """Return True if operation is one of the provided states."""
        return self.status in states

    def is_completed(self) -> bool:
        """Return True if operation successly completed."""
        return self.status == Status.COMPLETED

    def was_run(self) -> bool:
        """Return True if operation was run, nevertheless the result."""
        return self.status in (Status.COMPLETED, Status.FAILED, Status.ROLLED_BACK)

    # ---- Status set
    def set_status(self, status, error: Optional[str | Exception] = None):
        self.history.append(StateInfo(status=self.status, error=self.error, updated=self.updated))
        self.status = status
        self.error = error and str(error)
        self.updated = tz.now()
        return self

    def start(self) -> State:
        """Mark state as started."""
        return self.set_status(Status.RUNNING)

    def rolling_back(self) -> State:
        return self.set_status(Status.ROLLING_BACK)

    def finish(self, state=Status.COMPLETED, exc: Optional[str | Exception] = None) -> State:
        """Mark state as finished."""
        return self.set_status(Status.COMPLETED, exc)

    def rolled_back(self, exc: Optional[str | Exception] = None) -> State:
        """Mark state as rolled back."""
        return self.set_status(Status.ROLLED_BACK, exc)

    def fail(self, exc: Exception) -> State:
        """Mark state as failed."""
        return self.set_status(Status.FAILED, exc)

    # ---- Generic info & helpers
    def summary(self) -> str:
        """Return a summary of the state (and substates)."""
        if not self.states:
            return str(self)
        lines = [f"{self}:"] + ["- " + str(state).replace("\n", "\n  ") for state in self.states]
        return "\n".join(lines)

    def clone(self):
        """Copy of self."""
        data = self.model_dump(mode="json")
        return type(self).model_validate(data)

    def __str__(self):
        name = ""
        if self._operation:
            name = self._operation.label
        else:
            name = self.name
        return f"{name} (status={self.status})"
