"""
This modules allows to fetch Applications from pypi repository.
"""

from __future__ import annotations

import asyncio
import logging

from packaging.requirements import Requirement
import httpx

from .app import Application, Dependency


__all__ = ("PyPIClient", "AppProvider")


logger = logging.getLogger("ox-orch")


class PyPIClient:
    """Async client for PyPI metadata."""

    BASE_URL = "https://pypi.org/pypi"

    def __init__(self, concurrency: int = 10):
        self._limits = httpx.Limits(max_connections=concurrency)
        self._client = httpx.AsyncClient(limits=self._limits, timeout=10.0)

    async def close(self):
        await self._client.aclose()

    async def fetch_metadata(self, package: str) -> dict:
        """
        Fetch raw PyPI metadata for a package.
        """
        url = f"{self.BASE_URL}/{package}/json"
        resp = await self._client.get(url)
        if resp.status_code == 200:
            return resp.json()
        return None

    async def fetch_many(self, packages: list[str]) -> dict[str, dict]:
        """
        Fetch multiple packages concurrently.
        """
        results = await asyncio.gather(*(self.fetch_metadata(pkg) for pkg in packages))
        return {pkg: data for pkg, data in zip(packages, results)}


class AppProvider:
    """
    Builds Application from a list of package names by requesting Pypi repository.

    Dependencies are recorded ONLY if they are also declared.
    """

    def __init__(self, client: PyPIClient | None = None):
        self.client = client or PyPIClient()

    def build(self, packages: list[str]) -> list[Application]:
        """Sync version of :py:meth:`abuild`."""
        return asyncio.run(self.abuild(packages))

    async def abuild(self, packages: list[str]) -> list[Application]:
        """
        Fetch python packages from repository and return a list of
        Applications.

        :param packages: user-provided package list
        """

        # 1. Fetch metadata concurrently
        metadata_map = await self.client.fetch_many(packages)

        # 2. Extract dependency info
        reqs: dict[str, list[str]] = {}
        apps = {}

        for pkg, meta in metadata_map.items():
            if meta is None:
                logger.error(f"No package found for `{pkg}`")
                continue

            deps = parse_requires_dist(meta)
            reqs[pkg] = deps

            info = meta["info"]
            app = Application(
                id=pkg,
                name=pkg,
                version=info.get("version"),
            )
            apps[pkg] = app

        # 4. Dependencies
        for app in apps.values():
            for req in reqs[app.package]:
                dep = apps.get(req.name)
                # package is an app and has matching version
                if dep and dep.version in req.specifier:
                    app.dependencies.append(Dependency(id=dep.id, version=dep.version))
        return list(apps.values())


def parse_requires_dist(metadata: dict) -> list[Requirement]:
    """Extract direct dependencies from PyPI metadata."""
    info = metadata.get("info", {})
    requires = info.get("requires_dist") or []

    deps = []
    for req in requires:
        deps.append(Requirement(req))
    return deps
