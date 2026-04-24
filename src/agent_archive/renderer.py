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
