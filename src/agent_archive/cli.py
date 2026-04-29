# src/agent_archive/cli.py
import http.server
import os
import threading
import webbrowser
import typer
from pathlib import Path
from typing import Optional

from .parsers.claude_code import ClaudeCodeParser
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


@app.command()
def sync(
    output: Path = typer.Option(..., help="Output directory for the markdown files and static site"),
    claude_path: Optional[Path] = typer.Option(None, help="Override Claude Code log directory"),
    pi_path: Optional[Path] = typer.Option(None, help="Override pi agent log directory"),
    opencode_db: Optional[Path] = typer.Option(None, help="Override opencode database path"),
    copilot_path: Optional[Path] = typer.Option(None, help="Override copilot log directory"),
    redact: bool = typer.Option(True, help="Redact secrets (tokens, API keys, env var values) before writing output"),
):
    """Sync agent logs and build MkDocs site."""
    output.mkdir(parents=True, exist_ok=True)

    state = SyncState(_state_path(output))

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
        sessions_to_render = all_sessions
        if redact:
            sessions_to_render = Redactor().redact_sessions(all_sessions)
            typer.echo("Redacted secrets from sessions")
        renderer = MarkdownRenderer()
        renderer.render_all(sessions_to_render, output)
        typer.echo("Rendered Markdown files")
    else:
        typer.echo("No new sessions to sync")

    builder = SiteBuilder(output)
    builder.generate_config()
    builder.build()
    typer.echo("Site built successfully")

    state.save()


@app.command()
def serve(
    output: Path = typer.Option(..., help="Output directory used during sync"),
    port: int = typer.Option(8000, help="Port to serve on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a browser tab automatically"),
):
    """Serve the HTML archive locally."""
    site_dir = output / "site"
    if not site_dir.exists():
        typer.echo(f"Site directory not found: {site_dir}. Run 'sync' first.", err=True)
        raise typer.Exit(1)

    os.chdir(site_dir)
    handler = http.server.SimpleHTTPRequestHandler
    # silence the per-request log lines
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


if __name__ == "__main__":
    app()
