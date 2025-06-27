from __future__ import annotations


import click
from rich import print


from ox_orch.hooks.base import EXECUTOR_HOOK_REGISTRY
from ox_orch.operations import OPERATION_REGISTRY, STATE_REGISTRY

from .base import cli
from .utils import print_registry_info

__all__ = ("info", "list_operations", "list_hooks", "list_states")


@cli.group()
def info():
    """Fetch an display various information."""
    pass


# ---------------------------------------------------------
# CLI group
# ---------------------------------------------------------


@info.command("operations")
@click.option("--details", "-d", is_flag=True, help="Show detailed informations.")
def list_operations(details):
    """
    List registered operations.
    """
    for type_id, cls in sorted(OPERATION_REGISTRY.items()):
        click.echo(f"{type_id:<40} {cls.__module__}.{cls.__name__}")

    if details:
        print()
        print_registry_info("Operations & Fields", OPERATION_REGISTRY)


@info.command("hooks")
def list_hooks():
    """List registered hooks."""

    for type_id, cls in sorted(EXECUTOR_HOOK_REGISTRY.items()):
        click.echo(f"{type_id:<30} {cls.__module__}.{cls.__name__}")


@info.command("states")
def list_states():
    """List registered operation states."""
    print_registry_info("Operations State & Fields", STATE_REGISTRY)
