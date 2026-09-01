import os
import unittest
from app.vector_memory import VectorMemoryStore
from app.memory import MemoryManager


class TestVectorMemory(unittest.TestCase):
    def setUp(self):
        self.test_db = "data/test_vector.db"
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass
        self.store = VectorMemoryStore(db_path=self.test_db)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_embedding_generation_and_normalization(self):
        vec = self.store.embed_text("Roha is an autonomous personal AI agent.")
        self.assertIsNotNone(vec)
        self.assertEqual(len(vec), 384)

    def test_add_and_retrieve_memories(self):
        added = self.store.add_memory("Roshan loves programming in Python and Rust.", category="creator_fact")
        self.assertTrue(added)

        all_mems = self.store.get_all_memories()
        self.assertEqual(len(all_mems), 1)
        self.assertIn("Python and Rust", all_mems[0]["text"])

    def test_semantic_similarity_search(self):
        # Insert diverse facts
        self.store.add_memory("User enjoys playing badminton on weekends.", category="hobbies")
        self.store.add_memory("The project uses SQLite for persistent storage.", category="architecture")
        self.store.add_memory("User lives in Bangalore.", category="location")

        # Query semantically (e.g. asking about sports should match badminton)
        results = self.store.search("What sports or athletic activities does the user like?", k=1)
        self.assertGreater(len(results), 0)
        matched_text, score = results[0]
        self.assertIn("badminton", matched_text)
        self.assertGreater(score, 0.05)

    def test_memory_manager_integration(self):
        manager = MemoryManager(db_path=self.test_db)
        manager.add_semantic_fact("Creator preferred model is qwen2.5:3b-instruct.", category="model_preference")
        
        relevant = manager.get_relevant_memories("Which LLM model does the creator prefer?", k=1)
        self.assertGreater(len(relevant), 0)
        self.assertIn("qwen2.5:3b-instruct", relevant[0])
        manager.close()


if __name__ == "__main__":
    unittest.main()
