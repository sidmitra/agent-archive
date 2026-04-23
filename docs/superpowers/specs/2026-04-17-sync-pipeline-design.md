# Sync Pipeline Design

## Overview

Build out the `agent-archive sync` command to parse session logs from four coding agents (Claude Code, pi, opencode, copilot), render them as Markdown, and generate a searchable MkDocs static site with incremental sync support.

## Architecture & Data Flow

The `sync` command runs a four-stage pipeline:

```
discover → parse → render → build
```

1. **Discover**: Each parser knows its agent's default log location. It scans for session files and checks `.sync_state.json` to skip unchanged ones (by file mtime and size).
2. **Parse**: Each parser reads its format (JSONL for Claude Code/pi/copilot, SQLite for opencode) and returns `List[Session]`.
3. **Render**: A `MarkdownRenderer` writes each `Session` as a Markdown file with YAML frontmatter and full conversation transcript. Index pages provide summaries.
4. **Build**: A `SiteBuilder` generates `mkdocs.yml` and runs `mkdocs build` to produce the static HTML site.

After a successful sync, `.sync_state.json` is updated with the latest mtimes.

## Data Models

Extend the existing Pydantic models:

```python
class Message(BaseModel):
    role: str              # "user", "assistant", "system", "tool_result"
    content: str           # rendered text content
    timestamp: Optional[datetime] = None
    tool_name: Optional[str] = None      # e.g. "bash", "edit", "read"
    token_usage: Optional[dict] = None   # {"input": N, "output": N}

class Session(BaseModel):
    id: str
    agent_name: str        # "claude_code", "pi", "opencode", "copilot"
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    messages: List[Message]
    model: Optional[str] = None          # primary model used
    project_dir: Optional[str] = None    # working directory
    source_path: str                     # original log file path
```

Key decisions:
- `content` is always pre-rendered to plain text during parsing — thinking blocks, tool calls, and tool results are flattened to readable strings.
- `source_path` tracks where the session came from, needed for incremental sync.
- Tool calls become messages with `role="assistant"` and `tool_name` set; tool results become `role="tool_result"`.

## Parsers

Each parser subclasses `BaseParser` and implements two methods:

```python
class BaseParser(ABC):
    @abstractmethod
    def discover(self) -> List[Path]:
        """Return all session log file paths for this agent."""

    @abstractmethod
    def parse(self, filepath: Path) -> List[Session]:
        """Parse a single log file into Session objects."""
```

### ClaudeCodeParser

- Scans `~/.claude/projects/*/` for `*.jsonl` files. Each file is one session.
- Extracts messages from records with `type: "user"` or `type: "assistant"`.
- Flattens `content` arrays (thinking, text, tool_use blocks) into readable text.
- Pulls `slug` for title, `model` from assistant messages, project dir from `cwd`.

### PiParser

- Scans `~/.pi/agent/sessions/*/` for `*.jsonl` files. Each file is one session.
- First line (`type: "session"`) has metadata.
- Message records have `type: "message"` with role in `message.role`.

### OpencodeParser

- Opens `~/.local/share/opencode/opencode.db` via sqlite3 (stdlib).
- Queries `session` → `message` → `part` tables.
- Each session row becomes a `Session`. Parts are assembled per-message.

### CopilotParser

- Scans `~/.copilot/session-state/*/events.jsonl`.
- Session metadata from `session.start` event.
- Messages from `user.message` and `assistant.message` events.
- Reads `workspace.yaml` for title/project info.

Each parser has a hardcoded default path but accepts an override for testing.

## Markdown Rendering & Site Structure

### File structure

```
<output>/
  docs/
    index.md                              # Homepage with stats + recent sessions
    2026-04/
      index.md                            # Month summary grouped by agent
      claude_code/
        <session_id>.md                   # Full transcript
      pi/
        <session_id>.md
      opencode/
        <session_id>.md
      copilot/
        <session_id>.md
  mkdocs.yml                              # Auto-generated
  site/                                    # Built HTML output
```

### Session page format

```markdown
---
title: "fix auth middleware"
agent: claude_code
model: claude-opus-4-6
date: 2026-04-15
tokens: {input: 12000, output: 3400}
project: /Users/smitra/myproject
---

# fix auth middleware

**Agent:** Claude Code | **Model:** claude-opus-4-6 | **Duration:** 12m
**Project:** /Users/smitra/myproject

---

**User** (12:01)
> Fix the auth middleware bug

**Assistant** (12:01)
Let me look at the auth middleware.

**Assistant** [tool: read] (12:01)
Reading `src/auth.py`...

**User** [tool_result] (12:01)
<file contents>
```

### Index pages

- **Homepage**: Total sessions/agents, 20 most recent sessions.
- **Month index**: All sessions for that month grouped by agent, showing title, timestamp, model, and token count.

### MkDocs config

Auto-generated `mkdocs.yml` with material theme, search plugin, and nav built from the directory structure.

## Incremental Sync

`.sync_state.json` lives in the output directory root:

```json
{
  "version": 1,
  "last_sync": "2026-04-17T10:30:00Z",
  "files": {
    "/path/to/session.jsonl": {
      "mtime": 1776444132.859,
      "size": 45230
    }
  }
}
```

### Flow

1. Each parser calls `discover()` to get all session file paths.
2. For each file, check `.sync_state.json` — if mtime and size match, skip it.
3. Parse only new/changed files.
4. After rendering, update `.sync_state.json` with current mtime/size for all processed files.

### Edge cases

- **Opencode (SQLite)**: Track the DB's mtime/size as a single entry. If changed, re-query all sessions and compare session IDs + `time_updated` against already-rendered pages. Only re-render changed sessions.
- **Deleted source files**: Not handled. Old rendered pages stay. A future `--clean` flag could prune them.

## Testing Strategy

### Unit tests per component

- **Parsers**: Each parser gets a test with a small fixture file (a few JSONL lines or a test SQLite DB). Tests verify that `discover()` finds files and `parse()` returns correct `Session` objects with expected fields.
- **Renderer**: Test that a `Session` object produces the expected Markdown string — frontmatter, headings, message formatting.
- **SiteBuilder**: Test that `mkdocs.yml` generation produces valid YAML with correct nav structure. Mock the actual `mkdocs build` call.
- **SyncState**: Test load/save of `.sync_state.json`, skip logic for unchanged files, detection of changed files.

### Integration test

One end-to-end test: fixture logs for all four agents → `sync` command → verify Markdown files exist with correct structure and content.

### Fixtures

- `tests/fixtures/claude_code/` — 1-2 small JSONL session files
- `tests/fixtures/pi/` — 1 small JSONL session file
- `tests/fixtures/opencode/` — a test SQLite DB with a couple sessions
- `tests/fixtures/copilot/` — 1 events.jsonl + workspace.yaml

All fixture data is anonymized/synthetic, not copied from real sessions.

## Project Files

```
src/agent_archive/
  __init__.py              # existing
  cli.py                   # extend sync command
  models.py                # extend Message, Session
  state.py                 # NEW: SyncState load/save/check
  renderer.py              # NEW: MarkdownRenderer
  site_builder.py          # NEW: mkdocs.yml generation + build
  parsers/
    __init__.py            # existing
    base.py                # extend with discover()
    claude_code.py         # NEW
    pi.py                  # NEW
    opencode.py            # NEW
    copilot.py             # NEW
```
