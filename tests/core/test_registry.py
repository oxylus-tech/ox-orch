import pytest


from django_installer.core import MemoryAppRegistry


@pytest.fixture
def mem_registry(app_metas):
    # enforce misordering for iteration and search
    return MemoryAppRegistry(apps=list(reversed(app_metas)))


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

    def test_is_installed(self, mem_registry, app_meta, app_dep):
        pass

    def test_is_installed_with_missing_app(self, mem_registry, app_dep):
        pass

    def test_get(self, mem_registry, app_meta):
        pass

    def test_get_failed_raises_not_found(self, mem_registry, app_meta):
        pass

    def test_get_all(self, mem_registry, app_meta, app_dep):
        pass

    def test_get_all_raises_not_found(self, mem_registry, app_meta, app_dep):
        pass

    def test_search(self, mem_registry, app_meta, app_meta_1):
        pass
