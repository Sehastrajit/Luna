"""Scheduled job functions — events, tasks, memory, personality, patterns."""
import re
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.models.database import SessionLocal, CalendarEvent, Task, ProactiveLog, Message
from backend.services.scheduler.notifications import send_windows_notification, proactive_queue


def check_upcoming_events():
    """Check for events starting within the next hour and notify."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        soon = now + timedelta(hours=1)
        events = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.start_datetime >= now,
                CalendarEvent.start_datetime <= soon,
            )
            .all()
        )
        for event in events:
            minutes = int((event.start_datetime - now).total_seconds() / 60)
            msg = f"Heads up — '{event.title}' starts in {minutes} minutes."
            send_windows_notification("Luna", msg)
            proactive_queue.append(msg)
            db.add(ProactiveLog(message=msg, reason="upcoming_event"))
        db.commit()
    finally:
        db.close()


def check_overdue_tasks():
    """Notify about overdue tasks once per day."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        overdue = (
            db.query(Task)
            .filter(Task.completed == False, Task.due_date < now)
            .all()
        )
        if overdue:
            names = ", ".join(t.title for t in overdue[:3])
            extra = f" (+{len(overdue) - 3} more)" if len(overdue) > 3 else ""
            msg = f"You have overdue tasks: {names}{extra}"
            send_windows_notification("Luna", msg)
            proactive_queue.append(msg)
            db.add(ProactiveLog(message=msg, reason="overdue_tasks"))
            db.commit()
    finally:
        db.close()


def daily_memory_compaction():
    """Merge redundant/duplicate facts once a day at 3am."""
    db: Session = SessionLocal()
    try:
        from backend.services.memory_manager import MemoryManager
        manager = MemoryManager(db)
        loop = asyncio.new_event_loop()
        removed = loop.run_until_complete(manager.compact_facts())
        loop.close()
        if removed > 0:
            print(f"[memory] Compaction complete — removed {removed} redundant facts.")
    except Exception as e:
        print(f"[memory] Compaction failed: {e}")
    finally:
        db.close()


def daily_personality_decay():
    """Decay personality preferences slightly toward neutral each day."""
    db: Session = SessionLocal()
    try:
        from backend.services.personality import PersonalityEngine
        engine = PersonalityEngine(db)
        engine.daily_decay()
    finally:
        db.close()


def morning_greeting():
    """Send a morning greeting notification."""
    msg = "Morning. Ready when you are."
    send_windows_notification("Luna", msg)
    proactive_queue.append(msg)
    db: Session = SessionLocal()
    try:
        db.add(ProactiveLog(message=msg, reason="morning_greeting"))
        db.commit()
    finally:
        db.close()


def confidence_decay():
    """
    Decay confidence of stale preference and goal facts slightly each week.
    Prevents outdated beliefs from competing equally with fresh information.
    Min confidence floor is 0.3 — facts are never deleted, just de-prioritised.
    """
    db: Session = SessionLocal()
    try:
        from backend.models.database import Fact
        cutoff = datetime.utcnow() - timedelta(days=30)
        stale = (
            db.query(Fact)
            .filter(
                Fact.is_active == True,
                Fact.category.in_(["preference", "goal"]),
                Fact.updated_at <= cutoff,
            )
            .all()
        )
        for f in stale:
            f.confidence = max(0.3, round(f.confidence - 0.04, 4))
        if stale:
            db.commit()
            print(f"[memory] Decayed confidence for {len(stale)} stale preference/goal facts.")
    except Exception as e:
        print(f"[memory] Confidence decay failed: {e}")
    finally:
        db.close()


