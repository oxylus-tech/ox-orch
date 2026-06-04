import pytest


from ox_orch.core.registry import NotFoundError, FileAppRegistry


@pytest.fixture
def yaml_file(data_dir):
    path = data_dir / "apps.test.yaml"
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def file_registry(yaml_file, app_metas):
    # enforce misordering for iteration and search
    return FileAppRegistry.from_yaml(yaml_file, apps=list(reversed(app_metas)), load=False)


class TestAppRegistry:
    def test_get_full(self, mem_registry, app_metas, app_meta, app_meta_1, app_dep, app_dep_1):
        apps = mem_registry.get_full([app_meta_1.id, app_dep_1.id])
        ids = [a.id for a in apps]

        assert len(ids) == len(app_metas)
        assert ids.index(app_dep.id) > ids.index(app_meta.id)
        assert ids.index(app_dep.id) > ids.index(app_meta_1.id)
        assert ids.index(app_dep_1.id) > ids.index(app_dep.id)


class TestMemoryAppRegistry:
    def test__init__from_list(self, mem_registry):
        # mem_registry is initialized from a list
        assert all(k == v.id for k, v in mem_registry.apps.items())

    def test_get(self, mem_registry, app_meta):
        app = mem_registry.get(app_meta.id)
        # enforce cloning over using the same object
        assert app == app_meta and app is not app_meta

    def test_get_failed_raises_not_found(self, mem_registry, app_meta):
        with pytest.raises(NotFoundError):
            mem_registry.get("not-an-app", exc=True)

    def test_get_all(self, mem_registry, app_meta, app_dep):
        assert mem_registry.get_all([app_meta.id, app_dep.id]) == [app_meta, app_dep]

    def test_get_all_raises_not_found(self, mem_registry, app_meta):
        fake_apps = ["not-an-app", "not-an-app-2"]
        try:
            mem_registry.get_all([app_meta.id, *fake_apps], exc=True)
        except NotFoundError as err:
            assert err.apps == fake_apps
        else:
            raise RuntimeError("mem_registry.get_all should have raised NotFoundError")

    def test_search(self, mem_registry, app_metas, app_meta, app_meta_1):
        items = mem_registry.search(groups="group-1", tags="tag")
        assert set(i.id for i in items) == {app_meta.id, app_meta_1.id}


class TestFileAppRegistry:
    def test__from_backend_load_from_file(self, file_registry, yaml_file):
        file_registry.save()
        obj = FileAppRegistry.from_yaml(yaml_file)
        assert obj.apps == file_registry.apps
