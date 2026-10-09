```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

TZ = ZoneInfo("Europe/London")
DAYS = 7

channels = {
    "1": ("Split Screen", [
        ("🌅 Control Room: Morning", "Hikvision multi-camera/NVR control view."),
        ("🚨 Control Room: Perimeter", "Street, entry, garden and outbuilding coverage."),
        ("🔴 Control Room: Live", "Four-camera CCTV split view."),
        ("☀️ Control Room: Day", "Multi-camera daytime monitoring."),
        ("🔎 Control Room: Property", "Multi-zone property surveillance."),
        ("☀️ Control Room: Afternoon", "Continuous property monitoring."),
        ("🌇 Control Room: Evening", "Evening perimeter watch."),
        ("🌙 Control Room: Night", "Night surveillance."),
        ("🌙 Control Room: Surveillance", "Multi-camera night surveillance."),
        ("🌑 Control Room: Late Night", "Late-night security monitoring."),
        ("🌑 Control Room: Overnight", "Overnight multi-camera surveillance."),
        ("🌘 Control Room: Pre-Dawn", "Pre-dawn security monitoring.")
    ]),
    "2": ("Doorbell", [
        ("🌅 Front Entry Watch", "Tapo D130 • 2K 5MP • 180° view • Person/vehicle/pet/package detection • Colour night vision • 2-way audio."),
        ("🚨 Visitor Perimeter", "Tapo D130 • 2K 5MP • AI detection • 2-way audio."),
        ("🔴 Doorbell Live", "Tapo D130 • 2K 5MP • Wide-angle entry monitoring."),
        ("☀️ Front Entry Watch", "Tapo D130 • Front entrance monitoring • 2-way audio."),
        ("🔎 Visitor Watch", "Tapo D130 • Person/vehicle/pet/package detection."),
        ("☀️ Delivery Watch", "Tapo D130 • Delivery monitoring • 2-way audio."),
        ("🌇 Evening Entry", "Tapo D130 • Evening entrance surveillance."),
        ("🌙 Night Entry", "Tapo D130 • Colour night vision."),
        ("🌙 Late Night Entry", "Tapo D130 • Night visitor monitoring."),
        ("🌑 Late Night Security", "Tapo D130 • Entrance night surveillance."),
        ("🌑 Overnight Entry", "Tapo D130 • Overnight monitoring."),
        ("🌘 Pre-Dawn Entry", "Tapo D130 • Pre-dawn surveillance.")
    ]),
    "3": ("Front Street", [
        ("🌅 Street Watch", "Reolink TrackMix • 4K • Dual lens • Auto tracking • Person/vehicle/animal detection."),
        ("🚨 Perimeter Watch", "Reolink TrackMix • 4K dual-lens surveillance."),
        ("🔴 Street Live", "Reolink TrackMix • Dual-view street surveillance."),
        ("☀️ Street Monitoring", "Reolink TrackMix • Detection and auto tracking."),
        ("🔎 Street Activity", "Reolink TrackMix • AI detection and tracking."),
        ("☀️ Traffic Watch", "Reolink TrackMix • Street and traffic monitoring."),
        ("🌇 Evening Street", "Reolink TrackMix • Evening surveillance."),
        ("🌙 Street Night Watch", "Reolink TrackMix • Night surveillance."),
        ("🌙 Night Perimeter", "Reolink TrackMix • Auto-tracking perimeter surveillance."),
        ("🌑 Late Night Street", "Reolink TrackMix • Overnight street monitoring."),
        ("🌑 Overnight Perimeter", "Reolink TrackMix • Overnight security."),
        ("🌘 Pre-Dawn Street", "Reolink TrackMix • Pre-dawn surveillance.")
    ]),
    "4": ("Back Garden", [
        ("🌅 Garden Watch", "Tapo C320WS • 2K QHD 2560×1440 • Colour night vision • Person/vehicle detection • 2-way audio."),
        ("🚨 Rear Perimeter", "Tapo C320WS • 2K QHD • Built-in alarm."),
        ("🔴 Garden Live", "Tapo C320WS • Wide rear garden surveillance."),
        ("☀️ Garden Security", "Tapo C320WS • Person/vehicle detection."),
        ("🔎 Garden Activity", "Tapo C320WS • AI person and vehicle monitoring."),
        ("☀️ Rear Property Watch", "Tapo C320WS • Rear property surveillance • 2-way audio."),
        ("🌇 Evening Garden", "Tapo C320WS • Evening perimeter monitoring."),
        ("🌙 Garden Night Watch", "Tapo C320WS • Colour night vision."),
        ("🌙 Rear Surveillance", "Tapo C320WS • Colour night surveillance."),
        ("🌑 Late Night Garden", "Tapo C320WS • Night surveillance."),
        ("🌑 Overnight Garden", "Tapo C320WS • Overnight rear security."),
        ("🌘 Pre-Dawn Garden", "Tapo C320WS • Pre-dawn surveillance.")
    ]),
    "5": ("Shed", [
        ("🌅 Shed Watch", "Tapo C310 • 3MP 2304×1296 • IR night vision up to 30m • Person/motion detection • 2-way audio."),
        ("🚨 Outbuilding Perimeter", "Tapo C310 • 3MP • Person/motion detection."),
        ("🔴 Shed Live", "Tapo C310 • Shed and outbuilding surveillance."),
        ("☀️ Shed Security", "Tapo C310 • Person/motion monitoring • 2-way audio."),
        ("🔎 Outbuilding Watch", "Tapo C310 • Person/motion detection."),
        ("☀️ Shed Activity", "Tapo C310 • Continuous surveillance."),
        ("🌇 Evening Shed", "Tapo C310 • Evening security."),
        ("🌙 Shed Night Watch", "Tapo C310 • IR night vision up to 30m."),
        ("🌙 Outbuilding Surveillance", "Tapo C310 • IR night vision • 2-way audio."),
        ("🌑 Late Night Shed", "Tapo C310 • Overnight IR surveillance."),
        ("🌑 Overnight Shed", "Tapo C310 • Overnight security."),
        ("🌘 Pre-Dawn Shed", "Tapo C310 • Pre-dawn surveillance.")
    ])
}

def xml_time(dt):
    offset = dt.strftime("%z")
    return dt.strftime("%Y%m%d%H%M%S") + " " + offset

def generate():
    now = datetime.now(TZ)
    start = now.replace(hour=6, minute=0, second=0, microsecond=0)

    if now < start:
        start -= timedelta(days=1)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Rolling CCTV EPG">'
    ]

    for cid, (name, _) in channels.items():
        lines += [
            f'  <channel id="{cid}">',
            f'    <display-name>{escape(name)}</display-name>',
            '  </channel>'
        ]

    for day in range(DAYS):
        for cid, (name, programmes) in channels.items():
            for slot, (title, desc) in enumerate(programmes):
                begin = start + timedelta(days=day, hours=slot * 2)
                end = begin + timedelta(hours=2)

                lines += [
                    f'  <programme start="{xml_time(begin)}" stop="{xml_time(end)}" channel="{cid}">',
                    f'    <title>{escape(title)}</title>',
                    f'    <desc>🔴 LIVE • {escape(desc)}</desc>',
                    '    <category>CCTV</category>',
                    '  </programme>'
                ]

    lines.append('</tv>')

    with open("cctv-epg.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    generate()
```
