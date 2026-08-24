import os
import unittest
from unittest.mock import MagicMock, patch

from app.assistant_session import RohaSession


class TestReActLoop(unittest.TestCase):
    def setUp(self):
        self.db_path = "data/test_react.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    @patch("app.assistant_session.MemoryManager")
    @patch("app.assistant_session.create_default_tts")
    @patch("app.assistant_session._call_model_with_timeout")
    def test_single_turn_no_tools(self, mock_model_call, mock_tts, mock_memory):
        mock_memory.return_value.load_recent_history.return_value = []
        mock_memory.return_value.get_relevant_memories.return_value = []

        mock_model_call.return_value = {
            "content": "Hello! How can I help you?",
            "tool_calls": [],
        }

        session = RohaSession()
        reply = session.process_user_input("Hi")
        self.assertEqual(reply, "Hello! How can I help you?")
        self.assertEqual(mock_model_call.call_count, 1)

    @patch("app.assistant_session.MemoryManager")
    @patch("app.assistant_session.create_default_tts")
    @patch("app.assistant_session._call_model_with_timeout")
    def test_multi_step_react_loop(self, mock_model_call, mock_tts, mock_memory):
        mock_memory.return_value.load_recent_history.return_value = []
        mock_memory.return_value.get_relevant_memories.return_value = []

        # Step 1: Model calls system_info tool
        # Step 2: Model returns final text synthesis
        mock_model_call.side_effect = [
            {
                "content": "Checking system info...",
                "tool_calls": [{"function": {"name": "system_info", "arguments": {}}}],
            },
            {
                "content": "Your system is running Windows.",
                "tool_calls": [],
            },
        ]

        session = RohaSession()
        reply = session.process_user_input("Check my system")
        self.assertEqual(reply, "Your system is running Windows.")
        self.assertEqual(mock_model_call.call_count, 2)


if __name__ == "__main__":
    unittest.main()
