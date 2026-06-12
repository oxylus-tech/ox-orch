import subprocess
from typing import Any, Optional


from ox_orch.core.registry import register
from ox_orch.core.shell import Shell
from .base import AbstractOperation, OperationState


__all__ = ("SubprocessMixin", "SubprocessState", "SubprocessOperation")


class SubprocessMixin:
    """
    Provides safe subprocess execution primitives for operations.

    This class is responsible for:
    - executing forward commands
    - executing backward commands
    - capturing stdout/stderr if configured
    """

    _stdout: Optional[Any] = None
    _stderr: Optional[Any] = None

    def run(self, args: list[str]):
        """
        Execute a subprocess command.

        :param args: full command as list of strings
        """
        subprocess.run(
            args,
            check=True,
            stdout=self._stdout,
            stderr=self._stderr,
        )

    def get_forward(self, state, **context) -> list[str]:
        """
        Build forward command.

        Override in subclasses.
        """
        raise NotImplementedError

    def get_backward(self, state, **context) -> list[str]:
        """
        Build rollback command.

        Override in subclasses.
        """
        raise NotImplementedError

    def _apply(self, state, shell: Shell, **context):
        """Run forward command, as returned by :py:meth:`get_forward`."""
        cmd = self.get_forward(state, **context)
        if cmd:
            self.log("Run: {' '.join(cmd)}")

            if not context.get("dry_run"):
                shell.run(cmd)
        else:
            self.log("No command to apply")

        if isinstance(state, SubprocessState):
            state.forward_cmd = cmd

    def _rollback(self, state, shell: Shell, **context):
        """Run forward command, as returned by :py:meth:`get_backward`."""
        cmd = self.get_backward(state, **context)

        if spec := context.get("spec"):
            if spec.dry_run:
                self.log("Dry rollback: {' '.join(cmd)}")
                return

        if cmd:
            self.log("Run: {' '.join(cmd)}")
            if not context.get("dry_run"):
                shell.run(cmd)
        else:
            self.log("No command to apply")

        if isinstance(state, SubprocessState):
            state.backward_cmd = cmd


@register("subprocess")
class SubprocessState(OperationState):
    """
    State for subprocess operations.

    Stores executed commands for auditability.
    """

    forward_cmd: list[str] | None = None
    backward_cmd: list[str] | None = None


@register("subprocess")
class SubprocessOperation(SubprocessMixin, AbstractOperation):
    """
    Generic subprocess-based operation.

    All concrete operations only override:
    - get_forward()
    - get_backward()
    """

    _state_class = SubprocessState
    __apply_spec__ = "shell"
    __rollback_spec__ = "shell"
    __full_context__ = True

    forward: list[str] = []
    backward: list[str] = []

    # ---- command builders

    def get_forward(self, state, **context) -> list[str]:
        """
        Build forward command.

        Override in subclasses.
        """
        return self.forward

    def get_backward(self, state, **context) -> list[str]:
        """
        Build rollback command.

        Override in subclasses.
        """
        return self.backward
