# src/agent_archive/parsers/claude_code.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser


class ClaudeCodeParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".claude"

    def discover(self) -> List[Path]:
        projects_dir = self.base_path / "projects"
        if not projects_dir.exists():
            return []
        return sorted(projects_dir.glob("*/*.jsonl"))

    def parse(self, filepath: Path) -> List[Session]:
        messages: List[Message] = []
        slug = None
        model = None
        last_model = None
        cwd = None
        session_id = None
        first_ts = None
        last_ts = None

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record_type = record.get("type")

                ts_str = record.get("timestamp")
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
                if ts and first_ts is None:
                    first_ts = ts
                if ts:
                    last_ts = ts

                if slug is None:
                    slug = record.get("slug")
                if cwd is None:
                    cwd = record.get("cwd")
                if session_id is None:
                    session_id = record.get("sessionId")

                # ── Meta events ──────────────────────────────────────────

                if record_type == "system":
                    subtype = record.get("subtype", "")
                    if subtype == "turn_duration":
                        duration_s = (record.get("durationMs", 0) or 0) / 1000
                        messages.append(Message(
                            role="meta",
                            meta_subtype="turn_duration",
                            content=f"Turn completed in **{duration_s:.1f}s**",
                            timestamp=ts,
                        ))
                    # skip other system subtypes (init, permission, etc.)
                    continue

                if record_type == "file-history-snapshot":
                    # skip — not useful for reading
                    continue

                if record_type == "last-prompt":
                    # skip — internal marker
                    continue

                if record_type not in ("user", "assistant"):
                    continue

                msg = record.get("message", {})
                role = msg.get("role", record_type)
                content = msg.get("content", "")

                if isinstance(content, str):
                    messages.append(Message(role=role, content=content, timestamp=ts))
                elif isinstance(content, list):
                    if role == "user":
                        for block in content:
                            if block.get("type") == "tool_result":
                                block_content = block.get("content", "")
                                if isinstance(block_content, list):
                                    parts = []
                                    for item in block_content:
                                        if item.get("type") == "text":
                                            parts.append(item.get("text", ""))
                                        elif item.get("type") == "tool_reference":
                                            parts.append(f"[tool_reference: {item.get('tool_name', '')}]")
                                        else:
                                            parts.append(json.dumps(item))
                                    block_content = "\n\n".join(parts)
                                elif not isinstance(block_content, str):
                                    block_content = json.dumps(block_content)
                                messages.append(Message(
                                    role="tool_result",
                                    content=block_content,
                                    timestamp=ts,
                                ))
                    elif role == "assistant":
                        msg_model = msg.get("model")
                        if msg_model:
                            if model is None:
                                model = msg_model
                            elif msg_model != last_model and last_model is not None:
                                messages.append(Message(
                                    role="meta",
                                    meta_subtype="model_change",
                                    content=f"Switched model to **{msg_model}**",
                                    timestamp=ts,
                                ))
                            last_model = msg_model
                        usage = msg.get("usage")
                        token_usage = None
                        if usage:
                            token_usage = {
                                "input": usage.get("input_tokens", 0),
                                "output": usage.get("output_tokens", 0),
                            }

                        text_parts = []
                        tool_name = None
                        for block in content:
                            btype = block.get("type")
                            if btype == "text":
                                text_parts.append(block.get("text", ""))
                            elif btype == "thinking":
                                text_parts.append(block.get("thinking", ""))
                            elif btype == "tool_use":
                                tool_name = block.get("name")
                                tool_input = block.get("input", {})
                                tool_desc = json.dumps(tool_input) if tool_input else ""
                                text_parts.append(tool_desc)

                        messages.append(Message(
                            role="assistant",
                            content="\n\n".join(text_parts) if text_parts else "",
                            timestamp=ts,
                            tool_name=tool_name,
                            token_usage=token_usage,
                        ))

        if not messages:
            return []

        session = Session(
            id=session_id or filepath.stem,
            agent_name="claude_code",
            title=slug or filepath.stem,
            start_time=first_ts or datetime.now(),
            end_time=last_ts,
            messages=messages,
            model=model,
            project_dir=cwd,
            source_path=str(filepath),
        )
        return [session]
