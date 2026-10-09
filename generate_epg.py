import json
import re
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

# Configuration
TZ = ZoneInfo("Europe/London")
DAYS = 7
OUTPUT_FILE = "cctv-epg.xml"

# Generic reference point for the Hyndburn / Accrington area (not a specific address)
LATITUDE = 53.75
LONGITUDE = -2.36

# Official BBC Lancashire RSS Feed
LOCAL_NEWS_URL = "https://feeds.bbci.co.uk/news/england/lancashire/rss.xml"

SLOTS = [
    ("Morning Watch", "Morning CCTV monitoring."),
    ("Perimeter Watch", "Perimeter and access-point monitoring."),
    ("Live Surveillance", "Continuous CCTV surveillance."),
    ("Daytime Watch", "Daytime security monitoring."),
    ("Activity Watch", "General property and perimeter monitoring."),
    ("Afternoon Watch", "Afternoon CCTV monitoring."),
    ("Evening Watch", "Evening security monitoring."),
    ("Night Watch", "Night-time CCTV surveillance."),
    ("Late Night Watch", "Late-night security monitoring."),
    ("Overnight Watch", "Overnight CCTV surveillance."),
    ("Security Monitor", "Continuous security monitoring."),
    ("Pre-Dawn Watch", "Pre-dawn CCTV monitoring."),
]

CHANNELS = {str(i): f"Camera {i:02d}" for i in range(1, 35)}


def fetch_json(url):
    """Utility to make HTTP requests and return JSON."""
    request = Request(url, headers={"User-Agent": "CCTV-EPG/1.0"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def get_weather():
    """Fetch 7-day hourly forecast from Open-Meteo."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&hourly=temperature_2m,precipitation_probability,weather_code"
        "&forecast_days=7&timezone=Europe%2FLondon"
    )

    try:
        data = fetch_json(url)["hourly"]
        result = {}

        for i, time_string in enumerate(data["time"]):
            dt = datetime.fromisoformat(time_string).replace(tzinfo=TZ)
            result[dt] = {
                "temperature": data["temperature_2m"][i],
                "rain": data["precipitation_probability"][i],
                "code": data["weather_code"][i],
            }

        return result

    except Exception as error:
        print(f"Weather unavailable: {error}")
        return {}


def get_local_news():
    """Fetch up to 20 local headlines and strip HTML tags safely."""
    try:
        request = Request(
            LOCAL_NEWS_URL, headers={"User-Agent": "CCTV-EPG/1.0"}
        )
        with urlopen(request, timeout=15) as response:
            root = ET.fromstring(response.read())

        headlines = []

        for item in root.findall("./channel/item"):
            title = item.findtext("title", "").strip()
            description = item.findtext("description", "").strip()

            # Safely remove HTML formatting if present
            description = re.sub(r"<[^>]+>", "", description).strip()

            if title:
                text = title
                if description and len(description) < 150:
                    text += " — " + description
                headlines.append(text)

            if len(headlines) >= 20:
                break

        return headlines

    except Exception as error:
        print(f"Local news unavailable: {error}")
        return []


def weather_description(begin, forecast):
    """Format hourly weather into a human-readable text snapshot."""
    entries = [
        forecast.get(begin),
        forecast.get(begin + timedelta(hours=1)),
    ]
    entries = [entry for entry in entries if entry]

    if not entries:
        return "Local weather snapshot unavailable."

    conditions = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Freezing fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        80: "Light showers",
        81: "Rain showers",
        82: "Heavy showers",
        95: "Thunderstorms",
    }

    temperatures = [
        item["temperature"]
        for item in entries
        if item["temperature"] is not None
    ]
    rain_values = [
        item["rain"] for item in entries if item["rain"] is not None
    ]

    temperature_text = (
        f"{round(sum(temperatures) / len(temperatures))}°C"
        if temperatures
        else "N/A"
    )

    rain_text = (
        f"{max(rain_values)}% rain risk"
        if rain_values
        else "Rain risk unavailable"
    )

    condition = conditions.get(entries[0]["code"], "Variable conditions")

    return f"Local weather: {condition}; {temperature_text}; {rain_text}."


def xml_time(dt):
    """Format datetime into standard XMLTV timezone string."""
    return dt.strftime("%Y%m%d%H%M%S %z")


def generate():
    """Build and save the XMLTV EPG file."""
    now = datetime.now(TZ)
    start = now.replace(hour=6, minute=0, second=0, microsecond=0)

    if now < start:
        start -= timedelta(days=1)

    forecast = get_weather()
    headlines = get_local_news()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Reusable CCTV EPG">',
    ]

    # Declare channels
    for channel_id, name in CHANNELS.items():
        lines.extend(
            [
                f'  <channel id="{channel_id}">',
                f"    <display-name>{escape(name)}</display-name>",
                "  </channel>",
            ]
        )

    # Generate programme slots
    for day in range(DAYS):
        for slot, (title, description) in enumerate(SLOTS):
            begin = start + timedelta(days=day, hours=slot * 2)
            end = begin + timedelta(hours=2)

            # Rotate through local headlines per 2-hour block
            slot_index = (day * len(SLOTS)) + slot
            if headlines:
                current_headline = headlines[slot_index % len(headlines)]
                news_text = f"Local News: {current_headline}"
            else:
                news_text = "Local news headlines temporarily unavailable."

            for channel_id, name in CHANNELS.items():
                extra = []

                # Append extra metadata (weather & news) only to Camera 01 to save space
                if channel_id == "1":
                    extra.append(weather_description(begin, forecast))
                    extra.append(news_text)

                full_description = description
                if extra:
                    full_description += " | " + " | ".join(extra)

                lines.extend(
                    [
                        (
                            f'  <programme start="{xml_time(begin)}" '
                            f'stop="{xml_time(end)}" channel="{channel_id}">'
                        ),
                        f'    <title>{escape(name + ": " + title)}</title>',
                        (
                            "    <desc>"
                            f'{escape("🔴 LIVE • " + full_description)}'
                            "</desc>"
                        ),
                        "    <category>CCTV</category>",
                        "  </programme>",
                    ]
                )

    lines.append("</tv>")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")

    print(
        f"Generated {OUTPUT_FILE}: {len(CHANNELS)} channels, {DAYS} days."
    )


if __name__ == "__main__":
    generate()
