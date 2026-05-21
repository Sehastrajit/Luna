"""
Health platform integration service.

Supported platforms
-------------------
- Fitbit         — OAuth2, full metrics (steps, HR, HRV, sleep, SpO2, weight, …)
- Google Fit     — OAuth2, aggregate API
- Oura Ring      — Personal API token (v2), activity + sleep + readiness + stress
- Withings       — OAuth2 (smart scales, blood pressure monitors)
- Garmin Connect — garth library (unofficial REST session)
- Apple Health   — webhook receiver (Health Auto Export iOS app format)
- Samsung Health — webhook receiver (compatible exporter apps)

All platforms normalize data into HealthMetricPoint objects that are stored in
the health_metrics SQLite table via the persist() helper.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import HealthMetric, HealthSync

log = logging.getLogger(__name__)

# ── Metric type constants ──────────────────────────────────────────────────

STEPS            = "steps"
DISTANCE_KM      = "distance_km"
CALORIES         = "calories"
HEART_RATE       = "heart_rate"
RESTING_HR       = "resting_heart_rate"
HRV              = "hrv"
SLEEP_DURATION   = "sleep_duration_min"
SLEEP_DEEP       = "sleep_deep_min"
SLEEP_REM        = "sleep_rem_min"
SLEEP_LIGHT      = "sleep_light_min"
SLEEP_AWAKE      = "sleep_awake_min"
SLEEP_SCORE      = "sleep_score"
BLOOD_OXYGEN     = "blood_oxygen_pct"
WEIGHT_KG        = "weight_kg"
BMI              = "bmi"
BODY_FAT_PCT     = "body_fat_pct"
BP_SYSTOLIC      = "blood_pressure_systolic"
BP_DIASTOLIC     = "blood_pressure_diastolic"
STRESS_SCORE     = "stress_score"
READINESS_SCORE  = "readiness_score"
VO2_MAX          = "vo2_max"
RESPIRATORY_RATE = "respiratory_rate"
SKIN_TEMP        = "skin_temp_c"
ACTIVE_MINUTES   = "active_minutes"
WORKOUT          = "workout"

METRIC_UNITS: dict[str, str] = {
    STEPS: "steps",
    DISTANCE_KM: "km",
    CALORIES: "kcal",
    HEART_RATE: "bpm",
    RESTING_HR: "bpm",
    HRV: "ms",
    SLEEP_DURATION: "min",
    SLEEP_DEEP: "min",
    SLEEP_REM: "min",
    SLEEP_LIGHT: "min",
    SLEEP_AWAKE: "min",
    SLEEP_SCORE: "score",
    BLOOD_OXYGEN: "%",
    WEIGHT_KG: "kg",
    BMI: "kg/m2",
    BODY_FAT_PCT: "%",
    BP_SYSTOLIC: "mmHg",
    BP_DIASTOLIC: "mmHg",
    STRESS_SCORE: "score",
    READINESS_SCORE: "score",
    VO2_MAX: "mL/kg/min",
    RESPIRATORY_RATE: "rpm",
    SKIN_TEMP: "°C",
    ACTIVE_MINUTES: "min",
    WORKOUT: "",
}


@dataclass
class HealthMetricPoint:
    platform: str
    metric_type: str
    value: float
    unit: str
    date_str: str                           # YYYY-MM-DD
    timestamp: Optional[datetime] = None    # intra-day precision
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        if self.timestamp:
            d["timestamp"] = self.timestamp.isoformat()
        d.pop("raw", None)
        return d


class HealthIntegrationError(Exception):
    pass


# ── DB helpers ────────────────────────────────────────────────────────────

def persist(db: Session, points: list[HealthMetricPoint]) -> int:
    """Upsert health metric points into DB (deduplicates by platform+type+date)."""
    saved = 0
    for p in points:
        existing = (
            db.query(HealthMetric)
            .filter_by(platform=p.platform, metric_type=p.metric_type, date_str=p.date_str)
            .first()
        )
        raw_str = json.dumps(p.raw) if p.raw else None
        if existing:
            existing.value = p.value
            existing.unit = p.unit
            existing.timestamp = p.timestamp
            existing.raw_json = raw_str
        else:
            db.add(HealthMetric(
                platform=p.platform,
                metric_type=p.metric_type,
                value=p.value,
                unit=p.unit,
                date_str=p.date_str,
                timestamp=p.timestamp,
                raw_json=raw_str,
            ))
            saved += 1
    db.commit()
    return saved


def _update_sync(db: Session, platform: str, status: str, count: int = 0, error: str = "") -> None:
    row = db.query(HealthSync).filter_by(platform=platform).first()
    if not row:
        row = HealthSync(platform=platform)
        db.add(row)
    row.last_sync_at = datetime.now(timezone.utc)
    row.status = status
    row.metrics_synced = count
    row.error_message = error or None
    db.commit()


def get_sync_status(db: Session) -> list[dict]:
    rows = db.query(HealthSync).all()
    return [
        {
            "platform": r.platform,
            "status": r.status,
            "last_sync_at": r.last_sync_at.isoformat() if r.last_sync_at else None,
            "metrics_synced": r.metrics_synced,
            "error_message": r.error_message,
        }
        for r in rows
    ]


def query_metrics(
    db: Session,
    platform: Optional[str] = None,
    metric_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    q = db.query(HealthMetric)
    if platform:
        q = q.filter(HealthMetric.platform == platform)
    if metric_type:
        q = q.filter(HealthMetric.metric_type == metric_type)
    if from_date:
        q = q.filter(HealthMetric.date_str >= from_date)
    if to_date:
        q = q.filter(HealthMetric.date_str <= to_date)
    rows = q.order_by(HealthMetric.date_str.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "platform": r.platform,
            "metric_type": r.metric_type,
            "value": r.value,
            "unit": r.unit,
            "date_str": r.date_str,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


def daily_summary(db: Session, date_str: str) -> dict:
    """Aggregate all stored health metrics for one day across all platforms."""
    rows = db.query(HealthMetric).filter(HealthMetric.date_str == date_str).all()
    summary: dict[str, list] = {}
    for r in rows:
        summary.setdefault(r.metric_type, []).append(
            {"platform": r.platform, "value": r.value, "unit": r.unit}
        )
    return {"date": date_str, "metrics": summary}


# ── OAuth2 helpers ────────────────────────────────────────────────────────

async def _oauth_refresh(token_url: str, client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Generic OAuth2 token refresh. Returns new token dict."""
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            token_url,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
    resp.raise_for_status()
    return resp.json()


