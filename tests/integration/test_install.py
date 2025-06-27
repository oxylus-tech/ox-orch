import pytest

from ox_orch.operations.execution import ExecutionSpec, Executor
from ox_orch.operations.install import PipInstall


@pytest.fixture
def executor():
    return Executor()


@pytest.fixture
def spec(shell):
    return ExecutionSpec(
        operation=PipInstall(),
        shell=shell.spec,
    )


class TestDemoInstall:
    def test_install_with_dependency(self, executor, shell, spec, app_store_demo):
        apps = app_store_demo.resolve(["demo-1"])
        executor.apply_sync(spec, apps=apps)

        # demo_1 + demo_2 must be installed
        result_1 = shell.run_python_module(["pip", "show", "demo-1"])
        print("Pip show demo-1:", result_1)

        result_2 = shell.run_python_module(["pip", "show", "demo-2"])
        print("Pip show demo-2:", result_2)

        assert result_1.returncode == 0
        assert result_2.returncode == 0

    def test_rollback_uninstalls_both(self, executor, shell, spec, app_store_demo):
        apps = app_store_demo.resolve(["demo-1"])
        state = executor.apply_sync(spec, apps=apps)

        shell.run_python_module(["pip", "show", "demo-1"])
        shell.run_python_module(["pip", "show", "demo-2"], check=True)

        executor.rollback_sync(spec, state)

        result_1 = shell.run_python_module(["pip", "show", "demo-1"])
        result_2 = shell.run_python_module(["pip", "show", "demo-2"])
        assert result_1.returncode != 0
        assert result_2.returncode != 0
