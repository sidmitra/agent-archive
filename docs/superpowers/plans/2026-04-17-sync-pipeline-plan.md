# Sync Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agent-archive sync --output <dir>` parse session logs from Claude Code, pi, opencode, and copilot, render them as Markdown, and build a searchable MkDocs static site with incremental sync.

**Architecture:** A four-stage pipeline (discover → parse → render → build). Each agent has a parser that returns `List[Session]`. A `MarkdownRenderer` writes session pages and index pages. A `SiteBuilder` generates `mkdocs.yml` and runs `mkdocs build`. A `SyncState` tracks file mtimes to skip unchanged files.

**Tech Stack:** Python 3.10+, Typer, Pydantic, MkDocs, MkDocs-Material, sqlite3 (stdlib), PyYAML.

**Worktree:** All work happens in `.worktrees/sync-pipeline` on branch `feature/sync-pipeline`.

**Run tests with:** `source /Users/smitra/Shared/Projects/opensource/venv/bin/activate && PYTHONPATH=src pytest <test_file> -v`

**Task order:** Tasks 1-6 are sequential. **Task 11 (pyyaml dep) must be done before Task 7** (copilot parser imports `yaml`). Tasks 8-9 can follow in any order after 7. Task 10 depends on all others.

---

### Task 1: Extend Data Models

**Files:**
- Modify: `src/agent_archive/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_models.py -v`
Expected: FAIL — `Message` and `Session` lack the new fields.

- [ ] **Step 3: Write minimal implementation**

Replace `src/agent_archive/models.py` with:

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None
    tool_name: Optional[str] = None
    token_usage: Optional[dict] = None


class Session(BaseModel):
    id: str
    agent_name: str
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    messages: List[Message]
    model: Optional[str] = None
    project_dir: Optional[str] = None
    source_path: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_archive/models.py tests/test_models.py
git commit -m "feat: extend Message and Session models with tool and source fields"
```

---

### Task 2: Extend BaseParser with discover()

**Files:**
- Modify: `src/agent_archive/parsers/base.py`
- Modify: `tests/test_base_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_base_parser.py
from agent_archive.parsers.base import BaseParser
from pathlib import Path


class DummyParser(BaseParser):
    def discover(self):
        return [Path("/tmp/session.jsonl")]

    def parse(self, filepath: Path):
        return []


def test_base_parser_interface():
    parser = DummyParser()
    assert hasattr(parser, "parse")


def test_base_parser_discover():
    parser = DummyParser()
    paths = parser.discover()
    assert len(paths) == 1
    assert paths[0] == Path("/tmp/session.jsonl")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_base_parser.py -v`
Expected: FAIL — `discover` is not abstract yet, `DummyParser` won't be forced to implement it, but the import will work. Actually the test should pass since DummyParser defines discover. The real check is that BaseParser now requires discover as abstract. Write a test that tries to instantiate BaseParser directly:

Actually, replace the test file entirely:

```python
# tests/test_base_parser.py
import pytest
from agent_archive.parsers.base import BaseParser
from pathlib import Path


class DummyParser(BaseParser):
    def discover(self):
        return [Path("/tmp/session.jsonl")]

    def parse(self, filepath: Path):
        return []


class IncompleteParser(BaseParser):
    def parse(self, filepath: Path):
        return []


def test_base_parser_interface():
    parser = DummyParser()
    assert hasattr(parser, "parse")
    assert hasattr(parser, "discover")


def test_base_parser_discover():
    parser = DummyParser()
    paths = parser.discover()
    assert len(paths) == 1
    assert paths[0] == Path("/tmp/session.jsonl")


def test_incomplete_parser_raises():
    with pytest.raises(TypeError):
        IncompleteParser()
```

- [ ] **Step 2b: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_base_parser.py -v`
Expected: FAIL — `test_incomplete_parser_raises` passes but `test_base_parser_discover` may fail because `discover` is not yet abstract on the base class. More precisely, `IncompleteParser` will instantiate fine because `discover` isn't abstract yet, so `test_incomplete_parser_raises` fails.

- [ ] **Step 3: Write minimal implementation**

Replace `src/agent_archive/parsers/base.py` with:

```python
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from ..models import Session


class BaseParser(ABC):
    @abstractmethod
    def discover(self) -> List[Path]:
        """Return all session log file paths for this agent."""

    @abstractmethod
    def parse(self, filepath: Path) -> List[Session]:
        """Parse a single log file into Session objects."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_base_parser.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_archive/parsers/base.py tests/test_base_parser.py
git commit -m "feat: add abstract discover() method to BaseParser"
```

---

### Task 3: SyncState

