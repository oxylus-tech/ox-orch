import subprocess
from importlib import metadata
from typing import Any, Optional

from pydantic import PrivateAttr, Field

from .base import OperationState, AbstractOperation


__all__ = ("InstallState", "InstallOperation", "PipInstall")


class InstallState(OperationState):
    __type_id__ = "state:op:install"

    before_versions: dict[str, str | None] = Field(default_factory=dict)
    after_versions: dict[str, str | None] = Field(default_factory=dict)

    freeze_done: bool = False
    install_done: bool = False
    post_freeze_done: bool = False


class InstallOperation(AbstractOperation):
    """Install packages using pip."""

    update: bool = True
    """ Invoke pip with `--update`. """

    def _apply(self, state, apps, **context):
        if not state.freeze_done:
            state.before_versions = self.freeze()
            state.freeze_done = True
            yield state

        if not state.install_done:
            self.install({app.package: app.version for app in self.apps})
            state.install_done = True
            yield state

        if not state.post_freeze_done:
            state.after_versions = self.freeze()
            state.post_freeze_done = True
            yield state

    def _rollback(self, state, **context):
        if state.install_done:
            packages = state.before_versions
            to_remove = [name for name, version in packages.items() if not version]
            self.uninstall(to_remove)

            to_restore = {name: version for name, version in packages.items() if version}
            self.install(to_restore)

    def install(self, packages: dict[str, str]):
        raise NotImplementedError

    def uninstall(self, packages: list[str]):
        """Uninstall packages.

        :param package: list of packages to uninstall.
        """
        raise NotImplementedError

    def freeze(self) -> dict[str, str | None]:
        """
        Capture installed versions before execution.
        """
        result = {}

        for app in self.apps:
            try:
                result[app.package] = metadata.version(app.package)
            except metadata.PackageNotFoundError:
                result[app.package] = None

        return result


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
