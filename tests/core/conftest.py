import pytest

from django_installer.core.operations import AbstractOperation, Plan, AppsPlan


class Operation(AbstractOperation):
    applied: bool = False
    rollbacked: bool = False

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
def apps_plan(app_metas, plan, op, op_1):
    return AppsPlan(name="plan", apps=app_metas, pre_operations=[op], app_operations=[op_1])
