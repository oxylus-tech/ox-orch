from __future__ import annotations
from graphlib import TopologicalSorter
from typing import Iterable

from pydantic import Field

from ox_orch.core import stores, register, FileBackend, JSONBackend, Registry, RegisteredClass
from .app import Application, AppRef, AppId, AppRelease, as_app_ref


__all__ = (
    "resolve_install_order",
    "APP_STORE_REGISTRY",
    "AppStoreModel",
    "AppStore",
    "AppMemoryStore",
    "AppFileStore",
)


APP_STORE_REGISTRY = Registry()


class AppStore(stores.Store, RegisteredClass):
    """
    This registry is used to get and resolve application metadata.
    """

    __registry__ = APP_STORE_REGISTRY

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


class AppStoreModel(stores.FileStoreModel):
    """Store model for saving to files."""

    data: dict[str, Application] = Field(default_factory=dict)


@register("memory")
class AppMemoryStore(AppStore, stores.MemoryStore):
    """
    App registry keeping the store in memory.

    This class is a pydantic model, allowing it to be deserialized from
    a source file.

    Applications are kept as a dict of ``app_id: list[Application]``. The list
    is sorted by version.
    """

    pass


@register("file")
class AppFileStore(AppMemoryStore, stores.FileStore):
    """
    Load and store the whole registry in a single file.

    You should call :py:meth:`from_yaml` or :py:meth:`from_json`.
    """

    backend: FileBackend = JSONBackend(AppStoreModel)


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
