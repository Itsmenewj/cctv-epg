
import json
import re
import html
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/London")
DAYS_AHEAD = 7
BACK_DAYS = 3
TOTAL_DAYS = BACK_DAYS + DAYS_AHEAD
SLOT_HOURS = 2
SLOTS_PER_DAY = 24 // SLOT_HOURS
OUTPUT_FILE = "cctv-epg.xml"

LATITUDE = 53.75
LONGITUDE = -2.36

LOCAL_NEWS_URL = "https://feeds.bbci.co.uk/news/england/lancashire/rss.xml"
ON_THIS_DAY_URL = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events"
VISIT_LANCASHIRE_EVENTS_URL = "https://www.visitlancashire.com/events/"

PICON_URL = (
    "https://raw.githubusercontent.com/"
    "Itsmenewj/cctv-epg/main/picons/cctv.png"
)

CHANNELS = {str(i): f"Camera {i:02d}" for i in range(1, 35)}
CHANNELS["35"] = "Handley Aerials"

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

FALLBACK_EVENTS = [
    "Lancashire event listings are currently unavailable. Check Visit Lancashire for confirmed dates and times.",
]
HANDLEY_SERVICES = [
    "TV aerial installation and repairs; Freeview and Freesat; Sky and satellite systems; FM and DAB radio aerials; communal TV and IRS systems; CCTV and security solutions; Wi-Fi and data networking; fibre and data cabling; multi-room TV and audio; home cinema and TV mounting; smart-home and entertainment integration.",
]
HANDLEY_ADDRESS = "Unit 2, Primet Business Centre, Burnley Road, Colne, Lancashire, BB8 8DQ."
HANDLEY_COVERAGE = "Serving East Lancashire and West Yorkshire, including Colne, Nelson, Burnley, Blackburn, Accrington, Clitheroe, Rawtenstall, Bacup, Darwen, Haslingden, Barnoldswick, Todmorden, Skipton, Keighley and surrounding areas."
HANDLEY_HOURS = "Office hours listed on the company website: Monday to Friday, 08:00–17:00. Saturday and Sunday hours/appointments may vary; contact the company to confirm."

def fetch_bytes(url, timeout=12):
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; LancashireCCTVEpg/3.0)",
        "Accept": "text/html,application/xml,application/json,*/*",
    })
    with urlopen(request, timeout=timeout) as response:
        return response.read()

def fetch_json(url, timeout=12):
    return json.loads(fetch_bytes(url, timeout).decode("utf-8"))

def clean_text(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def unique_texts(items):
    result, seen = [], set()
    for item in items:
        item = clean_text(item)
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result

def get_weather():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "forecast_days": 7,
        "timezone": "Europe/London",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)
    try:
        hourly = fetch_json(url)["hourly"]
        result = {}
        for i, value in enumerate(hourly["time"]):
            dt = datetime.fromisoformat(value).replace(tzinfo=TZ)
            result[dt] = {
                "temperature": hourly["temperature_2m"][i],
                "rain": hourly["precipitation_probability"][i],
                "code": hourly["weather_code"][i],
            }
        print(f"Loaded {len(result)} hourly weather records.")
        return result
    except Exception as error:
        print(f"Weather feed unavailable: {error}")
        return {}

def weather_description(begin, forecast):
    entries = [forecast.get(begin), forecast.get(begin + timedelta(hours=1))]
    entries = [e for e in entries if e]
    if not entries:
        return "Forecast unavailable."
    conditions = {
        0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle",
        55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Heavy freezing drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
        67: "Heavy freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
        77: "Snow grains", 80: "Light showers", 81: "Rain showers",
        82: "Heavy showers", 85: "Snow showers", 86: "Heavy snow showers",
        95: "Thunderstorms", 96: "Thunderstorms with hail",
        99: "Severe thunderstorms with hail",
    }
    temps = [e["temperature"] for e in entries if e.get("temperature") is not None]
    rain = [e["rain"] for e in entries if e.get("rain") is not None]
    temp_text = f"{round(sum(temps) / len(temps))}°C" if temps else "N/A"
    rain_text = f"{max(rain)}% chance of precipitation" if rain else "Rain chance unavailable"
    return f'{conditions.get(entries[0].get("code"), "Variable conditions")}; {temp_text}; {rain_text}.'

