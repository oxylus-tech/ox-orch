from typing import ClassVar

from pydantic import Field

from ox_orch.core.registry import register
from ox_orch.core.shell import Shell
from .base import Operation, OperationState


__all__ = ("ShellMixin", "ShellState", "ShellOperation")


@register("shell")
class ShellState(OperationState):
    """
    State for subprocess operations.

    Stores executed commands for auditability.
    """

    forward_cmd: list[str] | None = Field(default=None, description="Applied command")
    backward_cmd: list[str] | None = Field(default=None, description="Rollback command")


class ShellMixin:
    """
    Provides safe subprocess execution primitives for operations.

    This class is responsible for:
    - executing forward commands
    - executing backward commands
    - capturing stdout/stderr if configured
    """

    __state_class__ = ShellState

    _shell: ClassVar[Shell | None] = None
    """ Overrides shell provided by execution context. """
    # _stdout: Optional[Any] = None
    # _stderr: Optional[Any] = None

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

    def _apply(self, state, exec_ctx, **context):
        """Run forward command, as returned by :py:meth:`get_forward`."""
        cmd = self.get_forward(state, **context)
        if cmd:
            self.log("Run: {' '.join(cmd)}")

            if not exec_ctx.run.dry_run:
                shell = self._shell or exec_ctx.shell
                shell.run(cmd)
        else:
            self.log("No command to apply")

        if isinstance(state, ShellState):
            state.forward_cmd = cmd

    def _rollback(self, state, exec_ctx, **context):
        """Run forward command, as returned by :py:meth:`get_backward`."""
        cmd = self.get_backward(state, **context)

        if cmd:
            self.log("Run: {' '.join(cmd)}")
            if not exec_ctx.run.dry_run:
                shell = self._shell or exec_ctx.shell
                shell.run(cmd)
        else:
            self.log("No command to apply")

        if isinstance(state, ShellState):
            state.backward_cmd = cmd


@register("shell")
class ShellOperation(ShellMixin, Operation):
    """
    Generic subprocess-based operation.

    All concrete operations only override:
    - get_forward()
    - get_backward()
    """

    _label = "Shell"
    _description = "Run commands for the provided shell."

    forward: list[str] | None = Field(default=None, description="Forward command, to run on apply.")
    backward: list[str] | None = Field(default=None, description="Backward command, to run on rollback")

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
