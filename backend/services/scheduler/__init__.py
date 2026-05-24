"""Luna proactive scheduler: background jobs, notifications, companion check-ins."""
from backend.services.scheduler.notifications import send_windows_notification, proactive_queue
from backend.services.scheduler.jobs import (
    check_upcoming_events,
    check_overdue_tasks,
    daily_memory_compaction,
    daily_personality_decay,
    morning_greeting,
    confidence_decay,
    state_aware_proactive,
    companion_check_in,
    _COMMITMENT_RE,
    mine_behavioral_patterns,
    proactive_commitment_followup,
)
from backend.services.scheduler.service import LunaScheduler, luna_scheduler

__all__ = [
    "send_windows_notification",
    "proactive_queue",
    "check_upcoming_events",
    "check_overdue_tasks",
    "daily_memory_compaction",
    "daily_personality_decay",
    "morning_greeting",
    "confidence_decay",
    "state_aware_proactive",
    "companion_check_in",
    "_COMMITMENT_RE",
    "mine_behavioral_patterns",
    "proactive_commitment_followup",
    "LunaScheduler",
    "luna_scheduler",
]