**Files:**
- Create: `src/agent_archive/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
import json
import time
from pathlib import Path
from agent_archive.state import SyncState


def test_sync_state_new(tmp_path):
    state = SyncState(tmp_path / ".sync_state.json")
    assert state.files == {}


def test_sync_state_is_changed_new_file(tmp_path):
    state = SyncState(tmp_path / ".sync_state.json")
    # Create a dummy file
    f = tmp_path / "session.jsonl"
    f.write_text('{"type": "user"}')
    assert state.is_changed(f) is True


def test_sync_state_save_and_load(tmp_path):
    state_path = tmp_path / ".sync_state.json"
    state = SyncState(state_path)

    f = tmp_path / "session.jsonl"
    f.write_text('{"type": "user"}')

    state.mark_synced(f)
    state.save()

    # Load fresh
    state2 = SyncState(state_path)
    assert state2.is_changed(f) is False


def test_sync_state_detects_modification(tmp_path):
    state_path = tmp_path / ".sync_state.json"
    state = SyncState(state_path)

    f = tmp_path / "session.jsonl"
    f.write_text('{"type": "user"}')
    state.mark_synced(f)
    state.save()

    # Modify the file (change size)
    f.write_text('{"type": "user", "content": "modified"}')

    state2 = SyncState(state_path)
    assert state2.is_changed(f) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_archive.state'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_archive/state.py
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


class SyncState:
    def __init__(self, path: Path):
        self.path = path
        self.files: Dict[str, dict] = {}
        if path.exists():
            data = json.loads(path.read_text())
            self.files = data.get("files", {})

    def is_changed(self, filepath: Path) -> bool:
        key = str(filepath.resolve())
        if key not in self.files:
            return True
        stat = filepath.stat()
        entry = self.files[key]
        return entry["mtime"] != stat.st_mtime or entry["size"] != stat.st_size

    def mark_synced(self, filepath: Path) -> None:
        key = str(filepath.resolve())
        stat = filepath.stat()
        self.files[key] = {"mtime": stat.st_mtime, "size": stat.st_size}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "files": self.files,
        }
        self.path.write_text(json.dumps(data, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_state.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_archive/state.py tests/test_state.py
git commit -m "feat: add SyncState for incremental sync tracking"
```

---

### Task 4: Claude Code Parser

**Files:**
- Create: `src/agent_archive/parsers/claude_code.py`
- Create: `tests/fixtures/claude_code/test-project/test-session.jsonl`
- Create: `tests/test_claude_code_parser.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/claude_code/test-project/test-session.jsonl` with synthetic data (one line per JSON object, no trailing newline between objects):

```jsonl
{"type":"user","uuid":"u1","parentUuid":null,"timestamp":"2023-06-15T10:00:00.000Z","sessionId":"sess1","cwd":"/home/user/myproject","version":"2.1.0","slug":"test-session","message":{"role":"user","content":"Fix the bug in auth.py"}}
{"type":"assistant","uuid":"a1","parentUuid":"u1","timestamp":"2023-06-15T10:00:05.000Z","sessionId":"sess1","cwd":"/home/user/myproject","version":"2.1.0","slug":"test-session","message":{"role":"assistant","model":"claude-opus-4-6","content":[{"type":"text","text":"Let me look at the auth module."}],"usage":{"input_tokens":100,"output_tokens":50}}}
{"type":"assistant","uuid":"a2","parentUuid":"a1","timestamp":"2023-06-15T10:00:10.000Z","sessionId":"sess1","cwd":"/home/user/myproject","version":"2.1.0","slug":"test-session","message":{"role":"assistant","model":"claude-opus-4-6","content":[{"type":"tool_use","id":"toolu_1","name":"Read","input":{"file_path":"auth.py"}}],"usage":{"input_tokens":150,"output_tokens":30}}}
{"type":"user","uuid":"u2","parentUuid":"a2","timestamp":"2023-06-15T10:00:11.000Z","sessionId":"sess1","cwd":"/home/user/myproject","version":"2.1.0","slug":"test-session","sourceToolAssistantUUID":"a2","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_1","content":"def login():\n    pass"}]}}
{"type":"assistant","uuid":"a3","parentUuid":"u2","timestamp":"2023-06-15T10:00:20.000Z","sessionId":"sess1","cwd":"/home/user/myproject","version":"2.1.0","slug":"test-session","message":{"role":"assistant","model":"claude-opus-4-6","content":[{"type":"thinking","thinking":"The login function is empty."},{"type":"text","text":"I found the issue. The login function is empty."}],"usage":{"input_tokens":200,"output_tokens":80}}}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_claude_code_parser.py
from pathlib import Path
from agent_archive.parsers.claude_code import ClaudeCodeParser


FIXTURES = Path(__file__).parent / "fixtures" / "claude_code"


def test_discover(tmp_path):
    # Set up a fake claude dir structure
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

    # 5 lines in fixture: user, assistant(text), assistant(tool_use), user(tool_result), assistant(thinking+text)
    # We expect messages for: user, assistant, assistant(tool:Read), tool_result, assistant
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_claude_code_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_archive.parsers.claude_code'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/agent_archive/parsers/claude_code.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser


class ClaudeCodeParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".claude"

    def discover(self) -> List[Path]:
        projects_dir = self.base_path / "projects"
        if not projects_dir.exists():
            return []
        return sorted(projects_dir.glob("*/*.jsonl"))

    def parse(self, filepath: Path) -> List[Session]:
        messages: List[Message] = []
        slug = None
        model = None
        cwd = None
        session_id = None
        first_ts = None
        last_ts = None

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record_type = record.get("type")

                if record_type not in ("user", "assistant"):
                    continue

                ts_str = record.get("timestamp")
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
                if ts and first_ts is None:
                    first_ts = ts
                if ts:
                    last_ts = ts

                if slug is None:
                    slug = record.get("slug")
                if cwd is None:
                    cwd = record.get("cwd")
                if session_id is None:
                    session_id = record.get("sessionId")

                msg = record.get("message", {})
                role = msg.get("role", record_type)
                content = msg.get("content", "")

                if isinstance(content, str):
                    # Plain user message
                    messages.append(Message(role=role, content=content, timestamp=ts))
                elif isinstance(content, list):
                    if role == "user":
                        # Tool results
                        for block in content:
                            if block.get("type") == "tool_result":
                                messages.append(Message(
                                    role="tool_result",
                                    content=block.get("content", ""),
                                    timestamp=ts,
                                ))
                    elif role == "assistant":
                        # Assistant content blocks
                        msg_model = msg.get("model")
                        if msg_model and model is None:
                            model = msg_model
                        usage = msg.get("usage")
                        token_usage = None
                        if usage:
                            token_usage = {
                                "input": usage.get("input_tokens", 0),
                                "output": usage.get("output_tokens", 0),
                            }

                        text_parts = []
                        tool_name = None
                        for block in content:
                            btype = block.get("type")
                            if btype == "text":
                                text_parts.append(block.get("text", ""))
                            elif btype == "thinking":
                                text_parts.append(block.get("thinking", ""))
                            elif btype == "tool_use":
                                tool_name = block.get("name")
                                tool_input = block.get("input", {})
                                tool_desc = json.dumps(tool_input) if tool_input else ""
                                text_parts.append(tool_desc)

                        messages.append(Message(
                            role="assistant",
                            content="\n\n".join(text_parts) if text_parts else "",
                            timestamp=ts,
                            tool_name=tool_name,
                            token_usage=token_usage,
                        ))

        if not messages:
            return []

        session = Session(
            id=session_id or filepath.stem,
            agent_name="claude_code",
            title=slug or filepath.stem,
            start_time=first_ts or datetime.now(),
            end_time=last_ts,
            messages=messages,
            model=model,
            project_dir=cwd,
            source_path=str(filepath),
        )
        return [session]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_claude_code_parser.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/agent_archive/parsers/claude_code.py tests/test_claude_code_parser.py tests/fixtures/
git commit -m "feat: add Claude Code session parser"
```

