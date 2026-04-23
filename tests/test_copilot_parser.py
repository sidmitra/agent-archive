# tests/test_copilot_parser.py
from pathlib import Path
from agent_archive.parsers.copilot import CopilotParser


FIXTURES = Path(__file__).parent / "fixtures" / "copilot"


def test_discover(tmp_path):
    s1 = tmp_path / "session-state" / "sess1"
    s1.mkdir(parents=True)
    (s1 / "events.jsonl").write_text("{}")
    s2 = tmp_path / "session-state" / "sess2"
    s2.mkdir(parents=True)
    (s2 / "events.jsonl").write_text("{}")
    s3 = tmp_path / "session-state" / "sess3"
    s3.mkdir(parents=True)

    parser = CopilotParser(base_path=tmp_path)
    paths = parser.discover()
    assert len(paths) == 2
    assert all(p.name == "events.jsonl" for p in paths)


def test_parse_session():
    fixture = FIXTURES / "test-session" / "events.jsonl"
    parser = CopilotParser(base_path=FIXTURES)
    sessions = parser.parse(fixture)

    assert len(sessions) == 1
    session = sessions[0]
    assert session.agent_name == "copilot"
    assert session.id == "test-session-uuid"
    assert session.title == "Fix authentication"
    assert session.model == "claude-sonnet-4.6"
    assert session.project_dir == "/home/user/myproject"
    assert session.source_path == str(fixture)

    assert len(session.messages) == 4
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Fix the auth bug"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].tool_name == "bash"
    assert session.messages[2].role == "tool_result"
    assert "def login" in session.messages[2].content
    assert session.messages[3].role == "assistant"
    assert "login function is empty" in session.messages[3].content