async def _get(url: str, token: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
    resp.raise_for_status()
    return resp.json()


async def _post_json(url: str, token: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=body)
    resp.raise_for_status()
    return resp.json()


# ── Fitbit ────────────────────────────────────────────────────────────────

FITBIT_BASE = "https://api.fitbit.com"
FITBIT_TOKEN_URL = "https://api.fitbit.com/oauth2/token"
FITBIT_AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
FITBIT_SCOPES = "activity heartrate sleep weight oxygen_saturation respiratory_rate temperature"


def fitbit_is_configured() -> bool:
    return bool(settings.fitbit_client_id and settings.fitbit_access_token)


async def _fitbit_token() -> str:
    """Return a valid Fitbit access token, refreshing if needed."""
    if not fitbit_is_configured():
        raise HealthIntegrationError("Fitbit not configured — set fitbit_client_id, fitbit_access_token in .env")
    if settings.fitbit_refresh_token:
        try:
            data = await _oauth_refresh(
                FITBIT_TOKEN_URL,
                settings.fitbit_client_id,
                settings.fitbit_client_secret,
                settings.fitbit_refresh_token,
            )
            # Settings are read-only after startup; store to env for this session
            import os
            os.environ["FITBIT_ACCESS_TOKEN"] = data.get("access_token", "")
            if data.get("refresh_token"):
                os.environ["FITBIT_REFRESH_TOKEN"] = data["refresh_token"]
            return data["access_token"]
        except Exception:
            pass
    return settings.fitbit_access_token


async def fitbit_oauth_url(redirect_uri: str) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": settings.fitbit_client_id,
        "redirect_uri": redirect_uri,
        "scope": FITBIT_SCOPES,
    }
    return f"{FITBIT_AUTH_URL}?{urlencode(params)}"


