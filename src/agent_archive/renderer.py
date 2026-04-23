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

        for month, month_sessions in by_month.items():
            index_file = docs_dir / month / "index.md"
            index_file.write_text(self.render_month_index(month, month_sessions))

        homepage = docs_dir / "index.md"
        homepage.write_text(self.render_homepage(sessions))
