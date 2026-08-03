import sqlite3
import atexit
import logging
from typing import List, Optional, Tuple, Any
from types import TracebackType


class MemoryManager:
    """Simple SQLite-backed memory manager.

    Use `add_message(role, content)` to persist messages and
    `get_memories(limit)` to retrieve recent memory entries.
    Call `close()` when done to release the DB connection.
    """

    def __init__(self, db_path: str = "data/roha.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_memory_table()
        atexit.register(self.close)

    def create_memory_table(self) -> None:
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        self.conn.commit()

    def add_message(self, role: str, content: str) -> None:
        try:
            self.cursor.execute(
                "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
            )
            self.conn.commit()
        except Exception:
            # on write failure, log and rollback but do not crash the whole app
            logging.exception("Failed to persist memory message (role=%s)", role)
            try:
                self.conn.rollback()
            except Exception:
                pass

    def get_memories(self, limit: Optional[int] = None) -> List[str]:
        if limit is not None and limit > 0:
            self.cursor.execute(
                "SELECT content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            )
            rows: List[Tuple[Any, ...]] = self.cursor.fetchall()
            # return oldest->newest order
            return [r[0] for r in reversed(rows)]

        self.cursor.execute("SELECT content FROM messages ORDER BY id ASC")
        rows2: List[Tuple[Any, ...]] = self.cursor.fetchall()
        return [row[0] for row in rows2]

    def get_relevant_memories(self, query: str, k: int = 5) -> List[str]:
        """Return up to k most relevant memory contents for the given query.

        This uses fuzzy string matching (rapidfuzz) as a lightweight semantic proxy.
        If rapidfuzz is not available, falls back to recent messages.
        """
        try:
            from rapidfuzz import fuzz
        except Exception:
            # rapidfuzz not installed; fallback to recency
            return self.get_memories(limit=k)

        # fetch recent N candidates to rank (bounded for performance)
        candidate_limit = max(200, k * 20)
        self.cursor.execute(
            "SELECT content FROM messages ORDER BY id DESC LIMIT ?", (candidate_limit,)
        )
        rows = [r[0] for r in self.cursor.fetchall()]
        if not rows:
            return []

        scored = []
        for r in rows:
            try:
                score = fuzz.token_set_ratio(query, r)
            except Exception:
                score = 0
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [t[1] for t in scored[:k]]
        return list(reversed(top))  # return oldest->newest ordering for selected items

    def summarize_memory(self, keep_last: int = 50, use_llm: bool = True) -> None:
        """Collapse older messages into a single summary entry.

        If use_llm is True, attempt to use the chat model to generate a concise
        summary. Falls back to a naive concatenation if the model call fails.
        """
        try:
            # count total messages
            self.cursor.execute("SELECT COUNT(*) FROM messages")
            total = self.cursor.fetchone()[0]
            if total <= keep_last:
                return

            # fetch oldest messages to summarize
            to_summarize = total - keep_last
            self.cursor.execute(
                "SELECT id, role, content FROM messages ORDER BY id ASC LIMIT ?",
                (to_summarize,),
            )
            rows: List[Tuple[Any, ...]] = self.cursor.fetchall()
            if not rows:
                return

            texts = [f"{r[1]}: {r[2]}" for r in rows]

            summary_text = None
            if use_llm:
                try:
                    from app.summarizer import summarize_texts

                    summary_text = summarize_texts(texts, max_chars=4000)
                except Exception:
                    logging.exception("LLM-based summarization failed, falling back to naive summary")

            if not summary_text:
                combined = " \n".join(texts)
                summary_text = (combined[:4000] + "...") if len(combined) > 4000 else combined

            # delete summarized rows using parameterized query
            ids: List[int] = [r[0] for r in rows]
            placeholders = ",".join(["?" for _ in ids])
            self.cursor.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", tuple(ids))

            # store summary as a memory entry
            self.cursor.execute(
                "INSERT INTO messages (role, content) VALUES (?, ?)", ("memory_summary", summary_text)
            )
            self.conn.commit()
        except Exception:
            logging.exception("Failed to summarize memory")
            try:
                self.conn.rollback()
            except Exception:
                pass

    def close(self) -> None:
        try:
            if hasattr(self, "conn") and self.conn:
                self.conn.close()
        except Exception:
            logging.exception("Error closing memory DB")

    # context manager support
    def __enter__(self) -> "MemoryManager":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """Context manager exit; close DB connection.

        Returns None (do not suppress exceptions).
        """
        self.close()
        return None
