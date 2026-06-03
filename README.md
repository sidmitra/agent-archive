# Agent Archive

Archive and browse agentic coding sessions. Parses session logs from multiple agents and generates a searchable MkDocs static site.

![Agent Archive screenshot](screenshot.jpg)

**Supported agents:** Claude Code, Gemini CLI, Pi, OpenCode, GitHub Copilot

## Requirements

- Python 3.10+

## Installation

Install as a standalone CLI with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install agent-archive
```

Or with pip:

```bash
pip install agent-archive
```

For development (from a local clone):

```bash
uv sync
```

## Usage

### Quick start

The `run` command syncs, builds, and serves the archive in one step:

```bash
agent-archive run --output ~/ai-sessions
```

This is equivalent to running `sync`, `build`, and `serve` in sequence. It accepts all the same flags as the individual commands:

```bash
agent-archive run --output ~/ai-sessions \
  --claude-path ~/.claude \
  --pi-path ~/.pi/agent \
  --opencode-db ~/.local/share/opencode/opencode.db \
  --gemini-path ~/.gemini/tmp \
  --copilot-path ~/.copilot \
  --port 9000 \
  --no-browser
```

### Individual commands

Use the individual commands when you need more control — for example, to sync on one machine and serve on another, or to rebuild without re-syncing.

#### Sync

Parse agent logs and write Markdown files into `<output>/docs`:

```bash
agent-archive sync --output ~/ai-sessions
```

Agent log directories are auto-discovered at their default locations. Override any of them:

```bash
agent-archive sync --output ~/ai-sessions \
  --claude-path ~/.claude \
  --pi-path ~/.pi/agent \
  --opencode-db ~/.local/share/opencode/opencode.db \
  --gemini-path ~/.gemini/tmp \
  --copilot-path ~/.copilot
```

Only sessions that have changed since the last sync are re-parsed (incremental).

**Secret redaction** is on by default — API keys, tokens, and env var values are replaced with `REDACTED` in the rendered output. To disable:

```bash
agent-archive sync --output ~/ai-sessions --no-redact
```

#### Build

Generate the MkDocs config and build the static HTML site into `<output>/site`:

```bash
agent-archive build --output ~/ai-sessions
```

#### Serve

Start a local HTTP server and open the archive in a browser:

```bash
agent-archive serve --output ~/ai-sessions
```

A local server is required because the site uses JavaScript for search. Default port is 8000.

```bash
agent-archive serve --output ~/ai-sessions --port 9000 --no-browser
```

## Sharing across multiple machines

You can point all your machines at the same output directory synced via Dropbox, Syncthing, or similar. Each machine maintains its own `.sync_state.<hostname>.json` file in the output directory so they never interfere with each other.

On each machine, run sync independently:

```bash
agent-archive sync --output ~/Dropbox/ai-sessions
```

Sessions from all machines accumulate in the shared archive. To browse from any machine, build and serve:

```bash
agent-archive build --output ~/Dropbox/ai-sessions
agent-archive serve --output ~/Dropbox/ai-sessions
```

Or use the shortcut:

```bash
agent-archive run --output ~/Dropbox/ai-sessions
```

## Development

Run tests:

```bash
uv run pytest
```

## Project Structure

```
src/agent_archive/
  cli.py              # Typer CLI (run, sync, build, serve)
  models.py           # Pydantic models (Session, Message)
  redactor.py         # Secret redaction
  renderer.py         # Markdown + MkDocs site generation
  site_builder.py     # mkdocs.yml config and build
  state.py            # Incremental sync state (per-machine)
  parsers/
    base.py           # Abstract BaseParser
    claude_code.py
    gemini.py
    pi.py
    opencode.py
    copilot.py
```

## Adding a Parser

Subclass `BaseParser` to support a new agent log format:

```python
from pathlib import Path
from agent_archive.parsers.base import BaseParser
from agent_archive.models import Session

class MyAgentParser(BaseParser):
    def discover(self) -> list[Path]:
        # Return all log file paths for this agent
        ...

    def parse(self, filepath: Path) -> list[Session]:
        # Parse the log file and return Session objects
        ...
```
