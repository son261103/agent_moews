# Practical Tools (Thay tool code bằng tool thực tế) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove code-related tools (`python_repl`, `read_file`, `write_file`) from the agent and replace them with practical free tools: current time, VnExpress news, weather.

**Architecture:** Three new LangChain tools in `backend/src/tools/` (async httpx for network tools, stdlib for time). Old tool files deleted; `tools/__init__.py`, `graph/builder.py`, and `agents/sub_agents.py` rewired. Frontend gets matching example prompts and tool icons.

**Tech Stack:** Python 3.12 (zoneinfo, xml.etree.ElementTree, httpx — all stdlib/already installed), langchain_core tools, Next.js 16 + Tailwind v4.

## Global Constraints

- No new pip/npm dependencies — only stdlib + already-installed packages (httpx).
- All tool outputs must be user-facing Vietnamese strings (or friendly Vietnamese error messages).
- Keep `web_search` and `web_fetch` untouched.
- Every backend task ends with green tests: `uv run python -m pytest` from `backend/` (venv at `backend/.venv`; pytest requires `uv run` — dev extra already installed).
- Commits: one per task, message style `feat: ...` / `refactor: ...` (repo uses conventional short messages).

---

### Task 1: `get_current_time` tool (TDD)

**Files:**
- Create: `backend/src/tools/time_tools.py`
- Modify: `backend/tests/test_tools.py` (append new test class at end of file)

**Interfaces:**
- Consumes: nothing
- Produces: `get_current_time` — `@tool`, sync, param `tz: str = "Asia/Ho_Chi_Minh"`, returns `str` like `Thứ Tư, 12/08/2026, 14:30` (Vietnamese weekday + DD/MM/YYYY + HH:MM)

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_tools.py`:

```python
class TestCurrentTime:
    def test_get_current_time_format(self):
        from src.tools.time_tools import get_current_time

        result = get_current_time.invoke({})
        assert result.count(",") == 2
        assert "202" in result  # year present
        assert ":" in result    # time present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_tools.py::TestCurrentTime -v` (from `backend/`)
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.time_tools'`

- [ ] **Step 3: Write minimal implementation** — create `backend/src/tools/time_tools.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

VIETNAMESE_WEEKDAYS = [
    "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật",
]


@tool
def get_current_time(tz: str = "Asia/Ho_Chi_Minh") -> str:
    """Get the current date and time. Returns a Vietnamese string like 'Thứ Tư, 12/08/2026, 14:30'."""
    now = datetime.now(ZoneInfo(tz))
    weekday = VIETNAMESE_WEEKDAYS[now.weekday()]
    return f"{weekday}, {now.strftime('%d/%m/%Y')}, {now.strftime('%H:%M')}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_tools.py::TestCurrentTime -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/tools/time_tools.py backend/tests/test_tools.py
git commit -m "feat: add get_current_time tool"
```

---

### Task 2: `get_news` tool (TDD)

**Files:**
- Create: `backend/src/tools/news_tools.py`
- Modify: `backend/tests/test_tools.py` (append test class)

**Interfaces:**
- Consumes: `truncate_text` from `src.tools.truncate` (exists: `truncate_text(text, max_chars=2000)`)
- Produces: `get_news` — `@tool` async, params `category: str = "tin-moi-nhat"`, `limit: int = 5`, returns `str` (formatted list, or Vietnamese error message)

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_tools.py` (reuse the mock pattern from `TestWebFetch`, lines 39-53):

```python
class TestNews:
    RSS_XML = (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<item><title>Tin so mot</title><link>https://vnexpress.net/a1</link>"
        "<description>Mo ta mot</description></item>"
        "<item><title>Tin so hai</title><link>https://vnexpress.net/a2</link>"
        "<description>Mo ta hai</description></item>"
        "</channel></rss>"
    )

    @patch("src.tools.news_tools.httpx.AsyncClient")
    async def test_get_news_returns_items(self, mock_client_class):
        from src.tools.news_tools import get_news

        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = self.RSS_XML
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await get_news.ainvoke({})
        assert "Tin so mot" in result
        assert "https://vnexpress.net/a1" in result

    @patch("src.tools.news_tools.httpx.AsyncClient")
    async def test_get_news_unknown_category(self, mock_client_class):
        from src.tools.news_tools import get_news

        result = await get_news.ainvoke({"category": "khong-co"})
        assert "Không hỗ trợ" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_tools.py::TestNews -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.news_tools'`

