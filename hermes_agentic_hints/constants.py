from __future__ import annotations

import os
from pathlib import Path

try:
    from .config import ProjectName, MCPName, get_proj_home as _config_proj_home
except ImportError:
    from config import ProjectName, MCPName, get_proj_home as _config_proj_home

def get_proj_home() -> Path:
    """Return the project data directory used by this starter framework."""
    root = os.getenv("AGENTIC_HOME")
    if root:
        return Path(root).expanduser()
    return _config_proj_home()
