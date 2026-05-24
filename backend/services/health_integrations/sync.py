"""Unified sync dispatcher and integration status."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.services.health_integrations.db import _update_sync, get_sync_status
from backend.services.health_integrations.fitbit import (
    fitbit_exchange_code, fitbit_is_configured, fitbit_oauth_url, fitbit_sync,
)
from backend.services.health_integrations.garmin import garmin_is_configured, garmin_sync
from backend.services.health_integrations.google_fit import (
    google_fit_exchange_code, google_fit_is_configured, google_fit_oauth_url, google_fit_sync,
)
from backend.services.health_integrations.models import HealthIntegrationError
from backend.services.health_integrations.oura import oura_is_configured, oura_sync
from backend.services.health_integrations.withings import (
    withings_exchange_code, withings_is_configured, withings_oauth_url, withings_sync,
)

log = logging.getLogger(__name__)

PLATFORM_SYNC = {
    "fitbit":     fitbit_sync,
    "google_fit": google_fit_sync,
    "oura":       oura_sync,
    "withings":   withings_sync,
    "garmin":     garmin_sync,
}

PLATFORM_CONFIGURED = {
    "fitbit":     fitbit_is_configured,
    "google_fit": google_fit_is_configured,
    "oura":       oura_is_configured,
    "withings":   withings_is_configured,
    "garmin":     garmin_is_configured,
    "apple":      lambda: True,
    "samsung":    lambda: True,
}

PLATFORM_OAUTH = {
    "fitbit":     (fitbit_oauth_url,     fitbit_exchange_code),
    "google_fit": (google_fit_oauth_url, google_fit_exchange_code),
    "withings":   (withings_oauth_url,   withings_exchange_code),
}


async def sync_all(db: Session, target_date: Optional[str] = None) -> dict[str, int]:
    results = {}
    for name, fn in PLATFORM_SYNC.items():
        if PLATFORM_CONFIGURED[name]():
            try:
                pts = await fn(db, target_date)
                results[name] = len(pts)
            except HealthIntegrationError as e:
                log.warning("Health sync %s: %s", name, e)
                results[name] = -1
            except Exception as e:
                log.error("Health sync %s unexpected: %s", name, e)
                _update_sync(db, name, "error", 0, str(e))
                results[name] = -1
    return results


def integration_status(db: Session) -> dict:
    syncs     = {r["platform"]: r for r in get_sync_status(db)}
    platforms = []
    for name, configured_fn in PLATFORM_CONFIGURED.items():
        sync = syncs.get(name, {})
        platforms.append({
            "platform":       name,
            "configured":     configured_fn(),
            "auth_type":      "webhook" if name in ("apple", "samsung") else
                              ("api_key" if name == "oura" else
                               ("credentials" if name == "garmin" else "oauth2")),
            "status":         sync.get("status", "never"),
            "last_sync_at":   sync.get("last_sync_at"),
            "metrics_synced": sync.get("metrics_synced", 0),
        })
    return {"platforms": platforms}
