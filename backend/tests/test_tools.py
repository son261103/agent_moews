from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestWebSearch:
    def test_web_search_import(self):
        from src.tools.web_search import web_search
        assert hasattr(web_search, "invoke")


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

        result = await python_repl.ainvoke({"code": "import time; time.sleep(60)"})
        assert "timeout" in result.lower() or "timed out" in result.lower()


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
