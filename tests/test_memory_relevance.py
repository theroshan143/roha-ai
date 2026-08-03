import os
import tempfile
from app.memory import MemoryManager


def test_memory_relevance_simple():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        mm = MemoryManager(db_path=path)
        mm.add_message("user", "I enjoy working on machine learning projects")
        mm.add_message("assistant", "Noted")
        mm.add_message("user", "My favorite language is Python")
        rel = mm.get_relevant_memories("machine learning", k=1)
        assert len(rel) == 1
        assert "machine learning" in rel[0].lower()
    finally:
        try:
            mm.close()
        except Exception:
            pass
        if os.path.exists(path):
            os.remove(path)