async def fitbit_exchange_code(code: str, redirect_uri: str) -> dict:
    auth = base64.b64encode(f"{settings.fitbit_client_id}:{settings.fitbit_client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            FITBIT_TOKEN_URL,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        )
    resp.raise_for_status()
    return resp.json()


async def fitbit_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    token = await _fitbit_token()
    d = target_date or date.today().isoformat()
    points: list[HealthMetricPoint] = []

    async def _fetch(path: str) -> dict:
        return await _get(f"{FITBIT_BASE}{path}", token)

    try:
        # Steps + distance + calories + active minutes
        acts = await _fetch(f"/1/user/-/activities/date/{d}.json")
        summary = acts.get("summary", {})
        if "steps" in summary:
            points.append(HealthMetricPoint("fitbit", STEPS, float(summary["steps"]), "steps", d))
        if "distances" in summary:
            for dist in summary["distances"]:
                if dist.get("activity") == "total":
                    points.append(HealthMetricPoint("fitbit", DISTANCE_KM, float(dist["distance"]), "km", d))
        if "caloriesOut" in summary:
            points.append(HealthMetricPoint("fitbit", CALORIES, float(summary["caloriesOut"]), "kcal", d))
        if "veryActiveMinutes" in summary and "fairlyActiveMinutes" in summary:
            active = summary["veryActiveMinutes"] + summary["fairlyActiveMinutes"]
            points.append(HealthMetricPoint("fitbit", ACTIVE_MINUTES, float(active), "min", d))
    except Exception as e:
        log.warning("Fitbit activities: %s", e)

    try:
        # Resting heart rate
        hr = await _fetch(f"/1/user/-/activities/heart/date/{d}/1d.json")
        hr_val = hr.get("activities-heart", [{}])[0].get("value", {})
        if "restingHeartRate" in hr_val:
            points.append(HealthMetricPoint("fitbit", RESTING_HR, float(hr_val["restingHeartRate"]), "bpm", d))
    except Exception as e:
        log.warning("Fitbit heart rate: %s", e)

    try:
        # Sleep
        sleep = await _fetch(f"/1.2/user/-/sleep/date/{d}.json")
        for s in sleep.get("sleep", []):
            if s.get("isMainSleep"):
                lsummary = s.get("levels", {}).get("summary", {})
                duration = s.get("minutesAsleep", 0)
                points.append(HealthMetricPoint("fitbit", SLEEP_DURATION, float(duration), "min", d))
                if "deep" in lsummary:
                    points.append(HealthMetricPoint("fitbit", SLEEP_DEEP, float(lsummary["deep"]["minutes"]), "min", d))
                if "rem" in lsummary:
                    points.append(HealthMetricPoint("fitbit", SLEEP_REM, float(lsummary["rem"]["minutes"]), "min", d))
                if "light" in lsummary:
                    points.append(HealthMetricPoint("fitbit", SLEEP_LIGHT, float(lsummary["light"]["minutes"]), "min", d))
                if "wake" in lsummary:
                    points.append(HealthMetricPoint("fitbit", SLEEP_AWAKE, float(lsummary["wake"]["minutes"]), "min", d))
    except Exception as e:
        log.warning("Fitbit sleep: %s", e)

    try:
        # SpO2
        spo2 = await _fetch(f"/1/user/-/spo2/date/{d}.json")
        val = spo2.get("value", {}).get("avg")
        if val is not None:
            points.append(HealthMetricPoint("fitbit", BLOOD_OXYGEN, float(val), "%", d))
    except Exception as e:
        log.warning("Fitbit SpO2: %s", e)

    try:
        # HRV
        hrv = await _fetch(f"/1/user/-/hrv/date/{d}.json")
        for entry in hrv.get("hrv", []):
            val = entry.get("value", {}).get("dailyRmssd")
            if val is not None:
                points.append(HealthMetricPoint("fitbit", HRV, float(val), "ms", d))
    except Exception as e:
        log.warning("Fitbit HRV: %s", e)

    try:
        # Breathing rate
        br = await _fetch(f"/1/user/-/br/date/{d}.json")
        for entry in br.get("br", []):
            val = entry.get("value", {}).get("breathingRate")
            if val is not None:
                points.append(HealthMetricPoint("fitbit", RESPIRATORY_RATE, float(val), "rpm", d))
    except Exception as e:
        log.warning("Fitbit breathing rate: %s", e)

    try:
        # Skin temperature
        temp = await _fetch(f"/1/user/-/temp/skin/date/{d}.json")
        for entry in temp.get("tempSkin", []):
            val = entry.get("value", {}).get("nightlyRelative")
            if val is not None:
                points.append(HealthMetricPoint("fitbit", SKIN_TEMP, float(val), "°C", d))
    except Exception as e:
        log.warning("Fitbit skin temp: %s", e)

    try:
        # Weight
        weight = await _fetch(f"/1/user/-/body/weight/date/{d}/1d.json")
        entries = weight.get("body-weight", [])
        if entries:
            points.append(HealthMetricPoint("fitbit", WEIGHT_KG, float(entries[-1]["value"]), "kg", d))
    except Exception as e:
        log.warning("Fitbit weight: %s", e)

    count = persist(db, points)
    _update_sync(db, "fitbit", "ok", count)
    return points


# ── Google Fit ────────────────────────────────────────────────────────────

GOOGLE_FIT_BASE = "https://www.googleapis.com/fitness/v1/users/me"
GOOGLE_FIT_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_FIT_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_FIT_SCOPES = " ".join([
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.blood_glucose.read",
    "https://www.googleapis.com/auth/fitness.blood_pressure.read",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.read",
])


def google_fit_is_configured() -> bool:
    return bool(settings.google_fit_client_id and settings.google_fit_access_token)


async def _google_fit_token() -> str:
    if not google_fit_is_configured():
        raise HealthIntegrationError("Google Fit not configured — set google_fit_client_id, google_fit_access_token in .env")
    if settings.google_fit_refresh_token:
        try:
            data = await _oauth_refresh(
                GOOGLE_FIT_TOKEN_URL,
                settings.google_fit_client_id,
                settings.google_fit_client_secret,
                settings.google_fit_refresh_token,
            )
            import os
            os.environ["GOOGLE_FIT_ACCESS_TOKEN"] = data.get("access_token", "")
            return data["access_token"]
        except Exception:
            pass
    return settings.google_fit_access_token


async def google_fit_oauth_url(redirect_uri: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": settings.google_fit_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_FIT_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_FIT_AUTH_URL}?{urlencode(params)}"


async def google_fit_exchange_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GOOGLE_FIT_TOKEN_URL, data={
            "client_id": settings.google_fit_client_id,
            "client_secret": settings.google_fit_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
    resp.raise_for_status()
    return resp.json()


def _day_millis(day: str) -> tuple[int, int]:
    """Return (start_ms, end_ms) for a YYYY-MM-DD day."""
    d = date.fromisoformat(day)
    start = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)
    end = start + 86_400_000
    return start, end


async def google_fit_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    token = await _google_fit_token()
    d = target_date or date.today().isoformat()
    start_ms, end_ms = _day_millis(d)
    points: list[HealthMetricPoint] = []

    data_type_map = {
        "com.google.step_count.delta": (STEPS, "steps"),
        "com.google.distance.delta": (DISTANCE_KM, "km"),
        "com.google.calories.expended": (CALORIES, "kcal"),
        "com.google.heart_rate.bpm": (HEART_RATE, "bpm"),
        "com.google.weight": (WEIGHT_KG, "kg"),
        "com.google.body.fat.percentage": (BODY_FAT_PCT, "%"),
        "com.google.active_minutes": (ACTIVE_MINUTES, "min"),
        "com.google.oxygen_saturation": (BLOOD_OXYGEN, "%"),
        "com.google.blood_pressure": (None, None),  # handled separately
    }

    body = {
        "aggregateBy": [{"dataTypeName": k} for k in data_type_map],
        "startTimeMillis": start_ms,
        "endTimeMillis": end_ms,
        "bucketByTime": {"durationMillis": 86_400_000},
    }

    try:
        resp = await _post_json(f"{GOOGLE_FIT_BASE}/dataset:aggregate", token, body)
        for bucket in resp.get("bucket", []):
            for ds in bucket.get("dataset", []):
                dtype = ds.get("dataSourceId", "")
                # Match data type from dataSourceId suffix
                matched_metric = None
                matched_unit = None
                for k, (m, u) in data_type_map.items():
                    if k in dtype and m:
                        matched_metric, matched_unit = m, u
                        break
                if not matched_metric:
                    continue
                for pt in ds.get("point", []):
                    for val in pt.get("value", []):
                        raw_val = val.get("fpVal") or val.get("intVal")
                        if raw_val is not None:
                            # Distance comes in meters from Google Fit
                            if matched_metric == DISTANCE_KM:
                                raw_val = float(raw_val) / 1000.0
                            points.append(HealthMetricPoint("google_fit", matched_metric, float(raw_val), matched_unit, d))
    except Exception as e:
        log.warning("Google Fit aggregate: %s", e)

    # Sleep requires separate call (different endpoint)
    try:
        sessions_resp = await _get(
            f"{GOOGLE_FIT_BASE}/sessions",
            token,
            params={"startTime": f"{d}T00:00:00.000Z", "endTime": f"{d}T23:59:59.000Z",
                    "activityType": "72"},  # 72 = sleep
        )
        total_sleep = 0
        for s in sessions_resp.get("session", []):
            start_ns = int(s.get("startTimeMillis", 0))
            end_ns = int(s.get("endTimeMillis", 0))
            total_sleep += (end_ns - start_ns) // 60000  # ms → min
        if total_sleep:
            points.append(HealthMetricPoint("google_fit", SLEEP_DURATION, float(total_sleep), "min", d))
    except Exception as e:
        log.warning("Google Fit sleep: %s", e)

    count = persist(db, points)
    _update_sync(db, "google_fit", "ok", count)
    return points


# ── Oura Ring ────────────────────────────────────────────────────────────

OURA_BASE = "https://api.ouraring.com/v2/usercollection"


def oura_is_configured() -> bool:
    return bool(settings.oura_api_key)


async def oura_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    if not oura_is_configured():
        raise HealthIntegrationError("Oura not configured — set oura_api_key in .env")
    token = settings.oura_api_key
    d = target_date or date.today().isoformat()
    points: list[HealthMetricPoint] = []
    params = {"start_date": d, "end_date": d}

    async def _oura_get(endpoint: str) -> dict:
        return await _get(f"{OURA_BASE}/{endpoint}", token, params)

    try:
        act = await _oura_get("daily_activity")
        for entry in act.get("data", []):
            if entry.get("day") == d:
                if "steps" in entry:
                    points.append(HealthMetricPoint("oura", STEPS, float(entry["steps"]), "steps", d))
                if "active_calories" in entry:
                    points.append(HealthMetricPoint("oura", CALORIES, float(entry["active_calories"]), "kcal", d))
                if "equivalent_walking_distance" in entry:
                    km = float(entry["equivalent_walking_distance"]) / 1000
                    points.append(HealthMetricPoint("oura", DISTANCE_KM, km, "km", d))
                if "meet_daily_targets" in entry:
                    points.append(HealthMetricPoint("oura", ACTIVE_MINUTES, float(entry.get("high_activity_time", 0)) / 60, "min", d))
    except Exception as e:
        log.warning("Oura daily_activity: %s", e)

    try:
        sleep = await _oura_get("sleep")
        for entry in sleep.get("data", []):
            if entry.get("day") == d:
                total = entry.get("total_sleep_duration", 0)
                points.append(HealthMetricPoint("oura", SLEEP_DURATION, float(total) / 60, "min", d))
                if "deep_sleep_duration" in entry:
                    points.append(HealthMetricPoint("oura", SLEEP_DEEP, float(entry["deep_sleep_duration"]) / 60, "min", d))
                if "rem_sleep_duration" in entry:
                    points.append(HealthMetricPoint("oura", SLEEP_REM, float(entry["rem_sleep_duration"]) / 60, "min", d))
                if "light_sleep_duration" in entry:
                    points.append(HealthMetricPoint("oura", SLEEP_LIGHT, float(entry["light_sleep_duration"]) / 60, "min", d))
                if "awake_time" in entry:
                    points.append(HealthMetricPoint("oura", SLEEP_AWAKE, float(entry["awake_time"]) / 60, "min", d))
                if "average_hrv" in entry:
                    points.append(HealthMetricPoint("oura", HRV, float(entry["average_hrv"]), "ms", d))
                if "lowest_heart_rate" in entry:
                    points.append(HealthMetricPoint("oura", RESTING_HR, float(entry["lowest_heart_rate"]), "bpm", d))
                if "average_breathing_rate" in entry:
                    points.append(HealthMetricPoint("oura", RESPIRATORY_RATE, float(entry["average_breathing_rate"]), "rpm", d))
    except Exception as e:
        log.warning("Oura sleep: %s", e)

    try:
        readiness = await _oura_get("daily_readiness")
        for entry in readiness.get("data", []):
            if entry.get("day") == d and "score" in entry:
                points.append(HealthMetricPoint("oura", READINESS_SCORE, float(entry["score"]), "score", d))
    except Exception as e:
        log.warning("Oura readiness: %s", e)

    try:
        stress = await _oura_get("daily_stress")
        for entry in stress.get("data", []):
            if entry.get("day") == d and "stress_high" in entry:
                points.append(HealthMetricPoint("oura", STRESS_SCORE, float(entry["stress_high"]), "score", d))
    except Exception as e:
        log.warning("Oura stress: %s", e)

    try:
        hr = await _oura_get("heartrate")
        today_hrs = [e["bpm"] for e in hr.get("data", []) if e.get("timestamp", "").startswith(d)]
        if today_hrs:
            avg_hr = sum(today_hrs) / len(today_hrs)
            points.append(HealthMetricPoint("oura", HEART_RATE, float(avg_hr), "bpm", d))
    except Exception as e:
        log.warning("Oura heart rate: %s", e)

    count = persist(db, points)
    _update_sync(db, "oura", "ok", count)
    return points


# ── Withings ─────────────────────────────────────────────────────────────

WITHINGS_BASE = "https://wbsapi.withings.net"
WITHINGS_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
WITHINGS_AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"

# Withings measure types
_WITHINGS_WEIGHT     = 1
_WITHINGS_BMI        = 35
_WITHINGS_FAT_PCT    = 6
_WITHINGS_BP_DIASTOL = 9
_WITHINGS_BP_SYSTOL  = 10
_WITHINGS_HR         = 11


def withings_is_configured() -> bool:
    return bool(settings.withings_client_id and settings.withings_access_token)


async def _withings_token() -> str:
    if not withings_is_configured():
        raise HealthIntegrationError("Withings not configured — set withings_client_id, withings_access_token in .env")
    if settings.withings_refresh_token:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(WITHINGS_TOKEN_URL, data={
                    "action": "requesttoken",
                    "grant_type": "refresh_token",
                    "client_id": settings.withings_client_id,
                    "client_secret": settings.withings_client_secret,
                    "refresh_token": settings.withings_refresh_token,
                })
            resp.raise_for_status()
            data = resp.json().get("body", {})
            import os
            os.environ["WITHINGS_ACCESS_TOKEN"] = data.get("access_token", "")
            if data.get("refresh_token"):
                os.environ["WITHINGS_REFRESH_TOKEN"] = data["refresh_token"]
            return data["access_token"]
        except Exception:
            pass
    return settings.withings_access_token


async def withings_oauth_url(redirect_uri: str) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": settings.withings_client_id,
        "redirect_uri": redirect_uri,
        "scope": "user.info,user.metrics,user.activity",
        "state": "luna",
    }
    return f"{WITHINGS_AUTH_URL}?{urlencode(params)}"


async def withings_exchange_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(WITHINGS_TOKEN_URL, data={
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": settings.withings_client_id,
            "client_secret": settings.withings_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        })
    resp.raise_for_status()
    return resp.json().get("body", {})


async def withings_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    token = await _withings_token()
    d = target_date or date.today().isoformat()
    d_obj = date.fromisoformat(d)
    start_ts = int(datetime(d_obj.year, d_obj.month, d_obj.day, tzinfo=timezone.utc).timestamp())
    end_ts = start_ts + 86400
    points: list[HealthMetricPoint] = []

    type_map = {
        _WITHINGS_WEIGHT: (WEIGHT_KG, "kg", 1),
        _WITHINGS_BMI: (BMI, "kg/m2", 1),
        _WITHINGS_FAT_PCT: (BODY_FAT_PCT, "%", 1),
        _WITHINGS_BP_DIASTOL: (BP_DIASTOLIC, "mmHg", 1),
        _WITHINGS_BP_SYSTOL: (BP_SYSTOLIC, "mmHg", 1),
        _WITHINGS_HR: (HEART_RATE, "bpm", 1),
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{WITHINGS_BASE}/measure",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "action": "getmeas",
                    "startdate": start_ts,
                    "enddate": end_ts,
                    "category": 1,
                },
            )
        resp.raise_for_status()
        groups = resp.json().get("body", {}).get("measuregrps", [])
        for grp in groups:
            for meas in grp.get("measures", []):
                mtype = meas.get("type")
                if mtype in type_map:
                    metric, unit, _ = type_map[mtype]
                    val = meas["value"] * (10 ** meas.get("unit", 0))
                    points.append(HealthMetricPoint("withings", metric, float(val), unit, d))
    except Exception as e:
        log.warning("Withings measures: %s", e)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{WITHINGS_BASE}/v2/sleep",
                headers={"Authorization": f"Bearer {token}"},
                params={"action": "getsummary", "startdateymd": d, "enddateymd": d},
            )
        resp.raise_for_status()
        for s in resp.json().get("body", {}).get("series", []):
            data = s.get("data", {})
            if "nb_rem_episodes" in data:
                duration = data.get("total_sleep_time", 0)
                points.append(HealthMetricPoint("withings", SLEEP_DURATION, float(duration) / 60, "min", d))
                if "sleep_score" in data:
                    points.append(HealthMetricPoint("withings", SLEEP_SCORE, float(data["sleep_score"]), "score", d))
    except Exception as e:
        log.warning("Withings sleep: %s", e)

    count = persist(db, points)
    _update_sync(db, "withings", "ok", count)
    return points


