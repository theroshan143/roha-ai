import math
import os
import platform
import time
from typing import Any, Dict
from tools.base import BaseTool


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Safely evaluate basic mathematical expressions (e.g. '2 + 2', 'math.sqrt(16)', '15 * 45')."
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate.",
            }
        },
        "required": ["expression"],
    }

    def execute(self, expression: str = "", **kwargs: Any) -> str:
        if not expression:
            return "Error: Expression parameter is required."
        try:
            # Safe evaluation with allowed math functions
            allowed_names = {
                "math": math,
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "pow": pow,
                "sum": sum,
            }
            code = compile(expression, "<string>", "eval")
            for name in code.co_names:
                if name not in allowed_names and not hasattr(math, name):
                    raise NameError(f"Use of '{name}' is not allowed in math evaluator.")
            result = eval(code, {"__builtins__": {}}, allowed_names)
            return f"Result: {result}"
        except Exception as e:
            return f"Calculation Error: {str(e)}"


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read text contents of a file relative to the current workspace directory."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read.",
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum lines to read (default 100).",
            },
        },
        "required": ["file_path"],
    }

    def execute(self, file_path: str = "", max_lines: int = 100, **kwargs: Any) -> str:
        if not file_path:
            return "Error: file_path parameter is required."
        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist."
        try:
            lines = []
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... (truncated at {max_lines} lines)")
                        break
                    lines.append(line)
            return "".join(lines)
        except Exception as e:
            return f"Error reading file '{file_path}': {str(e)}"


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = "Retrieve basic system information including current local time, operating system, and Python version."
    parameters = {
        "type": "object",
        "properties": {},
    }

    def execute(self, **kwargs: Any) -> str:
        return (
            f"Local Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
            f"Architecture: {platform.machine()}\n"
            f"Python Version: {platform.python_version()}"
        )


class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List files and subdirectories inside a directory path in the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "Directory path to list (default '.' for workspace root).",
            }
        },
    }

    def execute(self, dir_path: str = ".", **kwargs: Any) -> str:
        target = dir_path or "."
        if not os.path.exists(target):
            return f"Error: Directory '{target}' does not exist."
        try:
            items = os.listdir(target)
            result = []
            for item in items[:60]:
                full = os.path.join(target, item)
                item_type = "[DIR]" if os.path.isdir(full) else "[FILE]"
                result.append(f"{item_type} {item}")
            return "\n".join(result) if result else "Directory is empty."
        except Exception as e:
            return f"Error listing directory '{target}': {str(e)}"

