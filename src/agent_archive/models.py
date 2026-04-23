from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None
    tool_name: Optional[str] = None
    token_usage: Optional[dict] = None


class Session(BaseModel):
    id: str
    agent_name: str
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    messages: List[Message]
    model: Optional[str] = None
    project_dir: Optional[str] = None
    source_path: Optional[str] = None
