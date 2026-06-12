from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Optional, Type

from pydantic import Field

from . import files
from .pydantic import CloneBaseModel


__all__ = (
    "Status",
    "STATUS_LABELS",
    "StateInfo",
    "State",
    "HistoryState",
    "TreeState",
    "StateBackend",
    "StateFileBackend",
    "StateYAMLBackend",
    "StateJSONBackend",
)


class Status(StrEnum):
    """The state of an operation.

    It is derived from Django's ``TextChoices``, providing labels
    for each choice.
    """

    PENDING = "pending"
    """ Operation is awaiting for execution. """
    RUNNING = "running"
    """ Operation is running. """
    ROLLING_BACK = "rolling_back"
    """ Rolling back is running. """
    COMPLETED = "completed"
    """ Operation was successfully completed. """
    FAILED = "failed"
    """ Operation failed. """
    ROLLED_BACK = "rolled_back"
    """ Operation was successfully rolled-back. """

    @property
    def label(self):
        return STATUS_LABELS[self]


STATUS_LABELS = {
    Status.PENDING: "⏸️ Pending",
    Status.RUNNING: "▶️️ Running",
    Status.ROLLING_BACK: "⏪ Rolling back",
    Status.COMPLETED: "✅ Completed",
    Status.FAILED: "❌ Failed",
    Status.ROLLED_BACK: "❕Rolled back",
}
""" Label for statuses. """


class StateInfo(CloneBaseModel):
    """
    Base state informations, as stored in :py:attr:`State.history`.
    """

    status: Status
    """ Current status. """
    error: Optional[str] = None
    """ Error string (on failure). """
    updated: datetime
    """ Last update datetime. """


class State(StateInfo):
    """
    Generic State interface from which all states are derived.

    You MUST provide :py:attr:`_transitions` class attribute on subclasses.
    """

    status: Status = Status.PENDING
    """ Current status. """
    name: str = ""
    """ State name, """
    error: str | None = None
    """ Error string (on failure). """
    updated: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    """ Last update datetime. """

    _source: Any | None = None
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

    # class Config:
    #    arbitrary_types_allowed = True

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
    def set_status(self, status, error: str | Exception | None = None) -> State:
        """Update status (validating transition).

        :param status: new status to assign.
        :param error: set error if provided.
        :returns: self
        """
        self.validate_transition(status)
        self.status = status
        if error is not None:
            self.error = str(error)
        self.updated = datetime.now(timezone.utc)
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
        return str(self)

    def __str__(self):
        return f"{self.name or type(self).__name__} (status={self.status})"


class HistoryState(State):
    """
    Add state transition history capabilities.
    """

    history: list[StateInfo] = Field(default_factory=list)
    """ History of state transitions. """

    def set_status(self, status, error: Optional[str | Exception] = None):
        """Update status (validating transition)."""
        state_info = StateInfo(status=self.status, error=self.error, updated=self.updated)
        super().set_status(status, error)
        self.history.append(state_info)
        return self


class TreeState(State):
    """
    A State that actually is a tree state, offering parent-child mechanisms.

    """

    children: list[State] = Field(default_factory=list)
    """ Children states. """

    _parent: State | None = None
    """ Parent state (set at init). """
    _root: State | None = None
    """ Root state (set at init). """

    def __init__(self, *args, _root: Optional[State] = None, **kwargs):
        super().__init__(*args, _root=_root, **kwargs)

        if self._parent and self._root is None:
            self._root = self._parent._root
        elif self.is_root:
            self.propagate_parents()

    @property
    def is_root(self) -> bool:
        """Return whether this node is root or note."""
        return self._root is None

    # ---- Status tree
    def append(self, child, force=False):
        """
        Append a new child state to self, ensuring correct parenting.

        To keep the states scope, the child must not be already used on
        another tree, otherwise it raises a ``ValueError`` -- unless you
        force it.

        :param child: the child to append.
        :param force: force child insertion.
        :raises ValueError: When a child already is assigned to another tree.
        """
        if child._parent not in (None, self) and child._root not in (None, self):
            if not force:
                raise ValueError("Child is already in another state tree.")

        self.children.append(child)

    def propagate_parents(self):
        """
        Ensure that _root and _parent are correctly set.

        Note that each child's method will be called recursively.
        """
        for child in self.children:
            child._parent = self
            child._root = self._root
            child._propagate_root_parent()

    def summary(self) -> str:
        """Return a summary of the state (and children)."""
        if not self.children:
            return super().summary()
        lines = [f"{self}:"] + ["- " + str(state).replace("\n", "\n  ") for state in self.children]
        return "\n".join(lines)


class StateBackend:
    """
    Backend interface used to load and store states.

    Notes:

        - the StateBackend should set the :py:attr:`State._source` attribute
          to know where to store the
    """

    state_class: Type[State] = State
    """ Operation state class to use for loading and instanciating. """

    def __init__(self, state_class: Type[State] | None = None):
        if state_class is not None:
            self.state_class = state_class

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

    You must provide a :py:class:`~ox_orch.core.files.FileBackend`
    subclass to handle file writing and saving.
    If you're too lazy (which is good), you can use :py:class:`StateYAMLBackend`
    or :py:class:`StateJSONBackend` instead.
    """

    def __init__(self, backend_class: Type[files.FileBackend], state_class: Type[State] | None = None):
        super().__init__(state_class)
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

    def __init__(self, state_class: Type[State] | None = None):
        super().__init__(files.YAMLBackend, state_class)


class StateJSONBackend(StateFileBackend):
    """State backend storing to JSON file."""

    def __init__(self, state_class: Type[State] | None = None):
        super().__init__(files.JSONBackend, state_class)
