"""Coding agent tool implementations and dispatcher."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR
from backend.services.coding.indexer import _INDEX_IGNORE

WORKSPACE_ROOT = DATA_DIR / "workspace"


def _make_safe_path(root: Path):
    def _safe(rel: str) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        p = (root / rel).resolve()
        if not str(p).startswith(str(root.resolve())):
            raise ValueError(f"Path escapes workspace: {rel}")
        return p
    return _safe


def tool_read_file(path: str, root: Path | None = None) -> str:
    _root = root or WORKSPACE_ROOT
    sp = _make_safe_path(_root)
    try:
        p = sp(path)
        if not p.exists():
            return f"error: file not found: {path}"
        size = p.stat().st_size
        if size > 100_000:
            return f"error: file too large ({size} bytes). Use code_search to locate specific sections."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"error: {e}"


def tool_write_file(path: str, content: str, root: Path | None = None) -> str:
    _root = root or WORKSPACE_ROOT
    sp = _make_safe_path(_root)
    try:
        p = sp(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"written: {path} ({len(content)} chars)"
    except Exception as e:
        return f"error: {e}"


def tool_list_files(path: str = "", root: Path | None = None) -> str:
    _root = root or WORKSPACE_ROOT
    sp = _make_safe_path(_root)
    try:
        p = sp(path) if path else _root
        if not p.exists():
            return f"error: directory not found: {path or '(workspace root)'}"
        items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = [
            f"{'[dir]  ' if item.is_dir() else '[file] '}{item.name}"
            for item in items[:200]
        ]
        return "\n".join(lines) or "(empty)"
    except Exception as e:
        return f"error: {e}"


def tool_search(pattern: str, path: str = "", root: Path | None = None) -> str:
    _root = root or WORKSPACE_ROOT
    sp = _make_safe_path(_root)
    try:
        search_root = sp(path) if path else _root
        results: list[str] = []
        for fp in search_root.rglob("*"):
            if any(p in _INDEX_IGNORE for p in fp.parts):
                continue
            if not fp.is_file() or fp.stat().st_size > 100_000:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if re.search(pattern, line):
                        try:
                            rel = fp.relative_to(_root)
                        except ValueError:
                            rel = fp
                        results.append(f"{rel}:{i}: {line.strip()}")
                        if len(results) >= 60:
                            break
            except Exception:
                pass
            if len(results) >= 60:
                break
        return "\n".join(results) or "no matches"
    except Exception as e:
        return f"error: {e}"


def tool_run_shell(command: str, root: Path | None = None) -> str:
    _root = root or WORKSPACE_ROOT
    _root.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        parts: list[str] = []
        if proc.stdout.strip():
            parts.append(f"stdout:\n{proc.stdout.strip()[:4000]}")
        if proc.stderr.strip():
            parts.append(f"stderr:\n{proc.stderr.strip()[:2000]}")
        if not parts:
            parts.append(f"(exit code {proc.returncode})")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return "error: command timed out after 60 seconds"
    except Exception as e:
        return f"error: {e}"


def execute_coding_tool(
    tool_name: str,
    args: dict[str, Any],
    workspace_root: Path | None = None,
) -> tuple[str, bool]:
    """Return (result_text, requires_user_confirmation)."""
    r = workspace_root
    if tool_name == "code_read_file":
        return tool_read_file(args.get("path", ""), r), False
    if tool_name == "code_write_file":
        return tool_write_file(args.get("path", ""), args.get("content", ""), r), False
    if tool_name == "code_list_files":
        return tool_list_files(args.get("path", ""), r), False
    if tool_name == "code_search":
        return tool_search(args.get("pattern", ""), args.get("path", ""), r), False
    if tool_name == "code_run_shell":
        return tool_run_shell(args.get("command", ""), r), True
    return f"unknown tool: {tool_name}", False
