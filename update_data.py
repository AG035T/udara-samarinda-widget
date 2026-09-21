import json
import re
import urllib.request
from html import unescape, escape
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta
from pathlib import Path

SOURCE_URL = "https://www.bmkg.go.id/kualitas-udara/pm25"
FETCH_URL = "https://r.jina.ai/https://www.bmkg.go.id/kualitas-udara/pm25"

WIB = timezone(timedelta(hours=7))
WITA = timezone(timedelta(hours=8))

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data.strip())

def marker_x(v):
    if v <= 15.5:
        pct = (v / 15.5) * 20
    elif v <= 55.4:
        pct = 20 + ((v - 15.5) / (55.4 - 15.5)) * 20
    elif v <= 150.4:
        pct = 40 + ((v - 55.4) / (150.4 - 55.4)) * 20
    elif v <= 250.4:
        pct = 60 + ((v - 150.4) / (250.4 - 150.4)) * 20
    else:
        pct = min(98, 80 + ((v - 250.4) / 150) * 20)
    return 14 + (292 * pct / 100)

def status_color(status):
    return {
        "Baik": "#22c55e",
        "Sedang": "#f6c445",
        "Tidak Sehat": "#f08a45",
        "Sangat Tidak Sehat": "#e24d6b",
        "Berbahaya": "#a855f7",
    }.get(status, "#f6c445")

def make_svg(payload):
    value = float(payload["value"])
    status = escape(str(payload["status"]))
    trend = escape(str(payload["trend"]))
    updated = escape(str(payload["updated"]))
    checked = escape(str(payload["checked"]))
    arrow = "↗" if payload["trend"] == "Meningkat" else "↘" if payload["trend"] == "Menurun" else "→"
    dot = status_color(payload["status"])
    marker = marker_x(value)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#216af0"/>
    <stop offset="1" stop-color="#0e4fda"/>
  </linearGradient>
</defs>
<rect width="320" height="320" rx="22" fill="url(#bg)"/>
<text x="18" y="28" fill="#dce8ff" font-family="Arial,sans-serif" font-size="8" font-weight="700" letter-spacing="1">PEMANTAUAN KUALITAS UDARA</text>
<text x="18" y="50" fill="#ffffff" font-family="Arial,sans-serif" font-size="19" font-weight="700">Udara Samarinda</text>
<rect x="274" y="16" width="32" height="32" rx="10" fill="#ffffff" fill-opacity=".14"/>
<text x="290" y="38" text-anchor="middle" fill="#ffffff" font-family="Arial,sans-serif" font-size="18">↻</text>
<text x="18" y="126" fill="#ffffff" font-family="Arial,sans-serif" font-size="64" font-weight="800">{value:.1f}</text>
<text x="220" y="126" fill="#dce8ff" font-family="Arial,sans-serif" font-size="15" font-weight="700">µg/m³</text>
<rect x="18" y="148" width="108" height="30" rx="15" fill="#ffffff"/>
<circle cx="31" cy="163" r="4" fill="{dot}"/>
<text x="41" y="168" fill="#13213a" font-family="Arial,sans-serif" font-size="11" font-weight="700">{status}</text>
<text x="137" y="168" fill="#eef4ff" font-family="Arial,sans-serif" font-size="12" font-weight="700">{arrow} {trend}</text>
<text x="18" y="205" fill="#dce8ff" font-family="Arial,sans-serif" font-size="9" font-weight="700">Update BMKG: {updated}</text>
<rect x="14" y="220" width="58.4" height="7" rx="4" fill="#22c55e"/>
<rect x="72.4" y="220" width="58.4" height="7" fill="#f6c445"/>
<rect x="130.8" y="220" width="58.4" height="7" fill="#f08a45"/>
<rect x="189.2" y="220" width="58.4" height="7" fill="#e24d6b"/>
<rect x="247.6" y="220" width="58.4" height="7" rx="4" fill="#a855f7"/>
<rect x="{marker-2:.1f}" y="214" width="4" height="19" rx="2" fill="#ffffff"/>
<text x="18" y="250" fill="#dce8ff" font-family="Arial,sans-serif" font-size="8">Sumber diperiksa: {checked}</text>
<text x="18" y="267" fill="#dce8ff" font-family="Arial,sans-serif" font-size="8">Pengukuran mengikuti ketersediaan BMKG</text>
</svg>
"""

req = urllib.request.Request(
    FETCH_URL,
    headers={"User-Agent": "Mozilla/5.0", "Accept": "text/plain,text/html"}
)

with urllib.request.urlopen(req, timeout=30) as r:
    raw = r.read().decode("utf-8", "replace")

parser = TextExtractor()
parser.feed(unescape(raw))
text = re.sub(r"\s+", " ", " ".join(parser.parts))

match = re.search(
    r"Samarinda\s+([0-9]{1,2}\.[0-9]{2})\s+WIB"
    r".{0,160}?"
    r"PM\s*(?:_?\{?\s*2[.,]5\s*\}?|2[.,]5)"
    r"\s*:?\s*([0-9]+(?:[.,][0-9]+)?)",
    text,
    re.I
)

if not match:
    raise RuntimeError("Data Samarinda tidak ditemukan pada halaman BMKG")

time_text = match.group(1)
value = float(match.group(2).replace(",", "."))

if value <= 15.5:
    status = "Baik"
elif value <= 55.4:
    status = "Sedang"
elif value <= 150.4:
    status = "Tidak Sehat"
elif value <= 250.4:
    status = "Sangat Tidak Sehat"
else:
    status = "Berbahaya"

old_value = None
try:
    old = json.loads(Path("data.json").read_text(encoding="utf-8"))
    old_value = float(old.get("value"))
except Exception:
    pass

if old_value is None:
    trend = "Stabil"
elif value > old_value:
    trend = "Meningkat"
elif value < old_value:
    trend = "Menurun"
else:
    trend = "Stabil"

hour, minute = map(int, time_text.split("."))
now_wib = datetime.now(WIB)

measurement_wib = now_wib.replace(hour=hour, minute=minute, second=0, microsecond=0)

if measurement_wib > now_wib + timedelta(hours=2):
    measurement_wib -= timedelta(days=1)

measurement_wita = measurement_wib.astimezone(WITA)
checked_wita = datetime.now(WITA)

payload = {
    "value": value,
    "status": status,
    "trend": trend,
    "updated": measurement_wita.strftime("%d %b %Y · %H:%M WITA"),
    "checked": checked_wita.strftime("%d %b %Y · %H:%M WITA"),
    "source": SOURCE_URL
}

Path("data.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

Path("widget.svg").write_text(make_svg(payload), encoding="utf-8")

stamp = checked_wita.strftime("%Y%m%d%H%M")
viewer = f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Udara Samarinda</title>
<style>
html,body{{margin:0;padding:0;background:transparent;width:100%;height:100%;overflow:hidden}}
body{{display:flex;justify-content:center;align-items:flex-start;padding-top:8px}}
img{{display:block;width:320px;height:320px;border:0}}
</style>
</head>
<body>
<img id="card" src="widget.svg?v={stamp}" alt="Udara Samarinda">
</body>
</html>
"""
Path("widget-live.html").write_text(viewer, encoding="utf-8")

print(json.dumps(payload, ensure_ascii=False))
