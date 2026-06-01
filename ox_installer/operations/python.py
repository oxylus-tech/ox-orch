import subprocess
from typing import Any, Optional

from pydantic import PrivateAttr, Field

from ..core.apps import AppID
from ..core.registry import AppStateDiffs
from .base import OperationState, AbstractOperation


__all__ = ("InstallState", "InstallOperation", "PipInstall")


class InstallState(AppStateDiffs, OperationState):
    __type_id__ = "state:op:install"

    packages: dict[AppID, str] = Field(default_factory=dict)
    """ Mapping of app id to package names used for installation. """


class InstallOperation(AbstractOperation):
    """Install packages using pip."""

    _state_class = InstallState

    update: bool = True
    """ Invoke pip with `--update`. """

    def _apply(self, state, apps, **context):
        state.backward = self._get_versions_diff(apps)
        state.packages = {app.id: app.package for app in apps}

        self.install({app.package: app.version for app in apps})

        state.forward = self._get_versions_diff(apps)

    def _rollback(self, state, **context):
        to_restore = {
            state.packages[app_id]: vals["installed_version"]
            for app_id, vals in state.backward.items()
            if vals.get("installed_version") is not None
        }
        self.install(to_restore)

        to_remove = [
            state.packages[app_id] for app_id, vals in state.backward.items() if vals.get("installed_version") is None
        ]
        self.uninstall(to_remove)

    def _get_versions_diff(self, apps):
        return {app.id: {"installed_version": app.get_installed_version()} for app in apps}

    def install(self, packages: dict[str, str]):
        raise NotImplementedError

    def uninstall(self, packages: list[str]):
        """Uninstall packages.

        :param package: list of packages to uninstall.
        """
        raise NotImplementedError


class PipInstall(InstallOperation):
    """Install python packages using Pip."""

    __type_id__ = "op:pip_install"
    _stdout: Optional[Any] = PrivateAttr()
    _stderr: Optional[Any] = PrivateAttr()

    def install(self, packages):
        if packages:
            requirements = [f"{name}=={version}" if version else name for name, version in packages.items()]
            subprocess.run(
                ["pip", "install"] + requirements,
                check=True,
                stdout=self._stdout,
                stderr=self._stderr,
            )

    def uninstall(self, packages):
        if packages:
            subprocess.run(["pip", "uninstall"] + packages, check=True, stdout=self._stdout, stderr=self._stderr)
