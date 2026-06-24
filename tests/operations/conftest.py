from typing import Optional

import pytest

from ox_orch.core import state
from ox_orch.operations import Plan, ExecutionContext

from ..conftest import Operation


def apply(op, state, **kwargs):
    """Apply operations and return a tuple of states and exception (if any)."""
    states, exc = [], None
    try:
        for s in op.apply(state, ExecutionContext(), **kwargs):
            states.append(s.model_copy(deep=True))
    except Exception as e:
        exc = e
    return states, exc


def rollback(op, state, **kwargs):
    """Rollback operations and return a tuple of states and exception (if any)."""
    states, exc = [], None
    try:
        for s in op.rollback(state, ExecutionContext(), **kwargs):
            states.append(s.model_copy(deep=True))
    except Exception as e:
        exc = e
    return states, exc


def assert_states(states, expected: list[tuple[str, state.Status, Optional[str | Exception]]]):
    """
    Assert states values from the provided list of expected results.

    Expected values are: ``operation_id``, ``status``, ``error`` (optional).
    """
    assert len(states) == len(expected)

    for op_state, (operation_id, status, *err) in zip(states, expected):
        assert op_state.operation_id == operation_id
        assert op_state.status == status
        if err:
            assert op_state.error == str(err[0])


@pytest.fixture
def op_1():
    return Operation(operation_id="op_1")


@pytest.fixture
def op_2():
    return Operation(operation_id="op_2")


@pytest.fixture
def op_3():
    return Operation(operation_id="op_3")


@pytest.fixture
def plan(op, op_1):
    return Plan(operation_id="plan", operations=[op, op_1])
