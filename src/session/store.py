"""Session History Pesistence"""

from __future__ import annotations

import json
import uuid
from typing import Any
from dataclasses import asdict
from pathlib import Path

from src.models.entities import (
    Session,
    SessionEvent,
    EventType,
    Mode,
    Plan,
    Patch
)

# =======================
# helpers
# =======================

def _event_to_dict(event: SessionEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "content": event.content,
        "timestamp": event.timestamp,
        "tool_name": event.tool_name,
        "tool_input": event.tool_input,
        "tool_calls": event.tool_calls,
        "refernced_files": event.refernced_files,
    }

def _parse_event(data: dict) -> SessionEvent:
    event_type = data.get("event_type") or data.get("role", "internal")
    
    try:
        et = EventType(event_type)
    except ValueError:
        et = EventType.INTERNAL
    
    return SessionEvent(
        event_type=et,
        content=data.get("content", ""),
        timestamp=data.get("timestamp", ""),
        tool_name=data.get("tool_name", None),
        tool_input=data.get("tool_input", {}),
        tool_calls=data.get("tool_calls", []),
        refernced_files=data.get("refernced_files", [])
    )
        
# =======================
    

class SessionStore:
    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def create(self, workspace_id: str, model: str = "") -> Session:
        session = Session(
            session_id = str(uuid.uuid4())[:12],
            workspace_id=workspace_id,
            model=model
        )
        self.save(session)
        return session
    
    def save(self, session: Session) -> None:
        session_path = self.session_dir / f"{session.session_id}.json"
        data = {
            "session_id": session.session_id,
            "workspace_id": session.workspace_id,
            "mode": session.mode.value,
            "user_goal": session.user_goal,
            "events": [_event_to_dict(event) for event in session.events],
            "plans": [asdict(plan) for plan in session.plans],
            "patchs": [asdict(patch) for patch in session.patchs],
            "model": session.model,
            "started_at": session.started_at
        }
        session_path.write_text(session.json())
    
    def load(self, session_id:str) -> Session | None:
        path = self.session_dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        
        if "events" in data:
            events = [_parse_event(e) for e in data["events"]]
        
        return Session(
            session_id=data["session_id"],
            workspace_id=data["workspace_id"],
            mode=Mode(data.get("mode", "chat")),
            user_goal=data.get("user_goal", ""),
            events=events,
            plans=[Plan(**p) for p in data.get("plans",[])],
            patchs=[Patch(*p) for p in data.get("patchs",[])],
            model=data.get("model", ""),
            started_at=data.get("started_at", "")
        )
    
    def list_sessions(self) -> list[str]:
        return sorted(
            [f.stem for f in self.session_dir.glob("*.json")],
            reverse=True
        )
