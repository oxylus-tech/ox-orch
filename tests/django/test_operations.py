import pytest

from ox_orch.operations import Operation
from ox_orch.django.operations import DjangoEnable, DjangoSetup, Migrate, DjangoProjectSync


class TestDjangoContext:
    def test_from_apps_ctx(self, django_ctx, apps_ctx):
        # already initialized using from_apps_ctx
        assert django_ctx.project.store is apps_ctx.store
        assert django_ctx.project.state_store is apps_ctx.state_store


class TestDjangoEnable:
    def test__apply(self, apps_ctx, django_ctx, d_app_1):
        op = DjangoEnable()

        assert not django_ctx.project.get_installed_apps()
        op._apply(op.create_state(), apps_ctx=apps_ctx, django_ctx=django_ctx)
        assert django_ctx.project.get_installed_apps() == [
            "django_app_2",
            "django_app_1",
        ]


class TestDjangoSetup:
    def test__apply(self, django_project, django_ctx):
        # Simple mock
        class FakeProject:
            def setup(self, settings_module, project_path):
                self.settings_module = settings_module
                self.project_path = project_path

        django_ctx.project = FakeProject()
        DjangoSetup()._apply(None, django_ctx=django_ctx)
        assert django_ctx.project.settings_module == django_ctx.settings_module
        assert django_ctx.project.project_path == django_ctx.project_path


class TestMigrate:
    def test__apply_and_rollback(self, django_project, django_ctx, setup_project):
        # DB clean up
        snapshot = django_project.get_applied_migrations()
        django_project.restore_migrations({})

        op = Migrate()
        state = op.create_state()

        op._apply(state, django_ctx=django_ctx)
        assert "django_app_1" in state.forward
        assert "django_app_2" in state.forward
        snapshot = django_project.get_applied_migrations()
        assert snapshot.get("django_app_1")
        assert snapshot.get("django_app_2")

        op._rollback(state, django_ctx=django_ctx)
        snapshot = django_project.get_applied_migrations()
        assert not snapshot


class TestDjangoProjectSync:
    @pytest.fixture
    def operations(self):
        return [Operation() for i in range(0, 6)]

    def test_get_operations(self, django_ctx, operations):
        op = DjangoProjectSync(before_migrate=operations[:2], after_migrate=operations[2:4], operations=operations[4:])
        assert isinstance(op.pre_operation, DjangoSetup)
        assert op.get_operations(op.create_state()) == [
            operations[0],
            operations[1],
            op.migrate,
            operations[2],
            operations[3],
            op.collectstatic,
            op.compilemessages,
            operations[4],
            operations[5],
        ]
