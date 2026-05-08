# src/agent_archive/parsers/pi.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Message, Session
from .base import BaseParser


class PiParser(BaseParser):
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or (Path.home() / ".pi" / "agent")

    def discover(self) -> List[Path]:
        sessions_dir = self.base_path / "sessions"
        if not sessions_dir.exists():
            return []
        return sorted(sessions_dir.glob("*/*.jsonl"))

    def parse(self, filepath: Path) -> List[Session]:
        messages: List[Message] = []
        session_id = None
        cwd = None
        model = None
        first_ts = None
        last_ts = None

        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record_type = record.get("type")

                if record_type == "session":
                    session_id = record.get("id")
                    cwd = record.get("cwd")
                    ts_str = record.get("timestamp")
                    if ts_str:
                        first_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    continue

                ts_str = record.get("timestamp")
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
                if ts:
                    if first_ts is None:
                        first_ts = ts

                # ── Meta events ──────────────────────────────────────────

                if record_type == "model_change":
                    provider = record.get("provider", "")
                    model_id = record.get("modelId", "")
                    if model is None:
                        model = model_id
                    else:
                        messages.append(Message(
                            role="meta",
                            meta_subtype="model_change",
                            content=f"Switched model to **{provider}/{model_id}**",
                            timestamp=ts,
                        ))
                    continue

                if record_type == "thinking_level_change":
                    level = record.get("thinkingLevel", "")
                    messages.append(Message(
                        role="meta",
                        meta_subtype="thinking_level_change",
                        content=f"Thinking level set to **{level}**",
                        timestamp=ts,
                    ))
                    continue

                if record_type == "compaction":
                    summary = record.get("summary", "")
                    tokens_before = record.get("tokensBefore", 0)
                    messages.append(Message(
                        role="meta",
                        meta_subtype="compaction",
                        content=f"Context compacted — {tokens_before} tokens summarized." +
                                (f"\n\n> {summary}" if summary else ""),
                        timestamp=ts,
                    ))
                    continue

                if record_type == "branch_summary":
                    summary = record.get("summary", "")
                    from_id = record.get("fromId", "")
                    messages.append(Message(
                        role="meta",
                        meta_subtype="branch_summary",
                        content=f"Branch switched (from {from_id})" +
                                (f"\n\n> {summary}" if summary else ""),
                        timestamp=ts,
                    ))
                    continue

                if record_type == "session_info":
                    name = record.get("name", "")
                    if name:
                        messages.append(Message(
                            role="meta",
                            meta_subtype="session_info",
                            content=f"Session named **{name}**",
                            timestamp=ts,
                        ))
                    continue

                if record_type == "label":
                    label = record.get("label")
                    target_id = record.get("targetId", "")
                    if label:
                        messages.append(Message(
                            role="meta",
                            meta_subtype="label",
                            content=f"Bookmark **{label}** set on {target_id}",
                            timestamp=ts,
                        ))
                    continue

                if record_type != "message":
                    continue

                if ts:
                    last_ts = ts

                msg = record.get("message", {})
                role = msg.get("role", "")

                if role == "user":
                    content_blocks = msg.get("content", [])
                    text = "\n\n".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                    messages.append(Message(role="user", content=text, timestamp=ts))

                elif role == "assistant":
                    msg_model = msg.get("model")
                    if msg_model and model is None:
                        model = msg_model
                    usage = msg.get("usage")
                    token_usage = None
                    if usage:
                        token_usage = {"input": usage.get("input", 0), "output": usage.get("output", 0)}

                    content_blocks = msg.get("content", [])
                    text_parts = []
                    tool_name = None
                    for block in content_blocks:
                        btype = block.get("type")
                        if btype == "text":
                            text_parts.append(block.get("text", ""))
                        elif btype == "thinking":
                            text_parts.append(block.get("thinking", ""))
                        elif btype == "toolCall":
                            tool_name = block.get("name")
                            args = block.get("arguments", {})
                            text_parts.append(json.dumps(args) if args else "")

                    messages.append(Message(
                        role="assistant",
                        content="\n\n".join(text_parts) if text_parts else "",
                        timestamp=ts,
                        tool_name=tool_name,
                        token_usage=token_usage,
                    ))

                elif role == "toolResult":
                    content_blocks = msg.get("content", [])
                    text = "\n\n".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                    messages.append(Message(
                        role="tool_result",
                        content=text,
                        timestamp=ts,
                        tool_name=msg.get("toolName"),
                    ))

                elif role == "bashExecution":
                    output = msg.get("output", "")
                    command = msg.get("command", "")
                    if msg.get("excludeFromContext"):
                        # !!-prefixed commands are hidden from LLM context
                        messages.append(Message(
                            role="tool_result",
                            content=output,
                            timestamp=ts,
                            tool_name="bash",
                        ))

                elif role == "custom":
                    custom_type = msg.get("customType", "")
                    if custom_type:
                        messages.append(Message(
                            role="meta",
                            meta_subtype="custom",
                            content=f"Extension event: **{custom_type}**",
                            timestamp=ts,
                        ))

                elif role == "branchSummary":
                    messages.append(Message(
                        role="meta",
                        meta_subtype="branch_summary",
                        content=f"Branch summary: {msg.get('summary', '')}",
                        timestamp=ts,
                    ))

                elif role == "compactionSummary":
                    messages.append(Message(
                        role="meta",
                        meta_subtype="compaction",
                        content=f"Context compacted: {msg.get('summary', '')}",
                        timestamp=ts,
                    ))

        if not messages:
            return []

        title = session_id or filepath.stem

        session = Session(
            id=session_id or filepath.stem,
            agent_name="pi",
            title=title,
            start_time=first_ts or datetime.now(),
            end_time=last_ts,
            messages=messages,
            model=model,
            project_dir=cwd,
            source_path=str(filepath),
        )
        return [session]
