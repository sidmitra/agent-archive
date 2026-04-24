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
                "name": "material",
                "features": [
                    "search.suggest",
                    "search.highlight",
                    "navigation.sections",
                ],
            },
            "plugins": ["search"],
            "use_directory_urls": False,
        }
        if nav:
            config["nav"] = nav

        self.config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

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
                        label = session_file.stem
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
