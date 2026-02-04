from graphlib import TopologicalSorter
from typing import List, Dict
from .apps import AppMetadata


def resolve_install_order(apps: List[AppMetadata]) -> List[AppMetadata]:
    """
    Returns apps sorted according to required dependencies.
    """
    nodes: Dict[str, AppMetadata] = {app.id: app for app in apps}
    ts = TopologicalSorter()

    for app in apps:
        deps = app.dependencies.get("required", [])
        ts.add(app.id, *deps)

    ordered_ids = list(ts.static_order())
    ordered_apps = [nodes[app_id] for app_id in ordered_ids if app_id in nodes]
    return ordered_apps
