from ox_orch.core import register
from ox_orch.operations import Subprocess
from ox_orch.operations.multiprocessing import ForkChild

from ..shell import ManageCommandShell


__all__ = ("ManageCommand", "CollectStatic")


@register("django:manage")
class ManageCommand(ForkChild, Subprocess):
    """Run a generic manage.py command."""

    _shell = ManageCommandShell()
    label = "Manage command"


@register("django:collectstatic")
class CollectStatic(ManageCommand):
    """Run collectstatic project wide."""

    label = "Collect Static Files"
    forward = ["collectstatic"]
