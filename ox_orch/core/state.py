from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, ClassVar, Optional, Iterable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


__all__ = (
    "Status",
    "STATUS_LABELS",
    "StateInfo",
    "State",
    "HistoryState",
    "TreeState",
    "ChangeSet",
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


class StateInfo(BaseModel):
    """
    Base state informations, as stored in :py:attr:`State.history`.
    """

    status: Status
    """ Current status. """
    error: str | None = None
    """ Error string (on failure). """
    updated: datetime
    """ Last update datetime. """


class State(StateInfo):
    """
    Generic State interface from which all states are derived.

    You MUST provide :py:attr:`_transitions` class attribute on subclasses.
    """

    id: UUID = Field(default_factory=uuid4)
    status: Status = Status.PENDING
    """ Current status. """
    # FIXME: remove?
    error: str | None = None
    """ Error string (on failure). """
    updated: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    """ Last update datetime. """

    _source: Any | None = None
    """ Source path or id, set and used by the backend. """
    _transitions: ClassVar[dict[str, set[str]]] = {
        Status.PENDING: {Status.RUNNING, Status.FAILED},
        Status.RUNNING: {Status.FAILED, Status.COMPLETED},
        Status.ROLLING_BACK: {Status.COMPLETED, Status.ROLLED_BACK, Status.FAILED},
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
        return f"{type(self).__name__} (status={self.status})"


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


Changes = dict[str, Any]


class ChangeSet(BaseModel):
    """
    Keep track of multiple objects changes.

    Workflow:

        - :py:meth:`add_change`: add forward changes for an object by reference;
        - :py:meth:`set_backward`: using the provided object, compute backward diff;
        - :py:meth:`validate_changes`: validate all diff inputs;
    """

    backward: dict[Any, Changes] = Field(default_factory=dict)
    """ Initial application states. """
    forward: dict[Any, Changes] = Field(default_factory=dict)
    """ Application states updates to commit on success. """

    def merge(self, other: ChangeSet):
        """
        Extend self with the provided change-set.

        .. important::

            Nested dictionaries wont be merge if another value is provided.
            It instead will be overriden by the latest one.
        """

        for ref, values in other.forward.items():
            self.add_changes(ref, values)

        for ref, values in other.backward.items():
            if values is None:
                self.backward[ref] = None
            else:
                self.backward.setdefault(ref, {}).update(values)

    def merge_from(self, change_sets: Iterable[ChangeSet]):
        """Merge multiple change sets into self."""
        for cs in change_sets:
            self.merge(cs)

    def add_changes(self, ref, values):
        """
        Register update values for an object by reference.

        It only store the forward change. To provide the

        """
        if not values:
            return

        if ref not in self.forward:
            self.forward[ref] = values
        else:
            self.forward[ref].update(values)

    def set_backward(self, ref, obj: BaseModel | None):
        """
        Compute backward diff for the provided original object.

        If not change is found, do nothing.
        """
        forward = self.forward.get(ref)
        if not forward:
            return

        if obj is None:
            backward = None
        else:
            backward = {key: deepcopy(getattr(obj, key, None)) for key in forward.keys()}
        self.backward[ref] = backward

    def validate_changes(self):
        if self.forward.keys() != self.backward.keys():
            raise ValueError(
                "Inconsistent references between backward and forward changes."
                "Did you forget to register some backward object?"
            )

        # for key, forward in self.forward.items():
        #     backward = self.backward[key]
        #     if backward is not None and backward.keys() != forward.keys():
        #         fields = set(backward.keys()) ^ set(forward.keys())
        #         raise ValueError(
        #             "Backward and forward Fields dont match. Mismatchs:" +
        #             ", ".join(fields)
        #         )
