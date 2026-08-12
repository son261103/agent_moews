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
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
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
