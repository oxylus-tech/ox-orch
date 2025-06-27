from __future__ import annotations


import click


from ox_orch.utils import load_modules


__all__ = ("cli",)


@click.group()
@click.option("--module", "modules", multiple=True, help="Import module registering operations and hooks.")
@click.pass_context
def cli(ctx, modules):
    load_modules(modules)
    ctx.obj = {
        "modules": modules,
    }
