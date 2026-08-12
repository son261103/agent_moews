import re

import httpx
from langchain_core.tools import tool

from src.tools.truncate import truncate_text


@tool
async def web_fetch(url: str) -> str:
    """Fetch a web page and return its text content with HTML stripped."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

            html = response.text
            html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
            html = re.sub(r"<[^>]+>", " ", html)
            html = re.sub(r"\s+", " ", html)
            return truncate_text(html.strip())
    except Exception as exc:
        return f"Lỗi khi đọc trang web ({url}): {exc}"

