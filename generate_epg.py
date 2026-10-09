
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
import json

TZ = ZoneInfo("Europe/London")
DAYS = 7
OUTPUT_FILE = "cctv-epg.xml"

# Generic UK-wide reference point, not a personal location.
LATITUDE = 52.5
LONGITUDE = -1.9

NEWS_URL = "https://feeds.bbci.co.uk/news/uk/rss.xml"

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

CHANNELS = {
    str(i): f"Camera {i:02d}"
    for i in range(1, 35)
}


def fetch_json(url):
    request = Request(
        url,
        headers={"User-Agent": "CCTV-EPG/1.0"}
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def get_weather():
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


def get_news():
    """Return a few current UK headlines; never fail the EPG build."""
    try:
        request = Request(
            NEWS_URL,
            headers={"User-Agent": "CCTV-EPG/1.0"}
        )
        with urlopen(request, timeout=15) as response:
            root = ET.fromstring(response.read())

        headlines = []

        for item in root.findall("./channel/item"):
            title = item.findtext("title", "").strip()
            description = item.findtext("description", "").strip()

            if title:
                text = title
                if description:
                    text += " — " + description
                headlines.append(text)

            if len(headlines) >= 5:
                break

        return headlines

    except Exception as error:
        print(f"News unavailable: {error}")
        return []


def weather_description(begin, forecast):
    entries = [
        forecast.get(begin),
        forecast.get(begin + timedelta(hours=1)),
    ]
    entries = [entry for entry in entries if entry]

    if not entries:
        return "UK weather snapshot unavailable."

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
        56: "Freezing drizzle",
        57: "Freezing drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Heavy freezing rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Light showers",
        81: "Rain showers",
        82: "Heavy showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorms",
        96: "Thunderstorms with hail",
        99: "Severe thunderstorms with hail",
    }

    temperatures = [
        item["temperature"]
        for item in entries
        if item["temperature"] is not None
    ]
    rain_values = [
        item["rain"]
        for item in entries
        if item["rain"] is not None
    ]

    temperature_text = (
        f"{round(sum(temperatures) / len(temperatures))}°C"
        if temperatures else "Temperature unavailable"
    )

    rain_text = (
        f"{max(rain_values)}% precipitation chance"
        if rain_values else "Precipitation chance unavailable"
    )

    condition = conditions.get(entries[0]["code"], "Variable conditions")

    return (
        f"Central England weather snapshot: {condition}; "
        f"{temperature_text}; {rain_text}. "
        "Conditions vary across the UK."
    )


def xml_time(dt):
    return dt.strftime("%Y%m%d%H%M%S %z")


def generate():
    now = datetime.now(TZ)
    start = now.replace(
        hour=6, minute=0, second=0, microsecond=0
    )

    if now < start:
        start -= timedelta(days=1)

    forecast = get_weather()
    headlines = get_news()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Reusable CCTV EPG">',
    ]

    # Stable numeric IDs preserve compatibility with existing templates.
    for channel_id, name in CHANNELS.items():
        lines.extend([
            f'  <channel id="{channel_id}">',
            f'    <display-name>{escape(name)}</display-name>',
            '  </channel>',
        ])

    for day in range(DAYS):
        for channel_id, name in CHANNELS.items():
            for slot, (title, description) in enumerate(SLOTS):
                begin = start + timedelta(
                    days=day, hours=slot * 2
                )
                end = begin + timedelta(hours=2)

                extra = []

                # Shared information is shown on Camera 01 only,
                # avoiding unnecessary repetition in the other channels.
                if channel_id == "1":
                    extra.append(weather_description(begin, forecast))

                    if headlines:
                        extra.append("UK news headlines: " + " | ".join(headlines))
                    else:
                        extra.append("UK news headlines temporarily unavailable.")

                full_description = description
                if extra:
                    full_description += " | " + " | ".join(extra)

                lines.extend([
                    (
                        f'  <programme start="{xml_time(begin)}" '
                        f'stop="{xml_time(end)}" channel="{channel_id}">'
                    ),
                    f'    <title>{escape(name + ": " + title)}</title>',
                    f'    <desc>{escape("🔴 LIVE • " + full_description)}</desc>',
                    '    <category>CCTV</category>',
                    '  </programme>',
                ])

    lines.append("</tv>")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")

    print(
        f"Generated {OUTPUT_FILE}: "
        f"{len(CHANNELS)} channels, {DAYS} days."
    )


if __name__ == "__main__":
    generate()
