from pydantic import Field

from ..core.apps import AppID
from ..core.registry import AppStateDiffs
from .base import OperationState, AbstractOperation
from .subprocess import SubprocessMixin


__all__ = ("InstallState", "InstallOperation", "PipInstall")


class InstallState(AppStateDiffs, OperationState):
    __type_id__ = "state:op:install"

    packages: dict[AppID, str] = Field(default_factory=dict)
    """ Mapping of app id to package names used for installation. """


class InstallOperation(SubprocessMixin, AbstractOperation):
    """Install packages using pip."""

    __state_class__ = InstallState
    __apply_spec__ = ("apps",)
    __rollback_spec__ = ("apps",)

    update: bool = True
    """ Update packages. """
    force_reinstall: bool = False
    """ Force reinstall. """

    def _apply(self, state, apps, **context):
        if not apps:
            return

        state.backward = self._snapshot(apps)
        state.packages = {app.id: app.package for app in apps}

        options = self.get_install_options()
        self.install(state, {app.package: app.version for app in apps}, options=options)

        state.forward = self._snapshot(apps)

    def _rollback(self, state, **context):
        downgrade = {
            state.packages[app_id]: vals["installed_version"]
            for app_id, vals in state.backward.items()
            if vals.get("installed_version") is not None
        }
        if downgrade:
            self.install(state, downgrade)

        uninstall = [
            state.packages[app_id] for app_id, vals in state.backward.items() if vals.get("installed_version") is None
        ]
        self.uninstall(state, uninstall)

    def get_install_options(self):
        """Build CLI option for installation (forward only)."""
        options = []
        if self.update:
            options.append("--upgrade")
        if self.force_reinstall:
            options.append("--force-reinstall")
        return options

    def _snapshot(self, apps):
        return {app.id: {"installed_version": app.get_installed_version()} for app in apps}

    def install(self, state, packages: dict[str, str], **kwargs):
        cmd = self.get_forward(state, packages, **kwargs)
        self.run(cmd)

    def uninstall(self, state, packages: list[str], **kwargs):
        """Uninstall packages.

        :param package: list of packages to uninstall.
        """
        cmd = self.get_backward(state, packages, **kwargs)
        self.run(cmd)


class PipInstall(InstallOperation):
    """Install python packages using Pip."""

    __type_id__ = "op:install:pip"

    def get_forward(self, state, packages, options=None, **_):
        cmd = ["pip", "install", *(options or [])]
        return cmd + [f"{name}=={version}" if version else name for name, version in packages.items()]

    def get_backward(self, state, packages, **_):
        return ["pip", "uninstall", "-y", *packages]


class UvInstall(InstallOperation):
    """Install python packages using UV."""

    __type_id__ = "op:install:uv"

    def get_forward(self, state, packages, options=None, **_):
        cmd = ["uv", "pip", "install", *(options or [])]
        return cmd + [f"{n}=={v}" if v else n for n, v in packages.items()]

    def get_backward(self, state, packages, **_):
        return ["uv", "pip", "uninstall", *packages]


class PoetryInstall(InstallOperation):
    """Install python packages using Poetry."""

    __type_id__ = "op:poetry_install"

    def get_forward(self, state, packages, options=None, **_):
        cmd = ["poetry", "add", *(options or [])]
        return cmd + [f"{n}@{v}" if v else n for n, v in packages.items()]

    def get_backward(self, state, packages, **_):
        return ["poetry", "remove", *packages]
