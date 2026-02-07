from datetime import datetime
from graphlib import TopologicalSorter
from typing import Optional

from pydantic import BaseModel, Field


__all__ = ("AppMetadata", "resolve_install_order")


class AppMetadata(BaseModel):
    """
    Standardized and generic application metadata.

    Note: the dependencies declared here are python module path to the
    actual django application. Actual dependencies resolution and versioning
    for environment installation are done at the package manager level.
    """

    id: str
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

    installed_at: Optional[datetime] = None
    """ Date of installation. """
    previous_migration: Optional[str] = None  # track last applied migration
    """ Previous applied migration. """


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
