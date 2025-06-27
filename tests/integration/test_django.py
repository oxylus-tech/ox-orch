import pytest

from ox_orch.operations.execution import ExecutionSpec, Executor
from ox_orch.operations import AppsPlan, UvInstall, ForkOperation
from ox_orch.django import DjangoProjectSync, DjangoEnable

from ..django.conftest import *  # noqa F403


@pytest.fixture
def executor():
    return Executor()


@pytest.fixture
def make_spec(shell):
    def _make(operation):
        return ExecutionSpec(
            operation=operation,
            shell=shell.spec,
        )

    return _make


@pytest.fixture
def d_app_plan():
    return AppsPlan(install=UvInstall(), operations=[DjangoEnable(), ForkOperation(operation=DjangoProjectSync())])


class TestDjango:
    def test_apply_base_plan(
        self, executor, d_app_plan, django_project, django_ctx, setup_project, make_spec, apps_ctx, app_store, db_path
    ):
        db_path.unlink(missing_ok=True)

        context = {"apps_ctx": apps_ctx, "django_ctx": django_ctx}
        django_project.disable(apps_ctx.apps)

        spec = make_spec(d_app_plan)
        state = executor.apply_sync(spec, **context)

        django_project.state_store.load()
        enabled = django_project.get_installed_apps()
        assert "django_app_1" in enabled
        assert "django_app_2" in enabled

        # FIXME: empty migrations returned whilst the db migrations actually are
        # applied.
        migrations = django_project.get_applied_migrations()
        assert "django_app_1" in migrations
        assert "django_app_2" in migrations

        executor.rollback_sync(spec, state, **context)

        django_project.state_store.load()
        assert not django_project.get_installed_apps()
        assert not django_project.get_applied_migrations()
