import subprocess
import sys
import os

import pytest

from ox_orch.apps import Application, AppMemoryStore
from ox_orch.core.shell import ShellSpec, Shell


@pytest.fixture
def shell_spec(tmp_path):
    venv = tmp_path / "venv"
    print("Create venv at", venv)
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
    )

    python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    print("Python:", python)
    return ShellSpec(python=str(python))


@pytest.fixture
def shell(shell_spec):
    return Shell.from_spec(shell_spec)


@pytest.fixture
def app_store_demo(data_dir):
    demo_2 = Application(
        id="demo-2",
        name="Demo 2",
        version="0.1.0",
        package="demo_2",
        source=str((data_dir / "packages/demo_2").resolve()),
    )
    demo_1 = Application(
        id="demo-1",
        name="Demo 1",
        version="0.1.0",
        package="demo_1",
        source=str((data_dir / "packages/demo_1").resolve()),
        dependencies=["demo-2@0.1.0"],
    )
    return AppMemoryStore(items=[demo_1, demo_2])
