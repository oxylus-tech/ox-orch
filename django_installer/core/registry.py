from __future__ import annotations
from abc import abstractmethod
from pathlib import Path
from typing import Iterable, Type

from django.utils.translation import gettext as __
from pydantic import BaseModel, Field, PrivateAttr

from . import files
from .apps import AppID, AppMetadata, resolve_install_order


__all__ = (
    "NotFoundError",
    "AppDict",
    "AppRegistry",
    "MemoryAppRegistry",
    "FileAppRegistry",
)


class NotFoundError(Exception):
    def __init__(self, apps: Iterable[AppMetadata], msg=None, **kwargs):
        if not msg:
            msg = __("The following apps could not be found: {apps}").format(apps=apps)
        self.apps = apps
        super().__init__(msg, **kwargs)


AppDict = dict[str, AppMetadata]
""" AppMetadata as a dict of ``app_id: AppMetadata``. """


class AppRegistry:
    """
    This is the base class that is used to get applications metadata.
    """

    name: str = ""
    """ Human readable name of the store """
    source: str = ""
    """ Storage source URL/information """

    @abstractmethod
    def get(self, app_id: AppID, exc: bool = False) -> AppMetadata | None:
        """Get app by id.

        :param id: application id
        :param exc: raise :py:class:`NotFoundError` if not found.
        """
        pass

    @abstractmethod
    def get_all(self, app_ids: list[AppID], exc: bool = False) -> list[AppMetadata]:
        """Get all apps corresponding to those ids.

        :param ids: application ids
        :param exc: raise :py:class:`NotFoundError` if not found.
        """
        pass

    @abstractmethod
    def search(self, **lookups: str | list[str]) -> list[AppMetadata]:
        """
        Search in the registry using the provided lookups.

        Lookups are AppMetadata attribute ids + value(s).

        When multiple values are provided, it looks for those matching at
        least one of them. When multiple lookups are provided, it looks
        for those matching both lookups.

        Registry should provided support for at least: ``id`` (contains),
        ``tags`` and ``groups``.
        """
        pass

    @abstractmethod
    def save_state(self, app: AppMetadata):
        """Persist app's state to store."""
        pass

    # ---- implementated methods
    def get_full(self, app_ids: Iterable[AppID]) -> list[AppMetadata]:
        """
        Get all applications metadata including their dependencies.

        :param ids: application ids
        :return: apps and dependencies ordered by install order.
        :yield NotFoundError: some application(s) haven't been found.
        """
        apps: dict[str, "AppMetadata"] = {}

        def visit(batch_ids: list[str]):
            to_fetch = [aid for aid in batch_ids if aid not in apps]
            if not to_fetch:
                return

            fetched_apps = self.get_all(to_fetch)
            next_batch: list[str] = []

            for app in fetched_apps:
                apps[app.id] = app
                for dep_id in app.dependencies:
                    if dep_id not in apps:
                        next_batch.append(dep_id)

            if next_batch:
                visit(next_batch)

        visit(app_ids)
        return resolve_install_order(apps.values())


class MemoryAppRegistry(AppRegistry, BaseModel):
    """
    App registry keeping the store in memory.

    This class is a pydantic model, allowing it to be deserialized from
    a source file.

    Applications are kept as a dict of ``app_id: AppMetadata``.
    """

    apps: AppDict = Field(default_factory=dict)
    """ The registered applications. """

    def __init__(self, apps: Iterable[AppMetadata] | AppDict | None = None, **kwargs):
        if not isinstance(apps, (type(None), dict)):
            apps = {a.id: a for a in apps}
        super().__init__(apps=apps, **kwargs)

    def get(self, app_id: AppID, exc: bool = False):
        if app := self.apps.get(app_id):
            return app
        elif exc:
            raise NotFoundError([app_id])

    def get_all(self, app_ids: list[AppID], exc: bool = False):
        apps, missings = [], []
        for app_id in app_ids:
            if app := self.get(app_id):
                apps.append(app)
            elif exc:
                missings.append(app_id)

        if missings:
            raise NotFoundError(missings)
        return apps

    def save_state(self, app):
        pass

    def search(self, **lookups):
        items = {}

        for app in self.apps.values():
            if app.id in items:
                continue

            for key, search in lookups.items():
                attr = getattr(app, key, "") or ""
                if isinstance(search, str):
                    if search in attr:
                        items[app.id] = app
                        continue
                else:
                    if any(v in attr for v in search):
                        items[app.id] = app
                        continue
        return list(items.values())


class FileAppRegistry(MemoryAppRegistry):
    """
    Load and store the whole registry in a single file.

    You should call :py:meth:`from_yaml` or :py:meth:`from_json`.
    """

    _path: Path = PrivateAttr()
    _backend: files.FileBackend = PrivateAttr()

    def __init__(self, _path: Path, _backend: files.FileBackend, **data):
        super().__init__(**data)
        self._path = _path
        self._backend = _backend

    @classmethod
    def from_yaml(cls, path: Path, **kwargs) -> FileAppRegistry:
        """
        Use :py:class:`.files.YAMLBackend` and try to load registry if it exists.

        :param path: path of the file
        :param **kwargs: extra fields values
        """
        return cls.from_backend(path, files.YAMLBackend, **kwargs)

    @classmethod
    def from_json(cls, path: Path, **kwargs) -> FileAppRegistry:
        """
        Use :py:class:`.files.JSONBackend` and try to load registry if it exists.

        :param path: path of the file
        :param **kwargs: extra fields values
        """
        return cls.from_backend(path, files.JSONBackend, **kwargs)

    @classmethod
    def from_backend(
        cls, path: Path, backend_class: Type[files.FileBackend], load: bool = True, **kwargs
    ) -> FileAppRegistry:
        """
        Return FileAppRegistry for the provided path and backend class.

        If the file exists on filesystem, it will be loaded before the new
        instance is returned.

        :param path: path of the file
        :param backend_class: file backend class to use
        :param load: whether to load file before init (default) or not.
        :param **kwargs: extra fields values
        """

        backend = backend_class(cls)
        kwargs["_path"] = path
        kwargs["_backend"] = backend
        if path.exists():
            return backend.load(path, **kwargs)
        return cls(**kwargs)

    def save(self):
        """Save registry to file."""
        self._backend.save(self._path, self)

    def save_state(self, app):
        """Save state (the whole registry actually) to file."""
        self.apps[app.id] = app  # ensure we have the updated app
        self.save()
