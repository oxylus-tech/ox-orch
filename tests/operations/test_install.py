from ox_orch.core.shell import EchoShell
from ox_orch.operations.install import (
    InstallOperation,
    InstallState,
    PipInstall,
    UvInstall,
    PoetryInstall,
)


class DummyApp:
    def __init__(self, app_id, package, version, installed_version=None, source=None):
        self.id = app_id
        self.package = package
        self.version = version
        self._version = installed_version
        self.source = source

    def get_installed_version(self):
        return self._version


class DummyInstall(InstallOperation):
    __type_id__ = "tests:op:install:dummy"

    def install(self, state, shell, packages, **kwargs):
        self._last_install = (list(packages), kwargs)

    def uninstall(self, state, shell, packages, **kwargs):
        self._last_uninstall = packages


class TestInstallOperation:
    def test_apply_snapshots_and_calls_install(self, exec_ctx):
        op = DummyInstall()

        state = InstallState()
        apps = [
            DummyApp("a", "pkg_a", "1.0", "0.9"),
            DummyApp("b", "pkg_b", "2.0", None),
        ]

        op._apply(state, exec_ctx, shell=EchoShell(), apps=apps)

        assert "a" in state.backward
        assert "b" in state.backward

        installed, _ = op._last_install
        assert installed[0] == {"package": "pkg_a", "source": "pkg_a", "version": "1.0"}
        assert installed[1] == {"package": "pkg_b", "source": "pkg_b", "version": "2.0"}

    def test_rollback_downgrade_and_uninstall(self, exec_ctx):
        op = DummyInstall()

        state = InstallState()
        state.backward = {
            "a": {"package": "a", "source": "a", "version": "1.0"},
            "b": {"package": "b", "source": "b", "version": None},
        }

        op._rollback(state, exec_ctx, shell=EchoShell())

        # uninstall case
        assert op._last_uninstall == ["b"]

        # downgrade case
        installed, _ = op._last_install
        assert installed[0] == {"package": "a", "source": "a", "version": "1.0"}

    def test_snapshot_collects_versions(self):
        op = DummyInstall()

        apps = [
            DummyApp("a", "pkg_a", "1.0", "0.8"),
        ]

        snapshot = op._snapshot(apps)

        assert snapshot["a"]["version"] == "0.8"


class TestPipInstall:
    def test_get_forward(self, shell):
        op = PipInstall()
        state = InstallState()

        cmd = op.get_forward(state, shell, ["pkg_a==1.0", "pkg_b"], options=["--upgrade"])

        assert cmd == [shell.spec.python, "-m", "pip", "install", "--upgrade", "pkg_a==1.0", "pkg_b"]


class TestUvInstall:
    def test_get_forward(self, shell):
        op = UvInstall()
        state = InstallState()

        cmd = op.get_forward(state, shell, ["pkg_a==1.0"])
        assert cmd[0:3] == ["uv", "pip", "install"]
        assert "pkg_a==1.0" in cmd


class TestPoetryInstall:
    def test_get_forward(self, shell):
        op = PoetryInstall()
        state = InstallState()

        cmd = op.get_forward(state, shell, ["pkg_a==1.0"])
        assert cmd[0:4] == ["poetry", "run", "pip", "install"]
        assert "pkg_a==1.0" in cmd
