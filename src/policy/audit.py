"""Audit log"""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path
from datetime import datetime, timezone


class AuditLog:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, details: dict[str, Any]) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
            
    def read_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        
        lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines[-limit:]:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                
        return entries