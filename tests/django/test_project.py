class TestProject:
    def test_setup(self, django_project, setup_project):
        from django.conf import settings

        assert settings.TEST_TAG

    def test_get_installed_apps(self, django_project):
        django_project.get_feature().installed_apps = ["a", "b"]
        assert django_project.get_installed_apps() == ["a", "b"]

    def test_sync_installed_apps(self, django_project, d_app_1, d_app_2):
        django_project.enable([d_app_1, d_app_2])
        django_project.sync_installed_apps()
        assert django_project.get_feature().installed_apps == ["django_app_2", "django_app_1"]

    def test_get_feature(self, django_project):
        assert not django_project.state_store.features
        feature = django_project.get_feature()
        assert feature is django_project.state_store.features["django"]

    def test_snapshot_migrations_and_reverse(self, django_project, setup_project, d_app_1, d_app_2):
        from django.core.management import call_command

        snapshot = django_project.snapshot_migrations()
        call_command("migrate", interactive=False, verbosity=1)

        snapshot_2 = django_project.snapshot_migrations()
        assert "django_app_1" in snapshot_2
        assert "django_app_2" in snapshot_2

        django_project.restore_migrations(snapshot)
        snapshot_3 = django_project.snapshot_migrations()
        assert not snapshot_3

    def test_restore_migrations(self, django_project):
        pass

    def test_get_migration_executor(self, django_project):
        pass
