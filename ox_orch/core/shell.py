from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import subprocess
import sys
from typing import Dict, Sequence


from pydantic import BaseModel, Field


__all__ = ("ShellSpec", "Shell", "EchoShell", "LocalShell", "SHELL_REGISTRY")


class ShellExecutionError(Exception):
    """
    Raised when a shell command fails.

    Carries full execution context (stdout, stderr, return code).
    """

    def __init__(self, result: ShellResult):
        self.result = result
        super().__init__(f"Command failed (code={result.returncode})")


class ShellSpec(BaseModel):
    """
    Serializable description of how subprocess execution must behave.
    """

    @staticmethod
    def default_python():
        if env := os.environ.get("PYTHON_EXECUTABLE"):
            return env

        return sys.executable

    backend: str = "local"
    """
    Sandbox backend identifier:
    - subprocess
    - docker (future)
    - ssh (future)
    """

    python: str = Field(default_factory=default_python)
    """ Python executable path. """
    cwd: str | None = None
    """ Current working directory. """
    env: Dict[str, str] = Field(default_factory=dict)
    """ Environment variables. """
    timeout: int | None = None
    """ Execution timeout. """


@dataclass
class ShellResult:
    returncode: int
    stdout: str | None = None
    stderr: str | None = None

    def check(self):
        """
        Raise an error when command returned failure code.

        :raises ShellExecutionError: command returned non-0 exit code.
        """
        if self.returncode:
            raise ShellExecutionError(self)


class Shell(ABC):
    """
    This base class allows subprocess execution in a sandboxed environment.
    """

    def __init__(self, spec: ShellSpec):
        self.spec = spec

    @staticmethod
    def from_spec(spec: ShellSpec | None = None) -> Shell:
        """
        Return a Shell instance based on the provided spec.

        It looks up for a relevant backend provided by SHELL_REGISTRY.
        When no spec is provided, it'll return a default one.
        """
        if spec is None:
            return LocalShell(ShellSpec())

        backend = SHELL_REGISTRY.get(spec.backend)
        if backend is None:
            raise ValueError(f"Unknown shell backend for {spec.backend}")
        return backend(spec)

    @abstractmethod
    def run(self, command: Sequence[str], check=False):
        """Execute a command in the sandbox."""
        raise NotImplementedError

    def run_python(self, command: Sequence[str], **kw):
        """Run python shell with provided arguments."""
        return self.run(self.python_cmd(*command), **kw)

    def run_python_module(self, command: Sequence[str], **kw):
        """Run python module with provided arguments."""
        return self.run(self.python_module(*command), **kw)

    @property
    def python(self) -> str:
        """Python executable path based on spec."""
        return str(self.spec.python)

    def python_cmd(self, *args) -> list[str]:
        """Return python command arguments.

        Shortcut to ``self.python, *args``.
        """
        return [self.python, *args]

    def python_module(self, module: str, *args) -> list[str]:
        """Return python module arguments.

        Shortcut to ``self.python, '-m', module, *args``.
        """
        return [self.python, "-m", module, *args]


class EchoShell(Shell):
    """Simple sandbox that only print the command."""

    def __init__(self, spec=None):
        super().__init__(spec)

    def run(self, command):
        print(command)
        return ShellResult(returncode=0, stdout=str(command))


class LocalShell(Shell):
    """Implement subprocess execution for a sandbox."""

    def run(self, command, check=False):
        config = self.spec
        env = os.environ.copy()
        env.update(config.env)

        # if config.venv_path:
        #    bin_path = Path(config.venv_path) / "bin"
        #    env["PATH"] = str(bin_path) + ":" + env["PATH"]

        print(f">>> \033[32m{command}\033[0m")
        result = subprocess.run(
            list(command),
            cwd=config.cwd,
            env=env,
            # capture_output=True,
            text=True,
            timeout=config.timeout,
            check=False,
        )
        shell_result = ShellResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        check and shell_result.check()
        return shell_result


SHELL_REGISTRY = {
    "echo": EchoShell,
    "local": LocalShell,
}
