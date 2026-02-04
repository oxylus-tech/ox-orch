import pytest

from django_installer.core.operations import AbstractOperation, Plan


class Operation(AbstractOperation):
    def _apply(self, exc=None, **kw):
        if exc:
            raise exc
        self.applied = True

    def _rollback(self, rexc=None, **kw):
        if rexc:
            raise rexc
        self.rollbacked = True


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
def parent_plan(plan, op, op_1):
    return Plan(name="plan", operations=[op, plan, op_1])
