# tests/test_redactor.py
from datetime import datetime, timezone

import pytest

from agent_archive.models import Message, Session
from agent_archive.redactor import Redactor, _redact_text


def _session(content: str) -> Session:
    return Session(
        id="s1",
        agent_name="pi",
        title="Test session",
        start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        messages=[Message(role="user", content=content)],
    )


# ---------------------------------------------------------------------------
# _redact_text unit tests
# ---------------------------------------------------------------------------


class TestKnownTokenFormats:
    def test_openai_key(self):
        text = "set OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"
        result = _redact_text(text)
        assert "sk-" not in result
        assert "REDACTED" in result

    def test_openai_proj_key(self):
        text = "export OPENAI_KEY=sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
        result = _redact_text(text)
        assert "sk-proj-" not in result
        assert "REDACTED" in result

    def test_anthropic_key(self):
        text = "ANTHROPIC_API_KEY=sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"
        result = _redact_text(text)
        assert "sk-ant-" not in result
        assert "REDACTED" in result

    def test_github_personal_token(self):
        text = "token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = _redact_text(text)
        assert "ghp_" not in result
        assert "REDACTED" in result

    def test_aws_access_key(self):
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = _redact_text(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "REDACTED" in result

    def test_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload"
        result = _redact_text(text)
        assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer REDACTED" in result

    def test_bearer_case_insensitive(self):
        text = "authorization: bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        result = _redact_text(text)
        assert "eyJ" not in result


class TestEnvVarAssignments:
    def test_export_with_token_name(self):
        text = "export MY_API_TOKEN=supersecretvalue123"
        result = _redact_text(text)
        assert "supersecretvalue123" not in result
        assert "MY_API_TOKEN=REDACTED" in result

    def test_plain_assignment_password(self):
        text = "DB_PASSWORD=hunter2\nDB_HOST=localhost"
        result = _redact_text(text)
        assert "hunter2" not in result
        assert "localhost" in result  # non-secret var untouched

    def test_secret_keyword_in_name(self):
        text = "GITHUB_TOKEN=ghs_ABCDEFGHIJKLMNOPQRSTUVWXYZabc123"
        result = _redact_text(text)
        assert "ghs_" not in result

    def test_non_secret_var_not_redacted(self):
        text = "EDITOR=vim\nSHELL=/bin/zsh"
        result = _redact_text(text)
        assert result == text


class TestJsonKeyValuePairs:
    def test_api_key_json(self):
        text = '{"api_key": "mysecretapikey12345", "model": "gpt-4"}'
        result = _redact_text(text)
        assert "mysecretapikey12345" not in result
        assert "REDACTED" in result
        assert '"model": "gpt-4"' in result  # non-secret untouched

    def test_token_json(self):
        text = '{"access_token": "sometoken12345678", "expires_in": 3600}'
        result = _redact_text(text)
        assert "sometoken12345678" not in result
        assert "3600" in result

    def test_password_json(self):
        text = '{"username": "alice", "password": "p@ssw0rd!!"}'
        result = _redact_text(text)
        assert "p@ssw0rd" not in result
        assert '"username": "alice"' in result

    def test_non_secret_json_untouched(self):
        text = '{"name": "my-project", "version": "1.0.0"}'
        result = _redact_text(text)
        assert result == text


class TestEdgeCases:
    def test_empty_string(self):
        assert _redact_text("") == ""

    def test_no_secrets(self):
        text = "Hello world, this is just a regular message."
        assert _redact_text(text) == text

    def test_multiple_secrets_in_one_string(self):
        text = (
            "export OPENAI_KEY=sk-abcdefghijklmnopqrstuvwxyz1234 and "
            "ANTHROPIC_KEY=sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        )
        result = _redact_text(text)
        assert "sk-" not in result
        assert result.count("REDACTED") >= 2


# ---------------------------------------------------------------------------
# Redactor class tests
# ---------------------------------------------------------------------------


class TestRedactor:
    def test_redact_session_returns_new_object(self):
        session = _session("export API_KEY=supersecret123")
        redactor = Redactor()
        redacted = redactor.redact_session(session)
        # original untouched
        assert session.messages[0].content == "export API_KEY=supersecret123"
        # redacted copy has secret removed
        assert "supersecret123" not in redacted.messages[0].content
        assert "REDACTED" in redacted.messages[0].content

    def test_redact_sessions_list(self):
        sessions = [
            _session("sk-abcdefghijklmnopqrstuvwxyz1234"),
            _session("no secrets here"),
        ]
        redactor = Redactor()
        results = redactor.redact_sessions(sessions)
        assert "sk-" not in results[0].messages[0].content
        assert results[1].messages[0].content == "no secrets here"

    def test_session_metadata_preserved(self):
        session = _session("OPENAI_KEY=sk-abcdefghijklmnopqrstuvwxyz1234")
        session.model = "claude-opus-4"
        session.project_dir = "/home/user/project"
        redacted = Redactor().redact_session(session)
        assert redacted.id == session.id
        assert redacted.agent_name == session.agent_name
        assert redacted.title == session.title
        assert redacted.model == session.model
        assert redacted.project_dir == session.project_dir
        assert redacted.start_time == session.start_time

    def test_all_message_roles_redacted(self):
        session = Session(
            id="s2",
            agent_name="pi",
            title="Multi-role",
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            messages=[
                Message(role="user", content="my token is ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"),
                Message(role="assistant", content="I see token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"),
                Message(role="tool_result", content="Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.stuff"),
            ],
        )
        redacted = Redactor().redact_session(session)
        for msg in redacted.messages:
            assert "ghp_" not in msg.content
            assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in msg.content
