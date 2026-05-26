# tests/test_sync_integration.py
import json
from pathlib import Path
from typer.testing import CliRunner
from agent_archive.cli import app
from agent_archive.state import _state_path


runner = CliRunner()


def test_sync_creates_markdown(tmp_path):
    claude_dir = tmp_path / "claude" / "projects" / "test-project"
    claude_dir.mkdir(parents=True)
    fixture = claude_dir / "session1.jsonl"
    fixture.write_text("\n".join([
        json.dumps({"type": "user", "uuid": "u1", "parentUuid": None, "timestamp": "2023-06-15T10:00:00.000Z", "sessionId": "s1", "cwd": "/tmp/proj", "slug": "test-sess", "message": {"role": "user", "content": "Hello"}}),
        json.dumps({"type": "assistant", "uuid": "a1", "parentUuid": "u1", "timestamp": "2023-06-15T10:00:05.000Z", "sessionId": "s1", "cwd": "/tmp/proj", "slug": "test-sess", "message": {"role": "assistant", "model": "claude-opus-4-6", "content": [{"type": "text", "text": "Hi there!"}], "usage": {"input_tokens": 10, "output_tokens": 5}}}),
    ]))

    output_dir = tmp_path / "output"

    result = runner.invoke(app, [
        "sync",
        "--output", str(output_dir),
        "--claude-path", str(tmp_path / "claude"),
        "--pi-path", str(tmp_path / "pi"),
        "--opencode-db", str(tmp_path / "opencode.db"),
        "--copilot-path", str(tmp_path / "copilot"),
    ])

    assert result.exit_code == 0, result.output

    session_files = list((output_dir / "docs").rglob("*.md"))
    assert len(session_files) >= 2

    state_file = _state_path(output_dir)
    assert state_file.exists()
