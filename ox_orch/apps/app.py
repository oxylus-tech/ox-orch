from __future__ import annotations
from importlib import metadata
from graphlib import TopologicalSorter
from packaging.version import Version
from typing import Iterable, TypeAlias

from pydantic import Field, BaseModel, field_validator, model_validator

from ox_orch.core import stores, Registry, PolymorphicModel
from ox_orch.utils import map_or_return


__all__ = (
    "AppId",
    "AppVersion",
    "AppRef",
    "APP_FEATURE_REGISTRY",
    "AppFeature",
    "Versioned",
    "Dependency",
    "AppRelease",
    "Application",
    "resolve_install_order",
)


AppId: TypeAlias = str
""" Application ID """
AppVersion: TypeAlias = str
""" Applicatino version. """
AppRef: TypeAlias = tuple[AppId, AppVersion | None]
""" Application reference. """


def as_app_ref(ref) -> AppRef:
    """Return AppRef from the provided app ref or id."""
    if isinstance(ref, str):
        return ref, None
    return ref


APP_FEATURE_REGISTRY = Registry()


class AppFeature(PolymorphicModel):
    """Base class for all optional features extension."""

    __registry__ = APP_FEATURE_REGISTRY

    pass


class Versioned(BaseModel):
    """Base class that provide an app id and a version."""

    id: str
    """ Name. """
    version: str | None = None
    """ Version. """

    @property
    def ref(self) -> AppRef:
        """Return version unique key."""
        return (self.id, self.version)

    def __hash__(self):
        return hash(self.ref)


class Dependency(Versioned):
    """Define a versioned dependency to another app."""

    _version: Version | None = None
    """ Packaging Version instance. """

    @classmethod
    def parse(cls, value: str) -> "Dependency":
        """
        Return a Dependency using provided requirement string.

        Only exact match specifier are allowed.
        """
        if "*" not in value and "^" not in value:
            if "@" in value:
                id, version = value.split("@", 1)
                return cls(id=id, version=version)
            if "==" in value:
                id, version = value.split("==", 1)
                return cls(id=id, version=version)
        raise ValueError(f"Version constraints not supported: {value}")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._version = Version(self.version)

    def to_string(self) -> str:
        """Return dependency as a string."""
        if self.version:
            return self.id + self.version
        return self.id

    def __eq__(self, item):
        return (self.id, self.version) == (item.id, item.version)

    def __lt__(self, item):
        return self.id < item.id or self._version < item._version

    def __hash__(self):
        return hash(self.ref)


class AppRelease(Versioned):
    """
    Release data for an application.
    """

    package: str
    """ Pypi package providing the app. """
    dependencies: list[Dependency] = Field(default_factory=list)
    """ Orchestration workflow dependencies.

    You can provide depencencies as string list like ``["ox_orch==1.0"]``.
    """
    requirements: list[str] = Field(default_factory=list)
    """
    Python package dependencies.

    It is only used as informative data, and does not impact pipeline execution.
    """
    source: str | None = None
    """
    Specifies the real installation source of the application release.
    If not provided, install defaults to package.

    Can be:

        - a local path
        - a git url
        - a wheel file

    Note that on uninstallation, :py:attr:`package` is used.
    """
    features: dict[str, AppFeature] = Field(default_factory=dict)
    """ Optional features extension data. """

    @field_validator("dependencies", mode="before")
    @classmethod
    def normalize_dependencies(cls, value):
        if isinstance(value, list):
            return map_or_return(
                value,
                lambda item: isinstance(item, str),
                lambda item: Dependency.parse(item),
            )
        return value

    def get_installed_version(self) -> str | None:
        """Return installed version read from environment metadata."""
        try:
            return metadata.version(self.package)
        except metadata.PackageNotFoundError:
            return None


