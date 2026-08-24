from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    """Abstract base class for all Roha tools."""

    name: str
    description: str
    parameters: Dict[str, Any]

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Execute the tool logic and return a string representation of the result."""
        pass

    def to_ollama_schema(self) -> Dict[str, Any]:
        """Convert tool metadata to the standard Ollama tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
