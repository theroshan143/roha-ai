import os
import unittest
from app.memory import MemoryManager


class TestMemoryManager(unittest.TestCase):
    DB_PATH = "data/test_roha.db"

    def setUp(self):
        # ensure data dir
        os.makedirs("data", exist_ok=True)
        # remove old test db if present
        try:
            os.remove(self.DB_PATH)
        except OSError:
            pass
        self.mm = MemoryManager(db_path=self.DB_PATH)

    def tearDown(self):
        self.mm.close()
        try:
            os.remove(self.DB_PATH)
        except OSError:
            pass

    def test_add_and_get(self):
        self.mm.add_message("user", "hello")
        self.mm.add_message("assistant", "hi there")
        mems = self.mm.get_memories()
        self.assertIn("hello", mems[0])

    def test_summarize_prunes(self):
        for i in range(60):
            self.mm.add_message("user", f"u{i}")
        # keep_last default 50 -> will summarize 10
        self.mm.summarize_memory(keep_last=50)
        mems = self.mm.get_memories()
        # after summarization there should be <= 51 entries (50 + summary)
        self.assertTrue(len(mems) <= 51)


if __name__ == "__main__":
    unittest.main()
