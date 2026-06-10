"""Agent tools — implements DESIGN.md §2.3.2 tool clinic.

`default_registry()` returns a ToolRegistry containing all 8 tools.
Used by the agent's plan / tool_call nodes and exposed for debugging
via the agent service's `/internal/tools` endpoint.
"""

from dcode_agent.tools.base import Tool, ToolRegistry
from dcode_agent.tools.find_definition import FindDefinitionTool
from dcode_agent.tools.find_references import FindReferencesTool
from dcode_agent.tools.get_dependencies import GetDependenciesTool
from dcode_agent.tools.get_file_outline import GetFileOutlineTool
from dcode_agent.tools.grep import GrepTool
from dcode_agent.tools.list_directory import ListDirectoryTool
from dcode_agent.tools.read_file import ReadFileTool
from dcode_agent.tools.search_code import SearchCodeTool


def default_registry() -> ToolRegistry:
    """Construct the canonical 8-tool registry."""
    registry = ToolRegistry()
    for tool_cls in (
        SearchCodeTool,
        ReadFileTool,
        FindDefinitionTool,
        FindReferencesTool,
        GetDependenciesTool,
        GetFileOutlineTool,
        GrepTool,
        ListDirectoryTool,
    ):
        registry.register(tool_cls())
    return registry


__all__ = ["Tool", "ToolRegistry", "default_registry"]
