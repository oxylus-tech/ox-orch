from pydantic import Field

from ox_orch.core.apps import AppID
from ox_orch.core.app_registry import AppStateDiffs
from ox_orch.core.registry import register
from .base import OperationState, AbstractOperation
from .subprocess import SubprocessMixin


__all__ = ("InstallState", "InstallOperation", "PipInstall")


@register("install")
class InstallState(AppStateDiffs, OperationState):

    packages: dict[AppID, str] = Field(default_factory=dict)
    """ Mapping of app id to package names used for installation. """


class InstallOperation(SubprocessMixin, AbstractOperation):
    """Install packages using pip."""

    __state_class__ = InstallState
    __apply_spec__ = ("apps", "shell")
    __rollback_spec__ = ("apps", "shell")

    update: bool = True
    """ Update packages. """
    force_reinstall: bool = False
    """ Force reinstall. """

    def _apply(self, state, shell, apps, **context):
        if not apps:
            return

        state.backward = self._snapshot(apps)
        state.packages = {app.id: app.package for app in apps}

        options = self.get_install_options()

        self.log("Install:\n" + "\n".join(f"- {key}=={val}" for key, val in state.packages.items()))

        if context.get("dry_run"):
            state.forward = {app.id: {"installed_version": app.version} for app in apps}
        else:
            self.install(state, shell, {app.package: app.version for app in apps}, options=options)
            state.forward = self._snapshot(apps)

    def _rollback(self, state, shell, **context):
        downgrade = {
            state.packages[app_id]: vals["installed_version"]
            for app_id, vals in state.backward.items()
            if vals.get("installed_version") is not None
        }
        self.log("Downgrade to:\n" + "\n".join(f"- {key}=={val}" for key, val in downgrade.items()))

        if not context.get("dry_run") and downgrade:
            self.install(state, shell, downgrade)

        uninstall = [
            state.packages[app_id] for app_id, vals in state.backward.items() if vals.get("installed_version") is None
        ]
        self.log("Remove:\n" + "\n".join(f"- {key}" for key in uninstall))

        if not context.get("dry_run") and uninstall:
            self.uninstall(state, shell, uninstall)

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

    def install(self, state, shell, packages: dict[str, str], **kwargs):
        cmd = self.get_forward(state, packages, **kwargs)
        shell.run(cmd)

    def uninstall(self, state, shell, packages: list[str], **kwargs):
        """Uninstall packages.

        :param package: list of packages to uninstall.
        """
        cmd = self.get_backward(state, packages, **kwargs)
        shell.run(cmd)


@register("install:pip")
class PipInstall(InstallOperation):
    """Install python packages using Pip."""

    def get_forward(self, state, packages, options=None, **_):
        cmd = ["pip", "install", *(options or [])]
        return cmd + [f"{name}=={version}" if version else name for name, version in packages.items()]

    def get_backward(self, state, packages, **_):
        return ["pip", "uninstall", "-y", *packages]


@register("install:uv")
class UvInstall(InstallOperation):
    """Install python packages using UV."""

    def get_forward(self, state, packages, options=None, **_):
        cmd = ["uv", "pip", "install", *(options or [])]
        return cmd + [f"{n}=={v}" if v else n for n, v in packages.items()]

    def get_backward(self, state, packages, **_):
        return ["uv", "pip", "uninstall", *packages]


@register("install:poetry")
class PoetryInstall(InstallOperation):
    """Install python packages using Poetry."""

    def get_forward(self, state, packages, options=None, **_):
        cmd = ["poetry", "add", *(options or [])]
        return cmd + [f"{n}@{v}" if v else n for n, v in packages.items()]

    def get_backward(self, state, packages, **_):
        return ["poetry", "remove", *packages]
