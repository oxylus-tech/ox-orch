from django.core.management import call_command
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django.utils.translation import gettext_lazy as _

from django_installer.utils import LazyTranslation
from .base import AbstractOperation


__all__ = ("Migrations", "ManageCommand", "CollectStatic")


class Migrations(AbstractOperation):
    """
    Apply Django migrations incrementally.
    """

    name: str = "migrations"
    label: LazyTranslation = _("Run app migrations")

    def _get_last_applied_migration(self) -> list[tuple[str, str]]:
        recorder = MigrationRecorder(connections["default"])
        return recorder.applied_migrations()

    def _apply(self, app):
        recorder = MigrationRecorder.Migration
        last_migration_qs = recorder.objects.filter(app=app.id).order_by("-applied")
        last_migration = last_migration_qs.first().name if last_migration_qs.exists() else None
        app.previous_migration = last_migration

        call_command("migrate", app.id, verbosity=1)

    def _rollback(self, app):
        """
        Rollback migrations to previous state.
        """
        if app.previous_migration:
            call_command("migrate", app.id, app.previous_migration, verbosity=1)


class ManageCommand(AbstractOperation):
    """
    Run a generic manage.py command.
    """

    command: str
    args: list[str] = []
    name: str = "manage"
    label: LazyTranslation = _("Manage command")

    def _apply(self, app):
        call_command(self.command, *self.args)

    def _rollback(self, app):
        """
        Generic rollback is undefined.
        Caller decides if safe or not.
        """
        pass


class CollectStatic(ManageCommand):
    command: str = "collectstatic"
    name: str = "manage:collectstatic"
    label: LazyTranslation = _("Collect Static Files")

    def _apply(self, app):
        # if settings.STATIC_ROOT.exists():
        #    target = ox_settings.external_data_dir / "lifecycle" / "backups"
        #    # TODO here
        pass

    def _rollback(self, app):
        pass
