from pathlib import Path
from importlib import metadata

import pytest
from pydantic import PrivateAttr

from ox_orch.core import app_registry, files
from ox_orch.core.contexts import ExecutionContext
from ox_orch.core.apps import AppMetadata, AppInstallState
from ox_orch.operations import AbstractOperation, OperationState
from ox_orch.operations.install import InstallOperation


# We need real package names though their dependencies relationship here are fake.
# Keep only one with its current version for reconciliation detection tests.
package_versions = {
    "pydantic": metadata.version("pydantic"),
    "pytest": metadata.version("pytest"),
    "pyyaml": metadata.version("pyyaml"),
    "black": metadata.version("black"),
}
package_next_versions = {key: f"{int(value.split('.')[0])+1}" for key, value in package_versions.items()}


class Operation(AbstractOperation):
    applied: bool = False
    rollbacked: bool = False
    __type_id__ = "op:test:operation"

    def _apply(self, state, ctx, exc=None, **kw):
        if exc:
            raise exc
        self.applied = True

    def _rollback(self, state, ctx, rexc=None, **kw):
        if rexc:
            raise rexc
        self.rollbacked = True


class FakeInstall(InstallOperation):
    __type_id__ = "op:test:install"

    _called = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._called = False

    def install(self, state, shell, packages, **kwargs):
        self._last_install = (packages, kwargs)

    def uninstall(self, state, shell, packages, **_):
        self._last_uninstall = packages

    def _snapshot(self, apps):
        if not self._called:
            versions = package_versions
            self._called = True
        else:
            versions = package_next_versions

        return {app.id: {"installed_version": versions[app.package]} for app in apps}


@pytest.fixture
def data_dir():
    return Path(__file__).parent / "data"


@pytest.fixture
def yaml_backend():
    return files.YAMLBackend(OperationState)


@pytest.fixture
def json_backend():
    return files.JSONBackend(OperationState)


@pytest.fixture
def op():
    return Operation(operation_id="op")


@pytest.fixture
def op_state(op):
    return op.create_state()


@pytest.fixture
def app():
    return AppMetadata(
        id="pydantic",
        package="pydantic",
        version="3",
    )


@pytest.fixture
def app_meta():
    return AppMetadata(
        id="pydantic",
        name="Pydantic",
        version=package_next_versions["pydantic"],
        package="pydantic",
        groups=["group-1", "group"],
        tags=["tag-1", "tag"],
    )


@pytest.fixture
def app_meta_1():
    return AppMetadata(
        id="pytest",
        name="Pytest",
        version=package_next_versions["pytest"],
        package="pytest",
        groups=["group"],
        tags=["tag"],
    )


@pytest.fixture
def app_dep(app_meta, app_meta_1):
    return AppMetadata(
        id="pyyaml",
        name="PyYaml",
        version=package_next_versions["pyyaml"],
        package="pyyaml",
        dependencies=[app_meta.id, app_meta_1.id],
    )


@pytest.fixture
def app_dep_1(app_meta, app_dep):
    return AppMetadata(
        id="black",
        name="Black",
        version=package_versions["black"],
        package="black",
        state=AppInstallState(installed_version=package_versions["black"]),
        dependencies=[app_meta.id, app_dep.id],
    )


@pytest.fixture
def app_metas(app_meta, app_meta_1, app_dep, app_dep_1):
    return [app_meta, app_meta_1, app_dep, app_dep_1]


@pytest.fixture
def mem_registry(app_metas):
    # enforce misordering for iteration and search tests
    return app_registry.MemoryAppRegistry(apps=list(reversed(app_metas)))


@pytest.fixture
def exec_ctx():
    return ExecutionContext()
