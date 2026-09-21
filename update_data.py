import json
import re
import urllib.request
from html import unescape
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


req = urllib.request.Request(
    FETCH_URL,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/plain,text/html"
    }
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

measurement_wib = now_wib.replace(
    hour=hour,
    minute=minute,
    second=0,
    microsecond=0
)

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

print(json.dumps(payload, ensure_ascii=False))
