from pathlib import Path

from django.core.management import call_command
from pydantic import Field

from ox_orch.core import register
from ox_orch.operations import Operation, OperationState, Plan, ShellOperation

from .project import DjangoProject
from .shell import ManageCommandShell


__all__ = (
    "DjangoContext",
    "DjangoEnable",
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

    @classmethod
    def from_apps_ctx(cls, apps_ctx, **kwargs):
        """
        Create a new instance of the context, using apps context to init the
        django project instance.
        """
        kwargs["project"] = DjangoProject(store=apps_ctx.store, state_store=apps_ctx.state_store)
        return cls(**kwargs)


@register("django:enable")
class DjangoEnable(Operation):
    """
    Enable all Django applications of an Application.

    Currently we don't provide support for enabling only a subset of applications,
    as this would mean dependency management at this level. Dependencies are
    already handled at the Application level, so if you want fine-grained
    enabling, you shall divide the target app in multiple python packages.

    This application MUST be run inside an :py:class:`~ox_orch.operations.apps.AppPlan`.
    """

    __apply_spec__ = ("app_ctx",)

    def _apply(self, state, *_, app_ctx, **__):
        if feature := app_ctx.app.features.get("django"):
            app_ctx.app_plan_state.add_facts({"features": {"django": {"enabled": list(feature.apps)}}})

    # Rollback is handled by upstream state restoration.


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
class ManageCommand(ShellOperation):
    """Run a generic manage.py command."""

    _shell = ManageCommandShell(None)
    label = "Manage command"


@register("django:collectstatic")
class CollectStatic(ManageCommand):
    """Run collectstatic project wide."""

    label = "Collect Static Files"
    forward: list[str] = ["collectstatic"]


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

    It runs common post-install operations at a global level (not per-application),
    such as migration or collectstatic.

    Operations flowchart:

        - :py:attr:`setup`: initialize Django (setup).
        - :py:attr:`before_migrate` (optional): operations to run before migrations.
        - :py:attr:`migrate`: apply migrations.
        - :py:attr:`after_migrate` (optional): operations to run after migrations.
        - :py:attr:`collectstatic` (optional, enabled by default): collect statics.
        - :py:attr:`operations` (optional): other operations to run.
    """

    setup: DjangoSetup = Field(default_factory=DjangoSetup)
    """ Operation ensuring django is setup. """
    before_migrate: list[Operation] = Field(default_factory=list)
    """ Operations to run before migrations happens. """
    migrate: Migrate = Field(default_factory=Migrate)
    """ Apply Django migrations. """
    after_migrate: list[Operation] = Field(default_factory=list)
    """ Operation to run after Django migration. """
    collectstatic: CollectStatic | None = Field(default_factory=CollectStatic)
    """ Collect static data. """

    def get_operations(self, state):
        operations = [self.setup, *self.before_migrate, self.migrate, *self.after_migrate]

        if self.collectstatic:
            operations.append(self.collectstatic)
        if self.operations:
            operations.extend(self.operations)
        return operations
