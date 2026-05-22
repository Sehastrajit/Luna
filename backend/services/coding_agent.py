"""
Ollama-powered coding agent with ReAct (Reason + Act) loop.

Uses a code-specialized model (settings.coding_model) and exposes five
workspace-scoped tools:
  code_read_file   — read a file
  code_write_file  — write / overwrite a file
  code_list_files  — list a directory
  code_search      — grep for a pattern across workspace files
  code_run_shell   — run a shell command (requires user confirmation)
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, AsyncGenerator

import httpx

from backend.config import DATA_DIR, settings

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=5.0)

WORKSPACE_ROOT = DATA_DIR / "workspace"

# ── Coding system prompt ───────────────────────────────────────────────────────

_SYSTEM = """You are a coding assistant powered by Ollama, running inside the Luna AI platform.

## Tools
Emit a JSON block anywhere in your reply to call a tool:
{"tool_call": {"tool": "<name>", "args": {<params>}}}

Available tools:
  code_read_file(path)               — Read a workspace file
  code_write_file(path, content)     — Write / overwrite a workspace file
  code_list_files(path)              — List a workspace directory (path="" = root)
  code_search(pattern, path)         — Regex / text search across workspace files
  code_run_shell(command)            — Run a shell command (needs user approval)

## Rules
1. Think before writing code. Read existing files before overwriting.
2. Write clean, idiomatic code. Keep comments minimal and meaningful.
3. Wrap code in markdown fences (```language ... ```).
4. For shell commands, prefer read-only first; destructive actions require approval.
5. After completing a task, describe what changed and any recommended next steps.
6. Keep prose concise — developers prefer working code over long explanations.
"""


# ── Workspace helpers ──────────────────────────────────────────────────────────

def _safe_path(rel: str) -> Path:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    p = (WORKSPACE_ROOT / rel).resolve()
    if not str(p).startswith(str(WORKSPACE_ROOT.resolve())):
        raise ValueError(f"Path escapes workspace: {rel}")
    return p


def tool_read_file(path: str) -> str:
    try:
        p = _safe_path(path)
        if not p.exists():
            return f"error: file not found: {path}"
        size = p.stat().st_size
        if size > 100_000:
            return f"error: file too large ({size} bytes). Use code_search to locate specific sections."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"error: {e}"


def tool_write_file(path: str, content: str) -> str:
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"written: {path} ({len(content)} chars)"
    except Exception as e:
        return f"error: {e}"


def tool_list_files(path: str = "") -> str:
    try:
        p = _safe_path(path) if path else WORKSPACE_ROOT
        if not p.exists():
            return f"error: directory not found: {path or '(workspace root)'}"
        items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = [
            f"{'[dir]  ' if item.is_dir() else '[file] '}{item.name}"
            for item in items[:100]
        ]
        return "\n".join(lines) or "(empty)"
    except Exception as e:
        return f"error: {e}"


def tool_search(pattern: str, path: str = "") -> str:
    try:
        root = _safe_path(path) if path else WORKSPACE_ROOT
        results: list[str] = []
        for fp in root.rglob("*"):
            if not fp.is_file() or fp.stat().st_size > 100_000:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if re.search(pattern, line):
                        rel = fp.relative_to(WORKSPACE_ROOT)
                        results.append(f"{rel}:{i}: {line.strip()}")
                        if len(results) >= 50:
                            break
            except Exception:
                pass
            if len(results) >= 50:
                break
        return "\n".join(results) or "no matches"
    except Exception as e:
        return f"error: {e}"


def tool_run_shell(command: str) -> str:
    try:
        WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
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
        return "error: command timed out after 30 seconds"
    except Exception as e:
        return f"error: {e}"


# ── Tool dispatcher ────────────────────────────────────────────────────────────

def execute_coding_tool(tool_name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Return (result_text, requires_user_confirmation)."""
    if tool_name == "code_read_file":
        return tool_read_file(args.get("path", "")), False
    if tool_name == "code_write_file":
        return tool_write_file(args.get("path", ""), args.get("content", "")), False
    if tool_name == "code_list_files":
        return tool_list_files(args.get("path", "")), False
    if tool_name == "code_search":
        return tool_search(args.get("pattern", ""), args.get("path", "")), False
    if tool_name == "code_run_shell":
        return tool_run_shell(args.get("command", "")), True
    return f"unknown tool: {tool_name}", False


# ── JSON tool-call parser (mirrors chat.py logic) ─────────────────────────────

