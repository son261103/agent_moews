def test_real_tools_registered_in_groups():
    from src.tools import get_all_tools, get_groups, get_tools_by_group

    names = {t.name for t in get_all_tools()}
    assert names == {
        "web_search",
        "web_fetch",
        "get_current_time",
        "get_news",
        "get_weather",
    }
    assert set(get_groups()) == {"research", "info"}
    assert {t.name for t in get_tools_by_group("research")} == {"web_search", "web_fetch"}
    assert {t.name for t in get_tools_by_group("info")} == {
        "get_current_time",
        "get_news",
        "get_weather",
    }
