"""
This module provide operations used to install python packages and setup virtual
environments.

We support three installation methods:

    - ``install:pip``: install packages using Pip
    - ``install:uv``: install packages using Uv
    - ``install:poetry``: install packages using Poetry

To create virtual environment, you can use the ``venv:create`` operation.
"""

from pathlib import Path
from typing import Iterable

from pydantic import Field

from ox_orch.core import ChangeSet, register
from .base import OperationState, Operation
from .shell import ShellMixin


__all__ = (
    "InstallState",
    "InstallOperation",
    "PipInstall",
    "UvInstall",
    "PoetryInstall",
    "CheckPackageInstalled",
    "CheckPackageInstalledState",
)


@register("install")
class InstallState(ChangeSet, OperationState):
    pass


class InstallOperation(ShellMixin, Operation):
    """Install packages using pip.

    There are two context values required, note however that ``apps`` is a
    simple list of Application classes.
    """

    __state_class__ = InstallState
    __apply_spec__ = (
        "exec_ctx",
        "apps",
    )
    __rollback_spec__ = ("exec_ctx",)

    update: bool = Field(default=True, description="Update packages")
    """ Update packages. """
    force_reinstall: bool = Field(default=False, description="Force package reinstallation.")
    """ Force reinstall. """

    def _apply(self, state, exec_ctx, apps, **inputs):
        if not apps:
            return

        state.backward = self._snapshot(apps)

        options = self.get_install_options()

        apps_req = self._snapshot(apps, True)
        self.log("Install:\n" + "\n".join(f"- {v['package']} @ {v['version']}" for v in state.backward.values()))

        if exec_ctx.run.dry_run:
            state.forward = apps_req
        else:
            self.install(state, exec_ctx.shell, apps_req.values(), options=options)
            state.forward = self._snapshot(apps)

    def _rollback(self, state, exec_ctx, **inputs):
        downgrade = [values for values in state.backward.values() if values.get("version") is not None]
        self.log("Downgrade to:\n" + "\n".join(f"- {vals['package']} @ {vals['version']}" for vals in downgrade))

        if not exec_ctx.run.dry_run and downgrade:
            self.install(state, exec_ctx.shell, downgrade)

        uninstall = [values["package"] for values in state.backward.values() if values.get("version") is None]
        self.log("Remove:\n" + "\n".join(f"- {key}" for key in uninstall))

        if not exec_ctx.run.dry_run and uninstall:
            self.uninstall(state, exec_ctx.shell, uninstall)

    def get_install_options(self):
        """Build CLI option for installation (forward only)."""
        options = []
        if self.update:
            options.append("--upgrade")
        if self.force_reinstall:
            options.append("--force-reinstall")
        return options

    def _snapshot(self, apps, dry_run=False):
        return {
            app.id: {
                "package": app.package,
                "source": app.source or app.package,
                "version": app.version if dry_run else app.get_installed_version(),
            }
            for app in apps
        }

    def install(self, state, shell, requirements: Iterable[dict[str, str]], **kwargs):
        requirements = [self.get_requirement(val["source"], val["version"]) for val in requirements]
        cmd = self.get_forward(state, shell, requirements, **kwargs)
        shell.run(cmd, check=True)

    def uninstall(self, state, shell, packages: list[str], **kwargs):
        """Uninstall packages.

        :param package: list of packages to uninstall.
        """
        cmd = self.get_backward(state, shell, packages, **kwargs)
        shell.run(cmd, check=True)

    @staticmethod
    def get_requirement(source, version):
        if not version or source.startswith(("git+", "file://")) or Path(source).exists():
            return source

        return f"{source}=={version}"


@register("install:pip")
class PipInstall(InstallOperation):
    """Install python packages using Pip."""

    _label = "Pip Install"
    _description = "Install packages using Pip."

    def get_forward(self, state, shell, requirements, options=None, **_):
        return [shell.python, "-m", "pip", "install", *(options or []), *requirements]

    def get_backward(self, state, shell, packages, **_):
        return [shell.python, "-m", "pip", "uninstall", "-y", *packages]


@register("install:uv")
class UvInstall(InstallOperation):
    """Install python packages using UV."""

    _label = "UV Install"
    _description = "Install packages using UV."

    def get_forward(self, state, shell, requirements, options=None, **_):
        return ["uv", "pip", "install", *(options or []), *requirements]

    def get_backward(self, state, shell, packages, **_):
        return ["uv", "pip", "uninstall", *packages]


@register("install:poetry")
class PoetryInstall(InstallOperation):
    """Install python packages using Poetry."""

    _label = "Poetry Install"
    _description = "Install packages using Poetry."

    def get_forward(self, state, shell, requirements, options=None, **_):
        return ["poetry", "run", "pip", "install", *(options or []), *requirements]

    def get_backward(self, state, shell, packages, **_):
        return ["poetry", "run", "pip", "uninstall", *packages]


# ---- Install checks
@register("install:check")
class CheckPackageInstalledState(OperationState):
    """ """

    installed: list[str]
    not_installed: list[str]


@register("install:check")
class CheckPackageInstalled(Operation):
    """
    Check if a package is installed inside the execution shell environment.

    Note that it won't raise any error, but will instead update the values of
    :py:class:`CheckPackageInstalledState`
    """

    _label = "Check Install"
    _description = "Check that provided applications' packages are installed."

    __apply_spec__ = ()
    __rollback_spec__ = ()

    packages: list[str]

    def _apply(self, state: CheckPackageInstalledState, exec_ctx, **_):
        """
        Uses the shell runtime (venv-aware) to check installation.
        """
        for package in self.packages:
            result = exec_ctx.shell.run(
                ["python", "-m", "pip", "show", package],
            )
            if result.returncode == 0:
                state.installed.append(package)
            else:
                state.not_installed.append(package)
