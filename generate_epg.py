
import json
import random
import re
import hashlib
import html
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

# ============================================================
# CCTV EPG CONFIGURATION
# ============================================================

TZ = ZoneInfo("Europe/London")

DAYS_AHEAD = 7
BACK_DAYS = 3
TOTAL_DAYS = BACK_DAYS + DAYS_AHEAD

SLOT_HOURS = 2
SLOTS_PER_DAY = 24 // SLOT_HOURS

OUTPUT_FILE = "cctv-epg.xml"
JOKE_CACHE_FILE = "joke_cache.json"

LATITUDE = 53.75
LONGITUDE = -2.36

LOCAL_NEWS_URL = (
    "https://feeds.bbci.co.uk/news/england/lancashire/rss.xml"
)
ON_THIS_DAY_URL = (
    "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events"
)

JOKE_API = "https://v2.jokeapi.dev/joke"

# Retain the existing 34 channel IDs.
CHANNELS = {
    str(i): f"Camera {i:02d}"
    for i in range(1, 35)
}

# These information feeds use the first five channel IDs.
# Edit the names above if you want different public defaults.

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

# ============================================================
# OFFLINE FALLBACKS
# ============================================================

FALLBACK_CLEAN_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call a fake noodle? An impasta!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
    "How does a penguin build its house? Igloos it together!",
    "Why don't skeletons fight? They don't have the guts.",
    "What do you call a belt made out of watches? A waist of time!",
    "Why did the bicycle fall over? It was two-tired.",
    "What kind of tree fits in your hand? A palm tree.",
    "Why was the maths book sad? It had too many problems.",
    "What do clouds wear? Thunderwear.",
    "Why did the golfer bring two pairs of trousers? In case he got a hole in one.",
    "What do you call cheese that isn't yours? Nacho cheese.",
    "Why can't your nose be twelve inches long? Then it would be a foot.",
    "What do you call a sleeping bull? A bulldozer.",
    "Why did the computer go to the doctor? It had a virus.",
    "What did one wall say to the other? I'll meet you at the corner.",
    "Why was the broom late? It swept in.",
    "What do you call a bear with no teeth? A gummy bear.",
    "Why did the tomato blush? It saw the salad dressing.",
    "What kind of shoes do ninjas wear? Sneakers.",
    "Why are elevator jokes so good? They work on many levels.",
    "What did the ocean say to the beach? Nothing, it just waved.",
    "Why did the cookie go to hospital? It felt crummy.",
    "What do you call a dinosaur with an extensive vocabulary? A thesaurus.",
    "Why did the picture go to jail? It was framed.",
    "What do you call a can opener that doesn't work? A can't opener.",
    "Why did the stadium get hot? All the fans left.",
    "What has ears but cannot hear? A cornfield.",
    "Why was the calendar nervous? Its days were numbered.",
    "What do you call a pile of cats? A meowtain.",
]

FALLBACK_DARK_JOKES = [
    "I told my doctor I broke my arm in two places. He told me to stop going to those places.",
    "My grandfather has the heart of a lion and a lifetime ban from the zoo.",
    "You don't need a parachute to go skydiving. You only need one to go skydiving twice.",
    "I have a stepladder because my real ladder left when I was a child.",
    "I started a company selling land mines disguised as prayer mats. Prophets are going through the roof.",
    "My grief counsellor died. He was so good, I don't even care.",
    "I have a joke about an unstable chair, but it might collapse under pressure.",
    "I used to be addicted to soap, but I'm clean now.",
    "The cemetery is so popular because people are dying to get in.",
    "I asked the undertaker for a discount. He said business was dead.",
    "My memory is so bad I can hide my own Easter eggs.",
    "I bought a coffin with a lifetime guarantee. That seems optimistic.",
    "I told my suitcase there would be no holidays this year. Now I'm dealing with emotional baggage.",
    "My doctor told me to watch my drinking. So now I drink in front of a mirror.",
    "I wrote a book about falling down stairs. It has its ups and downs.",
    "The future, the present and the past walked into a bar. Things got tense.",
    "I have a fear of speed bumps, but I'm slowly getting over it.",
    "I tried to organise a hide-and-seek tournament, but good players are hard to find.",
    "My bank account is like an onion. Looking at it makes me cry.",
    "I wanted to learn how to make ice, but I lost interest.",
    "My house is haunted by an optimist. Everything goes bump in the bright side.",
    "I bought a used hearse. The previous owner was the last person to drive it.",
    "I don't trust stairs. They're always up to something.",
    "I tried writing a joke about a broken pencil, but it was pointless.",
    "My calendar's days are numbered, and it knows it.",
    "I opened a restaurant on a cliff. The reviews have been up and down.",
    "I told my plants a dark joke. They didn't laugh; they just needed more thyme.",
    "I wanted to be a grave digger, but I couldn't get to the bottom of it.",
    "I lost my job at the orange juice factory. I couldn't concentrate.",
    "I started a business making emergency exits. When things got bad, I left.",
]