# ── Garmin Connect ────────────────────────────────────────────────────────

def garmin_is_configured() -> bool:
    return bool(settings.garmin_email and settings.garmin_password)


async def garmin_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    """Sync from Garmin Connect using the garth library (unofficial API)."""
    if not garmin_is_configured():
        raise HealthIntegrationError("Garmin not configured — set garmin_email, garmin_password in .env")
    try:
        import garth  # type: ignore
    except ImportError:
        raise HealthIntegrationError(
            "garth library not installed — run: pip install garth"
        )

    d = target_date or date.today().isoformat()
    points: list[HealthMetricPoint] = []

    try:
        garth.login(settings.garmin_email, settings.garmin_password)

        stats = garth.connectapi(f"/wellness-service/wellness/dailySummaryChart/{d}")
        if isinstance(stats, dict):
            if "totalSteps" in stats:
                points.append(HealthMetricPoint("garmin", STEPS, float(stats["totalSteps"]), "steps", d))
            if "totalKilocalories" in stats:
                points.append(HealthMetricPoint("garmin", CALORIES, float(stats["totalKilocalories"]), "kcal", d))
            if "totalDistanceMeters" in stats:
                points.append(HealthMetricPoint("garmin", DISTANCE_KM, float(stats["totalDistanceMeters"]) / 1000, "km", d))
            if "restingHeartRate" in stats:
                points.append(HealthMetricPoint("garmin", RESTING_HR, float(stats["restingHeartRate"]), "bpm", d))
            if "averageStressLevel" in stats and stats["averageStressLevel"] >= 0:
                points.append(HealthMetricPoint("garmin", STRESS_SCORE, float(stats["averageStressLevel"]), "score", d))
            if "bodyBattery" in stats:
                battery = stats["bodyBattery"]
                if isinstance(battery, list) and battery:
                    latest = battery[-1].get("value", battery[-1])
                    if isinstance(latest, (int, float)):
                        points.append(HealthMetricPoint("garmin", READINESS_SCORE, float(latest), "score", d))

        sleep_data = garth.connectapi(f"/wellness-service/wellness/dailySleepData/{d}")
        if isinstance(sleep_data, dict):
            summary = sleep_data.get("dailySleepDTO", {})
            if "sleepTimeSeconds" in summary:
                points.append(HealthMetricPoint("garmin", SLEEP_DURATION, float(summary["sleepTimeSeconds"]) / 60, "min", d))
            if "deepSleepSeconds" in summary:
                points.append(HealthMetricPoint("garmin", SLEEP_DEEP, float(summary["deepSleepSeconds"]) / 60, "min", d))
            if "remSleepSeconds" in summary:
                points.append(HealthMetricPoint("garmin", SLEEP_REM, float(summary["remSleepSeconds"]) / 60, "min", d))
            if "lightSleepSeconds" in summary:
                points.append(HealthMetricPoint("garmin", SLEEP_LIGHT, float(summary["lightSleepSeconds"]) / 60, "min", d))
            if "awakeSleepSeconds" in summary:
                points.append(HealthMetricPoint("garmin", SLEEP_AWAKE, float(summary["awakeSleepSeconds"]) / 60, "min", d))
            if "averageSpO2" in summary:
                points.append(HealthMetricPoint("garmin", BLOOD_OXYGEN, float(summary["averageSpO2"]), "%", d))
            if "avgSleepStress" in summary and summary["avgSleepStress"] > 0:
                points.append(HealthMetricPoint("garmin", HRV, float(summary["avgSleepStress"]), "ms", d))

        hrv_data = garth.connectapi(f"/hrv-service/hrv/{d}")
        if isinstance(hrv_data, dict):
            hrv_val = hrv_data.get("lastNight", {}).get("avg5MinHrv")
            if hrv_val:
                points.append(HealthMetricPoint("garmin", HRV, float(hrv_val), "ms", d))

    except HealthIntegrationError:
        raise
    except Exception as e:
        _update_sync(db, "garmin", "error", 0, str(e))
        raise HealthIntegrationError(f"Garmin sync failed: {e}") from e

    count = persist(db, points)
    _update_sync(db, "garmin", "ok", count)
    return points


