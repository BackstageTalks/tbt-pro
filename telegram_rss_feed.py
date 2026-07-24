# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

BOT_TOKEN = os.getenv("TGBOT") or os.getenv("TG_BOT") or os.getenv("TG_BOT_BTLKR")
CHAT_ID = os.getenv("TGCHID") or os.getenv("TG_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = os.getenv("TBTPRO_BASE_URL", "https://backstagetalks.github.io/tbt-pro/").rstrip("/") + "/"
CORQ_FEED_URL = os.getenv("CORQ_FEED_URL", BASE_URL + "h4v34n1c3d4y184.xml")
THINQ_FEED_URL = os.getenv("THINQ_FEED_URL", BASE_URL + "h4v34n1c3d4y187.xml")
CLOQ_FEED_URL = os.getenv("CLOQ_FEED_URL", BASE_URL + "h4v34n1c3d4y185.xml")
SELECTED_FEED = os.getenv("TG_FEED", "corq").strip().lower()
PICK_LIMIT = int(os.getenv("TG_PICK_LIMIT", "7"))
FAIL_ON_EMPTY = os.getenv("TG_FAIL_ON_EMPTY", "0").strip().lower() in {"1", "true", "yes", "y"}

FEEDS = {
    "corq": (CORQ_FEED_URL, "TOP7 | Corq Model"),
    "thinq": (THINQ_FEED_URL, "TOP7 | Thinq Model"),
    "cloq": (CLOQ_FEED_URL, "TOP7 | Cloq Model"),
}

def bratislava_tz():
    if ZoneInfo is not None:
        return ZoneInfo("Europe/Bratislava")
    return timezone.utc

def today_bratislava() -> str:
    return datetime.now(timezone.utc).astimezone(bratislava_tz()).strftime("%d.%m.%Y")

def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(str(value))
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value)
    return value.strip()

def clean_one_line(value: str | None) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).strip()

def field(label: str, text: str) -> str:
    pattern = re.escape(label) + r":\s*([^:]+?)(?=\s+[A-Z][A-Za-z /]+:|\s+ThinQ summary:|\s+This data|$)"
    match = re.search(pattern, text)
    return clean_one_line(match.group(1)) if match else ""

def to_float(value: str | None) -> float:
    try:
        if not value:
            return 0.0
        return float(re.sub(r"[^0-9.+-]", "", value).replace(",", "."))
    except Exception:
        return 0.0

def fetch_xml(url: str) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": "TBT-PRO-Telegram-RSS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    return ET.fromstring(data)

def get_text(item: ET.Element, tag: str) -> str:
    node = item.find(tag)
    return clean_text(node.text if node is not None else "")

def parse_entry(item: ET.Element) -> dict:
    title = get_text(item, "title")
    desc = clean_one_line(get_text(item, "description"))
    return {
        "title": title,
        "time": field("Time", desc) or (title.split(" | ", 1)[0] if " | " in title else ""),
        "pick": field("Pick", desc),
        "opponent": field("Opponent", desc),
        "prob": field("Win probability", desc),
        "odds": field("Odds", desc),
        "corq": field("CorQ", desc) or field("Corq AI", desc) or field("Win probability", desc),
    }

def item_line(idx: int, pick: dict) -> str:
    digits = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
    badge = digits[idx] if idx < len(digits) else f"{idx}."
    name = pick.get("pick") or pick.get("title") or "—"
    time = pick.get("time") or "—"
    prob = pick.get("prob") or pick.get("corq") or "—"
    odds = pick.get("odds") or "—"
    return f"{badge} {name} | {time} | {prob} | {odds}"

def build_message(feed_url: str, feed_title: str, limit: int) -> str:
    root = fetch_xml(feed_url)
    items = root.findall("./channel/item")
    picks = [parse_entry(item) for item in items]
    picks = sorted(picks, key=lambda p: to_float(p.get("corq") or p.get("prob")), reverse=True)[:limit]
    lines = [
        "AI Betting by Backstage Talks",
        f"📅 {today_bratislava()}, 🎾 {feed_title}",
        "",
    ]
    lines.extend(item_line(i, pick) for i, pick in enumerate(picks, 1))
    lines.extend(["", "ℹ️ Analytical preview only", "🧠 by BackstageTalks AI Engine"])
    return "\n".join(lines).strip()

def send_telegram_message(message: str) -> None:
    if not BOT_TOKEN:
        raise ValueError("Missing Telegram bot secret. Set TGBOT or TG_BOT_BTLKR.")
    if not CHAT_ID:
        raise ValueError("Missing Telegram chat secret. Set TGCHID or TG_CHAT_ID.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": "true",
    }).encode()
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", "replace")
    if '"ok":true' not in body:
        raise RuntimeError(f"Telegram send failed: {body}")

def selected_feeds() -> list[tuple[str, str, str]]:
    if SELECTED_FEED in {"", "all", "*"}:
        keys = ["corq", "thinq", "cloq"]
    else:
        keys = [SELECTED_FEED]
    return [(key, *FEEDS[key]) for key in keys if key in FEEDS]

def main() -> None:
    sent = 0
    for key, url, title in selected_feeds():
        message = build_message(url, title, PICK_LIMIT)
        if not message.strip():
            print(f"No message for {key}")
            continue
        print(f"Sending {key} feed from {url}")
        send_telegram_message(message)
        sent += 1
    if sent == 0 and FAIL_ON_EMPTY:
        raise RuntimeError("No Telegram RSS messages sent")
    print(f"Telegram RSS feed sent: {sent}")

if __name__ == "__main__":
    main()
