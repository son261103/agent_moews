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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        root = ET.fromstring(response.text)
        items = root.findall(".//item")[:limit]
        if not items:
            return "Không có tin tức nào."
        return truncate_text("\n".join(_format_item(it) for it in items))
    except Exception as exc:
        return f"Không lấy được tin tức: {exc}"
