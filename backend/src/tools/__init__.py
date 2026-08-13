import pkgutil
from importlib import import_module

from src.tools.news_tools import get_news
from src.tools.registry import get_all_tools, get_groups, get_tools_by_group, register_tool
from src.tools.time_tools import get_current_time
from src.tools.weather_tools import get_weather
from src.tools.web_fetch import web_fetch
from src.tools.web_search import web_search

# Import every module under src/tools so their @register_tool decorators run.
# truncate.py and registry.py import fine and register nothing.
for _module in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
    if _module.name != "registry":
        import_module(f"{__name__}.{_module.name}")

__all__ = [
    "register_tool",
    "get_all_tools",
    "get_tools_by_group",
    "get_groups",
    "get_current_time",
    "get_news",
    "get_weather",
    "web_fetch",
    "web_search",
]
