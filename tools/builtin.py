import html
import math
import os
import platform
import re
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List
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


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write text content to a file in the workspace. Creates parent directories automatically if needed."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path of the file to create or write to.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write to the file.",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite if file already exists (default: true).",
            },
        },
        "required": ["file_path", "content"],
    }

    def execute(self, file_path: str = "", content: str = "", overwrite: bool = True, **kwargs: Any) -> str:
        if not file_path:
            return "Error: file_path is required."
        try:
            parent = os.path.dirname(file_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            if os.path.exists(file_path) and not overwrite:
                return f"Error: File '{file_path}' already exists and overwrite is set to False."

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Successfully wrote {len(content)} characters to '{file_path}'."
        except Exception as e:
            return f"Error writing file '{file_path}': {str(e)}"


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Perform targeted text replacement in an existing file in the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit.",
            },
            "target_text": {
                "type": "string",
                "description": "The exact substring in the file to be replaced.",
            },
            "replacement_text": {
                "type": "string",
                "description": "The new replacement string.",
            },
        },
        "required": ["file_path", "target_text", "replacement_text"],
    }

    def execute(self, file_path: str = "", target_text: str = "", replacement_text: str = "", **kwargs: Any) -> str:
        if not file_path:
            return "Error: file_path is required."
        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist."
        if not target_text:
            return "Error: target_text is required."

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()

            if target_text not in original:
                return f"Error: target_text was not found in '{file_path}'. Check exact casing and whitespace."

            updated = original.replace(target_text, replacement_text, 1)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated)

            return f"Successfully edited '{file_path}'."
        except Exception as e:
            return f"Error editing file '{file_path}': {str(e)}"


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a specific file or empty folder in the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to delete.",
            }
        },
        "required": ["file_path"],
    }

    def execute(self, file_path: str = "", **kwargs: Any) -> str:
        if not file_path:
            return "Error: file_path is required."
        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist."
        try:
            if os.path.isdir(file_path):
                os.rmdir(file_path)
                return f"Successfully removed directory '{file_path}'."
            else:
                os.remove(file_path)
                return f"Successfully deleted file '{file_path}'."
        except Exception as e:
            return f"Error deleting '{file_path}': {str(e)}"



class ExecuteCommandTool(BaseTool):
    name = "execute_command"
    description = "Execute a local shell or terminal command in the workspace directory with timeout and safety checks."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute (e.g. 'git status', 'python -m pytest', 'dir').",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30, max: 60).",
            },
        },
        "required": ["command"],
    }

    BLOCKED_PATTERNS = [
        r"\bformat\s+[a-zA-Z]:",
        r"\brmdir\s+/[sS]\s+/[qQ]\s+[cC]:\\",
        r"\brm\s+-rf\s+/\b",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
        r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]\s+[cC]:\\windows",
    ]

    def execute(self, command: str = "", timeout: int = 30, **kwargs: Any) -> str:
        if not command or not command.strip():
            return "Error: command parameter is required."

        cmd_clean = command.strip()
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                return f"Blocked: Command matches safety guardrail blocklist ('{pattern}'). Execution prevented."

        actual_timeout = min(max(1, timeout), 60)
        try:
            proc = subprocess.run(
                cmd_clean,
                shell=True,
                capture_output=True,
                text=True,
                timeout=actual_timeout,
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            code = proc.returncode

            output = []
            if stdout:
                output.append(stdout[:3000])
            if stderr:
                output.append(f"[STDERR]:\n{stderr[:1500]}")
            if not stdout and not stderr:
                output.append("(Command produced no standard output)")

            result_body = "\n\n".join(output)
            return f"Exit Code: {code}\nOutput:\n{result_body}"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {actual_timeout} seconds."
        except Exception as e:
            return f"Error executing command: {str(e)}"


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for technical documentation, tutorials, or public information via DuckDuckGo."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query keywords.",
            }
        },
        "required": ["query"],
    }

    def execute(self, query: str = "", **kwargs: Any) -> str:
        if not query or not query.strip():
            return "Error: query is required."
        try:
            encoded = urllib.parse.quote(query.strip())
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_html = resp.read().decode("utf-8", errors="replace")

            # Extract snippets using regex
            snippets = []
            matches = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', raw_html, re.DOTALL)
            for m in matches[:4]:
                clean = re.sub(r"<[^>]+>", "", m)
                clean = html.unescape(clean).strip()
                if clean:
                    snippets.append(clean)

            if not snippets:
                # Fallback: extract title snippets
                title_matches = re.findall(r'<a class="result__url[^>]*>(.*?)</a>', raw_html, re.DOTALL)
                for t in title_matches[:3]:
                    clean = re.sub(r"<[^>]+>", "", t).strip()
                    if clean:
                        snippets.append(clean)

            if snippets:
                return "Web Search Results:\n" + "\n\n".join(f"- {s}" for s in snippets)
            return f"No clear results found for query: '{query}'."
        except Exception as e:
            return f"Web search error: {str(e)}"


class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = "Fetch and extract readable text from a web URL."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The web URL to fetch.",
            }
        },
        "required": ["url"],
    }

    def execute(self, url: str = "", **kwargs: Any) -> str:
        if not url or not url.strip():
            return "Error: url is required."
        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = f"https://{clean_url}"

        try:
            req = urllib.request.Request(
                clean_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw_html = resp.read().decode("utf-8", errors="replace")

            # Strip scripts, styles, and tags
            no_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", no_scripts)
            clean_text = html.unescape(clean_text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()

            return clean_text[:2500] if clean_text else "Page returned empty content."
        except Exception as e:
            return f"Error fetching URL '{url}': {str(e)}"


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
