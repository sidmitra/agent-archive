# src/agent_archive/parsers/copilot.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from ..models import Message, Session
from .base import BaseParser


class CopilotParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or (Path.home() / ".copilot")

    def discover(self) -> List[Path]:
        state_dir = self.base_path / "session-state"
        if not state_dir.exists():
            return []
        results = []
        for session_dir in sorted(state_dir.iterdir()):
            events_file = session_dir / "events.jsonl"
            if events_file.exists():
                results.append(events_file)
        return results

    def parse(self, filepath: Path) -> List[Session]:
        session_dir = filepath.parent
        messages: List[Message] = []
        session_id = None
        model = None
        cwd = None
        title = None
        first_ts = None
        last_ts = None

        workspace_file = session_dir / "workspace.yaml"
        if workspace_file.exists():
            ws = yaml.safe_load(workspace_file.read_text())
            title = ws.get("summary")
            session_id = ws.get("id")
            cwd = ws.get("cwd")

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                etype = event.get("type")
                data = event.get("data", {})
                ts_str = event.get("timestamp")
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
                if ts and first_ts is None:
                    first_ts = ts
                if ts:
                    last_ts = ts

                if etype == "session.start":
                    if session_id is None:
                        session_id = data.get("sessionId")
                    ctx = data.get("context", {})
                    if cwd is None:
                        cwd = ctx.get("cwd")

                elif etype == "session.model_change":
                    new_model = data.get("newModel", "")
                    previous = data.get("previousModel", "")
                    if model is None:
                        model = new_model
                    else:
                        messages.append(Message(
                            role="meta",
                            meta_subtype="model_change",
                            content=f"Switched model to **{new_model}**" +
                                    (f" (from {previous})" if previous else ""),
                            timestamp=ts,
                        ))

                elif etype == "user.message":
                    content = data.get("content", "")
                    messages.append(Message(role="user", content=content, timestamp=ts))

                elif etype == "assistant.message":
                    content = data.get("content", "")
                    tool_requests = data.get("toolRequests", [])
                    output_tokens = data.get("outputTokens")
                    token_usage = {"input": 0, "output": output_tokens} if output_tokens else None

                    if tool_requests:
                        for tr in tool_requests:
                            tool_name = tr.get("name", "")
                            args = tr.get("arguments", {})
                            desc = json.dumps(args) if args else ""
                            messages.append(Message(
                                role="assistant",
                                content=desc,
                                timestamp=ts,
                                tool_name=tool_name,
                                token_usage=token_usage,
                            ))
                    elif content:
                        messages.append(Message(
                            role="assistant",
                            content=content,
                            timestamp=ts,
                            token_usage=token_usage,
                        ))

                elif etype == "tool.execution_complete":
                    result = data.get("result", {})
                    result_content = result.get("content", "")
                    if isinstance(result_content, list):
                        result_content = "\n".join(
                            item.get("text", str(item)) for item in result_content
                        )
                    messages.append(Message(
                        role="tool_result",
                        content=str(result_content),
                        timestamp=ts,
                    ))

        if not messages:
            return []

        session = Session(
            id=session_id or filepath.parent.name,
            agent_name="copilot",
            title=title or session_id or filepath.parent.name,
            start_time=first_ts or datetime.now(),
            end_time=last_ts,
            messages=messages,
            model=model,
            project_dir=cwd,
            source_path=str(filepath),
        )
        return [session]
