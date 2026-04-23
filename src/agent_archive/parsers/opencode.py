# src/agent_archive/parsers/opencode.py
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser

DEFAULT_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


class OpencodeParser(BaseParser):
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB

    def discover(self) -> List[Path]:
        if self.db_path.exists():
            return [self.db_path]
        return []

    def parse(self, filepath: Path) -> List[Session]:
        conn = sqlite3.connect(filepath)
        conn.row_factory = sqlite3.Row
        sessions: List[Session] = []

        for row in conn.execute("SELECT * FROM session ORDER BY time_created"):
            session_id = row["id"]
            messages: List[Message] = []
            model = None

            for msg_row in conn.execute(
                "SELECT * FROM message WHERE session_id = ? ORDER BY time_created",
                (session_id,),
            ):
                msg_data = json.loads(msg_row["data"])
                role = msg_data.get("role", "user")
                ts_ms = msg_data.get("time", {}).get("created")
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) if ts_ms else None

                if model is None:
                    model_info = msg_data.get("model", {})
                    if isinstance(model_info, dict):
                        model = model_info.get("modelID")

                token_usage = None
                tokens = msg_data.get("tokens")
                if tokens:
                    token_usage = {"input": tokens.get("input", 0), "output": tokens.get("output", 0)}

                parts = conn.execute(
                    "SELECT * FROM part WHERE message_id = ? ORDER BY time_created",
                    (msg_row["id"],),
                ).fetchall()

                for part_row in parts:
                    part_data = json.loads(part_row["data"])
                    ptype = part_data.get("type")

                    if ptype == "text":
                        messages.append(Message(
                            role="user" if role == "user" else "assistant",
                            content=part_data.get("text", ""),
                            timestamp=ts,
                            token_usage=token_usage if role == "assistant" else None,
                        ))
                    elif ptype == "tool":
                        tool_name = part_data.get("tool", "")
                        state = part_data.get("state", {})
                        output = state.get("output", "")
                        inp = state.get("input", {})
                        desc = json.dumps(inp) if inp else ""
                        content = output if output else desc
                        messages.append(Message(
                            role="assistant",
                            content=content,
                            timestamp=ts,
                            tool_name=tool_name,
                        ))

            if not messages:
                continue

            start_ts = datetime.fromtimestamp(row["time_created"] / 1000, tz=timezone.utc)
            end_ts = datetime.fromtimestamp(row["time_updated"] / 1000, tz=timezone.utc)

            sessions.append(Session(
                id=session_id,
                agent_name="opencode",
                title=row["title"],
                start_time=start_ts,
                end_time=end_ts,
                messages=messages,
                model=model,
                project_dir=row["directory"],
                source_path=str(filepath),
            ))

        conn.close()
        return sessions
