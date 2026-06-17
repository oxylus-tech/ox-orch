from ox_orch.core.registry import register
from ox_orch.utils import LazyTranslation
from .base import Operation


class DjangoRuntime:
    """
    Optional runtime adapter for Django features.

    If Django is not installed, this remains None.
    """

    def __init__(self):
        from django.core.management import call_command
        from django.db import connections
        from django.db.migrations.recorder import MigrationRecorder

        self.call_command = call_command
        self.connections = connections
        self.MigrationRecorder = MigrationRecorder


try:
    DJANGO = DjangoRuntime()
except ImportError:
    import logging

    DJANGO = None
    logger = logging.getLogger()
    logger.warning("Django not available: all related operation will be skipped.")

try:
    from django.utils.translation import gettext_lazy as _
except ImportError:

    def _(v):
        return str(v)


__all__ = ("Migrations", "ManageCommand", "CollectStatic")


@register("django:migrations")
class Migrations(Operation):
    """
    Apply Django migrations incrementally.
    """

    __apply_spec__ = ("app",)
    __rollback_spec__ = ("app",)

    name: str = "migrations"
    label: LazyTranslation = _("Run app migrations")

    def _get_last_applied_migration(self) -> list[tuple[str, str]]:
        recorder = DJANGO.MigrationRecorder(DJANGO.connections["default"])
        return recorder.applied_migrations()

    def _apply(self, state, app):
        if DJANGO is None:
            return

        recorder = DJANGO.MigrationRecorder.Migration
        last_migration_qs = recorder.objects.filter(app=app.id).order_by("-applied")
        last_migration = last_migration_qs.first().name if last_migration_qs.exists() else None
        app.previous_migration = last_migration

        DJANGO.call_command("migrate", app.id, verbosity=1)

    def _rollback(self, state, app):
        """
        Rollback migrations to previous state.
        """
        if DJANGO is None:
            return

        if app.previous_migration:
            DJANGO.call_command("migrate", app.id, app.previous_migration, verbosity=1)


@register("django:manage")
class ManageCommand(Operation):
    """
    Run a generic manage.py command.
    """

    __apply_spec__ = ("app",)
    __rollback_spec__ = ("app",)

    command: str
    args: list[str] = []
    name: str = "manage"
    label: LazyTranslation = _("Manage command")

    def _apply(self, state, app):
        if DJANGO is None:
            return

        DJANGO.call_command(self.command, *self.args)

    def _rollback(self, state, app):
        """
        Generic rollback is undefined.
        Caller decides if safe or not.
        """
        # intentionally undefined
        return


@register("django:collectstatic")
class CollectStatic(ManageCommand):
    __apply_spec__ = ("app",)
    __rollback_spec__ = ("app",)

    command: str = "collectstatic"
    name: str = "manage:collectstatic"
    label: LazyTranslation = _("Collect Static Files")

    def _apply(self, state, app):
        if DJANGO is None:
            return

        DJANGO.call_command(
            "collectstatic",
            interactive=False,
            verbosity=1,
        )

    def _rollback(self, state, app):
        pass
