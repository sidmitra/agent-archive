# tests/test_renderer.py
from datetime import datetime, timezone
from pathlib import Path
from agent_archive.renderer import MarkdownRenderer
from agent_archive.models import Message, Session


def _make_session():
    return Session(
        id="sess1",
        agent_name="claude_code",
        title="Fix auth bug",
        start_time=datetime(2023, 6, 15, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2023, 6, 15, 10, 5, tzinfo=timezone.utc),
        messages=[
            Message(role="user", content="Fix the bug", timestamp=datetime(2023, 6, 15, 10, 0, tzinfo=timezone.utc)),
            Message(role="assistant", content="Looking at it.", timestamp=datetime(2023, 6, 15, 10, 0, 5, tzinfo=timezone.utc)),
            Message(role="assistant", content='cat auth.py', timestamp=datetime(2023, 6, 15, 10, 0, 10, tzinfo=timezone.utc), tool_name="bash"),
            Message(role="tool_result", content="def login(): pass", timestamp=datetime(2023, 6, 15, 10, 0, 11, tzinfo=timezone.utc)),
        ],
        model="claude-opus-4-6",
        project_dir="/home/user/project",
        source_path="/home/user/.claude/projects/slug/sess1.jsonl",
    )


def test_render_session_page():
    renderer = MarkdownRenderer()
    md = renderer.render_session(_make_session())
    assert "title: \"Fix auth bug\"" in md
    assert "agent: claude_code" in md
    assert "**User** (10:00)" in md
    assert "**Assistant** (10:00)" in md
    assert "**Assistant** [tool: bash]" in md
    assert "**Tool Result**" in md
    assert "Fix the bug" in md


def test_render_writes_files(tmp_path):
    renderer = MarkdownRenderer()
    sessions = [_make_session()]
    renderer.render_all(sessions, tmp_path)

    session_file = tmp_path / "docs" / "2023-06" / "claude_code" / "sess1.md"
    assert session_file.exists()
    content = session_file.read_text()
    assert "Fix auth bug" in content

    month_index = tmp_path / "docs" / "2023-06" / "index.md"
    assert month_index.exists()
    assert "claude_code" in month_index.read_text().lower()

    homepage = tmp_path / "docs" / "index.md"
    assert homepage.exists()
    assert "Agent Archive" in homepage.read_text()
    assert "Claude Code" in homepage.read_text()  # agent display name appears in stats
