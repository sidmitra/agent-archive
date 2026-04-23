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
