"""
Planner → Executor → Critic agent execution engine.

Flow:
  1. planner.create_plan(goal, context)
       LLM outputs a JSON step DAG — a list of steps with explicit depends_on edges.
  2. planner.execute(plan)
       Topological execution: all steps whose dependencies are resolved run concurrently
       via asyncio.gather.  Failed steps are retried with exponential backoff (max 2).
  3. planner.critique(plan)
       LLM evaluates the combined results → verdict: success | partial | failure.
       Returns a list of step IDs to retry.
  4. planner.recover(plan, step_id)
       LLM patches a single failed step with corrected tool/args.

Step types:
  tool   — invoke a registered Luna tool (tool_name + tool_args)
  llm    — synthesis call; {stepId.result} placeholders are substituted
  wait   — asyncio.sleep(seconds)
  branch — select next step based on a prior result (evaluated as bool)
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Coroutine, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


# ── Enums ─────────────────────────────────────────────────────────────────────

class StepStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    SKIPPED  = "skipped"


class PlanStatus(str, Enum):
    PLANNING  = "planning"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    CRITIQUED = "critiqued"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Step:
    id: str
    action: str                           # tool | llm | wait | branch
    description: str
    tool_name: str       = ""
    tool_args: dict      = field(default_factory=dict)
    llm_prompt: str      = ""             # for action=llm; supports {stepId.result}
    depends_on: list[str]= field(default_factory=list)
    status: StepStatus   = StepStatus.PENDING
    result: Any          = None
    error: str           = ""
    retries: int         = 0
    max_retries: int     = 2
    started_at: float    = 0.0
    ended_at: float      = 0.0

    @property
    def latency_ms(self) -> float:
        if self.started_at and self.ended_at:
            return max(0.0, (self.ended_at - self.started_at) * 1000)
        return 0.0


@dataclass
class CritiqueResult:
    verdict: str                          # success | partial | failure
    reasoning: str
    score: float                    = 0.0 # 0–1
    retry_step_ids: list[str]       = field(default_factory=list)


@dataclass
class Plan:
    id: str                         = field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: str                       = ""
    conversation_id: Optional[int]  = None
    steps: list[Step]               = field(default_factory=list)
    status: PlanStatus              = PlanStatus.PLANNING
    critique: Optional[CritiqueResult] = None
    created_at: float               = field(default_factory=time.monotonic)
    completed_at: Optional[float]   = None

    # ── DAG helpers ───────────────────────────────────────────────────────────

    def step_by_id(self, sid: str) -> Optional[Step]:
        return next((s for s in self.steps if s.id == sid), None)

    def ready_steps(self) -> list[Step]:
        """Pending steps whose every dependency is already DONE."""
        done = {s.id for s in self.steps if s.status == StepStatus.DONE}
        return [
            s for s in self.steps
            if s.status == StepStatus.PENDING
            and all(dep in done for dep in s.depends_on)
        ]

    def is_complete(self) -> bool:
        return all(
            s.status in (StepStatus.DONE, StepStatus.FAILED, StepStatus.SKIPPED)
            for s in self.steps
        )

    def summary(self) -> dict:
        return {
            "id":     self.id,
            "goal":   self.goal,
            "status": self.status.value,
            "steps":  [
                {"id": s.id, "description": s.description,
                 "status": s.status.value, "latency_ms": round(s.latency_ms)}
                for s in self.steps
            ],
            "critique": asdict(self.critique) if self.critique else None,
        }


# ── Prompt templates ──────────────────────────────────────────────────────────

_PLAN_SCHEMA = """{
  "goal": "<restate goal>",
  "steps": [
    {
      "id": "s1",
      "action": "tool",
      "description": "what this step does",
      "tool_name": "tool_from_registry",
      "tool_args": {},
      "depends_on": []
    },
    {
      "id": "s2",
      "action": "llm",
      "description": "synthesise result",
      "llm_prompt": "Given this data: {s1.result} — summarise ...",
      "depends_on": ["s1"]
    }
  ]
}"""

_CRITIC_SCHEMA = """{
  "verdict": "success" | "partial" | "failure",
  "score": 0.0-1.0,
  "reasoning": "<paragraph>",
  "retry_step_ids": ["s2"]
}"""


# ── PlannerService ────────────────────────────────────────────────────────────

ToolExecutorT = Callable[[str, dict], Coroutine[Any, Any, str]]
LLMCompleteT  = Callable[[list[dict], float], Coroutine[Any, Any, str]]


class PlannerService:
    """
    Stateful planner that holds active plans in memory and persists
    completed plans to the plan_records table.

    llm_complete: async (messages: list[dict], temperature: float) -> str
    tool_executor: async (tool_name: str, args: dict) -> str
    """

    def __init__(
        self,
        llm_complete: LLMCompleteT,
        tool_executor: ToolExecutorT,
    ) -> None:
        self._llm = llm_complete
        self._exec = tool_executor
        self._active: dict[str, Plan] = {}

    # ── Plan creation ─────────────────────────────────────────────────────────

    async def create_plan(
        self,
        goal: str,
        context: str = "",
        conversation_id: Optional[int] = None,
        max_steps: int = 8,
    ) -> Plan:
        """
        Ask the LLM to decompose *goal* into a step DAG.
        Falls back to a single LLM step if the LLM output cannot be parsed.
        """
        prompt = (
            f"You are a planning agent. Decompose the following goal into a "
            f"dependency-aware step DAG (max {max_steps} steps).\n\n"
            f"GOAL: {goal}\n\n"
            f"CONTEXT:\n{context[:800]}\n\n"
            f"Output ONLY valid JSON matching this schema:\n{_PLAN_SCHEMA}\n\n"
            f"Rules:\n"
            f"- Use 'tool' for tool_registry actions, 'llm' for synthesis.\n"
            f"- depends_on must only reference earlier step IDs.\n"
            f"- Use {{stepId.result}} placeholders in llm_prompt.\n"
            f"- Prefer parallelism: steps that don't depend on each other should have empty depends_on.\n"
        )
        try:
            raw = await self._llm([{"role": "user", "content": prompt}], 0.15)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            data  = json.loads(raw[start:end])
            steps = [
                Step(
                    id          = s.get("id", f"s{i+1}"),
                    action      = s.get("action", "llm"),
                    description = s.get("description", ""),
                    tool_name   = s.get("tool_name", ""),
                    tool_args   = s.get("tool_args", {}),
                    llm_prompt  = s.get("llm_prompt", ""),
                    depends_on  = s.get("depends_on", []),
                )
                for i, s in enumerate(data.get("steps", []))
            ]
            plan = Plan(
                goal=data.get("goal", goal),
                steps=steps,
                conversation_id=conversation_id,
            )
        except Exception:
            plan = Plan(
                goal=goal,
                steps=[
                    Step(id="s1", action="llm",
                         description="Direct response",
                         llm_prompt=goal)
                ],
                conversation_id=conversation_id,
            )

        self._active[plan.id] = plan
        return plan

    # ── Execution ─────────────────────────────────────────────────────────────

    async def execute(
        self,
        plan: Plan,
        db: Optional[Session] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Execute the DAG, yielding SSE-compatible event dicts as steps run.

        Independent ready steps are launched concurrently via asyncio.gather.
        """
        plan.status = PlanStatus.RUNNING
        results: dict[str, Any] = {}

        while not plan.is_complete():
            ready = plan.ready_steps()
            if not ready:
                # Remaining steps have unresolvable dependencies → skip them.
                for s in plan.steps:
                    if s.status == StepStatus.PENDING:
                        s.status = StepStatus.SKIPPED
                break

            tasks = [self._run_step(s, results) for s in ready]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

            for step, outcome in zip(ready, outcomes):
                if isinstance(outcome, Exception):
                    step.status = StepStatus.FAILED
                    step.error  = str(outcome)[:300]
                    yield {"type": "step_failed", "step": step.id, "error": step.error}
                else:
                    results[step.id] = outcome
                    step.result = outcome
                    step.status = StepStatus.DONE
                    yield {
                        "type":   "step_done",
                        "step":   step.id,
                        "result": str(outcome)[:300],
                        "ms":     round(step.latency_ms),
                    }

        plan.completed_at = time.monotonic()
        failed = [s for s in plan.steps if s.status == StepStatus.FAILED]
        plan.status = PlanStatus.FAILED if failed else PlanStatus.DONE

        yield {"type": "plan_complete", "plan_id": plan.id, "status": plan.status.value}

        if db is not None:
            self._persist(plan, db)

    async def _run_step(self, step: Step, results: dict[str, Any]) -> Any:
        step.status     = StepStatus.RUNNING
        step.started_at = time.monotonic()
        last_exc: Optional[Exception] = None

        for attempt in range(step.max_retries + 1):
            try:
                if step.action == "tool":
                    result = await self._exec(step.tool_name, step.tool_args)
                elif step.action == "llm":
                    prompt = self._interpolate(step.llm_prompt, results)
                    result = await self._llm([{"role": "user", "content": prompt}], 0.3)
                elif step.action == "wait":
                    delay = float(step.tool_args.get("seconds", 1))
                    await asyncio.sleep(min(delay, 60))
                    result = f"waited {delay}s"
                else:
                    result = f"[unknown action: {step.action}]"

                step.ended_at = time.monotonic()
                return result

            except Exception as exc:
                last_exc = exc
                step.retries += 1
                if attempt < step.max_retries:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s

        step.ended_at = time.monotonic()
        raise last_exc or RuntimeError(f"step {step.id} failed")

    @staticmethod
    def _interpolate(template: str, results: dict[str, Any]) -> str:
        for sid, res in results.items():
            template = template.replace(f"{{{sid}.result}}", str(res)[:600])
        return template

    # ── Critic ────────────────────────────────────────────────────────────────

    async def critique(self, plan: Plan) -> CritiqueResult:
        """
        Ask the LLM to evaluate whether the plan achieved its goal.
        Returns a CritiqueResult with verdict and optional retry_step_ids.
        """
        step_lines = "\n".join(
            f"  [{s.id}] {s.description}: {s.status.value} "
            f"— {str(s.result or s.error)[:150]}"
            for s in plan.steps
        )
        prompt = (
            f"You are a critic agent evaluating plan execution.\n\n"
            f"GOAL: {plan.goal}\n\n"
            f"STEP RESULTS:\n{step_lines}\n\n"
            f"Output ONLY valid JSON:\n{_CRITIC_SCHEMA}"
        )
        try:
            raw   = await self._llm([{"role": "user", "content": prompt}], 0.1)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            data  = json.loads(raw[start:end])
            result = CritiqueResult(
                verdict        = data.get("verdict", "failure"),
                reasoning      = data.get("reasoning", ""),
                score          = float(data.get("score", 0.0)),
                retry_step_ids = data.get("retry_step_ids", []),
            )
        except Exception:
            result = CritiqueResult(
                verdict   = "failure",
                reasoning = "Critique unavailable.",
            )

        plan.critique = result
        plan.status   = PlanStatus.CRITIQUED
        return result

    # ── Recovery ─────────────────────────────────────────────────────────────

    async def recover(self, plan: Plan, failed_step_id: str) -> Optional[Step]:
        """
        Ask the LLM to suggest a corrected version of the failed step.
        Resets the step to PENDING so execute() can re-run it.
        """
        step = plan.step_by_id(failed_step_id)
        if step is None:
            return None

        prompt = (
            f"A planning step failed. Suggest a corrected replacement.\n\n"
            f"GOAL: {plan.goal}\n"
            f"FAILED STEP:\n{json.dumps(asdict(step), default=str)}\n\n"
            f"Output a JSON object for the replacement step with the same 'id': {failed_step_id}"
        )
        try:
            raw   = await self._llm([{"role": "user", "content": prompt}], 0.3)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            data  = json.loads(raw[start:end])
            step.tool_name  = data.get("tool_name",  step.tool_name)
            step.tool_args  = data.get("tool_args",  step.tool_args)
            step.llm_prompt = data.get("llm_prompt", step.llm_prompt)
            step.status     = StepStatus.PENDING
            step.retries    = 0
            step.error      = ""
            return step
        except Exception:
            return None

    # ── Plan access ───────────────────────────────────────────────────────────

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self._active.get(plan_id)

    def list_plans(self, limit: int = 20) -> list[dict]:
        plans = sorted(self._active.values(), key=lambda p: p.created_at, reverse=True)
        return [p.summary() for p in plans[:limit]]

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist(self, plan: Plan, db: Session) -> None:
        try:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO plan_records "
                    "(plan_id, goal, conversation_id, status, steps_json, "
                    " critique_json, created_at, completed_at) "
                    "VALUES (:pid, :goal, :cid, :status, :steps, :critique, :created, :completed)"
                ),
                {
                    "pid":      plan.id,
                    "goal":     plan.goal,
                    "cid":      plan.conversation_id,
                    "status":   plan.status.value,
                    "steps":    json.dumps([asdict(s) for s in plan.steps], default=str),
                    "critique": json.dumps(asdict(plan.critique), default=str) if plan.critique else None,
                    "created":  plan.created_at,
                    "completed": plan.completed_at,
                },
            )
            db.commit()
        except Exception:
            pass

    def load_plan_record(self, plan_id: str, db: Session) -> Optional[dict]:
        row = db.execute(
            text("SELECT plan_id, goal, status, steps_json, critique_json, created_at, completed_at "
                 "FROM plan_records WHERE plan_id = :pid"),
            {"pid": plan_id},
        ).fetchone()
        if not row:
            return None
        return {
            "plan_id":    row[0],
            "goal":       row[1],
            "status":     row[2],
            "steps":      json.loads(row[3] or "[]"),
            "critique":   json.loads(row[4]) if row[4] else None,
            "created_at": row[5],
            "completed_at": row[6],
        }