---

### Task 5: Pi Parser

**Files:**
- Create: `src/agent_archive/parsers/pi.py`
- Create: `tests/fixtures/pi/test-project/2023-06-15T100000_abc123.jsonl`
- Create: `tests/test_pi_parser.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/pi/test-project/2023-06-15T100000_abc123.jsonl`:

```jsonl
{"type":"session","version":3,"id":"abc123","timestamp":"2023-06-15T10:00:00.000Z","cwd":"/home/user/myproject"}
{"type":"model_change","id":"m1","parentId":null,"timestamp":"2023-06-15T10:00:00.100Z","provider":"google-antigravity","modelId":"gemini-3.1-pro-high"}
{"type":"message","id":"msg1","parentId":"m1","timestamp":"2023-06-15T10:00:05.000Z","message":{"role":"user","content":[{"type":"text","text":"What files are in this directory?"}],"timestamp":1686822005000}}
{"type":"message","id":"msg2","parentId":"msg1","timestamp":"2023-06-15T10:00:10.000Z","message":{"role":"assistant","content":[{"type":"text","text":"Let me check the directory."},{"type":"toolCall","id":"tc1","name":"bash","arguments":{"command":"ls"}}],"provider":"google-antigravity","model":"gemini-3.1-pro-high","usage":{"input":500,"output":100,"cacheRead":0,"cacheWrite":0,"totalTokens":600,"cost":{"input":0.001,"output":0.0012,"total":0.0022}},"stopReason":"toolUse","timestamp":1686822010000}}
{"type":"message","id":"msg3","parentId":"msg2","timestamp":"2023-06-15T10:00:12.000Z","message":{"role":"toolResult","toolCallId":"tc1","toolName":"bash","content":[{"type":"text","text":"README.md\nsrc/\ntests/"}],"details":{},"isError":false,"timestamp":1686822012000}}
{"type":"message","id":"msg4","parentId":"msg3","timestamp":"2023-06-15T10:00:15.000Z","message":{"role":"assistant","content":[{"type":"text","text":"The directory contains README.md, src/, and tests/."}],"provider":"google-antigravity","model":"gemini-3.1-pro-high","usage":{"input":600,"output":50,"cacheRead":0,"cacheWrite":0,"totalTokens":650,"cost":{"input":0.0012,"output":0.0006,"total":0.0018}},"stopReason":"endTurn","timestamp":1686822015000}}
```

- [ ] **Step 2: Write the failing test**

