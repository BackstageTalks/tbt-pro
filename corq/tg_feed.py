from __future__ import annotations

import argparse
import json
import os
import random
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
DEFAULT_TOP7_PATH = OUTPUTS / "latest_top7.json"
DEFAULT_ALL_PATH = OUTPUTS / "latest_all.json"
DEFAULT_MESSAGE_PATH = OUTPUTS / "telegram" / "latest_tg_message.txt"

HEADER = "AI Betting by BackstageTalks"
FOOTER = "ℹ️ Analytical preview only\n🧠 by BackstageTalks AI Engine"


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[tg_feed] failed to read {path}: {exc}", file=sys.stderr)
    return default


def json_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "top7", "all", "picks", "records", "data"):
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def fmt_odds(value: Any) -> str:
    num = as_float(value)
    if num is None or num <= 0:
        return "—"
    return f"{num:.2f}"


def fmt_pct(value: Any) -> str:
    num = as_float(value)
    if num is None:
        return "—"
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:.1f}%"


def pick_name(row: Dict[str, Any]) -> str:
    return str(
        row.get("pick")
        or row.get("cloq_pick")
        or row.get("player")
        or row.get("player1")
        or row.get("home")
        or ""
    ).strip()


def opponent_name(row: Dict[str, Any]) -> str:
    return str(
        row.get("opponent")
        or row.get("opp")
        or row.get("player2")
        or row.get("away")
        or ""
    ).strip()


def short_name(name: str) -> str:
    clean = " ".join(str(name or "").split()).strip()
    if not clean:
        return "—"
    parts = clean.split()
    if len(parts) == 1:
        return parts[0]
    # Surname-style compact display for TG: Lorenzo Musetti -> Musetti.
    return parts[-1]


def start_time(row: Dict[str, Any]) -> str:
    raw = (
        row.get("start_time_display")
        or row.get("match_time_display")
        or row.get("start_time")
        or row.get("start_time_utc")
        or row.get("match_time")
        or row.get("time")
        or ""
    )
    txt = str(raw).strip()
    if not txt:
        return "—"
    import re

    m = re.search(r"(\d{1,2}:\d{2})", txt)
    return m.group(1) if m else txt[:16]


def probability(row: Dict[str, Any]) -> Optional[float]:
    for key in (
        "corq_probability",
        "corq_estimated_win_probability",
        "win_probability",
        "estimated_win_probability",
        "probability",
        "cloq_probability",
    ):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return None


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in (
        "pick_odds",
        "cloq_pick_odds",
        "selected_odds",
        "odds_decimal",
        "decimal_odds",
        "odds",
    ):
        val = as_float(row.get(key))
        if val is not None and val > 1.0:
            return val
    return None


def snapshot_date(rows: List[Dict[str, Any]]) -> str:
    for row in rows:
        for key in ("snapshot_date", "date", "run_date", "match_date"):
            value = row.get(key)
            if value:
                txt = str(value)[:10]
                try:
                    dt = datetime.fromisoformat(txt)
                    return dt.strftime("%d.%m.%Y")
                except Exception:
                    pass
    return datetime.now().strftime("%d.%m.%Y")


def is_rejected(row: Dict[str, Any]) -> bool:
    if row.get("top7_publishable") is False or row.get("eligible_for_top7") is False:
        return True
    status = str(row.get("status") or row.get("match_status") or "").upper()
    if status in {"REJECTED", "CANCELLED", "CANCELED", "POSTPONED"}:
        return True
    flags: List[str] = []
    for key in ("reject_reasons", "top7_quality_reject_reasons", "risk_flags", "flags"):
        val = row.get(key)
        if isinstance(val, list):
            flags.extend(str(x).upper() for x in val if x)
        elif isinstance(val, str) and val:
            flags.append(val.upper())
    return any(flag.startswith("REJECT") for flag in flags)


def is_doubles(row: Dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("event_name", "tournament", "category", "match_type", "type", "competition")
    ).lower()
    return "double" in text or "doubles" in text


