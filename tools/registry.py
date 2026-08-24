import logging
from typing import Any, Dict, List, Optional
from tools.base import BaseTool


class ToolRegistry:
    """Registry for managing and executing Roha agent tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        if tool.name in self._tools:
            logging.warning("Overwriting existing tool registration for '%s'", tool.name)
        self._tools[tool.name] = tool
        logging.info("Registered tool: %s", tool.name)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return all registered tools formatted as Ollama function schemas."""
        return [tool.to_ollama_schema() for tool in self._tools.values()]

    def execute(self, name: str, kwargs: Dict[str, Any]) -> str:
        """Execute a tool by name with provided keyword arguments."""
        tool = self.get_tool(name)
        if not tool:
            error_msg = f"Error: Tool '{name}' is not registered."
            logging.error(error_msg)
            return error_msg

        try:
            logging.info("Executing tool '%s' with args: %s", name, kwargs)
            result = tool.execute(**kwargs)
            return str(result)
        except Exception as e:
            logging.exception("Failed to execute tool '%s'", name)
            return f"Error executing tool '{name}': {str(e)}"
