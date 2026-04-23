# tests/test_models.py
from datetime import datetime
from agent_archive.models import Message, Session

def test_session_model():
    msg = Message(role="user", content="Hello", timestamp=datetime(2023, 1, 1, 12, 0))
    session = Session(
        id="session123",
        agent_name="TestAgent",
        title="Test Session",
        start_time=datetime(2023, 1, 1, 12, 0),
        messages=[msg]
    )
    assert session.id == "session123"
    assert session.messages[0].role == "user"

def test_message_with_tool():
    msg = Message(
        role="assistant",
        content="Reading file",
        timestamp=datetime(2023, 1, 1, 12, 0),
        tool_name="read",
        token_usage={"input": 100, "output": 50},
    )
    assert msg.tool_name == "read"
    assert msg.token_usage["input"] == 100

def test_session_with_new_fields():
    msg = Message(role="user", content="Hello")
    session = Session(
        id="s1",
        agent_name="claude_code",
        title="Test",
        start_time=datetime(2023, 1, 1),
        messages=[msg],
        model="claude-opus-4-6",
        project_dir="/home/user/project",
        source_path="/home/user/.claude/projects/slug/abc.jsonl",
    )
    assert session.model == "claude-opus-4-6"
    assert session.project_dir == "/home/user/project"
    assert session.source_path == "/home/user/.claude/projects/slug/abc.jsonl"
