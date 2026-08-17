from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
DEFAULT_TOP7_PATH = OUTPUTS / "snapshots" / "latest_corq_top7_snapshot.json"
DEFAULT_CLOQ_PATH = OUTPUTS / "cloq" / "latest_cloq.json"
DEFAULT_ALL_PATH = OUTPUTS / "latest_all.json"
DEFAULT_MESSAGE_PATH = OUTPUTS / "telegram" / "latest_tg_message.txt"
DEFAULT_RESULTS_MESSAGE_PATH = OUTPUTS / "telegram" / "latest_tg_results_message.txt"
DEFAULT_CLOQ_RESULTS_MESSAGE_PATH = OUTPUTS / "telegram" / "latest_tg_cloq_results_message.txt"

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


def _first_text(row: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        txt = str(value).strip()
        if txt and txt.lower() not in {"none", "null", "nan", "—", "-"}:
            return txt
    return ""


def pick_name(row: Dict[str, Any]) -> str:
    # Support both old rows and newer CorQ/TOP7 snapshot exports.
    direct = _first_text(row, (
        "pick",
        "top7_pick",
        "corq_pick",
        "selected_pick",
        "selection",
        "selected_player",
        "predicted_winner",
        "winner_pick",
        "cloq_pick",
        "player",
        "player_name",
        "player1",
        "home",
    ))
    if direct:
        return direct
    snap = row.get("prediction_snapshot")
    if isinstance(snap, dict):
        for section in ("corq", "top7", "pick", "selection"):
            obj = snap.get(section)
            if isinstance(obj, dict):
                nested = _first_text(obj, ("pick", "player", "name", "selection", "predicted_winner"))
                if nested:
                    return nested
    return ""


def opponent_name(row: Dict[str, Any]) -> str:
    direct = _first_text(row, (
        "opponent",
        "opponent_name",
        "opp",
        "top7_opponent",
        "corq_opponent",
        "other_player",
        "player2",
        "away",
    ))
    if direct:
        return direct
    snap = row.get("prediction_snapshot")
    if isinstance(snap, dict):
        for section in ("corq", "top7", "opponent"):
            obj = snap.get(section)
            if isinstance(obj, dict):
                nested = _first_text(obj, ("opponent", "opponent_name", "opp", "player2", "away", "name"))
                if nested:
                    return nested
    # Do not block TOP7 Telegram if opponent is missing in a compact snapshot.
    return "TBD"

def short_name(name: str) -> str:
    clean = " ".join(str(name or "").split()).strip()
    if not clean:
        return "—"
    parts = clean.split()
    if len(parts) == 1:
        return parts[0]
    # Surname-style compact display for TG: Lorenzo Musetti -> Musetti.
    return parts[-1]


# ---------------------------------------------------------------------------
# Telegram display-name disambiguation
# ---------------------------------------------------------------------------
# Display names stay compact by default (surname only), but if one TG message
# contains multiple picks with the same surname, include initials. Examples:
#   Francisco Cerundolo -> F. Cerundolo
#   Juan Manuel Cerundolo -> J.M. Cerundolo
# If initials are still ambiguous, fall back to the full player name.

def _tg_display_norm(value: Any) -> str:
    import re
    import unicodedata
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _tg_name_parts(name: Any) -> List[str]:
    return [part for part in str(name or "").strip().split() if part]


def _tg_surname(name: Any) -> str:
    parts = _tg_name_parts(name)
    return parts[-1] if parts else ""


def _tg_initials(name: Any) -> str:
    parts = _tg_name_parts(name)
    if len(parts) <= 1:
        return ""
    return "".join(f"{part[0].upper()}." for part in parts[:-1] if part)


def display_name_map(rows: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    full_names: List[str] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = pick_name(row)
        if name and name not in full_names:
            full_names.append(name)

    surname_counts: Dict[str, int] = {}
    for name in full_names:
        key = _tg_display_norm(_tg_surname(name))
        if key:
            surname_counts[key] = surname_counts.get(key, 0) + 1

    proposed: Dict[str, str] = {}
    display_counts: Dict[str, int] = {}
    for name in full_names:
        surname = _tg_surname(name)
        surname_key = _tg_display_norm(surname)
        if surname and surname_counts.get(surname_key, 0) > 1:
            initials = _tg_initials(name)
            display = f"{initials} {surname}".strip() if initials else str(name).strip()
        else:
            display = short_name(name)
        proposed[name] = display
        display_key = _tg_display_norm(display)
        display_counts[display_key] = display_counts.get(display_key, 0) + 1

    # If initials still collide, show full names for that collision group.
    out: Dict[str, str] = {}
    for name, display in proposed.items():
        if display_counts.get(_tg_display_norm(display), 0) > 1:
            out[name] = str(name).strip() or "—"
        else:
            out[name] = display or "—"
    return out


def display_pick_name(row: Dict[str, Any], names: Optional[Dict[str, str]] = None) -> str:
    full = pick_name(row)
    if names and full in names:
        return names[full]
    return short_name(full)


def local_tz():
    """Telegram feed timezone.

    Default to Europe/Bratislava so summer/winter time is handled correctly.
    TG_FEED_TIME_OFFSET_HOURS remains as a fallback override for simple fixed
    offsets.
    """
    tz_name = os.getenv("TG_FEED_TIMEZONE") or os.getenv("TZ") or "Europe/Bratislava"
    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass
    offset = as_float(os.getenv("TG_FEED_TIME_OFFSET_HOURS"), 2.0)
    return timezone(timedelta(hours=offset or 0.0))


def row_date_text(row: Dict[str, Any]) -> Optional[str]:
    for key in ("betting_day", "snapshot_date", "snapshot_functional_day", "functional_day", "date", "run_date", "match_date", "start_date"):
        value = row.get(key)
        if value:
            txt = str(value).strip()
            if len(txt) >= 10:
                return txt[:10]
    return None


def parse_datetime_value(value: Any, tz, assume_utc: bool = False) -> Optional[datetime]:
    txt = str(value or "").strip()
    if not txt:
        return None
    raw = txt.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc if assume_utc else tz)
        return dt.astimezone(tz)
    except Exception:
        pass
    return None


def match_start_datetime(row: Dict[str, Any], now: Optional[datetime] = None) -> Optional[datetime]:
    tz = local_tz()
    now = now or datetime.now(tz)

    # Prefer full datetime fields, especially UTC fields if available.
    for key in (
        "start_time_utc",
        "match_time_utc",
        "start_time",
        "match_time",
        "start_time_display",
        "match_time_display",
    ):
        dt = parse_datetime_value(row.get(key), tz, assume_utc=key.endswith("_utc"))
        if dt is not None:
            return dt

    # Fallback for fields that contain only HH:MM.
    time_txt = start_time(row)
    if time_txt == "—":
        return None
    import re

    m = re.search(r"(\d{1,2}):(\d{2})", time_txt)
    if not m:
        return None
    date_txt = row_date_text(row) or now.date().isoformat()
    try:
        base = datetime.fromisoformat(date_txt[:10]).date()
        hour = int(m.group(1))
        minute = int(m.group(2))
        # Betting day is 06:00 -> 06:00 Europe/Bratislava. If a snapshot row
        # only has HH:MM and the time is before 06:00, assign it to the next
        # calendar date inside the betting day. Example: betting_day 2026-08-05
        # and 03:00 means 2026-08-06 03:00 local.
        if (row.get("betting_day") or row.get("snapshot_date")) and hour < 6:
            base = base + timedelta(days=1)
        return datetime(base.year, base.month, base.day, hour, minute, tzinfo=tz)
    except Exception:
        return None


def is_upcoming_match(row: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    tz = local_tz()
    now = now or datetime.now(tz)
    start_dt = match_start_datetime(row, now=now)
    if start_dt is None:
        return False
    grace = as_float(os.getenv("TG_FEED_PAST_GRACE_MINUTES"), 0.0) or 0.0
    return start_dt >= now - timedelta(minutes=grace)

def start_time(row: Dict[str, Any]) -> str:
    tz = local_tz()
    # Prefer full datetime fields and always convert UTC fields to TG local time.
    for key in (
        "start_time_utc",
        "match_time_utc",
        "scheduled_time_utc",
        "event_time_utc",
        "start_at_utc",
        "start_time",
        "match_time",
        "scheduled_time",
        "event_time",
        "start_at",
        "start_time_display",
        "match_time_display",
        "time_local",
        "local_time",
    ):
        dt = parse_datetime_value(row.get(key), tz, assume_utc=key.endswith("_utc"))
        if dt is not None:
            return dt.strftime("%H:%M")

    raw = row.get("time") or row.get("match_time_label") or row.get("time_label") or ""
    txt = str(raw).strip()
    if not txt:
        return "—"
    import re
    m = re.search(r"(\d{1,2}:\d{2})", txt)
    return m.group(1) if m else txt[:16]

def probability(row: Dict[str, Any]) -> Optional[float]:
    for key in (
        "top7_corq_probability",
        "top7_pick_probability",
        "corq_final",
        "corq_final_probability",
        "corq_probability",
        "corq_estimated_win_probability",
        "pick_probability",
        "predicted_probability",
        "win_probability",
        "estimated_win_probability",
        "probability",
        "cloq_probability",
    ):
        val = as_float(row.get(key))
        if val is not None:
            return val / 100.0 if val > 1.0 else val

    snap = row.get("prediction_snapshot")
    if isinstance(snap, dict):
        for section in ("corq", "top7", "model"):
            obj = snap.get(section)
            if isinstance(obj, dict):
                for key in ("probability", "pick_probability", "calibrated_probability", "raw_model_probability", "win_probability"):
                    val = as_float(obj.get(key))
                    if val is not None:
                        return val / 100.0 if val > 1.0 else val
    return None


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in (
        "top7_pick_odds",
        "pick_odds",
        "corq_pick_odds",
        "selected_pick_odds",
        "selected_odds",
        "market_odds",
        "closing_odds",
        "current_odds",
        "decimal_odds",
        "odds_decimal",
        "cloq_pick_odds",
        "odds",
    ):
        val = as_float(row.get(key))
        if val is not None and val > 1.0:
            return val
    snap = row.get("prediction_snapshot")
    if isinstance(snap, dict):
        for section in ("corq", "top7", "market"):
            obj = snap.get(section)
            if isinstance(obj, dict):
                for key in ("pick_odds", "odds", "decimal_odds", "selected_odds"):
                    val = as_float(obj.get(key))
                    if val is not None and val > 1.0:
                        return val
    return None


def snapshot_date(rows: List[Dict[str, Any]]) -> str:
    for row in rows:
        for key in ("betting_day", "snapshot_date", "snapshot_functional_day", "functional_day", "date", "run_date", "match_date"):
            value = row.get(key)
            if value:
                txt = str(value)[:10]
                try:
                    dt = datetime.fromisoformat(txt)
                    return dt.strftime("%d.%m.%Y")
                except Exception:
                    pass
    return datetime.now(local_tz()).strftime("%d.%m.%Y")


def today_iso() -> str:
    return datetime.now(local_tz()).date().isoformat()


def row_day_iso(row: Dict[str, Any]) -> str:
    for key in ("betting_day", "snapshot_date", "snapshot_functional_day", "functional_day", "date", "run_date", "match_date", "top7_match_date_local"):
        value = row.get(key)
        if value:
            txt = str(value).strip()[:10]
            try:
                datetime.fromisoformat(txt)
                return txt
            except Exception:
                pass
    dt = match_start_datetime(row)
    if dt is not None:
        return dt.astimezone(local_tz()).date().isoformat()
    return ""


def rows_look_current(rows: List[Dict[str, Any]]) -> bool:
    if not rows:
        return False
    today = today_iso()
    days = [row_day_iso(r) for r in rows if row_day_iso(r)]
    return bool(days) and any(d == today for d in days)


def rows_have_sendable_top7(rows: List[Dict[str, Any]]) -> bool:
    return bool(valid_rows(rows, upcoming_only=False))


def is_top7_like_row(row: Dict[str, Any]) -> bool:
    if row.get("top7_publishable") is True or row.get("eligible_for_top7") is True:
        return True
    if _rank_value(row) is not None:
        return True
    source = str(row.get("model") or row.get("source_snapshot") or row.get("snapshot_type") or "").lower()
    return "corq" in source or "top7" in source


def top7_like_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    subset = [r for r in rows if is_top7_like_row(r)]
    return subset if subset else []


def is_rejected(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("match_status") or "").upper()
    if status in {"REJECTED", "CANCELLED", "CANCELED", "POSTPONED"}:
        return True

    # Important: compact TOP7 snapshots can carry legacy boolean fields that are
    # False even though the row was already written into latest_top7/snapshot.
    # Do not let these legacy booleans invalidate the Telegram feed when the row
    # has a rank or TOP7-like source. Hard reject statuses/reasons still apply.
    if not is_top7_like_row(row):
        if row.get("top7_publishable") is False or row.get("eligible_for_top7") is False:
            return True

    flags: List[str] = []
    for key in ("reject_reasons", "top7_quality_reject_reasons", "risk_flags", "flags"):
        val = row.get(key)
        if isinstance(val, list):
            flags.extend(str(x).upper() for x in val if x)
        elif isinstance(val, str) and val:
            flags.append(val.upper())
    return any(flag.startswith("REJECT_FATAL") or flag in {"REJECT", "REJECTED"} for flag in flags)


def is_doubles(row: Dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("event_name", "tournament", "category", "match_type", "type", "competition")
    ).lower()
    return "double" in text or "doubles" in text


def invalid_corq_reason(row: Dict[str, Any], upcoming_only: bool = True) -> str:
    if is_rejected(row):
        return "rejected"
    if is_doubles(row):
        return "doubles"
    if not pick_name(row):
        return "missing_pick"
    # Opponent is allowed to be TBD for compact TOP7 snapshots.
    if start_time(row) == "—":
        return "missing_time"
    if pick_odds(row) is None:
        return "missing_odds"
    if probability(row) is None:
        return "missing_probability"
    if upcoming_only and not is_upcoming_match(row):
        return "not_upcoming"
    return ""


def valid_corq_row(row: Dict[str, Any], upcoming_only: bool = True) -> bool:
    return invalid_corq_reason(row, upcoming_only=upcoming_only) == ""


def _rank_value(row: Dict[str, Any]) -> Optional[float]:
    for key in ("top7_rank", "corq_rank", "snapshot_rank", "rank"):
        val = as_float(row.get(key))
        if val is not None and val > 0:
            return val
    return None


def valid_rows(rows: Iterable[Dict[str, Any]], upcoming_only: bool = True) -> List[Dict[str, Any]]:
    out = [row for row in rows if valid_corq_row(row, upcoming_only=upcoming_only)]
    if any(_rank_value(r) is not None for r in out):
        out.sort(key=lambda r: (_rank_value(r) or 9999, -(as_float(probability(r), 0.0) or 0.0)))
    else:
        out.sort(key=lambda r: as_float(probability(r), 0.0) or 0.0, reverse=True)
    return out


def number_emoji(index: int) -> str:
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    return emojis[index - 1] if 1 <= index <= len(emojis) else f"{index}."


def format_row(row: Dict[str, Any], prefix: str, names: Optional[Dict[str, str]] = None) -> str:
    name = display_pick_name(row, names)
    return f"{prefix} {name} | {start_time(row)} | {fmt_pct(probability(row))} | {fmt_odds(pick_odds(row))}"


def build_top7_message(rows: List[Dict[str, Any]], limit: int = 7, upcoming_only: bool = True) -> str:
    # TOP7 is an immutable daily snapshot. Do not drop already-started rows.
    rows = valid_rows(rows, upcoming_only=False)[:limit]
    date_text = snapshot_date(rows)
    lines = [HEADER, "", "🎾 TOP Picks | CorQ", f"📅 {date_text}", ""]
    if rows:
        names = display_name_map(rows)
        lines.extend(format_row(row, number_emoji(idx), names) for idx, row in enumerate(rows, 1))
    else:
        lines.append("No valid upcoming CorQ picks available today.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)


def build_free_message(rows: List[Dict[str, Any]], upcoming_only: bool = True) -> str:
    rows = valid_rows(rows, upcoming_only=upcoming_only)
    date_text = snapshot_date(rows)
    lines = [HEADER, "", "🎾 FREE | CorQ", f"📅 {date_text}", ""]
    if rows:
        names = display_name_map(rows)
        row = rows[0]
        lines.append(format_row(row, "🆓", names))
    else:
        lines.append("No valid upcoming CorQ free pick available today.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)

def build_cloq_message(rows: List[Dict[str, Any]], limit: int = 10, upcoming_only: bool = True) -> str:
    rows = drop_cloq_corq_overlaps(rows)
    rows = valid_rows(rows, upcoming_only=upcoming_only)[:limit]
    date_text = snapshot_date(rows)
    lines = [HEADER, "", "🎾 TOP Picks | CloQ", f"📅 {date_text}", ""]
    if rows:
        names = display_name_map(rows)
        lines.extend(format_row(row, number_emoji(idx), names) for idx, row in enumerate(rows, 1))
    else:
        lines.append("No valid upcoming CloQ picks available today.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)


def build_cloq_free_message(rows: List[Dict[str, Any]], upcoming_only: bool = True) -> str:
    rows = valid_rows(drop_cloq_corq_overlaps(rows), upcoming_only=upcoming_only)
    date_text = snapshot_date(rows)
    lines = [HEADER, "", "🎾 FREE | CloQ", f"📅 {date_text}", ""]
    if rows:
        names = display_name_map(rows)
        lines.append(format_row(rows[0], "🆓", names))
    else:
        lines.append("No valid upcoming CloQ free pick available today.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)


# ============================================================
# CloQ / CorQ match-overlap safety
# ============================================================
def _norm_match_name(value: Any) -> str:
    import re
    txt = str(value or "").strip().lower()
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return " ".join(txt.split())

def _row_event_id(row: Dict[str, Any]) -> str:
    for key in ("event_id", "match_id", "fixture_id", "api_event_id", "id", "top7_event_id", "cloq_event_id"):
        value = row.get(key)
        if value not in (None, "", "—", "-"):
            return str(value).strip()
    return ""

def tg_match_identity(row: Dict[str, Any]) -> str:
    event_id = _row_event_id(row)
    if event_id:
        return "event:" + event_id
    names = sorted([_norm_match_name(pick_name(row)), _norm_match_name(opponent_name(row))])
    names = [n for n in names if n and n != "tbd"]
    day = row_day_iso(row)
    dt = match_start_datetime(row)
    time_part = dt.strftime("%H:%M") if dt is not None else start_time(row)
    if len(names) >= 2:
        return "names:" + "|".join(names) + "|" + str(day or "") + "|" + str(time_part or "")
    return ""

def load_corq_overlap_match_keys() -> set[str]:
    keys: set[str] = set()
    for path in (
        DEFAULT_TOP7_PATH,
        OUTPUTS / "latest_top7.json",
        OUTPUTS / "snapshots" / "latest_corq_top7_snapshot.json",
    ):
        rows = json_rows(read_json(path, []))
        for row in rows:
            key = tg_match_identity(row)
            if key:
                keys.add(key)
    return keys

def drop_cloq_corq_overlaps(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keys = load_corq_overlap_match_keys()
    if not keys or not rows:
        return rows
    out: List[Dict[str, Any]] = []
    skipped = 0
    for row in rows:
        key = tg_match_identity(row)
        if key and key in keys:
            skipped += 1
            continue
        out.append(row)
    if skipped:
        print(f"[tg_feed] CloQ overlap safety skipped {skipped} row(s) already covered by CorQ")
    return out

def result_status(row: Dict[str, Any]) -> str:
    for key in ("settlement_status", "result_status", "status", "outcome"):
        txt = str(row.get(key) or "").strip().lower()
        if txt in {"won", "win", "w"}:
            return "won"
        if txt in {"lost", "loss", "l"}:
            return "lost"
        if txt in {"void", "push", "cancelled", "canceled"}:
            return "void"
        if txt in {"pending", "notstarted", "inprogress", "live"}:
            return "pending"
    if row.get("won") is True:
        return "won"
    if row.get("lost") is True:
        return "lost"
    return "pending"

def result_units(row: Dict[str, Any]) -> float:
    for key in ("units", "profit_units", "pnl_units", "result_units", "settlement_units"):
        val = as_float(row.get(key))
        if val is not None:
            return float(val)
    st = result_status(row)
    odds = pick_odds(row) or 0.0
    if st == "won" and odds > 1.0:
        return odds - 1.0
    if st == "lost":
        return -1.0
    return 0.0

def build_results_summary_message(rows: List[Dict[str, Any]], model_label: str) -> str:
    rows = rows or []
    date_text = snapshot_date(rows)
    counts = {"won": 0, "lost": 0, "void": 0, "pending": 0}
    units = 0.0
    for row in rows:
        st = result_status(row)
        counts[st if st in counts else "pending"] += 1
        units += result_units(row)
    decided = counts["won"] + counts["lost"]
    win_rate = (counts["won"] / decided * 100.0) if decided else 0.0
    lines = [HEADER, "", f"📊 Results | {model_label}", f"📅 {date_text}", ""]
    if rows:
        lines.append(f"✅ W {counts['won']} | ❌ L {counts['lost']} | ⏳ P {counts['pending']} | ↩️ V {counts['void']}")
        lines.append(f"📈 Win {win_rate:.1f}% | Units {units:+.2f}u")
        lines.append("")
        for idx, row in enumerate(rows[:10], 1):
            st = result_status(row)
            icon = {"won": "✅", "lost": "❌", "void": "↩️", "pending": "⏳"}.get(st, "⏳")
            lines.append(f"{number_emoji(idx)} {display_pick_name(row, display_name_map(rows))} | {icon} | {fmt_odds(pick_odds(row))} | {result_units(row):+.2f}u")
    else:
        lines.append(f"No {model_label} results summary available yet.")
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


def _describe_rows(label: str, rows: List[Dict[str, Any]]) -> str:
    reason_counts = {}
    for row in rows or []:
        reason = invalid_corq_reason(row, upcoming_only=False) or "valid"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    reasons = ",".join(f"{k}:{v}" for k, v in sorted(reason_counts.items())) or "none"
    return f"{label}: raw={len(rows)} valid={len(valid_rows(rows, upcoming_only=False))} current={rows_look_current(rows)} reasons={reasons}"


def load_rows_for_mode(mode: str, top7_path: Path, all_path: Path) -> List[Dict[str, Any]]:
    """Load rows for Telegram feeds with stale/empty snapshot protection.

    TOP7 should normally use the immutable daily snapshot, but if the morning
    snapshot is empty, stale, or not parseable by the formatter, fall back to
    outputs/latest_top7.json. If that is also empty, use CorQ-like rows from
    outputs/latest_all.json as a last resort so the feed does not send an empty
    daily CorQ message when the web page already has current picks.
    """
    sources: List[tuple[str, List[Dict[str, Any]]]] = []

    snapshot_rows = json_rows(read_json(top7_path, []))
    sources.append((str(top7_path), snapshot_rows))

    latest_top7_path = OUTPUTS / "latest_top7.json"
    if top7_path != latest_top7_path:
        sources.append((str(latest_top7_path), json_rows(read_json(latest_top7_path, []))))

    all_rows_raw = json_rows(read_json(all_path, []))
    all_top7_rows = top7_like_rows(all_rows_raw)

    if mode == "top7":
        for label, rows in sources:
            print(f"[tg_feed] TOP7 source check | {_describe_rows(label, rows)}")
            if rows_have_sendable_top7(rows) and rows_look_current(rows):
                print(f"[tg_feed] TOP7 source selected: {label}")
                return rows

        # If there are valid rows but no date metadata, prefer latest_top7 over
        # sending an empty message. This avoids blocking the feed on old exports
        # missing snapshot_date/betting_day.
        for label, rows in sources:
            if rows_have_sendable_top7(rows):
                print(f"[tg_feed] TOP7 source selected without current-date metadata: {label}")
                return rows

        print(f"[tg_feed] TOP7 source check | {_describe_rows(str(all_path) + ' filtered corq/top7', all_top7_rows)}")
        if rows_have_sendable_top7(all_top7_rows):
            print(f"[tg_feed] TOP7 source selected: {all_path} filtered corq/top7")
            return all_top7_rows

        print("[tg_feed] TOP7 source selected: empty, no valid current rows found")
        return []

    # FREE prefers the same current TOP7 snapshot, then latest_top7, then ALL.
    if mode == "free":
        for label, rows in sources:
            if rows_have_sendable_top7(rows) and rows_look_current(rows):
                print(f"[tg_feed] FREE source selected: {label}")
                return rows
        if all_top7_rows:
            print(f"[tg_feed] FREE source selected: {all_path} filtered corq/top7")
            return all_top7_rows
        return all_rows_raw

    return all_rows_raw


def tg_match_identity(row: Dict[str, Any]) -> str:
    for key in ("match_key", "event_key", "match_id", "event_id", "fixture_id", "api_match_id", "id"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    p1 = pick_name(row).strip().lower()
    p2 = opponent_name(row).strip().lower()
    start = str(row.get("start_time_utc") or row.get("match_time_utc") or row.get("start_time") or row.get("match_time") or "").strip().lower()
    tournament = str(row.get("tournament") or row.get("competition") or row.get("league") or "").strip().lower()
    names = "::".join(sorted([p1, p2]))
    return f"fallback::{names}::{start}::{tournament}"


def current_corq_match_keys_for_tg(top7_path: Optional[Path] = None) -> set[str]:
    candidates = []
    if top7_path is not None:
        candidates.append(top7_path)
    candidates.extend([
        OUTPUTS / "latest_top7.json",
        OUTPUTS / "snapshots" / "latest_corq_top7_snapshot.json",
    ])
    seen_paths: set[str] = set()
    for path in candidates:
        path_key = str(path)
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)
        rows = json_rows(read_json(path, []))
        if not rows:
            continue
        keys = {tg_match_identity(row) for row in rows if isinstance(row, dict) and tg_match_identity(row)}
        if keys:
            return keys
    return set()


def filter_cloq_corq_overlap_for_tg(rows: List[Dict[str, Any]], corq_match_keys: Optional[set[str]] = None) -> List[Dict[str, Any]]:
    corq_match_keys = corq_match_keys or current_corq_match_keys_for_tg()
    if not corq_match_keys:
        return rows
    out: List[Dict[str, Any]] = []
    skipped = 0
    for row in rows or []:
        key = tg_match_identity(row)
        if key in corq_match_keys:
            skipped += 1
            continue
        out.append(row)
    if skipped:
        print(f"[tg_feed] CloQ duplicate guard skipped {skipped} CorQ-overlap matches")
    return out


def load_cloq_rows(cloq_path: Path, all_path: Path) -> List[Dict[str, Any]]:
    sources: List[tuple[str, List[Dict[str, Any]]]] = []
    sources.append((str(cloq_path), json_rows(read_json(cloq_path, []))))
    latest_flat = OUTPUTS / "latest_cloq.json"
    if cloq_path != latest_flat:
        sources.append((str(latest_flat), json_rows(read_json(latest_flat, []))))
    latest_nested = OUTPUTS / "cloq" / "latest_cloq.json"
    if cloq_path != latest_nested and latest_nested != latest_flat:
        sources.append((str(latest_nested), json_rows(read_json(latest_nested, []))))
    corq_keys = current_corq_match_keys_for_tg()
    for label, rows in sources:
        rows = filter_cloq_corq_overlap_for_tg(rows, corq_match_keys=corq_keys)
        print(f"[tg_feed] CloQ source check | {_describe_rows(label, rows)}")
        if valid_rows(rows, upcoming_only=False):
            print(f"[tg_feed] CloQ source selected: {label}")
            return drop_cloq_corq_overlaps(rows)
    all_rows = json_rows(read_json(all_path, []))
    fallback = [r for r in all_rows if str(r.get("cloq_passed") or r.get("is_cloq") or "").lower() in {"1", "true", "yes"}]
    fallback = filter_cloq_corq_overlap_for_tg(fallback, corq_match_keys=corq_keys)
    if fallback:
        print(f"[tg_feed] CloQ source selected: {all_path} filtered cloq")
        return drop_cloq_corq_overlaps(fallback)
    print("[tg_feed] CloQ source selected: empty, no valid rows found")
    return []


# ============================================================
# TG safety + results settlement override V10
# ============================================================
# Pick feeds keep a hard Telegram floor. Results feeds are date-aware and can
# rebuild from JSON rows if the pre-generated message is missing or only a
# placeholder. This fixes CorQ/CloQ result messages that previously said
# "No previous snapshot rows found" despite rows existing in results JSON.
TG_MIN_PICK_PROBABILITY = float(os.getenv("TG_MIN_PICK_PROBABILITY", "0.50") or "0.50")


def probability_below_tg_floor(row: Dict[str, Any]) -> bool:
    prob = probability(row)
    return bool(prob is None or prob < TG_MIN_PICK_PROBABILITY)


_ORIGINAL_INVALID_CORQ_REASON_V10 = invalid_corq_reason


def invalid_corq_reason(row: Dict[str, Any], upcoming_only: bool = True) -> str:
    reason = _ORIGINAL_INVALID_CORQ_REASON_V10(row, upcoming_only=upcoming_only)
    if reason:
        return reason
    if probability_below_tg_floor(row):
        prob = probability(row)
        return "probability_below_50" if prob is not None else "missing_probability"
    return ""


def completed_betting_day_iso(tz_name: str = "Europe/Bratislava") -> str:
    tz = local_tz()
    now_local = datetime.now(tz)
    current_betting_day = now_local.date() - timedelta(days=1) if now_local.hour < 6 else now_local.date()
    return (current_betting_day - timedelta(days=1)).isoformat()


def _row_result_day(row: Dict[str, Any]) -> str:
    for key in ("betting_day", "snapshot_date", "snapshot_functional_day", "functional_day", "date", "run_date", "match_date"):
        value = row.get(key)
        if value:
            txt = str(value).strip()[:10]
            try:
                datetime.fromisoformat(txt)
                return txt
            except Exception:
                pass
    dt = match_start_datetime(row)
    if dt is not None:
        return dt.astimezone(local_tz()).date().isoformat()
    return ""


def _model_label(model: str) -> str:
    return "CloQ" if str(model).lower() == "cloq" else "CorQ"


def result_status(row: Dict[str, Any]) -> str:
    for key in (
        "settlement_status", "result_status", "pick_result", "final_result",
        "status", "outcome", "settlement", "result", "winner_status",
    ):
        txt = str(row.get(key) or "").strip().lower()
        if txt in {"won", "win", "w", "hit", "winner", "correct", "green"}:
            return "won"
        if txt in {"lost", "loss", "l", "miss", "loser", "incorrect", "red"}:
            return "lost"
        if txt in {"void", "push", "cancelled", "canceled", "walkover", "retired"}:
            return "void"
        if txt in {"pending", "notstarted", "not_started", "inprogress", "live", "open"}:
            return "pending"
    if row.get("won") is True:
        return "won"
    if row.get("lost") is True:
        return "lost"
    return "pending"


def result_units(row: Dict[str, Any]) -> float:
    st = result_status(row)
    explicit = None
    for key in ("units", "profit_units", "pnl_units", "result_units", "settlement_units"):
        val = as_float(row.get(key))
        if val is not None:
            explicit = float(val)
            break
    odds = pick_odds(row) or 0.0
    if st == "won" and odds > 1.0:
        computed = odds - 1.0
        return computed if explicit in (None, 0.0) else explicit
    if st == "lost":
        return -1.0 if explicit in (None, 0.0) else explicit
    if st == "void":
        return 0.0
    return explicit if explicit is not None else 0.0


def _result_row_model_matches(row: Dict[str, Any], model: str) -> bool:
    model = str(model or "corq").lower()
    row_model = str(row.get("model") or "").lower()
    source = str(row.get("snapshot_source") or row.get("source_filter") or row.get("snapshot_type") or "").upper()
    if model == "cloq":
        return row_model == "cloq" or source in {"CLOQ", "CLOQ_DAILY", "DAILY_CLOQ_SNAPSHOT"} or "CLOQ" in source
    return row_model == "corq" or source in {"CORQ", "CORQ_DAILY", "CORQ_TOP7"} or "CORQ" in source


def filter_result_rows(rows: List[Dict[str, Any]], model: str, day: Optional[str] = None) -> List[Dict[str, Any]]:
    target = str(day or "").strip()[:10]
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if not _result_row_model_matches(row, model):
            continue
        if target and _row_result_day(row) != target:
            continue
        out.append(row)
    out.sort(key=lambda r: (as_float(r.get("snapshot_rank") or r.get("top7_rank") or r.get("cloq_rank") or r.get("rank"), 9999) or 9999, start_time(r), pick_name(r)))
    return out


def build_results_summary_message(rows: List[Dict[str, Any]], model_label: str, day: Optional[str] = None) -> str:
    model = str(model_label or "CorQ").lower()
    label = _model_label(model)
    rows = filter_result_rows(rows or [], model, day=day)
    date_text = ""
    if day:
        try:
            date_text = datetime.fromisoformat(str(day)[:10]).strftime("%d.%m.%y")
        except Exception:
            date_text = str(day)[:10]
    else:
        date_text = snapshot_date(rows)
    counts = {"won": 0, "lost": 0, "void": 0, "pending": 0}
    units = 0.0
    for row in rows:
        st = result_status(row)
        counts[st if st in counts else "pending"] += 1
        units += result_units(row)
    decided = counts["won"] + counts["lost"]
    roi = (units / decided) if decided else None
    roi_txt = "ROI —" if roi is None else f"ROI {roi * 100:+.1f}%"
    lines = [HEADER, "", f"📊 Results | {label}", f"📅 {date_text}", ""]
    if rows:
        names = display_name_map(rows)
        for idx, row in enumerate(rows[:10], 1):
            st = result_status(row)
            icon = {"won": "✅", "lost": "❌", "void": "➖", "pending": "⏳"}.get(st, "⏳")
            unit_txt = "Pending" if st == "pending" else f"{result_units(row):+.2f}u"
            lines.append(f"{number_emoji(idx)} {icon} {display_pick_name(row, names)} | {start_time(row)} | {fmt_odds(pick_odds(row))} | {unit_txt}")
        lines.extend([
            "",
            f"✅{counts['won']} ❌{counts['lost']} ➖{counts['void']} ⏳{counts['pending']} | {units:+.2f}u | {roi_txt}",
        ])
    else:
        lines.append(f"No previous {label} snapshot rows found.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)


def _display_day_to_iso(value: str) -> str:
    txt = str(value or "").strip()
    if not txt:
        return ""
    # Supported TG headers include dd.mm.yy, dd.mm.yyyy and yyyy-mm-dd.
    try:
        if len(txt) >= 10 and txt[4] == "-" and txt[7] == "-":
            datetime.fromisoformat(txt[:10])
            return txt[:10]
    except Exception:
        pass
    import re
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})", txt)
    if not m:
        return ""
    dd = int(m.group(1))
    mm = int(m.group(2))
    yy = int(m.group(3))
    if yy < 100:
        yy += 2000
    try:
        return datetime(yy, mm, dd).date().isoformat()
    except Exception:
        return ""

def _extract_results_message_day(message: str) -> str:
    txt = str(message or "")
    if not txt.strip():
        return ""
    # Prefer the explicit RESULTS header line, but accept any first date in the message.
    for line in txt.splitlines()[:8]:
        upper = line.upper()
        if "RESULT" in upper or "📅" in line:
            day = _display_day_to_iso(line)
            if day:
                return day
    return _display_day_to_iso(txt[:250])

def _results_message_needs_rebuild(message: str, model_label: str, target_day: Optional[str] = None) -> bool:
    txt = str(message or "").strip()
    if not txt:
        return True
    low = txt.lower()
    if "no previous" in low or "snapshot rows found" in low or "summary available yet" in low:
        return True
    target = str(target_day or "").strip()[:10]
    if target:
        try:
            datetime.fromisoformat(target)
            message_day = _extract_results_message_day(txt)
            if message_day and message_day != target:
                print(f"[tg_feed] stale {model_label} results message detected: message_day={message_day} target_day={target}; rebuilding from JSON rows")
                return True
            if not message_day:
                print(f"[tg_feed] {model_label} results message has no parseable day; rebuilding from JSON rows")
                return True
        except Exception:
            pass
    if os.getenv("TG_RESULTS_FORCE_REBUILD", "0").lower() in {"1", "true", "yes", "y"}:
        return True
    if str(model_label).lower() == "cloq" and "+0.00u" in txt and "❌" not in txt and "✅" not in txt:
        return True
    return False


def _load_result_rows(model: str) -> List[Dict[str, Any]]:
    model = str(model or "corq").lower()
    if model == "cloq":
        candidates = [
            OUTPUTS / "results" / "latest_results_cloq.json",
            OUTPUTS / "results" / "latest_cloq_results.json",
            OUTPUTS / "latest_results_cloq.json",
        ]
    else:
        candidates = [
            OUTPUTS / "results" / "latest_results_corq.json",
            OUTPUTS / "results" / "latest_corq_results.json",
            OUTPUTS / "latest_results_corq.json",
        ]
    for path in candidates:
        rows = json_rows(read_json(path, []))
        if rows:
            print(f"[tg_feed] {model.upper()} results rows selected: {path} raw={len(rows)}")
            return rows
    print(f"[tg_feed] {model.upper()} results rows selected: empty")
    return []



# ============================================================
# Results TG completeness override V11
# ============================================================
# Problem fixed:
# Existing results messages were built only from settled/latest_results rows.
# If the settlement ledger skipped a pick, especially around overlap/model
# de-duplication or still-pending settlement, Telegram showed fewer rows than
# the original daily snapshot. Results feeds must display the whole snapshot
# and mark rows without settlement as Pending.

TG_RESULTS_COMPLETENESS_MODEL_VERSION = "TG_RESULTS_COMPLETENESS_V11"


def _tg_norm_text(value: Any) -> str:
    import re
    txt = str(value or "").strip().lower()
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    return " ".join(txt.split())


def _tg_event_id(row: Dict[str, Any]) -> str:
    for key in ("event_id", "match_id", "id", "fixture_id", "api_match_id", "custom_id", "customId"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for key in ("id", "customId"):
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _tg_side_identity(row: Dict[str, Any]) -> str:
    existing = str(row.get("side_identity") or "").strip()
    if existing:
        return existing.lower()
    event_id = _tg_event_id(row)
    pick = _tg_norm_text(pick_name(row))
    if event_id and pick:
        return f"id:{event_id}|pick:{pick}"
    match_key = str(row.get("match_identity") or row.get("match_key") or "").strip().lower()
    if match_key and pick:
        return f"{match_key}|pick:{pick}"
    p1 = _tg_norm_text(row.get("player1") or row.get("home") or row.get("home_player") or "")
    p2 = _tg_norm_text(row.get("player2") or row.get("away") or row.get("away_player") or opponent_name(row))
    start = str(row.get("start_time_utc") or row.get("match_time_utc") or row.get("start_time") or row.get("match_time") or "").strip()[:16]
    return f"pair:{'|'.join(sorted([pick or p1, p2]))}|{start}|pick:{pick}"


def _tg_row_day_from_value(row: Dict[str, Any]) -> str:
    for key in ("betting_day", "snapshot_date", "snapshot_functional_day", "functional_day", "date", "run_date", "match_date"):
        value = row.get(key)
        if value:
            txt = str(value).strip()[:10]
            try:
                datetime.fromisoformat(txt)
                return txt
            except Exception:
                pass
    return ""


def _row_result_day(row: Dict[str, Any]) -> str:
    explicit = _tg_row_day_from_value(row)
    if explicit:
        return explicit
    dt = match_start_datetime(row)
    if dt is not None:
        local_dt = dt.astimezone(local_tz())
        day = local_dt.date()
        # Project/results day is 06:00 -> 06:00 Europe/Bratislava.
        if local_dt.hour < 6:
            day = day - timedelta(days=1)
        return day.isoformat()
    return ""



def _results_message_needs_rebuild(message: str, model_label: str, target_day: Optional[str] = None) -> bool:
    """Force JSON/snapshot-based results rendering by default.

    Pre-built result messages can be stale or incomplete when the settlement
    ledger contains only settled rows. Rebuilding here lets the completeness
    layer use the full expected daily snapshot and fill missing rows as Pending.
    Set TG_RESULTS_USE_PREBUILT=1 only for debugging a pre-rendered message.
    """
    if os.getenv("TG_RESULTS_USE_PREBUILT", "0").lower() in {"1", "true", "yes", "y"}:
        txt = str(message or "").strip()
        if not txt:
            return True
        target = str(target_day or "").strip()[:10]
        if target:
            message_day = _extract_results_message_day(txt)
            return bool(message_day != target)
        return False
    return True

def _tg_result_source_candidates(model: str, day: Optional[str] = None) -> List[Path]:
    day = str(day or "").strip()[:10]
    model = str(model or "corq").lower()
    candidates: List[Path] = []
    if model == "cloq":
        candidates.extend([
            OUTPUTS / "cloq" / "latest_cloq.json",
            OUTPUTS / "latest_cloq.json",
            OUTPUTS / "snapshots" / "latest_cloq_snapshot.json",
            OUTPUTS / "snapshots" / "latest_cloq.json",
        ])
        if day:
            candidates.extend([
                OUTPUTS / "snapshots" / f"cloq_{day}.json",
                OUTPUTS / "snapshots" / f"cloq_top_{day}.json",
                OUTPUTS / "cloq" / f"cloq_{day}.json",
            ])
    else:
        candidates.extend([
            OUTPUTS / "snapshots" / "latest_corq_top7_snapshot.json",
            OUTPUTS / "latest_top7.json",
            OUTPUTS / "snapshots" / "latest_top7.json",
        ])
        if day:
            candidates.extend([
                OUTPUTS / "snapshots" / f"corq_top7_{day}.json",
                OUTPUTS / "snapshots" / f"top7_{day}.json",
                OUTPUTS / "snapshots" / f"CORQ_TOP7_{day}.json",
            ])
    # Preserve order but remove duplicates.
    out: List[Path] = []
    seen = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            out.append(path)
            seen.add(key)
    return out


def _tg_expected_rows_from_snapshots(model: str, day: Optional[str] = None) -> List[Dict[str, Any]]:
    target = str(day or "").strip()[:10]
    model = str(model or "corq").lower()
    for path in _tg_result_source_candidates(model, day=target):
        rows = json_rows(read_json(path, []))
        if not rows:
            continue
        selected: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if target and _row_result_day(row) != target:
                continue
            # TOP7/CloQ snapshot files can be compact and may not carry model.
            if model == "corq":
                rank = as_float(row.get("top7_rank") or row.get("snapshot_rank") or row.get("corq_rank") or row.get("rank"), None)
                if rank is None and not (row.get("top7_publishable") is True or "CORQ" in str(row.get("snapshot_type") or row.get("snapshot_source") or "").upper()):
                    continue
            else:
                rank = as_float(row.get("cloq_rank") or row.get("rank") or row.get("snapshot_rank"), None)
                row_text = str(row.get("model") or row.get("snapshot_type") or row.get("snapshot_source") or row.get("source_filter") or "").upper()
                # CloQ files are often pure CloQ lists, so accept rows even if no explicit model exists.
                if rank is None and rows.index(row) >= 10 and "CLOQ" not in row_text:
                    continue
            selected.append(dict(row))
        if selected:
            print(f"[tg_feed] {model.upper()} expected snapshot rows selected: {path} rows={len(selected)}")
            return selected
    print(f"[tg_feed] {model.upper()} expected snapshot rows selected: empty")
    return []




def _tg_result_loose_identity(row: Dict[str, Any], day: Optional[str] = None) -> str:
    """Fallback identity for result/snapshot merge when event ids differ.

    Some settled rows and snapshot rows can represent the same pick but carry a
    different side_identity/event key. Use conservative visible fields so a
    settled row replaces the Pending snapshot row instead of creating duplicate
    lines in Telegram results.
    """
    pick = _tg_norm_text(pick_name(row))
    if not pick:
        return ""
    target_day = str(day or _row_result_day(row) or "").strip()[:10]
    t = start_time(row)
    odds = pick_odds(row)
    odds_txt = f"{odds:.2f}" if odds else ""
    opponent = _tg_norm_text(opponent_name(row))
    # Opponent can be missing/TBD in compact snapshots. Keep it only when useful.
    opponent_part = opponent if opponent and opponent != "tbd" else ""
    return "|".join([target_day, pick, opponent_part, str(t or ""), odds_txt])


def _tg_merge_key_set(row: Dict[str, Any], day: Optional[str] = None) -> set[str]:
    out = set()
    side = _tg_side_identity(row)
    if side:
        out.add("side:" + side)
    loose = _tg_result_loose_identity(row, day=day)
    if loose:
        out.add("loose:" + loose)
    return out

def _tg_merge_expected_and_results(results: List[Dict[str, Any]], expected: List[Dict[str, Any]], model: str, day: Optional[str]) -> List[Dict[str, Any]]:
    model = str(model or "corq").lower()
    target = str(day or "").strip()[:10]
    results_filtered = filter_result_rows(results or [], model, day=target)

    by_key: Dict[str, Dict[str, Any]] = {}
    for row in results_filtered:
        for key in _tg_merge_key_set(row, day=target):
            by_key.setdefault(key, row)

    merged: List[Dict[str, Any]] = []
    used_keys: set[str] = set()
    expected_sorted = sorted(
        expected or [],
        key=lambda r: (
            as_float(r.get("snapshot_rank") or r.get("top7_rank") or r.get("cloq_rank") or r.get("rank"), 9999) or 9999,
            start_time(r),
            pick_name(r),
        ),
    )
    for row in expected_sorted:
        keys = _tg_merge_key_set(row, day=target)
        settled = None
        for key in keys:
            if key in by_key:
                settled = by_key[key]
                break
        if settled is not None:
            merged.append(settled)
            used_keys.update(_tg_merge_key_set(settled, day=target))
            used_keys.update(keys)
        else:
            pending = dict(row)
            pending.setdefault("model", model)
            if target:
                pending.setdefault("date", target)
                pending.setdefault("betting_day", target)
            pending["result_status"] = "PENDING"
            pending["result"] = "PENDING"
            pending["settlement_status"] = "PENDING"
            pending["units"] = None
            pending["tg_results_fill_status"] = "PENDING_FROM_EXPECTED_SNAPSHOT"
            pending["tg_results_completeness_version"] = TG_RESULTS_COMPLETENESS_MODEL_VERSION
            merged.append(pending)
            used_keys.update(keys)
            print(f"[tg_feed] {model.upper()} results completeness filled pending row: {pick_name(pending)} {start_time(pending)}")

    # Add extra settled rows that were not in expected snapshot, but do not add
    # another copy if the same pick/time/odds already exists as Pending/settled.
    for row in results_filtered:
        keys = _tg_merge_key_set(row, day=target)
        if keys and keys.intersection(used_keys):
            continue
        if not any(_tg_merge_key_set(x, day=target).intersection(keys) for x in merged):
            merged.append(row)
            used_keys.update(keys)

    merged.sort(key=lambda r: (
        as_float(r.get("snapshot_rank") or r.get("top7_rank") or r.get("cloq_rank") or r.get("rank"), 9999) or 9999,
        start_time(r),
        pick_name(r),
    ))
    return merged

def filter_result_rows(rows: List[Dict[str, Any]], model: str, day: Optional[str] = None) -> List[Dict[str, Any]]:
    target = str(day or "").strip()[:10]
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if not _result_row_model_matches(row, model):
            continue
        if target and _row_result_day(row) != target:
            continue
        out.append(row)
    out.sort(key=lambda r: (as_float(r.get("snapshot_rank") or r.get("top7_rank") or r.get("cloq_rank") or r.get("rank"), 9999) or 9999, start_time(r), pick_name(r)))
    return out


def build_results_summary_message(rows: List[Dict[str, Any]], model_label: str, day: Optional[str] = None) -> str:
    model = str(model_label or "CorQ").lower()
    label = _model_label(model)
    filtered = filter_result_rows(rows or [], model, day=day)
    expected = _tg_expected_rows_from_snapshots(model, day=day)
    if expected:
        rows = _tg_merge_expected_and_results(rows or [], expected, model, day)
    else:
        rows = filtered

    date_text = ""
    if day:
        try:
            date_text = datetime.fromisoformat(str(day)[:10]).strftime("%d.%m.%y")
        except Exception:
            date_text = str(day)[:10]
    else:
        date_text = snapshot_date(rows)

    counts = {"won": 0, "lost": 0, "void": 0, "pending": 0}
    units = 0.0
    for row in rows:
        st = result_status(row)
        counts[st if st in counts else "pending"] += 1
        units += result_units(row)
    decided = counts["won"] + counts["lost"]
    roi = (units / decided) if decided else None
    roi_txt = "ROI —" if roi is None else f"ROI {roi * 100:+.1f}%"
    lines = [HEADER, "", f"📊 Results | {label}", f"📅 {date_text}", ""]
    if rows:
        names = display_name_map(rows)
        for idx, row in enumerate(rows[:10], 1):
            st = result_status(row)
            icon = {"won": "✅", "lost": "❌", "void": "➖", "pending": "⏳"}.get(st, "⏳")
            unit_txt = "Pending" if st == "pending" else f"{result_units(row):+.2f}u"
            lines.append(f"{number_emoji(idx)} {icon} {display_pick_name(row, names)} | {start_time(row)} | {fmt_odds(pick_odds(row))} | {unit_txt}")
        lines.extend([
            "",
            f"✅{counts['won']} ❌{counts['lost']} ➖{counts['void']} ⏳{counts['pending']} | {units:+.2f}u | {roi_txt}",
        ])
        if expected and len(rows) != len(filtered):
            lines.append(f"↪️ Filled {len(rows) - len(filtered)} missing snapshot row(s) as Pending")
    else:
        lines.append(f"No previous {label} snapshot rows found.")
    lines.extend(["", FOOTER])
    return "\n".join(lines)



# ============================================================
# CloQ/CorQ overlap guard override V13
# ============================================================
# Previous behavior removed CloQ rows when the same match also existed in CorQ.
# That was useful to avoid duplicate Telegram posts, but it also made CloQ
# audit/results harder to reason about. Default is now OFF: CloQ is allowed to
# publish and evaluate its own rows even when CorQ has the same match.
# To re-enable old behavior temporarily, set TG_CLOQ_CORQ_OVERLAP_GUARD=1.

TG_CLOQ_CORQ_OVERLAP_GUARD_MODEL_VERSION = "TG_CLOQ_CORQ_OVERLAP_GUARD_DISABLED_V13"


def _cloq_corq_overlap_guard_enabled() -> bool:
    return str(os.getenv("TG_CLOQ_CORQ_OVERLAP_GUARD", "0")).lower() in {"1", "true", "yes", "y", "on"}


def drop_cloq_corq_overlaps(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not _cloq_corq_overlap_guard_enabled():
        print("[tg_feed] CloQ/CorQ overlap guard disabled; CloQ rows kept unchanged")
        return list(rows or [])
    keys = load_corq_overlap_match_keys() if "load_corq_overlap_match_keys" in globals() else current_corq_match_keys_for_tg()
    if not keys or not rows:
        return rows
    out: List[Dict[str, Any]] = []
    skipped = 0
    for row in rows:
        key = tg_match_identity(row)
        if key and key in keys:
            skipped += 1
            continue
        out.append(row)
    if skipped:
        print(f"[tg_feed] CloQ overlap safety skipped {skipped} row(s) already covered by CorQ")
    return out


def filter_cloq_corq_overlap_for_tg(rows: List[Dict[str, Any]], corq_match_keys: Optional[set[str]] = None) -> List[Dict[str, Any]]:
    if not _cloq_corq_overlap_guard_enabled():
        print("[tg_feed] CloQ duplicate guard disabled; source rows kept unchanged")
        return list(rows or [])
    corq_match_keys = corq_match_keys or current_corq_match_keys_for_tg()
    if not corq_match_keys:
        return rows
    out: List[Dict[str, Any]] = []
    skipped = 0
    for row in rows or []:
        key = tg_match_identity(row)
        if key in corq_match_keys:
            skipped += 1
            continue
        out.append(row)
    if skipped:
        print(f"[tg_feed] CloQ duplicate guard skipped {skipped} CorQ-overlap matches")
    return out

# ============================================================
# Immutable TG snapshot persistence V12
# ============================================================
# The Results feed must be based on the exact rows sent in the original pick
# feed, not on whatever latest_* file exists the next morning. This writes a
# dated snapshot whenever TOP7/CloQ pick messages are built/sent.

TG_SENT_SNAPSHOT_VERSION = "TG_SENT_SNAPSHOT_V12"


def _tg_snapshot_day_from_rows(rows: List[Dict[str, Any]]) -> str:
    for row in rows or []:
        day = row_day_iso(row)
        if day:
            return day[:10]
    return datetime.now(local_tz()).date().isoformat()


def _tg_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def persist_sent_pick_snapshot(mode: str, rows: List[Dict[str, Any]], limit: int = 7) -> None:
    mode = str(mode or "").lower()
    if mode not in {"top7", "cloq"}:
        return
    rows = [dict(r) for r in rows or [] if isinstance(r, dict)]
    if not rows:
        print(f"[tg_feed] {mode.upper()} sent snapshot skipped: no rows")
        return
    day = _tg_snapshot_day_from_rows(rows)
    snapshot_rows: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows[:limit], start=1):
        row.setdefault("betting_day", day)
        row.setdefault("snapshot_date", day)
        row.setdefault("snapshot_functional_day", day)
        row.setdefault("functional_day", day)
        row.setdefault("tg_sent_snapshot_version", TG_SENT_SNAPSHOT_VERSION)
        row.setdefault("tg_sent_snapshot_written_at", datetime.now(timezone.utc).replace(microsecond=0).isoformat())
        if mode == "cloq":
            row.setdefault("model", "cloq")
            row.setdefault("snapshot_source", "CLOQ_DAILY")
            row.setdefault("snapshot_type", "DAILY_CLOQ_SNAPSHOT")
            row.setdefault("source_filter", "CloQ")
            row.setdefault("cloq_rank", row.get("cloq_rank") or row.get("rank") or idx)
            row.setdefault("snapshot_rank", row.get("snapshot_rank") or row.get("cloq_rank") or idx)
        else:
            row.setdefault("model", "corq")
            row.setdefault("snapshot_source", "CORQ_DAILY")
            row.setdefault("snapshot_type", "DAILY_CORQ_SNAPSHOT")
            row.setdefault("source_filter", "CorQ")
            row.setdefault("top7_rank", row.get("top7_rank") or row.get("rank") or idx)
            row.setdefault("snapshot_rank", row.get("snapshot_rank") or row.get("top7_rank") or idx)
        snapshot_rows.append(row)

    out_dir = OUTPUTS / "snapshots"
    if mode == "cloq":
        dated_path = out_dir / f"cloq_top_{day}.json"
        latest_path = out_dir / "latest_cloq_snapshot.json"
    else:
        dated_path = out_dir / f"corq_top7_{day}.json"
        latest_path = out_dir / "latest_corq_top7_snapshot.json"
    _tg_write_json(dated_path, snapshot_rows)
    _tg_write_json(latest_path, snapshot_rows)
    print(f"[tg_feed] {mode.upper()} sent snapshot persisted: {dated_path} rows={len(snapshot_rows)}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram feed formatter/sender for CorQ")
    parser.add_argument("--mode", choices=("cloq", "cloq-free", "top7", "free", "results", "corq-results", "cloq-results"), default=os.getenv("TG_FEED_MODE", "top7"))
    parser.add_argument("--top7-path", default=os.getenv("TG_TOP7_PATH", str(DEFAULT_TOP7_PATH)))
    parser.add_argument("--cloq-path", default=os.getenv("TG_CLOQ_PATH", str(DEFAULT_CLOQ_PATH)))
    parser.add_argument("--all-path", default=os.getenv("TG_ALL_PATH", str(DEFAULT_ALL_PATH)))
    parser.add_argument("--results-message-path", default=os.getenv("TG_RESULTS_MESSAGE_PATH", str(DEFAULT_RESULTS_MESSAGE_PATH)))
    parser.add_argument("--cloq-results-message-path", default=os.getenv("TG_CLOQ_RESULTS_MESSAGE_PATH", str(DEFAULT_CLOQ_RESULTS_MESSAGE_PATH)))
    parser.add_argument("--results-date", default=os.getenv("TG_RESULTS_DATE", ""), help="Results betting day YYYY-MM-DD. Defaults to previous completed betting day.")
    parser.add_argument("--output", default=os.getenv("TG_MESSAGE_OUTPUT", str(DEFAULT_MESSAGE_PATH)))
    parser.add_argument("--send", action="store_true", help="Send to Telegram using env bot token and chat id")
    parser.add_argument("--chat-id", default=None, help="Telegram chat id. Defaults by mode from env.")
    parser.add_argument(
        "--bot-token",
        default=(
            os.getenv("TELEGRAM_BOT_TOKEN")
            or os.getenv("TG_BOT_TOKEN")
            or os.getenv("TGBOT")
        ),
    )
    parser.add_argument("--limit", type=int, default=7)
    parser.add_argument(
        "--include-started",
        action="store_true",
        help="Include matches that already started. Default is upcoming only.",
    )
    args = parser.parse_args()
    if args.mode == "corq-results":
        args.mode = "results"
    upcoming_only_env = str(os.getenv("TG_FEED_UPCOMING_ONLY", "true")).lower() not in {"0", "false", "no"}
    upcoming_only = upcoming_only_env and not args.include_started
    results_day = (args.results_date or completed_betting_day_iso()).strip()[:10]
    sendable_rows: List[Dict[str, Any]] = []

    if args.mode == "results":
        results_path = Path(args.results_message_path)
        message = results_path.read_text(encoding="utf-8").strip() if results_path.exists() else ""
        if _results_message_needs_rebuild(message, "CorQ", target_day=results_day):
            corq_results = _load_result_rows("corq")
            message = build_results_summary_message(corq_results, "CorQ", day=results_day)
    elif args.mode == "cloq-results":
        results_path = Path(args.cloq_results_message_path)
        message = results_path.read_text(encoding="utf-8").strip() if results_path.exists() else ""
        if _results_message_needs_rebuild(message, "CloQ", target_day=results_day):
            cloq_results = _load_result_rows("cloq")
            message = build_results_summary_message(cloq_results, "CloQ", day=results_day)
    elif args.mode == "cloq-free":
        rows = load_cloq_rows(Path(args.cloq_path), Path(args.all_path))
        cloq_rows_for_message = valid_rows(drop_cloq_corq_overlaps(rows), upcoming_only=upcoming_only)[:1]
        sendable_rows = cloq_rows_for_message
        message = build_cloq_free_message(rows, upcoming_only=upcoming_only)
    elif args.mode == "cloq":
        rows = load_cloq_rows(Path(args.cloq_path), Path(args.all_path))
        cloq_rows_for_message = valid_rows(drop_cloq_corq_overlaps(rows), upcoming_only=upcoming_only)[:max(args.limit, 10)]
        sendable_rows = cloq_rows_for_message
        message = build_cloq_message(rows, limit=max(args.limit, 10), upcoming_only=upcoming_only)
        persist_sent_pick_snapshot("cloq", cloq_rows_for_message, limit=max(args.limit, 10))
    else:
        rows = load_rows_for_mode(args.mode, Path(args.top7_path), Path(args.all_path))
        sendable_rows = valid_rows(rows, upcoming_only=(upcoming_only if args.mode == "free" else False))
        if args.mode == "free":
            message = build_free_message(rows, upcoming_only=upcoming_only)
        else:
            top7_rows_for_message = valid_rows(rows, upcoming_only=False)[:args.limit]
            message = build_top7_message(rows, limit=args.limit, upcoming_only=False)
            persist_sent_pick_snapshot("top7", top7_rows_for_message, limit=args.limit)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(message, encoding="utf-8")
    print(message)

    if args.send:
        if args.mode in {"free", "cloq", "cloq-free"} and not sendable_rows:
            print(f"[tg_feed] No valid upcoming rows for mode={args.mode}; Telegram send skipped.")
            return
        if args.mode == "top7" and "No valid upcoming CorQ picks" in message:
            print(f"[tg_feed] No valid TOP7 rows for mode={args.mode}; Telegram send skipped.")
            return
        if args.mode in {"results", "cloq-results"} and not message.strip():
            print("[tg_feed] Empty results summary; Telegram send skipped.")
            return
        chat_id = args.chat_id
        if not chat_id:
            if args.mode in {"free", "cloq-free"}:
                chat_id = (
                    os.getenv("TELEGRAM_FREE_CHAT_ID")
                    or os.getenv("TG_FREE_CHAT_ID")
                    or os.getenv("TELEGRAM_TOP7_CHAT_ID")
                    or os.getenv("TG_TOP7_CHAT_ID")
                    or os.getenv("TGCHID")
                    or os.getenv("TELEGRAM_CHAT_ID")
                    or os.getenv("TG_CHAT_ID")
                )
            else:
                chat_id = (
                    os.getenv("TELEGRAM_TOP7_CHAT_ID")
                    or os.getenv("TG_TOP7_CHAT_ID")
                    or os.getenv("TGCHID")
                    or os.getenv("TELEGRAM_CHAT_ID")
                    or os.getenv("TG_CHAT_ID")
                )
        if not args.bot_token:
            if args.mode in {"free", "cloq-free"}:
                print("[tg_feed] Missing TELEGRAM_BOT_TOKEN/TG_BOT_TOKEN/TGBOT; FREE Telegram send skipped.")
                return
            raise SystemExit("Missing TELEGRAM_BOT_TOKEN/TG_BOT_TOKEN/TGBOT")
        if not chat_id:
            if args.mode in {"free", "cloq-free"}:
                print("[tg_feed] Missing Telegram chat id for FREE mode; FREE Telegram send skipped.")
                return
            raise SystemExit("Missing Telegram chat id for mode")
        try:
            send_telegram(message, args.bot_token, chat_id)
        except Exception as exc:
            if args.mode in {"free", "cloq-free"}:
                print(f"[tg_feed] FREE Telegram send failed but production workflow will continue: {exc}")
                return
            raise


if __name__ == "__main__":
    main()
