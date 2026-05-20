"""OpenClaw-style local skill discovery for Luna."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import BASE_DIR, DATA_DIR

SKILL_DIRS = [BASE_DIR / "skills", DATA_DIR / "workspace" / "skills"]


def _read_skill(folder: Path) -> dict[str, Any] | None:
    md = folder / "SKILL.md"
    meta_file = folder / "skill.json"
    if not md.exists() and not meta_file.exists():
        return None

    meta: dict[str, Any] = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    body = md.read_text(encoding="utf-8", errors="replace") if md.exists() else ""
    title = meta.get("name") or folder.name
    description = meta.get("description")
    if not description:
        for line in body.splitlines():
            clean = line.strip("# ").strip()
            if clean:
                description = clean
                break

    return {
        "id": meta.get("id") or folder.name,
        "name": title,
        "description": description or "",
        "permissions": meta.get("permissions", []),
        "tools": meta.get("tools", []),
        "path": str(folder),
        "body": body[:4000],
    }


def list_skills() -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for root in SKILL_DIRS:
        root.mkdir(parents=True, exist_ok=True)
        for folder in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
            skill = _read_skill(folder)
            if skill:
                skills.append(skill)
    return skills


def get_skills_prompt() -> str:
    skills = list_skills()
    if not skills:
        return "No local skills are installed yet."
    lines = ["Installed local skills:"]
    for skill in skills:
        perms = ", ".join(skill.get("permissions") or []) or "none"
        tools = ", ".join(skill.get("tools") or []) or "none"
        lines.append(f"- {skill['id']}: {skill['description']} (permissions: {perms}; tools: {tools})")
    return "\n".join(lines)
