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
except Exception:  # pragma: no cover
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
    "corq": (CORQ_FEED_URL, "TOP7 | CorQ"),
    "thinq": (THINQ_FEED_URL, "TOP7 | ThinQ"),
    "cloq": (CLOQ_FEED_URL, "CloQ"),
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
    text = html.unescape(str(value))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def clean_one_line(value: str | None) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).strip()


def fetch_xml(url: str) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": "TBT-PRO-Telegram-RSS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    return ET.fromstring(data)


def get_text(item: ET.Element, tag: str) -> str:
    node = item.find(tag)
    return clean_text(node.text if node is not None else "")


def _label_value(desc: str, label: str) -> str:
    """Extract values from RSS descriptions written as 'Label: value'.

    Works even when descriptions are rendered on one line by RSS readers.
    """
    labels = [
        "Time",
        "Pick",
        "Opponent",
        "Win probability",
        "Probability",
        "Odds",
        "CorQ",
        "Corq AI",
        "ThinQ",
        "CloQ",
        "Tournament",
        "Surface",
    ]
    next_labels = "|".join(re.escape(x) for x in labels if x.lower() != label.lower())
    pattern = rf"\b{re.escape(label)}\s*:\s*(.*?)(?=\s+(?:{next_labels})\s*:|$)"
    match = re.search(pattern, desc, flags=re.I)
    if not match:
        return ""
    return clean_one_line(match.group(1))


def to_float(value: str | None) -> float:
    try:
        if value is None:
            return 0.0
        text = str(value).replace(",", ".")
        text = re.sub(r"[^0-9.+-]", "", text)
        return float(text) if text else 0.0
    except Exception:
        return 0.0


def format_pct(value: str | None) -> str:
    if not value:
        return "—"
    number = to_float(value)
    if number <= 0:
        return clean_one_line(value) or "—"
    return f"{number:.1f}%"


def format_odds(value: str | None) -> str:
    if not value:
        return "—"
    number = to_float(value)
    if number <= 0:
        return clean_one_line(value) or "—"
    return f"{number:.2f}"


def surname(full_name: str | None) -> str:
    name = clean_one_line(full_name)
    if not name:
        return "—"
    # Remove common decorations that can appear in titles/descriptions.
    name = re.sub(r"\s+\([^)]*\)$", "", name).strip()
    parts = [p for p in re.split(r"\s+", name) if p]
    if not parts:
        return "—"
    return parts[-1]


def _time_from_title(title: str) -> str:
    if " | " in title:
        candidate = title.split(" | ", 1)[0].strip()
        if re.match(r"^\d{1,2}:\d{2}$", candidate):
            return candidate
    match = re.search(r"\b(\d{1,2}:\d{2})\b", title)
    return match.group(1) if match else ""


def parse_entry(item: ET.Element) -> dict:
    title = clean_one_line(get_text(item, "title"))
    desc = clean_one_line(get_text(item, "description"))

    pick = _label_value(desc, "Pick")
    opponent = _label_value(desc, "Opponent")
    probability = (
        _label_value(desc, "Win probability")
        or _label_value(desc, "Probability")
        or _label_value(desc, "CorQ")
        or _label_value(desc, "Corq AI")
    )
    odds = _label_value(desc, "Odds")
    time = _label_value(desc, "Time") or _time_from_title(title)

    # Fallback title pattern: 'HH:MM | Player to beat Opponent'.
    if not pick and " to beat " in title:
        after_time = title.split(" | ", 1)[-1]
        pick = after_time.split(" to beat ", 1)[0].strip()
    if not opponent and " to beat " in title:
        after_time = title.split(" | ", 1)[-1]
        opponent = after_time.split(" to beat ", 1)[1].strip()

    return {
        "title": title,
        "time": time or "—",
        "pick": pick,
        "opponent": opponent,
        "prob": probability,
        "odds": odds,
        "sort_probability": to_float(probability),
    }


def item_line(idx: int, pick: dict) -> str:
    digits = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
    badge = digits[idx] if idx < len(digits) else f"{idx}."
    name = surname(pick.get("pick") or pick.get("title"))
    time = pick.get("time") or "—"
    prob = format_pct(pick.get("prob"))
    odds = format_odds(pick.get("odds"))
    return f"{badge} {name} | {time} | {prob} | {odds}"


def build_message(feed_url: str, feed_title: str, limit: int) -> str:
    root = fetch_xml(feed_url)
    items = root.findall("./channel/item")
    picks = [parse_entry(item) for item in items]
    picks = [p for p in picks if p.get("pick") or p.get("title")]
    picks = sorted(picks, key=lambda p: p.get("sort_probability", 0.0), reverse=True)[:limit]

    lines = [
        "AI Betting by BackstageTalks",
        "",
        f"🎾 {feed_title}",
        f"📅 {today_bratislava()}",
        "",
    ]
    lines.extend(item_line(i, pick) for i, pick in enumerate(picks, 1))
    lines.extend([
        "",
        "ℹ️ Analytical preview only",
        "🧠 by BackstageTalks AI Engine",
    ])
    return "\n".join(lines).strip()


def send_telegram_message(message: str) -> None:
    if not BOT_TOKEN:
        raise ValueError("Missing Telegram bot secret. Set TGBOT or TG_BOT_BTLKR.")
    if not CHAT_ID:
        raise ValueError("Missing Telegram chat secret. Set TGCHID or TG_CHAT_ID.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode()
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", "replace")
    if '"ok":true' not in body:
        raise RuntimeError(f"Telegram send failed: {body[:500]}")


def selected_feeds() -> list[tuple[str, str, str]]:
    if SELECTED_FEED in {"", "all", "*"}:
        keys = ["corq", "cloq"]
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
