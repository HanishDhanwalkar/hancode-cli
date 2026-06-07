"""Project config"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


def get_project_root() -> Path:
    return Path(__file__).parent.parent

@dataclass
class ProjectConfig:
    memory_path: Path = get_project_root() / ".hancoder" / "MEMORY.md"
    

if __name__ == "__main__":
    config = ProjectConfig()
    print(config.memory_path)