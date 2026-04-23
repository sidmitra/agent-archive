# tests/test_site_builder.py
import yaml
from pathlib import Path
from unittest.mock import patch
from agent_archive.site_builder import SiteBuilder


def test_generate_mkdocs_yml(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home")
    month_dir = docs_dir / "2023-06"
    month_dir.mkdir()
    (month_dir / "index.md").write_text("# June")
    agent_dir = month_dir / "claude_code"
    agent_dir.mkdir()
    (agent_dir / "sess1.md").write_text("# Session")

    builder = SiteBuilder(tmp_path)
    builder.generate_config()

    config_path = tmp_path / "mkdocs.yml"
    assert config_path.exists()

    config = yaml.safe_load(config_path.read_text())
    assert config["site_name"] == "Agent Archive"
    assert config["theme"]["name"] == "material"
    assert "search" in str(config.get("plugins", []))


def test_build_site(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home")

    builder = SiteBuilder(tmp_path)
    builder.generate_config()

    with patch("agent_archive.site_builder.subprocess.run") as mock_run:
        mock_run.return_value = None
        builder.build()
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert "mkdocs" in args[0][0]
        assert "build" in args[0][0]
