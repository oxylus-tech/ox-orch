from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

from pydantic import Field

from ox_orch.core import register
from ox_orch.apps import Application, AppFeature, AppStore, AppStateFeature, AppStateStore, AppStateStoreFeature


@register("django")
class DjangoAppFeature(AppFeature):
    """
    Application feature for Django.
    """

    apps: list[str]
    """ Django application paths, following INSTALLED_APPS order. """


@register("django")
class DjangoStateFeature(AppStateFeature):
    """Application state feature for Django."""

    enabled: list[str] = Field(default_factory=list)
    """
    The list of enabled Django application paths.
    """


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

    state_store: AppStateStore
    store: AppStore | None = None

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

    def get_feature(self) -> DjangoStateStoreFeature:
        """Get or create django feature."""
        if "django" not in self.state_store.features:
            feature = DjangoStateStoreFeature()
            self.state_store.features["django"] = feature
            return feature
        return self.state_store.features["django"]

    def get_installed_apps(self) -> list[str]:
        """
        Return installed application.

        Shorthand to access :py:attr:`DjangoStateStoreFeature.installed_apps`.
        """
        if feature := self.state_store.features.get("django"):
            return feature.installed_apps
        return []

    def enable(self, apps: list[Application]):
        """Enable applications and synchronize stores."""
        app_ids = [app.id for app in apps]
        app_states = {st.id: st for st in self.state_store.get_all(app_ids)}

        commits, updates = [], {}
        for app in apps:
            enabled = {"django": DjangoStateFeature(enabled=app.features["django"].apps)}
            if app_state := app_states.get(app.id):
                updates[app_state.id] = {"features": enabled}
            else:
                commits.append(app.create_state(features=enabled))

        self.state_store.commit(commits)
        self.state_store.partial_commit(updates, merge=True)

    def sync_installed_apps(self):
        """
        Update the list of :py:attr:`~DjangoStateStoreFeature.installed_apps`.

        This will scan application states store to determine which ones to update
        and reverse order apps by dependencies.
        """
        self._assert_has_store()

        d_states = {st.ref: st for st in self.state_store.all() if st.features.get("django")}
        releases = self.store.resolve(d_states.keys())

        installed_apps = []
        for release in releases:
            if d_state := d_states.get(release.ref):
                installed_apps.extend(d_state.features["django"].enabled)

        # We reverse the order since Django application dependencies in INSTALLED_APPS
        # are reverse ordered. Dependant applications appear before dependencies.
        installed_apps.reverse()

        feature = self.get_feature()
        feature.installed_apps = installed_apps

        if hasattr(self.state_store, "save"):
            self.state_store.save()

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
        from django.db import connections
        from django.db.migrations.executor import MigrationExecutor

        return MigrationExecutor(connections["default"])

    def _assert_has_store(self):
        if self.store is None:
            raise ValueError("To run this method, you must provide an application store.")
