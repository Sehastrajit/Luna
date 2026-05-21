"""
Admin API — production user and JWT token management.

All endpoints require  Authorization: Bearer <jwt_secret>  header.
Enabled only when  jwt_secret  is non-empty in .env.

Usage
─────
Create a user and get a JWT token:
  POST /api/admin/users
  Body: { "username": "alice", "role": "user" }
  Returns: { "user_id": "...", "token": "..." }

List users:
  GET /api/admin/users

Revoke a user:
  DELETE /api/admin/users/{user_id}

Rotate a user token:
  POST /api/admin/users/{user_id}/rotate-token

System info:
  GET /api/admin/info
"""
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from backend.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Simple JSON flat-file store for users (no extra DB table required)
_USERS_FILE = Path("data/users.json")


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _sign_jwt(user_id: str, username: str, role: str) -> str:
    """Create a HS256 JWT.  Falls back to opaque token if PyJWT is not installed."""
    try:
        import jwt  # PyJWT
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + settings.jwt_expiry_hours * 3600,
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    except ImportError:
        # No PyJWT — fall back to an opaque random token stored in the user record
        return secrets.token_urlsafe(48)


def verify_jwt(token: str) -> dict | None:
    """Return decoded payload or None if invalid/expired."""
    try:
        import jwt
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except Exception:
        return None


# ── flat-file user store ──────────────────────────────────────────────────────

def _load_users() -> dict:
    import json
    if _USERS_FILE.exists():
        try:
            return json.loads(_USERS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_users(users: dict):
    import json
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(users, indent=2))


# ── auth guard ────────────────────────────────────────────────────────────────

def _require_admin(request: Request):
    secret = settings.jwt_secret
    if not secret:
        raise HTTPException(403, "Admin API requires jwt_secret to be set in .env")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != secret:
        raise HTTPException(401, "Unauthorized")


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/info")
def admin_info(request: Request):
    _require_admin(request)
    users = _load_users()
    return {
        "provider": settings.llm_provider,
        "model": _current_model(),
        "jwt_enabled": bool(settings.jwt_secret),
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "user_count": len(users),
        "channels": {
            "telegram": bool(settings.telegram_bot_token),
            "discord": bool(settings.discord_bot_token),
            "slack": bool(settings.slack_bot_token),
        },
    }


@router.get("/users")
def list_users(request: Request):
    _require_admin(request)
    users = _load_users()
    # Strip tokens from list response
    return [
        {k: v for k, v in u.items() if k != "token"}
        for u in users.values()
    ]


@router.post("/users", status_code=201)
def create_user(request: Request, body: dict):
    _require_admin(request)
    if not settings.jwt_secret:
        raise HTTPException(503, "jwt_secret must be set in .env to create users")

    username = str(body.get("username", "")).strip()
    role: Literal["admin", "user"] = body.get("role", "user")
    if not username:
        raise HTTPException(400, "username is required")
    if role not in ("admin", "user"):
        raise HTTPException(400, "role must be 'admin' or 'user'")

    users = _load_users()
    # Check uniqueness
    if any(u["username"] == username for u in users.values()):
        raise HTTPException(409, f"User '{username}' already exists")

    user_id = str(uuid.uuid4())
    token = _sign_jwt(user_id, username, role)
    users[user_id] = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "token": token,
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
    }
    _save_users(users)
    return {"user_id": user_id, "username": username, "role": role, "token": token}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, request: Request):
    _require_admin(request)
    users = _load_users()
    if user_id not in users:
        raise HTTPException(404, "User not found")
    users.pop(user_id)
    _save_users(users)
    return {"ok": True, "user_id": user_id}


@router.post("/users/{user_id}/rotate-token")
def rotate_token(user_id: str, request: Request):
    _require_admin(request)
    if not settings.jwt_secret:
        raise HTTPException(503, "jwt_secret must be set in .env")
    users = _load_users()
    if user_id not in users:
        raise HTTPException(404, "User not found")
    u = users[user_id]
    new_token = _sign_jwt(user_id, u["username"], u["role"])
    u["token"] = new_token
    _save_users(users)
    return {"user_id": user_id, "token": new_token}


@router.get("/llm/providers")
def list_providers(request: Request):
    """Return all configured LLM providers and which is active."""
    _require_admin(request)
    return {
        "active": settings.llm_provider,
        "providers": {
            "ollama": {
                "configured": True,
                "model": settings.ollama_model,
                "base_url": settings.ollama_base_url,
            },
            "openai-compatible": {
                "configured": bool(settings.openai_api_key or settings.openai_base_url),
                "model": settings.openai_model,
                "base_url": settings.openai_base_url,
            },
            "anthropic": {
                "configured": bool(settings.anthropic_api_key),
                "model": settings.anthropic_model,
            },
            "google": {
                "configured": bool(settings.google_api_key),
                "model": settings.google_model,
            },
            "groq": {
                "configured": bool(settings.groq_api_key),
                "model": settings.groq_model,
            },
            "cohere": {
                "configured": bool(settings.cohere_api_key),
                "model": settings.cohere_model,
            },
            "mistral": {
                "configured": bool(settings.mistral_api_key),
                "model": settings.mistral_model,
            },
        },
    }


def _current_model() -> str:
    from backend.services.llm import ollama as llm
    return llm.model
