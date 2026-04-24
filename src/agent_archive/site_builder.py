# src/agent_archive/site_builder.py
import subprocess
import sys
from pathlib import Path

import yaml


class SiteBuilder:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.docs_dir = output_dir / "docs"
        self.config_path = output_dir / "mkdocs.yml"

    def generate_config(self) -> None:
        nav = self._build_nav()

        config = {
            "site_name": "Agent Archive",
            "docs_dir": str(self.docs_dir),
            "site_dir": str(self.output_dir / "site"),
            "theme": {
                "name": "dracula",
            },
            "plugins": ["search"],
            "use_directory_urls": False,
        }
        if nav:
            config["nav"] = nav

        self.config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    @staticmethod
    def _parse_frontmatter(path: Path) -> dict:
        """Extract YAML frontmatter from a markdown file."""
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            return {}
        end = text.find("---", 3)
        if end == -1:
            return {}
        try:
            return yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            return {}

    def _build_nav_label(self, session_file: Path) -> str:
        """Build a nav label like 'copilot | airbase-backend - Fix BYOC Tests'."""
        fm = self._parse_frontmatter(session_file)
        agent = fm.get("agent", "")
        project_path = fm.get("project", "")
        title = fm.get("title", session_file.stem)

        project_name = Path(project_path).name if project_path else ""

        parts = []
        if agent:
            parts.append(agent)
        if project_name:
            parts.append(project_name)

        prefix = " | ".join(parts)
        if prefix:
            return f"{prefix} - {title}"
        return title

    def _build_nav(self) -> list:
        nav = []
        if not self.docs_dir.exists():
            return nav

        nav.append({"Home": "index.md"})

        months = sorted(
            [d for d in self.docs_dir.iterdir() if d.is_dir() and d.name != "site"],
            reverse=True,
        )
        for month_dir in months:
            month_items = [{"Overview": f"{month_dir.name}/index.md"}]
            for agent_dir in sorted(month_dir.iterdir()):
                if agent_dir.is_dir():
                    for session_file in sorted(agent_dir.glob("*.md")):
                        label = self._build_nav_label(session_file)
                        month_items.append(
                            {label: f"{month_dir.name}/{agent_dir.name}/{session_file.name}"}
                        )
            nav.append({month_dir.name: month_items})

        return nav

    def build(self) -> None:
        subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "-f", str(self.config_path)],
            check=True,
            cwd=self.output_dir,
        )
