# src/agent_archive/site_builder.py
import json
import re
import shutil
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
        self._write_theme_overrides()

        overrides_dir = self.output_dir / "overrides"
        config = {
            "site_name": "Agent Archive",
            "docs_dir": str(self.docs_dir),
            "site_dir": str(self.output_dir / "site"),
            "theme": {
                "name": "mkdocs",
                "custom_dir": str(overrides_dir),
                "color_mode": "auto",
                "user_color_mode_toggle": True,
                "hljs_style": "github",
                "hljs_style_dark": "github-dark",
            },
            "plugins": ["search"],
            "use_directory_urls": False,
            "validation": {"links": {"not_found": "ignore"}},
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
        """Build nav list and collect tooltip mapping as a side effect."""
        self._nav_tooltips: dict[str, str] = {}
        nav = []
        if not self.docs_dir.exists():
            return nav

        nav.append({"Home": "index.md"})

        month_re = re.compile(r"^\d{4}-\d{2}$")
        months = sorted(
            [d for d in self.docs_dir.iterdir() if d.is_dir() and month_re.match(d.name)],
            reverse=True,
        )
        for month_dir in months:
            month_items = [{"Overview": f"{month_dir.name}/index.md"}]
            all_session_files = [
                f
                for agent_dir in month_dir.iterdir()
                if agent_dir.is_dir()
                for f in agent_dir.glob("*.md")
            ]
            for session_file in sorted(all_session_files, key=lambda f: f.name, reverse=True):
                label = self._build_nav_label(session_file)
                rel_path = f"{month_dir.name}/{session_file.parent.name}/{session_file.name}"
                month_items.append({label: rel_path})

                fm = self._parse_frontmatter(session_file)
                project = fm.get("project", "")
                if project:
                    self._nav_tooltips[label] = project
            nav.append({month_dir.name: month_items})

        return nav

    def _write_theme_overrides(self) -> None:
        """Write theme override templates (e.g. blank footer)."""
        # The default mkdocs theme keeps its footer in partials/footer.html
        overrides_dir = self.output_dir / "overrides" / "partials"
        overrides_dir.mkdir(parents=True, exist_ok=True)
        (overrides_dir / "footer.html").write_text("")

        tooltips = getattr(self, "_nav_tooltips", {})
        main_html = f"""{{% extends "base.html" %}}
{{% block scripts %}}
{{{{ super() }}}}
<script>
(function() {{
  var tips = {json.dumps(tooltips)};
  document.addEventListener('DOMContentLoaded', function() {{
    document.querySelectorAll('nav a, .md-nav a, .sidebar a, [data-md-component="navigation"] a').forEach(function(a) {{
      var text = a.textContent.trim();
      if (tips[text]) {{
        a.setAttribute('title', tips[text]);
      }}
    }});
  }});
}})();
</script>
{{% endblock %}}
"""
        (self.output_dir / "overrides" / "main.html").write_text(main_html)

    def build(self) -> None:
        subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "-f", str(self.config_path)],
            check=True,
            cwd=self.output_dir,
        )
        # Copy every source .md file into a sibling _raw/ subdirectory so
        # that "📄 Raw" links resolve to the .md source.  The links use the
        # _raw/ prefix so MkDocs cannot resolve them as docs files and
        # therefore leaves the .md href untouched during the build.
        site_dir = self.output_dir / "site"
        for md_src in self.docs_dir.rglob("*.md"):
            rel = md_src.relative_to(self.docs_dir)
            dest = site_dir / rel.parent / "_raw" / rel.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_src, dest)
