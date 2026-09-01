"""Tests for hybrid local/cloud backend switching.

Tests provider registry, switching, command interception, and response normalization.
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestProviderRegistry(unittest.TestCase):
    """Test provider registry in config.py."""

    def test_providers_dict_exists(self):
        from app.config import PROVIDERS
        self.assertIsInstance(PROVIDERS, dict)
        self.assertIn("local", PROVIDERS)
        self.assertIn("cloud", PROVIDERS)

    def test_local_provider_config(self):
        from app.config import PROVIDERS
        local = PROVIDERS["local"]
        self.assertEqual(local["name"], "Local Ollama")
        self.assertIn("localhost", local["base_url"])
        self.assertIn("11434", local["base_url"])
        self.assertIsNotNone(local["model"])
        self.assertIsInstance(local["timeout"], int)

    def test_cloud_provider_config(self):
        from app.config import PROVIDERS
        cloud = PROVIDERS["cloud"]
        self.assertEqual(cloud["name"], "Groq Cloud")
        self.assertIn("groq.com", cloud["base_url"])
        self.assertIsNotNone(cloud["model"])
        self.assertIsInstance(cloud["timeout"], int)

    def test_default_provider(self):
        from app.config import DEFAULT_PROVIDER
        self.assertIn(DEFAULT_PROVIDER, ("local", "cloud"))


class TestSessionSwitchProvider(unittest.TestCase):
    """Test RohaSession.switch_provider() behavior."""

    @patch("app.assistant_session.MemoryManager")
    @patch("app.assistant_session.load_system_prompt", return_value="test prompt")
    @patch("app.assistant_session.create_default_tts", return_value=None)
    def setUp(self, mock_tts, mock_prompt, mock_mm):
        mock_mm_instance = MagicMock()
        mock_mm_instance.load_recent_history.return_value = []
        mock_mm_instance.get_memories.return_value = []
        mock_mm.return_value = mock_mm_instance
        from app.assistant_session import RohaSession
        self.session = RohaSession()

    def test_switch_to_cloud_without_api_key(self):
        """Switching to cloud should fail if GROQ_API_KEY is empty."""
        from app.config import PROVIDERS
        original_key = PROVIDERS["cloud"]["api_key"]
        PROVIDERS["cloud"]["api_key"] = ""
        try:
            result = self.session.switch_provider("cloud")
            self.assertFalse(result["ok"])
            self.assertIn("GROQ_API_KEY", result["error"])
        finally:
            PROVIDERS["cloud"]["api_key"] = original_key

    def test_switch_to_cloud_with_api_key(self):
        """Switching to cloud should succeed when API key is set."""
        from app.config import PROVIDERS
        original_key = PROVIDERS["cloud"]["api_key"]
        PROVIDERS["cloud"]["api_key"] = "test-key-123"
        try:
            result = self.session.switch_provider("cloud")
            self.assertTrue(result["ok"])
            self.assertEqual(result["provider"], "cloud")
            self.assertEqual(self.session.active_provider, "cloud")
            self.assertEqual(self.session.model, PROVIDERS["cloud"]["model"])
        finally:
            PROVIDERS["cloud"]["api_key"] = original_key

    def test_switch_to_local(self):
        """Switching to local should always succeed."""
        result = self.session.switch_provider("local")
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "local")
        self.assertEqual(self.session.active_provider, "local")

    def test_switch_to_invalid_provider(self):
        """Switching to unknown provider should return error."""
        result = self.session.switch_provider("azure")
        self.assertFalse(result["ok"])
        self.assertIn("azure", result["error"])

    def test_roundtrip_preserves_messages(self):
        """Switching providers should not lose conversation history."""
        self.session.messages.append({"role": "user", "content": "hello"})
        self.session.messages.append({"role": "assistant", "content": "hi"})
        msg_count_before = len(self.session.messages)

        from app.config import PROVIDERS
        original_key = PROVIDERS["cloud"]["api_key"]
        PROVIDERS["cloud"]["api_key"] = "test-key"
        try:
            self.session.switch_provider("cloud")
            self.session.switch_provider("local")
            self.assertEqual(len(self.session.messages), msg_count_before)
        finally:
            PROVIDERS["cloud"]["api_key"] = original_key

    def test_get_backend_status(self):
        """get_backend_status should return current provider info."""
        status = self.session.get_backend_status()
        self.assertIn("provider", status)
        self.assertIn("model", status)
        self.assertIn("provider_name", status)
        self.assertIn("base_url", status)

    def test_provider_config_property(self):
        """provider_config should return the active provider's config dict."""
        cfg = self.session.provider_config
        self.assertIn("name", cfg)
        self.assertIn("base_url", cfg)
        self.assertIn("model", cfg)


