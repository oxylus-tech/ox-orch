from __future__ import annotations
from datetime import datetime
from enum import Enum
from importlib import metadata
from graphlib import TopologicalSorter
from typing import TypeAlias

from pydantic import Field

from ox_installer.utils import CloneBaseModel
from . import state
from .state import Status


__all__ = ("AppID", "AppMetadata", "resolve_install_order")


AppID: TypeAlias = str
""" Application ID """


class AppMetadata(CloneBaseModel):
    """
    Standardized and generic application metadata.

    Note: the dependencies declared here are python module path to the
    actual django application. Actual dependencies resolution and versioning
    for environment installation are done at the package manager level.
    """

    id: AppID
    """
    Unique name for the application, which actually is the path to the
    application's module.
    """
    name: str
    """ Human readable name of the application. """
    version: str
    """ Package version. """
    package: str
    """ Pypi package providing the app. """

    groups: list[str] = Field(default_factory=list)
    """ Assign Application to groups. """
    tags: list[str] = Field(default_factory=list)
    """ Assign Application to tags. """
    dependencies: list[str] = Field(default_factory=list)
    """ Required dependencies. """

    state: AppInstallState | None = None
    """ Current application install state. """

    def get_installed_version(self) -> str | None:
        """Return installed version read from environment metadata."""
        try:
            return metadata.version(self.package)
        except metadata.PackageNotFoundError:
            return None

    def __hash__(self):
        return hash(self.id)


class InstallOrigin(Enum):
    USER = "user"
    DEPENDENCY = "dependency"


class AppInstallState(state.State):
    """Application installation state."""

    installed_version: str
    """ Application installed version. """
    origin: InstallOrigin = InstallOrigin.USER
    """ Install reason """
    installed_at: datetime | None = None
    """ First installation datetime. """
    enabled: bool = False
    """ The application is enabled. """
    last_migration: str | None = None
    """ Last applied migration. """
    dependents: set[str] = set()
    """ Dependent apps. """

    @property
    def migrated(self):
        return bool(self.last_migration)

    def validate_transition(self, new_status):
        super().validate_transition(new_status)

        if new_status == Status.ROLLING_BACK and self.dependents:
            raise ValueError(
                "This package is required by those applications: {apps}.".format(apps=", ".join(self.dependents))
            )


def resolve_install_order(apps: list[AppMetadata]) -> list[AppMetadata]:
    """
    Returns apps sorted according to required dependencies.
    """
    nodes: dict[str, AppMetadata] = {app.id: app for app in apps}
    ts = TopologicalSorter()

    for app in apps:
        ts.add(app.id, *app.dependencies)

    ordered_ids = list(ts.static_order())
    ordered_apps = [nodes[app_id] for app_id in ordered_ids if app_id in nodes]
    return ordered_apps
