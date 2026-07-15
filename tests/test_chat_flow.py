import unittest
from unittest.mock import patch
import app.chat  # ensure submodule is loaded so patch can find attribute


class TestChatFlow(unittest.TestCase):
    @patch("app.chat.chat_with_roha")
    def test_main_flow_mocked(self, mock_chat):
        # mock reply
        mock_chat.return_value = "mocked reply"

        # import modules to ensure no import errors
        from app.prompts import load_system_prompt
        from app.memory import MemoryManager

        # basic smoke calls
        sp = load_system_prompt()
        self.assertTrue(isinstance(sp, str))

        mm = MemoryManager(db_path="data/test_flow.db")
        try:
            mm.add_message("user", "hello")
            reply = mock_chat([{"role": "system", "content": sp}, {"role": "user", "content": "hello"}])
            self.assertEqual(reply, "mocked reply")
        finally:
            mm.close()


if __name__ == "__main__":
    unittest.main()
