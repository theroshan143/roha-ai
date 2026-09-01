import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.web_app import _resolve_secure_workspace_path, _build_workspace_tree


class TestPhase5Workspace(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self.temp_dir.name)

        # Create sample workspace structure
        os.makedirs(os.path.join(self.temp_dir.name, "app"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir.name, ".git"), exist_ok=True)

        with open(os.path.join(self.temp_dir.name, "run.py"), "w", encoding="utf-8") as f:
            f.write("print('hello world')")

        with open(os.path.join(self.temp_dir.name, "app", "main.py"), "w", encoding="utf-8") as f:
            f.write("# Main app entry point")

        with open(os.path.join(self.temp_dir.name, ".git", "config"), "w", encoding="utf-8") as f:
            f.write("[core]")

    def tearDown(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_build_workspace_tree(self):
        tree = _build_workspace_tree(self.temp_dir.name)
        names = [item["name"] for item in tree]

        # Should include regular files/directories
        self.assertIn("app", names)
        self.assertIn("run.py", names)

        # Should exclude hidden/ignored dirs like .git
        self.assertNotIn(".git", names)

        # App directory should have children
        app_node = next(item for item in tree if item["name"] == "app")
        self.assertTrue(app_node["is_dir"])
        self.assertEqual(len(app_node["children"]), 1)
        self.assertEqual(app_node["children"][0]["name"], "main.py")

    def test_resolve_secure_workspace_path_valid(self):
        target = _resolve_secure_workspace_path("app/main.py")
        expected = os.path.abspath(os.path.join(self.temp_dir.name, "app", "main.py"))
        self.assertEqual(target, expected)

    def test_path_traversal_prevention(self):
        # Attempting to access outside workspace should raise PermissionError
        with self.assertRaises(PermissionError):
            _resolve_secure_workspace_path("../outside_file.txt")

        with self.assertRaises(PermissionError):
            _resolve_secure_workspace_path("../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
