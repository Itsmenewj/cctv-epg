import json
import random
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

LATITUDE = 53.75
LONGITUDE = -2.36

LOCAL_NEWS_URL = "https://feeds.bbci.co.uk/news/england/lancashire/rss.xml"
ON_THIS_DAY_URL = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events"

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

# Offline fallback pools to guarantee channel content
FALLBACK_CLEAN_JOKES = [
    "😄 Why don't scientists trust atoms? Because they make up everything!",
    "😄 What do you call a fake noodle? An impasta!",
    "😄 Why did the scarecrow win an award? Because he was outstanding in his field!",
    "😄 How does a penguin build its house? Igloos it together!",
    "😄 Why don't skeletons fight each other? They don't have the guts.",
    "😄 What do you call a belt made out of watches? A waist of time!",
]

FALLBACK_DARK_JOKES = [
    "😈 I told my doctor that I broke my arm in two places. He told me to stop going to those places.",
    "😈 My grandfather has the heart of a lion... and a lifetime ban from the zoo.",
    "😈 Give a man a match, and he'll be warm for a minute. Set a man on fire, and he'll be warm for the rest of his life.",
    "😈 You don't need a parachute to go skydiving. You only need a parachute to go skydiving twice.",
    "😈 I built a model of Mount Everest and my son asked if it was to scale. I said no, it's to look at.",
]

FALLBACK_EVENTS = [
    "📍 Accrington Market Hall: Local Produce & Artisan Market — Open 08:00 - 16:00",
    "📍 Haworth Art Gallery: Europe's Largest Tiffany Glass Collection — Open 12:00 - 16:00",
    "📍 Towneley Hall Burnley: Historic House & Parkland Walkways — Open Daily",
    "📍 East Lancashire Railway: Heritage Steam Train Journeys (Rawtenstall to Bury)",
    "📍 Oswaldtwistle Mills: Heritage Shopping Village & Gardens — Open 10:00 - 16:00",
    "📍 Peel Park Accrington: Coppice Hill Walk & Panoramic Views — Public Access",
]


def fetch_json(url, headers=None):
    """Utility helper to send HTTP requests and parse JSON."""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CCTV-EPG/1.0"
    }
    if headers:
        default_headers.update(headers)

    request = Request(url, headers=default_headers)
    with urlopen(request, timeout=10) as response:
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
        print(f"Weather API unavailable: {error}")
        return {}


def get_local_news():
    """Fetch local headlines from BBC Lancashire RSS."""
    try:
        request = Request(
            LOCAL_NEWS_URL,
            headers={"User-Agent": "Mozilla/5.0 CCTV-EPG/1.0"},
        )
        with urlopen(request, timeout=10) as response:
            root = ET.fromstring(response.read())

        headlines = []
        for item in root.findall("./channel/item"):
            title = item.findtext("title", "").strip()
            description = item.findtext("description", "").strip()
            description = re.sub(r"<[^>]+>", "", description).strip()

            if title:
                text = title
                if description and len(description) < 140:
                    text += " — " + description
                headlines.append(text)

            if len(headlines) >= 20:
                break
        return headlines if headlines else ["Local news updates pending."]
    except Exception as error:
        print(f"Local news RSS error: {error}")
        return ["Local news feed currently offline."]


def get_joke(category, emoji):
    """Fetch individual jokes safely with full endpoint fallback handling."""
    if category == "safe":
        url = "https://v2.jokeapi.dev/joke/Any?safe-mode"
    else:
        url = "https://v2.jokeapi.dev/joke/Dark,Pun"

    try:
        data = fetch_json(url)
        if data.get("error"):
            raise ValueError(data.get("message", "API returned error"))

        if data.get("type") == "single":
            return f"{emoji} {data.get('joke')}"
        elif data.get("type") == "twopart":
            return f"{emoji} {data.get('setup')} ... {data.get('delivery')}"
    except Exception as error:
        print(f"Joke fetch error ({category}): {error}")

    fallback_list = (
        FALLBACK_CLEAN_JOKES if category == "safe" else FALLBACK_DARK_JOKES
    )
    return random.choice(fallback_list)