def _scan_json_object(text: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
        elif c == "\\" and in_string:
            escape = True
        elif c == '"':
            in_string = not in_string
        elif not in_string:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def _parse_tool_call(response: str) -> dict | None:
    i = 0
    while i < len(response):
        if response[i] != "{":
            i += 1
            continue
        end = _scan_json_object(response, i)
        if end is None:
            break
        candidate = response[i : end + 1]
        if '"tool_call"' in candidate:
            try:
                obj = json.loads(candidate)
                tc = obj.get("tool_call")
                if tc and "tool" in tc:
                    return tc
            except Exception:
                pass
        i += 1
    return None


def _strip_tool_call(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            out.append(text[i])
            i += 1
            continue
        end = _scan_json_object(text, i)
        if end is None:
            out.append(text[i])
            i += 1
            continue
        candidate = text[i : end + 1]
        if '"tool_call"' in candidate:
            try:
                obj = json.loads(candidate)
                if obj.get("tool_call") and "tool" in obj["tool_call"]:
                    out.append(" ")
                    i = end + 1
                    continue
            except Exception:
                pass
        out.append(text[i])
        i += 1
    return "".join(out).strip()


# ── Main streaming generator ───────────────────────────────────────────────────

async def stream_coding_agent(
    messages: list[dict],
    *,
    auto_confirm_shell: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    Run the coding agent with a ReAct loop.

    Yields event dicts:
      {"type": "token",                "content": str}
      {"type": "tool_call",            "tool": str, "args": dict}
      {"type": "tool_result",          "tool": str, "result": str}
      {"type": "confirmation_required","tool": str, "args": dict}
      {"type": "error",                "message": str}
      {"type": "done"}
    """
    loop_messages = list(messages)
    max_iter = settings.coding_max_iterations

    for _iteration in range(max_iter):
        full_response = ""
        # Buffer tokens when a tool_call JSON might be forming mid-stream
        token_buffer: list[str] = []
        in_possible_json = False

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            payload = {
                "model": settings.coding_model,
                "messages": [{"role": "system", "content": _SYSTEM}] + loop_messages,
                "stream": True,
                "think": False,
                "options": {
                    "temperature": 0.15,
                    "top_p": 0.9,
                    "repeat_penalty": 1.05,
                    "num_ctx": 8192,
                    "num_predict": 4096,
                },
            }
            try:
                async with client.stream(
                    "POST",
                    f"{settings.ollama_base_url}/api/chat",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full_response += token
                            # Once we see `{"tool_call"` start buffering instead
                            # of streaming, to avoid emitting partial JSON to UI
                            if not in_possible_json and '{"tool_call"' in full_response:
                                in_possible_json = True
                                # Flush anything before the JSON block
                                pre = full_response[: full_response.find('{"tool_call"')].strip()
                                if pre:
                                    yield {"type": "token", "content": pre}
                            elif not in_possible_json:
                                yield {"type": "token", "content": token}
                        if data.get("done"):
                            break
            except Exception as exc:
                yield {"type": "error", "message": str(exc)}
                return

        # Detect tool call in the completed response
        tc = _parse_tool_call(full_response)

        if not tc:
            # No tool call — yield any buffered suffix and finish
            if in_possible_json:
                suffix = _strip_tool_call(full_response).strip()
                if suffix:
                    yield {"type": "token", "content": suffix}
            yield {"type": "done"}
            return

        # We have a tool call — yield visible text (before JSON block) if any
        visible = _strip_tool_call(full_response).strip()
        if visible and not in_possible_json:
            yield {"type": "token", "content": visible}
        elif visible and in_possible_json:
            # Pre-JSON text was already flushed; yield post-JSON suffix
            pass

        tool_name = tc.get("tool", "")
        args = tc.get("args", {})

        yield {"type": "tool_call", "tool": tool_name, "args": args}

        result, needs_confirm = execute_coding_tool(tool_name, args)

        if needs_confirm and not auto_confirm_shell:
            yield {"type": "confirmation_required", "tool": tool_name, "args": args}
            result = "Skipped — awaiting user confirmation before running shell command."

        yield {"type": "tool_result", "tool": tool_name, "result": result[:4000]}

        # Feed result back into conversation and loop
        loop_messages.append({"role": "assistant", "content": full_response})
        loop_messages.append({
            "role": "user",
            "content": f"Tool result for {tool_name}:\n{result}\n\nContinue.",
        })

    yield {"type": "done"}
