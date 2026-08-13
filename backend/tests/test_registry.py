import pytest
from langchain_core.tools import tool

from src.tools.registry import ToolRegistry


def test_register_and_query_groups():
    reg = ToolRegistry()

    @reg.register(group="research")
    @tool
    def fake_search(query: str) -> str:
        """Search fake."""
        return ""

    @reg.register(group="info")
    @tool
    def fake_time() -> str:
        """Time fake."""
        return ""

    assert {t.name for t in reg.all_tools()} == {"fake_search", "fake_time"}
    assert [t.name for t in reg.tools_by_group("research")] == ["fake_search"]
    assert [t.name for t in reg.tools_by_group("info")] == ["fake_time"]
    assert reg.groups() == ["research", "info"]


def test_register_keeps_registration_order():
    reg = ToolRegistry()

    @reg.register(group="info")
    @tool
    def fake_time() -> str:
        """Time fake."""
        return ""

    @reg.register(group="research")
    @tool
    def fake_search(query: str) -> str:
        """Search fake."""
        return ""

    assert reg.groups() == ["info", "research"]


def test_duplicate_name_raises():
    reg = ToolRegistry()

    @reg.register(group="research")
    @tool
    def fake_search(query: str) -> str:
        """Search fake."""
        return ""

    with pytest.raises(ValueError, match="Duplicate tool name registered"):

        @reg.register(group="info")
        @tool
        def fake_search(query: str) -> str:
            """Search fake again."""
            return ""


def test_custom_name_override():
    reg = ToolRegistry()

    @reg.register(group="info", name="custom_name")
    @tool
    def fake_time() -> str:
        """Time fake."""
        return ""

    assert reg.all_tools()[0].name == "custom_name"
