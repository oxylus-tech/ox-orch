from dataclasses import dataclass

from pydantic import Field

from ox_orch.core import register
from ox_orch.apps import AppStore, AppStateFeature, AppStateStore, AppStateStoreFeature


@register("django")
class DjangoStateFeature(AppStateFeature):
    enabled: bool = False
    """ Whether app is enabled or not. """
    last_migration: str | None = None
    """ Last enabled migration. """


@register("django")
class DjangoStateStoreFeature(AppStateStoreFeature):
    """Required data for the django project to be able to run."""

    installed_apps: list[str] = Field(default_factory=list)
    """
    Enabled application, ordered by reverse dependency as for the INSTALLED_APPS
    django settings.
    This is a list of tuples of ``app_ref, app_label``.
    """
    last_migration: str | None = None
    """ Last applied migration. """


@dataclass
class DjangoProject:
    """
    Represent a django project.

    This class can be used by the django project to retrieve relevant information
    as enabled applications.
    """

    store: AppStore
    state_store: AppStateStore

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
