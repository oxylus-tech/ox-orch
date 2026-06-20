from pathlib import Path
from importlib import metadata

import pytest
from pydantic import PrivateAttr, BaseModel

from ox_orch.core import files
from ox_orch.core import ExecutionContext
from ox_orch.core.shell import EchoShell, ShellSpec
from ox_orch.apps import Application, AppMemoryStore, AppStateMemoryStore
from ox_orch.operations import Operation, OperationState
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


class Operation(Operation):
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

    def _snapshot(self, apps, dry_run=False):
        if not self._called:
            versions = package_versions
            self._called = True
        else:
            versions = package_next_versions

        return {
            app.id: {"package": app.package, "version": versions[app.package], "source": app.source or app.package}
            for app in apps
        }


class DummyModel(BaseModel):
    name: str
    value: int = 0


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
    return Application(
        id="pydantic",
        package="pydantic",
        version="3",
    )


@pytest.fixture
def app_meta():
    return Application(
        id="pydantic",
        name="Pydantic",
        version=package_next_versions["pydantic"],
        package="pydantic",
        groups=["group-1", "group"],
        tags=["tag-1", "tag"],
    )


@pytest.fixture
def app_meta_1():
    return Application(
        id="pytest",
        name="Pytest",
        version=package_next_versions["pytest"],
        package="pytest",
        groups=["group"],
        tags=["tag"],
    )


@pytest.fixture
def app_dep(app_meta, app_meta_1):
    return Application(
        id="pyyaml",
        name="PyYaml",
        version=package_next_versions["pyyaml"],
        package="pyyaml",
        dependencies=[f"{app_meta.id}@{app_meta.version}", f"{app_meta_1.id}@{app_meta_1.version}"],
    )


@pytest.fixture
def app_dep_1(app_meta, app_dep):
    return Application(
        id="black",
        name="Black",
        version=package_versions["black"],
        package="black",
        # state=AppState(version=package_versions["black"]),
        dependencies=[f"{app_meta.id}@{app_meta.version}", f"{app_dep.id}@{app_dep.version}"],
    )


@pytest.fixture
def app_metas(app_meta, app_meta_1, app_dep, app_dep_1):
    return [app_meta, app_meta_1, app_dep, app_dep_1]


@pytest.fixture
def app_store(app_metas):
    return AppMemoryStore(items=list(app_metas))


@pytest.fixture
def app_state_store(app_dep_1):
    return AppStateMemoryStore(items=[app_dep_1.create_state()])


@pytest.fixture
def exec_ctx():
    return ExecutionContext()


@pytest.fixture
def shell():
    return EchoShell(ShellSpec(backend="echo"))
