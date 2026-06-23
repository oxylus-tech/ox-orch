class TestProject:
    def test_setup(self, django_project, setup_project):
        from django.conf import settings

        assert settings.TEST_TAG

    def test_get_installed_apps(self, django_project):
        django_project.get_feature().installed_apps = ["a", "b"]
        assert django_project.get_installed_apps() == ["a", "b"]

    def test_enable_and_disable(self, django_project, d_app_1, d_app_2):
        enabled = django_project.get_installed_apps()
        if enabled:
            assert "django_app_1" in enabled
            assert "django_app_2" in enabled

            django_project.disable([d_app_1, d_app_2])
            django_project.sync_installed_apps()
            assert not django_project.get_installed_apps()
        else:
            django_project.enable([d_app_1, d_app_2])
            django_project.sync_installed_apps()
            assert django_project.get_installed_apps()
            self.test_enable_and_disable(django_project, d_app_1, d_app_2)

    def test_sync_installed_apps(self, django_project, d_app_1, d_app_2):
        django_project.enable([d_app_1, d_app_2])
        django_project.sync_installed_apps()
        assert django_project.get_feature().installed_apps == ["django_app_2", "django_app_1"]

    def test_get_feature(self, django_project):
        assert not django_project.state_store.features
        feature = django_project.get_feature()
        assert feature is django_project.state_store.features["django"]

    def test_get_applied_migrations_and_restore(self, django_project, setup_project, d_app_1, d_app_2):
        from django.core.management import call_command

        django_project.restore_migrations({})
        snapshot = django_project.get_applied_migrations()
        call_command("migrate", interactive=False, verbosity=1)

        snapshot_2 = django_project.get_applied_migrations()
        assert "django_app_1" in snapshot_2
        assert "django_app_2" in snapshot_2

        django_project.restore_migrations(snapshot)
        snapshot_3 = django_project.get_applied_migrations()
        assert not snapshot_3
