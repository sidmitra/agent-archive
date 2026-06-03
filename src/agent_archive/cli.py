# src/agent_archive/cli.py
import http.server
import os
import threading
import webbrowser
import typer
from pathlib import Path
from typing import Optional

from .parsers.claude_code import ClaudeCodeParser
from .parsers.gemini import GeminiParser
from .parsers.pi import PiParser
from .parsers.opencode import OpencodeParser
from .parsers.copilot import CopilotParser
from .redactor import Redactor
from .renderer import MarkdownRenderer
from .site_builder import SiteBuilder
from .state import SyncState, _state_path

app = typer.Typer()


@app.callback()
def main():
    """Archive and browse agentic coding sessions."""


# ---------------------------------------------------------------------------
# Shared helpers (used by both the individual commands and `run`)
# ---------------------------------------------------------------------------

def _sync(
    output: Path,
    claude_path: Optional[Path] = None,
    pi_path: Optional[Path] = None,
    opencode_db: Optional[Path] = None,
    gemini_path: Optional[Path] = None,
    copilot_path: Optional[Path] = None,
    redact: bool = True,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    state = SyncState(_state_path(output))
    parsers = [
        ClaudeCodeParser(base_path=claude_path),
        PiParser(base_path=pi_path),
        OpencodeParser(db_path=opencode_db),
        GeminiParser(base_path=gemini_path),
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
        sessions_to_render = all_sessions
        if redact:
            sessions_to_render = Redactor().redact_sessions(all_sessions)
            typer.echo("Redacted secrets from sessions")
        renderer = MarkdownRenderer()
        renderer.render_all(sessions_to_render, output)
        typer.echo("Rendered Markdown files")
    else:
        typer.echo("No new sessions to sync")
    state.save()


def _build(output: Path) -> None:
    if not output.exists():
        typer.echo(f"Output directory not found: {output}. Run 'sync' first.", err=True)
        raise typer.Exit(1)
    builder = SiteBuilder(output)
    builder.generate_config()
    builder.build()
    typer.echo("Site built successfully")


def _serve(output: Path, port: int = 8000, no_browser: bool = False) -> None:
    site_dir = output / "site"
    if not site_dir.exists():
        typer.echo(f"Site directory not found: {site_dir}. Run 'build' first.", err=True)
        raise typer.Exit(1)
    os.chdir(site_dir)
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *_: None  # type: ignore[method-assign]
    with http.server.HTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}"
        typer.echo(f"Serving {site_dir} at {url}  (Ctrl+C to stop)")
        if not no_browser:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            typer.echo("\nStopped.")


# ---------------------------------------------------------------------------
# Individual commands (thin wrappers around the helpers above)
# ---------------------------------------------------------------------------

@app.command()
def sync(
    output: Path = typer.Option(..., help="Output directory for the markdown files"),
    claude_path: Optional[Path] = typer.Option(None, help="Override Claude Code log directory"),
    pi_path: Optional[Path] = typer.Option(None, help="Override pi agent log directory"),
    opencode_db: Optional[Path] = typer.Option(None, help="Override opencode database path"),
    gemini_path: Optional[Path] = typer.Option(None, help="Override Gemini CLI session directory"),
    copilot_path: Optional[Path] = typer.Option(None, help="Override copilot log directory"),
    redact: bool = typer.Option(True, help="Redact secrets (tokens, API keys, env var values) before writing output"),
):
    """Extract agent sessions and write them as Markdown files."""
    _sync(output, claude_path, pi_path, opencode_db, gemini_path, copilot_path, redact)


@app.command()
def build(
    output: Path = typer.Option(..., help="Output directory produced by 'sync'"),
):
    """Generate MkDocs config and build the static site from synced Markdown files."""
    _build(output)


@app.command()
def serve(
    output: Path = typer.Option(..., help="Output directory used during sync"),
    port: int = typer.Option(8000, help="Port to serve on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a browser tab automatically"),
):
    """Serve the HTML archive locally."""
    _serve(output, port, no_browser)


@app.command()
def run(
    output: Path = typer.Option(..., help="Output directory for the archive"),
    claude_path: Optional[Path] = typer.Option(None, help="Override Claude Code log directory"),
    pi_path: Optional[Path] = typer.Option(None, help="Override pi agent log directory"),
    opencode_db: Optional[Path] = typer.Option(None, help="Override opencode database path"),
    gemini_path: Optional[Path] = typer.Option(None, help="Override Gemini CLI session directory"),
    copilot_path: Optional[Path] = typer.Option(None, help="Override copilot log directory"),
    redact: bool = typer.Option(True, help="Redact secrets before writing output"),
    port: int = typer.Option(8000, help="Port to serve on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a browser tab automatically"),
):
    """Sync, build, and serve the archive in one step."""
    typer.echo("--- sync ---")
    _sync(output, claude_path, pi_path, opencode_db, gemini_path, copilot_path, redact)
    typer.echo("--- build ---")
    _build(output)
    typer.echo("--- serve ---")
    _serve(output, port, no_browser)


if __name__ == "__main__":
    app()
