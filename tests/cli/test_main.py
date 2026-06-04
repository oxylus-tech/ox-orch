import json
from pathlib import Path

from click.testing import CliRunner

from cli.core.main import cli
from core.core.execution import ExecutionSpec


class DummySpec(ExecutionSpec):
    pass


def write_spec(path: Path):
    spec = ExecutionSpec(
        operation="tests.core.test_resolvers:DummyOperation",
        context={},
        hooks=[],
        state_path=str(path.parent / "state.yaml"),
        run_trigger="cli",
    )

    path.write_text(spec.model_dump_json())
    return spec


class TestCLIApply:
    def test_apply_success(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        state_file = tmp_path / "state.yaml"

        spec = ExecutionSpec(
            operation="tests.core.test_resolvers:DummyOperation",
            context={},
            hooks=[],
            state_path=str(state_file),
            run_trigger="cli",
        )

        spec_file.write_text(spec.model_dump_json())

        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "apply",
                "--spec",
                str(spec_file),
            ],
        )

        assert result.exit_code == 0
        assert state_file.exists()

        output = result.output
        assert "Execution completed" in output


class TestCLIRollback:
    def test_rollback(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        state_file = tmp_path / "state.yaml"

        spec = ExecutionSpec(
            operation="tests.core.test_resolvers:DummyOperation",
            context={},
            hooks=[],
            state_path=str(state_file),
            run_trigger="cli",
        )

        spec_file.write_text(spec.model_dump_json())

        runner = CliRunner()

        # First apply
        runner.invoke(cli, ["apply", "--spec", str(spec_file)])

        # Then rollback
        result = runner.invoke(
            cli,
            [
                "rollback",
                "--spec",
                str(spec_file),
            ],
        )

        assert result.exit_code == 0
        assert "Rollback completed" in result.output


class TestCLIShow:
    def test_show(self, tmp_path):
        spec_file = tmp_path / "spec.json"

        spec = ExecutionSpec(
            operation="tests.core.test_resolvers:DummyOperation",
            context={"x": 1},
            hooks=[],
            state_path=str(tmp_path / "state.yaml"),
            run_trigger="cli",
        )

        spec_file.write_text(spec.model_dump_json())

        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "show",
                "--spec",
                str(spec_file),
            ],
        )

        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["operation"].endswith("DummyOperation")
        assert data["context"]["x"] == 1
