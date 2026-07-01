"""Base tool class — all agent tools inherit from this.

Provides:
    - Standardised interface (name, description, args_schema, _run)
    - Tool context injection (db, user_id, employee_id, user_email)
    - Conversion to LangChain StructuredTool
"""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel


class ToolContext(BaseModel):
    """Per-request context injected into tools at execution time."""
    user_id: int
    employee_id: int | None = None
    user_email: str | None = None

    class Config:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Module-level context registry — avoids threading through LangGraph nodes
# ---------------------------------------------------------------------------

_registry: dict[str, Any] = {}


def set_tool_context(**kwargs) -> None:
    """Set service references for tool execution. Called at request time."""
    _registry.update(kwargs)


def get_tool_context() -> ToolContext:
    """Get the current tool execution context."""
    return ToolContext(
        user_id=_registry.get("user_id", 0),
        employee_id=_registry.get("employee_id"),
        user_email=_registry.get("user_email"),
    )


# ---------------------------------------------------------------------------
# Base Tool
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    """Abstract base for all agent tools.

    Subclasses must define:
        name: str
        description: str
        args_schema: type[BaseModel]  — Pydantic model for LLM function parameters

    And implement:
        _run(**kwargs) -> Any  — the actual tool logic
    """

    name: str
    description: str
    args_schema: type[BaseModel]

    def __init__(self):
        self._context = get_tool_context()

    @abstractmethod
    def _run(self, **kwargs) -> Any:
        """Execute the tool. Subclasses implement this."""
        ...

    def to_langchain_tool(self) -> StructuredTool:
        """Convert to a LangChain StructuredTool for the agent graph."""
        return StructuredTool(
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            func=self._run,
        )

    def invoke(self, input_dict: dict) -> Any:
        """LangChain-compatible invoke (for ToolNode compatibility)."""
        return self._run(**input_dict)
