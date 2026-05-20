from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, JSON, ForeignKey, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
from backend.config import settings

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sentiment_score = Column(Float, nullable=True)  # -1 to 1
    conversation = relationship("Conversation", back_populates="messages")


class Fact(Base):
    __tablename__ = "facts"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)  # personal|preference|relationship|event|goal|health
    content = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    source_conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    # Memory quality fields (improvement #5)
    importance = Column(Float, default=0.5)          # 0=trivial, 1=critical
    expires_at = Column(DateTime, nullable=True)      # auto-deactivate after this datetime
    is_private = Column(Boolean, default=False)       # hide from prompt context when True
    source = Column(String, default="inferred")       # explicit|inferred|observed
    superseded_by = Column(Integer, ForeignKey("facts.id"), nullable=True)  # conflict resolution
    memory_type = Column(String, default="long")      # "short" | "long" | "persistent"


class FactRelationship(Base):
    __tablename__ = "fact_relationships"
    id = Column(Integer, primary_key=True, index=True)
    fact_id_a = Column(Integer, ForeignKey("facts.id"), nullable=False)
    fact_id_b = Column(Integer, ForeignKey("facts.id"), nullable=False)
    relationship = Column(String, nullable=False)  # contradicts|confirms|updates|pattern
    confidence = Column(Float, default=0.8)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    priority = Column(String, default="medium")  # low|medium|high
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)
    recurring = Column(String, nullable=True)  # daily|weekly|monthly|yearly
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PersonalityState(Base):
    __tablename__ = "personality_state"
    id = Column(Integer, primary_key=True, default=1)
    # Learned style preferences (0.0 - 1.0)
    verbosity = Column(Float, default=0.5)        # 0=brief, 1=detailed
    formality = Column(Float, default=0.35)       # 0=casual, 1=formal
    humor = Column(Float, default=0.6)            # 0=serious, 1=witty
    depth = Column(Float, default=0.55)           # 0=surface, 1=technical deep
    emotional_support = Column(Float, default=0.7)
    question_frequency = Column(Float, default=0.5)
    # Mood state
    current_mood = Column(String, default="neutral")
    mood_intensity = Column(Float, default=0.5)
    energy_level = Column(Float, default=1.0)
    # Interaction history
    total_interactions = Column(Integer, default=0)
    positive_signals = Column(Integer, default=0)
    negative_signals = Column(Integer, default=0)
    last_interaction = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FeedbackLog(Base):
    __tablename__ = "feedback_log"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    reward_signal = Column(Float, nullable=False)  # -1.0 to 1.0
    response_features = Column(JSON, nullable=True)  # {verbosity, humor, depth, ...}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ProactiveLog(Base):
    __tablename__ = "proactive_log"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    reason = Column(String, nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class StateEvent(Base):
    """Time-aware state engine event log."""
    __tablename__ = "state_events"
    id             = Column(Integer, primary_key=True, index=True)
    timestamp      = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    hour           = Column(Integer, nullable=False)
    day_of_week    = Column(Integer, nullable=False)   # 0=Mon … 6=Sun
    transcript     = Column(Text, nullable=True)
    emotion        = Column(String, nullable=True)
    volume         = Column(Float, nullable=True)       # RMS 0-1 (normalised)
    speech_speed   = Column(Float, nullable=True)       # words-per-minute
    speech_duration= Column(Float, nullable=True)       # seconds
    pc_active      = Column(Boolean, nullable=True)
    active_app     = Column(String, nullable=True)      # process name
    idle_seconds   = Column(Integer, nullable=True)     # seconds since last input
    inferred_state = Column(String, nullable=False)     # UserState enum value


class SleepLog(Base):
    __tablename__ = "sleep_logs"
    id          = Column(Integer, primary_key=True, index=True)
    sleep_start = Column(DateTime, nullable=False)
    sleep_end   = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True)   # filled on wake
    label       = Column(String, nullable=True)        # "bedtime" | "nap" | "away"
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)
    # Add new columns to existing tables when they don't exist yet (SQLite ALTER TABLE)
    with engine.connect() as conn:
        for col, definition in [
            ("importance",     "REAL DEFAULT 0.5"),
            ("expires_at",     "DATETIME"),
            ("is_private",     "BOOLEAN DEFAULT 0"),
            ("source",         "VARCHAR DEFAULT 'inferred'"),
            ("superseded_by",  "INTEGER"),
            ("memory_type",    "VARCHAR DEFAULT 'long'"),
        ]:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE facts ADD COLUMN {col} {definition}"
                    )
                )
                conn.commit()
            except Exception:
                pass  # column already exists

    db = SessionLocal()
    try:
        state = db.query(PersonalityState).filter_by(id=1).first()
        if not state:
            db.add(PersonalityState(id=1))
            db.commit()
    finally:
        db.close()
