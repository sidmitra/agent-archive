# tests/test_claude_code_parser.py
from pathlib import Path
from agent_archive.parsers.claude_code import ClaudeCodeParser


FIXTURES = Path(__file__).parent / "fixtures" / "claude_code"


def test_discover(tmp_path):
    project_dir = tmp_path / "projects" / "test-project"
    project_dir.mkdir(parents=True)
    (project_dir / "session1.jsonl").write_text("{}")
    (project_dir / "session2.jsonl").write_text("{}")

    parser = ClaudeCodeParser(base_path=tmp_path)
    paths = parser.discover()
    assert len(paths) == 2
    assert all(p.suffix == ".jsonl" for p in paths)


def test_parse_session():
    fixture = FIXTURES / "test-project" / "test-session.jsonl"
    parser = ClaudeCodeParser(base_path=FIXTURES)
    sessions = parser.parse(fixture)

    assert len(sessions) == 1
    session = sessions[0]
    assert session.agent_name == "claude_code"
    assert session.title == "test-session"
    assert session.model == "claude-opus-4-6"
    assert session.project_dir == "/home/user/myproject"
    assert session.source_path == str(fixture)

    assert len(session.messages) == 5
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Fix the bug in auth.py"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].content == "Let me look at the auth module."
    assert session.messages[2].role == "assistant"
    assert session.messages[2].tool_name == "Read"
    assert session.messages[3].role == "tool_result"
    assert session.messages[4].role == "assistant"
    assert "login function is empty" in session.messages[4].content