# ── Apple Health webhook (Health Auto Export format) ──────────────────────

def parse_apple_health_export(payload: dict, db: Session) -> list[HealthMetricPoint]:
    """
    Accept data in Health Auto Export / Health Export+ iOS app format.
    Expected shape: {"data": {"metrics": [{"name": "...", "units": "...", "data": [...]}]}}

    Configure the iOS app to POST to: POST /api/health/webhook/apple
    Add X-Health-Secret header matching health_webhook_secret in .env
    """
    metric_map = {
        "step_count": (STEPS, "steps"),
        "steps": (STEPS, "steps"),
        "heart_rate": (HEART_RATE, "bpm"),
        "resting_heart_rate": (RESTING_HR, "bpm"),
        "heart_rate_variability_sdnn": (HRV, "ms"),
        "hrv": (HRV, "ms"),
        "active_energy_burned": (CALORIES, "kcal"),
        "distance_walking_running": (DISTANCE_KM, "km"),
        "body_mass": (WEIGHT_KG, "kg"),
        "body_mass_index": (BMI, "kg/m2"),
        "body_fat_percentage": (BODY_FAT_PCT, "%"),
        "oxygen_saturation": (BLOOD_OXYGEN, "%"),
        "blood_pressure_systolic": (BP_SYSTOLIC, "mmHg"),
        "blood_pressure_diastolic": (BP_DIASTOLIC, "mmHg"),
        "respiratory_rate": (RESPIRATORY_RATE, "rpm"),
        "vo2_max": (VO2_MAX, "mL/kg/min"),
        "sleep_analysis": (SLEEP_DURATION, "min"),
        "mindful_minutes": (ACTIVE_MINUTES, "min"),
    }

    points: list[HealthMetricPoint] = []
    metrics_list = payload.get("data", {}).get("metrics", payload.get("metrics", []))

    for metric in metrics_list:
        raw_name = metric.get("name", "").lower().replace(" ", "_")
        if raw_name not in metric_map:
            continue
        m_type, m_unit = metric_map[raw_name]
        for dp in metric.get("data", []):
            qty = dp.get("qty") or dp.get("value") or dp.get("Qty")
            date_raw = dp.get("date") or dp.get("startDate") or dp.get("Date")
            if qty is None or not date_raw:
                continue
            try:
                date_str = str(date_raw)[:10]
                ts = datetime.fromisoformat(date_raw.replace("Z", "+00:00")) if "T" in date_raw else None
                # Distance: Apple Health reports in km by default but check units
                unit_raw = metric.get("units", "")
                val = float(qty)
                if m_type == DISTANCE_KM and "mi" in unit_raw.lower():
                    val *= 1.60934
                points.append(HealthMetricPoint("apple", m_type, val, m_unit, date_str, ts))
            except Exception:
                continue

    if points:
        persist(db, points)
        _update_sync(db, "apple", "ok", len(points))
    return points


