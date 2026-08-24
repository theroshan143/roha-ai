import unittest
from tools.builtin import CalculatorTool, ReadFileTool, SystemInfoTool
from tools.registry import ToolRegistry


class TestToolEngine(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(CalculatorTool())
        self.registry.register(ReadFileTool())
        self.registry.register(SystemInfoTool())

    def test_tool_registration_and_schemas(self):
        schemas = self.registry.get_schemas()
        self.assertEqual(len(schemas), 3)
        names = [s["function"]["name"] for s in schemas]
        self.assertIn("calculator", names)
        self.assertIn("read_file", names)
        self.assertIn("system_info", names)

    def test_calculator_execution(self):
        res = self.registry.execute("calculator", {"expression": "25 * 4"})
        self.assertIn("100", res)

    def test_system_info_execution(self):
        res = self.registry.execute("system_info", {})
        self.assertIn("OS:", res)

    def test_unregistered_tool(self):
        res = self.registry.execute("non_existent_tool", {})
        self.assertIn("Error", res)


if __name__ == "__main__":
    unittest.main()
