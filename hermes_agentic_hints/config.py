"""Lightweight configuration helpers for the local agentic framework."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


ProjectName = "agentic_hints"
MCPName = f"{ProjectName}_mcp"


def get_proj_home() -> Path:
    """Return the project-local data directory."""
    root = os.getenv("AGENTIC_HOME")
    return Path(root).expanduser() if root else Path.home() / ".agentic_hints"


def get_config_path() -> Path:
    return get_proj_home() / "config.json"


def load_config() -> Dict[str, Any]:
    """Load the local JSON config, returning an empty dict when absent."""
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Persist the local JSON config."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
