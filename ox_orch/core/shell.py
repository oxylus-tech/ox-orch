from __future__ import annotations
from abc import ABC, abstractmethod
import os
from pathlib import Path
import subprocess
from typing import Optional, Dict, Sequence


from pydantic import BaseModel


__all__ = ("ShellSpec", "Shell", "EchoShell", "LocalShell", "SHELL_REGISTRY")


class ShellSpec(BaseModel):
    """
    Serializable description of how subprocess execution must behave.
    """

    backend: str = "local"
    """
    Sandbox backend identifier:
    - subprocess
    - docker (future)
    - ssh (future)
    """

    venv_path: Optional[str] = None
    cwd: Optional[str] = None

    env: Dict[str, str] = {}
    timeout: Optional[int] = None


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
    def run(self, command: Sequence[str]):
        """Execute a command in the sandbox."""
        raise NotImplementedError


class EchoShell(Shell):
    """Simple sandbox that only print the command."""

    def __init__(self, spec=None):
        super().__init__(spec)

    def run(self, command):
        print(command)


class LocalShell(Shell):
    """Implement subprocess execution for a sandbox."""

    def run(self, command):
        config = self.spec
        env = os.environ.copy()
        env.update(config.env)

        if config.venv_path:
            bin_path = Path(config.venv_path) / "bin"
            env["PATH"] = str(bin_path) + ":" + env["PATH"]

        return subprocess.run(
            list(command),
            cwd=config.cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=config.timeout,
            check=True,
        )


SHELL_REGISTRY = {
    "local": LocalShell,
}
