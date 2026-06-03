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
    assert config["theme"]["name"] == "mkdocs"
    assert "search" in str(config.get("plugins", []))


def test_raw_link_uses_raw_subdir(tmp_path):
    """render_all should emit Raw links pointing to _raw/{filename}, not
    the rendered file itself, so MkDocs cannot resolve and rewrite them."""
    from agent_archive.renderer import MarkdownRenderer
    from agent_archive.models import Message, Session
    from datetime import datetime, timezone

    session = Session(
        id="sess1",
        agent_name="claude_code",
        title="Fix auth bug",
        start_time=datetime(2023, 6, 15, 10, 0, tzinfo=timezone.utc),
        messages=[Message(role="user", content="Fix it")],
    )
    renderer = MarkdownRenderer()
    renderer.render_all([session], tmp_path)

    session_file = tmp_path / "docs" / "2023-06" / "claude_code" / "2023-06-15-sess1.md"
    content = session_file.read_text()
    assert "[\U0001f4c4 Raw](_raw/2023-06-15-sess1.md)" in content


def test_build_copies_md_to_raw_subdir(tmp_path):
    """build() should copy .md source files into _raw/ sibling subdirs in site."""
    docs_dir = tmp_path / "docs"
    session_dir = docs_dir / "2023-06" / "claude_code"
    session_dir.mkdir(parents=True)
    (session_dir / "2023-06-15-sess1.md").write_text("# Session")
    (docs_dir / "index.md").write_text("# Home")

    builder = SiteBuilder(tmp_path)
    builder.generate_config()

    with patch("agent_archive.site_builder.subprocess.run"):
        # mkdocs is mocked; manually create the site structure it would produce
        site_dir = tmp_path / "site"
        (site_dir / "2023-06" / "claude_code").mkdir(parents=True)
        (site_dir / "2023-06" / "claude_code" / "2023-06-15-sess1.html").write_text("<html/>")
        builder.build()

    raw_dest = site_dir / "2023-06" / "claude_code" / "_raw" / "2023-06-15-sess1.md"
    assert raw_dest.exists()
    # The .md file should NOT be copied to the old sibling location
    assert not (site_dir / "2023-06" / "claude_code" / "2023-06-15-sess1.md").exists()


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
