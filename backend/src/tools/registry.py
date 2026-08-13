from typing import Callable

from langchain_core.tools import BaseTool


class ToolRegistry:
    """Collect @tool objects and tag them with a domain group."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._groups: dict[str, str] = {}

    def register(
        self, group: str, name: str | None = None
    ) -> Callable[[BaseTool], BaseTool]:
        """Decorator factory: `@registry.register(group="info")` above `@tool`."""

        def decorator(tool_obj: BaseTool) -> BaseTool:
            tool_name = name or tool_obj.name
            if tool_name in self._tools:
                raise ValueError(f"Duplicate tool name registered: {tool_name}")
            tool_obj.name = tool_name
            self._tools[tool_name] = tool_obj
            self._groups[tool_name] = group
            return tool_obj

        return decorator

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def tools_by_group(self, group: str) -> list[BaseTool]:
        return [t for name, t in self._tools.items() if self._groups[name] == group]

    def groups(self) -> list[str]:
        seen: list[str] = []
        for group in self._groups.values():
            if group not in seen:
                seen.append(group)
        return seen


# Module-level singleton used by application code.
registry = ToolRegistry()
register_tool = registry.register
get_all_tools = registry.all_tools
get_tools_by_group = registry.tools_by_group
get_groups = registry.groups