class Application(AppRelease):
    """
    Standardized and generic application metadata.

    An Application is composed of multiple release information, which
    can be used to resolve dependencies and other informations for the
    same installation unit.

    It also contains extra information to be used by extensions, as for
    Django. Those are put in :py:attr:`features` (by extension name).


    Features
    --------

    Extensions can register additional data on application using the field
    :py:attr:`features`. This is a dictionary of pydantic models by feature
    name.

    The model shall be subclassing the polymorphic model :py:class:`AppFeature`
    that must be registered using the ``register`` decorator.

    .. code-block:: python

        from ox_orch.core import register
        from ox_orch.apps import AppFeature

        @register("django")
        class DjangoFeature(AppFeature):
            app_label: str
            migration_enabled = True


        # Then on the application:
        app = Application(name="app", package="app_pkg", version="0.0.1", features={
            "django": DjangoFeature(app_label="app.label")
        })

    The mechanism is similar on other classes as for:

        -:py:class:`~state.AppStateFeature` and :py:class:`~state.AppState`
        -:py:class:`~state.AppStateStoreFeature` and :py:class:`~state.AppStateStore`

    """

    name: str
    """ Human readable name of the application. """
    groups: list[str] = Field(default_factory=list)
    """ Assign Application to groups. """
    tags: list[str] = Field(default_factory=list)
    """ Assign Application to tags. """
    releases: dict[str, AppRelease] = Field(default_factory=dict)
    """ Application information for other releases. """

    @model_validator(mode="after")
    def validate_releases_consistency(self) -> "Application":
        """Ensures all releases belong to this app."""
        for version, release in self.releases.items():
            release._app = self
            if release.id != self.id:
                raise ValueError(f"Release `{version}` has id=`{release.id}` " f"but expected `{self.id}`")
            if release.version != version:
                raise ValueError(f"Release version `{release.version}` does not match its key `{version}`")
        return self

    def get_release(self, version: str | None = None, exc: bool = False) -> AppRelease | None:
        """Return release information for the provided version."""
        if version is None or version == self.version:
            return self

        release = self.releases.get(version)
        if release is None and exc:
            raise KeyError(f"No release found for {self.id}@{version}")
        return release

    def create_state(self, **kwargs):
        """
        Return new state for this application.

        :param kwargs: extra init arguments.
        :returns: AppState
        """
        from .state import AppState

        return AppState(id=self.id, version=self.version, package=self.package, **kwargs)


class AppStore(stores.Store):
    """
    This registry is used to get and resolve application metadata.
    """

    model_class = Application
    key = "id"

    def __init__(self, *args, apps: Iterable[Application] | None = None, **kwargs):
        super().__init__(*args, **kwargs)

        if apps:
            self.commit(apps)

    # ---- implementated methods
    def resolve(self, app_refs: Iterable[AppRef | AppId]) -> list[AppRelease]:
        """
        Get all applications metadata including their dependencies.

        :param ids: application ids
        :return: apps and dependencies ordered by install order.
        :yield NotFoundError: some application(s) haven't been found.
        """
        releases = {}
        versions = {}
        errors = []

        def visit(batch_refs: list[AppRef]):
            batch_refs = (as_app_ref(ref) for ref in batch_refs)
            to_fetch = {aref[0]: aref[1] for aref in batch_refs if aref not in releases}
            if not to_fetch:
                return

            fetched_releases = self.get_all(to_fetch.keys())
            next_batch: list[str] = []
            for app in fetched_releases:
                version = to_fetch[app.id]
                if v := versions.get(app.id):
                    errors.append(f"- Dependency version mismatch for `{app.id}`: `{v}` and `{version}` both required")
                    continue

                try:
                    release = app.get_release(version, True)
                    releases[(app.id, version)] = release
                    for dep in release.dependencies:
                        dep_ref = dep.ref
                        if dep_ref not in releases:
                            next_batch.append(dep_ref)
                except Exception as err:
                    import traceback

                    traceback.print_exc()
                    errors.append("- " + str(err))
            if next_batch:
                visit(next_batch)

        visit(app_refs)
        if errors:
            raise RuntimeError(f"Multiple errors occurred:\n{'\n'.join(errors)}")
        return resolve_install_order(releases.values())


class AppMemoryStore(AppStore, stores.MemoryStore):
    """
    App registry keeping the store in memory.

    This class is a pydantic model, allowing it to be deserialized from
    a source file.

    Applications are kept as a dict of ``app_id: list[Application]``. The list
    is sorted by version.
    """

    pass


class AppFileStore(AppMemoryStore, stores.FileStore):
    """
    Load and store the whole registry in a single file.

    You should call :py:meth:`from_yaml` or :py:meth:`from_json`.
    """

    pass


def resolve_install_order(releases: list[AppRelease]) -> list[AppRelease]:
    """
    Returns releases sorted according to required dependencies.
    """
    nodes = {release.id: release for release in releases}
    ts = TopologicalSorter()

    for release in releases:
        ts.add(release.id, *release.dependencies)

    ordered_ids = list(ts.static_order())
    ordered_releases = [nodes[release_id] for release_id in ordered_ids if release_id in nodes]
    return ordered_releases
