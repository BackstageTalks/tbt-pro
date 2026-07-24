"""Presentation helpers for CORQ public cards and Telegram feed.

This module keeps public display rules separate from model/runtime logic.
- Probability is displayed once, in the WIN PROBABILITY box.
- CORQ duplicate box is not generated here.
- THINQ is compressed to four useful rows.
- SETS/GAMES is compressed to user-facing rows.
- Telegram TOP7 is always sorted by probability descending and odds use two decimals.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from corq.messages import public_messages

TG_BRAND_HEADER = "AI Betting by BackstageTalks"
TG_TOP_N = 7
TG_DISPLAY_TIMEZONE = "Europe/Bratislava"


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def pct(value: Any, decimals: int = 1, signed: bool = False) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    if abs(number) <= 1:
        number *= 100
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{number:.{decimals}f}%"


def odds(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    return f"{number:.2f}"


def one_decimal(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    return f"{number:.1f}"


def two_decimals(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    return f"{number:.2f}"


def get_nested(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def probability_value(item: Dict[str, Any]) -> Optional[float]:
    for key in (
        "corq_estimated_win_probability",
        "estimated_win_probability",
        "corq_score",
        "probability",
        "win_probability",
    ):
        value = safe_float(item.get(key))
        if value is not None:
            return value if value <= 1 else value / 100
    pct_value = safe_float(item.get("estimated_win_pct"))
    if pct_value is not None:
        return pct_value / 100 if pct_value > 1 else pct_value
    return None


def probability_label(item: Dict[str, Any]) -> str:
    value = probability_value(item)
    return pct(value, decimals=1) if value is not None else "—"


def parse_match_time_utc(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def display_time(item: Dict[str, Any], timezone_name: str = TG_DISPLAY_TIMEZONE) -> str:
    raw_value = item.get("match_start") or item.get("start_time") or item.get("commence_time")
    dt = parse_match_time_utc(raw_value)
    if dt is None:
        return "TBD"
    if timezone_name and ZoneInfo is not None:
        dt = dt.astimezone(ZoneInfo(timezone_name))
    return dt.strftime("%H:%M")


def display_date(item: Dict[str, Any], timezone_name: str = TG_DISPLAY_TIMEZONE) -> str:
    raw_value = item.get("match_start") or item.get("start_time") or item.get("commence_time")
    dt = parse_match_time_utc(raw_value)
    if dt is None:
        return datetime.now().strftime("%d.%m.%Y")
    if timezone_name and ZoneInfo is not None:
        dt = dt.astimezone(ZoneInfo(timezone_name))
    return dt.strftime("%d.%m.%Y")


def first_name(name: Any) -> str:
    text = str(name or "").strip()
    if not text:
        return "Player"
    return text.split()[0]


def sort_by_probability_desc(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(list(items or []), key=lambda item: probability_value(item) or 0.0, reverse=True)


def build_telegram_top7(items: Iterable[Dict[str, Any]], run_date: Optional[str] = None) -> str:
    rows = sort_by_probability_desc(items)[:TG_TOP_N]
    if run_date:
        date_text = _format_run_date(run_date)
    elif rows:
        date_text = display_date(rows[0])
    else:
        date_text = datetime.now().strftime("%d.%m.%Y")

    lines = [
        TG_BRAND_HEADER,
        "",
        f"📅 {date_text} | 🎾 TOP7",
        "",
    ]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
    for index, item in enumerate(rows):
        lines.append(
            f"{emojis[index]} {first_name(item.get('pick'))} | {display_time(item)} | {probability_label(item)} | {odds(item.get('odds') or item.get('pick_odds'))}"
        )
    lines.extend(["", "ℹ️ Analytical preview only", "🧠 by BackstageTalks AI Engine"])
    return "\n".join(lines)


def _format_run_date(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d.%m.%Y")
        except Exception:
            pass
    return text


def side_display(item: Dict[str, Any]) -> str:
    # Do not expose PICK_IS_PLAYER2_AWAY / Away pick style internals to public UI.
    status = item.get("status_type") or get_nested(item, "raw", "status", "type")
    return f"Status: {status}" if status else ""


def build_win_probability_box(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "WIN PROBABILITY",
        "probability": probability_label(item),
        "rows": [],
    }


def build_thinq_rows(item: Dict[str, Any]) -> List[Dict[str, str]]:
    thinq = item.get("thinq") if isinstance(item.get("thinq"), dict) else {}
    h2h = thinq.get("h2h") if isinstance(thinq.get("h2h"), dict) else {}
    recent = thinq.get("recent_form") if isinstance(thinq.get("recent_form"), dict) else {}

    overall_elo = item.get("thinq_overall_elo_edge")
    if overall_elo is None:
        overall_elo = get_nested(thinq, "edges", "overall_elo_edge")
    surface_elo = item.get("thinq_surface_elo_edge")
    if surface_elo is None:
        surface_elo = get_nested(thinq, "edges", "surface_elo_edge")

    h2h_status = h2h.get("status") or item.get("thinq_h2h_status") or "—"
    h2h_edge = h2h.get("edge") if h2h.get("edge") is not None else item.get("thinq_h2h_edge")
    h2h_value = f"{h2h_status} · {pct(h2h_edge, signed=True)}"

    form_value = "Pending"
    if recent.get("status") == "OK":
        form_value = pct(recent.get("recent_form_edge"), signed=True)

    confidence = item.get("thinq_confidence")
    if confidence is None:
        confidence = thinq.get("confidence")

    return [
        {"label": "ELO / S-ELO", "value": f"{pct(overall_elo, signed=True)} / {pct(surface_elo, signed=True)}"},
        {"label": "H2H", "value": h2h_value},
        {"label": "Form", "value": form_value},
        {"label": "Confidence", "value": pct(confidence)},
    ]


def build_sets_games_rows(item: Dict[str, Any]) -> List[Dict[str, str]]:
    expected_sets = item.get("expected_sets") or item.get("projected_sets")
    expected_games = item.get("expected_games") or item.get("projected_games")
    three_sets = item.get("three_sets_probability") or item.get("sets_probability")
    score = item.get("most_likely_score") or item.get("predicted_score")
    tie_break = item.get("tie_break_probability") or item.get("tiebreak_probability")

    games_line = item.get("games_line")
    games_over = item.get("games_over_probability")
    ou_value = "—"
    if safe_float(games_line) is not None and safe_float(games_over) is not None:
        ou_value = f"Over {two_decimals(games_line)} · {pct(games_over)}"
    elif safe_float(games_line) is not None:
        ou_value = f"Line {two_decimals(games_line)}"
    elif safe_float(games_over) is not None:
        ou_value = f"Over · {pct(games_over)}"

    return [
        {"label": "Sets", "value": two_decimals(expected_sets)},
        {"label": "Games", "value": one_decimal(expected_games)},
        {"label": "O/U", "value": ou_value},
        {"label": "3 Sets", "value": pct(three_sets)},
        {"label": "Score", "value": str(score or "—")},
        {"label": "Tie-break", "value": pct(tie_break)},
    ]


def build_public_card(item: Dict[str, Any]) -> Dict[str, Any]:
    flags = []
    for key in ("thinq_flags", "corq_risk_flags", "corq_warning_flags"):
        value = item.get(key)
        if isinstance(value, list):
            flags.extend(value)

    return {
        "rank": item.get("corq_rank"),
        "pick": item.get("pick"),
        "opponent": item.get("opponent"),
        "pick_odds": odds(item.get("odds") or item.get("pick_odds")),
        "opponent_odds": odds(item.get("opponent_odds")),
        "match_meta": {
            "time": display_time(item),
            "tournament": item.get("tournament"),
            "surface": item.get("surface"),
            "best_of": item.get("best_of") or 3,
            "status": item.get("status_type"),
        },
        "status_text": side_display(item),
        "win_probability": build_win_probability_box(item),
        "thinq_rows": build_thinq_rows(item),
        "sets_games_rows": build_sets_games_rows(item),
        "messages": public_messages(flags),
    }


def build_public_cards(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [build_public_card(item) for item in sort_by_probability_desc(items)]
