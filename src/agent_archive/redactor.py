# src/agent_archive/redactor.py
"""Redact secrets from session messages before backup."""

import copy
import re
from typing import List

from .models import Message, Session

# ---------------------------------------------------------------------------
# Known secret token formats
# ---------------------------------------------------------------------------
_LITERAL_PATTERNS: List[re.Pattern] = [
    # OpenAI API keys: sk-... or sk-proj-...
    re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{20,}'),
    # Anthropic API keys: sk-ant-...
    re.compile(r'sk-ant-[A-Za-z0-9_-]{20,}'),
    # GitHub tokens: ghp_, ghs_, gho_, ghu_, github_pat_
    re.compile(r'gh[psoua]_[A-Za-z0-9]{36,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{80,}'),
    # SendGrid API keys: SG.<public>.<secret>
    re.compile(r'SG\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}'),
    # AWS access key IDs
    re.compile(r'AKIA[0-9A-Z]{16}'),
    # Generic "Bearer <token>" (HTTP Authorization headers)
    re.compile(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/=\-]{16,}'),
]

# ---------------------------------------------------------------------------
# Variable-name heuristics
# ---------------------------------------------------------------------------
_SECRET_VAR_RE = re.compile(
    r'(?i)TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|AUTH|CREDENTIAL|PRIVATE|OAUTH|CERT|ACCESS_?KEY|SIGNING',
)

# Shell env var assignment: [export ]VARNAME=value  (value up to whitespace or end-of-line)
_ENV_ASSIGN_RE = re.compile(
    r'((?:export\s+)?[A-Za-z_][A-Za-z0-9_]*)(=)\s*(\S+)',
)

# JSON/YAML key-value pairs: "key": "value"  or  key: value  (quoted and bare)
_JSON_KV_RE = re.compile(
    r'("(?:[A-Za-z_][A-Za-z0-9_]*)"\s*:\s*")([^"]{4,})(")',
)
_YAML_KV_RE = re.compile(
    r"^(\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s+)(\S.*?)(\s*)$",
    re.MULTILINE,
)


def _redact_text(text: str) -> str:
    """Return a copy of *text* with all detected secrets replaced by REDACTED."""
    if not text:
        return text

    # 1. Known literal token formats
    for pattern in _LITERAL_PATTERNS:
        # For Bearer, preserve the keyword
        if b'Bearer' in pattern.pattern.encode() or 'Bearer' in pattern.pattern:
            text = pattern.sub(lambda m: m.group(1) + 'REDACTED', text)
        else:
            text = pattern.sub('REDACTED', text)

    # 2. Shell env var assignments where the name looks secret-like
    def _redact_env(m: re.Match) -> str:
        name = m.group(1)
        # Strip leading "export " to inspect just the variable name
        var_name = name.lstrip().removeprefix('export').strip()
        if _SECRET_VAR_RE.search(var_name):
            return name + m.group(2) + 'REDACTED'
        return m.group(0)

    text = _ENV_ASSIGN_RE.sub(_redact_env, text)

    # 3. JSON key-value pairs where the key looks secret-like
    def _redact_json_kv(m: re.Match) -> str:
        key_part = m.group(1)  # e.g. '"api_key": "'
        # Extract just the key name from the prefix
        key_name_match = re.search(r'"([^"]+)"', key_part)
        if key_name_match and _SECRET_VAR_RE.search(key_name_match.group(1)):
            return key_part + 'REDACTED' + m.group(3)
        return m.group(0)

    text = _JSON_KV_RE.sub(_redact_json_kv, text)

    return text


class Redactor:
    """Apply secret redaction to a list of sessions, returning new objects."""

    def redact_session(self, session: Session) -> Session:
        """Return a deep-copied session with secrets scrubbed from all messages."""
        redacted_messages = [
            Message(
                role=msg.role,
                content=_redact_text(msg.content),
                timestamp=msg.timestamp,
                tool_name=msg.tool_name,
                token_usage=msg.token_usage,
            )
            for msg in session.messages
        ]
        return Session(
            id=session.id,
            agent_name=session.agent_name,
            title=session.title,
            start_time=session.start_time,
            end_time=session.end_time,
            messages=redacted_messages,
            model=session.model,
            project_dir=session.project_dir,
            source_path=session.source_path,
        )

    def redact_sessions(self, sessions: List[Session]) -> List[Session]:
        return [self.redact_session(s) for s in sessions]
