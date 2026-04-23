# tests/test_pi_parser.py
from pathlib import Path
from agent_archive.parsers.pi import PiParser


FIXTURES = Path(__file__).parent / "fixtures" / "pi"


def test_discover(tmp_path):
    session_dir = tmp_path / "sessions" / "test-project"
    session_dir.mkdir(parents=True)
    (session_dir / "2023-06-15T100000_abc.jsonl").write_text("{}")
    (session_dir / "2023-06-15T110000_def.jsonl").write_text("{}")

    parser = PiParser(base_path=tmp_path)
    paths = parser.discover()
    assert len(paths) == 2
    assert all(p.suffix == ".jsonl" for p in paths)


def test_parse_session():
    fixture = FIXTURES / "test-project" / "2023-06-15T100000_abc123.jsonl"
    parser = PiParser(base_path=FIXTURES)
    sessions = parser.parse(fixture)

    assert len(sessions) == 1
    session = sessions[0]
    assert session.agent_name == "pi"
    assert session.id == "abc123"
    assert session.model == "gemini-3.1-pro-high"
    assert session.project_dir == "/home/user/myproject"
    assert session.source_path == str(fixture)

    assert len(session.messages) == 4
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "What files are in this directory?"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].tool_name == "bash"
    assert session.messages[2].role == "tool_result"
    assert "README.md" in session.messages[2].content
    assert session.messages[3].role == "assistant"
