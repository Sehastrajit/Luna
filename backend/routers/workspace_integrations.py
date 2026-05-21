from fastapi import APIRouter, Body, Header
from fastapi.responses import JSONResponse

from backend.services.audit_log import record_audit
from backend.services.workspace_integrations import (
    WorkspaceIntegrationError,
    google_workspace,
    integration_status,
    microsoft_workspace,
)

router = APIRouter(prefix="/api/integrations/workspace", tags=["workspace-integrations"])


def _token_from_header(authorization: str | None) -> str:
    if not authorization:
        return ""
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix):].strip()
    return authorization.strip()


@router.get("/status")
def status():
    return integration_status()


@router.post("/google/{service}/{action}")
async def google_action(
    service: str,
    action: str,
    payload: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    try:
        result = await google_workspace(service, action, payload, _token_from_header(authorization))
        record_audit(
            "google_workspace",
            args={"service": service, "action": action},
            result=str(result.data)[:500],
            status="ok",
        )
        return result.as_dict()
    except WorkspaceIntegrationError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@router.post("/microsoft/{service}/{action}")
async def microsoft_action(
    service: str,
    action: str,
    payload: dict = Body(default={}),
    authorization: str | None = Header(default=None),
):
    try:
        result = await microsoft_workspace(service, action, payload, _token_from_header(authorization))
        record_audit(
            "microsoft_workspace",
            args={"service": service, "action": action},
            result=str(result.data)[:500],
            status="ok",
        )
        return result.as_dict()
    except WorkspaceIntegrationError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)
