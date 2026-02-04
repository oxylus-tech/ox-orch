from graphlib import TopologicalSorter
from typing import Optional
from pydantic import BaseModel


__all__ = ("AppMetadata", "resolve_install_order")


class AppMetadata(BaseModel):
    id: str
    name: str
    version: str
    groups: list[str] = []
    tags: list[str] = []
    dependencies: dict[str, list[str]] = {}  # {"required": [...], "optional": [...]}
    conflicts: list[str] = []
    # hooks: dict[str, str] = {}  # pre_install, post_install, etc.
    package: str  # PyPI package providing multiple apps
    # assets: dict[str, bool] = {}  # collectstatic, translations
    previous_migration: Optional[str] = None  # track last applied migration


def resolve_install_order(apps: list[AppMetadata]) -> list[AppMetadata]:
    """
    Returns apps sorted according to required dependencies.
    """
    nodes: dict[str, AppMetadata] = {app.id: app for app in apps}
    ts = TopologicalSorter()

    for app in apps:
        deps = app.dependencies.get("required", [])
        ts.add(app.id, *deps)

    ordered_ids = list(ts.static_order())
    ordered_apps = [nodes[app_id] for app_id in ordered_ids if app_id in nodes]
    return ordered_apps