```python
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

    # user, assistant(text+tool), toolResult, assistant(text)
    assert len(session.messages) == 4
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "What files are in this directory?"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].tool_name == "bash"
    assert session.messages[2].role == "tool_result"
    assert "README.md" in session.messages[2].content
    assert session.messages[3].role == "assistant"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_pi_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/agent_archive/parsers/pi.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser


class PiParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or (Path.home() / ".pi" / "agent")

    def discover(self) -> List[Path]:
        sessions_dir = self.base_path / "sessions"
        if not sessions_dir.exists():
            return []
        return sorted(sessions_dir.glob("*/*.jsonl"))

    def parse(self, filepath: Path) -> List[Session]:
        messages: List[Message] = []
        session_id = None
        cwd = None
        model = None
        first_ts = None
        last_ts = None

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record_type = record.get("type")

                if record_type == "session":
                    session_id = record.get("id")
                    cwd = record.get("cwd")
                    ts_str = record.get("timestamp")
                    if ts_str:
                        first_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    continue

                if record_type == "model_change":
                    if model is None:
                        model = record.get("modelId")
                    continue

                if record_type != "message":
                    continue

                ts_str = record.get("timestamp")
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
                if ts:
                    last_ts = ts
                    if first_ts is None:
                        first_ts = ts

                msg = record.get("message", {})
                role = msg.get("role", "")

                if role == "user":
                    content_blocks = msg.get("content", [])
                    text = "\n\n".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                    messages.append(Message(role="user", content=text, timestamp=ts))

                elif role == "assistant":
                    msg_model = msg.get("model")
                    if msg_model and model is None:
                        model = msg_model
                    usage = msg.get("usage")
                    token_usage = None
                    if usage:
                        token_usage = {"input": usage.get("input", 0), "output": usage.get("output", 0)}

                    content_blocks = msg.get("content", [])
                    text_parts = []
                    tool_name = None
                    for block in content_blocks:
                        btype = block.get("type")
                        if btype == "text":
                            text_parts.append(block.get("text", ""))
                        elif btype == "thinking":
                            text_parts.append(block.get("thinking", ""))
                        elif btype == "toolCall":
                            tool_name = block.get("name")
                            args = block.get("arguments", {})
                            text_parts.append(json.dumps(args) if args else "")

                    messages.append(Message(
                        role="assistant",
                        content="\n\n".join(text_parts) if text_parts else "",
                        timestamp=ts,
                        tool_name=tool_name,
                        token_usage=token_usage,
                    ))

                elif role == "toolResult":
                    content_blocks = msg.get("content", [])
                    text = "\n\n".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                    messages.append(Message(
                        role="tool_result",
                        content=text,
                        timestamp=ts,
                        tool_name=msg.get("toolName"),
                    ))

        if not messages:
            return []

        title = session_id or filepath.stem

        session = Session(
            id=session_id or filepath.stem,
            agent_name="pi",
            title=title,
            start_time=first_ts or datetime.now(),
            end_time=last_ts,
            messages=messages,
            model=model,
            project_dir=cwd,
            source_path=str(filepath),
        )
        return [session]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_pi_parser.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/agent_archive/parsers/pi.py tests/test_pi_parser.py tests/fixtures/pi/
git commit -m "feat: add pi agent session parser"
```

---

### Task 6: Opencode Parser

**Files:**
- Create: `src/agent_archive/parsers/opencode.py`
- Create: `tests/test_opencode_parser.py`
- Fixture: SQLite DB created in test via setup

- [ ] **Step 1: Write the failing test**

The fixture is a SQLite DB created programmatically in the test (no static file needed):

```python
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

    # user(text), assistant(text + tool)
    assert len(session.messages) == 3
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Fix the auth bug"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].content == "I'll look at the auth module."
    assert session.messages[2].role == "assistant"
    assert session.messages[2].tool_name == "bash"
    assert "def login" in session.messages[2].content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_opencode_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_archive/parsers/opencode.py
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser

DEFAULT_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


class OpencodeParser(BaseParser):
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB

    def discover(self) -> List[Path]:
        if self.db_path.exists():
            return [self.db_path]
        return []

    def parse(self, filepath: Path) -> List[Session]:
        conn = sqlite3.connect(filepath)
        conn.row_factory = sqlite3.Row
        sessions: List[Session] = []

        for row in conn.execute("SELECT * FROM session ORDER BY time_created"):
            session_id = row["id"]
            messages: List[Message] = []
            model = None

            for msg_row in conn.execute(
                "SELECT * FROM message WHERE session_id = ? ORDER BY time_created",
                (session_id,),
            ):
                msg_data = json.loads(msg_row["data"])
                role = msg_data.get("role", "user")
                ts_ms = msg_data.get("time", {}).get("created")
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) if ts_ms else None

                if model is None:
                    model_info = msg_data.get("model", {})
                    if isinstance(model_info, dict):
                        model = model_info.get("modelID")

                token_usage = None
                tokens = msg_data.get("tokens")
                if tokens:
                    token_usage = {"input": tokens.get("input", 0), "output": tokens.get("output", 0)}

                # Get parts for this message
                parts = conn.execute(
                    "SELECT * FROM part WHERE message_id = ? ORDER BY time_created",
                    (msg_row["id"],),
                ).fetchall()

                for part_row in parts:
                    part_data = json.loads(part_row["data"])
                    ptype = part_data.get("type")

                    if ptype == "text":
                        messages.append(Message(
                            role="user" if role == "user" else "assistant",
                            content=part_data.get("text", ""),
                            timestamp=ts,
                            token_usage=token_usage if role == "assistant" else None,
                        ))
                    elif ptype == "tool":
                        tool_name = part_data.get("tool", "")
                        state = part_data.get("state", {})
                        output = state.get("output", "")
                        inp = state.get("input", {})
                        desc = json.dumps(inp) if inp else ""
                        content = output if output else desc
                        messages.append(Message(
                            role="assistant",
                            content=content,
                            timestamp=ts,
                            tool_name=tool_name,
                        ))
                    elif ptype == "reasoning":
                        # Skip reasoning parts for now, they are internal
                        pass

            if not messages:
                continue

            start_ts = datetime.fromtimestamp(row["time_created"] / 1000, tz=timezone.utc)
            end_ts = datetime.fromtimestamp(row["time_updated"] / 1000, tz=timezone.utc)

            sessions.append(Session(
                id=session_id,
                agent_name="opencode",
                title=row["title"],
                start_time=start_ts,
                end_time=end_ts,
                messages=messages,
                model=model,
                project_dir=row["directory"],
                source_path=str(filepath),
            ))

        conn.close()
        return sessions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_opencode_parser.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_archive/parsers/opencode.py tests/test_opencode_parser.py
git commit -m "feat: add opencode session parser (SQLite)"
```

