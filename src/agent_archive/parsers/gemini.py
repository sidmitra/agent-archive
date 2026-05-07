# src/agent_archive/parsers/gemini.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser


class GeminiParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or (Path.home() / ".gemini" / "tmp")

    def discover(self) -> List[Path]:
        if not self.base_path.exists():
            return []
        return sorted(self.base_path.glob("*/chats/session-*.json"))

    def parse(self, filepath: Path) -> List[Session]:
        data = json.loads(filepath.read_text())

        session_id = data.get("sessionId", filepath.stem)
        start_time_str = data.get("startTime")
        last_updated_str = data.get("lastUpdated")

        start_time = (
            datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            if start_time_str
            else datetime.now()
        )
        end_time = (
            datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            if last_updated_str
            else None
        )

        # Project directory from sibling .project_root file
        project_root_file = filepath.parent.parent / ".project_root"
        project_dir: Optional[str] = None
        if project_root_file.exists():
            project_dir = project_root_file.read_text().strip() or None

        messages: List[Message] = []
        model: Optional[str] = None
        title: Optional[str] = None

        for msg in data.get("messages", []):
            msg_type = msg.get("type")
            ts_str = msg.get("timestamp")
            ts = (
                datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts_str
                else None
            )

            # Skip info/system messages
            if msg_type == "info":
                continue

            if msg_type == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text = "\n\n".join(
                        b.get("text", "") for b in content if b.get("type") == "text" or "text" in b
                    )
                else:
                    text = str(content)

                if title is None and text.strip():
                    title = text.strip()[:120]

                messages.append(Message(role="user", content=text, timestamp=ts))

            elif msg_type == "gemini":
                if model is None:
                    model = msg.get("model")

                tokens = msg.get("tokens", {})
                token_usage = None
                if tokens:
                    token_usage = {
                        "input": tokens.get("input", 0),
                        "output": tokens.get("output", 0),
                    }

                content = str(msg.get("content", ""))

                tool_calls = msg.get("toolCalls", [])
                if tool_calls:
                    for tc in tool_calls:
                        tool_name = tc.get("name") or tc.get("displayName", "")
                        args = tc.get("args", {})
                        args_text = json.dumps(args) if args else ""

                        # Assistant message invoking the tool
                        messages.append(Message(
                            role="assistant",
                            content=args_text,
                            timestamp=ts,
                            tool_name=tool_name,
                            token_usage=token_usage,
                        ))
                        token_usage = None  # only charge tokens to first call

                        # Tool result
                        result = tc.get("result", [])
                        result_text = tc.get("resultDisplay", "")
                        if isinstance(result_text, dict):
                            result_text = result_text.get("fileDiff", "") or json.dumps(result_text)
                        elif not isinstance(result_text, str):
                            result_text = str(result_text)
                        if not result_text and result:
                            # Extract text from nested functionResponse if present
                            try:
                                resp = result[0]["functionResponse"]["response"]["output"]
                                result_text = str(resp)
                            except (KeyError, IndexError, TypeError):
                                result_text = json.dumps(result)

                        messages.append(Message(
                            role="tool_result",
                            content=result_text,
                            timestamp=ts,
                            tool_name=tool_name,
                        ))

                if content:
                    messages.append(Message(
                        role="assistant",
                        content=content,
                        timestamp=ts,
                        token_usage=token_usage,
                    ))

        if not messages:
            return []

        return [Session(
            id=session_id,
            agent_name="gemini",
            title=title or session_id,
            start_time=start_time,
            end_time=end_time,
            messages=messages,
            model=model,
            project_dir=project_dir,
            source_path=str(filepath),
        )]
