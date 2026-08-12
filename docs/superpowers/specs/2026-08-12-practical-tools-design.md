# Design: Practical Tools (thay tool code bằng tool thực tế)

**Date:** 2026-08-12
**Status:** Approved by user

## Goal

User (non-developer) does not want code-related tools. Remove `python_repl`, `read_file`, `write_file` from the agent and replace them with practical, free tools: current time, VnExpress news, and weather.

## Backend Changes (`backend/src/tools/`)

### Remove
- Delete `python_repl.py`, `file_tools.py`
- Remove their exports from `tools/__init__.py` and from `all_tools` in `backend/src/graph/builder.py`

### Keep
- `web_search` (Tavily), `web_fetch` (httpx) — unchanged

### Add
1. **`get_current_time()`** — sync tool. Local time in `Asia/Ho_Chi_Minh` (zonevia default tz, configurable via param). Returns Vietnamese string, e.g. `Thứ Tư, 12/08/2026, 14:30`. No network.
2. **`get_news(category="tin-moi-nhat")`** — sync/async tool using `httpx` (already installed) + stdlib `xml.etree.ElementTree` (no new dependency). Fetches VnExpress RSS (`https://vnexpress.net/rss/<category>.rss`). Supported categories map: tin-moi-nhat (default), thoi-su, the-gioi, kinh-doanh, giai-tri, the-thao, doi-song, giao-duc, khoa-hoc. Returns top 5-8 items: title + link + short description, formatted in Vietnamese. Errors → friendly Vietnamese message.
3. **`get_weather(city="Hà Nội")`** — async tool using httpx. Two calls:
   - Open-Meteo geocoding `https://geocoding-api.open-meteo.com/v1/search?name=<city>&count=1&language=vi&format=json` to resolve city → lat/lon
   - Open-Meteo current weather `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m`
   - Map weather_code → Vietnamese description ("Trời quang", "Có mây", "Mưa nhẹ", ...). Returns temperature, feels-like, humidity, wind, description. City not found → default to Hà Nội coordinates. Errors → friendly Vietnamese message.

### Tests (`backend/tests/test_tools.py`)
- Add tests for the 3 new tools with mocked `httpx` (follow existing mock patterns from `test_web_fetch`).
- Keep all existing tests green (`uv run python -m pytest`).

## Frontend Changes (`frontend/`)

- `components/ChatWindow.tsx`: replace the 4 `EXAMPLE_PROMPTS` (remove Python/Next.js prompts) with practical Vietnamese prompts (weather, news, time, web search).
- `components/ToolCard.tsx`: extend tool→icon map with `get_current_time` (clock), `get_news` (newspaper), `get_weather` (cloud/sun) + humanized labels ("Xem giờ", "Tin tức", "Thời tiết").
- No other frontend changes.

## Verification
- Backend: `uv run python -m pytest` all green.
- Frontend: `npm run build` passes, eslint 0 errors.
