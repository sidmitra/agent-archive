import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser


class AntigravityParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or (Path.home() / ".gemini" / "antigravity-cli" / "brain")

    def discover(self) -> List[Path]:
        if not self.base_path.exists():
            return []
        return sorted(self.base_path.glob("*/.system_generated/logs/transcript.jsonl"))

    def parse(self, filepath: Path) -> List[Session]:
        session_id = filepath.parent.parent.parent.name

        messages: List[Message] = []
        title: Optional[str] = None
        start_time = None
        end_time = None

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                source = data.get("source")
                ts_str = data.get("created_at")
                ts = (
                    datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts_str
                    else None
                )

                if start_time is None and ts:
                    start_time = ts
                if ts:
                    end_time = ts

                if source == "USER_EXPLICIT" and msg_type == "USER_INPUT":
                    content = data.get("content", "")
                    
                    if title is None and content:
                        match = re.search(r'<USER_REQUEST>\n(.*?)\n</USER_REQUEST>', content, re.DOTALL)
                        if match:
                            title = match.group(1).strip()[:120]
                        else:
                            title = content.strip()[:120]
                    
                    messages.append(Message(
                        role="user",
                        content=content,
                        timestamp=ts,
                    ))

                elif source == "MODEL" and msg_type == "PLANNER_RESPONSE":
                    thinking = data.get("thinking")
                    content = data.get("content")
                    
                    if thinking:
                        messages.append(Message(
                            role="assistant",
                            content=f"**Thinking:**\n{thinking}",
                            timestamp=ts
                        ))
                    if content:
                        messages.append(Message(
                            role="assistant",
                            content=content,
                            timestamp=ts
                        ))

                    tool_calls = data.get("tool_calls", [])
                    for tc in tool_calls:
                        name = tc.get("name", "unknown")
                        args = tc.get("args", {})
                        args_text = json.dumps(args, indent=2)
                        messages.append(Message(
                            role="assistant",
                            content=args_text,
                            timestamp=ts,
                            tool_name=name
                        ))

                elif source == "MODEL" and msg_type not in ("PLANNER_RESPONSE", "USER_INPUT"):
                    tool_name = str(msg_type).lower()
                    content = data.get("content", "")
                    if content:
                        messages.append(Message(
                            role="tool_result",
                            content=content,
                            timestamp=ts,
                            tool_name=tool_name
                        ))

        if not messages:
            return []

        if start_time is None:
            start_time = datetime.now()

        return [Session(
            id=session_id,
            agent_name="antigravity",
            title=title or session_id,
            start_time=start_time,
            end_time=end_time,
            messages=messages,
            project_dir=None,
            source_path=str(filepath),
        )]
