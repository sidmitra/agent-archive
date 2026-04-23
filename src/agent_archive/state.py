# src/agent_archive/state.py
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


class SyncState:
    def __init__(self, path: Path):
        self.path = path
        self.files: Dict[str, dict] = {}
        if path.exists():
            data = json.loads(path.read_text())
            self.files = data.get("files", {})

    def is_changed(self, filepath: Path) -> bool:
        key = str(filepath.resolve())
        if key not in self.files:
            return True
        stat = filepath.stat()
        entry = self.files[key]
        return entry["mtime"] != stat.st_mtime or entry["size"] != stat.st_size

    def mark_synced(self, filepath: Path) -> None:
        key = str(filepath.resolve())
        stat = filepath.stat()
        self.files[key] = {"mtime": stat.st_mtime, "size": stat.st_size}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "files": self.files,
        }
        self.path.write_text(json.dumps(data, indent=2))