- [ ] **Step 3: Write minimal implementation** — create `backend/src/tools/news_tools.py`:

```python
import re
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

from src.tools.truncate import truncate_text

VNEXPRESS_CATEGORIES = {
    "tin-moi-nhat": "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "thoi-su": "https://vnexpress.net/rss/thoi-su.rss",
    "the-gioi": "https://vnexpress.net/rss/the-gioi.rss",
    "kinh-doanh": "https://vnexpress.net/rss/kinh-doanh.rss",
    "giai-tri": "https://vnexpress.net/rss/giai-tri.rss",
    "the-thao": "https://vnexpress.net/rss/the-thao.rss",
    "doi-song": "https://vnexpress.net/rss/doi-song.rss",
    "giao-duc": "https://vnexpress.net/rss/giao-duc.rss",
    "khoa-hoc": "https://vnexpress.net/rss/khoa-hoc.rss",
}


def _item_text(item: ET.Element, tag: str) -> str:
    node = item.find(tag)
    return node.text.strip() if node is not None and node.text else ""


def _format_item(item: ET.Element) -> str:
    title = _item_text(item, "title")
    link = _item_text(item, "link")
    desc = _item_text(item, "description")
    desc = re.sub(r"<[^>]+>", "", desc).strip()
    line = title
    if desc:
        line += f" — {desc[:120]}"
    return f"{line}\n   {link}"


@tool
async def get_news(category: str = "tin-moi-nhat", limit: int = 5) -> str:
    """Get the latest news from VnExpress (Vietnamese). category: tin-moi-nhat (default), thoi-su, the-gioi, kinh-doanh, giai-tri, the-thao, doi-song, giao-duc, khoa-hoc."""
    url = VNEXPRESS_CATEGORIES.get(category)
    if url is None:
        return f"Không hỗ trợ chuyên mục '{category}'. Chọn: {', '.join(VNEXPRESS_CATEGORIES)}"
    limit = max(1, min(limit, 8))
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        root = ET.fromstring(response.text)
        items = root.findall(".//item")[:limit]
        if not items:
            return "Không có tin tức nào."
        return truncate_text("\n".join(_format_item(it) for it in items))
    except Exception as exc:
        return f"Không lấy được tin tức: {exc}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_tools.py::TestNews -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/tools/news_tools.py backend/tests/test_tools.py
git commit -m "feat: add get_news tool (VnExpress RSS)"
```

---

### Task 3: `get_weather` tool (TDD)

**Files:**
- Create: `backend/src/tools/weather_tools.py`
- Modify: `backend/tests/test_tools.py` (append test class)

**Interfaces:**
- Consumes: nothing (httpx only)
- Produces: `get_weather` — `@tool` async, param `city: str = "Hà Nội"`, returns `str` (Vietnamese weather summary or error message)

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_tools.py` (two sequential mocked GETs via `side_effect`):

```python
class TestWeather:
    @patch("src.tools.weather_tools.httpx.AsyncClient")
    async def test_get_weather_returns_summary(self, mock_client_class):
        from src.tools.weather_tools import get_weather

        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        geo_response = MagicMock()
        geo_response.json.return_value = {
            "results": [{"latitude": 21.0285, "longitude": 105.8542, "name": "Hà Nội"}]
        }
        weather_response = MagicMock()
        weather_response.json.return_value = {
            "current": {
                "temperature_2m": 30.5,
                "apparent_temperature": 32.1,
                "relative_humidity_2m": 70,
                "weather_code": 1,
                "wind_speed_10m": 12,
            }
        }
        mock_client.get.side_effect = [geo_response, weather_response]

        result = await get_weather.ainvoke({})
        assert "Hà Nội" in result
        assert "30.5" in result
        assert "ít mây" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_tools.py::TestWeather -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.weather_tools'`

