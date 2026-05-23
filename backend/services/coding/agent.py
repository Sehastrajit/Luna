"""
Coding agent main loop — plan + ReAct execution over Ollama.

Events emitted:
  {"type": "workspace_index", "summary": str}
  {"type": "plan",            "summary": str, "steps": [str]}
  {"type": "plan_step",       "index": int,   "status": "running"|"done"}
  {"type": "token",           "content": str}
  {"type": "tool_call",       "tool": str,    "args": dict}
  {"type": "tool_result",     "tool": str,    "result": str}
  {"type": "confirmation_required", "tool": str, "args": dict}
  {"type": "error",           "message": str}
  {"type": "done"}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncGenerator

import httpx

from backend.config import settings
from backend.services.coding.indexer import build_workspace_index
from backend.services.coding.parser import extract_plan, parse_tool_call, strip_tool_call
from backend.services.coding.prompts import PLAN_PROMPT, SYSTEM
from backend.services.coding.tools import WORKSPACE_ROOT, execute_coding_tool

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=5.0)

# Chars to hold back while checking if a token stream is about to emit JSON
_HOLDBACK = 16
_JSON_TRIGGERS = ('{"tool_call"', '{"plan"')


async def stream_coding_agent(
    messages: list[dict],
    *,
    auto_confirm_shell: bool = False,
    workspace_root: Path | None = None,
) -> AsyncGenerator[dict, None]:
    coding_model = await _resolve_model()

    _ws_root = workspace_root or WORKSPACE_ROOT
    _ws_root.mkdir(parents=True, exist_ok=True)

    # ── Workspace index ──────────────────────────────────────────────────────
    ws_index = ""
    if workspace_root:
        try:
            ws_index = build_workspace_index(workspace_root)
            summary = ws_index[:300] + "…" if len(ws_index) > 300 else ws_index
            yield {"type": "workspace_index", "summary": summary}
        except Exception:
            pass

    system_prompt = _build_system_prompt(workspace_root, ws_index)
    loop_messages = list(messages)
    max_iter = max(settings.coding_max_iterations, 20)

    # ── Phase 0: generate plan, inject for execution ─────────────────────────
    plan_steps: list[str] = []
    current_step_index = 0

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            plan_payload = {
                "model": coding_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *loop_messages,
                    {"role": "user", "content": PLAN_PROMPT},
                ],
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1, "num_ctx": 16384, "num_predict": 512},
            }
            pr = await client.post(f"{settings.ollama_base_url}/api/chat", json=plan_payload)
            if pr.status_code == 200:
                plan_text = pr.json().get("message", {}).get("content", "")
                plan_obj = extract_plan(plan_text)
                if plan_obj:
                    plan_steps = plan_obj.get("steps", [])
                    yield {"type": "plan", "summary": plan_obj.get("summary", ""), "steps": plan_steps}
                    steps_str = "\n".join(plan_steps)
                    loop_messages = list(loop_messages) + [
                        {"role": "assistant", "content": plan_text},
                        {"role": "user", "content": (
                            f"Good plan. Now execute it step by step using tools.\n"
                            f"Steps:\n{steps_str}\n\n"
                            "Start with step 1 — emit a tool_call now."
                        )},
                    ]
    except Exception:
        pass  # plan is best-effort; execution continues without it

    # ── Phase 1+: ReAct tool loop ─────────────────────────────────────────────
    for _iteration in range(max_iter):
        full_response = ""
        in_possible_json = False
        hold = ""

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            payload = {
                "model": coding_model,
                "messages": [{"role": "system", "content": system_prompt}] + loop_messages,
                "stream": True,
                "think": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "repeat_penalty": 1.05,
                    "num_ctx": 16384,
                    "num_predict": 8192,
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
                            if in_possible_json:
                                pass  # accumulate silently until done
                            elif any(t in full_response for t in _JSON_TRIGGERS):
                                in_possible_json = True
                                first_brace = min(
                                    full_response.find(t)
                                    for t in _JSON_TRIGGERS
                                    if t in full_response
                                )
                                pre = full_response[:first_brace].strip()
                                if pre:
                                    yield {"type": "token", "content": pre}
                                hold = ""
                            else:
                                hold += token
                                if len(hold) > _HOLDBACK:
                                    yield {"type": "token", "content": hold[:-_HOLDBACK]}
                                    hold = hold[-_HOLDBACK:]

                        if data.get("done"):
                            if hold and not in_possible_json:
                                yield {"type": "token", "content": hold}
                                hold = ""
                            break
            except Exception as exc:
                yield {"type": "error", "message": str(exc)}
                return

        tc = parse_tool_call(full_response)

        if not tc:
            suffix = strip_tool_call(full_response).strip()
            if suffix:
                yield {"type": "token", "content": suffix}
            yield {"type": "done"}
            return

        visible = strip_tool_call(full_response).strip()
        if visible and not in_possible_json:
            yield {"type": "token", "content": visible}

        tool_name = tc.get("tool", "")
        args = tc.get("args", {})

        if plan_steps and current_step_index < len(plan_steps):
            yield {"type": "plan_step", "index": current_step_index, "status": "running"}

        yield {"type": "tool_call", "tool": tool_name, "args": args}

        result, needs_confirm = execute_coding_tool(tool_name, args, workspace_root)

        if needs_confirm and not auto_confirm_shell:
            yield {"type": "confirmation_required", "tool": tool_name, "args": args}
            result = "Skipped — awaiting user confirmation before running shell command."

        yield {"type": "tool_result", "tool": tool_name, "result": result[:4000]}

        if plan_steps and current_step_index < len(plan_steps):
            yield {"type": "plan_step", "index": current_step_index, "status": "done"}
            current_step_index += 1

        loop_messages.append({"role": "assistant", "content": full_response})
        loop_messages.append({
            "role": "user",
            "content": f"Tool result for {tool_name}:\n{result}\n\nContinue with the next step.",
        })

    yield {"type": "done"}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_model() -> str:
    """Use coding_model if available, otherwise fall back to chat model."""
    model = settings.coding_model
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": False},
            )
            if r.status_code == 404:
                return settings.ollama_model
    except Exception:
        pass
    return model


def _build_system_prompt(workspace_root: Path | None, ws_index: str) -> str:
    parts = [SYSTEM]
    if workspace_root:
        parts.append(
            f"\n\n## Active workspace\nPath: {workspace_root}\n"
            "All file paths are relative to this directory unless absolute.\n"
        )
    if ws_index:
        parts.append(f"\n\n## Workspace snapshot\n{ws_index}")
    return "".join(parts)