def get_local_news():
    try:
        root = ET.fromstring(fetch_bytes(LOCAL_NEWS_URL))
        headlines = []
        for item in root.findall("./channel/item"):
            title = clean_text(item.findtext("title", ""))
            description = clean_text(item.findtext("description", ""))
            if not title:
                continue
            text = title
            if description and len(description) < 240:
                text += " — " + description
            headlines.append(text)
        headlines = unique_texts(headlines)
        if headlines:
            print(f"Loaded {len(headlines)} Lancashire news items.")
            return headlines
    except Exception as error:
        print(f"Lancashire news feed unavailable: {error}")
    return ["Lancashire news feed currently unavailable. Check BBC News Lancashire for the latest headlines."]

def parse_datetime(value):
    if not value:
        return None
    try:
        value = value.strip()
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except (ValueError, TypeError):
        return None

def flatten_jsonld(node):
    if isinstance(node, list):
        for item in node:
            yield from flatten_jsonld(item)
    elif isinstance(node, dict):
        yield node
        graph = node.get("@graph")
        if graph:
            yield from flatten_jsonld(graph)

def get_upcoming_events(now):
    """
    Read public Event JSON-LD where available. Only retain future events.
    Event times are shown only when the source publishes them; date-only
    events are explicitly labelled 'time not listed'.
    """
    try:
        page = fetch_bytes(VISIT_LANCASHIRE_EVENTS_URL).decode("utf-8", "replace")
        scripts = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            page, flags=re.I | re.S
        )
        events = []
        for raw in scripts:
            try:
                data = json.loads(html.unescape(raw.strip()))
            except (ValueError, TypeError):
                continue
            for item in flatten_jsonld(data):
                types = item.get("@type", [])
                if isinstance(types, str):
                    types = [types]
                if not any(t.lower() == "event" for t in types):
                    continue
                name = clean_text(item.get("name", ""))
                start = parse_datetime(item.get("startDate"))
                end = parse_datetime(item.get("endDate"))
                if not name or not start or start < now:
                    continue
                location = item.get("location", {})
                place = ""
                if isinstance(location, dict):
                    place = clean_text(location.get("name", ""))
                    address = location.get("address", {})
                    if isinstance(address, dict):
                        locality = clean_text(address.get("addressLocality", ""))
                        if locality:
                            place = f"{place}, {locality}" if place else locality
                
                when = start.strftime("%a %d %b %Y, %H:%M")
                if end and (end.date() == start.date()) and end != start:
                    when += "–" + end.strftime("%H:%M")
                elif not ("T" in item.get("startDate", "")):
                    when = start.strftime("%a %d %b %Y") + " (time not listed)"
                
                description = clean_text(item.get("description", ""))
                text = f"{name} — {when}"
                if place:
                    text += f" — {place}"
                if description and len(description) < 180:
                    text += f" — {description}"
                events.append((start, text))
                
        events.sort(key=lambda pair: pair[0])
        unique = unique_texts(text for _, text in events)
        if unique:
            print(f"Loaded {len(unique)} upcoming Lancashire events.")
            return unique
        print("No upcoming Event JSON-LD found on Visit Lancashire page.")
    except Exception as error:
        print(f"Upcoming events feed unavailable: {error}")
    return FALLBACK_EVENTS

def get_on_this_day(dt):
    try:
        data = fetch_json(f"{ON_THIS_DAY_URL}/{dt.month}/{dt.day}")
        events = []
        for item in data.get("events", []):
            year, text = item.get("year"), clean_text(item.get("text", ""))
            if year and text:
                events.append(f"{year}: {text}")
            if len(events) >= 20:
                break
        if events:
            return unique_texts(events)
    except Exception as error:
        print(f"History feed unavailable for {dt:%B %d}: {error}")
    return [f"{dt:%B %d}: Historical information unavailable."]

def xml_time(dt):
    return dt.strftime("%Y%m%d%H%M%S %z")

def xml_safe(value):
    value = str(value)
    value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)
    return escape(value)

