import pytest
from unittest.mock import MagicMock

from ox_orch.core.shell import EchoShell
from ox_orch.operations.subprocess import (
    SubprocessOperation,
    SubprocessState,
    SubprocessMixin,
)


class DummyOp(SubprocessOperation):
    """
    Minimal concrete implementation for testing SubprocessOperation.
    """

    def __init__(self):
        super().__init__()
        self.forward = ["echo", "forward"]
        self.backward = ["echo", "backward"]


@pytest.fixture
def mock_run(monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_run)
    return mock_run


class TestSubprocessMixin:
    """
    Unit tests for SubprocessMixin behavior.
    """

    class FakeOp(SubprocessMixin):
        def __init__(self):
            self.run_calls = []

        def run(self, args):
            self.run_calls.append(args)

    def test_apply_sets_forward_command(self, exec_ctx, mock_run):
        op = DummyOp()
        state = SubprocessState()

        op._apply(state, exec_ctx, shell=EchoShell())
        # mock_run.assert_called_once_with(["echo", "forward"], check=True, stdout=None, stderr=None)
        assert state.forward_cmd == ["echo", "forward"]

    def test_rollback_sets_backward_command(self, exec_ctx, mock_run):
        op = DummyOp()
        state = SubprocessState()

        op._rollback(state, exec_ctx, shell=EchoShell())
        # mock_run.assert_called_once_with(["echo", "backward"], check=True, stdout=None, stderr=None)
        assert state.backward_cmd == ["echo", "backward"]


class TestSubprocessOperation:
    """
    Tests default behavior of SubprocessOperation.
    """

    def test_default_forward_command(self):
        op = DummyOp()
        state = SubprocessState()

        assert op.get_forward(state) == ["echo", "forward"]

    def test_default_backward_command(self):
        op = DummyOp()
        state = SubprocessState()

        assert op.get_backward(state) == ["echo", "backward"]


class TestSubprocessState:
    """
    Tests state container behavior.
    """

    def test_state_initialization(self):
        state = SubprocessState()

        assert state.forward_cmd is None
        assert state.backward_cmd is None
