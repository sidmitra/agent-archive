# Agent Archive

Archive and browse agentic coding sessions. Parses agent session logs and generates a searchable MkDocs static site.

## Requirements

- Python 3.10+

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Usage

```bash
agent-archive sync --output ./site
```

This parses agent logs and generates Markdown files and an MkDocs site in the specified output directory.

## Development

Run tests:

```bash
PYTHONPATH=src pytest tests/ -v
```

## Project Structure

```
src/agent_archive/
  __init__.py
  cli.py              # Typer CLI entry point
  models.py            # Pydantic models (Session, Message)
  parsers/
    base.py            # Abstract BaseParser for plugin-style log parsers
```

## Adding a Parser

Subclass `BaseParser` to support a new agent log format:

```python
from pathlib import Path
from agent_archive.parsers.base import BaseParser
from agent_archive.models import Session

class MyAgentParser(BaseParser):
    def parse(self, filepath: Path) -> list[Session]:
        # Parse your agent's log format and return Session objects
        ...
```
