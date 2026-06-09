
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TrustLevel(str, Enum):
    UNTRUSTED = "untrusted"
    READ_ONLY = "trusted_read_only"
    EDITABLE = "trusted_editable"
    AUTOMATED = "trusted_automated"


@dataclass
class Workspace:
    workspace_id: str
    root_path: str
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    is_git_repo: bool = False
    git_branch: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EventType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATUS = "status"
    INTERNAL = "internal"


class Mode(str, Enum):
    CHAT = "chat"
    PLAN = "plan"
    EDIT = "edit"
    REVIEW = "review"
    DEBUG = "debug"


@dataclass
class Plan:
    plan_id: str
    user_goal: str
    content: str
    files_affected: list[str] = field(default_factory=list)
    approval_status: str = "pending"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class Patch:
    patch_id: str
    files_changed: list[str]
    summary: str
    diff_content: str
    risk_level: str = "medium"
    approval_status: str = "pending"
    appplied: bool = False
    plan_id: str


@dataclass
class SessionEvent:

    """Single entry in the session timeline; distinct from provider API roles"""

    event_type: str
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    refernced_files: list[str] = field(default_factory=list)


@dataclass
class Session:
    session_id: str
    workspace_id: str
    mode: Mode = Mode.CHAT
    user_goal: str = ""
    events: list[SessionEvent] = field(default_factory=list)
    plans: list[Plan] = field(default_factory=list)
    patches: list[Patch] = field(default_factory=list)
    model: str = field(default_factory=str)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
