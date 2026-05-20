from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from backend.services.agent_tasks import create_agent_task, list_agent_tasks, update_agent_task
from backend.services.audit_log import list_audit, record_audit
from backend.services.browser_automation import browser_open, browser_read, playwright_status
from backend.services.permission_manager import permission_manager
from backend.services.skill_manager import list_skills
from backend.services.task_planner import generate_plan
from backend.services.workspace import list_workspace, read_workspace_file, write_workspace_file
from backend.processes.registry import list_processes

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/skills")
def skills():
    return list_skills()


@router.get("/processes")
def processes():
    return list_processes()


@router.get("/audit")
def audit(limit: int = 100):
    return list_audit(limit)


@router.get("/permissions")
def permissions():
    return permission_manager.list_policy()


@router.post("/permissions/{tool_name}")
def set_permission(tool_name: str, payload: dict = Body(default={})):
    mode = payload.get("mode")
    if mode not in ("allow", "confirm", "block"):
        return JSONResponse({"detail": "mode must be allow, confirm, or block"}, status_code=400)
    permission_manager.set_policy(tool_name, mode)
    return permission_manager.list_policy()


@router.get("/workspace")
def workspace_list(path: str = ""):
    return list_workspace(path)


@router.get("/workspace/read")
def workspace_read(path: str):
    return {"path": path, "content": read_workspace_file(path)}


@router.post("/workspace/write")
def workspace_write(payload: dict = Body(default={})):
    result = write_workspace_file(payload.get("path", ""), payload.get("content", ""))
    record_audit("workspace_write", args=result, status="ok")
    return result


@router.get("/browser/status")
async def browser_status():
    return await playwright_status()


@router.post("/browser/open")
def open_browser(payload: dict = Body(default={})):
    result = browser_open(payload.get("url", ""))
    record_audit("browser_open", args=result, status="ok")
    return result


@router.post("/browser/read")
async def read_browser(payload: dict = Body(default={})):
    result = await browser_read(payload.get("url", ""))
    record_audit("browser_read", args={"url": payload.get("url", "")}, result=str(result)[:500], status="ok")
    return result


@router.get("/tasks")
def tasks(limit: int = 50):
    return list_agent_tasks(limit)


@router.post("/tasks")
async def create_task(payload: dict = Body(default={})):
    description = payload.get("description", "").strip()
    if not description:
        return JSONResponse({"detail": "description is required"}, status_code=400)
    steps = payload.get("steps")
    if steps is None:
        steps = await generate_plan(description)
    task = create_agent_task(description, steps)
    record_audit("agent_task_created", args={"description": description, "steps": steps}, result=task["id"], status="ok")
    return task


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, payload: dict = Body(default={})):
    task = update_agent_task(task_id, **payload)
    if not task:
        return JSONResponse({"detail": "task not found"}, status_code=404)
    return task