def valid_corq_row(row: Dict[str, Any]) -> bool:
    if is_rejected(row) or is_doubles(row):
        return False
    if not pick_name(row) or not opponent_name(row):
        return False
    if pick_odds(row) is None:
        return False
    if probability(row) is None:
        return False
    return True


def valid_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = [row for row in rows if valid_corq_row(row)]
    out.sort(key=lambda r: as_float(probability(r), 0.0) or 0.0, reverse=True)
    return out


def number_emoji(index: int) -> str:
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    return emojis[index - 1] if 1 <= index <= len(emojis) else f"{index}."


def format_row(row: Dict[str, Any], prefix: str) -> str:
    name = short_name(pick_name(row))
    return f"{prefix} {name} | {start_time(row)} | {fmt_pct(probability(row))} | {fmt_odds(pick_odds(row))}"


def build_top7_message(rows: List[Dict[str, Any]], limit: int = 7) -> str:
    rows = valid_rows(rows)[:limit]
    date_text = snapshot_date(rows)
    lines = [HEADER, "", "🎾 TOP7 | CorQ", f"📅 {date_text}", ""]
    if rows:
        lines.extend(format_row(row, number_emoji(idx)) for idx, row in enumerate(rows, 1))
    else:
        lines.append("No valid CorQ picks available today.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)


def build_free_message(rows: List[Dict[str, Any]]) -> str:
    rows = valid_rows(rows)
    date_text = snapshot_date(rows)
    lines = [HEADER, "", "🎾 FREE | CorQ", f"📅 {date_text}", ""]
    if rows:
        row = random.choice(rows)
        lines.append(format_row(row, "🆓"))
    else:
        lines.append("No valid CorQ free pick available today.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)


def send_telegram(message: str, bot_token: str, chat_id: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    print(f"[tg_feed] Telegram response: {body[:500]}")


def load_rows_for_mode(mode: str, top7_path: Path, all_path: Path) -> List[Dict[str, Any]]:
    top7 = json_rows(read_json(top7_path, []))
    if mode == "top7":
        return top7
    # FREE prefers CorQ TOP7, then falls back to ALL if TOP7 is empty.
    if top7:
        return top7
    return json_rows(read_json(all_path, []))


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram feed formatter/sender for CorQ")
    parser.add_argument("--mode", choices=("top7", "free"), default=os.getenv("TG_FEED_MODE", "top7"))
    parser.add_argument("--top7-path", default=os.getenv("TG_TOP7_PATH", str(DEFAULT_TOP7_PATH)))
    parser.add_argument("--all-path", default=os.getenv("TG_ALL_PATH", str(DEFAULT_ALL_PATH)))
    parser.add_argument("--output", default=os.getenv("TG_MESSAGE_OUTPUT", str(DEFAULT_MESSAGE_PATH)))
    parser.add_argument("--send", action="store_true", help="Send to Telegram using env bot token and chat id")
    parser.add_argument("--chat-id", default=None, help="Telegram chat id. Defaults by mode from env.")
    parser.add_argument("--bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN"))
    parser.add_argument("--limit", type=int, default=7)
    args = parser.parse_args()

    rows = load_rows_for_mode(args.mode, Path(args.top7_path), Path(args.all_path))
    if args.mode == "free":
        message = build_free_message(rows)
    else:
        message = build_top7_message(rows, limit=args.limit)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(message, encoding="utf-8")
    print(message)

    if args.send:
        chat_id = args.chat_id
        if not chat_id:
            if args.mode == "free":
                chat_id = os.getenv("TELEGRAM_FREE_CHAT_ID") or os.getenv("TG_FREE_CHAT_ID")
            else:
                chat_id = os.getenv("TELEGRAM_TOP7_CHAT_ID") or os.getenv("TG_TOP7_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        if not args.bot_token:
            raise SystemExit("Missing TELEGRAM_BOT_TOKEN/TG_BOT_TOKEN")
        if not chat_id:
            raise SystemExit("Missing Telegram chat id for mode")
        send_telegram(message, args.bot_token, chat_id)


if __name__ == "__main__":
    main()
