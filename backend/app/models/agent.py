from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"


class AgentRegister(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    role: str = Field(min_length=2, max_length=80)
    skills: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStatusUpdate(BaseModel):
    status: AgentStatus


class Agent(BaseModel):
    agent_id: str
    name: str
    role: str
    skills: list[str] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.ONLINE
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

