from __future__ import annotations

from pathlib import Path

import click
from rich import print

from ox_orch.apps import AppFileStore
from ox_orch.apps.provider import AppProvider


from .base import cli


__all__ = (
    "apps",
    "list_apps",
    "import_apps",
)


@cli.group()
def apps():
    """Provide utilities to work with applications and stores."""
    pass


@apps.command("list")
@click.argument("path", type=click.Path(dir_okay=False, path_type=Path))
def list_apps(path):
    """List applications stored in the provided app store."""
    app_store = AppFileStore(path=path)
    app_store.load()

    print(f"[b yellow]{'Id':<30} {'Version':<20} Package[/b yellow]")
    for app in app_store.all():
        print(f"{app.id:<30} {app.version:<20} {app.package}")


@apps.command("import")
@click.argument("path", type=click.Path(dir_okay=False, path_type=Path))
@click.argument("packages", nargs=-1)
def import_apps(packages, path):
    """Import applications from Pypi and save them to the app store."""
    app_store = AppFileStore(path=path)
    app_store.load()

    provider = AppProvider()
    apps = provider.build(packages)

    print(f"We got {len(apps)} application from the provided package list.")
    app_store.commit(apps)
    app_store.save()
    print(f"Store saved to `{path}`")
