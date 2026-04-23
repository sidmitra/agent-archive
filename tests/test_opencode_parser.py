# tests/test_opencode_parser.py
import json
import sqlite3
from pathlib import Path
from agent_archive.parsers.opencode import OpencodeParser


def _create_test_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""CREATE TABLE session (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, parent_id TEXT,
        slug TEXT NOT NULL, directory TEXT NOT NULL, title TEXT NOT NULL,
        version TEXT NOT NULL, share_url TEXT,
        summary_additions INTEGER, summary_deletions INTEGER,
        summary_files INTEGER, summary_diffs TEXT, revert TEXT,
        permission TEXT, time_created INTEGER NOT NULL,
        time_updated INTEGER NOT NULL, time_compacting INTEGER,
        time_archived INTEGER, workspace_id TEXT
    )""")
    c.execute("""CREATE TABLE message (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
        time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL,
        data TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE part (
        id TEXT PRIMARY KEY, message_id TEXT NOT NULL,
        session_id TEXT NOT NULL, time_created INTEGER NOT NULL,
        time_updated INTEGER NOT NULL, data TEXT NOT NULL
    )""")

    c.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        "ses_001", "proj1", None, "test-slug", "/home/user/project",
        "Fix auth bug", "1.0.0", None, None, None, None, None, None, None,
        1686822000000, 1686822060000, None, None, None,
    ))

    user_data = json.dumps({
        "role": "user", "time": {"created": 1686822005000},
        "agent": "build", "model": {"providerID": "github-copilot", "modelID": "claude-opus-4.6"},
    })
    c.execute("INSERT INTO message VALUES (?,?,?,?,?)", (
        "msg_u1", "ses_001", 1686822005000, 1686822005000, user_data,
    ))
    user_part = json.dumps({
        "type": "text", "text": "Fix the auth bug", "time": {"start": 1686822005000, "end": 1686822005000},
    })
    c.execute("INSERT INTO part VALUES (?,?,?,?,?,?)", (
        "part_u1", "msg_u1", "ses_001", 1686822005000, 1686822005000, user_part,
    ))

    asst_data = json.dumps({
        "role": "assistant", "time": {"created": 1686822010000},
        "agent": "build", "model": {"providerID": "github-copilot", "modelID": "claude-opus-4.6"},
        "tokens": {"input": 200, "output": 80, "reasoning": 0, "cache": {"read": 0, "write": 0}},
    })
    c.execute("INSERT INTO message VALUES (?,?,?,?,?)", (
        "msg_a1", "ses_001", 1686822010000, 1686822010000, asst_data,
    ))
    asst_part = json.dumps({
        "type": "text", "text": "I'll look at the auth module.", "time": {"start": 1686822010000, "end": 1686822012000},
    })
    c.execute("INSERT INTO part VALUES (?,?,?,?,?,?)", (
        "part_a1", "msg_a1", "ses_001", 1686822010000, 1686822012000, asst_part,
    ))

    tool_part = json.dumps({
        "type": "tool", "tool": "bash", "callID": "toolu_1",
        "state": {"status": "completed", "input": {"command": "cat auth.py"}, "output": "def login(): pass"},
        "time": {"start": 1686822012000, "end": 1686822014000},
    })
    c.execute("INSERT INTO part VALUES (?,?,?,?,?,?)", (
        "part_a2", "msg_a1", "ses_001", 1686822012000, 1686822014000, tool_part,
    ))

    conn.commit()
    conn.close()


def test_discover(tmp_path):
    db_path = tmp_path / "opencode.db"
    _create_test_db(db_path)
    parser = OpencodeParser(db_path=db_path)
    paths = parser.discover()
    assert len(paths) == 1
    assert paths[0] == db_path


def test_parse_session(tmp_path):
    db_path = tmp_path / "opencode.db"
    _create_test_db(db_path)
    parser = OpencodeParser(db_path=db_path)
    sessions = parser.parse(db_path)

    assert len(sessions) == 1
    session = sessions[0]
    assert session.agent_name == "opencode"
    assert session.id == "ses_001"
    assert session.title == "Fix auth bug"
    assert session.model == "claude-opus-4.6"
    assert session.project_dir == "/home/user/project"
    assert session.source_path == str(db_path)

    assert len(session.messages) == 3
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Fix the auth bug"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].content == "I'll look at the auth module."
    assert session.messages[2].role == "assistant"
    assert session.messages[2].tool_name == "bash"
    assert "def login" in session.messages[2].content
