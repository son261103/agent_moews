import pkgutil
from importlib import import_module

from src.tools.registry import get_all_tools, get_groups, get_tools_by_group, register_tool

# Import every module under src/tools so their @register_tool decorators run.
# truncate.py and registry.py import fine and register nothing.
for _module in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
    if _module.name != "registry":
        import_module(f"{__name__}.{_module.name}")

__all__ = ["register_tool", "get_all_tools", "get_tools_by_group", "get_groups"]
