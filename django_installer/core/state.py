from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Optional, Type

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _
from django.utils import timezone as tz
from pydantic import Field

from .. import utils
from . import files


__all__ = ("State", "StateInfo", "StateBackend", "StateFileBackend", "StateYAMLBackend", "StateJSONBackend")


class Status(TextChoices):
    """The state of an operation.

    It is derived from Django's ``TextChoices``, providing labels
    for each choice.
    """

    PENDING = "pending", _("⏸️ Pending")
    """ Operation is awaiting for execution. """
    RUNNING = "running", _("▶️️ Running")
    """ Operation is running. """
    ROLLING_BACK = "rolling_back", _("⏪ Rolling back")
    """ Rolling back is running. """
    COMPLETED = "completed", _("✅ Completed")
    """ Operation was successfully completed. """
    FAILED = "failed", _("❌ Failed")
    """ Operation failed. """
    ROLLED_BACK = "rolled_back", _("❕Rolled back")
    """ Operation was successfully rolled-back. """


class StateInfo(utils.CloneBaseModel):
    """
    Base state informations, as stored in :py:attr:`State.history`.
    """

    status: Status
    """ Current status. """
    error: Optional[str] = None
    """ Error string (on failure). """
    updated: datetime
    """ Last update datetime. """


class State(StateInfo, utils.PolymorphicModel):
    """
    Generic State interface from which all states are derived.

    You MUST provide :py:attr:`_transitions` class attribute on subclasses.
    """

    status: Status = Status.PENDING
    """ Current status. """
    name: str = ""
    """ State name, """
    error: Optional[str] = None
    """ Error string (on failure). """
    updated: Optional[datetime] = Field(default_factory=tz.now)
    """ Last update datetime. """
    children: list[State] = Field(default_factory=list)
    """ Children states. """
    history: list[StateInfo] = Field(default_factory=list)
    """ History of state transitions. """

    _parent: Optional[State] = None
    """ Parent state (set at init). """
    _root: Optional[State] = None
    """ Root state (set at init). """
    _source: Optional[Any] = None
    """ Source path or id, set and used by the backend. """
    _transitions: ClassVar[dict[str, set[str]]] = {
        Status.PENDING: {Status.RUNNING, Status.FAILED},
        Status.RUNNING: {Status.FAILED, Status.COMPLETED},
        Status.ROLLING_BACK: {Status.ROLLED_BACK, Status.FAILED},
        Status.COMPLETED: {Status.ROLLING_BACK},
        Status.FAILED: {Status.ROLLING_BACK},
        Status.ROLLED_BACK: {},
    }
    """ Allowed transitions. """
    _registry_id = "state"

    # class Config:
    #    arbitrary_types_allowed = True

    def __init__(self, *args, _root: Optional[State] = None, **kwargs):
        if _root is None:
            _root = self
        super().__init__(*args, _root=_root, **kwargs)

        if self._root is self:
            self._propagate_root_parent()

    def _propagate_root_parent(self):
        """Ensure that _root and _parent are correctly set."""
        for child in self.children:
            child._parent = self
            child._root = self._root
            child._propagate_root_parent()

    # ---- Status get
    def is_any(self, *statuses: list[Status]) -> bool:
        """Return True if operation is one of the provided statuses."""
        return self.status in statuses

    def is_completed(self) -> bool:
        """Return True if operation successly completed."""
        return self.status == Status.COMPLETED

    def was_run(self) -> bool:
        """Return True if operation was run, nevertheless the result."""
        return self.status in (Status.COMPLETED, Status.FAILED, Status.ROLLED_BACK)

    # ---- Status set
    def set_status(self, status, error: Optional[str | Exception] = None):
        """Update status (validating transition)."""
        self.validate_transition(status)
        self.history.append(StateInfo(status=self.status, error=self.error, updated=self.updated))

        self.status = status
        if error:
            self.error = str(error)
        self.updated = tz.now()
        return self

    def validate_transition(self, new_status: str):
        """Validate a state transition."""
        allowed = self._transitions.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(f"Can not transition {self.status} to {new_status}")

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
        """Return a summary of the state (and children)."""
        if not self.children:
            return str(self)
        lines = [f"{self}:"] + ["- " + str(state).replace("\n", "\n  ") for state in self.children]
        return "\n".join(lines)

    def __str__(self):
        return f"{self.name} (status={self.status})"


class StateBackend:
    """
    Backend interface used to load and store states.

    Notes:

        - the StateBackend should set the :py:attr:`State._source` attribute
          to know where to store the
    """

    state_class: Type[State] = State
    """ Operation state class to use for loading and instanciating. """

    def load(self, source: Any) -> State | None:
        """
        Load or reload state from the backend.
        """
        return self.state

    def save(self, state: State = None, target: Any = None):
        """
        Save state in the backend, to target (defaults to :py:attr:`State._source`).

        .. note::

            The provided state can be a nested one from the root one, so if
            you need to save the whole tree at once, you can use the
            :py:attr:`State._root` attribute.

        """
        pass

    def delete(self, state):
        """Drop state from storage."""
        pass


class StateFileBackend(StateBackend):
    """Load and save state to provided file path.

    You must provide a :py:class:`~django_installer.core.files.FileBackend`
    subclass to handle file writing and saving.
    If you're too lazy (which is good), you can use :py:class:`StateYAMLBackend`
    or :py:class:`StateJSONBackend` instead.
    """

    def __init__(self, backend_class: Type[files.FileBackend]):
        self.backend = backend_class(self.state_class)

    def load(self, source: Path):
        obj = self.backend.load(source)
        obj._source = source
        return obj

    def save(self, state: State, target: Optional[str | Path] = None):
        """Save state to YAML file."""
        root = state._root or state._parent or state
        target = target and Path(target) or state._source
        if not target:
            raise ValueError("No target provided and no source on State")
        self.backend.save(target, root)


class StateYAMLBackend(StateFileBackend):
    """State backend storing to YAML file."""

    def __init__(self):
        super().__init__(files.YAMLBackend)


class StateJSONBackend(StateFileBackend):
    """State backend storing to JSON file."""

    def __init__(self):
        super().__init__(files.JSONBackend)
