#!/usr/bin/env python3
import json, re, urllib.request
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta
from pathlib import Path

URL="https://stamet-samarinda.bmkg.go.id/iklim/kualitas-udara"
WITA=timezone(timedelta(hours=8))

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self,data):
        if data and data.strip(): self.parts.append(data.strip())

req=urllib.request.Request(URL,headers={
    "User-Agent":"Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Accept":"text/html,application/xhtml+xml"
})
with urllib.request.urlopen(req,timeout=30) as r:
    raw=r.read().decode("utf-8","replace")

p=TextExtractor(); p.feed(unescape(raw))
text=re.sub(r"\s+"," "," ".join(p.parts))

m_value=re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*µg/m(?:³|3)",text,re.I)
m_update=re.search(r"Update:\s*([^|]{0,80}?WITA)",text,re.I)
m_trend=re.search(r"Tren:\s*(Meningkat|Menurun|Stabil)",text,re.I)
if not m_value:
    raise RuntimeError("Nilai PM2.5 tidak ditemukan")

value=float(m_value.group(1).replace(",","."))

def classify(v):
    if v<=15.5:return "Baik"
    if v<=55.4:return "Sedang"
    if v<=150.4:return "Tidak Sehat"
    if v<=250.4:return "Sangat Tidak Sehat"
    return "Berbahaya"

payload={
    "value":value,
    "status":classify(value),
    "trend":m_trend.group(1).title() if m_trend else "Stabil",
    "updated":m_update.group(1).strip() if m_update else "—",
    "checked":datetime.now(WITA).strftime("%d %b %Y · %H:%M WITA"),
    "source":URL
}
Path("data.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False))
