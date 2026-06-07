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



class AgentOrchestrator:
    def __init__(
        self,
        root: Path,
        workspace_id: str,
        trust_level, # TODO: assign type
        config,# TODO: assign type
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
                
                
        