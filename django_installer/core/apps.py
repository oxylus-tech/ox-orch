from __future__ import annotations
from datetime import datetime
from graphlib import TopologicalSorter
from typing import Optional, TypeAlias

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _
from pydantic import BaseModel, Field

from . import state
from .status import Status


__all__ = ("AppID", "AppMetadata", "resolve_install_order")


AppID: TypeAlias = str
""" Application ID """


class AppMetadata(BaseModel):
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
    """ Version. """
    package: str
    """ Pypi package providing the app. """

    groups: list[str] = Field(default_factory=list)
    """ Assign Application to groups. """
    tags: list[str] = Field(default_factory=list)
    """ Assign Application to tags. """
    dependencies: list[str] = Field(default_factory=list)
    """ Required dependencies. """

    state: Optional[AppInstallState] = None
    """ Current application install state. """


class InstallOrigin(TextChoices):
    USER = "user", _("Installed by user")
    DEPENDENCY = "dependency", _("Installed as dependency")


class AppInstallState(state.State):
    """Application installation state."""

    installed_at: Optional[datetime] = None
    """ First installation datetime. """
    enabled: bool = False
    """ The application is enabled. """
    last_migration: Optional[str] = None
    """ Last applied migration. """
    dependents: set[str] = set()
    """ Dependent apps. """
    installed_as: InstallOrigin = InstallOrigin.USER
    """ Install reason """

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
