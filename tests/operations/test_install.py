from ox_orch.core.shell import EchoShell
from ox_orch.operations.install import (
    InstallOperation,
    InstallState,
    PipInstall,
    UvInstall,
    PoetryInstall,
)


class DummyApp:
    def __init__(self, app_id, package, version, installed_version=None):
        self.id = app_id
        self.package = package
        self.version = version
        self._installed_version = installed_version

    def get_installed_version(self):
        return self._installed_version


class DummyInstall(InstallOperation):
    __type_id__ = "tests:op:install:dummy"

    def install(self, state, shell, packages, **kwargs):
        self._last_install = (packages, kwargs)

    def uninstall(self, state, shell, packages, **kwargs):
        self._last_uninstall = packages


class TestInstallOperation:
    def test_apply_snapshots_and_calls_install(self):
        op = DummyInstall()

        state = InstallState()
        apps = [
            DummyApp("a", "pkg_a", "1.0", "0.9"),
            DummyApp("b", "pkg_b", "2.0", None),
        ]

        op._apply(state, shell=EchoShell(), apps=apps)

        assert "a" in state.backward
        assert "b" in state.backward

        assert state.packages == {
            "a": "pkg_a",
            "b": "pkg_b",
        }

        installed, _ = op._last_install
        assert installed["pkg_a"] == "1.0"
        assert installed["pkg_b"] == "2.0"

    def test_rollback_downgrade_and_uninstall(self):
        op = DummyInstall()

        state = InstallState()
        state.packages = {
            "a": "pkg_a",
            "b": "pkg_b",
        }
        state.backward = {
            "a": {"installed_version": "1.0"},
            "b": {"installed_version": None},
        }

        op._rollback(state, shell=EchoShell())

        # uninstall case
        assert op._last_uninstall == ["pkg_b"]

        # downgrade case
        packages, _ = op._last_install
        assert packages["pkg_a"] == "1.0"

    def test_snapshot_collects_versions(self):
        op = DummyInstall()

        apps = [
            DummyApp("a", "pkg_a", "1.0", "0.8"),
        ]

        snapshot = op._snapshot(apps)

        assert snapshot["a"]["installed_version"] == "0.8"


class TestPipInstall:
    def test_get_forward(self):
        op = PipInstall()
        state = InstallState()

        cmd = op.get_forward(
            state,
            {"pkg_a": "1.0", "pkg_b": None},
            options=["--upgrade"],
        )

        assert cmd[0:3] == ["pip", "install", "--upgrade"]
        assert "pkg_a==1.0" in cmd
        assert "pkg_b" in cmd


class TestUvInstall:
    def test_get_forward(self):
        op = UvInstall()
        state = InstallState()

        cmd = op.get_forward(
            state,
            {"pkg_a": "1.0"},
        )

        assert cmd[0:3] == ["uv", "pip", "install"]
        assert "pkg_a==1.0" in cmd


class TestPoetryInstall:
    def test_get_forward(self):
        op = PoetryInstall()
        state = InstallState()

        cmd = op.get_forward(
            state,
            {"pkg_a": "1.0"},
        )

        assert cmd[0:2] == ["poetry", "add"]
        assert "pkg_a@1.0" in cmd
