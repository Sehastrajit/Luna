"""Controlled agent workspace helpers.

Luna can read/write inside data/workspace without receiving arbitrary disk access.
"""
from __future__ import annotations

from pathlib import Path

from backend.config import DATA_DIR

WORKSPACE_DIR = DATA_DIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_workspace_path(path: str) -> Path:
    clean = (path or "").replace("\\", "/").lstrip("/")
    target = (WORKSPACE_DIR / clean).resolve()
    root = WORKSPACE_DIR.resolve()
    if target != root and root not in target.parents:
        raise ValueError("Path escapes Luna workspace")
    return target


def list_workspace(path: str = "") -> list[dict]:
    root = _resolve_workspace_path(path)
    if not root.exists():
        return []
    if root.is_file():
        root = root.parent
    items = []
    for item in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        rel = item.relative_to(WORKSPACE_DIR).as_posix()
        items.append({
            "path": rel,
            "name": item.name,
            "type": "file" if item.is_file() else "directory",
            "size": item.stat().st_size if item.is_file() else None,
        })
    return items


def read_workspace_file(path: str, max_chars: int = 20_000) -> str:
    target = _resolve_workspace_path(path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(path)
    return target.read_text(encoding="utf-8", errors="replace")[:max_chars]


def write_workspace_file(path: str, content: str) -> dict:
    target = _resolve_workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content or "", encoding="utf-8")
    return {
        "path": target.relative_to(WORKSPACE_DIR).as_posix(),
        "size": target.stat().st_size,
    }
