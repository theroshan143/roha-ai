import sqlite3
import threading
import logging
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

try:
    from fastembed import TextEmbedding
    _FASTEMBED_AVAILABLE = True
except Exception:
    _FASTEMBED_AVAILABLE = False


class VectorMemoryStore:
    """Tier 3: Local semantic vector memory store backed by SQLite BLOBs and fastembed.
    
    Generates 384-dimensional dense vectors using local ONNX models (bge-small-en-v1.5)
    and computes cosine similarity over stored knowledge records.
    """

    def __init__(self, db_path: str = "data/roha.db", embedding_model: str = "BAAI/bge-small-en-v1.5"):
        self.db_path = db_path
        self.model_name = embedding_model
        self._embedder: Optional[Any] = None
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    def _init_table(self) -> None:
        """Create semantic memories table if it doesn't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                embedding BLOB,
                category TEXT DEFAULT 'general',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

    def _get_embedder(self) -> Optional[Any]:
        """Lazy-load the fastembed ONNX model."""
        if not _FASTEMBED_AVAILABLE:
            return None
        if self._embedder is None:
            with self._lock:
                if self._embedder is None:
                    try:
                        self._embedder = TextEmbedding(model_name=self.model_name)
                        logging.info("Initialized local vector embedder: %s", self.model_name)
                    except Exception:
                        logging.exception("Failed to initialize fastembed model")
                        return None
        return self._embedder

    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """Generate a normalized 384-dimensional dense vector for text."""
        embedder = self._get_embedder()
        if embedder is None or not text or not text.strip():
            return None
        try:
            generator = embedder.embed([text])
            vector = next(iter(generator))
            vec_np = np.array(vector, dtype=np.float32)
            # Normalize vector for cosine similarity
            norm = np.linalg.norm(vec_np)
            if norm > 0:
                vec_np = vec_np / norm
            return vec_np
        except Exception:
            logging.exception("Failed to compute embedding vector")
            return None

    def add_memory(self, text: str, category: str = "general") -> bool:
        """Embed text and persist as a semantic memory record."""
        clean_text = (text or "").strip()
        if not clean_text:
            return False

        vec = self.embed_text(clean_text)
        blob = vec.tobytes() if vec is not None else None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO semantic_memories (text, embedding, category) VALUES (?, ?, ?)",
                (clean_text, blob, category),
            )
            conn.commit()
            return True
        except Exception:
            logging.exception("Failed to insert semantic memory")
            try:
                self._get_connection().rollback()
            except Exception:
                pass
            return False

    def search(self, query: str, k: int = 3, min_similarity: float = 0.4) -> List[Tuple[str, float]]:
        """Perform semantic vector search and return top-k matches with similarity scores."""
        clean_query = (query or "").strip()
        if not clean_query:
            return []

        query_vec = self.embed_text(clean_query)
        if query_vec is None:
            return []

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT text, embedding FROM semantic_memories WHERE embedding IS NOT NULL")
            rows = cursor.fetchall()
            if not rows:
                return []

            results = []
            for text, blob in rows:
                if not blob:
                    continue
                stored_vec = np.frombuffer(blob, dtype=np.float32)
                # Cosine similarity for normalized unit vectors is dot product
                similarity = float(np.dot(query_vec, stored_vec))
                if similarity >= min_similarity:
                    results.append((text, similarity))

            results.sort(key=lambda x: x[1], reverse=True)
            return results[:k]
        except Exception:
            logging.exception("Semantic vector search failed")
            return []

    def get_all_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent semantic memory records."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, text, category, created_at FROM semantic_memories ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {"id": r[0], "text": r[1], "category": r[2], "created_at": r[3]}
                for r in rows
            ]
        except Exception:
            logging.exception("Failed to retrieve semantic memories")
            return []

    def close(self) -> None:
        """Close thread-local DB connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
