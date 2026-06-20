from pathlib import Path

from django.core.management import call_command
from pydantic import Field

from ox_orch.core import register
from ox_orch.operations import Operation, OperationState, Plan, Subprocess

from .project import DjangoProject
from .shell import ManageCommandShell


__all__ = (
    "DjangoContext",
    "DjangoSetup",
    "ManageCommand",
    "CollectStatic",
    "MigrationState",
    "Migrate",
    "DjangoReconciliation",
)


class DjangoContext:
    """
    This provide context information to run Django related operations.
    """

    project: DjangoProject
    """ The Django project object. """
    settings_module: str
    """ Path to the settings. """
    project_path: Path | None = None
    """ Path to the project. If not provided, assumes it is in current directory. """
    debug: bool = False
    """ Enable DEBUG. """

    @classmethod
    def from_apps_ctx(cls, apps_ctx, **kwargs):
        """
        Create a new instance of the context, using apps context to init the
        django project instance.
        """
        kwargs["project"] = DjangoProject(store=apps_ctx.store, state_store=apps_ctx.state_store)
        return cls(**kwargs)


@register("django:setup")
class DjangoSetup(Operation):
    """
    Setup a django project environment.

    .. important::

        As specified by the Django documentation, setup can only happens once,
        so you MUST ensure that it will be the case, either by running only
        once this operation per process, or either by spawning it into a child
        process.

        It also mean that there is no rollback possible.

    """

    def _apply(self, state, *_, django_ctx: DjangoContext, **__):
        django_ctx.project.setup(django_ctx.settings_module, django_ctx.project_path)


@register("django:manage")
class ManageCommand(Subprocess):
    """Run a generic manage.py command."""

    _shell = ManageCommandShell()
    label = "Manage command"


@register("django:collectstatic")
class CollectStatic(ManageCommand):
    """Run collectstatic project wide."""

    label = "Collect Static Files"
    forward = ["collectstatic"]


class MigrationState(OperationState):
    """
    Snapshot of migration state before and after migration execution.
    """

    backward: dict[str, list[str]] = Field(default_factory=dict)
    """ Previous migration snapshot. """
    forward: dict[str, list[str]] = Field(default_factory=dict)
    """ New migration snapshot. """


@register("django:migrate")
class Migrate(Operation):
    """Apply migrations and capture migration graph state."""

    __state_class__ = MigrationState
    __apply_spec__ = ("django_ctx",)

    def _apply(self, state, ctx, django_ctx, **inputs):
        project = django_ctx.project

        state.backward = project.snapshot_migrations()
        call_command("migrate", interactive=False, verbosity=1)
        state.forward = project.snapshot_migrations()

    def _rollback(self, state, ctx, django_ctx, **inputs):
        django_ctx.project.restore_migrations(state.backward)


@register("django:reconciliation")
class DjangoReconciliation(Plan):
    """
    Django reconciliation pipeline.

    The provided extra ``operations`` will be run after all other ones (setup, migrate,
    collecstatic).
    """

    setup: DjangoSetup = Field(default_factory=DjangoSetup)
    migrate: Migrate = Field(default_factory=Migrate)
    collectstatic: CollectStatic | None = None

    def get_operations(self, state):
        operations = [self.setup, self.migrate]

        if self.collectstatic:
            operations.append(self.collectstatic)
        if self.operations:
            operations.extend(self.operations)
        return operations
