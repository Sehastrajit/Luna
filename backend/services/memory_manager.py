"""
Luna's memory system.
Three layers: working (conversation), semantic (ChromaDB vector search), episodic (summaries).
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from backend.config import settings
from backend.models.database import Fact, Conversation, Message
from backend.services.llm import ollama


class MemoryManager:
    def __init__(self, db: Session):
        self.db = db
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            self._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="luna_memories",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def _embed(self, text: str) -> list[float]:
        return await ollama.embed(text)

    async def store_fact(
        self,
        content: str,
        category: str,
        conversation_id: Optional[int] = None,
        confidence: float = 1.0,
        importance: float = 0.5,
        source: str = "inferred",
        expires_at=None,
        is_private: bool = False,
        memory_type: str = "long",
        expires_in_days: Optional[float] = None,
    ) -> int:
        from datetime import timedelta
        if expires_at is None:
            if expires_in_days is not None:
                expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            elif memory_type == "persistent":
                expires_at = datetime.utcnow() + timedelta(days=3)    # fallback: 3 days
            elif memory_type == "short":
                expires_at = datetime.utcnow() + timedelta(days=30)   # fallback: month
            # long: no expiry

        # Deactivate expired facts before storing a new one
        self._expire_stale_facts()

        # Check for semantic duplicate on the first 40 chars
        existing = (
            self.db.query(Fact)
            .filter(Fact.content.ilike(f"%{content[:40]}%"), Fact.is_active == True)
            .first()
        )
        if existing:
            # Reinforce confidence and bump importance if new one is more certain
            existing.confidence = min(1.0, existing.confidence + 0.1)
            existing.importance = max(existing.importance, importance)
            existing.updated_at = datetime.utcnow()
            # Pattern detection: persistent fact seen enough times → promote to long (it's a routine)
            if (existing.memory_type == "persistent" and existing.confidence >= 0.9
                    and existing.created_at
                    and (datetime.utcnow() - existing.created_at).days >= 2):
                existing.memory_type = "long"
                existing.expires_at = None
            self.db.commit()
            return existing.id

        fact = Fact(
            category=category,
            content=content,
            confidence=confidence,
            importance=importance,
            source=source,
            expires_at=expires_at,
            is_private=is_private,
            source_conversation_id=conversation_id,
            memory_type=memory_type,
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)

        # Embed and store in ChromaDB
        try:
            embedding = await self._embed(content)
            if embedding:
                col = self._get_collection()
                col.add(
                    ids=[f"fact_{fact.id}"],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[{
                        "type": "fact",
                        "category": category,
                        "fact_id": fact.id,
                        "importance": importance,
                        "created_at": datetime.utcnow().timestamp(),
                    }],
                )
        except Exception:
            pass  # ChromaDB failure shouldn't break fact storage

        # LLM-based contradiction check runs in background after commit
        try:
            import asyncio
            asyncio.create_task(
                self._bg_llm_contradiction_check(fact.id, content, category, conversation_id)
            )
        except Exception:
            pass

        return fact.id

    def _expire_stale_facts(self):
        """Deactivate facts whose expires_at has passed."""
        now = datetime.utcnow()
        expired = (
            self.db.query(Fact)
            .filter(Fact.is_active == True, Fact.expires_at != None, Fact.expires_at <= now)
            .all()
        )
        for f in expired:
            f.is_active = False
        if expired:
            self.db.commit()

    async def _bg_llm_contradiction_check(
        self,
        new_fact_id: int,
        content: str,
        category: str,
        conversation_id,
    ):
        """
        Background: use LLM + ChromaDB to detect if the new fact contradicts
        any existing fact. If so, supersede the old one and queue a system-prompt
        note so Luna can acknowledge the update naturally on the next turn.
        """
        from backend.models.database import SessionLocal, FactRelationship
        from backend.services.contradiction_store import add as _store_note
        import json as _json, re as _re

        db = SessionLocal()
        try:
            # Step 1 — find semantically similar facts
            embedding = await self._embed(content)
            if not embedding:
                return
            col = self._get_collection()
            if col.count() < 2:
                return

            n = min(8, col.count())
            results = col.query(
                query_embeddings=[embedding],
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )
            docs      = results["documents"][0]
            metas     = results["metadatas"][0]
            distances = results["distances"][0]

            # Only consider active facts that are close enough to be relevant
            candidates = []
            for doc, meta, dist in zip(docs, metas, distances):
                fid = meta.get("fact_id")
                if not fid or int(fid) == new_fact_id or dist > 0.65:
                    continue
                fact_obj = db.query(Fact).filter_by(id=int(fid), is_active=True).first()
                if fact_obj:
                    candidates.append((int(fid), doc, fact_obj))

            if not candidates:
                return

            # Step 2 — ask LLM whether any candidate is contradicted
            pairs = "\n".join(
                f"{i+1}. [ID:{fid}] {doc}"
                for i, (fid, doc, _) in enumerate(candidates)
            )
            prompt = (
                f'New fact: "{content}"\n\n'
                f"Existing facts:\n{pairs}\n\n"
                "Does the new fact DIRECTLY CONTRADICT one of the existing facts? "
                "Contradiction = they cannot both be true simultaneously. "
                "Updates and refinements count. Additions do not.\n\n"
                'Reply ONLY with JSON: {"contradicts_id": <number or null>, "note": "<one sentence reason or empty>"}'
            )

            raw = await ollama.complete(
                prompt,
                system="You are a fact contradiction detector. Output only valid JSON. No commentary.",
                temperature=0.05,
            )

            m = _re.search(r'\{[^{}]*\}', raw, _re.DOTALL)
            if not m:
                return
            result = _json.loads(m.group())
            contradicts_id = result.get("contradicts_id")
            note = str(result.get("note", "")).strip()

            if not contradicts_id:
                return

            contradicts_id = int(contradicts_id)
            old_fact = db.query(Fact).filter_by(id=contradicts_id, is_active=True).first()
            if not old_fact:
                return

            old_content = old_fact.content

            # Step 3 — supersede the old fact
            old_fact.is_active = False
            old_fact.superseded_by = new_fact_id

            # Record the relationship
            db.add(FactRelationship(
                fact_id_a=new_fact_id,
                fact_id_b=contradicts_id,
                relationship="contradicts",
                confidence=0.9,
                note=note,
            ))
            db.commit()

            # Remove superseded fact from ChromaDB so it doesn't pollute retrieval
            try:
                col.delete(ids=[f"fact_{contradicts_id}"])
            except Exception:
                pass

            # Step 4 — queue a note for Luna's next system prompt
            _store_note(
                f'Memory just updated: you previously knew "{old_content}" '
                f'but that has been superseded by "{content}". '
                "If it comes up naturally, acknowledge the change briefly — don't force it.",
                conversation_id=conversation_id,
            )

        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

    async def store_conversation_summary(self, summary: str, conversation_id: int):
        try:
            embedding = await self._embed(summary)
            if embedding:
                col = self._get_collection()
                col.upsert(
                    ids=[f"conv_{conversation_id}"],
                    embeddings=[embedding],
                    documents=[summary],
                    metadatas=[{
                        "type": "conversation",
                        "conversation_id": conversation_id,
                        "created_at": datetime.utcnow().timestamp(),
                    }],
                )
        except Exception:
            pass

    async def retrieve_relevant(
        self, query: str, n: int = None
    ) -> dict[str, list[str]]:
        """
        Returns {"short_term": [...], "long_term": [...]}.
        Short-term  = memories from the last 48 h, recency-boosted.
        Long-term   = older memories, relevance-only.
        Persistent core facts are fetched separately via get_core_facts().
        """
        n = n or settings.memory_retrieval_count
        half = max(n // 2, 2)
        empty: dict[str, list[str]] = {"short_term": [], "long_term": []}

        try:
            embedding = await self._embed(query)
            if not embedding:
                return {"short_term": [], "long_term": self._fallback_facts()}

            col = self._get_collection()
            count = col.count()
            if count == 0:
                return {"short_term": [], "long_term": self._fallback_facts()}

            candidates = min(n * 4, count, 24)
            results = col.query(
                query_embeddings=[embedding],
                n_results=candidates,
                include=["documents", "metadatas", "distances"],
            )
            docs      = results.get("documents", [[]])[0]
            distances = results.get("distances",  [[]])[0]
            metas     = results.get("metadatas",  [[]])[0]

            now = datetime.utcnow().timestamp()
            TWO_DAYS   = 2   * 86_400
            THIRTY_DAYS = 30 * 86_400

            scored: list[tuple[str, float, float]] = []
            for doc, dist, meta in zip(docs, distances, metas):
                if dist >= 0.8:
                    continue  # too distant
                semantic  = 1.0 - dist
                created   = meta.get("created_at", now - THIRTY_DAYS)
                age_days  = max(0.0, (now - created) / 86_400)
                recency   = 1.0 / (1.0 + age_days * 0.15)
                importance = meta.get("importance", 0.5)
                score      = semantic * 0.55 + recency * 0.25 + importance * 0.20
                scored.append((doc, score, age_days))

            scored.sort(key=lambda x: x[1], reverse=True)

            short_term = [d for d, _, age in scored if age <  2][:half]
            long_term  = [d for d, _, age in scored if age >= 2][:half]
            return {"short_term": short_term, "long_term": long_term}

        except Exception:
            return {"short_term": [], "long_term": self._fallback_facts()}

    def _fallback_facts(self) -> list[str]:
        now = datetime.utcnow()
        facts = (
            self.db.query(Fact)
            .filter(
                Fact.is_active == True,
                Fact.is_private == False,
                (Fact.expires_at == None) | (Fact.expires_at > now),
            )
            .order_by(Fact.importance.desc(), Fact.updated_at.desc())
            .limit(settings.memory_retrieval_count)
            .all()
        )
        return [f.content for f in facts]

    def get_core_facts(self) -> list[str]:
        now = datetime.utcnow()
        personal = (
            self.db.query(Fact)
            .filter(
                Fact.category.in_(['personal', 'preference', 'relationship']),
                Fact.is_active == True,
                Fact.is_private == False,
                (Fact.expires_at == None) | (Fact.expires_at > now),
            )
            .order_by(Fact.importance.desc(), Fact.confidence.desc())
            .limit(10)
            .all()
        )
        return [f.content for f in personal]

    def _promote_routines(self) -> int:
        """Promote persistent facts that have become routines to long-term memory."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=2)
        candidates = (
            self.db.query(Fact)
            .filter(
                Fact.is_active == True,
                Fact.memory_type == "persistent",
                Fact.confidence >= 0.85,
                Fact.created_at <= cutoff,
            )
            .all()
        )
        promoted = 0
        for f in candidates:
            f.memory_type = "long"
            f.expires_at = None
            promoted += 1
        if promoted:
            self.db.commit()
        return promoted

    async def compact_facts(self) -> int:
        """
        Daily compaction: merge duplicate/near-identical facts per category.
        Uses the LLM to collapse redundant entries into clean single statements.
        Returns the number of facts removed.
        """
        import json as _json
        # First pass: promote any persistent facts that have become routines
        self._promote_routines()

        categories = ['personal', 'preference', 'relationship', 'context', 'behavior']
        removed = 0

        for cat in categories:
            facts = (
                self.db.query(Fact)
                .filter(
                    Fact.category == cat,
                    Fact.is_active == True,
                    Fact.memory_type == "long",  # short expires naturally; persistent stays as-is
                )
                .order_by(Fact.importance.desc(), Fact.updated_at.desc())
                .all()
            )
            if len(facts) < 2:
                continue  # nothing worth compacting

            numbered = "\n".join(f"{i+1}. {f.content}" for i, f in enumerate(facts))
            prompt = (
                f"These are long-term memory facts about a user in category '{cat}'.\n\n"
                f"{numbered}\n\n"
                "Task: merge any duplicates or near-duplicates into a single clean statement. "
                "Keep facts that are genuinely distinct. "
                "Reply ONLY with a JSON array of merged fact strings. "
                'Example: ["User prefers dark mode", "User is a software engineer"]'
            )

            try:
                raw = await ollama.complete(
                    prompt,
                    system="You are a precise memory curator. Output only valid JSON arrays. No commentary.",
                    temperature=0.1,
                )
                import re as _re
                m = _re.search(r'\[.*?\]|\[.*\]', raw, _re.DOTALL)
                if not m:
                    continue
                merged: list[str] = _json.loads(m.group())
                if not isinstance(merged, list):
                    continue

                # Only proceed if we actually reduced the count
                if len(merged) >= len(facts):
                    continue

                # Deactivate all old facts in this category
                best_importance = max(f.importance for f in facts)
                best_confidence = max(f.confidence for f in facts)
                col = self._get_collection()
                for f in facts:
                    f.is_active = False
                    # Only delete from ChromaDB if the embedding actually exists
                    try:
                        eid = f"fact_{f.id}"
                        existing = col.get(ids=[eid])
                        if existing and existing.get("ids"):
                            col.delete(ids=[eid])
                    except Exception:
                        pass
                removed += len(facts) - len(merged)

                # Store merged facts
                for content in merged:
                    content = content.strip()
                    if not content:
                        continue
                    new_fact = Fact(
                        category=cat,
                        content=content,
                        confidence=best_confidence,
                        importance=best_importance,
                        source="compaction",
                        memory_type="long",
                    )
                    self.db.add(new_fact)
                    self.db.flush()
                    try:
                        embedding = await self._embed(content)
                        if embedding:
                            col = self._get_collection()
                            col.add(
                                ids=[f"fact_{new_fact.id}"],
                                embeddings=[embedding],
                                documents=[content],
                                metadatas=[{"type": "fact", "category": cat,
                                            "fact_id": new_fact.id,
                                            "importance": best_importance,
                                            "created_at": datetime.utcnow().timestamp()}],
                            )
                    except Exception:
                        pass

                self.db.commit()
            except Exception:
                self.db.rollback()
                continue

        return removed

    def get_all_facts(self, category: Optional[str] = None) -> list[Fact]:
        q = self.db.query(Fact).filter(Fact.is_active == True)
        if category:
            q = q.filter(Fact.category == category)
        return q.order_by(Fact.updated_at.desc()).all()

    def get_upcoming_agenda(self) -> str:
        from backend.models.database import Task, CalendarEvent
        now = datetime.utcnow()
        from datetime import timedelta
        tomorrow = now + timedelta(days=1)

        tasks = (
            self.db.query(Task)
            .filter(Task.completed == False, Task.due_date <= tomorrow)
            .order_by(Task.due_date)
            .limit(5)
            .all()
        )
        events = (
            self.db.query(CalendarEvent)
            .filter(CalendarEvent.start_datetime >= now, CalendarEvent.start_datetime <= tomorrow)
            .order_by(CalendarEvent.start_datetime)
            .limit(5)
            .all()
        )

        lines = []
        for e in events:
            lines.append(f"- Event: {e.title} at {e.start_datetime.strftime('%H:%M')}")
        for t in tasks:
            due = t.due_date.strftime("%b %d") if t.due_date else "no date"
            lines.append(f"- Task [{t.priority}]: {t.title} (due {due})")
        return "\n".join(lines) if lines else "Nothing scheduled in the next 24 hours."

    def get_recent_conversation(self, conversation_id: int, limit: int = None) -> list[dict]:
        limit = limit or settings.max_conversation_history
        msgs = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in reversed(msgs)]

    def get_conversation_context(self, conversation_id: int, limit: int = None) -> str:
        """Return a compact transcript for prompt context."""
        conversation = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
        messages = self.get_recent_conversation(conversation_id, limit or settings.max_conversation_history)
        if not messages:
            if conversation and conversation.summary:
                return f"- Earlier summary: {conversation.summary}"
            return "- No recent messages yet."

        lines = []
        if conversation and conversation.summary:
            lines.append(f"- Earlier summary: {conversation.summary}")
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Luna"
            content = " ".join(msg["content"].split())
            if len(content) > 300:
                content = content[:297].rstrip() + "..."
            lines.append(f"- {role}: {content}")
        return "\n".join(lines)
