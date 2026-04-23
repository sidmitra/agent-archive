# Agent Archive Design

## Overview
`agent-archive` is a Python CLI tool installable via `uvx` or `pipx`. It automatically scours default local directories for coding agent sessions (like pi, Aider, Cursor, Cline), parses them, and exports them into standard Markdown files. Finally, it uses MkDocs to build a searchable static HTML site for easy browsing.

## Core Architecture & Dependencies
- **Typer**: CLI interface (`agent-archive sync --output ~/agent-history`).
- **Pydantic**: Strict schema validation for agent sessions.
- **MkDocs + Material Theme**: Static site generation.
- **Project Structure**:
  - `src/agent_archive/cli.py` (Entry point)
  - `src/agent_archive/models.py` (Universal data schema)
  - `src/agent_archive/state.py` (State tracking)
  - `src/agent_archive/site_builder.py` (MkDocs wrapper)
  - `src/agent_archive/parsers/` (Agent-specific plugins)

## Data Models & Parsing Flow
1. **Universal Model**: `Session` containing `id`, `agent_name`, `title`, timestamps, and a list of `Message` objects.
2. **Incremental Sync**: Uses `.sync_state.json` in the output directory to track `last_modified` timestamps.
3. **Parsers**: Base parser with specific implementations for each agent. They auto-discover logs from standard OS paths, skip files that haven't changed, and parse new/modified files into `Session` objects.

## Export & Site Generation
1. **Markdown**: Standardized files output to `docs/<agent_name>/<YYYY-MM>/<session_id>.md` with YAML frontmatter.
2. **Merging**: Existing sessions are safely overwritten if they receive new messages.
3. **MkDocs**: Automatically generates an `mkdocs.yml` with the `mkdocs-material` theme and runs the build process to produce a static HTML site in the `site/` folder.
