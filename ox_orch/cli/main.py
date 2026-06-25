from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich import print
from rich.align import Align
from rich.table import Table

from ox_orch.apps import AppFileStore
from ox_orch.apps.provider import AppProvider

from ox_orch.core import JSONBackend, ExecutionReplay
from ox_orch.operations import OPERATION_REGISTRY, STATE_REGISTRY, Executor, ExecutionSpec
from ox_orch.utils import load_modules


def create_table(title, columns, title_style="b yellow", expand=True):
    t = Table(title=title, title_style=title_style, expand=expand)
    for col in columns:
        if isinstance(col, str):
            t.add_column(col)
        else:
            t.add_column(col[0], style=col[1])
    return t


# ---------------------------------------------------------
# CLI group
# ---------------------------------------------------------


@click.group()
@click.option("--module", "modules", multiple=True, help="Import module registering operations and hooks.")
@click.pass_context
def cli(ctx, modules):
    load_modules(modules)
    ctx.obj = {
        "modules": modules,
    }


@cli.command("operations")
@click.option("--details", "-d", is_flag=True, help="Show detailed informations.")
def list_operations(details):
    """
    List registered operations.
    """
    from ox_orch.operations.base import OPERATION_REGISTRY

    for type_id, cls in sorted(OPERATION_REGISTRY.items()):
        click.echo(f"{type_id:<40} {cls.__module__}.{cls.__name__}")

    if details:
        print()
        display_registry_info("Operations & Fields", OPERATION_REGISTRY)


@cli.command("hooks")
def list_hooks():
    """List registered hooks."""
    from ox_orch.hooks.base import EXECUTOR_HOOK_REGISTRY

    for type_id, cls in sorted(EXECUTOR_HOOK_REGISTRY.items()):
        click.echo(f"{type_id:<30} {cls.__module__}.{cls.__name__}")


@cli.command("states")
def list_states():
    """List registered operation states."""
    display_registry_info("Operations State & Fields", STATE_REGISTRY)


def display_registry_info(title, registry):
    table = create_table(title, columns=["Name", "Label / Default", "Description"])
    infos = registry.get_infos(skip_no_doc=True)
    infos.sort(key=lambda o: o.type_id)

    for info in infos:
        table.add_row(f"[b]{info.type_id}[/b]", f"[b]{info.label}[/b]", f"[b]{info.description}[/b]")

        if info.fields:
            table.add_section()
            for field in info.fields:
                table.add_row(
                    Align(f"[i]{field.name}[/i]", "right"),
                    Align(f"[i cyan]{field.default}[/i cyan]", "right"),
                    f"[i]{field.description}[/i]",
                )
        table.add_section()
    print(table)


# ---------------------------------------------------------
# Applications
# ---------------------------------------------------------
@cli.group()
def apps():
    pass


@apps.command("import")
@click.argument("path", type=click.Path(dir_okay=False, path_type=Path))
@click.argument("packages", nargs=-1)
def apps_import(packages, path):
    """Import applications from Pypi and save them to the AppStore."""
    app_store = AppFileStore(path=path)
    app_store.load()

    provider = AppProvider()
    apps = asyncio.run(provider.build(packages))

    print(f"We got {len(apps)} application from the provided package list.")
    app_store.commit(apps)
    app_store.save()
    print(f"Store saved to `{path}`")


@apps.command("list")
@click.argument("path", type=click.Path(dir_okay=False, path_type=Path))
def apps_list(path):
    """Import applications from Pypi and save them to the AppStore."""
    app_store = AppFileStore(path=path)
    app_store.load()

    print(f"[b yellow]{'Id':<30} {'Version':<20} Package[/b yellow]")
    for app in app_store.all():
        print(f"{app.id:<30} {app.version:<20} {app.package}")


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------
@cli.command()
@click.argument("operation")
@click.option("--state-file", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--hook", "hooks", multiple=True, help="Executor hook identifier.")
@click.option("--context", multiple=True, help="Execution context key=value.")
@click.option("--backend", default="yaml", show_default=True)
@click.option("--trigger", default="cli", show_default=True)
@click.option("--dry-run", is_flag=True)
def run(operation, state_file, hooks, context, backend, trigger, dry_run):
    """Execute an operation."""

    operation = OPERATION_REGISTRY.get(operation)()
    state = None

    if state_file:
        backend_obj = None
        # backend_obj = get_state_backend(backend)

        if state_file.exists():
            state = backend_obj.load(state_file)
        else:
            state = operation.create_state()
            state._source = state_file
    else:
        state = operation.create_state()

    spec = ExecutionSpec(
        operation=operation,
        state=state,
        hooks=list(hooks),
        # context=parse_context(context),
        backend=backend,
        dry_run=dry_run,
        trigger=trigger,
    )
    executor = Executor()
    executor.apply_sync(spec)
    click.echo("Execution completed.")


# ---------------------------------------------------------
# ROLLBACK
# ---------------------------------------------------------
@cli.command()
@click.argument("state_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--hook", "hooks", multiple=True)
@click.option("--context", multiple=True)
@click.option("--backend", default="yaml", show_default=True)
@click.option("--dry-run", is_flag=True)
def rollback(operation_file, state_file, hooks, context, backend, dry_run):
    """
    Rollback a previously executed operation.
    """
    backend_obj = None
    # backend_obj = get_state_backend(backend)
    state = backend_obj.load(state_file)
    operation = OPERATION_REGISTRY.get(state._operation_id)
    spec = ExecutionSpec(
        operation=operation,
        state=state,
        hooks=list(hooks),
        # context=parse_context(context),
        backend=backend,
        dry_run=dry_run,
        trigger="cli",
    )
    executor = Executor()
    executor.rollback_sync(spec)
    click.echo("Rollback completed.")


# ---------------------------------------------------------
# REPLAY
# ---------------------------------------------------------
@cli.command()
@click.option("--trace", "trace_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--format", "fmt", type=click.Choice(["json", "summary"]), default="summary")
def replay(trace_path: Path, fmt: str):
    """
    Replay a previously executed run from trace.
    """

    backend = JSONBackend(None)
    replayer = ExecutionReplay(backend=backend)

    state = replayer.replay(trace_path)
    if fmt == "json":
        click.echo(state.model_dump_json(indent=2))
    else:
        click.echo(f"Run: {state.run_id}")
        click.echo(f"Operations: {len(state.operations)}")
        click.echo(f"Errors: {len(state.errors)}")
