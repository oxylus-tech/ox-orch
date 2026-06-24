import pytest
from unittest.mock import MagicMock

from ox_orch.core.shell import EchoShell
from ox_orch.operations.shell import (
    ShellOperation,
    ShellState,
    ShellMixin,
)


class DummyOp(ShellOperation):
    """
    Minimal concrete implementation for testing ShellOperation.
    """

    def __init__(self):
        super().__init__()
        self.forward = ["echo", "forward"]
        self.backward = ["echo", "backward"]


@pytest.fixture
def mock_run(monkeypatch):
    mock_run = MagicMock()
    # monkeypatch.setattr("ox_orch.core.shell.run", mock_run)
    return mock_run


class TestShellMixin:
    """
    Unit tests for ShellMixin behavior.
    """

    class FakeOp(ShellMixin):
        def __init__(self):
            self.run_calls = []

        def run(self, args):
            self.run_calls.append(args)

    def test_apply_sets_forward_command(self, exec_ctx, mock_run):
        op = DummyOp()
        state = ShellState()

        op._apply(state, exec_ctx, shell=EchoShell())
        # mock_run.assert_called_once_with(["echo", "forward"], check=True, stdout=None, stderr=None)
        assert state.forward_cmd == ["echo", "forward"]

    def test_rollback_sets_backward_command(self, exec_ctx, mock_run):
        op = DummyOp()
        state = ShellState()

        op._rollback(state, exec_ctx, shell=EchoShell())
        # mock_run.assert_called_once_with(["echo", "backward"], check=True, stdout=None, stderr=None)
        assert state.backward_cmd == ["echo", "backward"]


class TestShellOperation:
    """
    Tests default behavior of ShellOperation.
    """

    def test_default_forward_command(self):
        op = DummyOp()
        state = ShellState()

        assert op.get_forward(state) == ["echo", "forward"]

    def test_default_backward_command(self):
        op = DummyOp()
        state = ShellState()

        assert op.get_backward(state) == ["echo", "backward"]


class TestShellState:
    """
    Tests state container behavior.
    """

    def test_state_initialization(self):
        state = ShellState()

        assert state.forward_cmd is None
        assert state.backward_cmd is None