- [ ] **Step 3: Write minimal implementation** — create `backend/src/tools/weather_tools.py`:

```python
import httpx
from langchain_core.tools import tool

WEATHER_CODES = {
    0: "Trời quang", 1: "Trời ít mây", 2: "Trời có mây rải rác", 3: "Trời nhiều mây",
    45: "Sương mù", 48: "Sương mù đóng băng",
    51: "Mưa phùn nhẹ", 53: "Mưa phùn", 55: "Mưa phùn dày",
    61: "Mưa nhỏ", 63: "Mưa vừa", 65: "Mưa to",
    71: "Tuyết rơi nhẹ", 73: "Tuyết rơi vừa", 75: "Tuyết rơi dày", 77: "Mưa tuyết",
    80: "Mưa rào nhẹ", 81: "Mưa rào", 82: "Mưa rào mạnh",
    85: "Mưa tuyết rào nhẹ", 86: "Mưa tuyết rào",
    95: "Dông", 96: "Dông kèm mưa đá", 99: "Dông mạnh kèm mưa đá",
}

DEFAULT_CITY = ("Hà Nội", 21.0285, 105.8542)


@tool
async def get_weather(city: str = "Hà Nội") -> str:
    """Get the current weather for a city. Works with Vietnamese city names like 'Hà Nội' or 'TP Hồ Chí Minh'."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            geo_resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "vi", "format": "json"},
            )
            geo_resp.raise_for_status()
            results = geo_resp.json().get("results")
            if results:
                lat = results[0]["latitude"]
                lon = results[0]["longitude"]
                city_name = results[0].get("name", city)
            else:
                lat, lon, city_name = DEFAULT_CITY[1], DEFAULT_CITY[2], DEFAULT_CITY[0]

            weather_resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,"
                        "apparent_temperature,weather_code,wind_speed_10m"
                    ),
                },
            )
            weather_resp.raise_for_status()
            current = weather_resp.json()["current"]
    except Exception as exc:
        return f"Không lấy được thời tiết: {exc}"

    desc = WEATHER_CODES.get(current.get("weather_code"), "Thời tiết không xác định")
    return (
        f"Thời tiết {city_name}:\n"
        f"- {desc}\n"
        f"- Nhiệt độ: {current['temperature_2m']}°C (cảm giác {current['apparent_temperature']}°C)\n"
        f"- Độ ẩm: {current['relative_humidity_2m']}%\n"
        f"- Gió: {current['wind_speed_10m']} km/h"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_tools.py::TestWeather -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/tools/weather_tools.py backend/tests/test_tools.py
git commit -m "feat: add get_weather tool (Open-Meteo)"
```

---

### Task 4: Remove code tools and rewire imports

**Files:**
- Delete: `backend/src/tools/python_repl.py`, `backend/src/tools/file_tools.py`
- Modify: `backend/src/tools/__init__.py` (full rewrite), `backend/src/graph/builder.py` (lines 5, 19), `backend/src/agents/sub_agents.py` (remove coder subagent)
- Modify: `backend/tests/test_tools.py` (remove `TestPythonRepl` and `TestFileTools` classes, lines 72-159)

**Interfaces:**
- Consumes: tools created in Tasks 1-3 (`get_current_time`, `get_news`, `get_weather`)
- Produces: `all_tools = [web_search, web_fetch, get_current_time, get_news, get_weather]`; `sub_agents = [researcher_subagent]` only

- [ ] **Step 1: Rewrite `backend/src/tools/__init__.py`**

Replace entire contents with:

```python
from src.tools.news_tools import get_news
from src.tools.time_tools import get_current_time
from src.tools.weather_tools import get_weather
from src.tools.web_fetch import web_fetch
from src.tools.web_search import web_search

__all__ = ["web_search", "web_fetch", "get_current_time", "get_news", "get_weather"]
```

- [ ] **Step 2: Update `backend/src/graph/builder.py`**

- Line 5: replace `from src.tools import python_repl, read_file, web_fetch, web_search, write_file` with `from src.tools import get_current_time, get_news, get_weather, web_fetch, web_search`
- Line 19: replace `all_tools = [web_search, web_fetch, python_repl, read_file, write_file]` with `all_tools = [web_search, web_fetch, get_current_time, get_news, get_weather]`

