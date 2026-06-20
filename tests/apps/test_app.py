import pytest

from ox_orch.apps.app import Versioned, Dependency, AppRelease, Application


class TestVersioned:
    def test_ref(self):
        assert Versioned(id="test", version="123").ref == ("test", "123")


class TestDependency:
    def test_parse(self):
        assert Dependency.parse("test@12.3.4") == Dependency(id="test", version="12.3.4")
        assert Dependency.parse("test==1.2.3") == Dependency(id="test", version="1.2.3")

        with pytest.raises(ValueError):
            Dependency.parse("test==1.2*")

        with pytest.raises(ValueError):
            Dependency.parse("test^=1.2")

        with pytest.raises(ValueError):
            Dependency.parse("test<=1.2")

    def test_to_string(self):
        assert Dependency.parse("test@1.2.3").to_string() == "test==1.2.3"

    def test___lt__(self):
        a = Dependency(id="test", version="1.2.23")
        b = Dependency(id="test", version="1.2.5")
        assert b < a


class TestAppRelease:
    def test_normalize_dependencies(self):
        values = AppRelease.normalize_dependencies([Dependency(id="test", version="1.2"), "test-2==3.4.5"])
        assert values == [
            Dependency(id="test", version="1.2"),
            Dependency(id="test-2", version="3.4.5"),
        ]

    def test_get_installed_version(self):
        assert AppRelease(id="pytest", package="pytest", version="0").get_installed_version()
        assert AppRelease(id="test", package="alice-in-wonderland-test", version="1").get_installed_version() is None


class TestApplication:
    def test_validate_releases_consistency(self):
        dat = {"id": "test", "package": "test", "version": "1.0.0"}
        assert Application.model_validate({**dat, "releases": {"1.2.0": {**dat, "version": "1.2.0"}}})

        # Wrong id
        with pytest.raises(ValueError):
            Application.model_validate({**dat, "releases": {"1.2.0": {**dat, "id": "wrong-id", "version": "1.2.0"}}})

        # Wrong version
        with pytest.raises(ValueError):
            Application.model_validate({**dat, "releases": {"1.2.4": {**dat, "version": "1.2.0"}}})

    def test_get_release(self):
        dat = {"id": "test", "package": "test", "version": "1.0.0"}
        app = Application.model_validate({**dat, "releases": {"1.2.0": {**dat, "version": "1.2.0"}}})

        assert app.get_release("1.0.0") is app
        assert app.get_release(None) is app
        assert app.get_release("1.2.0") is app.releases["1.2.0"]
        assert app.get_release("2.453") is None
        with pytest.raises(KeyError):
            app.get_release("2.45543", exc=True)

    def test_create_state(self, app):
        state = app.create_state()
        assert state.id == app.id
        assert state.version == app.version
        assert state.package == app.package


class TestAppStore:
    def test_resolve(self, app_store, app_meta, app_meta_1, app_dep, app_dep_1):
        assert app_store.resolve([app_dep_1.ref, app_dep.ref, app_meta.ref]) == [
            app_meta,
            app_meta_1,
            app_dep_1,
            app_dep,
        ]
