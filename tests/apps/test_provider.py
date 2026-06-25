import pytest

from ox_orch.apps import Application
from ox_orch.apps.provider import PyPIClient, AppProvider


@pytest.fixture
def client():
    return PyPIClient()


@pytest.fixture
def app_provider():
    return AppProvider()


class TestPyPIClient:
    @pytest.mark.asyncio
    async def test_fetch_metadata(self, client):
        data = await client.fetch_metadata("pytest")
        assert data["info"]["name"] == "pytest"

    @pytest.mark.asyncio
    async def test_fetch_many(self, client):
        data = await client.fetch_many(["pytest", "black"])
        assert data["pytest"]["info"]["name"] == "pytest"
        assert data["black"]["info"]["name"] == "black"


class TestAppProvider:
    @pytest.mark.asyncio
    async def test_build(self, app_provider):
        pkgs = ["pytest", "packaging", "black"]
        apps = await app_provider.build(pkgs)

        apps = {a.id: a for a in apps}
        assert apps
        for key in pkgs:
            app = apps[key]
            assert isinstance(app, Application)
            assert app.id == key and app.version

        # - dependency check
        app = apps["black"]
        packaging = apps["packaging"]

        assert len(app.dependencies) == 1
        assert app.dependencies[0].to_string() == f"packaging=={packaging.version}"
