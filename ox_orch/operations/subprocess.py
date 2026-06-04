import subprocess
from typing import Any, Optional


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

    def _apply(self, state, **context):
        """Run forward command, as returned by :py:meth:`get_forward`."""
        cmd = self.get_forward(state, **context)

        if cmd:
            self.run(cmd)

        if isinstance(state, SubprocessState):
            state.forward_cmd = cmd

    def _rollback(self, state, **context):
        """Run forward command, as returned by :py:meth:`get_backward`."""
        cmd = self.get_backward(state, **context)

        if cmd:
            self.run(cmd)

        if isinstance(state, SubprocessState):
            state.backward_cmd = cmd


class SubprocessState(OperationState):
    """
    State for subprocess operations.

    Stores executed commands for auditability.
    """

    __type_id__ = "state:op:subprocess"

    forward_cmd: list[str] | None = None
    backward_cmd: list[str] | None = None


class SubprocessOperation(SubprocessMixin, AbstractOperation):
    """
    Generic subprocess-based operation.

    All concrete operations only override:
    - get_forward()
    - get_backward()
    """

    __type_id__ = "op:subprocess"
    _state_class = SubprocessState

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