- [ ] **Step 3: Update `backend/src/agents/sub_agents.py`**

Replace entire contents with:

```python
from src.tools import web_fetch, web_search

researcher_subagent = {
    "name": "researcher",
    "description": "Expert at finding, fetching, and synthesizing information from the web.",
    "system_prompt": (
        "You are a research specialist. "
        "For any research task: search the web with web_search, "
        "fetch relevant pages with web_fetch, synthesize findings into clear notes, "
        "and always cite sources."
    ),
    "tools": [web_search, web_fetch],
}

sub_agents = [researcher_subagent]
```

- [ ] **Step 4: Remove obsolete tests** — in `backend/tests/test_tools.py`, delete the `TestPythonRepl` class (lines 72-110) and the `TestFileTools` class (lines 113-159). Keep `TestWebSearch`, `TestWebFetch`, `TestCurrentTime`, `TestNews`, `TestWeather`.

- [ ] **Step 5: Verify no stale references**

Run: `rg -n "python_repl|file_tools|read_file|write_file|coder" backend/src backend/tests --glob '*.py'`
Expected: NO matches (empty output)

- [ ] **Step 6: Run full test suite**

Run: `uv run python -m pytest` (from `backend/`)
Expected: ALL PASS (test_tools now has 5 test classes; test_chat_stream and others still green). If any test outside `test_tools.py` fails due to stale tool references, fix that file the same way (grep first).

- [ ] **Step 7: Commit**

```bash
git add -A backend
git commit -m "refactor: remove code tools, wire practical tools"
```

---

### Task 5: Frontend — example prompts and tool icons

**Files:**
- Modify: `frontend/components/ChatWindow.tsx` (EXAMPLE_PROMPTS array, lines 27-32)
- Modify: `frontend/components/ToolCard.tsx` (TOOL_ICONS lines 12-19, TOOL_LABELS lines 21-28)

**Interfaces:**
- Consumes: nothing new — tool names arriving via SSE are `get_current_time`, `get_news`, `get_weather`
- Produces: updated prompt suggestions and icon/label map entries

- [ ] **Step 1: Replace EXAMPLE_PROMPTS in `frontend/components/ChatWindow.tsx`**

Replace the array (lines 27-32) with:

```ts
const EXAMPLE_PROMPTS = [
  "Thời tiết hôm nay ở Hà Nội thế nào?",
  "Cho tôi xem tin tức mới nhất",
  "Bây giờ là mấy giờ rồi?",
  "Tìm kiếm giúp tôi thông tin về LangChain",
];
```

- [ ] **Step 2: Update TOOL_ICONS in `frontend/components/ToolCard.tsx`**

Replace the whole `TOOL_ICONS` map (lines 12-19) with:

```ts
const TOOL_ICONS: Record<string, string> = {
  web_search: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
  web_fetch: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
  get_current_time: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  get_news: "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z",
  get_weather: "M12 3v2m0 14v2M5.6 5.6l1.4 1.4m10.4 10.4l1.4 1.4M3 12h2m14 0h2M5.6 18.4l1.4-1.4m10.4-10.4l1.4-1.4M12 7a5 5 0 105 5 4 4 0 00-4-4z",
  execute: "M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
};
```

(Note: `python_repl`, `read_file`, `write_file` entries are removed — those tools no longer exist.)

- [ ] **Step 3: Update TOOL_LABELS in `frontend/components/ToolCard.tsx`**

Replace the whole `TOOL_LABELS` map (lines 21-28) with:

```ts
const TOOL_LABELS: Record<string, string> = {
  web_search: "Tìm kiếm web",
  web_fetch: "Lấy nội dung web",
  get_current_time: "Xem giờ",
  get_news: "Tin tức",
  get_weather: "Thời tiết",
  execute: "Thực thi lệnh",
};
```

- [ ] **Step 4: Verify build**

Run: `npm run build` (from `frontend/`)
Expected: compiles successfully, no TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ChatWindow.tsx frontend/components/ToolCard.tsx
git commit -m "feat: practical tool prompts and icons"
```