def get_on_this_day(dt):
    """Fetch historical events for a given date from Wikipedia API."""
    try:
        url = f"{ON_THIS_DAY_URL}/{dt.month}/{dt.day}"
        # Wikipedia requires a descriptive user agent string
        headers = {
            "User-Agent": "CCTV-EPG-Bot/1.0 (https://github.com/cctv-epg; contact@example.com)"
        }
        data = fetch_json(url, headers=headers)
        events = []
        for item in data.get("events", []):
            year = item.get("year", "")
            text = item.get("text", "")
            if year and text:
                events.append(f"📜 {year}: {text}")
            if len(events) >= 20:
                break
        if events:
            return events
    except Exception as error:
        print(f"On This Day API error for {dt.strftime('%B %d')}: {error}")

    return [
        f"📜 {dt.strftime('%B %d')}: Historical records and events recorded across international archives."
    ]


def weather_description(begin, forecast):
    """Format hourly weather forecast into a clean standalone text string."""
    entries = [forecast.get(begin), forecast.get(begin + timedelta(hours=1))]
    entries = [entry for entry in entries if entry]

    if not entries:
        return "🌤️ Local Weather: Conditions variable across region."

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

    return f"🌤️ Local Weather: {condition}; {temperature_text}; {rain_text}."


def xml_time(dt):
    """Format datetime into standard XMLTV time string."""
    return dt.strftime("%Y%m%d%H%M%S %z")


def generate():
    now = datetime.now(TZ)
    start = now.replace(hour=6, minute=0, second=0, microsecond=0)

    if now < start:
        start -= timedelta(days=1)

    forecast = get_weather()
    news_list = get_local_news()

    # Pre-populate dynamic joke arrays for all 84 time slots
    clean_jokes = [get_joke("safe", "😄") for _ in range(20)]
    dark_jokes = [get_joke("dark", "😈") for _ in range(20)]

    on_this_day_cache = {}

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Reusable CCTV EPG">',
    ]

    for channel_id, name in CHANNELS.items():
        lines.extend(
            [
                f'  <channel id="{channel_id}">',
                f"    <display-name>{escape(name)}</display-name>",
                "  </channel>",
            ]
        )

    for day in range(DAYS):
        day_date = start + timedelta(days=day)
        date_key = day_date.strftime("%Y-%m-%d")

        if date_key not in on_this_day_cache:
            on_this_day_cache[date_key] = get_on_this_day(day_date)

        day_history = on_this_day_cache[date_key]

        for slot, (title, description) in enumerate(SLOTS):
            begin = start + timedelta(days=day, hours=slot * 2)
            end = begin + timedelta(hours=2)

            slot_index = (day * len(SLOTS)) + slot

            current_weather = weather_description(begin, forecast)
            current_news = f"📰 Local News: {news_list[slot_index % len(news_list)]}"
            current_event = FALLBACK_EVENTS[slot_index % len(FALLBACK_EVENTS)]
            current_clean_joke = clean_jokes[slot_index % len(clean_jokes)]
            current_dark_joke = dark_jokes[slot_index % len(dark_jokes)]
            current_history = day_history[slot_index % len(day_history)]

            for channel_id, name in CHANNELS.items():
                extra = []

                if channel_id == "1":
                    extra.append(current_weather)
                elif channel_id == "2":
                    extra.append(current_event)
                elif channel_id == "3":
                    extra.append(current_clean_joke)
                elif channel_id == "4":
                    extra.append(current_history)
                elif channel_id == "5":
                    extra.append(current_news)
                elif channel_id == "6":
                    extra.append(current_dark_joke)

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

    print(f"Generated {OUTPUT_FILE}: {len(CHANNELS)} channels, {DAYS} days.")


if __name__ == "__main__":
    generate()
