"""
This module provide operations used to install python packages and setup virtual
environments.

We support three installation methods:

    - ``install:pip``: install packages using Pip
    - ``install:uv``: install packages using Uv
    - ``install:poetry``: install packages using Poetry

To create virtual environment, you can use the ``venv:create`` operation.
"""

import os
from pathlib import Path
import shutil
from uuid import uuid4

from pydantic import BaseModel, Field

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
    """Install packages using pip.

    There are two context values required
    """

    __state_class__ = InstallState
    __apply_spec__ = ("apps",)
    __rollback_spec__ = ("apps",)

    update: bool = True
    """ Update packages. """
    force_reinstall: bool = False
    """ Force reinstall. """

    def _apply(self, state, ctx, apps, **inputs):
        if not apps:
            return

        state.backward = self._snapshot(apps)
        state.packages = {app.id: app.package for app in apps}

        options = self.get_install_options()

        self.log("Install:\n" + "\n".join(f"- {key}=={val}" for key, val in state.packages.items()))

        if ctx.run.dry_run:
            state.forward = {app.id: {"installed_version": app.version} for app in apps}
        else:
            self.install(state, ctx.shell, {app.package: app.version for app in apps}, options=options)
            state.forward = self._snapshot(apps)

    def _rollback(self, state, ctx, **inputs):
        downgrade = {
            state.packages[app_id]: vals["installed_version"]
            for app_id, vals in state.backward.items()
            if vals.get("installed_version") is not None
        }
        self.log("Downgrade to:\n" + "\n".join(f"- {key}=={val}" for key, val in downgrade.items()))

        if not ctx.run.dry_run and downgrade:
            self.install(state, ctx.shell, downgrade)

        uninstall = [
            state.packages[app_id] for app_id, vals in state.backward.items() if vals.get("installed_version") is None
        ]
        self.log("Remove:\n" + "\n".join(f"- {key}" for key in uninstall))

        if not ctx.run.dry_run and uninstall:
            self.uninstall(state, ctx.shell, uninstall)

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


# ---- Virtual Env


class VirtualEnvSpec(BaseModel):
    """Virtual environment configuration.

    You MUST provide :py:attr:`base_path` and SHALL provide a :py:attr:`python`
    executable. The default value for the latest will use PYTHON_EXECUTABLE
    environment variable if provided, otherwise it will try to find the
    plateform executable one.
    """

    @staticmethod
    def default_name():
        return "venv-" + str(uuid4())

    @staticmethod
    def default_python():
        if env := os.environ.get("PYTHON_EXECUTABLE"):
            return env

        if os.name == "nt":
            candidates = ["python", "py", "python.exe"]
        else:
            candidates = ["python3", "python"]

        for cmd in candidates:
            if path := shutil.which(cmd):
                return path

        raise RuntimeError(
            "No Python interpreter found. Please set PYTHON_EXECUTABLE or provide explicit python path "
            "on VirtualEnvSpec"
        )

    base_path: Path
    """ Base directory path in which the environment will be created. """
    name: str | None = Field(default_factory=default_name)
    """ Name of the environment """
    python: str | None = Field(default_factory=default_python)
    """ Python executable. """

    def get_path(self) -> Path:
        """
        The path where the environment is installed.

        It actually is ``base_path/name``.
        """
        return (self.base_path / self.name).resolve()


@register("venv:create")
class CreateVirtualEnvState(OperationState):
    """State for the create virtual env."""

    spec: VirtualEnvSpec | None = None


@register("venv:create")
class CreateVirtualEnv(AbstractOperation):
    """
    Create a virtual environment using the provided "venv" spec.
    """

    __apply_spec__ = ("venv",)

    def _apply(self, state, ctx, venv, **_):
        """Create virtual environment."""

        import virtualenv

        target_path = venv.get_path()
        if state.spec.path == target_path and target_path.exists():
            return state

        builder = virtualenv.EnvBuilder(
            python=venv.python,
            clear=False,
            with_pip=True,
        )
        builder.create(str(target_path))
        state.spec = venv.model_copy()

    def _rollback(self, state, ctx, **_):
        """Remove virtual environment."""

        if not state.spec:
            return

        target_path = state.spec.get_path()
        if target_path.exists():
            shutil.rmtree(target_path)
