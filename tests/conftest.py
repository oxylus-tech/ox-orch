import pytest

from django_installer.core.apps import AppMetadata


@pytest.fixture
def app_meta():
    return AppMetadata(
        id="test",
        name="Test",
        version="0.0.1",
    )


@pytest.fixture
def app_meta_1():
    return AppMetadata(
        id="test-1",
        name="Test 1",
        version="0.0.1",
    )


@pytest.fixture
def app_metas(app_meta, app_meta_1):
    return [app_meta, app_meta_1]
