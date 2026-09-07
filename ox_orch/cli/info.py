from __future__ import annotations

from typing import Type

import click


from ox_orch.core import CONTEXT_INPUT_REGISTRY, Registry
from ox_orch.hooks.base import EXECUTOR_HOOK_REGISTRY
from ox_orch.operations import OPERATION_REGISTRY, STATE_REGISTRY

from .base import cli
from .utils import print_registry_info

__all__ = (
    "info",
    "registries",
)


registries: dict[str, Type[Registry]] = {
    "operations": OPERATION_REGISTRY,
    "hooks": EXECUTOR_HOOK_REGISTRY,
    "states": STATE_REGISTRY,
    "contexts": CONTEXT_INPUT_REGISTRY,
}


@cli.command("info")
@click.argument("what", type=click.Choice(list(registries.keys())))
@click.option("--details", "-d", is_flag=True, help="Show detailed informations.")
def info(what=None, details=False):
    """Fetch an display various information."""
    if registry := registries.get(what):
        print_registry_info(f"{registry.label}", registry)  # , details=details)


# ---------------------------------------------------------
# CLI group
# ---------------------------------------------------------

# TODO:
# Use one function that take the registry name as input and use a dict
# to look them up. Allows extensions to add their registry to cli.
# => requires extra fields _label and _description on the DocumentedRegistry class