def state_aware_proactive():
    """
    Check the current user state and send a contextual proactive message
    when the state warrants it. Runs every 10 minutes alongside the existing
    companion_check_in, but state-specific messaging takes priority.
    """
    db: Session = SessionLocal()
    try:
        from backend.services.state_engine import state_engine
        state = state_engine.infer_passive(db)
        now = datetime.utcnow()

        # Throttle: don't repeat state messages within 60 minutes
        recent = (
            db.query(ProactiveLog)
            .filter(ProactiveLog.reason.in_(["state_staying_up", "state_just_woke_up", "state_back_from_work"]))
            .order_by(ProactiveLog.sent_at.desc())
            .first()
        )
        if recent:
            since_min = (now - recent.sent_at.replace(tzinfo=None)).total_seconds() / 60
            if since_min < 60:
                return

        msg = None
        reason = None

        if state.value == "STAYING_UP":
            msg = "It's late and you've been active for a while.\n\nShould I switch to focus mode or set a sleep reminder?"
            reason = "state_staying_up"

        elif state.value == "JUST_WOKE_UP":
            today_end = now.replace(hour=23, minute=59)
            tasks = (
                db.query(Task)
                .filter(Task.completed == False, Task.due_date <= today_end)
                .limit(3).all()
            )
            events = (
                db.query(CalendarEvent)
                .filter(CalendarEvent.start_datetime >= now, CalendarEvent.start_datetime <= today_end)
                .limit(3).all()
            )
            parts = ["Morning. I'll keep it brief."]
            if events:
                ev_str = ", ".join(e.title for e in events)
                parts.append(f"You have: {ev_str} today.")
            if tasks:
                t_str = ", ".join(t.title for t in tasks)
                parts.append(f"Open tasks: {t_str}.")
            if not events and not tasks:
                parts.append("Nothing urgent on the schedule.")
            msg = "\n\n".join(parts)
            reason = "state_just_woke_up"

        elif state.value == "BACK_FROM_WORK":
            msg = "Welcome back. You sound like you might be tired.\n\nWant a quick summary or should I stay quiet?"
            reason = "state_back_from_work"

        if msg:
            proactive_queue.append(msg)
            send_windows_notification("Luna", msg.split("\n\n")[0])
            db.add(ProactiveLog(message=msg, reason=reason))
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def companion_check_in():
    """
    Let Luna initiate after a quiet stretch — message is LLM-generated from
    recent conversation context so it never repeats the same static line.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()

        last_user_msg = (
            db.query(Message)
            .filter(Message.role == "user")
            .order_by(Message.created_at.desc())
            .first()
        )
        if not last_user_msg:
            return

        last_ts = last_user_msg.created_at.replace(tzinfo=None)

        # Only check in during today's conversation window
        if last_ts.date() < now.date():
            return

        quiet_minutes = (now - last_ts).total_seconds() / 60
        if quiet_minutes < 25 or quiet_minutes > 180:
            return

        recent_proactive = (
            db.query(ProactiveLog)
            .filter(ProactiveLog.reason == "companion_check_in")
            .order_by(ProactiveLog.sent_at.desc())
            .first()
        )
        if recent_proactive:
            since_last = (now - recent_proactive.sent_at.replace(tzinfo=None)).total_seconds() / 60
            if since_last < 90:
                return

        recent_msgs = (
            db.query(Message)
            .order_by(Message.created_at.desc())
            .limit(6)
            .all()
        )
        context = "\n".join(
            f"{'User' if m.role == 'user' else 'Luna'}: {m.content[:120]}"
            for m in reversed(recent_msgs)
        )

        prompt = (
            f"The conversation ended {int(quiet_minutes)} minutes ago.\n\n"
            f"Recent exchange:\n{context}\n\n"
            "Generate a single short unprompted message from Luna to check in naturally. "
            "Rules: max 2 sentences, no questions asking how they are, not clingy, "
            "could be a random thought or gentle observation rooted in what was discussed. "
            "Match Luna's terse, warm-but-not-gushing style."
        )

        try:
            loop = asyncio.new_event_loop()
            from backend.services.llm import ollama as _ollama
            msg = loop.run_until_complete(
                _ollama.complete(
                    prompt,
                    system="You are Luna. Be brief. No emojis. No terms of endearment.",
                    temperature=0.85,
                )
            )
            loop.close()
            msg = msg.strip().strip('"')[:240]
        except Exception:
            return

        if not msg or len(msg) < 5:
            return

        proactive_queue.append(msg)
        db.add(ProactiveLog(message=msg, reason="companion_check_in"))
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


_COMMITMENT_RE = re.compile(
    r'\b('
    r'tomorrow|next week|'
    r'next (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
    r'this (?:friday|thursday|wednesday|tuesday|monday|weekend)|'
    r'tonight|later today|in a few days|'
    r'(?:interview|presentation|exam|test|deadline|surgery|appointment|flight)'
    r')\b',
    re.IGNORECASE,
)


def mine_behavioral_patterns():
    """
    Mine StateEvent table to detect recurring patterns (peak hours, stress days,
    late-night tendency) and store them as long-term behavioral facts.
    Runs daily at 4 am — enough data accumulates within a week.
    """
    db: Session = SessionLocal()
    try:
        from backend.models.database import StateEvent, Fact
        from collections import Counter

        cutoff = datetime.utcnow() - timedelta(days=30)
        events = db.query(StateEvent).filter(StateEvent.timestamp >= cutoff).all()
        if len(events) < 20:
            return  # not enough data yet

        patterns: list[str] = []
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]

        hour_counts = Counter(e.hour for e in events)
        if hour_counts:
            peak_hour = hour_counts.most_common(1)[0][0]
            ampm = "am" if peak_hour < 12 else "pm"
            h12 = peak_hour % 12 or 12
            patterns.append(f"User is most active around {h12}{ampm}")

        day_emotions: dict[int, list[str]] = {}
        for e in events:
            if e.emotion and e.emotion not in ("neutral", "calm"):
                day_emotions.setdefault(e.day_of_week, []).append(e.emotion)
        for dow, emotions in day_emotions.items():
            if len(emotions) < 5:
                continue
            dominant, count = Counter(emotions).most_common(1)[0]
            if dominant in ("sad", "angry", "stressed") and count / len(emotions) > 0.5:
                patterns.append(f"User often feels {dominant} on {day_names[dow]}s")

        late = sum(1 for e in events if e.hour >= 23 or e.hour < 4)
        if late / len(events) > 0.3:
            patterns.append("User is frequently active late at night")

        if not patterns:
            return

        mem_db: Session = SessionLocal()
        try:
            from backend.models.database import Fact
            from backend.services.memory_manager import MemoryManager
            manager = MemoryManager(mem_db)
            loop = asyncio.new_event_loop()
            saved = 0
            for pattern in patterns:
                already = mem_db.query(Fact).filter(
                    Fact.content.ilike(f"%{pattern[:35]}%"),
                    Fact.is_active == True,
                    Fact.category == "behavior",
                ).first()
                if not already:
                    loop.run_until_complete(
                        manager.store_fact(
                            pattern, "behavior",
                            memory_type="long",
                            importance=0.7,
                            source="pattern_mining",
                        )
                    )
                    saved += 1
            loop.close()
            if saved:
                print(f"[patterns] Stored {saved} new behavioral pattern(s).")
        finally:
            mem_db.close()
    except Exception as e:
        print(f"[patterns] Mining failed: {e}")
    finally:
        db.close()


def proactive_commitment_followup():
    """
    Scan user messages from 1–6 days ago for future-tense commitments (interviews,
    exams, appointments, etc.). If the event has likely passed, generate a follow-up.
    Throttled to one follow-up per 24 hours.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()

        recent = (
            db.query(ProactiveLog)
            .filter(ProactiveLog.reason == "commitment_followup")
            .order_by(ProactiveLog.sent_at.desc())
            .first()
        )
        if recent:
            hours_since = (now - recent.sent_at.replace(tzinfo=None)).total_seconds() / 3600
            if hours_since < 24:
                return

        start = now - timedelta(days=6)
        end   = now - timedelta(hours=20)

        messages = (
            db.query(Message)
            .filter(Message.role == "user", Message.created_at.between(start, end))
            .order_by(Message.created_at.desc())
            .limit(40)
            .all()
        )

        for msg in messages:
            if not _COMMITMENT_RE.search(msg.content):
                continue

            hours_ago = (now - msg.created_at.replace(tzinfo=None)).total_seconds() / 3600
            prompt = (
                f"The user said this {int(hours_ago)} hours ago:\n\"{msg.content[:200]}\"\n\n"
                "If the event or commitment mentioned has LIKELY ALREADY HAPPENED based on the "
                "time elapsed, write one short natural follow-up from Luna "
                "(e.g. 'How'd the interview go?' / 'Did the exam happen?'). "
                "If it hasn't passed yet or is unclear, reply with empty string exactly: \"\""
            )

            try:
                loop = asyncio.new_event_loop()
                from backend.services.llm import ollama as _ollama
                followup = loop.run_until_complete(
                    _ollama.complete(
                        prompt,
                        system="You are Luna. One sentence. No emojis. No terms of endearment.",
                        temperature=0.6,
                    )
                )
                loop.close()
                followup = followup.strip().strip('"')
            except Exception:
                continue

            if not followup or len(followup) < 5:
                continue

            proactive_queue.append(followup)
            db.add(ProactiveLog(message=followup, reason="commitment_followup"))
            db.commit()
            break  # one follow-up per run
    except Exception as e:
        print(f"[scheduler] Commitment followup failed: {e}")
    finally:
        db.close()
