from typing import Optional

import pytest

from django_installer.core import files, state
from django_installer.core.operations import AbstractOperation, Plan, AppsPlan, register_operation


@register_operation
class Operation(AbstractOperation):
    applied: bool = False
    rollbacked: bool = False
    name = "operation"

    def _apply(self, exc=None, **kw):
        if exc:
            raise exc
        self.applied = True

    def _rollback(self, rexc=None, **kw):
        if rexc:
            raise rexc
        self.rollbacked = True


def apply(op, state, **kwargs):
    """Apply operations and return a tuple of states and exception (if any)."""
    states, exc = [], None
    try:
        for s in op.apply(state, **kwargs):
            states.append(s.clone())
    except Exception as e:
        exc = e
    return states, exc


def rollback(op, state, **kwargs):
    """Rollback operations and return a tuple of states and exception (if any)."""
    states, exc = [], None
    try:
        for s in op.rollback(state, **kwargs):
            states.append(s.clone())
    except Exception as e:
        exc = e
    return states, exc


def assert_states(states, expected: list[tuple[str, state.Status, Optional[str | Exception]]]):
    """
    Assert states values from the provided list of expected results.

    Expected values are: ``name``, ``status``, ``error`` (optional).
    """
    assert len(states) == len(expected)

    for op_state, (name, status, *err) in zip(states, expected):
        assert op_state.name == name
        assert op_state.status == status
        if err:
            assert op_state.error == str(err[0])


@pytest.fixture
def op():
    return Operation(name="op")


@pytest.fixture
def op_1():
    return Operation(name="op_1")


@pytest.fixture
def plan(op, op_1):
    return Plan(name="plan", operations=[op, op_1])


@pytest.fixture
def apps_plan(app_metas, plan, op, op_1):
    obj = AppsPlan(name="plan", pre_operations=[op], app_operations=[op_1])
    obj.set_apps(app_metas)
    return obj


@pytest.fixture
def op_state(op):
    return op.create_state()


@pytest.fixture
def yaml_backend():
    return files.YAMLBackend(state.State)


@pytest.fixture
def json_backend():
    return files.JSONBackend(state.State)
