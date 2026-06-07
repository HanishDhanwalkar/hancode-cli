"""
Agent Orchestrator:
manages 
    - conversation, 
    - tools
    - memory
    - modes
    
"""

from __future__ import annotations

from typing import Any, Callable
from pathlib import Path

from src.models.entities import SessionEvent, EventType


class AgentOrchestrator:
    def __init__(
        self,
        root: Path,
        workspace_id: str,
        trust_level,  # TODO: assign type
        config,  # TODO: assign type
        session_store: 
    ) -> None:
        self.root = root
        self.workspace_id = workspace_id
        self.trust_level = trust_level
        self.config = config

    def _load_memory(self):
        memory_path = self.config["memory_path"]
        if not memory_path:
            memory_path = self.root / ".hancoder" / "MEMORY.md"

        self.project_memory = ""
        if memory_path.exists():
            self.project_memory = memory_path.read_text(encoding="utf-8")

    def initise_index(self) -> int:
        pass

    def _emit_status(self, msg: str) -> None:
        self.on_status(msg)
        self._append_event(SessionEvent(
            event_type=EventType.STATUS, content=msg))

    def _append_event(self, event: SessionEvent):
        self.session.events.append(event)

    def set_mode(self, mode: str) -> None:
        self.session.mode = mode