from __future__ import annotations
from datetime import datetime
from enum import Enum


from ox_orch.core import stores
from .app import Versioned


__all__ = ("InstallOrigin", "AppState", "AppStateStore", "AppStateMemoryStore", "AppStateFileStore")


class InstallOrigin(Enum):
    USER = "user"
    DEPENDENCY = "dependency"


class AppState(Versioned):
    """Application installation state."""

    package: str
    """ Installed package. """
    source: str | None = None
    """ Source from which the package has been installed. """
    origin: InstallOrigin = InstallOrigin.USER
    """ Install reason """
    installed_at: datetime | None = None
    """ First installation datetime. """
    enabled: bool = False
    """ The application is enabled. """
    last_migration: str | None = None
    """ Last applied migration. """
    # dependents: set[str] = set()
    # """ Dependent apps. """

    @property
    def migrated(self):
        return bool(self.last_migration)

    def validate_transition(self, new_status):
        super().validate_transition(new_status)

        # FIXME
        # if new_status == Status.ROLLING_BACK and self.dependents:
        #    raise ValueError(
        #        "This package is required by those applications: {apps}.".format(apps=", ".join(self.dependents))
        #    )


class AppStateStore(stores.Store):
    """Application state store."""

    model_class = AppState
    key = "id"


class AppStateMemoryStore(AppStateStore, stores.MemoryStore):
    pass


class AppStateFileStore(AppStateStore, stores.FileStore):
    pass
