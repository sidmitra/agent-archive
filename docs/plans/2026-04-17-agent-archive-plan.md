# Agent Archive Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Build a Python CLI tool that parses coding agent session logs and generates an MkDocs static site.

**Architecture:** A modular Python CLI with Pydantic for data validation, Typer for CLI interface, and a plugin-style base parser for different agent log formats. Output is standard Markdown and a generated MkDocs site.

**Tech Stack:** Python 3.10+, Typer, Pydantic, Pytest, MkDocs, MkDocs-Material.

---

### Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/agent_archive/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Write the failing test (Verifying import)**

```python
import sys
# Try to import agent_archive - this will fail if not set up
import agent_archive
```

**Step 2: Run test to verify it fails**

Run: `python -c "import agent_archive"`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `pyproject.toml`:
```toml
[project]
name = "agent-archive"
version = "0.1.0"
description = "Archive and browse agentic coding sessions"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12.0",
    "pydantic>=2.7.0",
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.5.0"
]

[project.scripts]
agent-archive = "agent_archive.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0"
]
```

Create `src/agent_archive/__init__.py`:
```python
# Initialize agent_archive package
```

Create `tests/__init__.py`:
```python
# Initialize tests
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -c "import agent_archive"`
Expected: PASS (no output)

**Step 5: Commit**

```bash
git add pyproject.toml src/agent_archive/__init__.py tests/__init__.py
git commit -m "chore: setup initial python project structure"
```

### Task 2: Data Models

**Files:**
- Create: `src/agent_archive/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

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
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError" or similar.

**Step 3: Write minimal implementation**

```python
# src/agent_archive/models.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None

class Session(BaseModel):
    id: str
    agent_name: str
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    messages: List[Message]
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/agent_archive/models.py tests/test_models.py
git commit -m "feat: add pydantic models for sessions and messages"
```

### Task 3: Base Parser

**Files:**
- Create: `src/agent_archive/parsers/base.py`
- Create: `src/agent_archive/parsers/__init__.py`
- Create: `tests/test_base_parser.py`

**Step 1: Write the failing test**

```python
# tests/test_base_parser.py
from agent_archive.parsers.base import BaseParser
from pathlib import Path

class DummyParser(BaseParser):
    def parse(self, filepath: Path):
        return []

def test_base_parser_interface():
    parser = DummyParser()
    assert hasattr(parser, 'parse')
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_base_parser.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/agent_archive/parsers/__init__.py
# Init parsers module
```

```python
# src/agent_archive/parsers/base.py
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from ..models import Session

class BaseParser(ABC):
    @abstractmethod
    def parse(self, filepath: Path) -> List[Session]:
        pass
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_base_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/agent_archive/parsers tests/test_base_parser.py
git commit -m "feat: add base parser abstract class"
```

### Task 4: CLI Skeleton

**Files:**
- Create: `src/agent_archive/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py
from typer.testing import CliRunner
from agent_archive.cli import app

runner = CliRunner()

def test_sync_command_help():
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
    assert "output" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_cli.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/agent_archive/cli.py
import typer
from pathlib import Path

app = typer.Typer()

@app.command()
def sync(output: Path = typer.Option(..., help="Output directory for the markdown files and static site")):
    """Sync agent logs and build MkDocs site."""
    typer.echo(f"Syncing to {output}")

if __name__ == "__main__":
    app()
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/agent_archive/cli.py tests/test_cli.py
git commit -m "feat: add basic typer cli skeleton"
```
