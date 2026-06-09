"""Project config"""

from __future__ import annotations

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


# =======================
# Default values
# =======================

DEFAULT_IGNORE_GLOBS = []

DEFAULT_ALLOWED_GLOBS = ["**/*"] 

DEFAULT_TEST_COMMANDS:list[str] = []

# =======================

def get_project_root() -> Path:
    return Path(__file__).parent.parent

@dataclass
class ProjectConfig:
    project_name:str = ""
    default_provider:str = "ollama" 
    default_model:str = ""
    
    # paths
    memory_path: Path = get_project_root() / ".hancode" / "MEMORY.md"
    
    allowed_globs: list[str] = field(default_factory=lambda: DEFAULT_ALLOWED_GLOBS.copy())
    ignored_globs: list[str] = field(default_factory=lambda: DEFAULT_IGNORE_GLOBS.copy())
    test_commands: list[str] = field(default_factory=lambda: DEFAULT_TEST_COMMANDS.copy())
    build_command: list[str] = field(default_factory=list)
    format_command: list[str] = field(default_factory=list)
    permission_policy: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def load(cls, hancode_dir: Path) -> ProjectConfig:
        config_path = hancode_dir / "config.json"
        if not config_path.exists():
            return cls()  # return default config if no config file
        
        data = json.loads(config_path.read_text(encoding="utf-8"))
        
        return cls(
            project_name=data.get("project_name", ""),
            default_provider=data.get("default_provider", "ollama"),
            default_model=data.get("default_model", ""),
            memory_path=Path(data.get("memory_path", str(get_project_root() / ".hancode" / "MEMORY.md"))),
            allowed_globs=data.get("allowed_globs", DEFAULT_ALLOWED_GLOBS.copy()),
            ignored_globs=data.get("ignored_globs", DEFAULT_IGNORE_GLOBS.copy()),
            test_commands=data.get("test_commands", DEFAULT_TEST_COMMANDS.copy()),
            build_command=data.get("build_command", []),
            format_command=data.get("format_command", []),
            permission_policy=data.get("permission_policy", {}),
        )
    
    def save(self, hancode_dir: Path) -> None:
        hancode_dir.mkdir(parents=True, exist_ok=True)
        config_path = hancode_dir / "config.json"
        config_data = {
            "project_name": self.project_name,
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "memory_path": str(self.memory_path),
            "allowed_globs": self.allowed_globs,
            "ignored_globs": self.ignored_globs,
            "test_commands": self.test_commands,
            "build_command": self.build_command,
            "format_command": self.format_command,
            "permission_policy": self.permission_policy,
        }
        config_path.write_text(
            json.dumps(
                config_data, 
                indent=4
            ),
            encoding="utf-8"
        )
        
def default_memory_content() -> str:
    return """# Project Memory
Note: `Add durable project information here in markdown format. The agent loads this at agent startup`
""".strip()


if __name__ == "__main__":
    config = ProjectConfig()
    print(config.memory_path)