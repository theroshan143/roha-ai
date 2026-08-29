import os
import shutil
import unittest
from tools.builtin import (
    WriteFileTool,
    EditFileTool,
    ExecuteCommandTool,
    WebSearchTool,
    FetchUrlTool,
)
from app.assistant_session import RohaSession


class TestPhase3Tools(unittest.TestCase):
    def setUp(self):
        self.test_dir = "data/test_phase3_sandbox"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_write_file_tool(self):
        tool = WriteFileTool()
        target = os.path.join(self.test_dir, "nested/sample.txt")
        result = tool.execute(file_path=target, content="Hello Roha Agent!")
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.exists(target))

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "Hello Roha Agent!")

    def test_edit_file_tool(self):
        target = os.path.join(self.test_dir, "to_edit.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("Status: Inactive\nVersion: 1.0")

        tool = EditFileTool()
        result = tool.execute(file_path=target, target_text="Status: Inactive", replacement_text="Status: Active")
        self.assertIn("Successfully edited", result)

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "Status: Active\nVersion: 1.0")

    def test_execute_command_safe(self):
        tool = ExecuteCommandTool()
        # Safe echo command
        result = tool.execute(command="python -c \"print('Roha Safe Command')\"")
        self.assertIn("Exit Code: 0", result)
        self.assertIn("Roha Safe Command", result)

    def test_execute_command_blocked_safety(self):
        tool = ExecuteCommandTool()
        result = tool.execute(command="format C:")
        self.assertIn("Blocked: Command matches safety guardrail blocklist", result)

    def test_assistant_session_phase3_tool_registration(self):
        session = RohaSession()
        schemas = session.tool_registry.get_schemas()
        tool_names = [s["function"]["name"] for s in schemas]

        self.assertIn("write_file", tool_names)
        self.assertIn("edit_file", tool_names)
        self.assertIn("execute_command", tool_names)
        self.assertIn("web_search", tool_names)
        self.assertIn("fetch_url", tool_names)
        session.close()


if __name__ == "__main__":
    unittest.main()
