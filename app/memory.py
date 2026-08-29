import sqlite3
import threading
import atexit
import logging
from typing import List, Optional, Tuple, Any
from types import TracebackType
from app.types import Message
from app.vector_memory import VectorMemoryStore


class MemoryManager:
    """Thread-safe SQLite-backed memory manager with 3-tier memory support.

    - Tier 1: Working memory (managed in session scratchpad).
    - Tier 2: Episodic conversation messages (SQLite messages table).
    - Tier 3: Semantic vector long-term memory (VectorMemoryStore with ONNX embeddings).
    """

    def __init__(self, db_path: str = "data/roha.db"):
        self.db_path = db_path
        self._local = threading.local()
        self.vector_store = VectorMemoryStore(db_path=self.db_path)
        self.create_memory_table()
        atexit.register(self.close)

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    def create_memory_table(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()

    def add_message(self, role: str, content: str) -> None:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
            )
            conn.commit()

            # Index meaningful user messages into Tier 3 Vector Knowledge Store
            if role == "user" and len(content.strip()) > 10:
                self.vector_store.add_memory(f"User: {content.strip()}", category="conversation")
        except Exception:
            logging.exception("Failed to persist memory message (role=%s)", role)
            try:
                self._get_connection().rollback()
            except Exception:
                pass

    def add_semantic_fact(self, text: str, category: str = "user_fact") -> bool:
        """Explicitly add a verified fact or preference to Tier 3 Vector Knowledge Store."""
        return self.vector_store.add_memory(text, category=category)

    def load_recent_history(self, limit: int = 12) -> List[Message]:
        """Fetch recent conversation messages formatted for RohaSession context hydration."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # Only select user/assistant messages for context hydration
            cursor.execute(
                "SELECT role, content FROM messages WHERE role IN ('user', 'assistant') ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            messages: List[Message] = [{"role": r[0], "content": r[1]} for r in reversed(rows)]
            return messages
        except Exception:
            logging.exception("Failed to load recent history from memory")
            return []

    def get_memories(self, limit: Optional[int] = None) -> List[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        if limit is not None and limit > 0:
            cursor.execute(
                "SELECT content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            )
            rows: List[Tuple[Any, ...]] = cursor.fetchall()
            return [r[0] for r in reversed(rows)]

        cursor.execute("SELECT content FROM messages ORDER BY id ASC")
        rows2: List[Tuple[Any, ...]] = cursor.fetchall()
        return [row[0] for row in rows2]

    def get_relevant_memories(self, query: str, k: int = 3) -> List[str]:
        """Return up to k most relevant memory snippets using semantic vector search with fuzzy fallback."""
        if not query or not query.strip():
            return []

        # 1. Query Tier 3 Semantic Vector Memory Store first
        try:
            semantic_matches = self.vector_store.search(query, k=k, min_similarity=0.35)
            if semantic_matches:
                return [f"{text} (relevance: {round(score, 2)})" for text, score in semantic_matches]
        except Exception:
            logging.exception("Semantic vector search failed, falling back to episodic search")

        # 2. Fallback to Episodic Messages Search (Rapidfuzz + Recency)
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            candidate_limit = max(100, k * 10)
            cursor.execute(
                "SELECT role, content FROM messages WHERE role IN ('user', 'assistant') ORDER BY id DESC LIMIT ?",
                (candidate_limit,),
            )
            rows = cursor.fetchall()
            if not rows:
                return []

            try:
                from rapidfuzz import fuzz
                scored = []
                for role, content in rows:
                    score = fuzz.token_set_ratio(query, content)
                    if score > 30:  # Only include relevant matches
                        scored.append((score, f"{role.capitalize()}: {content}"))
                scored.sort(key=lambda x: x[0], reverse=True)
                top = [item[1] for item in scored[:k]]
                return list(reversed(top))
            except Exception:
                # Fallback to recency if rapidfuzz is unavailable
                return [f"{r[0].capitalize()}: {r[1]}" for r in reversed(rows[:k])]
        except Exception:
            logging.exception("Failed to fetch relevant memories")
            return []


    def summarize_memory(self, keep_last: int = 50, use_llm: bool = True) -> None:
        """Collapse older messages into a summary entry."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages")
            total = cursor.fetchone()[0]
            if total <= keep_last:
                return

            to_summarize = total - keep_last
            cursor.execute(
                "SELECT id, role, content FROM messages ORDER BY id ASC LIMIT ?",
                (to_summarize,),
            )
            rows: List[Tuple[Any, ...]] = cursor.fetchall()
            if not rows:
                return

            texts = [f"{r[1]}: {r[2]}" for r in rows]
            summary_text = None

            if use_llm:
                try:
                    from app.summarizer import summarize_texts
                    summary_text = summarize_texts(texts, max_chars=4000)
                except Exception:
                    logging.exception("LLM summarization failed, using fallback")

            if not summary_text:
                combined = " \n".join(texts)
                summary_text = (combined[:4000] + "...") if len(combined) > 4000 else combined

            ids: List[int] = [r[0] for r in rows]
            placeholders = ",".join(["?" for _ in ids])
            cursor.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", tuple(ids))
            cursor.execute(
                "INSERT INTO messages (role, content) VALUES (?, ?)", ("memory_summary", summary_text)
            )
            conn.commit()
        except Exception:
            logging.exception("Failed to summarize memory")
            try:
                self._get_connection().rollback()
            except Exception:
                pass

    def close(self) -> None:
        try:
            if hasattr(self._local, "conn") and self._local.conn:
                self._local.conn.close()
                self._local.conn = None
        except Exception:
            logging.exception("Error closing memory DB")

    def __enter__(self) -> "MemoryManager":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        self.close()
        return None

