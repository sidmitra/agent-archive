# tests/test_state.py
import json
import time
from pathlib import Path
from agent_archive.state import SyncState


def test_sync_state_new(tmp_path):
    state = SyncState(tmp_path / ".sync_state.json")
    assert state.files == {}


def test_sync_state_is_changed_new_file(tmp_path):
    state = SyncState(tmp_path / ".sync_state.json")
    f = tmp_path / "session.jsonl"
    f.write_text('{"type": "user"}')
    assert state.is_changed(f) is True


def test_sync_state_save_and_load(tmp_path):
    state_path = tmp_path / ".sync_state.json"
    state = SyncState(state_path)

    f = tmp_path / "session.jsonl"
    f.write_text('{"type": "user"}')

    state.mark_synced(f)
    state.save()

    state2 = SyncState(state_path)
    assert state2.is_changed(f) is False


def test_sync_state_detects_modification(tmp_path):
    state_path = tmp_path / ".sync_state.json"
    state = SyncState(state_path)

    f = tmp_path / "session.jsonl"
    f.write_text('{"type": "user"}')
    state.mark_synced(f)
    state.save()

    f.write_text('{"type": "user", "content": "modified"}')

    state2 = SyncState(state_path)
    assert state2.is_changed(f) is True