FALLBACK_EVENTS = [
    "Accrington Market Hall: Local market and shopping.",
    "Haworth Art Gallery: Tiffany glass collection.",
    "Towneley Hall, Burnley: Historic house and parkland.",
    "East Lancashire Railway: Heritage railway attraction.",
    "Oswaldtwistle Mills: Heritage shopping village.",
    "Peel Park, Accrington: Parkland and walking routes.",
]

# ============================================================
# GENERAL HELPERS
# ============================================================

def fetch_json(url, timeout=10):
    request = Request(
        url,
        headers={
            "User-Agent": "CCTV-EPG/2.0 (public XMLTV generator)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url, timeout=10):
    request = Request(
        url,
        headers={"User-Agent": "CCTV-EPG/2.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def normalise_joke(text):
    """Normalise spacing/case for duplicate detection."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def joke_key(text):
    return hashlib.sha256(
        normalise_joke(text).encode("utf-8")
    ).hexdigest()


def unique_texts(items):
    result = []
    seen = set()

    for item in items:
        if not isinstance(item, str):
            continue

        item = re.sub(r"\s+", " ", item).strip()
        key = normalise_joke(item)

        if item and key not in seen:
            seen.add(key)
            result.append(item)

    return result


def load_joke_cache():
    empty = {
        "safe": [],
        "dark": [],
        "recent_safe": [],
        "recent_dark": [],
    }

    try:
        data = json.loads(
            Path(JOKE_CACHE_FILE).read_text(encoding="utf-8")
        )

        for key in empty:
            if not isinstance(data.get(key), list):
                data[key] = []

        return data

    except (OSError, ValueError, TypeError):
        return empty


def save_joke_cache(cache):
    try:
        Path(JOKE_CACHE_FILE).write_text(
            json.dumps(cache, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        print(f"Could not save joke cache: {error}")


# ============================================================
# JOKES: BATCH FETCHING, DEDUPLICATION AND ROTATION
# ============================================================

def fetch_joke_batch(category):
    if category == "safe":
        url = (
            f"{JOKE_API}/Any?"
            + urlencode({
                "amount": 10,
                "safe-mode": "",
            })
        )
    else:
        url = (
            f"{JOKE_API}/Dark,Pun?"
            + urlencode({"amount": 10})
        )

    data = fetch_json(url)

    if data.get("error"):
        raise ValueError(data.get("message", "Joke API error"))

    results = []

    # JokeAPI returns a "jokes" array for amount requests.
    # It can also return one joke object.
    jokes = data.get("jokes", [data])

    for joke in jokes:
        if joke.get("type") == "single":
            text = joke.get("joke", "")
        elif joke.get("type") == "twopart":
            text = (
                f"{joke.get('setup', '')} "
                f"{joke.get('delivery', '')}"
            )
        else:
            continue

        text = re.sub(r"\s+", " ", text).strip()

        if text:
            results.append(text)

    return results


def build_joke_pool(category, cache, required):
    pool_key = category
    recent_key = f"recent_{category}"

    pool = unique_texts(cache.get(pool_key, []))
    seen = {normalise_joke(joke) for joke in pool}

    # Refresh the pool every run, but don't hammer the API.
    # Continue fetching on a first run until enough unique
    # jokes exist or the retry limit is reached.
    batches = 3
    if len(pool) < required:
        batches = 18

    for _ in range(batches):
        try:
            batch = fetch_joke_batch(category)

            for joke in batch:
                key = normalise_joke(joke)
                if key not in seen:
                    seen.add(key)
                    pool.append(joke)

        except Exception as error:
            print(f"Joke API ({category}) unavailable: {error}")
            break

        if len(pool) >= required + 30:
            break

    # Add reliable offline fallbacks if the API pool is small.
    fallbacks = (
        FALLBACK_CLEAN_JOKES
        if category == "safe"
        else FALLBACK_DARK_JOKES
    )

    for joke in fallbacks:
        key = normalise_joke(joke)
        if key not in seen:
            seen.add(key)
            pool.append(joke)

    # Keep a bounded cache so the JSON file stays manageable.
    random.shuffle(pool)
    pool = pool[:500]

    recent = cache.get(recent_key, [])
    recent_set = set(recent)

    # Prefer jokes that haven't appeared in recent generations.
    fresh = [
        joke for joke in pool
        if joke_key(joke) not in recent_set
    ]

    if len(fresh) >= required:
        selected = random.sample(fresh, required)
    elif len(pool) >= required:
        selected = random.sample(pool, required)
        print(
            f"Warning: {category} joke pool has fewer fresh jokes "
            "than required; some recent jokes may return."
        )
    else:
        # There aren't enough unique jokes to fill every slot.
        # Use each available joke before repeating any.
        selected = pool.copy()
        random.shuffle(selected)

        print(
            f"Warning: only {len(selected)} unique {category} jokes "
            f"available for {required} slots."
        )

        if not selected:
            selected = list(fallbacks)

    # Save a history of jokes used in this run.
    history = list(recent)
    history.extend(joke_key(joke) for joke in selected)

    # Keep recent history bounded.
    cache[pool_key] = pool
    cache[recent_key] = history[-500:]

    return selected


# ============================================================
# WEATHER
# ============================================================

def get_weather():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": (
            "temperature_2m,precipitation_probability,weather_code"
        ),
        "forecast_days": 7,
        "timezone": "Europe/London",
    }

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urlencode(params)
    )

    try:
        hourly = fetch_json(url)["hourly"]
        result = {}

        for index, time_string in enumerate(hourly["time"]):
            dt = datetime.fromisoformat(time_string).replace(tzinfo=TZ)

            result[dt] = {
                "temperature": hourly["temperature_2m"][index],
                "rain": hourly["precipitation_probability"][index],
                "code": hourly["weather_code"][index],
            }

        print(f"Loaded {len(result)} hourly weather records.")
        return result

    except Exception as error:
        print(f"Weather API unavailable: {error}")
        return {}


def weather_description(begin, forecast):
    entries = [
        forecast.get(begin),
        forecast.get(begin + timedelta(hours=1)),
    ]
    entries = [entry for entry in entries if entry]

    if not entries:
        return "Forecast unavailable for this time."

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
        57: "Heavy freezing drizzle",
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
        item["temperature"] for item in entries
        if item["temperature"] is not None
    ]
    rain_values = [
        item["rain"] for item in entries
        if item["rain"] is not None
    ]

    temperature_text = (
        f"{round(sum(temperatures) / len(temperatures))}°C"
        if temperatures else "N/A"
    )

    rain_text = (
        f"{max(rain_values)}% precipitation probability"
        if rain_values else "Precipitation probability unavailable"
    )

    condition = conditions.get(
        entries[0]["code"], "Variable conditions"
    )

    return f"{condition}; {temperature_text}; {rain_text}."


# ============================================================
# LOCAL NEWS
# ============================================================

def get_local_news():
    try:
        root = ET.fromstring(fetch_text(LOCAL_NEWS_URL))
        headlines = []

        for item in root.findall("./channel/item"):
            title = item.findtext("title", "").strip()
            description = item.findtext("description", "").strip()

            # RSS descriptions may contain HTML entities/tags.
            description = html.unescape(description)
            description = re.sub(r"<[^>]+>", "", description)
            description = re.sub(r"\s+", " ", description).strip()

            if not title:
                continue

            text = title
            if description and len(description) < 180:
                text += " — " + description

            headlines.append(text)

        headlines = unique_texts(headlines)

        if headlines:
            print(f"Loaded {len(headlines)} local news headlines.")
            return headlines

        return ["Local news updates currently unavailable."]

    except Exception as error:
        print(f"Local news feed unavailable: {error}")
        return ["Local news feed currently offline."]


# ============================================================
# ON THIS DAY
# ============================================================

def get_on_this_day(dt):
    url = f"{ON_THIS_DAY_URL}/{dt.month}/{dt.day}"

    try:
        data = fetch_json(url)
        events = []

        for item in data.get("events", []):
            year = item.get("year")
            text = item.get("text", "").strip()

            if year and text:
                events.append(f"{year}: {text}")

            if len(events) >= 30:
                break

        if events:
            return unique_texts(events)

    except Exception as error:
        print(
            f"On This Day unavailable for "
            f"{dt.strftime('%B %d')}: {error}"
        )

    return [
        f"{dt.strftime('%B %d')}: Historical information unavailable."
    ]


# ============================================================
# XMLTV GENERATION
# ============================================================

def xml_time(dt):
    return dt.strftime("%Y%m%d%H%M%S %z")


def xml_safe(text):
    # XML 1.0 does not permit most control characters.
    text = str(text)
    text = re.sub(
        r"[\x00-\x08\x0B\x0C\x0E-\x1F]",
        "",
        text,
    )
    return escape(text)


def generate():
    now = datetime.now(TZ)

    # Start at 06:00 three calendar days ago.
    # Ten complete 06:00-to-06:00 days provide the
    # requested three historical days plus seven ahead.
    today_start = now.replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    start = today_start - timedelta(days=BACK_DAYS)
    end = start + timedelta(days=TOTAL_DAYS)

    print(f"Local time: {now.isoformat()}")
    print(f"Guide starts: {start.isoformat()}")
    print(f"Guide ends:   {end.isoformat()}")

    forecast = get_weather()
    news_list = get_local_news()
    joke_cache = load_joke_cache()

    joke_slots = TOTAL_DAYS * SLOTS_PER_DAY

    clean_jokes = build_joke_pool(
        "safe", joke_cache, joke_slots
    )
    dark_jokes = build_joke_pool(
        "dark", joke_cache, joke_slots
    )

    save_joke_cache(joke_cache)

    # Avoid predictable joke order between runs.
    random.shuffle(clean_jokes)
    random.shuffle(dark_jokes)

    history_cache = {}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Reusable CCTV EPG" '
        'source-info-name="CCTV EPG">',
    ]

    # Channel declarations
    for channel_id, name in CHANNELS.items():
        lines.extend([
            f'  <channel id="{xml_safe(channel_id)}">',
            f'    <display-name>{xml_safe(name)}</display-name>',
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
            current_event = FALLBACK_EVENTS[
                slot_index % len(FALLBACK_EVENTS)
            ]

            # Each humour schedule contains unique jokes where
            # the available pool is large enough.
            clean_joke = (
                clean_jokes[slot_index % len(clean_jokes)]
            )
            dark_joke = (
                dark_jokes[slot_index % len(dark_jokes)]
            )

            current_history = day_history[
                slot_index % len(day_history)
            ]

            for channel_id, name in CHANNELS.items():
                description_lines = [
                    "🔴 LIVE CCTV",
                    description,
                ]

                if channel_id == "1":
                    description_lines.extend([
                        f"🌤️ WEATHER: {current_weather}",
                        f"📰 LOCAL NEWS: {current_news}",
                    ])

                elif channel_id == "2":
                    description_lines.append(
                        f"📍 LOCAL HIGHLIGHT: {current_event}"
                    )

                elif channel_id == "3":
                    description_lines.append(
                        f"😄 CLEAN JOKE: {clean_joke}"
                    )

                elif channel_id == "4":
                    description_lines.append(
                        f"📜 ON THIS DAY: {current_history}"
                    )

                elif channel_id == "5":
                    description_lines.append(
                        f"😈 DARK HUMOUR: {dark_joke}"
                    )

                full_description = "\n".join(description_lines)

                lines.extend([
                    (
                        f'  <programme start="{xml_time(begin)}" '
                        f'stop="{xml_time(finish)}" '
                        f'channel="{xml_safe(channel_id)}">'
                    ),
                    f'    <title>{xml_safe(name + ": " + title)}</title>',
                    f'    <desc>{xml_safe(full_description)}</desc>',
                    '    <category>CCTV</category>',
                    '  </programme>',
                ])

                programme_count += 1

    lines.append("</tv>")

    Path(OUTPUT_FILE).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"Generated {OUTPUT_FILE}")
    print(f"Channels: {len(CHANNELS)}")
    print(f"Days covered: {TOTAL_DAYS}")
    print(f"Programme slots per channel: {joke_slots}")
    print(f"Total programme entries: {programme_count}")
    print(f"Output size: {Path(OUTPUT_FILE).stat().st_size:,} bytes")


if __name__ == "__main__":
    generate()