---

### Task 7: Copilot Parser

**Files:**
- Create: `src/agent_archive/parsers/copilot.py`
- Create: `tests/fixtures/copilot/test-session/events.jsonl`
- Create: `tests/fixtures/copilot/test-session/workspace.yaml`
- Create: `tests/test_copilot_parser.py`

- [ ] **Step 1: Create test fixtures**

Create `tests/fixtures/copilot/test-session/workspace.yaml`:

```yaml
id: test-session-uuid
cwd: /home/user/myproject
git_root: /home/user/myproject
repository: user/myproject
host_type: github
branch: main
summary: Fix authentication
created_at: 2023-06-15T10:00:00.000Z
updated_at: 2023-06-15T10:01:00.000Z
```

Create `tests/fixtures/copilot/test-session/events.jsonl`:

```jsonl
{"type":"session.start","data":{"sessionId":"test-session-uuid","version":1,"producer":"copilot-agent","copilotVersion":"1.0.25","startTime":"2023-06-15T10:00:00.000Z","context":{"cwd":"/home/user/myproject","gitRoot":"/home/user/myproject","branch":"main","repository":"user/myproject","hostType":"github"}},"id":"evt1","timestamp":"2023-06-15T10:00:00.100Z","parentId":null}
{"type":"session.model_change","data":{"newModel":"claude-sonnet-4.6"},"id":"evt2","timestamp":"2023-06-15T10:00:00.200Z","parentId":"evt1"}
{"type":"user.message","data":{"content":"Fix the auth bug","transformedContent":"<datetime>...</datetime>\nFix the auth bug","attachments":[],"interactionId":"int1"},"id":"evt3","timestamp":"2023-06-15T10:00:05.000Z","parentId":"evt2"}
{"type":"assistant.turn_start","data":{"turnId":"turn1","interactionId":"int1"},"id":"evt4","timestamp":"2023-06-15T10:00:06.000Z","parentId":"evt3"}
{"type":"assistant.message","data":{"messageId":"msg1","content":"","toolRequests":[{"toolCallId":"tc1","name":"bash","arguments":{"command":"cat auth.py"},"type":"function"}],"interactionId":"int1","reasoningText":"I need to look at auth.py","outputTokens":50,"requestId":"req1"},"id":"evt5","timestamp":"2023-06-15T10:00:08.000Z","parentId":"evt4"}
{"type":"tool.execution_complete","data":{"toolCallId":"tc1","success":true,"result":{"content":"def login(): pass"}},"id":"evt6","timestamp":"2023-06-15T10:00:10.000Z","parentId":"evt5"}
{"type":"assistant.message","data":{"messageId":"msg2","content":"I found the issue. The login function is empty.","toolRequests":[],"interactionId":"int1","outputTokens":30,"requestId":"req2"},"id":"evt7","timestamp":"2023-06-15T10:00:15.000Z","parentId":"evt6"}
{"type":"assistant.turn_end","data":{"turnId":"turn1"},"id":"evt8","timestamp":"2023-06-15T10:00:16.000Z","parentId":"evt7"}
```

- [ ] **Step 2: Write the failing test**

```python
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
    # Session without events.jsonl should be skipped
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

    # user, assistant(tool:bash), tool_result, assistant(text)
    assert len(session.messages) == 4
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Fix the auth bug"
    assert session.messages[1].role == "assistant"
    assert session.messages[1].tool_name == "bash"
    assert session.messages[2].role == "tool_result"
    assert "def login" in session.messages[2].content
    assert session.messages[3].role == "assistant"
    assert "login function is empty" in session.messages[3].content
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_copilot_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

Add `pyyaml>=6.0` to `pyproject.toml` dependencies (needed for workspace.yaml parsing):

In `pyproject.toml`, add `"pyyaml>=6.0"` to the `dependencies` list.

```python
# src/agent_archive/parsers/copilot.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from ..models import Message, Session
from .base import BaseParser


class CopilotParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or (Path.home() / ".copilot")

    def discover(self) -> List[Path]:
        state_dir = self.base_path / "session-state"
        if not state_dir.exists():
            return []
        results = []
        for session_dir in sorted(state_dir.iterdir()):
            events_file = session_dir / "events.jsonl"
            if events_file.exists():
                results.append(events_file)
        return results

    def parse(self, filepath: Path) -> List[Session]:
        session_dir = filepath.parent
        messages: List[Message] = []
        session_id = None
        model = None
        cwd = None
        title = None
        first_ts = None
        last_ts = None

        # Read workspace.yaml for title
        workspace_file = session_dir / "workspace.yaml"
        if workspace_file.exists():
            ws = yaml.safe_load(workspace_file.read_text())
            title = ws.get("summary")
            session_id = ws.get("id")
            cwd = ws.get("cwd")

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                etype = event.get("type")
                data = event.get("data", {})
                ts_str = event.get("timestamp")
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
                if ts and first_ts is None:
                    first_ts = ts
                if ts:
                    last_ts = ts

                if etype == "session.start":
                    if session_id is None:
                        session_id = data.get("sessionId")
                    ctx = data.get("context", {})
                    if cwd is None:
                        cwd = ctx.get("cwd")

                elif etype == "session.model_change":
                    if model is None:
                        model = data.get("newModel")

                elif etype == "user.message":
                    content = data.get("content", "")
                    messages.append(Message(role="user", content=content, timestamp=ts))

                elif etype == "assistant.message":
                    content = data.get("content", "")
                    tool_requests = data.get("toolRequests", [])
                    output_tokens = data.get("outputTokens")
                    token_usage = {"input": 0, "output": output_tokens} if output_tokens else None

                    if tool_requests:
                        for tr in tool_requests:
                            tool_name = tr.get("name", "")
                            args = tr.get("arguments", {})
                            desc = json.dumps(args) if args else ""
                            messages.append(Message(
                                role="assistant",
                                content=desc,
                                timestamp=ts,
                                tool_name=tool_name,
                                token_usage=token_usage,
                            ))
                    elif content:
                        messages.append(Message(
                            role="assistant",
                            content=content,
                            timestamp=ts,
                            token_usage=token_usage,
                        ))

                elif etype == "tool.execution_complete":
                    result = data.get("result", {})
                    result_content = result.get("content", "")
                    if isinstance(result_content, list):
                        result_content = "\n".join(
                            item.get("text", str(item)) for item in result_content
                        )
                    messages.append(Message(
                        role="tool_result",
                        content=str(result_content),
                        timestamp=ts,
                    ))

        if not messages:
            return []

        session = Session(
            id=session_id or filepath.parent.name,
            agent_name="copilot",
            title=title or session_id or filepath.parent.name,
            start_time=first_ts or datetime.now(),
            end_time=last_ts,
            messages=messages,
            model=model,
            project_dir=cwd,
            source_path=str(filepath),
        )
        return [session]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_copilot_parser.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/agent_archive/parsers/copilot.py tests/test_copilot_parser.py tests/fixtures/copilot/ pyproject.toml
git commit -m "feat: add GitHub Copilot session parser"
```

---

### Task 8: Markdown Renderer

**Files:**
- Create: `src/agent_archive/renderer.py`
- Create: `tests/test_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
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

    # Session file
    session_file = tmp_path / "docs" / "2023-06" / "claude_code" / "sess1.md"
    assert session_file.exists()
    content = session_file.read_text()
    assert "Fix auth bug" in content

    # Month index
    month_index = tmp_path / "docs" / "2023-06" / "index.md"
    assert month_index.exists()
    assert "claude_code" in month_index.read_text().lower()

    # Homepage
    homepage = tmp_path / "docs" / "index.md"
    assert homepage.exists()
    assert "Fix auth bug" in homepage.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_renderer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_archive/renderer.py
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .models import Session


AGENT_DISPLAY = {
    "claude_code": "Claude Code",
    "pi": "Pi",
    "opencode": "OpenCode",
    "copilot": "Copilot",
}