# ── Samsung Health webhook ────────────────────────────────────────────────

def parse_samsung_health_export(payload: dict, db: Session) -> list[HealthMetricPoint]:
    """
    Accept data from Samsung Health compatible exporter apps.
    Supports both Health Auto Export-compatible format and Samsung Health raw export JSON.

    Configure your exporter to POST to: POST /api/health/webhook/samsung
    Add X-Health-Secret header matching health_webhook_secret in .env
    """
    # Samsung Health raw export uses camelCase keys
    metric_map = {
        "step_count": (STEPS, "steps"),
        "stepCount": (STEPS, "steps"),
        "heart_rate": (HEART_RATE, "bpm"),
        "heartRate": (HEART_RATE, "bpm"),
        "calories": (CALORIES, "kcal"),
        "caloriesBurned": (CALORIES, "kcal"),
        "distance": (DISTANCE_KM, "km"),
        "sleepDuration": (SLEEP_DURATION, "min"),
        "weight": (WEIGHT_KG, "kg"),
        "bloodOxygen": (BLOOD_OXYGEN, "%"),
        "stressScore": (STRESS_SCORE, "score"),
        "vo2Max": (VO2_MAX, "mL/kg/min"),
    }

    points: list[HealthMetricPoint] = []

    # Try Health Auto Export format first
    metrics_list = payload.get("data", {}).get("metrics", payload.get("metrics", []))
    if metrics_list:
        return parse_apple_health_export(payload, db)  # compatible format

    # Samsung Health raw JSON format
    for key, (m_type, m_unit) in metric_map.items():
        if key in payload:
            entries = payload[key]
            if not isinstance(entries, list):
                entries = [entries]
            for entry in entries:
                val = entry.get("value") or entry.get("count") or entry.get("amount")
                date_raw = entry.get("start_time") or entry.get("date") or entry.get("timestamp")
                if val is None or not date_raw:
                    continue
                try:
                    date_str = str(date_raw)[:10]
                    ts = None
                    if "T" in str(date_raw):
                        ts = datetime.fromisoformat(str(date_raw).replace("Z", "+00:00"))
                    points.append(HealthMetricPoint("samsung", m_type, float(val), m_unit, date_str, ts))
                except Exception:
                    continue

    if points:
        persist(db, points)
        _update_sync(db, "samsung", "ok", len(points))
    return points


