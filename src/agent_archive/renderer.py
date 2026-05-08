# src/agent_archive/renderer.py
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import re

import yaml

from .models import Message, Session


AGENT_DISPLAY = {
    "claude_code": "Claude Code",
    "gemini": "Gemini",
    "pi": "Pi",
    "opencode": "OpenCode",
    "copilot": "Copilot",
}

# (icon, label, mkdocs-admonition-type)
_META_STYLE = {
    "model_change":           ("🔄", "Model Change",       "info"),
    "thinking_level_change":  ("🧠", "Thinking Level",     "info"),
    "compaction":             ("🗜️", "Compaction",         "note"),
    "branch_summary":         ("🌿", "Branch Switch",      "note"),
    "session_info":           ("📝", "Session Info",       "note"),
    "label":                  ("🏷️", "Bookmark",           "note"),
    "turn_duration":          ("⏱️", "Turn Duration",      "tip"),
    "info":                   ("ℹ️", "System Info",        "note"),
    "custom":                 ("🔌", "Extension Event",    "note"),
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
            elif msg.role == "meta":
                subtype = msg.meta_subtype or "event"
                icon, label, admonition = _META_STYLE.get(
                    subtype,
                    ("ℹ️", subtype.replace("_", " ").title(), "note"),
                )
                lines.append(f'!!! {admonition} "{icon} {label} ({ts_str})"')
                for content_line in msg.content.split("\n"):
                    lines.append(f"    {content_line}")

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
            for s in sorted(by_agent[agent_name], key=lambda x: x.start_time, reverse=True):
                date = s.start_time.strftime("%Y-%m-%d %H:%M")
                model = s.model or "—"
                total_in = sum(m.token_usage.get("input", 0) for m in s.messages if m.token_usage)
                total_out = sum(m.token_usage.get("output", 0) for m in s.messages if m.token_usage)
                tokens = f"{total_in}/{total_out}" if total_in or total_out else "—"
                link = f"[{s.title}]({s.agent_name}/{s.id}.md)"
                lines.append(f"| {link} | {date} | {model} | {tokens} |")
            lines.append("")

        return "\n".join(lines)

    def _compute_stats(self, sessions: List[Session]) -> dict:
        """Compute aggregate statistics from all sessions."""
        import json
        from collections import Counter

        total_input = 0
        total_output = 0
        agent_counts: Counter = Counter()
        agent_tokens: Dict[str, Dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
        monthly_tokens: Dict[str, Dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
        project_counts: Counter = Counter()
        model_counts: Counter = Counter()

        for s in sessions:
            display = AGENT_DISPLAY.get(s.agent_name, s.agent_name)
            agent_counts[display] += 1

            if s.model:
                model_counts[s.model] += 1

            if s.project_dir:
                project_name = Path(s.project_dir).name
                project_counts[project_name] += 1

            month = s.start_time.strftime("%Y-%m")
            for m in s.messages:
                if m.token_usage:
                    inp = m.token_usage.get("input", 0)
                    out = m.token_usage.get("output", 0)
                    total_input += inp
                    total_output += out
                    agent_tokens[display]["input"] += inp
                    agent_tokens[display]["output"] += out
                    monthly_tokens[month]["input"] += inp
                    monthly_tokens[month]["output"] += out

        return {
            "total_sessions": len(sessions),
            "total_agents": len(agent_counts),
            "total_input": total_input,
            "total_output": total_output,
            "agent_counts": dict(agent_counts),
            "agent_tokens": {k: dict(v) for k, v in agent_tokens.items()},
            "monthly_tokens": {k: dict(v) for k, v in sorted(monthly_tokens.items())},
            "project_counts": dict(project_counts.most_common(10)),
            "model_counts": dict(model_counts.most_common(10)),
        }

    def render_homepage(self, sessions: List[Session]) -> str:
        import json

        stats = self._compute_stats(sessions)

        def _fmt(n: int) -> str:
            if n >= 1_000_000:
                return f"{n / 1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n / 1_000:.1f}K"
            return str(n)

        lines = []
        lines.append("# Agent Archive")
        lines.append("")

        # Summary cards
        lines.append(f"**{stats['total_sessions']} sessions** | "
                      f"**{stats['total_agents']} agents** | "
                      f"**{_fmt(stats['total_input'])} input tokens** | "
                      f"**{_fmt(stats['total_output'])} output tokens**")
        lines.append("")

        # Stats tables
        lines.append("## Sessions by Agent")
        lines.append("")
        lines.append("| Agent | Sessions | Input Tokens | Output Tokens |")
        lines.append("|-------|----------|-------------|--------------|")
        for agent, count in sorted(stats["agent_counts"].items(), key=lambda x: -x[1]):
            at = stats["agent_tokens"].get(agent, {"input": 0, "output": 0})
            lines.append(f"| {agent} | {count} | {_fmt(at['input'])} | {_fmt(at['output'])} |")
        lines.append("")

        lines.append("## Token Usage by Month")
        lines.append("")
        lines.append("| Month | Input Tokens | Output Tokens | Total |")
        lines.append("|-------|-------------|--------------|-------|")
        for month, tokens in stats["monthly_tokens"].items():
            total = tokens["input"] + tokens["output"]
            lines.append(f"| {month} | {_fmt(tokens['input'])} | {_fmt(tokens['output'])} | {_fmt(total)} |")
        lines.append("")

        lines.append("## Top Projects")
        lines.append("")
        lines.append("| Project | Sessions |")
        lines.append("|---------|----------|")
        for proj, count in stats["project_counts"].items():
            lines.append(f"| {proj} | {count} |")
        lines.append("")

        lines.append("## Top Models")
        lines.append("")
        lines.append("| Model | Sessions |")
        lines.append("|-------|----------|")
        for model, count in stats["model_counts"].items():
            lines.append(f"| {model} | {count} |")
        lines.append("")

        # Chart.js charts
        monthly_labels = json.dumps(list(stats["monthly_tokens"].keys()))
        monthly_input = json.dumps([v["input"] for v in stats["monthly_tokens"].values()])
        monthly_output = json.dumps([v["output"] for v in stats["monthly_tokens"].values()])
        agent_labels = json.dumps(list(stats["agent_counts"].keys()))
        agent_values = json.dumps(list(stats["agent_counts"].values()))

        lines.append('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>')
        lines.append("")
        lines.append("## Monthly Token Usage")
        lines.append("")
        lines.append('<canvas id="monthlyChart" style="max-height:400px;"></canvas>')
        lines.append("")
        lines.append("## Sessions by Agent")
        lines.append("")
        lines.append('<canvas id="agentChart" style="max-height:400px;max-width:400px;"></canvas>')
        lines.append("")
        lines.append(f"""<script>
  new Chart(document.getElementById('monthlyChart'), {{
    type: 'bar',
    data: {{
      labels: {monthly_labels},
      datasets: [
        {{ label: 'Input Tokens', data: {monthly_input}, backgroundColor: '#8be9fd' }},
        {{ label: 'Output Tokens', data: {monthly_output}, backgroundColor: '#bd93f9' }}
      ]
    }},
    options: {{
      responsive: true,
      scales: {{ y: {{ beginAtZero: true, ticks: {{ color: '#f8f8f2' }} }}, x: {{ ticks: {{ color: '#f8f8f2' }} }} }},
      plugins: {{ legend: {{ labels: {{ color: '#f8f8f2' }} }} }}
    }}
  }});
  new Chart(document.getElementById('agentChart'), {{
    type: 'doughnut',
    data: {{
      labels: {agent_labels},
      datasets: [{{ data: {agent_values}, backgroundColor: ['#8be9fd','#50fa7b','#ffb86c','#ff79c6','#bd93f9','#f1fa8c'] }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ labels: {{ color: '#f8f8f2' }} }} }}
    }}
  }});
</script>""")
        lines.append("")
        return "\n".join(lines)

    def _session_from_frontmatter(self, filepath: Path) -> Optional[Session]:
        """Reconstruct a lightweight Session from a rendered session markdown file.

        Only the fields needed for homepage stats and month-index tables are
        populated (title, agent, model, start_time, project_dir, token_usage).
        """
        text = filepath.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            return None
        end = text.find("---", 3)
        if end == -1:
            return None
        try:
            fm = yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            return None

        agent_name = fm.get("agent", "")
        date_val = fm.get("date")
        if not agent_name or not date_val:
            return None

        try:
            start_time = datetime.strptime(str(date_val), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

        tokens = fm.get("tokens") or {}
        inp = tokens.get("input", 0) if isinstance(tokens, dict) else 0
        out = tokens.get("output", 0) if isinstance(tokens, dict) else 0
        messages = []
        if inp or out:
            messages.append(Message(role="assistant", content="",
                                    token_usage={"input": inp, "output": out}))

        return Session(
            id=filepath.stem,
            agent_name=agent_name,
            title=str(fm.get("title", filepath.stem)),
            start_time=start_time,
            messages=messages,
            model=fm.get("model"),
            project_dir=fm.get("project"),
        )

    def _load_all_sessions(self, docs_dir: Path) -> List[Session]:
        """Load lightweight Session objects from every rendered session file on disk."""
        sessions: List[Session] = []
        month_re = re.compile(r"^\d{4}-\d{2}$")
        for month_dir in docs_dir.iterdir():
            if not month_dir.is_dir() or not month_re.match(month_dir.name):
                continue
            for agent_dir in month_dir.iterdir():
                if not agent_dir.is_dir():
                    continue
                for md_file in agent_dir.glob("*.md"):
                    s = self._session_from_frontmatter(md_file)
                    if s:
                        sessions.append(s)
        return sessions

    def render_all(self, sessions: List[Session], output_dir: Path) -> None:
        docs_dir = output_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Write individual session files for newly-parsed sessions
        for session in sessions:
            month = session.start_time.strftime("%Y-%m")
            session_dir = docs_dir / month / session.agent_name
            session_dir.mkdir(parents=True, exist_ok=True)
            date_prefix = session.start_time.strftime("%Y-%m-%d")
            session_file = session_dir / f"{date_prefix}-{session.id}.md"
            session_file.write_text(self.render_session(session))

        # Rebuild homepage and month indices from the full on-disk archive
        all_sessions = self._load_all_sessions(docs_dir)

        by_month: Dict[str, List[Session]] = defaultdict(list)
        for s in all_sessions:
            by_month[s.start_time.strftime("%Y-%m")].append(s)

        for month, month_sessions in by_month.items():
            index_file = docs_dir / month / "index.md"
            index_file.write_text(self.render_month_index(month, month_sessions))

        homepage = docs_dir / "index.md"
        homepage.write_text(self.render_homepage(all_sessions))