def handley_description(slot_title, slot_description, slot_index):
    items = [
        "📞 PHONE: 01282 861631",
        "Handley Aerials — TV, aerial, satellite, connectivity and home entertainment services.",
        f"SERVICE SPOTLIGHT: {HANDLEY_SERVICES[0]}",
        f"AREA COVERAGE: {HANDLEY_COVERAGE}",
        f"ADDRESS: {HANDLEY_ADDRESS}",
        f"OPENING INFORMATION: {HANDLEY_HOURS}",
        "WEBSITE: https://handley-aerials.uk.com/",
        "Call 📞 01282 861631 for advice, service information or to arrange an appointment.",
    ]
    rotations = [
        "TV aerial installation, signal checks and aerial repairs.",
        "Satellite TV, Sky, Freesat and Freeview systems.",
        "Communal TV and Integrated Reception Systems (IRS).",
        "CCTV, access communications and security solutions.",
        "Wi-Fi, data networking, fibre cabling and connectivity.",
        "Multi-room TV/audio, home cinema and TV mounting.",
        "FM and DAB radio aerials and reception troubleshooting.",
    ]
    items.insert(2, "FEATURED SERVICE: " + rotations[slot_index % len(rotations)])
    return "\n".join(items)

def generate():
    now = datetime.now(TZ)
    today_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
    start = today_start - timedelta(days=BACK_DAYS)
    end = start + timedelta(days=TOTAL_DAYS)
    print(f"Local time: {now.isoformat()}")
    print(f"Guide starts: {start.isoformat()}")
    print(f"Guide ends:   {end.isoformat()}")

    forecast = get_weather()
    news_list = get_local_news()
    events_list = get_upcoming_events(now)
    history_cache = {}

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Lancashire CCTV EPG" source-info-name="CCTV EPG">',
    ]
    for channel_id, name in CHANNELS.items():
        lines.extend([
            f'  <channel id="{xml_safe(channel_id)}">',
            f'    <display-name>{xml_safe(name)}</display-name>',
            f'    <icon src="{PICON_URL}"/>',
            '  </channel>',
        ])

    programme_count = 0
    for day in range(TOTAL_DAYS):
        day_start = start + timedelta(days=day)
        date_key = day_start.strftime("%Y-%m-%d")
        if date_key not in history_cache:
            history_cache[date_key] = get_on_this_day(day_start)
        day_history = history_cache[date_key]

        for slot in range(SLOTS_PER_DAY):
            begin = day_start + timedelta(hours=slot * SLOT_HOURS)
            finish = begin + timedelta(hours=SLOT_HOURS)
            slot_index = day * SLOTS_PER_DAY + slot
            title, description = SLOTS[slot % len(SLOTS)]
            current_weather = weather_description(begin, forecast)
            current_news = news_list[slot_index % len(news_list)]
            current_event = events_list[slot_index % len(events_list)]
            current_history = day_history[slot_index % len(day_history)]

            for channel_id, name in CHANNELS.items():
                description_lines = ["🔴 LIVE CCTV", description]
                if channel_id == "1":
                    description_lines.extend([
                        f"🌤️ LANCASHIRE WEATHER: {current_weather}",
                        f"📰 LANCASHIRE NEWS: {current_news}",
                        "📞 HANDLEY AERIALS:",
                        handley_description(title, description, slot_index),
                    ])
                elif channel_id == "2":
                    description_lines.append(f"📅 UPCOMING LANCASHIRE EVENT: {current_event}")
                elif channel_id == "3":
                    description_lines.append(f"📍 LANCASHIRE WHAT'S ON: {current_event}")
                elif channel_id == "4":
                    description_lines.append(f"📜 ON THIS DAY: {current_history}")
                elif channel_id == "5":
                    description_lines.extend([
                        f"📰 LANCASHIRE NEWS: {current_news}",
                        f"📅 UPCOMING EVENT: {current_event}",
                    ])
                elif channel_id == "35":
                    description_lines = [
                        "📞 HANDLEY AERIALS — CONTACT & SERVICES",
                        handley_description(title, description, slot_index),
                    ]

                full_description = "\n".join(description_lines)
                programme_title = (
                    f"Handley Aerials: {title}" if channel_id == "35"
                    else f"{name}: {title}"
                )
                lines.extend([
                    f'  <programme start="{xml_time(begin)}" stop="{xml_time(finish)}" channel="{xml_safe(channel_id)}">',
                    f'    <title>{xml_safe(programme_title)}</title>',
                    f'    <desc>{xml_safe(full_description)}</desc>',
                    '    <category>CCTV</category>',
                    '  </programme>',
                ])
                programme_count += 1

    lines.append("</tv>")
    Path(OUTPUT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT_FILE}")
    print(f"Channels: {len(CHANNELS)}")
    print(f"Days covered: {TOTAL_DAYS}")
    print(f"Programme entries: {programme_count}")
    print(f"Output size: {Path(OUTPUT_FILE).stat().st_size:,} bytes")

if __name__ == "__main__":
    generate()
