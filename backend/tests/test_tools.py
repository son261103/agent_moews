from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestWebSearch:
    def test_web_search_import(self):
        from src.tools.web_search import web_search
        assert hasattr(web_search, "invoke")

    def test_web_search_calls_tavily(self):
        from unittest.mock import patch, MagicMock
        from src.tools.web_search import web_search

        with patch("src.tools.web_search.TavilySearch") as mock_tavily:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = [{"title": "Test", "url": "https://example.com"}]
            mock_tavily.return_value = mock_instance

            result = web_search.invoke({"query": "test"})
            mock_tavily.assert_called_once_with(max_results=5)
            mock_instance.invoke.assert_called_once_with("test")
            assert "Test" in result

    def test_web_search_truncates_long_results(self):
        from unittest.mock import patch, MagicMock
        from src.tools.web_search import web_search

        with patch("src.tools.web_search.TavilySearch") as mock_tavily:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = [{"title": "x" * 3000, "url": "y" * 3000}]
            mock_tavily.return_value = mock_instance

            result = web_search.invoke({"query": "test"})
            assert "truncated" in result
            assert len(result) < 6000


class TestWebFetch:
    @patch("src.tools.web_fetch.httpx.AsyncClient")
    async def test_web_fetch_returns_markdown(self, mock_client_class):
        from src.tools.web_fetch import web_fetch

        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "<html><title>Test</title><p>Hello World</p></html>"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await web_fetch.ainvoke({"url": "https://example.com"})
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("src.tools.web_fetch.httpx.AsyncClient")
    async def test_web_fetch_truncates_long_page(self, mock_client_class):
        from src.tools.web_fetch import web_fetch

        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = f"<html><p>{'x' * 5000}</p></html>"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await web_fetch.ainvoke({"url": "https://example.com"})
        assert "truncated" in result
        assert len(result) < 5000


class TestPythonRepl:
    async def test_python_repl_runs_code(self):
        from src.tools.python_repl import python_repl

        result = await python_repl.ainvoke({"code": "print(2 + 2)"})
        assert "4" in result

    async def test_python_repl_captures_stderr(self):
        from src.tools.python_repl import python_repl

        result = await python_repl.ainvoke({"code": "import sys; sys.stderr.write('oops')"})
        assert "oops" in result

    async def test_python_repl_timeout(self):
        from src.tools.python_repl import python_repl

        # Use a short timeout by patching — we don't want to wait 30s in tests
        import concurrent.futures
        from unittest.mock import patch

        def raise_timeout(code):
            raise concurrent.futures.TimeoutError()

        with patch("src.tools.python_repl._execute_code", side_effect=raise_timeout):
            result = await python_repl.ainvoke({"code": "pass"})
        assert "timeout" in result.lower() or "timed out" in result.lower()

    async def test_python_repl_blocks_os(self):
        from src.tools.python_repl import python_repl

        result = await python_repl.ainvoke({"code": "import os; os.listdir('/')"})
        assert "Error" in result

    async def test_python_repl_truncates_long_output(self):
        from src.tools.python_repl import python_repl

        result = await python_repl.ainvoke({"code": 'print("x" * 3000)'})
        assert "truncated" in result
        assert len(result) < 3000


class TestFileTools:
    async def test_read_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
        import importlib
        import src.tools.file_tools as file_tools
        importlib.reload(file_tools)
        read_file = file_tools.read_file

        f = tmp_path / "test.txt"
        f.write_text("hello")

        result = await read_file.ainvoke({"path": str(f)})
        assert "hello" in result

    async def test_write_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
        import importlib
        import src.tools.file_tools as file_tools
        importlib.reload(file_tools)
        write_file = file_tools.write_file
        read_file = file_tools.read_file

        f = tmp_path / "out.txt"
        await write_file.ainvoke({"path": str(f), "content": "world"})

        result = await read_file.ainvoke({"path": str(f)})
        assert "world" in result

    async def test_read_file_not_found(self):
        from src.tools.file_tools import read_file

        result = await read_file.ainvoke({"path": "/nonexistent/path/file.txt"})
        assert "not found" in result.lower() or "error" in result.lower()

    async def test_read_file_truncates_long_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
        import importlib
        import src.tools.file_tools as file_tools
        importlib.reload(file_tools)
        read_file = file_tools.read_file

        f = tmp_path / "big.txt"
        f.write_text("x" * 5000)

        result = await read_file.ainvoke({"path": str(f)})
        assert "truncated" in result
        assert len(result) < 5000


class TestCurrentTime:
    def test_get_current_time_format(self):
        from src.tools.time_tools import get_current_time

        result = get_current_time.invoke({})
        assert result.count(",") == 2
        assert "202" in result  # year present
        assert ":" in result    # time present


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
