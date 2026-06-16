import pytest

from ox_orch.core.execution import ExecutionSpec, Executor
from ox_orch.operations.install import PipInstall


@pytest.fixture
def executor():
    return Executor()


@pytest.fixture
def make_spec(shell):
    def _make(apps):
        return ExecutionSpec(
            operation=PipInstall(),
            shell=shell.spec,
            inputs={"apps": apps},
        )

    return _make


class TestDemoInstall:
    def test_install_with_dependency(self, executor, shell, make_spec, app_store_demo):
        apps = app_store_demo.resolve(["demo-1"])
        spec = make_spec(apps)
        executor.apply_sync(spec)

        # demo_1 + demo_2 must be installed
        result_1 = shell.run_python_module(["pip", "show", "demo-1"])
        print("Pip show demo-1:", result_1)

        result_2 = shell.run_python_module(["pip", "show", "demo-2"])
        print("Pip show demo-2:", result_2)

        assert result_1.returncode == 0
        assert result_2.returncode == 0

    def test_rollback_uninstalls_both(self, executor, shell, make_spec, app_store_demo):
        apps = app_store_demo.resolve(["demo-1"])
        spec = make_spec(apps)
        state = executor.apply_sync(spec)

        shell.run_python_module(["pip", "show", "demo-1"])
        shell.run_python_module(["pip", "show", "demo-2"], check=True)

        executor.rollback_sync(spec, state)

        result_1 = shell.run_python_module(["pip", "show", "demo-1"])
        result_2 = shell.run_python_module(["pip", "show", "demo-2"])
        assert result_1.returncode != 0
        assert result_2.returncode != 0
