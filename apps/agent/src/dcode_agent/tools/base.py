"""Tool abstract base + registry — implements DESIGN.md §2.3.2.

Every agent tool subclasses `Tool[ArgsT, ResultT]` and exposes:
  - `name`        — canonical identifier shown to the planner LLM
  - `description` — natural-language hint for tool choice
  - `ArgsSchema`  — Pydantic model for accepted arguments
  - `execute()`   — coroutine returning a Pydantic result
  - `cache_key()` — Redis key for the tool: namespace (D-2.3.2, TTL 24h)

Tools NEVER touch the database directly — they call the Retrieval & Graph
API (or filesystem for `read_file` / `grep` / `list_directory`). This
keeps the agent service decoupled from storage and makes mocking trivial.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar

from dcode_shared.cache import tool_cache_key
from pydantic import BaseModel

ArgsT = TypeVar("ArgsT", bound=BaseModel)
ResultT = TypeVar("ResultT", bound=BaseModel)


class Tool(ABC, Generic[ArgsT, ResultT]):
    """Abstract base for every agent tool."""

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    ArgsSchema: ClassVar[type[BaseModel]] = BaseModel

    @abstractmethod
    async def execute(self, repo_id: str, args: ArgsT) -> ResultT:
        """Execute the tool against the live index for `repo_id`."""

    def cache_key(self, repo_id: str, args: ArgsT) -> str:
        """Redis cache key for this invocation (D-2.3.2, TTL 24h)."""
        return tool_cache_key(self.name, repo_id, args.model_dump(mode="json"))


class ToolRegistry:
    """Name → Tool instance lookup, used by the agent's plan and tool_call nodes."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any, Any]] = {}

    def register(self, tool: Tool[Any, Any]) -> None:
        if not tool.name:
            raise ValueError(f"Tool {type(tool).__name__} is missing a name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool[Any, Any] | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def manifest(self) -> list[dict[str, Any]]:
        """Tool catalog as LLM-consumable JSON (for prompting and debug)."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "args_schema": tool.ArgsSchema.model_json_schema(),
            }
            for tool in self._tools.values()
        ]
