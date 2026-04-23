# tests/test_base_parser.py
import pytest
from agent_archive.parsers.base import BaseParser
from pathlib import Path


class DummyParser(BaseParser):
    def discover(self):
        return [Path("/tmp/session.jsonl")]

    def parse(self, filepath: Path):
        return []


class IncompleteParser(BaseParser):
    def parse(self, filepath: Path):
        return []


def test_base_parser_interface():
    parser = DummyParser()
    assert hasattr(parser, "parse")
    assert hasattr(parser, "discover")


def test_base_parser_discover():
    parser = DummyParser()
    paths = parser.discover()
    assert len(paths) == 1
    assert paths[0] == Path("/tmp/session.jsonl")


def test_incomplete_parser_raises():
    with pytest.raises(TypeError):
        IncompleteParser()
