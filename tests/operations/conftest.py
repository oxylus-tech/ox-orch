import pytest

from ox_orch.operations import Plan

from ..conftest import Operation, apply, rollback, assert_states


__all__ = ("apply", "rollback", "assert_states")


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
