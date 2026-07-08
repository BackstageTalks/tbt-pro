import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

LOCAL_TZ = ZoneInfo("Europe/Bratislava")
BOT_TOKEN = os.getenv("TG_BOT_BTLKR") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
FORCE_SEND = os.getenv("TG_FORCE_SEND", "false").lower() == "true"


def load_json(path, default):
    try:
        p = Path(path)
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "-"


def dec(value):
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "-"


def short_name(value):
    parts = str(value or "").split()
    return parts[-1] if parts else "-"


def build_message():
    top = load_json("public/torq_top5.json", [])
    bhand = load_json("public/torq_b_hand.json", [])
    today = datetime.now(LOCAL_TZ).strftime("%d.%m.%Y")
    lines = [f"🎾 Torq AI · {today}", "", "🏆 Torq TOP5"]
    if top:
        for idx, item in enumerate(top[:5], 1):
            lines.append(f"{idx}. {short_name(item.get('pick'))} | Torq {pct(item.get('torq_probability') or item.get('probability'))} | odds {dec(item.get('odds'))}")
    else:
        lines.append("No TOP5 picks passed Torq filters.")
    lines += ["", "🅱️ Torq B-Hand"]
    if bhand:
        for idx, item in enumerate(bhand[:5], 1):
            lines.append(f"{idx}. {short_name(item.get('pick'))} | odds {dec(item.get('odds'))} | edge +{dec(item.get('b_hand_edge_pp'))} pp | Torq {pct(item.get('torq_probability') or item.get('probability'))}")
    else:
        lines.append("No B-Hand value edges passed filters.")
    lines += ["", "Analytical model output only. No result is guaranteed."]
    return "\n".join(lines)


def send(message):
    if not BOT_TOKEN:
        raise RuntimeError("Missing Telegram bot token. Set TG_BOT_BTLKR or TELEGRAM_BOT_TOKEN.")
    if not CHAT_ID:
        raise RuntimeError("Missing Telegram chat id. Set TG_CHAT_ID or TELEGRAM_CHAT_ID.")
    response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True}, timeout=30)
    response.raise_for_status()


def main():
    if not FORCE_SEND and datetime.now(LOCAL_TZ).hour != 9:
        print("Not local 09:00 Europe/Bratislava, Telegram send skipped.")
        return
    message = build_message()
    print(message)
    send(message)


if __name__ == "__main__":
    main()