class TestBackendCommandInterception(unittest.TestCase):
    """Test /online, /offline, /backend command interception."""

    @patch("app.assistant_session.MemoryManager")
    @patch("app.assistant_session.load_system_prompt", return_value="test prompt")
    @patch("app.assistant_session.create_default_tts", return_value=None)
    def setUp(self, mock_tts, mock_prompt, mock_mm):
        mock_mm_instance = MagicMock()
        mock_mm_instance.load_recent_history.return_value = []
        mock_mm_instance.get_memories.return_value = []
        mock_mm.return_value = mock_mm_instance
        from app.assistant_session import RohaSession
        self.session = RohaSession()

    def test_offline_command(self):
        """'/offline' should switch to local and return confirmation."""
        reply = self.session.process_user_input("/offline")
        self.assertIn("LOCAL", reply)
        self.assertEqual(self.session.active_provider, "local")

    def test_online_command_no_key(self):
        """'/online' without API key should return error."""
        from app.config import PROVIDERS
        original_key = PROVIDERS["cloud"]["api_key"]
        PROVIDERS["cloud"]["api_key"] = ""
        try:
            reply = self.session.process_user_input("/online")
            self.assertIn("GROQ_API_KEY", reply)
        finally:
            PROVIDERS["cloud"]["api_key"] = original_key

    def test_online_command_with_key(self):
        """'/online' with API key should switch to cloud."""
        from app.config import PROVIDERS
        original_key = PROVIDERS["cloud"]["api_key"]
        PROVIDERS["cloud"]["api_key"] = "test-key"
        try:
            reply = self.session.process_user_input("/online")
            self.assertIn("CLOUD", reply)
            self.assertEqual(self.session.active_provider, "cloud")
        finally:
            PROVIDERS["cloud"]["api_key"] = original_key

    def test_backend_command(self):
        """'/backend' should return status without switching."""
        reply = self.session.process_user_input("/backend")
        self.assertIn("Backend", reply)
        self.assertIn("Model", reply)
        self.assertIn("Endpoint", reply)

    def test_normal_message_not_intercepted(self):
        """Regular messages should not be intercepted by backend handler."""
        result = self.session._handle_backend_command("hello world")
        self.assertIsNone(result)


class TestResponseNormalization(unittest.TestCase):
    """Test OpenAI response normalization in chat.py."""

    def test_normalize_empty_tool_calls(self):
        from app.chat import _normalize_tool_calls
        self.assertEqual(_normalize_tool_calls(None), [])
        self.assertEqual(_normalize_tool_calls([]), [])

    def test_normalize_dict_tool_calls(self):
        from app.chat import _normalize_tool_calls
        raw = [
            {
                "function": {
                    "name": "calculator",
                    "arguments": '{"expression": "2+2"}',
                }
            }
        ]
        result = _normalize_tool_calls(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["function"]["name"], "calculator")
        self.assertEqual(result[0]["function"]["arguments"], {"expression": "2+2"})

    def test_normalize_object_tool_calls(self):
        """Test normalization with OpenAI-style objects (with attributes)."""
        from app.chat import _normalize_tool_calls

        class MockFunction:
            def __init__(self):
                self.name = "web_search"
                self.arguments = '{"query": "test"}'

        class MockToolCall:
            def __init__(self):
                self.function = MockFunction()

        result = _normalize_tool_calls([MockToolCall()])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["function"]["name"], "web_search")
        self.assertEqual(result[0]["function"]["arguments"], {"query": "test"})

    def test_normalize_invalid_json_arguments(self):
        """Invalid JSON in arguments should be kept as string."""
        from app.chat import _normalize_tool_calls
        raw = [{"function": {"name": "test", "arguments": "not-json"}}]
        result = _normalize_tool_calls(raw)
        self.assertEqual(result[0]["function"]["arguments"], "not-json")


class TestToolSchemaConversion(unittest.TestCase):
    """Test Ollama-to-OpenAI tool schema conversion."""

    def test_passthrough_openai_format(self):
        from app.chat import _convert_tool_schema
        schema = {
            "type": "function",
            "function": {"name": "calc", "description": "Do math", "parameters": {}}
        }
        result = _convert_tool_schema(schema)
        self.assertEqual(result, schema)

    def test_wraps_bare_function(self):
        from app.chat import _convert_tool_schema
        bare = {"name": "calc", "description": "Do math", "parameters": {}}
        result = _convert_tool_schema(bare)
        self.assertEqual(result["type"], "function")
        self.assertEqual(result["function"], bare)


if __name__ == "__main__":
    unittest.main()
