from abc import abstractmethod
from typing import Iterable, Optional

from django.utils.translation import gettext as __
from pydantic import BaseModel, Field

from .apps import AppMetadata, resolve_install_order


__all__ = (
    "NotFoundError",
    "AppDict",
    "AppRegistry",
    "MemoryAppRegistry",
)


class NotFoundError(Exception):
    def __init__(self, apps: Iterable[AppMetadata], msg=None, **kwargs):
        if not msg:
            msg = __("The following apps could not be found: {apps}").format(apps=apps)
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
    def is_installed(self, id: str) -> bool:
        """Return True whether an app is installed."""
        pass

    @abstractmethod
    def get(self, id: str, exc: bool = False) -> AppMetadata | None:
        """Get app by id.

        :param id: application id
        :param exc: raise :py:class:`NotFoundError` if not found.
        """
        pass

    @abstractmethod
    def get_all(self, ids: list[str], exc: bool = False) -> list[AppMetadata]:
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

    # ---- implementated methods
    def get_full(self, ids: Iterable[str], _apps: Optional[dict[str, AppMetadata]] = None) -> list[AppMetadata]:
        """
        Get all applications metadata including their dependencies.

        :param ids: application ids
        :return: apps and dependencies ordered by install order.
        :yield NotFoundError: some application(s) haven't been found.
        """
        apps = _apps or {}
        if apps:
            ids = [n for n in ids if n not in apps]

        if ids:
            apps.update({app.id: app for app in self.get_all(ids)})

        missings = {n for n in ids if n not in apps}
        if missings:
            raise NotFoundError(missings)

        todo = {dep for app in apps.values() for dep in app.dependencies if dep not in apps}
        todo and self.get_full(todo, apps)
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

    def is_installed(self, id):
        if app := self.get(id):
            return app.installed_at is not None
        return False

    def get(self, id: str, exc: bool = False):
        if app := self.apps.get(id):
            return app
        elif exc:
            raise NotFoundError([id])

    def get_all(self, ids: list[str], exc: bool = False):
        apps, missings = [], []
        for id in ids:
            if app := self.get(id):
                apps.append(app)
            elif exc:
                missings.append(id)

        if missings:
            raise NotFoundError(missings)
        return apps

    def prefetch(self):
        pass

    def search(self, **lookups):
        items = []

        for app in self.apps.values():
            for key, search in lookups.items():
                attr = (getattr(app, key, "") or "").lower()
                if isinstance(search, str):
                    if search in attr:
                        items.append(app)
                        continue
                else:
                    if any(v in attr for v in search):
                        items.append(app)
                        continue
        return items
