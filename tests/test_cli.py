# tests/test_cli.py
from typer.testing import CliRunner
from agent_archive.cli import app

runner = CliRunner()

def test_sync_command_help():
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
    assert "output" in result.stdout
