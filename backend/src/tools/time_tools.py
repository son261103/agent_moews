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
