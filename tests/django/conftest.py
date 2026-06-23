import sys

import pytest

from ox_orch.apps import Application, AppMemoryStore, AppStateFileStore
from ox_orch.django import DjangoProject, DjangoAppFeature, DjangoContext
from ox_orch.operations import AppsContext


@pytest.fixture
def project_path(data_dir):
    return data_dir / "packages" / "django-project" / "src"


@pytest.fixture
def project_settings():
    return "django_project.settings"


@pytest.fixture
def d_app_1(data_dir):
    return Application(
        id="django-app-1",
        name="Django App 1",
        version="0.1.0",
        source=str(data_dir / "packages" / "django-app-1"),
        features={"django": DjangoAppFeature(apps=["django_app_1"])},
    )


@pytest.fixture
def d_app_2(data_dir):
    return Application(
        id="django-app-2",
        name="Django App 2",
        version="0.1.0",
        source=str(data_dir / "packages" / "django-app-2"),
        dependencies=["django-app-1==0.1.0"],
        features={"django": DjangoAppFeature(apps=["django_app_2"])},
    )


@pytest.fixture
def app_store(d_app_1, d_app_2):
    return AppMemoryStore(items=[d_app_1, d_app_2])


@pytest.fixture
def app_state_store(project_path):
    path = project_path.parent / "app_states.json"
    yield AppStateFileStore(path)
    path.unlink(missing_ok=True)


@pytest.fixture
def django_project(app_store, app_state_store):
    return DjangoProject(store=app_store, state_store=app_state_store)


@pytest.fixture
def db_path(django_project):
    return django_project.state_store.path.parent / "db.sqlite3"


_is_setup = False


@pytest.fixture
def setup_project(django_project, project_path, project_settings, db_path, d_app_1, d_app_2):
    global _is_setup
    if not _is_setup:
        db_path.unlink(missing_ok=True)

        _is_setup = True
        sys.path = [
            f"{d_app_1.source}/src",
            f"{d_app_2.source}/src",
        ] + sys.path

        django_project.enable([d_app_1, d_app_2])
        django_project.sync_installed_apps()
        django_project.setup(project_settings, project_path)

        yield django_project
    else:
        yield django_project


@pytest.fixture
def apps_ctx(app_store, app_state_store, d_app_1, d_app_2):
    return AppsContext(
        apps=[d_app_1, d_app_2],
        store=app_store,
        state_store=app_state_store,
    )


@pytest.fixture
def django_ctx(apps_ctx, project_path, project_settings):
    return DjangoContext.from_apps_ctx(
        apps_ctx,
        settings_module=project_settings,
        project_path=project_path,
    )
