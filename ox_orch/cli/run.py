from __future__ import annotations

import json
from pathlib import Path
import traceback

import click
from rich import print

from ox_orch.core import files, Status, ExecutionReplay
from ox_orch.operations import ExecutionSpec, OperationState, Executor

from .base import cli
from .utils import load_file, save_file


__all__ = ("run", "apply", "rollback", "run_executor")


@cli.group()
@click.option("--save", "-S", type=click.Path(dir_okay=False, path_type=Path), help="Path to save updated state.")
@click.option(
    "--context", "-c", type=click.Path(dir_okay=False, path_type=Path), help="Use this file as inputs arguments"
)
@click.option(
    "--input", "-i", multiple=True, help="Context value, as `key=value`, where value is a json serialized value."
)
@click.pass_context
def run(ctx, state=None, context=None, input=None, save=None):
    """Run an operation workflow."""
    context_ = context and load_file(context, None) or {}
    inputs = read_ctx(input, **context_)

    if save and not save.parent.exists():
        raise ValueError(f"Save path: parent directory `{save.parent}` does not exists")

    ctx.obj.update(
        {
            "state_save_path": save,
            "inputs": inputs,
        }
    )


def read_ctx(inputs, **context):
    """Read context provided as cli argument and return the full context."""
    if inputs:
        for item in inputs:
            key, val = item.split("=", 1)
            context[key] = json.loads(val.split())
    return context


@run.command("apply")
@click.argument("conf", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.option(
    "--state",
    "-s",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to state file to load (mandatory for rollback).",
)
@click.option("--rollback", is_flag=True, help="Rollback on failure.")
@click.pass_context
def apply(ctx, conf, state=None, rollback=False):
    """Apply an operation."""
    spec = (load_file(conf, ExecutionSpec, exc=True),)
    state = load_file(state, OperationState) or None
    inputs = ctx.obj["inputs"]
    executor = Executor()

    print(f"Apply [magenta]{spec.operation.id}[/magenta]")
    state = run_executor(executor.apply(spec, inputs))

    if save_to := ctx.obj["state_save_path"]:
        save_file(save_to, OperationState, state)

    if state.status == Status.FAILED and rollback:
        print("[yellow]Apply failed and rollback enabled:[/yellow] rollback")
        run_executor(executor.rollback(spec, state, inputs))


@run.command("rollback")
@click.argument("conf", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.argument(
    "state",
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.pass_context
def rollback(ctx, conf, state):
    """Rollback an operation using provided status."""
    if not ctx.obj["state"]:
        raise ValueError("Missing state file to rollback from.")

    save_to = ctx.obj["state_save_path"]
    if not save_to:
        print("[yellow][Warning][/yellow] You did not provide a path to save the state file using --save.")
        print(f"We will use [magenta]{state}[/magenta]")
        save_to = state

    state = (load_file(state, OperationState) or None,)
    spec = (load_file(conf, ExecutionSpec, exc=True),)
    inputs = ctx.obj["inputs"]
    state = ctx.obj["state"]
    executor = Executor()

    print(f"Rollback [magenta]{spec.operation.id}[/magenta]")
    state = run_executor(executor.rollback(spec, state, inputs))
    save_file(save_to, OperationState)


def run_executor(gen):
    """From the executor apply or rollback generator."""
    print()

    state = None
    for state in gen:
        print(f"[yellow][{state.operation_id}][/yellow]: {state.get_status_display()}")

    if not state:
        print("Nothing to run. Exit")
        return

    for state in gen:
        print(f"[yellow][{state.operation_id}][/yellow]: {state.get_status_display()}")

    print()
    print(f"[magenta]{state.operation.id}[/magenta] finished to run")
    print(f"Resulting state is {state.get_status_display()}")
    if state.status is Status.FAILED:
        print(f"[red]Error:[/red] {state.error}")
        if state._exc:
            msg = 20 * "-" + " Traceback " + 20 * "-"
            print(f"[b red]{msg}[/b red]\n")
            traceback.print_exception(state._exc)
            print("[b red]" + len(msg) * "-" + "[/b red]")

    return state


@cli.command()
@click.option("--trace", "trace_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--format", "fmt", type=click.Choice(["json", "summary"]), default="summary")
def replay(trace_path: Path, fmt: str):
    """
    Replay a previously executed run from trace.
    """

    backend = files.JSONBackend(None)
    replayer = ExecutionReplay(backend=backend)

    state = replayer.replay(trace_path)
    if fmt == "json":
        click.echo(state.model_dump_json(indent=2))
    else:
        click.echo(f"Run: {state.run_id}")
        click.echo(f"Operations: {len(state.operations)}")
        click.echo(f"Errors: {len(state.errors)}")
