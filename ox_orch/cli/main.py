from __future__ import annotations

import json
from pathlib import Path

import click

from ox_orch.core.state import StateFileBackend, StateYAMLBackend
from ox_orch.core.execution import Executor, ExecutionSpec
from ox_orch.core.resolver import OperationResolver, HookResolver
from ox_orch.operations.base import RunContext


__all__ = ("cli",)


@click.group()
def cli():
    """
    Ox-Orch command line interface.

    This CLI is intentionally thin:
    - It loads an ExecutionSpec
    - Resolves operations and hooks
    - Delegates execution to Executor
    """
    pass


# ----------------------------------------------------------------------
# Apply
# ----------------------------------------------------------------------


@cli.command()
@click.option(
    "--spec",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to execution spec (YAML/JSON serialized ExecutionSpec).",
)
@click.option(
    "--state",
    type=click.Path(dir_okay=False),
    required=False,
    help="Optional state file override (overrides spec.state_path).",
)
def apply(spec: str, state: str | None):
    """
    Execute an operation defined by an ExecutionSpec file.
    """
    backend = StateFileBackend(StateYAMLBackend)

    spec_path = Path(spec)
    spec_obj: ExecutionSpec = backend.load(spec_path)

    state_path = Path(state) if state else (Path(spec_obj.state_path) if spec_obj.state_path else None)

    resolver = OperationResolver()
    hook_resolver = HookResolver()

    # Resolve operation
    operation_cls = resolver.resolve(spec_obj.operation)
    operation = operation_cls()

    # Load state
    state_obj = None
    if state_path:
        state_obj = backend.load(state_path)

    # Resolve hooks
    hooks = [hook_resolver.resolve(hook_ref)() for hook_ref in spec_obj.hooks]

    executor = Executor(hooks=hooks)

    run_context = RunContext(trigger=spec_obj.run_trigger)

    result = executor.apply(
        operation,
        state=state_obj,
        context=spec_obj.context,
        run_context=run_context,
    )

    # Persist state
    if state_path:
        backend.save(result, state_path)

    click.echo(f"Execution completed\n" f"- run_id: {run_context.run_id}\n" f"- status: {result.status}")


# ----------------------------------------------------------------------
# Rollback
# ----------------------------------------------------------------------


@cli.command()
@click.option(
    "--spec",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to execution spec.",
)
@click.option(
    "--state",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
    help="Override state file.",
)
def rollback(spec: str, state: str | None):
    """
    Rollback an operation defined in an ExecutionSpec.
    """
    backend = StateFileBackend(StateYAMLBackend)

    spec_path = Path(spec)
    spec_obj: ExecutionSpec = backend.load(spec_path)

    state_path = Path(state) if state else Path(spec_obj.state_path)

    if not state_path:
        raise click.ClickException("No state file provided.")

    resolver = OperationResolver()
    hook_resolver = HookResolver()

    operation_cls = resolver.resolve(spec_obj.operation)
    operation = operation_cls()

    state_obj = backend.load(state_path)

    hooks = [hook_resolver.resolve(hook_ref)() for hook_ref in spec_obj.hooks]

    executor = Executor(hooks=hooks)

    result = executor.rollback(operation, state_obj)

    backend.save(result, state_path)

    click.echo(f"Rollback completed\n" f"- status: {result.status}")


# ----------------------------------------------------------------------
# Utility: inspect spec
# ----------------------------------------------------------------------


@cli.command()
@click.option(
    "--spec",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
)
def show(spec: str):
    """
    Print an ExecutionSpec in human-readable form.
    """
    backend = StateFileBackend(StateYAMLBackend)

    spec_obj: ExecutionSpec = backend.load(Path(spec))

    click.echo(json.dumps(spec_obj.model_dump(), indent=4, default=str))
