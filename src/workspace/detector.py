"""Workspce detection and projecy initialisation"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from src.config import ProjectConfig, default_memory_content
from src.models.entities import TrustLevel, Workspace


def find_git_root(start: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def get_git_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    return ""


def detect_workspace(cwd: Path | None = None) -> Workspace:
    start = cwd or Path.cwd()
    git_root = find_git_root(start)
    root = git_root or start.resolve()
    is_git = git_root is not None

    trust = TrustLevel.UNTRUSTED
    trust_file = root / ".hancode" / "trust"
    if trust_file.exists():
        level = trust_file.read_text(encoding="utf-8").strip()
        try:
            trust = TrustLevel(level)
        except ValueError:
            trust = TrustLevel.READ_ONLY

    return Workspace(
        workspace_id=str(uuid.uuid4()),
        root_path=str(root),
        trust_level=trust,
        is_git_repo=is_git,
        git_branch=get_git_branch(root) if is_git else "",
    )


def initialize_project(root: Path) -> Path:
    hancode_dir = root / ".hancode"
    hancode_dir.mkdir(parents=True, exist_ok=True)
    (hancode_dir / "sessions").mkdir(exist_ok=True)
    (hancode_dir / "checkpoints").mkdir(exist_ok=True)

    config = ProjectConfig(project_name=root.name)
    config.save(hancode_dir)

    memory_path = hancode_dir / "MEMORY.md"
    if not memory_path.exists():
        memory_path.write_text(default_memory_content(), encoding="utf-8")

    return hancode_dir


def set_trust_level(root: Path, level: TrustLevel) -> None:
    hancode_dir = root / ".hancode"
    hancode_dir.mkdir(parents=True, exist_ok=True)
    (hancode_dir / "trust").write_text(level.value, encoding="utf-8")
