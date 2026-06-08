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

from src.models.entities import (
    SessionEvent, 
    EventType
)
from src.session.store import SessionStore
from policy.audit import AuditLog

class AgentOrchestrator:
    def __init__(
        self,
        root: Path,
        workspace_id: str,
        trust_level,  # TODO: assign type
        config,  # TODO: assign type
        session_store: SessionStore,
        audit: AuditLog
    ) -> None:
        self.root = root
        self.workspace_id = workspace_id
        self.trust_level = trust_level
        self.config = config
        self.session_store = session_store
        self.audit = audit

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
        self.session_store.save(self.session)
        self.audit.record("mode_change", {"mode": mode.value})
        
    def switch_provider(self, provider_name: str, model_name: str) -> str:
        from src.providers import get_provider
        
        self.session.model = provider_name
        self.session_store.save(self.session)
        self.audit.record("provider_switch", {"provider": provider_name, "model": model_name})