from __future__ import annotations
from enum import Enum

from pydantic import Field


from ox_orch.core import stores, JSONBackend, Registry, PolymorphicModel
from .app import Versioned, Application


__all__ = (
    "InstallOrigin",
    "APP_STATE_FEATURE_REGISTRY",
    "APP_STATE_STORE_FEATURE_REGISTRY",
    "AppStateFeature",
    "AppState",
    "AppStateStore",
    "AppStateMemoryStore",
    "AppStateFileStore",
)


class InstallOrigin(Enum):
    USER = "user"
    DEPENDENCY = "dependency"


APP_STATE_FEATURE_REGISTRY = Registry()
APP_STATE_STORE_FEATURE_REGISTRY = Registry()


class AppStateFeature(PolymorphicModel):
    """
    State information of an extension for an application.

    See :py:class:`.app.AppFeature` for more information about how features
    work.
    """

    __registry__ = APP_STATE_FEATURE_REGISTRY


class AppState(Versioned):
    """Application installation state."""

    package: str
    """ Installed package. """
    source: str | None = None
    """ Source from which the package has been installed. """
    origin: InstallOrigin = InstallOrigin.USER
    """ Install reason """
    # dependents: set[str] = set()
    # """ Dependent apps. """
    features: dict[str, AppStateFeature] = Field(default_factory=dict)
    """ Optional features extension data. """

    @property
    def migrated(self):
        return bool(self.last_migration)

    def validate_transition(self, new_status):
        super().validate_transition(new_status)

        # FIXME
        # if new_status == Status.ROLLING_BACK and self.dependents:
        #    raise ValueError(
        #        "This package is required by those applications: {apps}.".format(apps=", ".join(self.dependents))
        #    )


class AppStateStoreFeature(PolymorphicModel):
    """
    Extra features that can be appended to the store itself.

    See :py:class:`.app.AppFeature` for more information about how features
    work.
    """

    __registry__ = APP_STATE_STORE_FEATURE_REGISTRY


class AppStateStoreModel(stores.FileStoreModel):
    """Provide features to the AppStateStore."""

    features: dict[str, AppStateFeature] = Field(default_factory=dict)
    """ Optional features extension data. """


class AppStateStore(stores.Store):
    """Application state store."""

    model_class = AppState
    key = "id"
    backend = JSONBackend(AppStateStoreModel)
    features: dict[str, AppStateStoreFeature] = None

    def __init__(self, *args, features: dict[str, AppStateStoreFeature] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.features = features or {}

    def get_or_create(self, app: Application, **kwargs) -> AppState:
        """
        Return a state for the provided app or create a new one.

        :param app: the related application
        :param **kwargs: init arguments when creating a new app.
        """
        state = self.get(app.id)
        if not state:
            state = app.create_state(**kwargs)
            self.commit({state.id: state})
        return state


class AppStateMemoryStore(AppStateStore, stores.MemoryStore):
    pass


class AppStateFileStore(AppStateStore, stores.FileStore):
    def load(self):
        model = super().load()
        self.features = model.features
        return model

    def get_save_data(self, **kwargs):
        return super().get_save_data(features=self.features)
