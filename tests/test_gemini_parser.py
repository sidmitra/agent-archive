# tests/test_gemini_parser.py
from datetime import timezone
from pathlib import Path

import pytest

from agent_archive.parsers.gemini import GeminiParser

FIXTURES = Path(__file__).parent / "fixtures" / "gemini"


def test_discover_finds_session_files():
    parser = GeminiParser(base_path=FIXTURES)
    found = parser.discover()
    assert len(found) == 1
    assert found[0].name == "session-2024-03-10T09-00-abc12345.json"


def test_discover_missing_dir():
    parser = GeminiParser(base_path=Path("/nonexistent/path"))
    assert parser.discover() == []


def test_parse_returns_one_session():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    sessions = parser.parse(filepath)
    assert len(sessions) == 1


def test_session_metadata():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]

    assert session.id == "abc12345-0000-0000-0000-000000000001"
    assert session.agent_name == "gemini"
    assert session.model == "gemini-2.5-pro"
    assert session.start_time.tzinfo is not None
    assert session.end_time is not None
    assert session.end_time > session.start_time
    assert session.project_dir == "/tmp/test-project"
    assert session.source_path.endswith(".json")


def test_title_taken_from_first_user_message():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]
    assert session.title == "List files in the current directory"


def test_info_messages_skipped():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]
    # info messages are now emitted as meta events, not regular messages
    meta_msgs = [m for m in session.messages if m.role == "meta"]
    assert len(meta_msgs) == 1
    assert meta_msgs[0].meta_subtype == "info"
    assert meta_msgs[0].content == "Gemini CLI v1.0.0"
    # No raw info messages in the regular stream
    roles = [m.role for m in session.messages if m.role in ("user", "assistant", "tool_result")]
    assert "info" not in roles


def test_user_messages_parsed():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]
    user_msgs = [m for m in session.messages if m.role == "user"]
    assert len(user_msgs) == 2
    assert user_msgs[0].content == "List files in the current directory"
    assert user_msgs[1].content == "Thanks, that's all."


def test_assistant_text_message():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]
    assistant_text = [m for m in session.messages if m.role == "assistant" and not m.tool_name]
    assert any("I'll list the files for you." in m.content for m in assistant_text)
    assert any("You're welcome" in m.content for m in assistant_text)


def test_tool_call_message():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]
    tool_calls = [m for m in session.messages if m.role == "assistant" and m.tool_name]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "run_shell_command"
    assert "ls -la" in tool_calls[0].content


def test_tool_result_message():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]
    tool_results = [m for m in session.messages if m.role == "tool_result"]
    assert len(tool_results) == 1
    assert "README.md" in tool_results[0].content


def test_token_usage():
    parser = GeminiParser(base_path=FIXTURES)
    filepath = FIXTURES / "test-project" / "chats" / "session-2024-03-10T09-00-abc12345.json"
    session = parser.parse(filepath)[0]
    messages_with_tokens = [m for m in session.messages if m.token_usage]
    assert len(messages_with_tokens) >= 1
    for m in messages_with_tokens:
        assert "input" in m.token_usage
        assert "output" in m.token_usage


def test_no_project_root():
    """Parser works when .project_root file is absent."""
    import json, tempfile
    data = {
        "sessionId": "no-root-session",
        "startTime": "2024-01-01T00:00:00.000Z",
        "lastUpdated": "2024-01-01T00:01:00.000Z",
        "messages": [
            {"id": "1", "timestamp": "2024-01-01T00:00:01.000Z", "type": "user",
             "content": [{"text": "hello"}]},
            {"id": "2", "timestamp": "2024-01-01T00:00:05.000Z", "type": "gemini",
             "content": "hi", "tokens": {"input": 5, "output": 1}, "model": "gemini-2.5-flash"},
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        chats = Path(tmp) / "proj" / "chats"
        chats.mkdir(parents=True)
        session_file = chats / "session-2024-01-01T00-00-noroot.json"
        session_file.write_text(json.dumps(data))

        parser = GeminiParser(base_path=Path(tmp))
        sessions = parser.parse(session_file)
        assert len(sessions) == 1
        assert sessions[0].project_dir is None


def test_empty_session_returns_empty():
    import json, tempfile
    data = {
        "sessionId": "empty",
        "startTime": "2024-01-01T00:00:00.000Z",
        "lastUpdated": "2024-01-01T00:01:00.000Z",
        "messages": [],
    }
    with tempfile.TemporaryDirectory() as tmp:
        chats = Path(tmp) / "proj" / "chats"
        chats.mkdir(parents=True)
        f = chats / "session-2024-01-01T00-00-empty.json"
        f.write_text(json.dumps(data))
        parser = GeminiParser(base_path=Path(tmp))
        assert parser.parse(f) == []
