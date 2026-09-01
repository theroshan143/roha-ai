import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.vector_memory import VectorMemoryStore
from app.memory import MemoryManager
from app.assistant_session import RohaSession
from app.web_app import WebState, RohaWebHandler


def test_vector_memory_update_delete_graph():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = VectorMemoryStore(db_path=db_path)
        ok1 = store.add_memory("Roshan likes Python programming", category="personal")
        ok2 = store.add_memory("Python is an interpreted high-level language", category="technology")
        assert ok1 and ok2

        memories = store.get_all_memories()
        assert len(memories) >= 2
        first_id = memories[0]["id"]

        # Test update
        up_ok = store.update_memory(first_id, "Python is awesome and dynamically typed", category="tech")
        assert up_ok
        updated_mems = store.get_all_memories()
        updated_first = next(m for m in updated_mems if m["id"] == first_id)
        assert "dynamically typed" in updated_first["text"]
        assert updated_first["category"] == "tech"

        # Test graph
        graph = store.get_memory_graph(limit=10, similarity_threshold=0.1)
        assert "nodes" in graph
        assert "links" in graph
        assert len(graph["nodes"]) >= 2

        # Test delete
        del_ok = store.delete_memory(first_id)
        assert del_ok
        after_del = store.get_all_memories()
        assert not any(m["id"] == first_id for m in after_del)

        store.close()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass


def test_memory_manager_detailed_and_playground():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        mgr = MemoryManager(db_path=db_path)
        mgr.add_message("user", "Hello world from test")
        mgr.add_message("assistant", "Greetings from Roha AI")
        mgr.vector_store.add_memory("Roha is an Odysseus-styled assistant", category="system")

        # Detailed messages
        msgs = mgr.get_detailed_messages()
        assert len(msgs) == 2
        user_msg = next(m for m in msgs if m["role"] == "user")
        assert user_msg["content"] == "Hello world from test"

        # Update message
        up_ok = mgr.update_message(user_msg["id"], "Hello universe updated")
        assert up_ok
        msgs_after = mgr.get_detailed_messages()
        updated_user = next(m for m in msgs_after if m["id"] == user_msg["id"])
        assert updated_user["content"] == "Hello universe updated"

        # Search playground
        res = mgr.search_playground("Odysseus assistant", k=5, min_similarity=0.1)
        assert "semantic_matches" in res
        assert "episodic_matches" in res
        assert "rag_context_preview" in res
        assert len(res["semantic_matches"]) >= 1

        # Delete message
        del_ok = mgr.delete_message(user_msg["id"])
        assert del_ok
        assert len(mgr.get_detailed_messages()) == 1

        mgr.close()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