# ── Unified sync dispatcher ───────────────────────────────────────────────

PLATFORM_SYNC = {
    "fitbit": fitbit_sync,
    "google_fit": google_fit_sync,
    "oura": oura_sync,
    "withings": withings_sync,
    "garmin": garmin_sync,
}

PLATFORM_CONFIGURED = {
    "fitbit": fitbit_is_configured,
    "google_fit": google_fit_is_configured,
    "oura": oura_is_configured,
    "withings": withings_is_configured,
    "garmin": garmin_is_configured,
    "apple": lambda: True,    # always available (webhook-based)
    "samsung": lambda: True,  # always available (webhook-based)
}

PLATFORM_OAUTH = {
    "fitbit": (fitbit_oauth_url, fitbit_exchange_code),
    "google_fit": (google_fit_oauth_url, google_fit_exchange_code),
    "withings": (withings_oauth_url, withings_exchange_code),
}


async def sync_all(db: Session, target_date: Optional[str] = None) -> dict[str, int]:
    """Trigger sync on all configured API platforms. Returns {platform: points_saved}."""
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
    syncs = {r["platform"]: r for r in get_sync_status(db)}
    platforms = []
    for name, configured_fn in PLATFORM_CONFIGURED.items():
        sync = syncs.get(name, {})
        platforms.append({
            "platform": name,
            "configured": configured_fn(),
            "auth_type": "webhook" if name in ("apple", "samsung") else
                         ("api_key" if name == "oura" else
                          ("credentials" if name == "garmin" else "oauth2")),
            "status": sync.get("status", "never"),
            "last_sync_at": sync.get("last_sync_at"),
            "metrics_synced": sync.get("metrics_synced", 0),
        })
    return {"platforms": platforms}
