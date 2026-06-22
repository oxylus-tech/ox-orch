from ox_orch.core import register
from ox_orch.apps.state import AppStateFeature


@register("test-apps-state")
class DummyFeature(AppStateFeature):
    key: str
    value: str | None = None
    int_value: int | None = None


class TestAppStateStore:
    def test_get_or_create(self, app_state_store, app_dep):
        assert app_dep.id not in app_state_store

        state = app_state_store.get_or_create(app_dep)
        assert state.id == app_dep.id
        assert state.package == app_dep.package
        assert len(app_state_store.data) == 2

    def test_item_update(self, app_state_store, app_dep_1):
        state = app_state_store.get(app_dep_1.id)

        app_state_store.item_update(
            state, {"features": {"test-apps-state": {"key": "foo", "value": "bar"}}}, merge=True
        )
        assert state.features["test-apps-state"] == DummyFeature(key="foo", value="bar")

        app_state_store.item_update(
            state, {"features": {"test-apps-state": {"value": "tee", "int_value": 123}}}, merge=True
        )
        assert state.features["test-apps-state"] == DummyFeature(key="foo", value="tee", int_value=123)
