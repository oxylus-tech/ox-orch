from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from pydantic import Field

from ox_orch.core import register
from ox_orch.apps import AppStore, AppStateFeature, AppStateStore, AppStateStoreFeature


@register("django")
class DjangoStateFeature(AppStateFeature):
    enabled: bool = False
    """ Whether app is enabled or not. """


@register("django")
class DjangoStateStoreFeature(AppStateStoreFeature):
    """Required data for the django project to be able to run."""

    installed_apps: list[str] = Field(default_factory=list)
    """
    Enabled application, ordered by reverse dependency as for the INSTALLED_APPS
    django settings.
    This is a list of tuples of ``app_ref, app_label``.
    """


@dataclass
class DjangoProject:
    """
    Represent a django project.

    This class can be used by the django project to retrieve relevant information
    as enabled applications.
    """

    store: AppStore
    state_store: AppStateStore

    def setup(self, settings_module: str, project_path: Path | None = None):
        """
        Setup Django to run with the provided settings and project path.

        :param settings_module: path to settings module.
        :param project_path: optional path to the project (insert into sys path)
        """
        import os
        import sys
        import django

        if str(project_path) not in sys.path:
            sys.path.insert(0, str(project_path))

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
        django.setup()

    def sync_installed_apps(self):
        """
        Update the list of :py:attr:`~DjangoStateStoreFeature.installed_apps`.

        This will scan application states store to determine which ones to update
        and reverse order apps by dependencies.
        """
        enabled = [st.ref for st in self.state_store.all() if "django" in st.features and st.features["django"]]
        releases = self.store.resolve(enabled)

        installed_apps = []
        for release in releases:
            if feat := release.features.get("django"):
                installed_apps.append(feat.app_label)

        # We reverse the order since Django application dependencies in INSTALLED_APPS
        # are reverse ordered. Dependant applications appear before dependencies.
        installed_apps.reverse()

        feature = self.get_feature()
        feature.installed_apps = installed_apps

    def get_feature(self) -> DjangoStateStoreFeature:
        """Get or create django feature."""
        if "django" not in self.state_store.features:
            feature = DjangoStateStoreFeature()
            self.state_store.features["django"] = feature
            return feature
        return self.state_store.features["django"]

    # ---- Migrations
    def snapshot_migrations(self) -> dict[str, list[str]]:
        """Get a snapshot of migrations."""
        executor = self.get_migration_executor()

        result = defaultdict(list)

        for app_label, migration_name in executor.loader.applied_migrations:
            result[app_label].append(migration_name)

        return dict(result)

    def restore_migrations(self, snapshot: dict[str, list[str]]):
        """Restore migrations to a provided snapshot."""
        executor = self.get_migration_executor()

        targets = []

        for app_label in executor.loader.migrated_apps:
            migrations = snapshot.get(app_label)

            if migrations:
                targets.append((app_label, migrations[-1]))
            else:
                targets.append((app_label, None))

        # Django will handle dependencies resolution.
        executor.migrate(targets)

    def get_migration_executor(self):
        """Return migration executor."""
        return MigrationExecutor(connections["default"])
