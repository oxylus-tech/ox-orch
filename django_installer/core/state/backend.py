from pathlib import Path
from typing import Optional, Type


from ..files import FileBackend
from .base import State


__all__ = ("StateBackend", "StateFileBackend")


class StateBackend:
    """
    Backend interface used to store operation states.

    A StateBackend load and keep track of a single root state which
    is expected to be modified inplace by the operations (they shall be
    the same instance).
    """

    state: Optional[State] = None
    """ Loaded root state. """
    state_class: Type[State] = State
    """ Operation state class to use for loading and instanciating. """

    def __init__(self, state: Optional[State]):
        # we explicitely force state to be provided even for None.
        # This is up to implementing subclasses to change it.
        self.state = state

    def load(self) -> State | None:
        """
        Load or reload state from the backend.
        """
        return self.state

    def save(self, state: Optional[State] = None):
        """
        Save state in the backend.

        Note that the provided state can be a nested one from the main
        loaded here.
        """
        pass

    def flush(self):
        """Drop state from storage."""
        pass


class StateFileBackend(StateBackend):
    """Load and save state to provided file path.

    You must provide a :py:class:`~django_installer.core.files.FileBackend`
    subclass to handle file writing and saving.

    At loading, when a state is provided but the file doesn't exists, it will
    return the state (by using ``super.load`` method call).
    """

    def __init__(self, path: Path, backend_class: Type[FileBackend], state: Optional[State] = None):
        self.path = path
        self.backend = backend_class(self.state_class)
        super().__init__(state)

    def load(self):
        if not self.path.exists() and self.state:
            return super().load()

        self.state = self.backend.load(self.path)
        return self.state

    def save(self, path: Optional[str | Path] = None):
        """Save state to YAML file."""
        self.backend.save(path or self.path, self.state)
