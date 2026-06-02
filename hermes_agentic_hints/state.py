
"""Tiny session-store shim used by the MCP server helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

try:
    from .constants import get_proj_home
except ImportError:
    from constants import get_proj_home


class SessionDB:
    """Minimal file-backed session database placeholder.

    The starter project only needs a lightweight adapter that can safely
    return an empty transcript when no session archive exists yet.
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).expanduser() if root else get_proj_home()

    def _session_path(self, session_id: str) -> Path:
        return self.root / "sessions" / f"{session_id}.json"

    def get_messages(self, session_id: str) -> List[dict[str, Any]]:
        path = self._session_path(session_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            messages = payload.get("messages", [])
            if isinstance(messages, list):
                return [item for item in messages if isinstance(item, dict)]
        return []