class MarkdownRenderer:
    def render_session(self, session: Session) -> str:
        lines = []

        # Frontmatter
        total_input = sum(m.token_usage.get("input", 0) for m in session.messages if m.token_usage)
        total_output = sum(m.token_usage.get("output", 0) for m in session.messages if m.token_usage)

        lines.append("---")
        lines.append(f'title: "{session.title}"')
        lines.append(f"agent: {session.agent_name}")
        if session.model:
            lines.append(f"model: {session.model}")
        lines.append(f"date: {session.start_time.strftime('%Y-%m-%d')}")
        if total_input or total_output:
            lines.append(f"tokens: {{input: {total_input}, output: {total_output}}}")
        if session.project_dir:
            lines.append(f"project: {session.project_dir}")
        lines.append("---")
        lines.append("")

        # Header
        display_name = AGENT_DISPLAY.get(session.agent_name, session.agent_name)
        lines.append(f"# {session.title}")
        lines.append("")
        header_parts = [f"**Agent:** {display_name}"]
        if session.model:
            header_parts.append(f"**Model:** {session.model}")
        if session.end_time and session.start_time:
            duration = session.end_time - session.start_time
            minutes = int(duration.total_seconds() / 60)
            if minutes > 0:
                header_parts.append(f"**Duration:** {minutes}m")
        lines.append(" | ".join(header_parts))
        if session.project_dir:
            lines.append(f"**Project:** {session.project_dir}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Messages
        for msg in session.messages:
            ts_str = msg.timestamp.strftime("%H:%M") if msg.timestamp else ""

            if msg.role == "user":
                lines.append(f"**User** ({ts_str})")
                lines.append(f"> {msg.content}")
            elif msg.role == "assistant":
                if msg.tool_name:
                    lines.append(f"**Assistant** [tool: {msg.tool_name}] ({ts_str})")
                else:
                    lines.append(f"**Assistant** ({ts_str})")
                lines.append(msg.content)
            elif msg.role == "tool_result":
                lines.append(f"**Tool Result** ({ts_str})")
                lines.append(f"```\n{msg.content}\n```")

            lines.append("")

        return "\n".join(lines)

    def render_month_index(self, month: str, sessions: List[Session]) -> str:
        lines = []
        lines.append(f"# Sessions — {month}")
        lines.append("")

        by_agent: Dict[str, List[Session]] = defaultdict(list)
        for s in sessions:
            by_agent[s.agent_name].append(s)

        for agent_name in sorted(by_agent):
            display = AGENT_DISPLAY.get(agent_name, agent_name)
            lines.append(f"## {display}")
            lines.append("")
            lines.append("| Session | Date | Model | Tokens |")
            lines.append("|---------|------|-------|--------|")
            for s in sorted(by_agent[agent_name], key=lambda x: x.start_time):
                date = s.start_time.strftime("%Y-%m-%d %H:%M")
                model = s.model or "—"
                total_in = sum(m.token_usage.get("input", 0) for m in s.messages if m.token_usage)
                total_out = sum(m.token_usage.get("output", 0) for m in s.messages if m.token_usage)
                tokens = f"{total_in}/{total_out}" if total_in or total_out else "—"
                link = f"[{s.title}]({s.agent_name}/{s.id}.md)"
                lines.append(f"| {link} | {date} | {model} | {tokens} |")
            lines.append("")

        return "\n".join(lines)

    def render_homepage(self, sessions: List[Session]) -> str:
        lines = []
        lines.append("# Agent Archive")
        lines.append("")

        agents = set(s.agent_name for s in sessions)
        lines.append(f"**{len(sessions)} sessions** from **{len(agents)} agents**")
        lines.append("")
        lines.append("## Recent Sessions")
        lines.append("")
        lines.append("| Session | Agent | Date | Model |")
        lines.append("|---------|-------|------|-------|")

        recent = sorted(sessions, key=lambda s: s.start_time, reverse=True)[:20]
        for s in recent:
            display = AGENT_DISPLAY.get(s.agent_name, s.agent_name)
            date = s.start_time.strftime("%Y-%m-%d %H:%M")
            model = s.model or "—"
            month = s.start_time.strftime("%Y-%m")
            link = f"[{s.title}]({month}/{s.agent_name}/{s.id}.md)"
            lines.append(f"| {link} | {display} | {date} | {model} |")

        lines.append("")
        return "\n".join(lines)

    def render_all(self, sessions: List[Session], output_dir: Path) -> None:
        docs_dir = output_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        by_month: Dict[str, List[Session]] = defaultdict(list)

        for session in sessions:
            month = session.start_time.strftime("%Y-%m")
            by_month[month].append(session)

            session_dir = docs_dir / month / session.agent_name
            session_dir.mkdir(parents=True, exist_ok=True)
            session_file = session_dir / f"{session.id}.md"
            session_file.write_text(self.render_session(session))

        # Month indexes
        for month, month_sessions in by_month.items():
            index_file = docs_dir / month / "index.md"
            index_file.write_text(self.render_month_index(month, month_sessions))

        # Homepage
        homepage = docs_dir / "index.md"
        homepage.write_text(self.render_homepage(sessions))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_renderer.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_archive/renderer.py tests/test_renderer.py
git commit -m "feat: add Markdown renderer with session pages and indexes"
```

---

### Task 9: Site Builder

**Files:**
- Create: `src/agent_archive/site_builder.py`
- Create: `tests/test_site_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_site_builder.py
import yaml
from pathlib import Path
from unittest.mock import patch
from agent_archive.site_builder import SiteBuilder


def test_generate_mkdocs_yml(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home")
    month_dir = docs_dir / "2023-06"
    month_dir.mkdir()
    (month_dir / "index.md").write_text("# June")
    agent_dir = month_dir / "claude_code"
    agent_dir.mkdir()
    (agent_dir / "sess1.md").write_text("# Session")

    builder = SiteBuilder(tmp_path)
    builder.generate_config()

    config_path = tmp_path / "mkdocs.yml"
    assert config_path.exists()

    config = yaml.safe_load(config_path.read_text())
    assert config["site_name"] == "Agent Archive"
    assert config["theme"]["name"] == "material"
    assert "search" in str(config.get("plugins", []))


def test_build_site(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home")

    builder = SiteBuilder(tmp_path)
    builder.generate_config()

    with patch("agent_archive.site_builder.subprocess.run") as mock_run:
        mock_run.return_value = None
        builder.build()
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert "mkdocs" in args[0][0]
        assert "build" in args[0][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_site_builder.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_archive/site_builder.py
import subprocess
from pathlib import Path

import yaml


class SiteBuilder:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.docs_dir = output_dir / "docs"
        self.config_path = output_dir / "mkdocs.yml"

    def generate_config(self) -> None:
        nav = self._build_nav()

        config = {
            "site_name": "Agent Archive",
            "docs_dir": str(self.docs_dir),
            "site_dir": str(self.output_dir / "site"),
            "theme": {
                "name": "material",
                "features": [
                    "search.suggest",
                    "search.highlight",
                    "navigation.sections",
                ],
            },
            "plugins": ["search"],
        }
        if nav:
            config["nav"] = nav

        self.config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    def _build_nav(self) -> list:
        nav = []
        if not self.docs_dir.exists():
            return nav

        nav.append({"Home": "index.md"})

        months = sorted(
            [d for d in self.docs_dir.iterdir() if d.is_dir() and d.name != "site"],
            reverse=True,
        )
        for month_dir in months:
            month_items = [{"Overview": f"{month_dir.name}/index.md"}]
            for agent_dir in sorted(month_dir.iterdir()):
                if agent_dir.is_dir():
                    for session_file in sorted(agent_dir.glob("*.md")):
                        label = session_file.stem
                        month_items.append(
                            {label: f"{month_dir.name}/{agent_dir.name}/{session_file.name}"}
                        )
            nav.append({month_dir.name: month_items})

        return nav

    def build(self) -> None:
        subprocess.run(
            f"mkdocs build -f {self.config_path}",
            shell=True,
            check=True,
            cwd=self.output_dir,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_site_builder.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_archive/site_builder.py tests/test_site_builder.py
git commit -m "feat: add SiteBuilder for mkdocs config generation and build"
```

---

### Task 10: Wire Up the sync Command

**Files:**
- Modify: `src/agent_archive/cli.py`
- Create: `tests/test_sync_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync_integration.py
import json
from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner
from agent_archive.cli import app


runner = CliRunner()


def test_sync_creates_markdown(tmp_path):
    # Create a fake Claude Code session fixture
    claude_dir = tmp_path / "claude" / "projects" / "test-project"
    claude_dir.mkdir(parents=True)
    fixture = claude_dir / "session1.jsonl"
    fixture.write_text("\n".join([
        json.dumps({"type": "user", "uuid": "u1", "parentUuid": None, "timestamp": "2023-06-15T10:00:00.000Z", "sessionId": "s1", "cwd": "/tmp/proj", "slug": "test-sess", "message": {"role": "user", "content": "Hello"}}),
        json.dumps({"type": "assistant", "uuid": "a1", "parentUuid": "u1", "timestamp": "2023-06-15T10:00:05.000Z", "sessionId": "s1", "cwd": "/tmp/proj", "slug": "test-sess", "message": {"role": "assistant", "model": "claude-opus-4-6", "content": [{"type": "text", "text": "Hi there!"}], "usage": {"input_tokens": 10, "output_tokens": 5}}}),
    ]))

    output_dir = tmp_path / "output"

    with patch("agent_archive.cli.SiteBuilder.build"):
        result = runner.invoke(app, [
            "sync",
            "--output", str(output_dir),
            "--claude-path", str(tmp_path / "claude"),
            "--pi-path", str(tmp_path / "pi"),
            "--opencode-db", str(tmp_path / "opencode.db"),
            "--copilot-path", str(tmp_path / "copilot"),
        ])

    assert result.exit_code == 0, result.output

    # Check Markdown was generated
    session_files = list((output_dir / "docs").rglob("*.md"))
    assert len(session_files) >= 2  # at least session page + index

    # Check sync state was saved
    state_file = output_dir / ".sync_state.json"
    assert state_file.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_sync_integration.py -v`
Expected: FAIL — the current `sync` command just prints a message.

- [ ] **Step 3: Write minimal implementation**

Replace `src/agent_archive/cli.py` with:

```python
# src/agent_archive/cli.py
import typer
from pathlib import Path
from typing import Optional

from .parsers.claude_code import ClaudeCodeParser
from .parsers.pi import PiParser
from .parsers.opencode import OpencodeParser
from .parsers.copilot import CopilotParser
from .renderer import MarkdownRenderer
from .site_builder import SiteBuilder
from .state import SyncState

app = typer.Typer()


@app.callback()
def main():
    """Archive and browse agentic coding sessions."""


@app.command()
def sync(
    output: Path = typer.Option(..., help="Output directory for the markdown files and static site"),
    claude_path: Optional[Path] = typer.Option(None, help="Override Claude Code log directory"),
    pi_path: Optional[Path] = typer.Option(None, help="Override pi agent log directory"),
    opencode_db: Optional[Path] = typer.Option(None, help="Override opencode database path"),
    copilot_path: Optional[Path] = typer.Option(None, help="Override copilot log directory"),
):
    """Sync agent logs and build MkDocs site."""
    output.mkdir(parents=True, exist_ok=True)

    state = SyncState(output / ".sync_state.json")

    parsers = [
        ClaudeCodeParser(base_path=claude_path),
        PiParser(base_path=pi_path),
        OpencodeParser(db_path=opencode_db),
        CopilotParser(base_path=copilot_path),
    ]

    all_sessions = []

    for parser in parsers:
        files = parser.discover()
        for filepath in files:
            if not state.is_changed(filepath):
                continue
            try:
                sessions = parser.parse(filepath)
                all_sessions.extend(sessions)
                state.mark_synced(filepath)
            except Exception as e:
                typer.echo(f"Warning: failed to parse {filepath}: {e}", err=True)

    if all_sessions:
        typer.echo(f"Parsed {len(all_sessions)} sessions")
        renderer = MarkdownRenderer()
        renderer.render_all(all_sessions, output)
        typer.echo("Rendered Markdown files")
    else:
        typer.echo("No new sessions to sync")

    builder = SiteBuilder(output)
    builder.generate_config()
    builder.build()
    typer.echo("Site built successfully")

    state.save()


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_sync_integration.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH=src pytest tests/ -v`
Expected: All tests pass. The old `test_cli.py::test_sync_command_help` should still pass because the sync command still has an `--output` option.

- [ ] **Step 6: Commit**

```bash
git add src/agent_archive/cli.py tests/test_sync_integration.py
git commit -m "feat: wire up sync command with full pipeline"
```

---

### Task 11: Add pyyaml Dependency

**Files:**
- Modify: `pyproject.toml`

Note: This is needed by both the copilot parser (workspace.yaml) and site_builder (mkdocs.yml). It should be done before Task 7 in practice, but is listed separately for clarity. The worker should add this early — when implementing Task 7 or Task 9, whichever comes first.

- [ ] **Step 1: Add pyyaml to dependencies**

In `pyproject.toml`, add `"pyyaml>=6.0"` to the `dependencies` list:

```toml
dependencies = [
    "typer>=0.12.0",
    "pydantic>=2.7.0",
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.5.0",
    "pyyaml>=6.0"
]
```

- [ ] **Step 2: Install in venv**

Run: `source /Users/smitra/Shared/Projects/opensource/venv/bin/activate && pip install -e ".[dev]"`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyyaml dependency"
```
