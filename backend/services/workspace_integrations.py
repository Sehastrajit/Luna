"""Google Workspace and Microsoft 365 integration helpers.

The clients intentionally use the providers' REST APIs directly. That keeps Luna
portable across desktop, Docker, and business deployments without SDK-specific
state, while still allowing broad Workspace/Graph coverage.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

import httpx

from backend.config import settings


class WorkspaceIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceResponse:
    provider: str
    service: str
    action: str
    data: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "service": self.service,
            "action": self.action,
            "data": self.data,
        }


GOOGLE_BASES = {
    "gmail": "https://gmail.googleapis.com/gmail/v1",
    "calendar": "https://www.googleapis.com/calendar/v3",
    "drive": "https://www.googleapis.com/drive/v3",
    "docs": "https://docs.googleapis.com/v1",
    "sheets": "https://sheets.googleapis.com/v4",
    "slides": "https://slides.googleapis.com/v1",
    "tasks": "https://tasks.googleapis.com/tasks/v1",
    "people": "https://people.googleapis.com/v1",
}

MICROSOFT_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _configured_token(provider: str) -> str:
    if provider == "google":
        return settings.google_workspace_access_token.strip()
    if provider == "microsoft":
        return settings.microsoft_workspace_access_token.strip()
    return ""


async def _refresh_google_token() -> str:
    if not (
        settings.google_workspace_client_id
        and settings.google_workspace_client_secret
        and settings.google_workspace_refresh_token
    ):
        return ""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_workspace_client_id,
                "client_secret": settings.google_workspace_client_secret,
                "refresh_token": settings.google_workspace_refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.is_error:
        raise WorkspaceIntegrationError(f"google OAuth refresh failed {response.status_code}: {response.text[:300]}")
    return response.json().get("access_token", "")


async def _refresh_microsoft_token() -> str:
    if not (
        settings.microsoft_workspace_client_id
        and settings.microsoft_workspace_client_secret
        and settings.microsoft_workspace_refresh_token
    ):
        return ""
    tenant = settings.microsoft_workspace_tenant_id or "common"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": settings.microsoft_workspace_client_id,
                "client_secret": settings.microsoft_workspace_client_secret,
                "refresh_token": settings.microsoft_workspace_refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.is_error:
        raise WorkspaceIntegrationError(f"microsoft OAuth refresh failed {response.status_code}: {response.text[:300]}")
    return response.json().get("access_token", "")


async def _resolved_token(provider: str, token: str = "") -> str:
    access_token = (token or _configured_token(provider)).strip()
    if access_token:
        return access_token
    if provider == "google":
        access_token = await _refresh_google_token()
    elif provider == "microsoft":
        access_token = await _refresh_microsoft_token()
    if not access_token:
        raise WorkspaceIntegrationError(f"{provider} workspace access token is not configured")
    return access_token


async def _headers(provider: str, token: str = "") -> dict[str, str]:
    access_token = await _resolved_token(provider, token)
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def _request(
    method: str,
    url: str,
    provider: str,
    token: str = "",
    params: dict[str, Any] | None = None,
    json_body: Any = None,
) -> Any:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(
            method.upper(),
            url,
            headers=await _headers(provider, token),
            params=params or None,
            json=json_body,
        )
    if response.status_code == 204:
        return {"status": "ok"}
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text}
    if response.is_error:
        detail = data.get("error", data) if isinstance(data, dict) else data
        raise WorkspaceIntegrationError(f"{provider} API error {response.status_code}: {detail}")
    return data


def _clean_path(path: str) -> str:
    if not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    if "://" in path:
        raise WorkspaceIntegrationError("raw paths must be relative API paths, not full URLs")
    return path


def _gmail_raw_message(to: str, subject: str, body: str, sender: str = "") -> str:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    if sender:
        message["From"] = sender
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")


async def google_workspace(service: str, action: str, args: dict[str, Any] | None = None, token: str = "") -> WorkspaceResponse:
    args = args or {}
    service = service.lower().strip()
    action = action.lower().strip()
    if service not in GOOGLE_BASES:
        raise WorkspaceIntegrationError(f"unsupported Google Workspace service: {service}")
    base = GOOGLE_BASES[service]

    if action == "raw_request":
        path = _clean_path(str(args.get("path", "")))
        data = await _request(
            str(args.get("method", "GET")),
            f"{base}{path}",
            "google",
            token,
            params=args.get("params"),
            json_body=args.get("body"),
        )
        return WorkspaceResponse("google", service, action, data)

    if service == "gmail":
        user = args.get("user_id", "me")
        if action == "search_messages":
            data = await _request("GET", f"{base}/users/{user}/messages", "google", token, {
                "q": args.get("query", ""),
                "maxResults": int(args.get("limit", 10)),
            })
        elif action == "get_message":
            data = await _request("GET", f"{base}/users/{user}/messages/{args['message_id']}", "google", token, {
                "format": args.get("format", "metadata"),
            })
        elif action == "send_message":
            raw = _gmail_raw_message(args["to"], args.get("subject", ""), args.get("body", ""), args.get("from", ""))
            data = await _request("POST", f"{base}/users/{user}/messages/send", "google", token, json_body={"raw": raw})
        else:
            raise WorkspaceIntegrationError(f"unsupported Gmail action: {action}")
    elif service == "calendar":
        calendar_id = args.get("calendar_id", "primary")
        if action == "list_events":
            data = await _request("GET", f"{base}/calendars/{calendar_id}/events", "google", token, {
                "timeMin": args.get("time_min"),
                "timeMax": args.get("time_max"),
                "maxResults": int(args.get("limit", 10)),
                "singleEvents": True,
                "orderBy": "startTime",
            })
        elif action == "create_event":
            event = {
                "summary": args["title"],
                "description": args.get("description", ""),
                "start": {"dateTime": args["start"], "timeZone": args.get("time_zone", settings.weather_timezone)},
                "end": {"dateTime": args["end"], "timeZone": args.get("time_zone", settings.weather_timezone)},
            }
            if args.get("attendees"):
                event["attendees"] = [{"email": email} for email in args["attendees"]]
            data = await _request("POST", f"{base}/calendars/{calendar_id}/events", "google", token, json_body=event)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Calendar action: {action}")
    elif service == "drive":
        if action == "search_files":
            data = await _request("GET", f"{base}/files", "google", token, {
                "q": args.get("query", "trashed=false"),
                "pageSize": int(args.get("limit", 10)),
                "fields": "files(id,name,mimeType,webViewLink,modifiedTime,size)",
            })
        elif action == "get_file":
            data = await _request("GET", f"{base}/files/{args['file_id']}", "google", token, {
                "fields": args.get("fields", "id,name,mimeType,webViewLink,modifiedTime,size,owners"),
            })
        elif action == "create_folder":
            payload = {"name": args["name"], "mimeType": "application/vnd.google-apps.folder"}
            if args.get("parent_id"):
                payload["parents"] = [args["parent_id"]]
            data = await _request("POST", f"{base}/files", "google", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Drive action: {action}")
    elif service == "docs":
        if action == "create_document":
            data = await _request("POST", f"{base}/documents", "google", token, json_body={"title": args["title"]})
        elif action == "get_document":
            data = await _request("GET", f"{base}/documents/{args['document_id']}", "google", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Docs action: {action}")
    elif service == "sheets":
        if action == "get_values":
            data = await _request("GET", f"{base}/spreadsheets/{args['spreadsheet_id']}/values/{args['range']}", "google", token)
        elif action == "update_values":
            data = await _request(
                "PUT",
                f"{base}/spreadsheets/{args['spreadsheet_id']}/values/{args['range']}",
                "google",
                token,
                params={"valueInputOption": args.get("value_input_option", "USER_ENTERED")},
                json_body={"values": args.get("values", [])},
            )
        elif action == "create_spreadsheet":
            data = await _request("POST", f"{base}/spreadsheets", "google", token, json_body={"properties": {"title": args["title"]}})
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Sheets action: {action}")
    elif service == "slides":
        if action == "create_presentation":
            data = await _request("POST", f"{base}/presentations", "google", token, json_body={"title": args["title"]})
        elif action == "get_presentation":
            data = await _request("GET", f"{base}/presentations/{args['presentation_id']}", "google", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Slides action: {action}")
    elif service == "tasks":
        tasklist = args.get("tasklist", "@default")
        if action == "list_tasks":
            data = await _request("GET", f"{base}/lists/{tasklist}/tasks", "google", token, {"maxResults": int(args.get("limit", 20))})
        elif action == "create_task":
            data = await _request("POST", f"{base}/lists/{tasklist}/tasks", "google", token, json_body={
                "title": args["title"],
                "notes": args.get("notes", ""),
                "due": args.get("due"),
            })
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Tasks action: {action}")
    elif service == "people":
        if action == "search_contacts":
            data = await _request("GET", f"{base}/people:searchContacts", "google", token, {
                "query": args.get("query", ""),
                "readMask": args.get("read_mask", "names,emailAddresses,phoneNumbers"),
                "pageSize": int(args.get("limit", 10)),
            })
        else:
            raise WorkspaceIntegrationError(f"unsupported Google People action: {action}")
    else:
        raise WorkspaceIntegrationError(f"unsupported Google Workspace action: {service}.{action}")

    return WorkspaceResponse("google", service, action, data)


async def microsoft_workspace(service: str, action: str, args: dict[str, Any] | None = None, token: str = "") -> WorkspaceResponse:
    args = args or {}
    service = service.lower().strip()
    action = action.lower().strip()

    if action == "raw_request":
        path = _clean_path(str(args.get("path", "")))
        data = await _request(
            str(args.get("method", "GET")),
            f"{MICROSOFT_GRAPH_BASE}{path}",
            "microsoft",
            token,
            params=args.get("params"),
            json_body=args.get("body"),
        )
        return WorkspaceResponse("microsoft", service or "graph", action, data)

    if service == "profile":
        if action == "me":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me", "microsoft", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft profile action: {action}")
    elif service == "mail":
        if action == "search_messages":
            params = {"$top": int(args.get("limit", 10))}
            if args.get("query"):
                params["$search"] = f'"{args["query"]}"'
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/messages", "microsoft", token, params)
        elif action == "send_message":
            payload = {
                "message": {
                    "subject": args.get("subject", ""),
                    "body": {"contentType": args.get("content_type", "Text"), "content": args.get("body", "")},
                    "toRecipients": [{"emailAddress": {"address": email}} for email in args.get("to", [])],
                },
                "saveToSentItems": bool(args.get("save_to_sent_items", True)),
            }
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/sendMail", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft mail action: {action}")
    elif service == "calendar":
        if action == "list_events":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/calendar/events", "microsoft", token, {"$top": int(args.get("limit", 10))})
        elif action == "create_event":
            payload = {
                "subject": args["title"],
                "body": {"contentType": "Text", "content": args.get("description", "")},
                "start": {"dateTime": args["start"], "timeZone": args.get("time_zone", settings.weather_timezone)},
                "end": {"dateTime": args["end"], "timeZone": args.get("time_zone", settings.weather_timezone)},
            }
            if args.get("attendees"):
                payload["attendees"] = [
                    {"emailAddress": {"address": email}, "type": "required"} for email in args["attendees"]
                ]
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/calendar/events", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft calendar action: {action}")
    elif service == "drive":
        if action == "list_children":
            item = args.get("item_id", "root")
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/drive/items/{item}/children", "microsoft", token, {"$top": int(args.get("limit", 20))})
        elif action == "search_files":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/drive/root/search(q='{args.get('query', '')}')", "microsoft", token)
        elif action == "create_folder":
            parent = args.get("parent_id", "root")
            payload = {"name": args["name"], "folder": {}, "@microsoft.graph.conflictBehavior": args.get("conflict_behavior", "rename")}
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/drive/items/{parent}/children", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft Drive action: {action}")
    elif service == "todo":
        if action == "list_tasks":
            list_id = args.get("list_id")
            if list_id:
                data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/todo/lists/{list_id}/tasks", "microsoft", token)
            else:
                data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/todo/lists", "microsoft", token)
        elif action == "create_task":
            list_id = args["list_id"]
            payload = {"title": args["title"], "body": {"content": args.get("body", ""), "contentType": "text"}}
            if args.get("due"):
                payload["dueDateTime"] = {"dateTime": args["due"], "timeZone": args.get("time_zone", settings.weather_timezone)}
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/todo/lists/{list_id}/tasks", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft To Do action: {action}")
    elif service == "excel":
        item_id = args["item_id"]
        workbook_path = f"{MICROSOFT_GRAPH_BASE}/me/drive/items/{item_id}/workbook"
        if action == "get_range":
            data = await _request("GET", f"{workbook_path}/worksheets/{args['worksheet_id_or_name']}/range(address='{args['range']}')", "microsoft", token)
        elif action == "update_range":
            data = await _request(
                "PATCH",
                f"{workbook_path}/worksheets/{args['worksheet_id_or_name']}/range(address='{args['range']}')",
                "microsoft",
                token,
                json_body={"values": args.get("values", [])},
            )
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft Excel action: {action}")
    elif service == "teams":
        if action == "list_joined_teams":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/joinedTeams", "microsoft", token)
        elif action == "list_channels":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/teams/{args['team_id']}/channels", "microsoft", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft Teams action: {action}")
    else:
        raise WorkspaceIntegrationError(f"unsupported Microsoft 365 service: {service}")

    return WorkspaceResponse("microsoft", service, action, data)


def integration_status() -> dict[str, Any]:
    return {
        "google": {
            "configured": bool(settings.google_workspace_access_token or settings.google_workspace_refresh_token),
            "services": sorted(GOOGLE_BASES),
        },
        "microsoft": {
            "configured": bool(settings.microsoft_workspace_access_token or settings.microsoft_workspace_refresh_token),
            "services": ["profile", "mail", "calendar", "drive", "todo", "excel", "teams", "graph"],
        },
    }
