from __future__ import annotations

import base64
import html
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
WEB_DIR = ROOT / "corq" / "web"
SITE_DIR = ROOT / "corq" / "site"
ASSET_SRC = WEB_DIR / "assets" / "tbt_ai_goat_icon_new.png"
ASSET_DIR = SITE_DIR / "assets"
LOGS_DIR = SITE_DIR / "logs"

# Web match times are always displayed in Europe/Bratislava local time.
# ZoneInfo applies DST automatically: CET UTC+1 in winter, CEST UTC+2 in summer.
WEB_DISPLAY_TIMEZONE = ZoneInfo("Europe/Bratislava")


_GOAT_BADGE_URI: Optional[str] = None

def goat_badge_src() -> str:
    """Return the goat logo as a data URI for card badges.

    Card pages can be rendered in hidden subfolders, so relative asset paths can
    break. Embedding the 512x512 logo keeps the small badge stable everywhere.
    """
    global _GOAT_BADGE_URI
    if _GOAT_BADGE_URI:
        return _GOAT_BADGE_URI
    for src in (
        WEB_DIR / "assets" / "tbt_ai_goat_badge.png",
        WEB_DIR / "assets" / "tbt_ai_goat_icon_small_safe.png",
        WEB_DIR / "assets" / "tbt_ai_goat_icon.png",
    ):
        try:
            if src.exists():
                encoded = base64.b64encode(src.read_bytes()).decode("ascii")
                _GOAT_BADGE_URI = f"data:image/png;base64,{encoded}"
                return _GOAT_BADGE_URI
        except Exception:
            pass
    return "assets/tbt_ai_goat_icon.png"


try:
    from corq.web.paths import (
        TOP7_PATH,
        CLOQ_PATH,
        ALL_PATH,
        RESULTS_PATH,
        THINQ_PATH,
        CORQ_RSS_PATH,
        CLOQ_RSS_PATH,
        THINQ_RSS_PATH,
        LUCQ_PATH,
        LUCQ_RSS_PATH,
        NAV_ITEMS,
    )
except Exception:
    TOP7_PATH = "h4v34n1c3d4y180"
    CLOQ_PATH = "h4v34n1c3d4y181"
    ALL_PATH = "h4v34n1c3d4y182"
    RESULTS_PATH = "h4v34n1c3d4y183"
    CORQ_RSS_PATH = "h4v34n1c3d4y184.xml"
    CLOQ_RSS_PATH = "h4v34n1c3d4y185.xml"
    THINQ_PATH = "h4v34n1c3d4y186"
    THINQ_RSS_PATH = "h4v34n1c3d4y187.xml"
    LUCQ_PATH = "h4v34n1c3d4y188"
    LUCQ_RSS_PATH = "h4v34n1c3d4y189.xml"
    NAV_ITEMS = [("CorQ", TOP7_PATH), ("All", ALL_PATH), ("Results", RESULTS_PATH), ("CloQ", CLOQ_PATH), ("TG RSS", CORQ_RSS_PATH)]

try:
    from corq.messages import public_flag_labels as _messages_public_flag_labels
except Exception:
    _messages_public_flag_labels = None


def public_flag_labels(flags: Iterable[str], limit: Optional[int] = None) -> List[str]:
    if _messages_public_flag_labels is not None:
        try:
            labels = _messages_public_flag_labels(flags)
        except TypeError:
            try:
                labels = _messages_public_flag_labels(flags, limit)
            except TypeError:
                labels = []
    else:
        labels = []
        for flag in flags or []:
            if flag:
                labels.append(str(flag).replace("_", " ").strip().title())
    if labels is None:
        labels = []
    if isinstance(labels, str):
        labels = [labels]
    out: List[str] = []
    seen = set()
    for item in labels:
        text = str(item).strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out[:limit] if limit is not None else out



_INFO_CACHE: Optional[Dict[str, Any]] = None

def load_explanations() -> Dict[str, Any]:
    global _INFO_CACHE
    if _INFO_CACHE is not None:
        return _INFO_CACHE
    data = read_json(WEB_DIR / "explanations.json", {})
    if not isinstance(data, dict):
        data = {}
    _INFO_CACHE = data
    return data

def explanation_text(key: str) -> str:
    data = load_explanations()
    aliases = {
        "corq": "corq_box",
        "thinq": "thinq_box",
        "ta": "ta_box",
        "ta_set_game": "ta_set_game",
        "ta_tiebreak": "ta_tiebreak",
        "ta_surface_dr": "ta_surface_dr",
        "ta_depth": "ta_depth",
        "aces": "aces",
        "h2h": "h2h",
        "s_h2h": "s_h2h",
        "stat_data_depth": "pick_data_depth",
        "form_data_depth": "form_data_depth",
        "mmx": "mmx_box",
        "marq": "marq_box",
        "sets_games": "sets_games_box",
        "marq_edge": "marq_edge",
        "marq_move": "marq_move",
        "thinq_pc": "thinq_pc",
        "p_el_s_e": "p_el_s_e",
        "o_el_s_e": "o_el_s_e",
        "h2h_p_o": "h2h_p_o",
        "s_h2h_p_o": "s_h2h_p_o",
        "p_thinq_edge": "p_thinq_edge",
        "s_data_depth": "s_data_depth",
        "p_f_s_f": "p_f_s_f",
        "o_f_s_f": "o_f_s_f",
        "p_r_edge": "p_r_edge",
        "p_s_edge": "p_s_edge",
        "p_f_qty": "p_f_qty",
        "f_data_depth": "f_data_depth",
        "thinq_prob": "thinq_prob",
        "marq_prob": "marq_prob",
        "thinq_input": "thinq_input",
        "marq_input": "marq_input",
        "corq_final": "corq_final",
        "marq_delta": "marq_delta",
        "sets_ou": "sets_ou",
        "games_ou": "games_ou",
        "tb_pct": "tb_pct",
        "aces_p_o_t": "aces_p_o_t",
        "df_p_o_t": "df_p_o_t",
        "pick_marq": "pick_marq",
        "opp_marq": "opp_marq",
        "clv": "clv",
        "marq_final": "marq_final",
        "odds_gap": "odds_gap",
        "status": "status",
        "source": "source",
        "rank": "rank",
        "filter": "filter",
        "limit": "limit",
        "signal": "signal",
        "action": "action",
        "confidence": "confidence",
        "reason": "reason",
        "winner_read": "winner_read",
        "sets_read": "sets_read",
        "games_read": "games_read",
        "ta_depth": "ta_depth",
    }
    lookup_keys = [key, aliases.get(key, "")]
    for lookup in lookup_keys:
        if not lookup:
            continue
        item = data.get(lookup)
        if isinstance(item, dict):
            title = str(item.get("title") or "").strip()
            text = str(item.get("text") or item.get("description") or "").strip()
            if title and text:
                return f"{title}: {text}"
            if text:
                return text
            if title:
                return title
        elif isinstance(item, str) and item.strip():
            return item.strip()
    defaults = {
        "corq": "CorQ is the final win probability for the displayed pick.",
        "thinq": "ThinQ is the internal model layer. It combines form, surface, Elo/H2H and match-dynamics signals before CorQ blends it with MarQ market data.",
        "ta": "TA Signal converts Tennis Abstract profile data into a bettor-facing action: sets lean, games lean, TB risk, score lean or no clear signal.",
        "sets_games": "Sets/Games combines TA set, game, tie-break and match-shape reads. It is a lean/projection, not a guaranteed final score.",
        "ta_set_game": "Set and game win percentages for pick and opponent from the relevant Tennis Abstract sample when available.",
        "ta_tiebreak": "Tiebreak win-loss split from the relevant Tennis Abstract sample when available.",
        "ta_surface_dr": "Dominance ratio on the relevant surface. Values above 1.00 indicate stronger performance.",
        "ta_depth": "Internal confidence score for Tennis Abstract coverage and sample quality.",
        "aces": "Projected aces for pick, opponent and total. Currently N/A until the set and game model is completed.",
        "stat_data_depth": "S Data Depth shows the statistical support for the current pick.",
        "form_data_depth": "F Data Depth shows the reliability of recent form, surface form and opponent-quality data.",
        "mmx": "MMx shows the final blend between ThinQ model signal and MarQ market signal.",
        "marq": "MarQ summarises market-facing signals: market probability, value versus model, price movement, data trust and final market read.",
        "marq_edge": "Value shows the model edge versus no-vig market probability, plus expected value at the current pick price. Positive values support the pick.",
        "marq_move": "Range | Move: opening pick odds -> current pick odds when AllOdds provides initial odds. If no opening price is available, the box shows current-only/no-open.",
        "thinq_pc": "ThinQ P | C: Probability and Confidence from the ThinQ model. P is the model win probability for the displayed pick. C is the ThinQ confidence/data-quality score used to judge how reliable the probability is.",
        "thinq_prob": "ThinQ Prob: raw ThinQ model probability for the displayed pick before the market blend. It is a model probability, not market-implied odds.",
        "p_el_s_e": "P EL | S-E: pick Elo edge and surface Elo edge versus the opponent. Displayed as overall Elo edge | surface-specific Elo edge.",
        "o_el_s_e": "O EL | S-E: opponent Elo edge and surface Elo edge viewed from the opponent side. Displayed as overall Elo edge | surface-specific Elo edge.",
        "h2h_p_o": "H2H P-O: head-to-head record between pick and opponent. Format is pick wins - opponent wins, with the derived edge when available.",
        "s_h2h_p_o": "S-H2H P-O: same-surface head-to-head record between pick and opponent. Format is pick wins - opponent wins, with the derived same-surface edge when available.",
        "p_thinq_edge": "P ThinQ Edge: ThinQ model edge for the displayed pick compared with the available market/price baseline. Positive values support the pick, negative values are against the pick.",
        "s_data_depth": "S Data Depth: real statistical-data quality for the current pick. It is based on available sample depth and completeness of set, game, tiebreak, ace, double-fault, return and surface fields. If the source data is missing, the value is N/A.",
        "p_f_s_f": "P F | S-F: pick recent form and surface form. Format is recent W-L | surface W-L, usually from the configured recent-match windows.",
        "o_f_s_f": "O F | S-F: opponent recent form and surface form. Format is recent W-L | surface W-L, usually from the configured recent-match windows.",
        "p_r_edge": "P R-Edge: pick recent-form edge. It compares the pick recent form with the opponent recent form and expresses the difference as a percentage-point edge when available.",
        "p_s_edge": "P S-Edge: pick surface-form edge. It compares the pick performance on the current surface with the opponent surface performance.",
        "p_f_qty": "P F Qty: pick form-quality edge. It captures opponent-quality strength within the recent-form sample, so a positive value means the pick form came against stronger opposition.",
        "f_data_depth": "F Data Depth: form-data quality score. It reflects coverage/completeness of recent form, surface form and opponent-quality data.",
        "marq_prob": "MarQ Prob: market-side probability for the displayed pick, usually derived from no-vig bookmaker/market prices.",
        "thinq_input": "ThinQ Input: contribution of ThinQ to the final CorQ probability, shown in percentage points. Positive values lift CorQ, negative values reduce CorQ.",
        "marq_input": "MarQ Input: contribution of MarQ market signal to the final CorQ probability, shown in percentage points. Positive values lift CorQ, negative values reduce CorQ.",
        "corq_final": "CorQ Final: final calibrated CorQ probability after blending ThinQ model signal and MarQ market signal.",
        "marq_delta": "Model Value: model edge versus no-vig market probability, plus expected value at the current pick price. Positive values support the pick.",
        "sets_ou": "Sets o|u: recommended over/under side for total sets with line and probability. Example O2.5 47% means over 2.5 sets at 47% model probability.",
        "games_ou": "Games o|u: recommended over/under side for total games with line and probability. Example O23.5 51% means over 23.5 games at 51% model probability.",
        "tb_pct": "TB%: projected tiebreak probability. It is derived from the set/game and serve profile when available; otherwise it falls back to the configured match-shape source.",
        "aces_p_o_t": "Aces P | O | T: projected aces for Pick | Opponent | Total. Values come from TA serve profile or ace model when available; missing source data is displayed as dashes.",
        "df_p_o_t": "DF P | O | T: projected double faults for Pick | Opponent | Total. Values come from TA serve/DF profile or DF model when available; missing source data is displayed as dashes.",
        "pick_marq": "Pick Marq: market-implied probability for the displayed pick after no-vig normalization across usable market quotes.",
        "opp_marq": "Opp Marq: market-implied probability for the opponent after no-vig normalization across usable market quotes.",
        "clv": "CLV: closing-line value status or percentage-point move versus the stored snapshot. Pending means no valid closing/snapshot comparison is available yet.",
        "marq_final": "MarQ Final: final market read for the pick. It summarizes market edge, movement and CLV into a bettor-facing verdict such as Market With Pick, Market Against Pick or Neutral.",
        "odds_gap": "Odds Gap: relative gap between pick and opponent prices. CloQ uses this to focus on close-price matches.",
        "status": "Status: processing or data status for this box/row.",
        "source": "Source: source bucket or feed used for the displayed value.",
        "rank": "Rank: ordering position after the active sorting/filtering logic.",
        "filter": "Filter: active selection rule used for the current view.",
        "limit": "Limit: configured threshold used by the current view or filter.",
        "signal": "Signal: compact TA-readable signal produced from available Tennis Abstract profile fields.",
        "action": "Action: bettor-facing instruction derived from the current TA signal and confidence.",
        "confidence": "Confidence: confidence/data-quality for the specific signal in this box, not necessarily final win probability.",
        "reason": "Reason: short explanation of why the current signal/action was selected.",
        "winner_read": "Winner Read: TA read for the match winner based on profile, surface and form inputs.",
        "sets_read": "Sets Read: TA read for set market direction based on set profile and match-shape inputs.",
        "games_read": "Games Read: TA read for game market direction based on game profile and match-shape inputs.",
    }
    return defaults.get(key, key)

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[render] failed to read {path}: {exc}")
    return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def json_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "top7", "all", "picks", "cloq", "records", "results", "data"):
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




def nested_get(data: Any, *path: str) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def thinq_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    value = row.get("thinq")
    return value if isinstance(value, dict) else {}


def thinq_context(row: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = thinq_dict(row).get(key)
    return value if isinstance(value, dict) else {}


def clean_status(value: Any) -> str:
    return str(value or "").strip().upper()


def edge_value(row: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        val = nested_get(row, *key.split(".")) if "." in key else row.get(key)
        parsed = as_float(val)
        if parsed is not None:
            return parsed
    return None


def signed_pct_na(value: Any, digits: int = 1, none: str = "N/A") -> str:
    num = as_float(value)
    if num is None:
        return none
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:+.{digits}f}%"


def elo_status(row: Dict[str, Any]) -> str:
    return clean_status(row.get("thinq_elo_status") or nested_get(row, "thinq", "elo", "status"))


def elo_edges(row: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    status = elo_status(row)
    if status and status != "OK":
        return None, None
    overall = edge_value(row, "thinq_overall_elo_edge", "overall_elo_edge", "elo_edge", "thinq.elo.overall_elo_edge")
    surface = edge_value(row, "thinq_surface_elo_edge", "surface_elo_edge", "thinq.elo.surface_elo_edge")
    return overall, surface


def elo_pair_display(row: Dict[str, Any], opponent: bool = False) -> str:
    overall, surface = elo_edges(row)
    if overall is None and surface is None:
        return "N/A | N/A"
    if opponent:
        overall = -overall if overall is not None else None
        surface = -surface if surface is not None else None
    return f"{signed_pct_na(overall)} | {signed_pct_na(surface)}"


def elo_pair_class(row: Dict[str, Any], opponent: bool = False) -> str:
    overall, surface = elo_edges(row)
    value = overall if overall is not None else surface
    if value is None:
        return "neutral"
    if opponent:
        value = -value
        # Opponent row is from opponent perspective. Positive opponent edge goes
        # against the displayed pick and should be orange. Negative opponent edge
        # supports the pick and must not be orange.
        return sign_class(value, mode="opp")
    return sign_class(value)
def as_pct(value: Any, digits: int = 1, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:.{digits}f}%"



def pct_pair(left: Any, right: Any, digits: int = 1) -> str:
    return f"{as_pct(left, digits)} | {as_pct(right, digits)}"

def value_pair(left: Any, right: Any, digits: int = 2) -> str:
    l = as_float(left)
    r = as_float(right)
    lt = "—" if l is None else f"{l:.{digits}f}"
    rt = "—" if r is None else f"{r:.{digits}f}"
    return f"{lt} | {rt}"

def wl_text(value: Any) -> str:
    if isinstance(value, dict):
        w = value.get("wins") if value.get("wins") is not None else value.get("w")
        l = value.get("losses") if value.get("losses") is not None else value.get("l")
        if w is not None or l is not None:
            return f"{fmt_int(w, '0')}-{fmt_int(l, '0')}"
    if isinstance(value, str) and value.strip():
        return esc(value.strip())
    return "—"

def ta_depth_display(row: Dict[str, Any]) -> str:
    return pct_pair(row.get("ta_pick_depth"), row.get("ta_opp_depth"), 0)

def aces_display(row: Dict[str, Any]) -> str:
    p = as_float(row.get("pick_aces_line"))
    o = as_float(row.get("opponent_aces_line"))
    t = as_float(row.get("total_aces_line"))
    if p is None and o is None and t is None:
        return "N/A | N/A | N/A"
    def one(x: Optional[float]) -> str:
        return "N/A" if x is None else f"{x:.1f}"
    return f"{one(p)} | {one(o)} | {one(t)}"

def signed_pct(value: Any, digits: int = 1) -> str:
    num = as_float(value, 0.0) or 0.0
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:+.{digits}f}%"


def fmt_odds(value: Any) -> str:
    num = as_float(value)
    if num is None or num <= 0:
        return "—"
    return f"{num:.2f}"


def fmt_int(value: Any, default: str = "—") -> str:
    try:
        if value is None or value == "":
            return default
        return str(int(float(value)))
    except Exception:
        return default


def normal_status(row: Dict[str, Any]) -> str:
    return str(row.get("status") or row.get("match_status") or row.get("event_status") or "").lower()


def compact_record_label(record: str) -> Tuple[Optional[int], Optional[int]]:
    txt = str(record or "").strip()
    m = re.search(r"(\d+)\D+(\d+)", txt)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def surface_name(row: Dict[str, Any]) -> str:
    return str(row.get("surface") or "Surface").strip() or "Surface"


def card_insights(row: Dict[str, Any], notes: Optional[List[str]] = None, limit: int = 2) -> List[str]:
    """Return compact top insight tags from displayed pick perspective.

    Top tags are limited and de-duplicated:
    - 🔥 means the signal supports the pick.
    - ⚠ means the signal goes against the pick.
    - If surface and general Last 10 show the same record for the same side,
      keep the surface tag and hide the mirrored duplicate.
    - Every tag explicitly says Pick or Opp.
    """
    candidates: List[Tuple[int, str, str]] = []

    def add(priority: int, text: Any, dedupe_key: Optional[str] = None) -> None:
        t = str(text or "").strip()
        if t:
            key = dedupe_key or re.sub(r"\s+", " ", t.replace("🔥 ", "").replace("⚠ ", "")).strip()
            candidates.append((priority, t, key))

    hp, ho = h2h_record(row)
    shp, sho = surface_h2h_record(row)

    # H2H. Surface H2H is skipped when it is the same sample as total H2H.
    if hp is not None and ho is not None and (hp + ho) >= 3 and max(hp, ho) >= 3:
        if hp == 0 or ho == 0 or abs(hp - ho) >= 3:
            icon = "🔥" if hp > ho else "⚠"
            add(96, f"{icon} Pick H2H | {hp}-{ho}", f"h2h:{hp}-{ho}")

    if shp is not None and sho is not None and (shp + sho) >= 3 and max(shp, sho) >= 3:
        duplicate_total = hp == shp and ho == sho
        if not duplicate_total and (shp == 0 or sho == 0 or abs(shp - sho) >= 3):
            icon = "🔥" if shp > sho else "⚠"
            add(94, f"{icon} Pick {surface_name(row)} H2H | {shp}-{sho}", f"surf-h2h:{shp}-{sho}")

    pf, psf = form_records(row, "pick")
    of, osf = form_records(row, "opponent")
    surf = surface_name(row)

    def add_form(priority: int, side_label: str, extra_label: str, rec: str, side: str) -> None:
        w, l = compact_record_label(rec)
        if w is None or l is None or (w + l) < 8:
            return
        icon = None
        qualifier = ""
        if side == "pick":
            if w >= 8:
                icon = "🔥"
                qualifier = "strong"
            elif l >= 7:
                icon = "⚠"
                qualifier = "weak"
        else:
            if l >= 7:
                icon = "🔥"
                qualifier = "weak"
            elif w >= 8:
                icon = "⚠"
                qualifier = "strong"
        if not icon:
            return
        # Keep the visible label short and readable. Surface still has higher
        # priority internally, but we do not print awkward strings like
        # "Opp weak Hard" in the top card tag.
        label = f"{side_label} {qualifier}".strip()
        # Deduplicate general/surface Last 10 same-side same-record. Surface has
        # higher priority, so it wins and the generic duplicate is skipped.
        add(priority, f"{icon} {label} | L10 | {w}-{l}", f"form:{side}:{w}-{l}")

    # Surface before generic, because it is more informative when record is same.
    add_form(92, "Pick", surf, psf, "pick")
    add_form(88, "Pick", "", pf, "pick")
    add_form(86, "Opp", surf, osf, "opponent")
    add_form(84, "Opp", "", of, "opponent")

    # Optional absence fields. Pick absence is a warning; Opp absence supports pick.
    for side, side_label, priority in (("pick", "Pick", 83), ("opponent", "Opp", 82)):
        weeks = None
        for key in (
            f"{side}_surface_absence_weeks",
            f"{side}_weeks_since_surface_match",
            f"{side}_surface_weeks_since_last_match",
        ):
            weeks = as_float(row.get(key))
            if weeks is not None:
                break
        if weeks is not None and weeks >= 26:
            icon = "⚠" if side == "pick" else "🔥"
            add(priority, f"{icon} {side_label} | No {surf} | {int(round(weeks))}w", f"absence:{side}:{surf}:{int(round(weeks))}")

    out: List[str] = []
    seen = set()
    for _, txt, key in sorted(candidates, key=lambda kv: (-kv[0], kv[1])):
        clean = re.sub(r"\s+", " ", txt).strip()
        if clean and key not in seen:
            out.append(clean)
            seen.add(key)
        if len(out) >= limit:
            break
    return out
def card_insights_html(row: Dict[str, Any], notes: Optional[List[str]] = None) -> str:
    insights = card_insights(row, notes, limit=2)
    if not insights:
        return '<div class="card-insights empty-insights"><span>—</span></div>'
    chips = []
    for item in insights[:2]:
        text = str(item or "")
        cls = "positive" if text.startswith("🔥") else "negative" if text.startswith("⚠") else "neutral"
        chips.append(f'<span class="insight-chip {cls}">{esc(text)}</span>')
    return f'<div class="card-insights chip-insights">{"".join(chips)}</div>'

RANK_FALLBACK_DISPLAY = "(X)"


def _clean_player_rank_value(value: Any) -> Optional[int]:
    """Return a real ranking integer or None when the rank is missing/invalid.

    Project rule: if ranking cannot be loaded for any player, render (X).
    Do not leak None, nan, null, blank, 0 or other placeholder values into UI.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"none", "nan", "null", "undefined", "n/a", "na", "-", "—", "x", "(x)"}:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
        if not text or text.lower() in {"none", "nan", "null", "undefined", "n/a", "na", "-", "—", "x"}:
            return None
    try:
        rank = int(float(text))
    except Exception:
        return None
    if rank <= 0:
        return None
    return rank


def player_rank_display(row: Dict[str, Any], side: str) -> str:
    """Return display rank for pick/opponent with TennisApi priority.

    TennisApi/API ranking fields are preferred over legacy TA rank fields. If no
    valid rank is available, UI must show (X), not blank, None or 0.
    """
    side_aliases = [side]
    if side == "pick":
        side_aliases.extend(["player1", "p1", "home", "selected"])
    elif side == "opponent":
        side_aliases.extend(["player2", "p2", "away", "opp"])

    keys: List[str] = []
    for alias in side_aliases:
        keys.extend([
            f"{alias}_api_rank",
            f"{alias}_tennisapi_rank",
            f"{alias}_current_rank",
            f"api_{alias}_rank",
            f"tennisapi_{alias}_rank",
            f"{alias}_ta_rank_display",
            f"{alias}_rank_display",
            f"{alias}_ta_rank",
            f"{alias}_rank",
        ])

    for key in keys:
        rank = _clean_player_rank_value(row.get(key))
        if rank is not None:
            return f"({rank})"

    # Results snapshots sometimes keep ranks under prediction_snapshot.*.
    for root_key in ("prediction_snapshot", "snapshot", "rankings", "api_rankings", "tennisapi"):
        ctx = row.get(root_key)
        if not isinstance(ctx, dict):
            continue
        for alias in side_aliases:
            candidate = ctx.get(alias)
            if isinstance(candidate, dict):
                for k in ("rank", "api_rank", "current_rank", "tennisapi_rank", "ta_rank"):
                    rank = _clean_player_rank_value(candidate.get(k))
                    if rank is not None:
                        return f"({rank})"
            for k in (f"{alias}_api_rank", f"{alias}_rank", f"{alias}_ta_rank"):
                rank = _clean_player_rank_value(ctx.get(k))
                if rank is not None:
                    return f"({rank})"
    return RANK_FALLBACK_DISPLAY


def add_rank(name: Any, row: Dict[str, Any], side: str) -> str:
    return f'{esc(name or "—")} <span class="rank">{esc(player_rank_display(row, side))}</span>'


def pick_name(row: Dict[str, Any]) -> str:
    return str(row.get("pick") or row.get("cloq_pick") or row.get("player") or row.get("player1") or row.get("home") or "—")


def opponent_name(row: Dict[str, Any]) -> str:
    return str(row.get("opponent") or row.get("opp") or row.get("player2") or row.get("away") or "—")


def pick_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("pick_odds", "cloq_pick_odds", "selected_odds", "odds_decimal", "decimal_odds"):
        val = as_float(row.get(key))
        if val and val > 0:
            return val
    val = as_float(row.get("odds"))
    if val and val > 0:
        return val
    return None


def opponent_odds(row: Dict[str, Any]) -> Optional[float]:
    for key in ("opponent_odds", "opp_odds", "cloq_opponent_odds", "opponent_price"):
        val = as_float(row.get(key))
        if val and val > 0:
            return val
    return None


def probability(row: Dict[str, Any]) -> Optional[float]:
    for key in ("corq_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "probability", "cloq_probability"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return None


def thinq_prob(row: Dict[str, Any]) -> Optional[float]:
    """Return displayed model probability for the pick.

    Prefer real ThinQ probability. If ThinQ attach failed but CorQ still carries
    the raw model probability used by MMx, use that as a transparent model
    fallback. Never convert missing ThinQ into a fake 0.0%.
    """
    failed = bool(row.get("thinq_error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (row.get("thinq_flags") or []))
    thinq = row.get("thinq")
    if isinstance(thinq, dict):
        failed = failed or bool(thinq.get("error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (thinq.get("flags") or []))
    for key in (
        "thinq_pick_probability",
        "thinq_probability",
        "top7_thinq_pick_probability",
        "corq_thinq_probability",
        "corq_raw_model_probability",
    ):
        val = as_float(row.get(key))
        if val is not None:
            if failed and abs(val) < 1e-12 and key not in ("corq_raw_model_probability",):
                continue
            return val
    layer = row.get("thinq_probability_layer") or row.get("probability_layer")
    if isinstance(layer, dict):
        val = as_float(layer.get("pick_probability") or layer.get("probability"))
        if val is not None:
            return val
    if isinstance(thinq, dict):
        for key in ("thinq_pick_probability", "thinq_probability", "corq_raw_model_probability"):
            val = as_float(thinq.get(key))
            if val is not None:
                return val
        layer = thinq.get("thinq_probability_layer") or thinq.get("probability_layer")
        if isinstance(layer, dict):
            return as_float(layer.get("pick_probability") or layer.get("probability"))
    return None


def thinq_conf(row: Dict[str, Any]) -> Optional[float]:
    """Return ThinQ data/model confidence, not win probability.

    A 0.0 confidence with THINQ_ATTACH_FAILED means missing data, not true zero
    confidence. Display it as N/A instead of a misleading 0.0%.
    """
    failed = bool(row.get("thinq_error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (row.get("thinq_flags") or []))
    thinq = row.get("thinq")
    if isinstance(thinq, dict):
        failed = failed or bool(thinq.get("error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (thinq.get("flags") or []))
    for key in ("thinq_data_confidence", "thinq_probability_confidence", "thinq_confidence", "thinq_overall_confidence", "data_confidence", "top7_thinq_data_confidence", "top7_thinq_confidence"):
        val = as_float(row.get(key))
        if val is not None:
            if failed and abs(val) < 1e-12:
                continue
            return val
    layer = row.get("thinq_probability_layer")
    if isinstance(layer, dict):
        val = as_float(layer.get("confidence"))
        if val is not None and not (failed and abs(val) < 1e-12):
            return val
    if isinstance(thinq, dict):
        for key in ("thinq_data_confidence", "confidence"):
            val = as_float(thinq.get(key))
            if val is not None and not (failed and abs(val) < 1e-12):
                return val
    return None


def stat_depth(row: Dict[str, Any]) -> Optional[float]:
    failed = bool(row.get("thinq_error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (row.get("thinq_flags") or []))
    thinq = row.get("thinq")
    if isinstance(thinq, dict):
        failed = failed or bool(thinq.get("error")) or "THINQ_ATTACH_FAILED" in set(str(x) for x in (thinq.get("flags") or []))
    for key in ("stat_data_depth", "pick_data_depth", "data_depth", "top7_pick_data_depth"):
        val = as_float(row.get(key))
        if val is not None:
            if failed and abs(val) < 1e-12:
                continue
            return val
    return thinq_conf(row)


def form_depth(row: Dict[str, Any]) -> Optional[float]:
    for key in ("form_data_depth", "form_confidence", "recent_form_confidence"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return None


def pick_edge(row: Dict[str, Any]) -> float:
    for key in ("pick_thinq_edge", "thinq_edge", "thinq_total_edge", "top7_pick_thinq_edge"):
        val = as_float(row.get(key))
        if val is not None:
            return val
    layer = row.get("thinq_probability_layer")
    if isinstance(layer, dict):
        val = as_float(layer.get("edge"))
        if val is not None:
            return val
    p = probability(row)
    if p is None:
        return 0.0
    if p > 1:
        p /= 100.0
    return p - 0.5


def sign_class(value: Any, mode: str = "pick") -> str:
    num = as_float(value, 0.0) or 0.0
    if abs(num) <= 1.0:
        num *= 100.0
    if abs(num) < 0.05:
        return "neutral"
    if mode == "opp":
        return "bad" if num > 0 else "good"
    return "good" if num > 0 else "bad"


def h2h_record(row: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    h2h = thinq_context(row, "h2h")
    total = as_float(row.get("thinq_h2h_total_matches") or row.get("h2h_total_matches") or (h2h.get("total_matches") if isinstance(h2h, dict) else None))
    if total is not None and int(total or 0) <= 0:
        return None, None

    pairs = (
        ("h2h_pick_wins", "h2h_opponent_wins"),
        ("thinq_h2h_pick_wins", "thinq_h2h_opponent_wins"),
    )
    for a, b in pairs:
        if row.get(a) is not None or row.get(b) is not None:
            p = int(as_float(row.get(a), 0) or 0)
            o = int(as_float(row.get(b), 0) or 0)
            if p == 0 and o == 0:
                return None, None
            return p, o

    if isinstance(h2h, dict):
        if h2h.get("pick_wins") is not None or h2h.get("opponent_wins") is not None:
            p = int(as_float(h2h.get("pick_wins"), 0) or 0)
            o = int(as_float(h2h.get("opponent_wins"), 0) or 0)
            if p == 0 and o == 0:
                return None, None
            return p, o
        txt = str(h2h.get("record") or "")
    else:
        txt = ""

    txt = str(row.get("h2h_record") or row.get("thinq_h2h_record") or txt)
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", txt)
    if m:
        p, o = int(m.group(1)), int(m.group(2))
        if p == 0 and o == 0:
            return None, None
        return p, o
    return None, None
def surface_h2h_record(row: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    h2h = thinq_context(row, "h2h")
    total = as_float(row.get("thinq_h2h_same_surface_matches") or row.get("surface_h2h_total_matches") or (h2h.get("same_surface_matches") if isinstance(h2h, dict) else None))
    if total is not None and int(total or 0) <= 0:
        return None, None

    for a, b in (("surface_h2h_pick_wins", "surface_h2h_opponent_wins"), ("thinq_surface_h2h_pick_wins", "thinq_surface_h2h_opponent_wins")):
        if row.get(a) is not None or row.get(b) is not None:
            p = int(as_float(row.get(a), 0) or 0)
            opp_raw = as_float(row.get(b))
            if opp_raw is None and total is not None:
                o = max(int(total or 0) - p, 0)
            else:
                o = int(opp_raw or 0)
            if p == 0 and o == 0:
                return None, None
            return p, o

    if isinstance(h2h, dict):
        pick_w = as_float(h2h.get("same_surface_pick_wins"))
        opp_w = as_float(h2h.get("same_surface_opponent_wins"))
        if pick_w is not None or opp_w is not None or total is not None:
            p = int(pick_w or 0)
            if opp_w is not None:
                o = int(opp_w or 0)
            elif total is not None:
                o = max(int(total or 0) - p, 0)
            else:
                o = 0
            if p == 0 and o == 0:
                return None, None
            return p, o

    txt = str(row.get("surface_h2h_record") or row.get("s_h2h_record") or "")
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", txt)
    if m:
        p, o = int(m.group(1)), int(m.group(2))
        if p == 0 and o == 0:
            return None, None
        return p, o
    return None, None
def h2h_display(row: Dict[str, Any]) -> str:
    nested_h2h = thinq_context(row, "h2h")
    status = str(row.get("h2h_status") or row.get("thinq_h2h_status") or nested_h2h.get("status") or "").upper()
    explicit_display = str(row.get("h2h_display") or nested_h2h.get("display") or "").strip()
    if "NO_PREVIOUS" in status or explicit_display.lower().startswith("no previous"):
        return "No previous matches"
    p, o = h2h_record(row)
    edge = as_float(row.get("h2h_edge") or row.get("thinq_h2h_edge") or nested_h2h.get("edge"))
    if p is None or o is None:
        return "No previous matches" if status in {"NO_DATA", "NO_MATCHES", "NO_PREVIOUS_MATCHES"} else "No data"
    if edge is None:
        return f"{p}W-{o}L"
    return f"{p}W-{o}L · {signed_pct(edge)}"
def h2h_class(row: Dict[str, Any]) -> str:
    p, o = h2h_record(row)
    edge = as_float(row.get("h2h_edge") or row.get("thinq_h2h_edge"), 0.0) or 0.0
    if p is None or o is None:
        return "neutral"
    if p > o or edge > 0:
        return "good"
    if p < o or edge < 0:
        return "bad"
    return "neutral"


def surface_h2h_display(row: Dict[str, Any]) -> str:
    p, o = surface_h2h_record(row)
    if p is None or o is None or (p == 0 and o == 0):
        return "No data"
    edge = as_float(row.get("surface_h2h_edge") or row.get("thinq_surface_h2h_edge") or nested_get(row, "thinq", "h2h", "same_surface_edge"))
    if edge is None:
        return f"{p}W-{o}L"
    return f"{p}W-{o}L · {signed_pct(edge)}"
def surface_h2h_class(row: Dict[str, Any]) -> str:
    p, o = surface_h2h_record(row)
    if p is None or o is None:
        return "neutral"
    if p > o:
        return "good"
    if p < o:
        return "bad"
    return "neutral"


def record_display(record: Any) -> str:
    if isinstance(record, dict):
        count = as_float(record.get("count"))
        w = record.get("wins") if record.get("wins") is not None else record.get("w") if record.get("w") is not None else record.get("win")
        l = record.get("losses") if record.get("losses") is not None else record.get("l") if record.get("l") is not None else record.get("loss")
        if count is not None and count <= 0:
            return "N/A"
        if w is None and l is None:
            return "N/A"
        if as_float(w, 0) == 0 and as_float(l, 0) == 0:
            return "N/A"
        return f"{fmt_int(w, '0')}W-{fmt_int(l, '0')}L"
    txt = str(record or "").strip()
    if not txt or txt.upper() in {"N/A", "NA", "NONE", "NULL", "0-0", "0W-0L"}:
        return "N/A"
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", txt)
    if m:
        if int(m.group(1)) == 0 and int(m.group(2)) == 0:
            return "N/A"
        return f"{m.group(1)}W-{m.group(2)}L"
    return esc(txt)
def form_records(row: Dict[str, Any], side: str) -> Tuple[str, str]:
    prefix = "pick" if side == "pick" else "opponent"
    rf = thinq_context(row, "recent_form") or (row.get("recent_form") if isinstance(row.get("recent_form"), dict) else {})
    status = clean_status(row.get("thinq_recent_form_status") or rf.get("status") or row.get("recent_form_status"))
    player_ctx = rf.get(prefix) if isinstance(rf.get(prefix), dict) else {}
    last10 = player_ctx.get("last10") if isinstance(player_ctx.get("last10"), dict) else {}
    surface = player_ctx.get("surface_last10") if isinstance(player_ctx.get("surface_last10"), dict) else {}
    form = (
        row.get(f"{prefix}_last10_record")
        or row.get(f"{prefix}_form_record")
        or row.get(f"{prefix}_recent_record")
        or rf.get(f"{prefix}_last10_record")
        or rf.get(f"{prefix}_record")
        or last10
    )
    sform = (
        row.get(f"{prefix}_surface_record")
        or row.get(f"{prefix}_surface_last10_record")
        or rf.get(f"{prefix}_surface_record")
        or surface
    )
    out_form = record_display(form)
    out_surface = record_display(sform)
    if status and status != "OK" and out_form == "N/A" and out_surface == "N/A":
        return "N/A", "N/A"
    return out_form, out_surface
def notes_for_row(row: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    for key in ("corq_warning_flags", "risk_flags", "reject_reasons", "top7_quality_reject_reasons", "top7_risk_tags", "flags"):
        val = row.get(key)
        if isinstance(val, list):
            flags.extend(str(x) for x in val if x)
        elif isinstance(val, str) and val:
            flags.append(val)
    if not row.get("odds_pair_available") or pick_odds(row) is None or opponent_odds(row) is None:
        flags.append("MISSING_ODDS")
    h2h_txt = h2h_display(row).lower()
    if h2h_txt.startswith("no previous"):
        flags.append("H2H_NO_PREVIOUS_MATCHES")
    if row.get("recent_form_status") in {"NO_DATA", "PENDING"} or str(row.get("recent_form_status") or "").upper().endswith("PENDING"):
        flags.append("RECENT_FORM_NO_DATA")
    return public_flag_labels(flags, limit=None)


def slugify(value: Any) -> str:
    text = str(value or "match").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "match"


def match_key(row: Dict[str, Any]) -> str:
    for key in ("match_key", "event_id", "match_id", "custom_id", "customId", "id"):
        val = row.get(key)
        if val:
            return slugify(val)
    return slugify(f"{pick_name(row)}-{opponent_name(row)}-{row.get('start_time') or row.get('match_time') or ''}")


def row_match_identity(row: Dict[str, Any]) -> str:
    for key in ("match_key", "event_id", "match_id", "custom_id", "customId", "id"):
        val = row.get(key)
        if val:
            return str(val)
    names = sorted([pick_name(row).lower(), opponent_name(row).lower()])
    return "|".join(names) + "|" + str(row.get("start_time") or row.get("match_time") or "")


def better_all_row(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    def score(r: Dict[str, Any]) -> Tuple[float, float, float, float, float, float]:
        publish = 1.0 if r.get("top7_publishable") or r.get("eligible_for_top7") else 0.0
        return (
            publish,
            as_float(probability(r), 0.0) or 0.0,
            as_float(stat_depth(r), 0.0) or 0.0,
            as_float(pick_edge(r), 0.0) or 0.0,
            as_float(form_depth(r), 0.0) or 0.0,
            as_float(pick_odds(r), 0.0) or 0.0,
        )
    return a if score(a) >= score(b) else b


def dedupe_matches(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        key = row_match_identity(row)
        if key not in by_key:
            by_key[key] = row
            order.append(key)
        else:
            by_key[key] = better_all_row(by_key[key], row)
    return [by_key[k] for k in order]


def bar_html(value: Any) -> str:
    raw = as_float(value)
    if raw is None:
        return '<span class="depth-wrap"><span class="depth-number">N/A</span><span class="depth-bar"><span class="bar-bad" style="width:0%"></span></span></span>'
    pct = raw
    if pct <= 1.0:
        pct *= 100.0
    pct = max(0.0, min(100.0, pct))
    cls = "bar-good" if pct >= 70 else "bar-mid" if pct >= 40 else "bar-bad"
    return f'<span class="depth-wrap"><span class="depth-number">{pct:.0f}%</span><span class="depth-bar"><span class="{cls}" style="width:{pct:.0f}%"></span></span></span>'
def _label_info_key(label: str) -> str:
    key = str(label or "").strip().lower()
    key = key.replace("|", " ").replace("/", " ").replace("%", "pct").replace("Δ", "delta")
    key = key.replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]+", "", key)
    key = re.sub(r"_+", "_", key).strip("_")
    aliases = {
        "p_el_s_e": "p_el_s_e",
        "o_el_s_e": "o_el_s_e",
        "h2h_p_o": "h2h_p_o",
        "s_h2h_p_o": "s_h2h_p_o",
        "p_thinq_edge": "p_thinq_edge",
        "s_data_depth": "s_data_depth",
        "p_f_s_f": "p_f_s_f",
        "o_f_s_f": "o_f_s_f",
        "p_r_edge": "p_r_edge",
        "p_s_edge": "p_s_edge",
        "p_f_qty": "p_f_qty",
        "f_data_depth": "f_data_depth",
        "thinq_prob": "thinq_prob",
        "marq_prob": "marq_prob",
        "thinq_input": "thinq_input",
        "marq_input": "marq_input",
        "corq_final": "corq_final",
        "marq_delta": "marq_delta",
        "sets_o_u": "sets_ou",
        "games_o_u": "games_ou",
        "tbpct": "tb_pct",
        "aces_p_o_t": "aces_p_o_t",
        "df_p_o_t": "df_p_o_t",
        "pick_marq": "pick_marq",
        "opp_marq": "opp_marq",
        "marq_edge": "marq_edge",
        "range_move": "marq_move",
        "clv": "clv",
        "marq_final": "marq_final",
        "odds_gap": "odds_gap",
    }
    return aliases.get(key, key)


def metric_row(label: str, value: str, cls: str = "") -> str:
    return f'<div class="metric-row {esc(cls)}"><span class="metric-label">{esc(label)} {info_icon(_label_info_key(label))}</span><b>{value}</b></div>'


def metric_row_info(label: str, value: str, info_key: str, cls: str = "") -> str:
    return f'<div class="metric-row {esc(cls)}"><span class="metric-label">{esc(label)} {info_icon(info_key)}</span><b>{value}</b></div>'


def info_icon(key: str) -> str:
    tip = explanation_text(key)
    return f'<span class="info info-dot" tabindex="0" role="button" aria-label="{esc(tip)}" data-tip="{esc(tip)}">i</span>'


def start_time(row: Dict[str, Any]) -> str:
    raw = (
        row.get("start_time_utc")
        or row.get("match_time_utc")
        or row.get("commence_time")
        or row.get("start_time")
        or row.get("match_time")
        or row.get("start_time_display")
        or row.get("match_time_display")
        or ""
    )
    text = str(raw or "").strip()
    if not text:
        return "—"
    try:
        if re.fullmatch(r"\d{10,13}", text):
            dt = datetime.fromtimestamp(int(text[:10]), tz=timezone.utc)
        else:
            iso = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                # API values without timezone are treated as UTC source times.
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        return dt.astimezone(WEB_DISPLAY_TIMEZONE).strftime("%H:%M")
    except Exception:
        # Fallback for already formatted strings. Leave them unchanged because
        # HH:MM without date/timezone cannot be converted safely.
        m = re.search(r"\b(\d{1,2}:\d{2})\b", text)
        return m.group(1) if m else text


def start_date(row: Dict[str, Any]) -> str:
    raw = (
        row.get("start_time_utc")
        or row.get("match_time_utc")
        or row.get("commence_time")
        or row.get("start_time")
        or row.get("match_time")
        or row.get("start_time_display")
        or row.get("match_time_display")
        or ""
    )
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        if re.fullmatch(r"\d{10,13}", text):
            dt = datetime.fromtimestamp(int(text[:10]), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        return dt.astimezone(WEB_DISPLAY_TIMEZONE).strftime("%d.%m.%y")
    except Exception:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            try:
                return datetime.fromisoformat(m.group(1)).strftime("%d.%m.%y")
            except Exception:
                return m.group(1)
        return ""


def meta_line(row: Dict[str, Any]) -> str:
    bits = []
    for key in ("tournament", "category", "surface", "best_of"):
        val = row.get(key)
        if val:
            bits.append(str(val))
    return " · ".join(bits) if bits else "—"


def render_logs_enabled() -> bool:
    """Return whether heavy per-match log pages should be rendered.

    Default is OFF because generated log pages and JSON dumps can make the
    GitHub Pages artifact too large and slow to deploy. Enable only for manual
    debugging by setting CORQ_RENDER_ENABLE_LOGS=1.
    """
    return os.getenv("CORQ_RENDER_ENABLE_LOGS", "0").strip().lower() in {"1", "true", "yes", "on"}


def log_link(row: Dict[str, Any]) -> str:
    if not render_logs_enabled():
        return "javascript:void(0)"
    return f'../logs/{esc(match_key(row))}/index.html'


def ensure_logs(rows: List[Dict[str, Any]]) -> None:
    if not render_logs_enabled():
        # Keep the rendered site small and remove stale log pages from previous
        # renders so web-render-only can deploy reliably.
        if LOGS_DIR.exists():
            shutil.rmtree(LOGS_DIR, ignore_errors=True)
        return
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        key = match_key(row)
        path = LOGS_DIR / key
        path.mkdir(parents=True, exist_ok=True)
        data = json.dumps(row, ensure_ascii=False, indent=2, default=str)
        write_text(path / "thinq-log.json", data)
        html_doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Calculation log</title><style>body{{background:#08111f;color:#dbeafe;font-family:Consolas,monospace;padding:24px}}pre{{white-space:pre-wrap;background:#0f1b2d;border:1px solid #23344d;border-radius:14px;padding:18px}}</style></head><body><h1>Calculation log</h1><pre>{esc(data)}</pre></body></html>"""
        write_text(path / "index.html", html_doc)


def render_card(row: Dict[str, Any], rank: Optional[int] = None, page: str = "corq") -> str:
    p = pick_name(row)
    o = opponent_name(row)
    p_odds = pick_odds(row)
    o_odds = opponent_odds(row)
    prob = probability(row)
    pe = pick_edge(row)
    pe_txt = signed_pct(pe)
    pe_state = "Support" if pe > 0.0005 else "Against" if pe < -0.0005 else "Neutral"
    pe_cls = "good" if pe > 0 else "bad" if pe < 0 else "neutral"
    pick_form, pick_sform = form_records(row, "pick")
    opp_form, opp_sform = form_records(row, "opponent")
    notes = notes_for_row(row)
    audit_tags = audit_filter_tags_for_row(row)
    data_tags = "|".join(notes + audit_tags)
    rank_badge = f'<div class="rank-num">#{rank}</div>' if rank else ""
    note_html = "".join(f'<span class="note" data-note="{esc(n)}">{esc(n)}</span>' for n in notes[:8])
    # Top row shows only one positive/support insight. Neutral public notes stay in the bottom row.
    top_tag_html = f'<div class="compact-top-tags">{card_insights_html(row, notes)}</div>'
    odds_gap = as_float(row.get("odds_gap_pct") or row.get("cloq_odds_gap_pct"))
    odds_gap_txt = as_pct(odds_gap, 1) if odds_gap is not None else "—"
    cloq_extra = ""
    html_parts = [
        f'<article class="pick-card" data-start-ts="{int(audit_match_time_utc(row).timestamp()) if audit_match_time_utc(row) else 0}" data-tags="{esc(data_tags)}">',
        '<section class="pick-main compact-v3">',
        '<div class="compact-topline">',
        (rank_badge or f'<div class="rank-num">#{rank or "—"}</div>'),
        f'<div class="compact-datetime-pill"><span class="compact-date">{esc(start_date(row))}</span><span class="compact-clock">{esc(start_time(row))}</span></div>',
        f'<a class="brain goat-badge" href="{log_link(row)}" title="Open calculation log"><img class="card-goat-logo" src="{goat_badge_src()}" alt="AI"></a>',
        top_tag_html,
        '</div>',
        '<div class="compact-player pick-side">'
        '<div class="compact-label">Pick</div>'
        f'<div class="compact-name-row"><span class="compact-name">{esc(p)} <span class="compact-odds inline pick">@ {fmt_odds(p_odds)}</span></span><span class="compact-rank">{esc(player_rank_display(row, "pick"))}</span></div>'
        '</div>',
        '<div class="compact-vs">to beat</div>',
        '<div class="compact-player opp-side no-label">'
        f'<div class="compact-name-row"><span class="compact-name">{esc(o)} <span class="compact-odds inline opp">@ {fmt_odds(o_odds)}</span></span><span class="compact-rank">{esc(player_rank_display(row, "opponent"))}</span></div>'
        '</div>',
        f'<div class="compact-match"><div class="compact-match-row"><span class="compact-meta compact-meta-only">{esc(meta_line(row))}</span></div></div>',
        f'<div class="compact-tags bottom-notes">{note_html}</div>' if note_html else '',
        '</section>',
        render_mmx_box(row),
        '<section class="metric-box">',
        f'<div class="box-head"><span>CorQ {info_icon("corq")}</span><b>{as_pct(prob, 1)}</b></div>',
        metric_row("P EL | S-E", esc(elo_pair_display(row)), elo_pair_class(row)),
        metric_row("O EL | S-E", esc(elo_pair_display(row, opponent=True)), elo_pair_class(row, opponent=True)),
        metric_row("H2H P-O", esc(h2h_display(row)), h2h_class(row)),
        metric_row("S-H2H P-O", esc(surface_h2h_display(row)), surface_h2h_class(row)),
        metric_row("P ThinQ Edge", esc(f"{pe_txt} | {pe_state}"), pe_cls),
        metric_row("S Data Depth", bar_html(stat_depth(row))),
        '</section>',
        
        '<section class="metric-box thinq-box">',
        f'<div class="box-head"><span>ThinQ P | C {info_icon("thinq_pc")}</span><b>{as_pct(thinq_prob(row), 1)} | {as_pct(thinq_conf(row), 1)}</b></div>',
        metric_row("P F | S-F", esc(f"{pick_form} | {pick_sform}")),
        metric_row("O F | S-F", esc(f"{opp_form} | {opp_sform}")),
        metric_row("P R-Edge", signed_pct_na(row.get("recent_form_edge") or row.get("short_form_edge")), sign_class(row.get("recent_form_edge") or row.get("short_form_edge"))),
        metric_row("P S-Edge", signed_pct_na(row.get("surface_recent_form_edge")), sign_class(row.get("surface_recent_form_edge"))),
        metric_row("P F Qty", signed_pct_na(row.get("opponent_quality_edge")), sign_class(row.get("opponent_quality_edge"))),
        metric_row("F Data Depth", bar_html(form_depth(row))),
        '</section>',
        render_sets_games_box(row),
        render_marq_box(row),
        cloq_extra,
        '</article>',
    ]
    return "\n".join(x for x in html_parts if x)



def ta_first_text(row: Dict[str, Any], keys: Iterable[str], default: str = "N/A") -> str:
    for key in keys:
        val = row.get(key)
        if val is None or val == "":
            continue
        txt = str(val).strip()
        if txt and txt.lower() not in {"none", "null", "nan", "—", "-"}:
            return txt
    return default


def ta_depth_label(row: Dict[str, Any]) -> str:
    explicit = ta_first_text(
        row,
        (
            "ta_depth_label",
            "ta_data_depth_label",
            "ta_decision_depth_label",
            "ta_coverage_label",
        ),
        "",
    )
    if explicit:
        return explicit
    vals = [as_float(row.get("ta_pick_depth")), as_float(row.get("ta_opp_depth"))]
    vals = [v * 100.0 if v is not None and abs(v) <= 1.0 else v for v in vals if v is not None]
    if not vals:
        return "N/A"
    avg = sum(vals) / len(vals)
    if avg >= 70:
        return "Good"
    if avg >= 40:
        return "Thin"
    return "Weak"


def ta_winner_read(row: Dict[str, Any]) -> str:
    explicit = ta_first_text(
        row,
        (
            "ta_winner_decision",
            "ta_winner_read",
            "ta_winner_support",
            "ta_pick_support",
        ),
        "",
    )
    if explicit:
        return explicit
    pick_dr = as_float(row.get("ta_pick_surface_dr") or row.get("ta_pick_dr"))
    opp_dr = as_float(row.get("ta_opp_surface_dr") or row.get("ta_opp_dr"))
    if pick_dr is None or opp_dr is None:
        return "N/A"
    diff = pick_dr - opp_dr
    if diff >= 0.08:
        return "Supports Pick"
    if diff <= -0.08:
        return "Supports Opp"
    if abs(diff) <= 0.03:
        return "Neutral"
    return "Slight Pick" if diff > 0 else "Slight Opp"


def ta_match_shape_read(row: Dict[str, Any]) -> str:
    explicit = ta_first_text(
        row,
        (
            "ta_match_shape",
            "ta_shape",
            "ta_match_type",
        ),
        "",
    )
    if explicit:
        return explicit
    pick_dr = as_float(row.get("ta_pick_surface_dr") or row.get("ta_pick_dr"))
    opp_dr = as_float(row.get("ta_opp_surface_dr") or row.get("ta_opp_dr"))
    if pick_dr is None or opp_dr is None:
        return "N/A"
    diff = abs(pick_dr - opp_dr)
    if diff <= 0.03:
        return "Competitive"
    if diff >= 0.12:
        return "One-sided"
    return "Moderate Edge"


def ta_aces_input_status(row: Dict[str, Any]) -> str:
    return ta_first_text(
        row,
        (
            "ta_aces_decision",
            "ta_aces_input_status",
            "ta_aces_status",
        ),
        aces_display(row),
    )


def compact_reason(value: Any) -> str:
    if isinstance(value, list):
        items = [str(x).strip() for x in value if str(x).strip()]
        return " | ".join(items[:2]) if items else "—"
    text = str(value or "").strip()
    return text or "—"


def ta_signal_conf_display(row: Dict[str, Any]) -> str:
    conf = as_float(row.get("ta_signal_confidence") or row.get("ta_decision_confidence"))
    strength = str(row.get("ta_signal_strength") or "").strip()
    if conf is None:
        return strength or "N/A"
    pct = f"{conf * 100:.0f}%" if conf <= 1 else f"{conf:.0f}%"
    return f"{strength} | {pct}" if strength else pct


def clean_signal_text(value: Any, fallback: str = "No Clear Signal") -> str:
    text = str(value or "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "—", "-"}:
        return fallback
    return text


def pct_or_na(value: Any) -> str:
    return as_pct(value, 1) if as_float(value) is not None else "N/A"


def sets_games_signal(row: Dict[str, Any]) -> Dict[str, str]:
    """Build a bettor-facing Sets/Games signal from TA first, then ThinQ fallback.

    This prevents raw numbers like 2.45 projected sets from being shown as the
    main UI output without an interpretation.
    """
    # TA signal wins if available and meaningful.
    ta_label = clean_signal_text(row.get("ta_signal_label") or row.get("ta_signal"), "")
    ta_market = str(row.get("ta_signal_market") or "").strip().lower()
    if ta_label and ta_label != "No Clear Signal" and ta_market in {"sets", "games", "sets_games", "tiebreak"}:
        return {
            "source": "TA",
            "signal": ta_label,
            "action": clean_signal_text(row.get("ta_signal_action"), "Use TA signal with market price check"),
            "confidence": ta_signal_conf_display(row),
        }

    decider = as_float(row.get("ta_decider_probability") or row.get("thinq_decider_probability") or row.get("three_sets_probability") or row.get("decider_probability"))
    tb = as_float(row.get("ta_tiebreak_probability") or row.get("thinq_tiebreak_probability") or row.get("tie_break_probability") or row.get("tiebreak_probability"))
    projected_sets = as_float(row.get("ta_projected_sets") or row.get("thinq_projected_sets") or row.get("projected_sets") or row.get("sets"))
    projected_games = as_float(row.get("ta_projected_games") or row.get("thinq_projected_games") or row.get("projected_games") or row.get("games"))
    games_read = clean_signal_text(row.get("ta_games_decision") or row.get("games_signal") or row.get("over_under_display") or row.get("ou_display"), "")
    conf = as_float(row.get("ta_signal_confidence") or row.get("thinq_match_dynamics_confidence") or row.get("data_confidence"))
    conf_txt = pct_or_na(conf)

    signal = "No Clear Sets/Games Signal"
    action = "No automatic set/games action"
    source = "TA/ThinQ"

    if decider is not None and decider >= 0.46:
        signal = "3 Sets Risk"
        action = "Avoid straight-sets angle; consider over-games only if line is fair"
    elif projected_sets is not None and projected_sets >= 2.35:
        signal = "3 Sets Lean"
        action = "Avoid 2-0 assumptions; check over-games market"
    elif tb is not None and tb >= 0.34:
        signal = "Tie-break Risk"
        action = "Be cautious with low-games unders and straight-set assumptions"
    elif projected_games is not None and projected_games >= 24.0:
        signal = "Games Over Lean"
        action = "Consider over-games angle if sportsbook line is not inflated"
    elif projected_games is not None and projected_games <= 20.0:
        signal = "Games Under Lean"
        action = "Consider under-games angle if line is high enough"
    elif games_read and games_read not in {"N/A", "Neutral"}:
        signal = games_read
        action = "Use games lean only with market price check"

    return {"source": source, "signal": signal, "action": action, "confidence": conf_txt}


def sets_lean_display(row: Dict[str, Any]) -> str:
    projected_sets = as_float(row.get("ta_projected_sets") or row.get("thinq_projected_sets") or row.get("projected_sets") or row.get("sets"))
    decider = as_float(row.get("ta_decider_probability") or row.get("thinq_decider_probability") or row.get("three_sets_probability") or row.get("decider_probability"))
    if projected_sets is None and decider is None:
        return "N/A"
    if decider is not None and decider >= 0.46:
        return "3 sets risk"
    if projected_sets is not None:
        if projected_sets >= 2.35:
            return "3 sets lean"
        if projected_sets <= 2.15:
            return "2 sets lean"
        return "neutral"
    return "3 sets risk" if decider and decider >= 0.43 else "neutral"


def games_lean_display(row: Dict[str, Any]) -> str:
    explicit = clean_signal_text(row.get("ta_games_decision") or row.get("games_signal") or row.get("over_under_display") or row.get("ou_display"), "")
    projected_games = as_float(row.get("ta_projected_games") or row.get("thinq_projected_games") or row.get("projected_games") or row.get("games"))
    if explicit and explicit not in {"N/A", "Neutral"}:
        return explicit
    if projected_games is None:
        return "N/A"
    if projected_games >= 24.0:
        return f"Over lean ({projected_games:.1f})"
    if projected_games <= 20.0:
        return f"Under lean ({projected_games:.1f})"
    return f"Neutral ({projected_games:.1f})"

def render_ta_box(row: Dict[str, Any]) -> str:
    """Render Tennis Abstract as bettor-facing signal output."""
    raw_signal = row.get("ta_signal_label") or row.get("ta_signal")
    signal = clean_signal_text(raw_signal, "No Clear TA Signal")
    action = clean_signal_text(row.get("ta_signal_action"), "No automatic TA action")
    reasons = compact_reason(row.get("ta_signal_reasons") or row.get("ta_decision_notes"))
    market = clean_signal_text(row.get("ta_signal_market"), "")
    return "\n".join([
        '<section class="metric-box small-box ta-signal-box">',
        f'<div class="box-head"><span>TA Signal {info_icon("ta")}</span><b>{esc(market)}</b></div>',
        metric_row("Signal", esc(signal)),
        metric_row("Action", esc(action)),
        metric_row("Confidence", esc(ta_signal_conf_display(row))),
        metric_row("Reason", esc(reasons)),
        metric_row("Winner Read", esc(clean_signal_text(ta_winner_read(row), "N/A"))),
        metric_row("Sets Read", esc(clean_signal_text(ta_first_text(row, ("ta_sets_decision", "ta_sets_read", "ta_set_direction", "ta_sets_direction")), "N/A"))),
        metric_row("Games Read", esc(clean_signal_text(ta_first_text(row, ("ta_games_decision", "ta_games_read", "ta_games_direction", "ta_games_lean")), "N/A"))),
        metric_row("TA Depth", esc(ta_depth_label(row))),
        '</section>',
    ])
def _ctx(row: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def _first_data_value(row: Dict[str, Any], *keys: str, contexts: Tuple[str, ...] = ("sets_games", "marq")) -> Any:
    for key in keys:
        if "." in key:
            value = nested_get(row, *key.split("."))
        else:
            value = row.get(key)
        if value not in (None, ""):
            return value
    for ctx_key in contexts:
        ctx = _ctx(row, ctx_key)
        for key in keys:
            short = key.split(".")[-1]
            value = ctx.get(short)
            if value not in (None, ""):
                return value
    return None


def market_pct(value: Any, digits: int = 1, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:.{digits}f}%"


def signed_market_pct(value: Any, digits: int = 1, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:+.{digits}f}%"


def compact_market_line(selection: Any, probability: Any = None, none: str = "—") -> str:
    text = str(selection or "").strip()
    if not text:
        side = str(_first_data_value({}, "") or "").strip()
    prob = as_float(probability)
    if not text:
        return none
    return f"{text} {market_pct(prob, 0)}" if prob is not None else text


def _side_line(action: Any, line: Any) -> str:
    action_txt = str(action or "").strip().upper()
    line_num = as_float(line)
    if not action_txt and line_num is None:
        return ""
    if action_txt in {"OVER", "O"}:
        prefix = "O"
    elif action_txt in {"UNDER", "U"}:
        prefix = "U"
    else:
        prefix = action_txt
    if line_num is None:
        return prefix or ""
    return f"{prefix}{line_num:.1f}" if prefix else f"{line_num:.1f}"


def market_pick_display(row: Dict[str, Any], prefix: str, default_line: Optional[float] = None) -> str:
    selection = _first_data_value(
        row,
        f"{prefix}_selection",
        f"{prefix}_display",
        f"sets_games_{prefix}_selection",
        f"sets_games_{prefix}_display",
    )
    probability = _first_data_value(
        row,
        f"{prefix}_probability_pct",
        f"{prefix}_probability",
        f"{prefix}_pct",
        f"sets_games_{prefix}_probability_pct",
        f"sets_games_{prefix}_probability",
        f"sets_games_{prefix}_pct",
    )
    if selection not in (None, ""):
        return compact_market_line(selection, probability)
    action = _first_data_value(row, f"{prefix}_side", f"{prefix}_action", f"sets_games_{prefix}_side", f"sets_games_{prefix}_action")
    line = _first_data_value(row, f"{prefix}_line", f"sets_games_{prefix}_line")
    # Do not display a bookmaker-style line unless at least one real signal is
    # present. The default_line only labels an existing probability/action; it
    # must not create a fake pick by itself.
    if line is None and default_line is not None and (action not in (None, "") or probability not in (None, "")):
        line = default_line
    text = _side_line(action, line)
    return compact_market_line(text, probability)


def _pct_input_value(value: Any, high: float = 60.0) -> Optional[float]:
    num = as_float(value)
    if num is None:
        return None
    if 0 < num <= 1.0:
        num *= 100.0
    if 0 <= num <= high:
        return num
    return None


def _recursive_pct_value(obj: Any, wanted_keys: Tuple[str, ...], high: float) -> Optional[float]:
    """Find a percentage deeply in nested TA/market structures."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_norm = str(key).lower().replace(" ", "_").replace("-", "_")
            if key_norm in wanted_keys:
                pct = _pct_input_value(value, high=high)
                if pct is not None:
                    return pct
        # Prefer obvious stat containers first.
        preferred = ("overall", "surface", "last52", "career", "stats", "profile", "ta", "data")
        for key in preferred:
            if key in obj:
                pct = _recursive_pct_value(obj.get(key), wanted_keys, high)
                if pct is not None:
                    return pct
        for value in obj.values():
            pct = _recursive_pct_value(value, wanted_keys, high)
            if pct is not None:
                return pct
    elif isinstance(obj, list):
        for item in obj:
            pct = _recursive_pct_value(item, wanted_keys, high)
            if pct is not None:
                return pct
    return None


def _side_nested_pct(row: Dict[str, Any], family: str, which: str, high: float) -> Optional[float]:
    if family == "aces":
        wanted = ("a%", "ace%", "ace_pct", "ace_percent", "ace_percentage", "aces_pct", "aces_percent", "ta_ace_pct")
    else:
        wanted = ("df%", "df_pct", "df_percent", "df_percentage", "double_fault_pct", "double_fault_percent", "double_faults_pct", "double_faults_percent", "ta_df_pct")
    side_keys = (
        ("pick", "p", "player", "pick_profile", "pick_stats", "pick_ta", "ta_pick", "ta_pick_profile")
        if which == "pick"
        else ("opponent", "opp", "o", "opponent_profile", "opp_profile", "opponent_stats", "opp_stats", "ta_opp", "ta_opponent", "ta_opp_profile")
    )
    containers = [row.get(k) for k in side_keys if isinstance(row.get(k), (dict, list))]
    ctx = row.get("ta_context")
    if isinstance(ctx, dict):
        # Build-match TA context commonly stores these as flat keys.
        flat_keys = (
            ("ta_pick_ace_pct", "pick_ace_pct") if family == "aces" and which == "pick" else
            ("ta_opp_ace_pct", "ta_opponent_ace_pct", "opponent_ace_pct", "opp_ace_pct") if family == "aces" else
            ("ta_pick_df_pct", "pick_df_pct", "pick_double_fault_pct") if which == "pick" else
            ("ta_opp_df_pct", "ta_opponent_df_pct", "opponent_df_pct", "opp_df_pct", "opponent_double_fault_pct")
        )
        for key in flat_keys:
            pct = _pct_input_value(ctx.get(key), high=high)
            if pct is not None:
                return pct
        containers.extend(ctx.get(k) for k in side_keys if isinstance(ctx.get(k), (dict, list)))
        # Some TA contexts use nested player sides under generic containers.
        for generic in ("players", "profiles", "stats", "ta_profiles"):
            value = ctx.get(generic)
            if isinstance(value, dict):
                containers.extend(value.get(k) for k in side_keys if isinstance(value.get(k), (dict, list)))
    for container in containers:
        pct = _recursive_pct_value(container, wanted, high)
        if pct is not None:
            return pct
    return None


def _projected_games_for_props(row: Dict[str, Any]) -> Optional[float]:
    for key in (
        "projected_total_games",
        "expected_games",
        "ta_projected_games",
        "thinq_projected_games",
        "projected_games",
        "games_projected",
        "games",
        "games_line",
        "total_games_line",
    ):
        val = as_float(row.get(key))
        if val is not None and val > 0:
            return val
    return None


def _prop_projection_from_pct(row: Dict[str, Any], family: str, side: str) -> Optional[float]:
    games = _projected_games_for_props(row)
    if games is None:
        return None

    if family == "aces":
        pct_keys = {
            "pick": ("api_pick_ace_pct", "ta_pick_ace_pct", "pick_ace_pct", "pick_aces_pct", "pick_ace_percent", "pick_aces_percent"),
            "opponent": ("api_opp_ace_pct", "api_opponent_ace_pct", "ta_opp_ace_pct", "ta_opponent_ace_pct", "opponent_ace_pct", "opp_ace_pct", "opponent_aces_pct", "opponent_ace_percent"),
        }
        high = 60.0
    else:
        pct_keys = {
            "pick": ("api_pick_df_pct", "ta_pick_df_pct", "pick_df_pct", "pick_double_fault_pct", "pick_double_faults_pct", "df_pick_pct", "pick_df_percent"),
            "opponent": ("api_opp_df_pct", "api_opponent_df_pct", "ta_opp_df_pct", "ta_opponent_df_pct", "opponent_df_pct", "opp_df_pct", "opponent_double_fault_pct", "opponent_double_faults_pct", "df_opponent_pct", "opponent_df_percent"),
        }
        high = 30.0

    def one(which: str) -> Optional[float]:
        for pct_key in pct_keys[which]:
            pct = _pct_input_value(row.get(pct_key), high=high)
            if pct is not None:
                service_points = (games / 2.0) * 6.2
                return service_points * (pct / 100.0)
        pct = _side_nested_pct(row, family, which, high)
        if pct is not None:
            service_points = (games / 2.0) * 6.2
            return service_points * (pct / 100.0)
        return None

    pick_proj = one("pick")
    opp_proj = one("opponent")
    if side == "pick":
        return pick_proj
    if side == "opponent":
        return opp_proj
    if side == "total" and pick_proj is not None and opp_proj is not None:
        return pick_proj + opp_proj
    return None


def _triplet_projection_fallback(row: Dict[str, Any], family: str, side: str) -> Optional[float]:
    explicit_keys = {
        "aces": {
            "pick": ("pick_aces_projection", "api_pick_aces_projection", "pick_aces"),
            "opponent": ("opponent_aces_projection", "api_opponent_aces_projection", "api_opp_aces_projection", "opponent_aces", "opp_aces"),
            "total": ("total_aces_projection", "api_total_aces_projection", "total_aces"),
        },
        "df": {
            "pick": ("pick_df_projection", "api_pick_df_projection", "df_pick", "pick_df", "pick_double_faults"),
            "opponent": ("opponent_df_projection", "api_opponent_df_projection", "api_opp_df_projection", "df_opponent", "opponent_df", "opp_df", "opponent_double_faults"),
            "total": ("total_df_projection", "api_total_df_projection", "df_total", "total_df", "total_double_faults"),
        },
    }
    for key in explicit_keys.get(family, {}).get(side, ()):
        val = as_float(row.get(key))
        if val is not None:
            return val
    return _prop_projection_from_pct(row, family, side)



def _api_h2h_pm_triplet(row: Dict[str, Any], family: str) -> Optional[str]:
    """Display real API H2H per-match values when available.

    These are not betting lines and not percentages. They come from TennisAPI H2H
    totals divided by statMatchesPlayed/matchesCount. If unavailable, return
    None so the regular market/projection display can decide what to show.
    """
    if family == "aces":
        p = as_float(row.get("api_pick_aces_per_match"))
        o = as_float(row.get("api_opp_aces_per_match"))
    else:
        p = as_float(row.get("api_pick_double_faults_per_match"))
        o = as_float(row.get("api_opp_double_faults_per_match"))
    if p is None and o is None:
        return None
    total = (p or 0.0) + (o or 0.0) if p is not None and o is not None else None
    def one(value: Optional[float]) -> str:
        return "N/A" if value is None else f"{value:.1f}"
    return f"{one(p)} | {one(o)} | {one(total)}"

def triplet_market_display(row: Dict[str, Any], family: str) -> str:
    api_pm = _api_h2h_pm_triplet(row, family)
    if api_pm is not None:
        return api_pm
    aliases = {
        "aces": (
            ("pick_aces", "p_aces", "aces_pick"),
            ("opponent_aces", "opp_aces", "o_aces", "aces_opponent"),
            ("total_aces", "t_aces", "aces_total"),
        ),
        "df": (
            ("pick_df", "p_df", "pick_double_faults", "double_faults_pick"),
            ("opponent_df", "opp_df", "o_df", "opponent_double_faults", "double_faults_opponent"),
            ("total_df", "t_df", "total_double_faults", "double_faults_total"),
        ),
    }
    side_names = ("pick", "opponent", "total")
    parts: List[str] = []
    for idx, group in enumerate(aliases.get(family, ())):  # pick, opponent, total
        value = ""
        for prefix in group:
            value = market_pick_display(row, prefix, None)
            if value != "—":
                break
        if value == "—" or not value:
            proj = _triplet_projection_fallback(row, family, side_names[idx])
            if proj is not None:
                value = f"{proj:.1f}"
        parts.append(value if value else "—")
    return " | ".join(parts) if parts else "— | — | —"


def abs_market_pct(value: Any, digits: int = 1, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{abs(num):.{digits}f}%"


def tiebreak_pct_display(row: Dict[str, Any]) -> str:
    value = _first_data_value(
        row,
        "sets_games_tiebreak_probability",
        "sets_games_tb_probability",
        "tb_probability",
        "tb_pct",
        "ta_tb_pct",
        "ta_tiebreak_pct",
        "tie_break_probability",
        "tiebreak_probability",
        "ta_tiebreak_probability",
        "thinq_tiebreak_probability",
    )
    return market_pct(value, 1)


def _candidate_text(candidate: Any, require_positive_edge: bool = False) -> str:
    if isinstance(candidate, str):
        text = candidate.strip()
        return text if text else "—"
    if not isinstance(candidate, dict):
        return "—"
    selection = (
        candidate.get("selection")
        or candidate.get("pick")
        or candidate.get("market")
        or candidate.get("bet")
        or candidate.get("label")
        or candidate.get("name")
    )
    probability = candidate.get("probability_pct") or candidate.get("probability") or candidate.get("model_probability_pct") or candidate.get("model_probability")
    edge = candidate.get("edge_pct") or candidate.get("edge") or candidate.get("value_edge_pct") or candidate.get("value_edge")
    edge_num = as_float(edge)
    if require_positive_edge and (edge_num is None or edge_num <= 0):
        return "—"
    text = str(selection or "").strip()
    if not text:
        return "—"
    parts = [text]
    if as_float(probability) is not None:
        parts.append(market_pct(probability, 0))
    if edge_num is not None:
        parts.append(signed_market_pct(edge, 1))
    return " | ".join(parts)


def _first_candidate(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = _first_data_value(row, key)
        if isinstance(value, list):
            for item in value:
                if item:
                    return item
        elif value not in (None, ""):
            return value
    return None


def best_bet_display(row: Dict[str, Any]) -> str:
    explicit = _first_data_value(
        row,
        "best_bet_display",
        "best_bet",
        "best_model_bet",
        "sets_games_best_bet",
        "model_best_bet",
    )
    if explicit not in (None, ""):
        return _candidate_text(explicit)
    candidate = _first_candidate(row, "best_bet_candidate", "sets_games_best_candidate", "sets_games_value_candidates")
    text = _candidate_text(candidate)
    if text != "—":
        return text
    return compact_market_line(
        _first_data_value(row, "sets_games_best_value", "sets_games_best_total", "best_total", "best_ou"),
        _first_data_value(row, "sets_games_best_value_probability", "sets_games_best_total_probability", "best_total_probability", "best_ou_probability"),
    )


def value_bet_display(row: Dict[str, Any]) -> str:
    explicit = _first_data_value(
        row,
        "value_bet_display",
        "value_bet",
        "best_value_bet",
        "sets_games_value_bet",
        "marq_value_bet",
    )
    if explicit not in (None, ""):
        return _candidate_text(explicit)
    candidate = _first_candidate(row, "value_bet_candidate", "sets_games_value_bet_candidate", "sets_games_value_candidates")
    return _candidate_text(candidate, require_positive_edge=True)


def move_signal_display(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Pending"
    upper = text.upper().replace("_", " ")
    if upper in {"UNKNOWN", "PENDING", "NO DATA", "NONE"}:
        return "Pending"
    if upper == "STABLE":
        return "Stable"
    return " ".join(part.capitalize() for part in upper.split())


def marq_range_display(row: Dict[str, Any]) -> str:
    explicit = _first_data_value(row, "marq_internal_range", "marq_move_range", "move_range", "range")
    if explicit not in (None, ""):
        return str(explicit)
    earliest = _first_data_value(row, "marq_initial_pick_odds", "move_earliest_odds", "initial_pick_odds")
    latest = _first_data_value(row, "marq_current_pick_odds", "move_latest_odds", "current_pick_odds")
    old = as_float(earliest)
    new = as_float(latest)
    if old is None or new is None:
        return "—"
    return f"{old:.2f} -> {new:.2f}"




def pp_display(value: Any, digits: int = 1, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    return f"{num:+.{digits}f}pp"



def _ratio_int(value: Any) -> Optional[int]:
    num = as_float(value)
    if num is None:
        return None
    if abs(num) <= 1.0:
        num *= 100.0
    return int(round(num))


def mmx_mix_display(row: Dict[str, Any]) -> str:
    """Compact Model Mix label for the MMx box header."""
    thinq_weight = _first_data_value(
        row,
        "corq_model_weight",
        "corq_thinq_weight",
        "thinq_weight",
        "model_mix_thinq_weight",
        "corq_model_mix_thinq_weight",
    )
    marq_weight = _first_data_value(
        row,
        "corq_market_weight",
        "corq_marq_weight",
        "marq_weight",
        "model_mix_marq_weight",
        "corq_model_mix_marq_weight",
    )
    t = _ratio_int(thinq_weight)
    m = _ratio_int(marq_weight)
    if t is not None or m is not None:
        if t is None and m is not None:
            t = max(0, 100 - m)
        if m is None and t is not None:
            m = max(0, 100 - t)
        return f"ThinQ {t} | MarQ {m}"

    label = str(row.get("corq_model_mix_label") or row.get("model_mix_label") or "").strip()
    if label:
        found = re.findall(r"(ThinQ|MarQ)\s*([0-9]+(?:\.[0-9]+)?)\s*%?", label, flags=re.I)
        values = {name.lower(): int(round(float(num))) for name, num in found}
        if "thinq" in values or "marq" in values:
            t = values.get("thinq")
            m = values.get("marq")
            if t is None and m is not None:
                t = max(0, 100 - m)
            if m is None and t is not None:
                m = max(0, 100 - t)
            return f"ThinQ {t} | MarQ {m}"
        return label.replace("%", "").replace("/", "|").replace("  ", " ")
    return "ThinQ 100 | MarQ 0"


def marq_delta_pp(row: Dict[str, Any]) -> Optional[float]:
    explicit = _first_data_value(
        row,
        "corq_market_adjustment_pp",
        "corq_marq_delta_pp",
        "marq_delta_pp",
        "market_adjustment_pp",
        "marq_adjustment_pp",
    )
    num = as_float(explicit)
    if num is not None:
        return num
    marq_prob = as_float(_first_data_value(row, "corq_market_probability", "marq_pick_probability", "marq_crowd_pick_pct", "market_pick_probability"))
    final_prob = as_float(_first_data_value(row, "corq_calibrated_probability", "corq_probability", "corq_estimated_win_probability"))
    if marq_prob is None or final_prob is None:
        return None
    if abs(marq_prob) <= 1.0:
        marq_prob *= 100.0
    if abs(final_prob) <= 1.0:
        final_prob *= 100.0
    return round(marq_prob - final_prob, 2)


def _projection_line(value: Any) -> str:
    num = as_float(value)
    if num is None:
        return "—"
    return f"{num:.1f}"


def sets_projection_display(row: Dict[str, Any]) -> str:
    projected = _first_data_value(row, "ta_projected_sets", "thinq_projected_sets", "projected_sets", "sets_projected")
    lean = sets_lean_display(row)
    text = _projection_line(projected)
    if text != "—" and lean and lean != "N/A":
        return f"{text} | {lean}"
    return lean if lean and lean != "N/A" else text


def games_projection_display(row: Dict[str, Any]) -> str:
    projected = _first_data_value(row, "ta_projected_games", "thinq_projected_games", "projected_total_games", "expected_games", "projected_games", "games_projected")
    lean = games_lean_display(row)
    text = _projection_line(projected)
    if text != "—" and lean and lean != "N/A":
        lean_clean = re.sub(r"\s*\([^)]*\)\s*$", "", lean).strip()
        return f"{text} | {lean_clean}" if lean_clean else text
    return lean if lean and lean != "N/A" else text




def _projection_value(row: Dict[str, Any], keys: Iterable[str]) -> str:
    value = _first_data_value(row, *tuple(keys))
    return _projection_line(value)


def sets_games_projection_pair(row: Dict[str, Any]) -> str:
    sets_text = _projection_value(row, ("ta_projected_sets", "thinq_projected_sets", "projected_sets", "sets_projected"))
    games_text = _projection_value(row, ("ta_projected_games", "thinq_projected_games", "projected_total_games", "expected_games", "projected_games", "games_projected"))
    return f"{sets_text} | {games_text}"


def market_pair_display(row: Dict[str, Any], left_prefix: str, right_prefix: str, left_default: Optional[float] = None, right_default: Optional[float] = None) -> str:
    left = market_pick_display(row, left_prefix, left_default)
    right = market_pick_display(row, right_prefix, right_default)
    return f"{left} | {right}"


def marq_range_move_display(row: Dict[str, Any]) -> str:
    move_range = marq_range_display(row)
    move_signal = move_signal_display(_first_data_value(row, "marq_internal_move_signal", "marq_display_move_signal", "marq_move_signal", "market_move"))
    return f"{move_range} | {move_signal}"


def _present_stat(row: Dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = _first_data_value(row, key)
        if value not in (None, "", "N/A", "—", "-"):
            return True
    return False


def s_data_depth(row: Dict[str, Any]) -> Optional[float]:
    """Return real Sets/Games data quality from TA-derived data only.

    This deliberately does not fall back to ThinQ/model confidence.  The score is
    based on real sample coverage and real field completeness for both players:
    50% sample depth + 50% stat-field completeness.  If no TA/stat data exists,
    return None so the UI displays N/A instead of a fake high percentage.
    """
    explicit = _first_data_value(row, "s_data_depth", "sets_games_data_depth", "ta_sets_games_depth")
    explicit_num = as_float(explicit)
    if explicit_num is not None:
        if explicit_num <= 1.0:
            explicit_num *= 100.0
        if explicit_num <= 0.0:
            # Legacy pipeline sometimes wrote 0 when TA/stat data was simply absent.
            # Do not render that as real 0% data depth unless another TA/stat field is present.
            candidate_fields = (
                "ta_pick_matches", "ta_opp_matches", "ta_pick_set_pct", "ta_opp_set_pct",
                "ta_pick_game_pct", "ta_opp_game_pct", "ta_pick_tb_pct", "ta_opp_tb_pct",
                "ta_pick_ace_pct", "ta_opp_ace_pct", "ta_pick_df_pct", "ta_opp_df_pct",
                "ta_pick_rpw_pct", "ta_opp_rpw_pct", "ta_pick_surface_dr", "ta_opp_surface_dr",
            )
            if not any(_present_stat(row, key) for key in candidate_fields):
                return None
        return max(0.0, min(100.0, explicit_num))

    p_matches = as_float(_first_data_value(row, "ta_pick_matches", "pick_ta_matches"))
    o_matches = as_float(_first_data_value(row, "ta_opp_matches", "ta_opponent_matches", "opp_ta_matches"))
    sample_values = [m for m in (p_matches, o_matches) if m is not None]

    stat_pairs = [
        ("ta_pick_set_pct", "ta_opp_set_pct"),
        ("ta_pick_game_pct", "ta_opp_game_pct"),
        ("ta_pick_tb_pct", "ta_opp_tb_pct"),
        ("ta_pick_ace_pct", "ta_opp_ace_pct"),
        ("ta_pick_df_pct", "ta_opp_df_pct"),
        ("ta_pick_rpw_pct", "ta_opp_rpw_pct"),
        ("ta_pick_surface_dr", "ta_opp_surface_dr"),
    ]
    total_fields = len(stat_pairs) * 2
    present_fields = 0
    for pick_key, opp_key in stat_pairs:
        present_fields += 1 if _present_stat(row, pick_key) else 0
        present_fields += 1 if _present_stat(row, opp_key) else 0

    if not sample_values and present_fields == 0:
        return None

    # 52 recent matches is the TA last-52 target sample. Anything less is scaled
    # proportionally, and missing one side is treated as incomplete sample data.
    sample_scores = [(max(0.0, min(m, 52.0)) / 52.0) for m in sample_values]
    if len(sample_scores) < 2:
        sample_scores += [0.0] * (2 - len(sample_scores))
    sample_score = (sum(sample_scores[:2]) / 2.0) * 50.0
    completeness_score = (present_fields / total_fields) * 50.0 if total_fields else 0.0
    return round(max(0.0, min(100.0, sample_score + completeness_score)), 1)

def render_mmx_box(row: Dict[str, Any]) -> str:
    """Compact CorQ Model Mix diagnostics box."""
    thinq_prob_value = _first_data_value(row, "corq_raw_model_probability", "thinq_pick_probability", "thinq_probability", "top7_thinq_pick_probability")
    marq_prob_value = _first_data_value(row, "corq_market_probability", "marq_pick_probability", "marq_crowd_pick_pct", "market_pick_probability")
    thinq_input = row.get("corq_thinq_input_pp")
    marq_input = row.get("corq_marq_input_pp")
    final_prob = _first_data_value(row, "corq_calibrated_probability", "corq_probability", "corq_estimated_win_probability")
    delta = marq_delta_pp(row)
    return "\n".join(
        [
            '<section class="metric-box mmx-box">',
            f'<div class="box-head"><span>MMx {info_icon("mmx")}</span><b>{esc(mmx_mix_display(row))}</b></div>',
            metric_row("ThinQ Prob", as_pct(thinq_prob_value, 1)),
            metric_row("MarQ Prob", as_pct(marq_prob_value, 1)),
            metric_row("ThinQ Input", pp_display(thinq_input, 1), sign_class(thinq_input)),
            metric_row("MarQ Input", pp_display(marq_input, 1), sign_class(marq_input)),
            metric_row("CorQ Final", as_pct(final_prob, 1)),
            metric_row("MarQ Δ", pp_display(delta, 1), sign_class(delta)),
            '</section>',
        ]
    )

def render_sets_games_box(row: Dict[str, Any]) -> str:
    sets_games_value = sets_games_projection_pair(row)
    sets_ou_value = market_pick_display(row, "sets", 2.5)
    games_ou_value = market_pick_display(row, "games", 23.5)
    return "\n".join([
        '<section class="metric-box small-box sets-signal-box">',
        f'<div class="box-head"><span>Sets / Games {info_icon("sets_games")}</span><b>{esc(sets_games_value)}</b></div>',
        metric_row("Sets o|u", esc(sets_ou_value)),
        metric_row("Games o|u", esc(games_ou_value)),
        metric_row("TB%", esc(tiebreak_pct_display(row))),
        metric_row("Aces/M P | O | T", esc(triplet_market_display(row, "aces"))),
        metric_row("DF/M P | O | T", esc(triplet_market_display(row, "df"))),
        metric_row("S Data Depth", bar_html(s_data_depth(row))),
        '</section>',
    ])


def render_sets_games_box(row: Dict[str, Any]) -> str:
    sets_games_value = sets_games_projection_pair(row)
    sets_ou_value = market_pick_display(row, "sets", 2.5)
    games_ou_value = market_pick_display(row, "games", 23.5)
    return "\n".join([
        '<section class="metric-box small-box sets-signal-box">',
        f'<div class="box-head"><span>Sets | Games {info_icon("sets_games")}</span><b>{esc(sets_games_value)}</b></div>',
        metric_row("Sets o|u", esc(sets_ou_value)),
        metric_row("Games o|u", esc(games_ou_value)),
        metric_row("TB%", esc(tiebreak_pct_display(row))),
        metric_row("Aces/M P | O | T", esc(triplet_market_display(row, "aces"))),
        metric_row("DF/M P | O | T", esc(triplet_market_display(row, "df"))),
        metric_row("S Data Depth", bar_html(s_data_depth(row))),
        '</section>',
    ])

def final_marq_display(row: Dict[str, Any]) -> str:
    explicit = _first_data_value(
        row,
        "marq_final",
        "marq_final_display",
        "final_marq",
        "final_marq_display",
        "marq_market_final",
        "market_final",
    )
    text = str(explicit or "").strip()
    if text and text.upper() not in {"UNKNOWN", "NO MARKET DATA", "NO DATA", "NONE", "NULL", "—", "-"}:
        return text

    raw_move = _first_data_value(row, "marq_display_move_signal", "marq_move_signal", "market_move")
    move = str(raw_move or "").strip().upper().replace("_", " ")
    edge = as_float(_first_data_value(row, "marq_edge_pct", "marq_edge", "edge_pct"))
    if edge is not None and abs(edge) <= 1.0:
        edge *= 100.0

    if "AGAINST" in move:
        return "Market Against Pick"
    if "TOWARD" in move or "SUPPORT PICK" in move:
        return "Market With Pick"
    if "SUPPORT OPP" in move or "OPP" in move and "SUPPORT" in move:
        return "Market Against Pick"

    if edge is not None:
        if edge >= 2.0:
            if "STABLE" in move:
                return "Market With Pick - Stable"
            return "Market With Pick"
        if edge <= -2.0:
            if "STABLE" in move:
                return "Market Against Pick - Stable"
            return "Market Against Pick"
        if "STABLE" in move:
            return "Neutral - Stable"
        return "Neutral"

    if "STABLE" in move:
        return "Neutral - Stable"
    return "Pending"


def marq_sharp_display(row: Dict[str, Any]) -> str:
    signal = str(_first_data_value(row, "marq_sharp_signal", "sharp_signal") or "").strip()
    pct_value = _first_data_value(row, "marq_sharp_pick_pct", "sharp_pick_pct", "marq_exchange_pick_probability", "exchange_pick_probability")
    pct_text = market_pct(pct_value, 1)
    bad = {"", "UNKNOWN", "PENDING", "NO DATA", "NONE", "NULL", "NO SHARP DATA", "N/A", "—", "-"}
    signal_upper = signal.upper().replace("_", " ")
    signal_text = " ".join(part.capitalize() for part in signal_upper.split()) if signal_upper not in bad else ""
    if pct_text != "—" and signal_text:
        return f"{pct_text} | {signal_text}"
    if pct_text != "—":
        return pct_text
    if signal_text:
        return signal_text
    return "—"


def marq_clv_display(row: Dict[str, Any]) -> str:
    pp_value = _first_data_value(row, "marq_internal_clv_pp", "marq_clv_pct", "clv_pct", "marq_closing_edge_pct", "closing_edge_pct")
    pp_num = as_float(pp_value)
    if pp_num is not None:
        return f"{pp_num:+.1f}pp"
    status = str(_first_data_value(row, "marq_internal_clv_status", "marq_clv_status", "clv_status", "marq_internal_status") or "").strip()
    status_upper = status.upper().replace("_", " ")
    if status_upper in {"", "UNKNOWN", "NO DATA", "NONE", "NULL", "N/A", "—", "-"}:
        return "Pending"
    if status_upper == "NO SNAPSHOT":
        return "No snapshot"
    return " ".join(part.capitalize() for part in status_upper.split())


def _marq_value_status(row: Dict[str, Any]) -> str:
    vd = as_float(_first_data_value(row, "marq_v2_value_delta_pp", "corq_value_delta_pp", "value_delta_pp"))
    ev = as_float(_first_data_value(row, "marq_v2_expected_value_pct", "expected_value_pct", "ev_pct"))
    if (vd is not None and vd >= 3.0) or (ev is not None and ev >= 4.0):
        return "Value+"
    if (vd is not None and vd >= 0.5) or (ev is not None and ev >= 1.0):
        return "Playable"
    if (vd is not None and vd <= -3.0) or (ev is not None and ev <= -4.0):
        return "No value"
    return "Neutral"


def _marq_status_clean(value: Any, default: str = "—") -> str:
    text = str(value or "").strip()
    if not text or text.upper() in {"NONE", "NULL", "NAN", "UNKNOWN", "—", "-"}:
        return default
    text = text.replace("_", " ").strip()
    return " ".join(part.capitalize() if not part.isupper() else part for part in text.split())


def _marq_pick_market_probability(row: Dict[str, Any]) -> Any:
    pick_key = str(_first_data_value(row, "pick_outcome_key", "marq_pick_outcome_key") or "od1").lower()
    if pick_key in {"od2", "2", "away"}:
        return _first_data_value(row, "marq_no_vig_probability_2", "marq_v2_no_vig_2", "marq_opp_no_vig_probability", "corq_market_probability")
    return _first_data_value(row, "marq_no_vig_probability_1", "marq_v2_no_vig_1", "marq_pick_no_vig_probability", "corq_market_probability")


def _marq_opp_market_probability(row: Dict[str, Any]) -> Any:
    pick_key = str(_first_data_value(row, "pick_outcome_key", "marq_pick_outcome_key") or "od1").lower()
    if pick_key in {"od2", "2", "away"}:
        return _first_data_value(row, "marq_no_vig_probability_1", "marq_v2_no_vig_1", "marq_pick_no_vig_probability")
    return _first_data_value(row, "marq_no_vig_probability_2", "marq_v2_no_vig_2", "marq_opp_no_vig_probability")


def _marq_market_pair_display(row: Dict[str, Any]) -> str:
    pick_prob = _marq_pick_market_probability(row)
    opp_prob = _marq_opp_market_probability(row)
    return f"{market_pct(pick_prob, 1)} | {market_pct(opp_prob, 1)}"


def _marq_current_odds_display(row: Dict[str, Any]) -> str:
    one = _first_data_value(row, "marq_current_odds_1", "current_odds_1", "odds_1")
    two = _first_data_value(row, "marq_current_odds_2", "current_odds_2", "odds_2")
    if one in (None, "") and two in (None, ""):
        return f"{fmt_odds(pick_odds(row))} | {fmt_odds(opponent_odds(row))}"
    return f"{fmt_odds(one)} | {fmt_odds(two)}"


def _marq_opening_odds_display(row: Dict[str, Any]) -> str:
    one = _first_data_value(row, "marq_opening_odds_1", "opening_odds_1", "initial_1")
    two = _first_data_value(row, "marq_opening_odds_2", "opening_odds_2", "initial_2")
    if one in (None, "") and two in (None, ""):
        return "Current only"
    return f"{fmt_odds(one)} | {fmt_odds(two)}"


def _marq_source_display(row: Dict[str, Any]) -> str:
    endpoint = _first_data_value(row, "marq_endpoint_name", "odds_endpoint_name")
    if endpoint:
        return _marq_status_clean(endpoint)
    source = _first_data_value(row, "marq_api_source", "marq_source", "odds_source")
    return _marq_status_clean(source, "TennisApi")


def _marq_signal_display(row: Dict[str, Any]) -> str:
    explicit = _first_data_value(row, "marq_v2_signal", "marq_signal", "marq_final", "marq_final_display", "final_marq")
    if explicit not in (None, ""):
        text = str(explicit).strip()
        if text.upper() not in {"UNKNOWN", "NO DATA", "NONE", "NULL", "—", "-", "NEUTRAL"}:
            return _marq_status_clean(text)
    status = _marq_value_status(row)
    tier = str(_first_data_value(row, "corq_marq_quality_tier") or "").upper()
    if status == "Value+" and tier not in {"THIN_FALLBACK", "NO_MARQ"}:
        return "Value market edge"
    if status == "Playable":
        return "Playable fair value"
    if status == "No value":
        return "No value price"
    if tier == "THIN_FALLBACK":
        return "Thin market data"
    return "No clear market edge"


def _marq_pick_outcome_key(row: Dict[str, Any]) -> str:
    key = str(_first_data_value(row, "pick_outcome_key", "marq_pick_outcome_key") or "").strip().lower()
    if key in {"od2", "2", "away", "player2"}:
        return "od2"
    side = str(_first_data_value(row, "pick_side") or "").strip().upper()
    if side == "AWAY":
        return "od2"
    return "od1"


def _marq_side_value(row: Dict[str, Any], side1_keys: Tuple[str, ...], side2_keys: Tuple[str, ...], fallback_keys: Tuple[str, ...] = ()) -> Any:
    value = _first_data_value(row, *(side2_keys if _marq_pick_outcome_key(row) == "od2" else side1_keys))
    if value not in (None, ""):
        return value
    return _first_data_value(row, *fallback_keys) if fallback_keys else None


def marq_value_ev_display(row: Dict[str, Any]) -> str:
    delta = _first_data_value(
        row,
        "marq_v2_value_delta_pp",
        "corq_value_delta_pp",
        "value_delta_pp",
        "model_market_delta_pp",
    )
    ev = _first_data_value(
        row,
        "marq_v2_expected_value_pct",
        "expected_value_pct",
        "ev_pct",
        "expected_value",
    )
    return f"{pp_display(delta, 1)} | EV {signed_market_pct(ev, 1)}"


def marq_value_ev_class(row: Dict[str, Any]) -> str:
    delta = as_float(_first_data_value(row, "marq_v2_value_delta_pp", "corq_value_delta_pp", "value_delta_pp", "model_market_delta_pp"))
    ev = as_float(_first_data_value(row, "marq_v2_expected_value_pct", "expected_value_pct", "ev_pct", "expected_value"))
    return sign_class(delta if delta is not None else ev)


def marq_open_move_display(row: Dict[str, Any]) -> str:
    open_odds = _marq_side_value(
        row,
        ("marq_opening_odds_1", "marq_initial_odds_1", "opening_1", "initial_1"),
        ("marq_opening_odds_2", "marq_initial_odds_2", "opening_2", "initial_2"),
        ("marq_initial_pick_odds", "move_earliest_odds", "initial_pick_odds"),
    )
    current_odds = _marq_side_value(
        row,
        ("marq_current_odds_1", "current_odds_1", "odds_1"),
        ("marq_current_odds_2", "current_odds_2", "odds_2"),
        ("marq_current_pick_odds", "move_latest_odds", "current_pick_odds", "pick_odds", "odds"),
    )
    move_signal = move_signal_display(_first_data_value(row, "marq_internal_move_signal", "marq_display_move_signal", "marq_move_signal", "market_move"))
    movement_status = str(_first_data_value(row, "marq_v2_movement_status", "marq_movement_status") or "").upper()

    open_num = as_float(open_odds)
    current_num = as_float(current_odds)
    if open_num is not None and current_num is not None:
        if move_signal == "Pending" and movement_status:
            if "CURRENT_ONLY" in movement_status:
                move_signal = "Current Only"
            elif "OPENING_EQUALS_CURRENT" in movement_status:
                move_signal = "Stable"
            elif "REAL_OPENING" in movement_status:
                move_signal = "Real Move"
        return f"{fmt_odds(open_num)} -> {fmt_odds(current_num)} | {move_signal}"
    if current_num is not None:
        return f"Current {fmt_odds(current_num)} | No open"
    if "THIN" in movement_status:
        return "No real movement"
    if "CURRENT_ONLY" in movement_status:
        return "Current only | No open"
    return marq_range_move_display(row)


def _marq_trust_label(row: Dict[str, Any]) -> str:
    confidence = str(_first_data_value(row, "marq_v2_confidence", "marq_confidence") or "").strip()
    tier = str(_first_data_value(row, "corq_marq_quality_tier", "marq_quality_tier") or "").strip()
    data_status = str(_first_data_value(row, "marq_v2_data_status", "marq_data_status", "marq_source_quality") or "").strip()
    combined = " ".join([confidence, tier, data_status]).upper()
    if "HIGH" in combined or "REAL_OPENING" in combined or "WITH_OPENING" in combined:
        return "High"
    if "MEDIUM" in combined or "CURRENT" in combined or "EXACT" in combined:
        return "Medium"
    if "LOW" in combined or "THIN" in combined or "FALLBACK" in combined:
        return "Low"
    return confidence.title() if confidence else "—"


def marq_trust_display(row: Dict[str, Any]) -> str:
    weight = _first_data_value(
        row,
        "corq_market_weight",
        "corq_marq_weight",
        "marq_weight",
        "model_mix_marq_weight",
        "corq_model_mix_marq_weight",
    )
    return f"{_marq_trust_label(row)} | MarQ {as_pct(weight, 0)}"


def marq_market_read_class(row: Dict[str, Any]) -> str:
    text = str(final_marq_display(row) or "").strip().lower().replace("_", " ")
    if "against" in text:
        return "bad"
    if "with pick" in text or "support" in text:
        return "good"
    return "neutral"


def marq_box_class(row: Dict[str, Any]) -> str:
    cls = marq_market_read_class(row)
    if cls == "bad":
        return "metric-box small-box marq-box marq-against"
    if cls == "good":
        return "metric-box small-box marq-box marq-with"
    return "metric-box small-box marq-box marq-neutral"


def render_marq_box(row: Dict[str, Any]) -> str:
    signal = _marq_signal_display(row)
    market_cls = marq_market_read_class(row)
    return "\n".join([
        f'<div class="{marq_box_class(row)}">',
        f'<div class="box-head"><span>MarQ {info_icon("marq")}</span><b>{esc(signal)}</b></div>',
        metric_row("Pick Marq", market_pct(_first_data_value(row, "marq_crowd_pick_pct", "pick_marq", "marq_pick_pct"))),
        metric_row("Opp Marq", market_pct(_first_data_value(row, "marq_crowd_opponent_pct", "opponent_marq", "opp_marq", "marq_opponent_pct"))),
        metric_row_info("Model Value", esc(marq_value_ev_display(row)), "marq_delta", marq_value_ev_class(row)),
        metric_row_info("Range | Move", esc(marq_open_move_display(row)), "marq_move"),
        metric_row("Trust", esc(marq_trust_display(row))),
        metric_row("Market Read", esc(final_marq_display(row)), market_cls),
        '</div>',
    ])

def render_cloq_box(row: Dict[str, Any]) -> str:
    return "\n".join([
        '<section class="metric-box small-box">',
        '<div class="box-head"><span>CloQ</span><b></b></div>',
        metric_row("Status", esc(row.get("cloq_status") or "OK")),
        metric_row("Odds Gap", as_pct(row.get("cloq_odds_gap_pct") or row.get("odds_gap_pct"), 1)),
        metric_row("Source", "ALL"),
        metric_row("Rank", esc(row.get("cloq_rank") or "—")),
        metric_row("Filter", "Close odds"),
        metric_row("Limit", "10% gap"),
        '</section>',
    ])


def copy_assets() -> str:
    """Return an embedded logo data URI when possible.

    The site pages live one folder below corq/site, so file paths are easy to
    break or cache incorrectly. Embedding the small PNG makes the logo stable
    everywhere: CorQ, Audit, Results, ThinQ and CloQ pages.
    """
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    target = ASSET_DIR / "tbt_ai_goat_icon.png"
    try:
        if ASSET_SRC.exists():
            shutil.copyfile(ASSET_SRC, target)
            raw = ASSET_SRC.read_bytes()
            encoded = base64.b64encode(raw).decode("ascii")
            return f"data:image/png;base64,{encoded}"
    except Exception as exc:
        print(f"[render] asset embed/copy failed: {exc}")
    version = str(int(datetime.now(tz=timezone.utc).timestamp()))
    return f"assets/tbt_ai_goat_icon.png?v={version}"


def css() -> str:
    return """
:root{--bg:#08111f;--panel:#111d2f;--panel2:#0e1828;--line:#24344d;--text:#e5eefc;--muted:#8ea5c2;--cyan:#38d5ff;--green:#34d399;--orange:#fb923c;--red:#f87171;--yellow:#facc15}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#10233d 0,#08111f 42%,#050b14 100%);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}.wrap{max-width:1920px;margin:0 auto;padding:14px}.topbar{display:flex;align-items:center;gap:18px;margin-bottom:18px;min-height:78px}.brand{display:flex;align-items:center;gap:14px;min-width:310px}.brand-mark{display:inline-flex;align-items:center;justify-content:center;width:72px;height:72px;border-radius:999px;background:#071827;border:1px solid rgba(56,213,255,.75);box-shadow:0 0 26px rgba(56,213,255,.24);overflow:hidden;flex:0 0 auto}.brand-logo{width:100%;height:100%;border-radius:999px;object-fit:contain;padding:0;background:#071827}.brand-fallback{display:none;align-items:center;justify-content:center;width:100%;height:100%;border-radius:999px;color:#e5eefc;font-weight:900;font-size:12px;letter-spacing:.02em}.brand-title{font-weight:900;font-size:20px}.brand-sub{font-size:11px;color:var(--muted);letter-spacing:.14em;text-transform:uppercase}.nav{display:flex;gap:10px;flex-wrap:wrap}.nav a{color:#bcd1ea;text-decoration:none;border:1px solid #22344d;background:#0d1727;padding:8px 13px;border-radius:999px;font-weight:700}.nav a.active{border-color:var(--cyan);box-shadow:0 0 0 1px rgba(56,213,255,.25),0 0 18px rgba(56,213,255,.14);color:#fff}.hero{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px}.hero-panel{background:linear-gradient(180deg,rgba(17,29,47,.92),rgba(9,17,30,.92));border:1px solid #23344d;border-radius:18px;padding:14px}.hero-title{font-size:11px;color:var(--cyan);text-transform:uppercase;letter-spacing:.14em;font-weight:900}.hero-line{margin-top:4px;color:#dbeafe}.grid{display:grid;gap:14px}.pick-card{display:grid;grid-template-columns:minmax(250px,1.15fr) repeat(5,minmax(170px,.95fr));gap:10px;background:rgba(10,18,32,.72);border:1px solid #20314a;border-radius:22px;padding:12px;box-shadow:0 12px 36px rgba(0,0,0,.25)}.pick-main,.metric-box{background:linear-gradient(180deg,#121f32,#0c1625);border:1px solid #283a55;border-radius:18px;padding:14px;min-width:0}.card-top{display:flex;justify-content:space-between;align-items:center}.rank-num{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:28px;padding:0 8px;border-radius:999px;background:#13253c;border:1px solid #2d4b6f;color:var(--cyan);font-size:12px;font-weight:900}.brain{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:999px;text-decoration:none;background:#15243a;border:1px solid #334862;flex:0 0 auto}.card-footer-row{display:flex;align-items:flex-end;gap:8px;margin-top:12px}.card-footer-tools{display:flex;align-items:center;gap:6px;flex:0 0 auto}.card-insights{flex:1;min-width:0;background:#101b2c;border:1px solid rgba(51,72,98,.55);border-radius:10px;padding:5px 8px;color:#dbeafe;font-size:11px;font-weight:800;line-height:1.25;overflow:hidden}.card-insights div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.card-insights.empty-insights{color:#64748b}.pick-main h2,.pick-main h3{margin:8px 0 4px;font-size:18px;line-height:1.2}.pick-main h3{font-size:16px;color:#dbeafe}.rank{font-size:.82em;color:#7dd3fc;font-weight:800}.odds-line{display:inline-block;color:#7ee7aa;background:#07351f;border:1px solid #0d7c49;border-radius:999px;padding:3px 8px;font-weight:800}.odds-line.muted{color:#bdd7f5;background:#111d2d;border-color:#263b58}.to-beat{margin:8px 0;color:#67e8f9;font-weight:900;text-transform:uppercase;font-size:11px}.time-line,.status-line{color:var(--muted);font-size:12px;margin-top:8px}.notes{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.note,.result-tag,.tag-chip{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;background:#16243a;border:1px solid #344a68;color:#bcd1ea;font-size:11px;font-weight:800}.box-head{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:10px;font-size:13px;font-weight:900;color:#bae6fd}.box-head b{font-size:18px;color:var(--green)}.metric-row{display:flex;justify-content:space-between;gap:10px;border-top:1px solid rgba(148,163,184,.14);padding:6px 0;color:#9fb5d1}.metric-row:first-of-type{border-top:0}.metric-row b{color:#f8fafc;text-align:right}.metric-row.good b{color:#f8fafc}.metric-row.bad b{color:var(--orange)}.metric-row.neutral b{color:#b9c6d8}.small-box .metric-row{font-size:12px}.depth-wrap{display:inline-flex;align-items:center;gap:8px}.depth-number{min-width:38px;text-align:right;color:#f8fafc}.depth-bar{display:inline-block;width:74px;height:8px;background:#1e293b;border-radius:999px;overflow:hidden;border:1px solid #334155}.depth-bar span{display:block;height:100%}.bar-good{background:linear-gradient(90deg,#10b981,#67e8f9)}.bar-mid{background:linear-gradient(90deg,#facc15,#fb923c)}.bar-bad{background:linear-gradient(90deg,#ef4444,#fb923c)}.info{position:relative;display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:999px;border:1px solid #4b6b8d;color:#93c5fd;font-size:10px;margin-left:4px;cursor:help}.info:hover:after,.info:focus:after{content:attr(data-tip);position:absolute;left:50%;top:22px;transform:translateX(-50%);z-index:50;width:min(320px,80vw);white-space:normal;text-align:left;background:#0b1424;color:#e5eefc;border:1px solid #34506f;border-radius:12px;padding:10px 12px;box-shadow:0 12px 30px rgba(0,0,0,.35);font-size:12px;line-height:1.35}.summary-panel,.results-panel{margin-top:16px;background:#0d1727;border:1px solid #24344d;border-radius:20px;padding:16px}.summary-title{font-size:12px;color:var(--cyan);font-weight:900;text-transform:uppercase;letter-spacing:.12em;margin-bottom:10px}.tag-list{display:flex;flex-wrap:wrap;gap:8px}.tag-chip{cursor:pointer}.tag-chip.active{border-color:var(--cyan);color:#fff;box-shadow:0 0 16px rgba(56,213,255,.18)}.clear-filter{display:none;margin-left:8px;color:#93c5fd;cursor:pointer}.table-wrap{overflow:auto;border:1px solid #24344d;border-radius:16px}.results-table{width:100%;border-collapse:collapse;min-width:1150px;background:#0b1424}.results-table th{background:#172235;color:#9cc5e8;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.08em;padding:11px}.results-table td{border-top:1px solid #26354d;padding:11px;vertical-align:top}.status-won{color:#34d399;font-weight:900}.status-lost{color:#fb7185;font-weight:900}.status-pending{color:#facc15;font-weight:900}.status-void{color:#94a3b8;font-weight:900}.empty{padding:34px;text-align:center;color:#9fb5d1;background:#0d1727;border:1px dashed #334155;border-radius:20px}.footer{margin-top:26px;text-align:center;color:#6f86a4;font-size:12px}@media(max-width:1350px){.pick-card{grid-template-columns:1fr 1fr}.hero{grid-template-columns:1fr}}@media(max-width:760px){.wrap{padding:10px}.topbar{align-items:flex-start;flex-direction:column;min-height:auto}.pick-card{grid-template-columns:1fr}.hero{grid-template-columns:1fr}.brand-mark{width:56px;height:56px}.metric-row{font-size:13px}.pick-main h2{font-size:17px}}
.chip-insights{display:flex;flex-wrap:wrap;gap:6px;background:transparent!important;border:0!important;padding:0!important}.insight-chip{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:4px 8px;background:#10233b;border:1px solid #2f4b6e;color:#d4e8ff;font-size:11px;font-weight:900;line-height:1.2;white-space:nowrap}.side-insights .chip-insights{margin-top:0}.side-insights .insight-chip{max-width:100%;overflow:hidden;text-overflow:ellipsis}.metric-row b{white-space:normal}.metric-row span{padding-right:6px}  
.pick-main.compact-v3{padding:12px;background:linear-gradient(180deg,#111f35,#0b1627);border-color:#2b405d;display:flex;flex-direction:column;gap:10px;min-height:268px}.compact-topline{display:flex;align-items:center;gap:7px;min-height:30px}.compact-topline .rank-num{height:26px;min-width:30px;font-size:12px}.compact-topline .brain{width:26px;height:26px;font-size:14px}.status-pill{display:inline-flex;align-items:center;min-height:24px;padding:3px 9px;border-radius:999px;border:1px solid #2f4059;background:#101c2e;color:#9fb5d1;font-size:11px;font-weight:800;margin-left:auto}.compact-player{padding:9px 10px;border-radius:14px;border:1px solid rgba(148,163,184,.14);background:rgba(9,18,32,.56)}.compact-player.pick-side{border-color:rgba(52,211,153,.38);background:linear-gradient(90deg,rgba(6,50,34,.62),rgba(9,18,32,.48))}.compact-player.opp-side{border-color:rgba(96,165,250,.22)}.compact-label{font-size:10px;line-height:1;letter-spacing:.15em;text-transform:uppercase;color:#67e8f9;font-weight:900;margin-bottom:6px}.compact-name-row{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.compact-name{font-size:16px;line-height:1.2;font-weight:900;color:#f8fafc}.compact-rank{font-size:12px;color:#7dd3fc;font-weight:900;white-space:nowrap}.compact-odds{display:inline-flex;margin-top:7px;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:900;border:1px solid}.compact-odds.pick{color:#86efac;background:#06351f;border-color:#12834e}.compact-odds.opp{color:#bfdbfe;background:#101d32;border-color:#2a4566}.compact-vs{display:flex;align-items:center;justify-content:center;text-transform:uppercase;letter-spacing:.16em;font-size:10px;font-weight:900;color:#22d3ee;margin:-2px 0}.compact-match{border-radius:13px;background:#0a1424;border:1px solid rgba(148,163,184,.12);padding:9px 10px;color:#9fb5d1}.compact-time{font-size:12px;color:#dbeafe;font-weight:900}.compact-meta{font-size:11px;line-height:1.35;margin-top:3px;color:#8ea5c2}.compact-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto;padding-top:4px;border-top:1px solid rgba(148,163,184,.10)}.compact-tags .note,.compact-tags .insight-chip{font-size:11px;padding:4px 8px;max-width:100%;overflow:hidden;text-overflow:ellipsis}.compact-tags .card-insights{display:contents}.compact-tags .chip-insights{display:flex;flex-wrap:wrap;gap:6px}.compact-tags .empty-insights{display:none}@media(max-width:760px){.compact-name{font-size:15px}.pick-main.compact-v3{min-height:auto}}  
.compact-odds.inline{display:inline-flex;margin:0 0 0 6px;vertical-align:middle;transform:translateY(-1px);padding:2px 7px;font-size:11px;line-height:1.2}.compact-player.no-label{padding-top:12px;padding-bottom:12px}.compact-name{display:inline;word-break:break-word}.compact-name-row{align-items:center}.compact-label{margin-bottom:5px}.compact-tags .insight-chip::first-letter{font-size:11px}.compact-tags .insight-chip{border-color:#2f4b6e;background:#10233b}.compact-v3 .compact-player{min-height:70px;display:flex;flex-direction:column;justify-content:center}.compact-v3 .pick-side{min-height:78px}  
.compact-top-tags{display:flex;align-items:center;gap:5px;min-width:0;flex:1;overflow:hidden;white-space:nowrap}.compact-top-tags .card-insights{display:contents}.compact-top-tags .chip-insights{display:flex;align-items:center;gap:5px;min-width:0;overflow:hidden;white-space:nowrap}.compact-top-tags .insight-chip,.compact-top-tags .top-note{display:inline-flex;align-items:center;max-width:132px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;border-radius:999px;padding:3px 7px;background:#10233b;border:1px solid #2f4b6e;color:#d4e8ff;font-size:10px;font-weight:900;line-height:1.15}.compact-top-tags .empty-insights{display:none}.compact-topline{overflow:hidden}.compact-tags{flex-wrap:nowrap!important;overflow:hidden;white-space:nowrap}.compact-tags .note,.compact-tags .insight-chip{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.compact-v3 .status-pill{display:none!important}  
.compact-top-tags .insight-chip.negative,.insight-chip.negative{background:rgba(250,204,21,.13)!important;border-color:rgba(250,204,21,.68)!important;color:#fde68a!important}.compact-top-tags .insight-chip.positive,.insight-chip.positive{background:rgba(251,146,60,.14)!important;border-color:rgba(251,146,60,.62)!important;color:#fed7aa!important}.compact-top-tags .insight-chip.neutral,.insight-chip.neutral{background:#10233b!important;border-color:#2f4b6e!important;color:#d4e8ff!important}  
.compact-top-tags .insight-chip.positive,.insight-chip.positive{background:rgba(16,185,129,.16)!important;border-color:rgba(52,211,153,.70)!important;color:#86efac!important}.compact-top-tags .chip-insights{max-width:158px}.compact-top-tags .insight-chip{max-width:158px}.compact-tags.bottom-notes{display:flex;flex-wrap:nowrap;gap:6px;overflow:hidden;white-space:nowrap;padding-top:6px;border-top:1px solid rgba(148,163,184,.10)}.compact-tags.bottom-notes .note{background:rgba(88,28,135,.20);border-color:rgba(168,85,247,.45);color:#e9d5ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:190px;font-size:10px;padding:3px 7px}.compact-top-tags .top-note{display:none!important}.compact-top-tags .empty-insights{display:none!important}  
.compact-topline{gap:8px;min-height:36px}.compact-topline .rank-num{height:34px;min-width:34px;padding:0 9px;font-size:13px;border-color:#1f75aa;background:#0b2740;box-shadow:0 0 12px rgba(56,213,255,.12)}.compact-topline .brain{width:34px;height:34px;font-size:17px;border-color:#4b5f7a;background:#192a42;box-shadow:0 0 12px rgba(236,72,153,.10)}.compact-top-tags{gap:6px}.compact-top-tags .insight-chip{padding:4px 8px;font-size:10.5px;line-height:1.15;max-width:166px}.compact-top-tags .chip-insights{max-width:340px}@media(max-width:760px){.compact-topline .rank-num{height:32px;min-width:32px}.compact-topline .brain{width:32px;height:32px}.compact-top-tags .insight-chip{max-width:150px}}  
.compact-topline .brain.ai-badge{width:30px!important;height:30px!important;min-width:30px!important;font-size:11px!important;font-weight:1000;letter-spacing:.02em;color:#f0abfc;background:radial-gradient(circle at 35% 28%,rgba(236,72,153,.38),rgba(31,41,55,.92));border-color:#6b4f91;box-shadow:0 0 10px rgba(236,72,153,.12)}.compact-top-tags .insight-chip{max-width:172px}.compact-top-tags .chip-insights{max-width:350px}@media(max-width:760px){.compact-topline .brain.ai-badge{width:29px!important;height:29px!important;min-width:29px!important;font-size:10.5px!important}.compact-top-tags .insight-chip{max-width:158px}}  
.compact-topline .brain.goat-badge{width:30px!important;height:30px!important;min-width:30px!important;padding:0!important;overflow:hidden;border-color:#6b4f91;background:#151f35;box-shadow:0 0 10px rgba(236,72,153,.12)}.card-goat-logo{width:100%;height:100%;display:block;object-fit:cover;border-radius:999px}@media(max-width:760px){.compact-topline .brain.goat-badge{width:29px!important;height:29px!important;min-width:29px!important}}  
.card-goat-logo{object-fit:contain!important;padding:2px;background:#101827}  
.compact-topline .brain.goat-badge{border-color:rgba(250,204,21,.72)!important;box-shadow:0 0 10px rgba(250,204,21,.16)!important;background:#101827!important}  
.pick-card,.metric-box{overflow:visible!important}.info{z-index:40;background:#0b2036;color:#93c5fd;border-color:#4b6b8d}.info:hover:after,.info:focus:after{z-index:99999!important;pointer-events:none}.compact-topline .brain.goat-badge{border-color:rgba(250,204,21,.72)!important;box-shadow:0 0 8px rgba(250,204,21,.12)!important;background:#101827!important}  
.ta-signal-box .metric-row b{font-size:12px;line-height:1.25}.ta-signal-box .metric-row span{min-width:74px}.ta-signal-box .box-head b{text-transform:uppercase;font-size:11px;color:#facc15}  
.sets-signal-box .metric-row b{font-size:12px;line-height:1.25}.sets-signal-box .metric-row span{min-width:76px}.sets-signal-box .box-head b{font-size:13px!important;line-height:1.15;color:var(--green)!important}  

.one-row-debug .metric-row b{font-size:11px}.marq-box .metric-row b,.sets-signal-box .metric-row b{font-size:11px}.mmx-box .box-head b{font-size:13px!important;line-height:1.15;color:var(--green)!important}.mmx-box .box-head{align-items:center}.info{line-height:1}.pick-card{align-items:stretch}.metric-box{min-height:0}.box-head{margin-bottom:7px}.metric-row span{font-size:11px}.metric-row b{font-size:11px}.compact-name{font-size:15px}

.data-notes-summary{border-radius:18px;background:rgba(8,21,36,.92);border-color:rgba(90,130,180,.35);box-shadow:0 16px 35px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.03);margin-bottom:18px}.data-notes-summary .summary-title{color:#44e7ff;letter-spacing:.14em}.data-notes-pills{display:flex;flex-wrap:wrap;gap:8px}.audit-pill{display:inline-flex;align-items:center;gap:5px;padding:6px 11px;border-radius:999px;border:1px solid rgba(120,170,230,.45);background:rgba(42,72,112,.72);color:#e9f4ff;font-size:12px;font-weight:850;line-height:1;text-decoration:none;white-space:nowrap;transition:140ms ease-in-out;cursor:pointer}.audit-pill:hover{border-color:rgba(70,230,255,.85);background:rgba(30,105,150,.85);color:#fff;transform:translateY(-1px)}.audit-pill.active{border-color:#44e7ff;background:rgba(0,210,255,.22);box-shadow:0 0 0 1px rgba(68,231,255,.25),0 0 18px rgba(68,231,255,.16)}.audit-pill-count{color:#fff;font-weight:950}.audit-pill-label{color:#e9f4ff}.audit-pill-note{border-color:rgba(120,170,230,.45);background:rgba(42,72,112,.72)}.audit-pill-corq{border-color:rgba(72,231,255,.58);background:rgba(0,113,150,.58)}.audit-pill-signal{border-color:rgba(255,178,63,.58);background:rgba(112,74,14,.62)}.audit-pill-safe{border-color:rgba(0,230,120,.68);background:rgba(0,110,70,.70)}.audit-pill-h2h{border-color:rgba(168,85,247,.62);background:rgba(76,29,149,.64)}.audit-pill-clear{border-color:rgba(255,120,120,.45);background:rgba(92,28,40,.65);color:#ffd8d8}
.result-status-summary{margin:0 0 12px 0}.result-summary-chip{font-weight:900}
.result-audit-filter-summary{margin:0 0 12px 0}.result-status-summary .tag-chip{cursor:pointer}
.audit-pill-date{border-color:rgba(96,165,250,.62);background:rgba(30,64,175,.62)}.audit-pill-model{border-color:rgba(236,72,153,.56);background:rgba(131,24,67,.62)}.result-audit-filter-summary{gap:8px}

.result-filter-builder{position:sticky;top:0;z-index:20;background:rgba(8,21,36,.96);backdrop-filter:blur(8px)}.result-filter-help{margin:-4px 0 10px 0;color:#8ea5c2;font-size:12px;font-weight:700}.result-filter-row{display:flex;align-items:flex-start;flex-wrap:wrap;gap:10px}.result-filter-group{display:flex;align-items:center;flex-wrap:wrap;gap:6px;padding:7px 8px;border-radius:14px;background:rgba(15,27,45,.72);border:1px solid rgba(90,130,180,.22)}.result-filter-group-title{margin-right:2px;color:#93c5fd;font-size:10px;font-weight:950;letter-spacing:.12em;text-transform:uppercase}.tag-analysis-row{transition:opacity 120ms ease-in-out}
/* Info icon polish: keep tooltip buttons circular even inside compact boxes. */
.box-head .info,.metric-row .info,.metric-row .metric-label>.info,.sets-signal-box .metric-row .info,.ta-signal-box .metric-row .info{position:relative!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;width:14px!important;min-width:14px!important;max-width:14px!important;height:14px!important;min-height:14px!important;max-height:14px!important;flex:0 0 14px!important;padding:0!important;margin-left:4px!important;border-radius:999px!important;border:1px solid rgba(125,211,252,.65)!important;background:rgba(8,28,48,.72)!important;color:#7dd3fc!important;font-size:9px!important;font-weight:900!important;line-height:1!important;vertical-align:middle!important;box-shadow:0 0 0 1px rgba(14,165,233,.10),0 0 8px rgba(14,165,233,.12)!important;cursor:help!important}.box-head .info:hover,.metric-row .info:hover,.box-head .info:focus,.metric-row .info:focus{border-color:#67e8f9!important;color:#e0f2fe!important;background:rgba(14,116,144,.30)!important;box-shadow:0 0 0 1px rgba(103,232,249,.22),0 0 12px rgba(34,211,238,.25)!important}.metric-row .metric-label{display:inline-flex;align-items:center;gap:2px;min-width:0!important;max-width:100%;padding-right:6px}.sets-signal-box .metric-row .metric-label,.ta-signal-box .metric-row .metric-label{min-width:76px!important}.ta-signal-box .metric-row .metric-label{min-width:74px!important}.info:hover:after,.info:focus:after{font-weight:700!important;color:#e5eefc!important;text-transform:none!important;letter-spacing:0!important}.metric-row .info:before,.box-head .info:before{content:"";position:absolute;inset:-3px;border-radius:999px}.sets-signal-box .metric-row span.depth-wrap,.sets-signal-box .metric-row span.depth-number,.sets-signal-box .metric-row span.depth-bar{min-width:0!important}

/* Compact pick panel final override: reduce free space in player boxes, keep top tags unchanged, put match meta on one row. */
.pick-main.compact-v3{padding:10px!important;gap:7px!important;min-height:0!important}.compact-v3 .compact-player{min-height:0!important;padding:8px 10px!important;justify-content:center!important}.compact-v3 .pick-side{min-height:0!important;padding-top:8px!important;padding-bottom:8px!important}.compact-player.no-label{padding-top:8px!important;padding-bottom:8px!important}.compact-label{margin-bottom:5px!important;font-size:9px!important;line-height:1!important}.compact-name-row{align-items:center!important;gap:7px!important}.compact-name{display:flex!important;align-items:center!important;gap:6px!important;min-width:0!important;font-size:13px!important;line-height:1.12!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}.compact-name .compact-odds.inline{flex:0 0 auto!important;margin-left:2px!important;transform:none!important;padding:2px 7px!important;font-size:10px!important;line-height:1.1!important}.compact-rank{font-size:11px!important;line-height:1!important;flex:0 0 auto!important}.compact-vs{height:14px!important;min-height:14px!important;margin:-1px 0!important;font-size:9px!important;line-height:1!important}.compact-match{padding:7px 9px!important;border-radius:12px!important}.compact-match-row{display:flex!important;align-items:center!important;gap:8px!important;min-width:0!important;white-space:nowrap!important;overflow:hidden!important}.compact-time{font-size:12px!important;line-height:1!important;flex:0 0 auto!important}.compact-meta{font-size:10px!important;line-height:1.15!important;margin-top:0!important;min-width:0!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}.compact-tags.bottom-notes{padding-top:4px!important;margin-top:auto!important}@media(max-width:760px){.compact-name{font-size:13px!important}.compact-match-row{gap:6px!important}.compact-meta{font-size:10px!important}}


/* Unified date/time pill for CorQ, Audit, CloQ and Results cards. */
.compact-datetime-pill{display:inline-flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:1px;min-width:62px;padding:3px 7px;border-radius:10px;background:rgba(15,32,54,.78);border:1px solid rgba(125,211,252,.28);box-shadow:inset 0 1px 0 rgba(255,255,255,.03);line-height:1.05;flex:0 0 auto}.compact-datetime-pill .compact-date{font-size:10.5px;font-weight:900;color:#bae6fd;letter-spacing:.02em}.compact-datetime-pill .compact-clock{font-size:13.5px;font-weight:1000;color:#f8fafc;letter-spacing:.02em}.compact-meta-only{width:100%;font-size:11px!important;line-height:1.2!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}.compact-match-row{align-items:center!important}.result-card .status-pill{display:inline-flex!important;margin-left:auto!important}.results-card .status-pill{display:inline-flex!important;margin-left:auto!important}
/* Active filters are orange across Audit and Results; inactive filters keep the neutral style. */

/* Final pick-card header order/style override: rank, date/time, log icon, tags. */
.compact-topline{display:flex!important;align-items:center!important;gap:8px!important;min-height:36px!important;overflow:hidden!important}.compact-topline .rank-num{order:1!important;flex:0 0 auto!important}.compact-datetime-pill{order:2!important;flex:0 0 auto!important;align-items:flex-start!important}.compact-datetime-pill .compact-date{font-size:10px!important;line-height:1.05!important;color:#bde9ff!important;font-weight:900!important}.compact-datetime-pill .compact-clock{font-size:14px!important;line-height:1.05!important;color:#fff!important;font-weight:1000!important}.compact-topline .brain.goat-badge{order:3!important;flex:0 0 auto!important}.compact-top-tags{order:4!important;flex:1 1 auto!important;min-width:0!important}.status-pill{order:5!important}.compact-match .compact-time{display:none!important}.compact-meta-only{padding-left:0!important}
.audit-pill.active,.tag-chip.active,.result-summary-chip.active{border-color:var(--orange)!important;background:rgba(251,146,60,.24)!important;color:#fff!important;box-shadow:0 0 0 1px rgba(251,146,60,.25),0 0 18px rgba(251,146,60,.18)!important}.audit-pill.active .audit-pill-label,.audit-pill.active .audit-pill-count{color:#fff!important}
@media(max-width:760px){.compact-datetime-pill{min-width:54px;padding:3px 6px}.compact-datetime-pill .compact-date{font-size:10px}.compact-datetime-pill .compact-clock{font-size:13px}}

"""


def nav_html(active: str) -> str:
    parts = []
    for item in NAV_ITEMS:
        if isinstance(item, dict):
            label = item.get("label") or item.get("name") or ""
            path = item.get("path") or item.get("url") or ""
            key = item.get("key") or label
        elif isinstance(item, (list, tuple)):
            label = item[0] if len(item) > 0 else ""
            path = item[1] if len(item) > 1 else ""
            key = item[2] if len(item) > 2 else label
        else:
            continue
        label_s = str(label)
        path_s = str(path)
        key_s = str(key)
        display_label = label_s
        if label_s.strip().lower() in {"all", "all audit"}:
            display_label = "Audit"
        elif label_s.strip().lower() in {"tg rss", "telegram rss"}:
            display_label = "TG"
        is_xml = path_s.endswith(".xml")
        if active == "root":
            href = path_s if is_xml else f"{path_s}/"
        else:
            href = f"../{path_s}" if is_xml else f"../{path_s}/"
        active_values = {label_s.lower(), path_s.lower(), key_s.lower()}
        cls = "active" if str(active).lower() in active_values else ""
        parts.append(f'<a class="{cls}" href="{esc(href)}">{esc(display_label)}</a>')
    return "".join(parts)


def hero_html(page_label: str, manifest: Dict[str, Any]) -> str:
    return f"""
<div class="hero">
  <div class="hero-panel"><div class="hero-title">WHO WE ARE</div><div class="hero-line">Independent tennis intelligence platform built for analytics and data enthusiasts.</div></div>
  <div class="hero-panel"><div class="hero-title">WHAT WE DO</div><div class="hero-line">We combine player data, market odds and machine learning to uncover value.</div></div>
  <div class="hero-panel"><div class="hero-title">WHY WE DO IT</div><div class="hero-line">To replace guesswork with transparent, data-driven insights.</div></div>
</div>
"""


def page_shell(title: str, active: str, body: str, manifest: Optional[Dict[str, Any]] = None) -> str:
    manifest = manifest or {}
    logo_url = copy_assets()
    if (
        active != "root"
        and not logo_url.startswith("../")
        and not logo_url.startswith("http")
        and not logo_url.startswith("data:")
    ):
        logo_url = "../" + logo_url
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title><style>{css()}</style></head>
<body><div class="wrap">
<header class="topbar">
  <div class="brand"><span class="brand-mark"><img class="brand-logo" src="{esc(logo_url)}" alt="BackstageTalks logo" onerror="this.style.display='none';this.nextElementSibling.style.display='inline-flex'"><span class="brand-fallback">BsT</span></span><div><div class="brand-title">BackstageTalks</div><div class="brand-sub">Statistical Engine</div></div></div>
  <nav class="nav">{nav_html(active)}</nav>
</header>
{hero_html(title, manifest)}
{body}
<div class="footer">This data is provided for informational and analytical purposes only. Powered by BackstageTalks Statistical Engine.</div>
</div>{tag_filter_script()}</body></html>"""



# ============================================================
# Audit page filter pills / CorQ summary signals
# ============================================================

AUDIT_CORQ_TOP20_LABEL = "CorQ Top20"
AUDIT_TIME_ODDS_LABEL = "Up to 2H | O>1.5"
AUDIT_SAFE_BET_LABEL = "Safe Bet Signal"
AUDIT_H2H_TOP10_LABEL = "H2H Top10"
AUDIT_CLOQ_LABEL = "CloQ"
AUDIT_OPP_WEAK_LABEL = "Opp weak"
AUDIT_PICK_STRONG_LABEL = "Pick strong"
AUDIT_FORM_SUPPORT_LABEL = "Form support"
AUDIT_ELO_SUPPORT_LABEL = "ELO support"
AUDIT_SURFACE_SUPPORT_LABEL = "Surface support"
AUDIT_MARKET_WITH_PICK_LABEL = "Market with pick"
AUDIT_VALUE_POSITIVE_LABEL = "Value+"
AUDIT_POSITIVE_TAG_LABEL = "Positive tag"
AUDIT_TWO_POSITIVE_TAGS_LABEL = "2 positive tags"
RESULT_LAST_3_DAYS_LABEL = "Last 3 days"
RESULT_LAST_24H_LABEL = "L24h"
RESULT_LAST_7_DAYS_LABEL = "Last 7 days"
RESULT_LAST_MONTH_LABEL = "Last month"
RESULT_THIS_YEAR_LABEL = "This year"
RESULT_MODEL_CORQ_LABEL = "CorQ"
RESULT_MODEL_CLOQ_LABEL = "CloQ"
RESULT_MODEL_AUDIT_LABEL = "Audit"


def audit_parse_datetime_utc(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            if re.fullmatch(r"\d{10,13}", text):
                dt = datetime.fromtimestamp(int(text[:10]), tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def audit_match_time_utc(row: Dict[str, Any]) -> Optional[datetime]:
    for key in (
        "match_time_utc",
        "start_time_utc",
        "commence_time",
        "start_time",
        "match_time",
    ):
        dt = audit_parse_datetime_utc(row.get(key))
        if dt is not None:
            return dt
    for parent in ("market", "event"):
        ctx = row.get(parent)
        if isinstance(ctx, dict):
            for key in ("commence_time", "start_time_utc", "start_time", "match_time_utc"):
                dt = audit_parse_datetime_utc(ctx.get(key))
                if dt is not None:
                    return dt
    return None


def audit_corq_rank(row: Dict[str, Any]) -> Optional[int]:
    candidates = [
        nested_get(row, "corq", "rank"),
        nested_get(row, "corq", "corq_rank"),
        row.get("corq_rank"),
        row.get("rank"),
        row.get("pick_rank"),
        row.get("top_rank"),
        row.get("_corq_render_rank"),
    ]
    for value in candidates:
        try:
            if value is None or value == "":
                continue
            text = str(value).strip()
            if text.startswith("#"):
                text = text[1:]
            return int(float(text))
        except Exception:
            continue
    return None


def audit_has_corq_top20(row: Dict[str, Any]) -> bool:
    rank = audit_corq_rank(row)
    return rank is not None and rank <= 20


def audit_has_up_to_2h_o15(row: Dict[str, Any]) -> bool:
    odds = pick_odds(row)
    if odds is None or odds <= 1.50:
        return False
    status = normal_status(row)
    if status and status not in {"prematch", "pre-match", "notstarted", "not_started", "scheduled", "pending", ""}:
        return False
    dt = audit_match_time_utc(row)
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    return now <= dt <= now + timedelta(hours=2)


def audit_record_pair(value: Any) -> Tuple[Optional[int], Optional[int]]:
    if isinstance(value, dict):
        w = value.get("wins") if value.get("wins") is not None else value.get("w")
        l = value.get("losses") if value.get("losses") is not None else value.get("l")
        return as_float(w), as_float(l)  # type: ignore[return-value]
    return compact_record_label(str(value or ""))


def audit_has_safe_bet_signal(row: Dict[str, Any]) -> bool:
    pick_form, pick_surface_form = form_records(row, "pick")
    opp_form, opp_surface_form = form_records(row, "opponent")

    def pick_strong(record: Any) -> bool:
        w, l = audit_record_pair(record)
        return w is not None and l is not None and (w + l) >= 8 and w >= 8

    def opp_weak(record: Any) -> bool:
        w, l = audit_record_pair(record)
        return w is not None and l is not None and (w + l) >= 8 and l >= 7

    pick_ok = pick_strong(pick_form) or pick_strong(pick_surface_form)
    opp_ok = opp_weak(opp_form) or opp_weak(opp_surface_form)

    # Fallback if future upstream passes the visible green tags directly.
    tag_text = " | ".join(str(x) for x in get_existing_public_tags(row)).lower().replace("last 10", "l10")
    if "pick strong" in tag_text and "l10" in tag_text:
        pick_ok = True
    if "opp weak" in tag_text and "l10" in tag_text:
        opp_ok = True

    return pick_ok and opp_ok



def audit_h2h_support_score(row: Dict[str, Any]) -> float:

    """Score positive H2H support from displayed pick perspective.

    The score is intentionally audit-only. It does not change CorQ ranking.
    It favors:
    - bigger pick vs opponent H2H difference,
    - enough sample size,
    - same-surface H2H when it is available and different from total H2H.
    """
    hp, ho = h2h_record(row)
    shp, sho = surface_h2h_record(row)
    score = 0.0

    if hp is not None and ho is not None:
        total = hp + ho
        diff = hp - ho
        if total >= 2 and diff > 0:
            win_rate = hp / total if total else 0.0
            score += (diff * 10.0) + (win_rate * 8.0) + min(total, 10) * 0.7

    if shp is not None and sho is not None:
        surface_total = shp + sho
        surface_diff = shp - sho
        duplicate_total = hp == shp and ho == sho
        if surface_total >= 2 and surface_diff > 0 and not duplicate_total:
            surface_win_rate = shp / surface_total if surface_total else 0.0
            score += (surface_diff * 12.0) + (surface_win_rate * 10.0) + min(surface_total, 10) * 0.9

    return score


def mark_audit_h2h_top10(rows: List[Dict[str, Any]]) -> None:
    """Mark the best 10 positive H2H indicators in-place for Audit filtering."""
    scored: List[Tuple[float, int, Dict[str, Any]]] = []

    for idx, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        row.pop("_audit_h2h_top10", None)
        row.pop("_audit_h2h_score", None)
        score = audit_h2h_support_score(row)
        if score > 0:
            scored.append((score, idx, row))

    scored.sort(key=lambda item: (-item[0], item[1]))

    for score, _, row in scored[:10]:
        row["_audit_h2h_top10"] = True
        row["_audit_h2h_score"] = round(score, 3)


def audit_has_h2h_top10(row: Dict[str, Any]) -> bool:
    return bool(row.get("_audit_h2h_top10"))


def audit_has_cloq(row: Dict[str, Any]) -> bool:
    """Return True when an Audit row belongs to the current CloQ shortlist.

    The flag is written during render_all by matching latest_all rows against
    outputs/latest_cloq.json. The direct cloq_passed fallback keeps the filter
    compatible with rows that already carry CloQ metadata.
    """
    return bool(row.get("_audit_cloq") or row.get("cloq_passed"))


def audit_tag_text(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    parts.extend(get_existing_public_tags(row))
    try:
        parts.extend(card_insights(row, notes_for_row(row), limit=8))
    except Exception:
        pass
    return " | ".join(str(x) for x in parts if x).lower().replace("last 10", "l10")


def audit_has_pick_strong(row: Dict[str, Any]) -> bool:
    pick_form, pick_surface_form = form_records(row, "pick")
    for record in (pick_form, pick_surface_form):
        w, l = audit_record_pair(record)
        if w is not None and l is not None and (w + l) >= 8 and w >= 8:
            return True
    return "pick strong" in audit_tag_text(row)


def audit_has_opp_weak(row: Dict[str, Any]) -> bool:
    opp_form, opp_surface_form = form_records(row, "opponent")
    for record in (opp_form, opp_surface_form):
        w, l = audit_record_pair(record)
        if w is not None and l is not None and (w + l) >= 8 and l >= 7:
            return True
    return "opp weak" in audit_tag_text(row)


def audit_has_form_support(row: Dict[str, Any]) -> bool:
    if as_float(row.get("recent_form_edge") or row.get("short_form_edge"), 0.0) > 0:
        return True
    if as_float(row.get("opponent_quality_edge"), 0.0) > 0:
        return True
    text = audit_tag_text(row)
    return any(token in text for token in ("pick strong", "opp weak", "form support", "form+"))


def audit_has_surface_support(row: Dict[str, Any]) -> bool:
    if as_float(row.get("surface_recent_form_edge"), 0.0) > 0:
        return True
    _, surface = elo_edges(row)
    if surface is not None and surface > 0:
        return True
    return "surface support" in audit_tag_text(row)


def audit_has_elo_support(row: Dict[str, Any]) -> bool:
    overall, surface = elo_edges(row)
    return bool((overall is not None and overall > 0) or (surface is not None and surface > 0))


def audit_has_market_with_pick(row: Dict[str, Any]) -> bool:
    text = " | ".join(str(x) for x in (
        row.get("marq_final"),
        row.get("marq_final_display"),
        row.get("final_marq"),
        row.get("market_final"),
        row.get("marq_market_final"),
    ) if x).lower().replace("_", " ")
    if "market with pick" in text:
        return True
    marq_delta = marq_delta_pp(row)
    return marq_delta is not None and marq_delta >= 0


def audit_has_value_positive(row: Dict[str, Any]) -> bool:
    for key in ("corq_value_delta_pp", "value_delta_pp", "expected_value_pct", "ev_pct"):
        val = as_float(row.get(key))
        if val is not None and val > 0:
            return True
    odds = pick_odds(row)
    prob = probability(row)
    if odds and prob is not None:
        p = prob / 100.0 if prob > 1 else prob
        return (p * odds - 1.0) > 0
    return False


def audit_positive_support_count(row: Dict[str, Any]) -> int:
    checks = [
        audit_has_pick_strong(row),
        audit_has_opp_weak(row),
        audit_has_form_support(row),
        audit_has_elo_support(row),
        audit_has_surface_support(row),
        audit_has_market_with_pick(row),
        audit_has_value_positive(row),
        audit_h2h_support_score(row) > 0,
    ]
    return sum(1 for x in checks if x)


def audit_has_positive_tag(row: Dict[str, Any]) -> bool:
    # At least one positive/support signal. Count only positive support tags.
    return audit_positive_support_count(row) >= 1


def audit_has_2plus_positive_tags(row: Dict[str, Any]) -> bool:
    # Two or more positive/support signals. Risk/warning tags are not counted.
    return audit_positive_support_count(row) >= 2

def get_existing_public_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    for key in ("tags", "audit_tags", "audit_filter_tags", "data_notes", "notes", "flags"):
        value = row.get(key)
        if isinstance(value, list):
            tags.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value.strip():
            tags.append(value.strip())
    return tags


def audit_filter_tags_for_row(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    if audit_has_corq_top20(row):
        tags.append(AUDIT_CORQ_TOP20_LABEL)
    if audit_has_up_to_2h_o15(row):
        tags.append(AUDIT_TIME_ODDS_LABEL)
    if audit_has_safe_bet_signal(row):
        tags.append(AUDIT_SAFE_BET_LABEL)
    if audit_has_h2h_top10(row):
        tags.append(AUDIT_H2H_TOP10_LABEL)
    if audit_has_cloq(row):
        tags.append(AUDIT_CLOQ_LABEL)
    if audit_has_opp_weak(row):
        tags.append(AUDIT_OPP_WEAK_LABEL)
    if audit_has_pick_strong(row):
        tags.append(AUDIT_PICK_STRONG_LABEL)
    if audit_has_form_support(row):
        tags.append(AUDIT_FORM_SUPPORT_LABEL)
    if audit_has_elo_support(row):
        tags.append(AUDIT_ELO_SUPPORT_LABEL)
    if audit_has_surface_support(row):
        tags.append(AUDIT_SURFACE_SUPPORT_LABEL)
    if audit_has_market_with_pick(row):
        tags.append(AUDIT_MARKET_WITH_PICK_LABEL)
    if audit_has_value_positive(row):
        tags.append(AUDIT_VALUE_POSITIVE_LABEL)
    if audit_has_positive_tag(row):
        tags.append(AUDIT_POSITIVE_TAG_LABEL)
    if audit_has_2plus_positive_tags(row):
        tags.append(AUDIT_TWO_POSITIVE_TAGS_LABEL)
    existing = row.get("audit_filter_tags")
    if isinstance(existing, list):
        tags.extend(str(x) for x in existing if x)
    out: List[str] = []
    seen = set()
    for tag in tags:
        t = str(tag or "").strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def audit_note_css(label: str) -> str:
    if label == AUDIT_CORQ_TOP20_LABEL:
        return "tag-chip audit-pill audit-pill-corq"
    if label == AUDIT_TIME_ODDS_LABEL:
        return "tag-chip audit-pill audit-pill-signal"
    if label == AUDIT_SAFE_BET_LABEL:
        return "tag-chip audit-pill audit-pill-safe"
    if label == AUDIT_H2H_TOP10_LABEL:
        return "tag-chip audit-pill audit-pill-h2h"
    if label == AUDIT_CLOQ_LABEL:
        return "tag-chip audit-pill audit-pill-signal"
    if label in {AUDIT_OPP_WEAK_LABEL, AUDIT_PICK_STRONG_LABEL, AUDIT_FORM_SUPPORT_LABEL, AUDIT_ELO_SUPPORT_LABEL, AUDIT_SURFACE_SUPPORT_LABEL, AUDIT_MARKET_WITH_PICK_LABEL, AUDIT_VALUE_POSITIVE_LABEL, AUDIT_POSITIVE_TAG_LABEL, AUDIT_TWO_POSITIVE_TAGS_LABEL}:
        return "tag-chip audit-pill audit-pill-safe"
    if label in {RESULT_LAST_3_DAYS_LABEL, RESULT_LAST_7_DAYS_LABEL, RESULT_LAST_MONTH_LABEL, RESULT_THIS_YEAR_LABEL}:
        return "tag-chip audit-pill audit-pill-date"
    if label in {RESULT_MODEL_CORQ_LABEL, RESULT_MODEL_CLOQ_LABEL, RESULT_MODEL_AUDIT_LABEL}:
        return "tag-chip audit-pill audit-pill-model"
    return "tag-chip audit-pill audit-pill-note"

def tag_filter_script() -> str:
    return """
<script>
(function(){
  const active = new Set();

  function getCardTags(card){
    return (card.getAttribute('data-tags') || '')
      .split('|')
      .map(x => x.trim())
      .filter(Boolean);
  }

  function sortVisibleCardsByTime(){
    const gridNodes = document.querySelectorAll('.grid');
    gridNodes.forEach(grid => {
      const cards = Array.from(grid.querySelectorAll('.pick-card'));
      if(!cards.length){ return; }
      cards.sort((a,b) => {
        const av = Number(a.getAttribute('data-start-ts') || '0');
        const bv = Number(b.getAttribute('data-start-ts') || '0');
        if(av === bv){ return 0; }
        if(av === 0){ return 1; }
        if(bv === 0){ return -1; }
        return av - bv;
      }).forEach(card => grid.appendChild(card));
    });
  }

  function applyFilters(){
    document.querySelectorAll('.tag-chip,[data-filter]').forEach(x => {
      const tag = x.dataset.filter;
      if(tag){ x.classList.toggle('active', active.has(tag)); }
    });

    document.querySelectorAll('.pick-card,.result-row').forEach(card => {
      const tags = getCardTags(card);
      const show = Array.from(active).every(tag => tags.includes(tag));
      card.style.display = (!active.size || show) ? '' : 'none';
    });

    document.querySelectorAll('.clear-filter').forEach(x => {
      x.style.display = active.size ? 'inline-flex' : 'none';
    });
  }

  document.addEventListener('click', function(e){
    const clear = e.target.closest('.clear-filter');
    if(clear){
      active.clear();
      applyFilters();
      return;
    }

    const chip = e.target.closest('[data-filter]');
    if(chip){
      const tag = chip.dataset.filter;
      if(!tag){ return; }
      if(active.has(tag)){ active.delete(tag); }
      else{ active.add(tag); }
      applyFilters();
    }
  });
})();
</script>"""


def render_cards_page(title: str, active: str, rows: List[Dict[str, Any]], manifest: Dict[str, Any], page: str = "corq", dedupe: bool = False) -> str:
    rows = dedupe_matches(rows) if dedupe else rows
    for idx, row in enumerate(rows):
        if isinstance(row, dict):
            row["_corq_render_rank"] = idx + 1
    mark_audit_h2h_top10(rows)
    ensure_logs(rows)
    if not rows:
        cards = '<div class="empty">No rows available.</div>'
    else:
        cards = f'<div class="grid" data-page="{esc(page)}">' + "\n".join(render_card(r, i + 1, page=page) for i, r in enumerate(rows)) + '</div>'
    summary = render_notes_summary(rows) if page == "all" else ""
    # Audit page: summary first, then cards. This makes the filter pills usable as the main control panel.
    body = summary + cards if page == "all" else cards
    return page_shell(title, active, body, manifest)


def render_notes_summary(rows: List[Dict[str, Any]]) -> str:
    mark_audit_h2h_top10(rows)
    counts = Counter()
    missing_breakdown = Counter()

    for row in rows:
        row_notes = notes_for_row(row)
        row_audit_tags = audit_filter_tags_for_row(row)

        for note in row_notes + row_audit_tags:
            counts[note] += 1

        if "Missing odds" in row_notes:
            reason = str(row.get("odds_missing_reason_group") or row.get("no_odds_reason") or "Unknown")
            reason = reason.replace("_", " ").title()
            missing_breakdown[reason] += 1

    def sort_key(item: Tuple[str, int]) -> Tuple[int, int, str]:
        label, count = item
        order = {
            AUDIT_CORQ_TOP20_LABEL: 0,
            AUDIT_TIME_ODDS_LABEL: 1,
            AUDIT_CLOQ_LABEL: 2,
            AUDIT_OPP_WEAK_LABEL: 3,
            AUDIT_PICK_STRONG_LABEL: 4,
            AUDIT_FORM_SUPPORT_LABEL: 5,
            AUDIT_ELO_SUPPORT_LABEL: 6,
            AUDIT_SURFACE_SUPPORT_LABEL: 7,
            AUDIT_MARKET_WITH_PICK_LABEL: 8,
            AUDIT_VALUE_POSITIVE_LABEL: 9,
            AUDIT_POSITIVE_TAG_LABEL: 10,
            AUDIT_TWO_POSITIVE_TAGS_LABEL: 11,
            AUDIT_SAFE_BET_LABEL: 13,
            AUDIT_H2H_TOP10_LABEL: 14,
        }.get(label, 20)
        return order, -count, label

    tag_items = sorted(counts.items(), key=sort_key)
    tags = "".join(
        f'<span class="{audit_note_css(k)}" data-filter="{esc(k)}"><span class="audit-pill-count">{v}</span> <span class="audit-pill-label">{esc(k)}</span></span>'
        for k, v in tag_items
    )
    clear = '<span class="clear-filter tag-chip audit-pill audit-pill-clear">Clear filter</span>'

    breakdown = ""
    if missing_breakdown:
        items = "".join(f'<span class="note">{v} {esc(k)}</span>' for k, v in missing_breakdown.most_common())
        breakdown = f'<div class="summary-panel"><div class="summary-title">Missing odds breakdown</div><div class="tag-list">{items}</div></div>'

    return f'<div class="summary-panel data-notes-summary"><div class="summary-title">Data notes summary</div><div class="tag-list data-notes-pills">{tags}{clear}</div></div>{breakdown}'


def result_status(row: Dict[str, Any]) -> str:
    return str(row.get("result") or row.get("result_status") or row.get("status") or "PENDING").upper()


def res_units(value: Any) -> str:
    num = as_float(value)
    if num is None:
        return "—"
    return f"{num:+.2f}u"


def summarize_results(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    won = lost = pending = void = 0
    units = 0.0
    odds_vals = []
    for r in rows:
        st = result_status(r)
        if st == "WON":
            won += 1
        elif st == "LOST":
            lost += 1
        elif st == "VOID":
            void += 1
        else:
            pending += 1
        units += as_float(r.get("units"), 0.0) or 0.0
        od = pick_odds(r)
        if od:
            odds_vals.append(od)
    decided = won + lost
    winp = (won / decided * 100.0) if decided else 0.0
    roi = (units / decided * 100.0) if decided else 0.0
    avg_odds = sum(odds_vals) / len(odds_vals) if odds_vals else None
    return {"picks": len(rows), "won": won, "lost": lost, "pending": pending, "void": void, "win_pct": winp, "units": units, "roi": roi, "avg_odds": avg_odds}


def summary_cards_html(summary: Dict[str, Any], title: str) -> str:
    avg = "—" if summary.get("avg_odds") is None else f"{summary['avg_odds']:.2f}"
    return f"""
<div class="summary-panel"><div class="summary-title">{esc(title)}</div><div class="tag-list">
<span class="note">Picks {summary.get('picks',0)}</span><span class="note">W-L {summary.get('won',0)}-{summary.get('lost',0)}</span><span class="note">Pending {summary.get('pending',0)}</span><span class="note">Win {summary.get('win_pct',0):.1f}%</span><span class="note">Units {summary.get('units',0):+.2f}u</span><span class="note">ROI {summary.get('roi',0):+.1f}%</span><span class="note">Avg odds {esc(avg)}</span>
</div></div>"""




def result_row_date_value(row: Dict[str, Any]) -> Optional[datetime]:
    """Best timestamp for Results filtering.

    Important for L24h: prefer real datetime fields before date-only fields.
    The old logic checked "date" first, so a row from yesterday with
    start_time after the rolling 24h cutoff was reduced to yesterday 00:00 UTC
    and incorrectly missed the L24h filter.
    """

    def _parse_dt(value: Any, assume_local: bool = False) -> Optional[datetime]:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            # Epoch seconds or milliseconds.
            if re.fullmatch(r"\d{10,13}", raw):
                ts = int(raw[:10])
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            normalized = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=WEB_DISPLAY_TIMEZONE if assume_local else timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    # 1) Prefer fields that should contain a full timestamp.
    for key in (
        "result_time_utc",
        "settled_at_utc",
        "settled_time_utc",
        "completed_at_utc",
        "finished_at_utc",
        "end_time_utc",
        "start_time_utc",
        "match_time_utc",
        "result_time",
        "settled_at",
        "settled_time",
        "completed_at",
        "finished_at",
        "end_time",
        "start_time",
        "match_time",
    ):
        dt = _parse_dt(row.get(key), assume_local=not key.endswith("_utc"))
        if dt is not None:
            return dt

    # 2) If only date + HH:MM exists, combine them in Europe/Bratislava.
    date_value = None
    for key in ("date", "snapshot_date", "run_date", "match_date", "top7_match_date_local", "start_date"):
        value = row.get(key)
        if value:
            raw = str(value).strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw[:10]):
                date_value = raw[:10]
                break
    if date_value:
        time_value = None
        for key in ("time", "start_time_display", "match_time_display", "local_time"):
            value = row.get(key)
            if value:
                m = re.search(r"(\d{1,2}):(\d{2})", str(value))
                if m:
                    time_value = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:00"
                    break
        if time_value:
            try:
                local_dt = datetime.fromisoformat(f"{date_value}T{time_value}").replace(tzinfo=WEB_DISPLAY_TIMEZONE)
                return local_dt.astimezone(timezone.utc)
            except Exception:
                pass

    # 3) Last resort for date-only rows. This cannot be exact for L24h, but
    # keeping the date makes existing Last 3/7/month filters work.
    if date_value:
        try:
            local_midnight = datetime.fromisoformat(date_value).replace(tzinfo=WEB_DISPLAY_TIMEZONE)
            return local_midnight.astimezone(timezone.utc)
        except Exception:
            pass

    return None

def result_date_filter_tags(row: Dict[str, Any]) -> List[str]:
    dt = result_row_date_value(row)
    if dt is None:
        return []

    today = datetime.now(timezone.utc).date()
    d = dt.date()
    tags: List[str] = []

    # Rolling range based on UTC timestamp where available.
    if dt >= datetime.now(timezone.utc) - timedelta(hours=24):
        tags.append(RESULT_LAST_24H_LABEL)

    # Inclusive ranges. Example: Last 7 days means today plus the previous 6 days.
    if today - timedelta(days=2) <= d <= today:
        tags.append(RESULT_LAST_3_DAYS_LABEL)
    if today - timedelta(days=6) <= d <= today:
        tags.append(RESULT_LAST_7_DAYS_LABEL)
    if today - timedelta(days=30) <= d <= today:
        tags.append(RESULT_LAST_MONTH_LABEL)
    if d.year == today.year:
        tags.append(RESULT_THIS_YEAR_LABEL)

    return tags


def result_model_filter_tag(row: Dict[str, Any], fallback_title: str = "") -> str:
    model = str(row.get("model") or row.get("source_snapshot") or fallback_title or "").strip().lower()
    if "cloq" in model:
        return RESULT_MODEL_CLOQ_LABEL
    if "audit" in model or "all" in model:
        return RESULT_MODEL_AUDIT_LABEL
    if "corq" in model or "top7" in model:
        return RESULT_MODEL_CORQ_LABEL
    return ""

def result_tags(row: Dict[str, Any]) -> List[str]:
    """Return Results filter/display tags.

    Results must expose the same audit filter signals as the Audit page so the
    settled rows can be filtered by the same bettor-facing signals:
    - CorQ Top20
    - Up to 2H | O>1.5
    - Safe Bet Signal
    - H2H Top10
    plus existing public data notes.
    """
    raw_tags: List[str] = []
    for key in ("tags", "technical_flags", "corq_warning_flags", "top7_risk_tags", "public_notes"):
        val = row.get(key)
        if isinstance(val, list):
            raw_tags.extend(str(x) for x in val if x)
        elif isinstance(val, str) and val:
            raw_tags.append(val)

    public_tags = public_flag_labels(raw_tags, limit=None) if raw_tags else notes_for_row(row)
    audit_tags = audit_filter_tags_for_row(row)
    date_tags = result_date_filter_tags(row)
    model_tag = result_model_filter_tag(row)
    status_tag = result_status(row)

    out: List[str] = []
    seen = set()
    for tag in list(public_tags) + audit_tags + date_tags + [model_tag, status_tag]:
        clean = str(tag or "").strip()
        if not clean:
            continue
        if clean not in seen:
            out.append(clean)
            seen.add(clean)
    return out




def result_lookup(row: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        cur: Any = row
        ok = True
        for part in str(key).split('.'):
            if isinstance(cur, dict) and part in cur:
                cur = cur.get(part)
            else:
                ok = False
                break
        if ok and cur not in (None, "", "—", "-"):
            return cur
    return default


def result_hit_badge(value: Any) -> str:
    if value is True:
        return '<span class="result-tag" style="border-color:#10b981;color:#86efac">HIT</span>'
    if value is False:
        return '<span class="result-tag" style="border-color:#ef4444;color:#fca5a5">MISS</span>'
    return '<span class="result-tag">—</span>'


def result_pct_text(value: Any, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    if abs(num) <= 1.0:
        num *= 100.0
    return f"{num:.1f}%"


def result_pp_text(value: Any, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    return f"{num:+.1f}pp"


def render_mmx_marq_result_cell(row: Dict[str, Any]) -> str:
    thinq_p = result_lookup(row, 'thinq_pick_probability', 'prediction_snapshot.thinq.pick_probability')
    thinq_c = result_lookup(row, 'thinq_data_confidence', 'prediction_snapshot.thinq.data_confidence')
    tw = result_lookup(row, 'mmx_thinq_weight', 'prediction_snapshot.mmx.thinq_weight')
    mw = result_lookup(row, 'mmx_marq_weight', 'prediction_snapshot.mmx.marq_weight')
    marq_p = result_lookup(row, 'marq_pick_probability', 'prediction_snapshot.marq.pick_probability')
    marq_edge = result_lookup(row, 'marq_edge_pct', 'prediction_snapshot.marq.edge_pct')
    move = result_lookup(row, 'marq_move', 'prediction_snapshot.marq.move', default='—')
    clv = result_lookup(row, 'marq_clv_pp', 'prediction_snapshot.marq.clv_pp')
    def weight_txt(v: Any) -> str:
        n = as_float(v)
        if n is None:
            return '—'
        if abs(n) <= 1.0:
            n *= 100.0
        return str(int(round(n)))
    lines = [
        f'<span class="result-tag">TQ {result_pct_text(thinq_p)} | C {result_pct_text(thinq_c)}</span>',
        f'<span class="result-tag">MMx {weight_txt(tw)}/{weight_txt(mw)}</span>',
        f'<span class="result-tag">MarQ {result_pct_text(marq_p)} / {result_pp_text(marq_edge)}</span>',
    ]
    if move != '—' or clv is not None:
        lines.append(f'<span class="result-tag">Move {esc(move)} | CLV {result_pp_text(clv)}</span>')
    return '<br>'.join(lines)


def render_props_result_cell(row: Dict[str, Any]) -> str:
    props = row.get('aces_df') if isinstance(row.get('aces_df'), dict) else {}
    aces_sel = result_lookup(row, 'total_aces_selection', 'prediction_snapshot.aces_df.aces_total_selection', 'aces_df.aces_total_selection')
    aces_proj = result_lookup(row, 'total_aces_projection', 'prediction_snapshot.aces_df.aces_total_projection', 'aces_df.aces_total_projection')
    aces_actual = result_lookup(row, 'actual_total_aces', 'aces_df.actual_total_aces')
    aces_hit = result_lookup(row, 'total_aces_hit', 'aces_df.total_aces_hit')
    df_sel = result_lookup(row, 'total_df_selection', 'prediction_snapshot.aces_df.df_total_selection', 'aces_df.df_total_selection')
    df_proj = result_lookup(row, 'total_df_projection', 'prediction_snapshot.aces_df.df_total_projection', 'aces_df.df_total_projection')
    df_actual = result_lookup(row, 'actual_total_df', 'aces_df.actual_total_df')
    df_hit = result_lookup(row, 'total_df_hit', 'aces_df.total_df_hit')
    src = result_lookup(row, 'api_serve_stats_source', 'prediction_snapshot.aces_df.serve_stats_source')
    lines = []
    if aces_sel or aces_proj is not None or aces_actual is not None:
        lines.append(f'<span class="result-tag">Aces {esc(aces_sel or "—")} | Pred {esc(aces_proj if aces_proj is not None else "—")} -> Real {esc(aces_actual if aces_actual is not None else "—")}</span> {result_hit_badge(aces_hit)}')
    if df_sel or df_proj is not None or df_actual is not None:
        lines.append(f'<span class="result-tag">DF {esc(df_sel or "—")} | Pred {esc(df_proj if df_proj is not None else "—")} -> Real {esc(df_actual if df_actual is not None else "—")}</span> {result_hit_badge(df_hit)}')
    if src:
        lines.append(f'<small>Src: {esc(src)}</small>')
    return '<br>'.join(lines) if lines else '—'
def render_results_table(rows: List[Dict[str, Any]], title: str, limit: Optional[int] = None) -> str:
    def result_table_sort_key(row: Dict[str, Any]) -> Tuple[int, int, str]:
        status_order = {
            "PENDING": 0,
            "WON": 1,
            "LOST": 2,
            "VOID": 3,
        }
        st = result_status(row)
        dt = result_row_date_value(row)
        # Results should look live: today's CorQ bets, even when PENDING,
        # must stay at the top instead of being buried below older settled rows.
        # Negative timestamp lets normal ascending sort show newest dates first.
        ts = -int(dt.timestamp()) if dt is not None else 0
        return (
            ts,
            status_order.get(st, 8),
            pick_name(row).lower(),
        )

    sorted_rows = sorted(rows or [], key=result_table_sort_key)
    show = sorted_rows[:limit] if limit else sorted_rows
    if not show:
        return f'<div class="results-panel"><div class="summary-title">{esc(title)}</div><div class="empty">No evaluated results yet.</div></div>'

    status_counts = Counter(result_status(r) for r in rows or [])
    status_summary = "".join(
        f'<span class="tag-chip result-summary-chip" data-filter="{esc(label)}">{esc(label)} {status_counts.get(label, 0)}</span>'
        for label in ("WON", "LOST", "VOID", "PENDING")
        if status_counts.get(label, 0)
    )

    tag_counts = Counter()
    for source_row in rows or []:
        for tag in result_tags(source_row):
            if tag not in {"WON", "LOST", "VOID", "PENDING"}:
                tag_counts[tag] += 1

    audit_priority = {
        RESULT_MODEL_CORQ_LABEL: 0,
        RESULT_MODEL_CLOQ_LABEL: 1,
        RESULT_MODEL_AUDIT_LABEL: 2,
        RESULT_LAST_24H_LABEL: 9,
        RESULT_LAST_3_DAYS_LABEL: 10,
        RESULT_LAST_7_DAYS_LABEL: 11,
        RESULT_LAST_MONTH_LABEL: 12,
        RESULT_THIS_YEAR_LABEL: 13,
        AUDIT_CORQ_TOP20_LABEL: 20,
        AUDIT_TIME_ODDS_LABEL: 21,
        AUDIT_CLOQ_LABEL: 22,
        AUDIT_SAFE_BET_LABEL: 23,
        AUDIT_H2H_TOP10_LABEL: 24,
        "No previous H2H matches": 24,
        "Recent form pending": 25,
    }

    tag_summary = "".join(
        f'<span class="{audit_note_css(label)}" data-filter="{esc(label)}"><span class="audit-pill-count">{count}</span> <span class="audit-pill-label">{esc(label)}</span></span>'
        for label, count in sorted(tag_counts.items(), key=lambda item: (audit_priority.get(item[0], 50), -item[1], item[0]))
    )
    clear_filter = '<span class="clear-filter tag-chip audit-pill audit-pill-clear">Clear filter</span>'

    body = []
    for r in show:
        tags = result_tags(r)
        data_tags = "|".join(tags)
        tag_html = "".join(f'<span class="result-tag">{esc(t)}</span>' for t in tags[:5])
        st = result_status(r)
        st_cls = "status-won" if st == "WON" else "status-lost" if st == "LOST" else "status-void" if st == "VOID" else "status-pending"
        sg = render_sets_games_result_cell(r)
        body.append(
            f'<tr class="result-row" data-tags="{esc(data_tags)}">'
            f'<td>{esc(r.get("date") or r.get("snapshot_date") or "—")}</td>'
            f'<td><b>{add_rank(pick_name(r), r, "pick")}</b><br><span class="odds-line">Pick @{fmt_odds(pick_odds(r))}</span><br><small>{esc(meta_line(r))}</small></td>'
            f'<td><b>{add_rank(opponent_name(r), r, "opponent")}</b></td>'
            f'<td>{as_pct(probability(r),1)}</td>'
            f'<td>{as_pct(thinq_prob(r),1)}<br><small>C {as_pct(thinq_conf(r),1)}</small></td>'
            f'<td>{render_mmx_marq_result_cell(r)}</td>'
            f'<td>{bar_html(stat_depth(r))}<br>{bar_html(form_depth(r))}</td>'
            f'<td>{signed_pct(pick_edge(r))}</td>'
            f'<td>{sg}</td>'
            f'<td>{render_props_result_cell(r)}</td>'
            f'<td><span class="odds-line">{fmt_odds(pick_odds(r))}</span></td>'
            f'<td class="{st_cls}">{esc(st)}</td>'
            f'<td>{esc(r.get("winner") or "—")}</td>'
            f'<td>{esc(r.get("score") or r.get("final_score") or "—")}</td>'
            f'<td>{esc(res_units(r.get("units")))}</td>'
            f'<td>{tag_html}</td>'
            f'</tr>'
        )
    return f"""
<div class="results-panel"><div class="summary-title">{esc(title)}</div><div class="tag-list result-status-summary">{status_summary}{clear_filter}</div><div class="tag-list result-audit-filter-summary">{tag_summary}</div><div class="table-wrap"><table class="results-table"><thead><tr>
<th>Date</th><th>Pick</th><th>Opponent</th><th>CorQ</th><th>ThinQ</th><th>MMx/MarQ</th><th>Depth</th><th>Pick Edge</th><th>Sets/Games</th><th>Aces/DF</th><th>Odds</th><th>Status</th><th>Winner</th><th>Score</th><th>Units</th><th>Tags</th>
</tr></thead><tbody>{''.join(body)}</tbody></table></div></div>"""


def render_sets_games_result_cell(row: Dict[str, Any]) -> str:
    sg = row.get("sets_games") if isinstance(row.get("sets_games"), dict) else {}
    pred_sets = result_lookup(row, "projected_sets", "sets_games.projected_sets")
    actual_sets = result_lookup(row, "actual_sets", "sets_games.actual_sets")
    sets_sel = result_lookup(row, "sets_selection", "sets_games.sets_selection", "prediction_snapshot.sets_games.sets_selection")
    sets_prob = result_lookup(row, "sets_probability", "sets_games.sets_probability", "prediction_snapshot.sets_games.sets_probability")
    sets_hit = result_lookup(row, "sets_ou_hit", "sets_games.sets_ou_hit")

    pred_games = result_lookup(row, "projected_games", "sets_games.projected_games")
    actual_games = result_lookup(row, "actual_games", "sets_games.actual_games")
    games_sel = result_lookup(row, "games_selection", "sets_games.games_selection", "prediction_snapshot.sets_games.games_selection")
    games_prob = result_lookup(row, "games_probability", "sets_games.games_probability", "prediction_snapshot.sets_games.games_probability")
    games_hit = result_lookup(row, "games_ou_hit", "sets_games.games_ou_hit")
    games_error = result_lookup(row, "games_error", "sets_games.games_error")

    tb_prob = result_lookup(row, "tb_probability", "sets_games.tb_probability", "sets_games.tie_break_probability", "prediction_snapshot.sets_games.tb_probability")
    actual_tb = result_lookup(row, "actual_tiebreak", "sets_games.actual_tiebreak")
    tb_hit = result_lookup(row, "tb_hit", "sets_games.tb_hit")

    bits = []
    if pred_sets is not None or actual_sets is not None or sets_sel:
        prob_txt = f" {result_pct_text(sets_prob)}" if sets_prob is not None else ""
        bits.append(f'<span class="result-tag">Sets: Pred {esc(pred_sets if pred_sets is not None else "—")} | {esc(sets_sel or "—")}{prob_txt} -> Real {esc(actual_sets if actual_sets is not None else "—")}</span> {result_hit_badge(sets_hit)}')
    if pred_games is not None or actual_games is not None or games_sel:
        prob_txt = f" {result_pct_text(games_prob)}" if games_prob is not None else ""
        err_txt = "" if games_error is None else f" · err {as_float(games_error,0):+.1f}"
        bits.append(f'<span class="result-tag">Games: Pred {esc(pred_games if pred_games is not None else "—")} | {esc(games_sel or "—")}{prob_txt} -> Real {esc(actual_games if actual_games is not None else "—")}{esc(err_txt)}</span> {result_hit_badge(games_hit)}')
    if tb_prob is not None or actual_tb is not None:
        tb_real = "Yes" if actual_tb is True else "No" if actual_tb is False else "—"
        bits.append(f'<span class="result-tag">TB: {result_pct_text(tb_prob)} -> Real {esc(tb_real)}</span> {result_hit_badge(tb_hit)}')
    source = result_lookup(row, "sets_games_market_source", "sets_model_source", "sets_games.market_source", "prediction_snapshot.sets_games.market_source")
    if source:
        bits.append(f'<small>Market: {esc(source)}</small>')
    return "<br>".join(bits) if bits else "—"


def tag_analysis(rows: List[Dict[str, Any]]) -> str:
    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "won": 0, "lost": 0, "pending": 0, "units": 0.0, "odds": []})
    for r in rows:
        for t in result_tags(r):
            a = agg[t]
            a["count"] += 1
            st = result_status(r)
            if st == "WON":
                a["won"] += 1
            elif st == "LOST":
                a["lost"] += 1
            else:
                a["pending"] += 1
            a["units"] += as_float(r.get("units"), 0.0) or 0.0
            od = pick_odds(r)
            if od:
                a["odds"].append(od)
    if not agg:
        return '<div class="results-panel"><div class="summary-title">Tag Analysis</div><div class="empty">No tag data yet.</div></div>'
    body = []
    for tag, a in sorted(agg.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        decided = a["won"] + a["lost"]
        winp = a["won"] / decided * 100 if decided else 0.0
        avg = sum(a["odds"]) / len(a["odds"]) if a["odds"] else None
        avg_txt = "—" if avg is None else f"{avg:.2f}"
        body.append(
            f'<tr class="result-row tag-analysis-row" data-tags="{esc(tag)}"><td><span class="tag-chip" data-filter="{esc(tag)}">{esc(tag)}</span></td>'
            f'<td>{a["count"]}</td><td>{a["won"]}-{a["lost"]}-{a["pending"]}</td>'
            f'<td>{winp:.1f}%</td><td>{a["units"]:+.2f}u</td><td>{esc(avg_txt)}</td></tr>'
        )
    return f'<div class="results-panel"><div class="summary-title">Tag Analysis</div><div class="table-wrap"><table class="results-table"><thead><tr><th>Tag</th><th>Count</th><th>W-L-P</th><th>Win %</th><th>Units</th><th>Avg odds</th></tr></thead><tbody>{"".join(body)}</tbody></table></div><span class="clear-filter tag-chip">Clear filter</span></div>'


def bucket_label(value: Optional[float], kind: str) -> str:
    if value is None:
        return "Missing"
    v = value * 100 if value <= 1.0 and kind != "odds" else value
    if kind == "odds":
        if v < 1.5:
            return "<1.50"
        if v < 1.8:
            return "1.50-1.79"
        if v < 2.2:
            return "1.80-2.19"
        return "2.20+"
    if v < 40:
        return "0-39%"
    if v < 60:
        return "40-59%"
    if v < 80:
        return "60-79%"
    return "80-100%"


def depth_analysis(rows: List[Dict[str, Any]]) -> str:
    sections = [
        ("S Data Depth", lambda r: stat_depth(r), "pct"),
        ("F Data Depth", lambda r: form_depth(r), "pct"),
        ("CorQ Probability", lambda r: probability(r), "pct"),
        ("Odds", lambda r: pick_odds(r), "odds"),
    ]
    blocks = []
    for title, getter, kind in sections:
        agg = Counter(bucket_label(getter(r), kind) for r in rows)
        chips = "".join(f'<span class="note">{esc(k)}: {v}</span>' for k, v in sorted(agg.items()))
        blocks.append(f'<div class="summary-title">{esc(title)}</div><div class="tag-list">{chips}</div>')
    return f'<div class="results-panel"><div class="summary-title">Data Depth Analysis</div>{"".join(blocks)}</div>'


def sets_games_audit(rows: List[Dict[str, Any]]) -> str:
    with_games = [r for r in rows if as_float(r.get("actual_games")) is not None]
    sets_rows = [r for r in rows if r.get("sets_hit") is not None]
    tb_rows = [r for r in rows if r.get("actual_tiebreak") is not None or r.get("tie_break_hit") is not None]
    avg_games = sum(as_float(r.get("actual_games"), 0) or 0 for r in with_games) / len(with_games) if with_games else 0
    errors = [as_float(r.get("games_error")) for r in rows if as_float(r.get("games_error")) is not None]
    avg_err = sum(errors) / len(errors) if errors else 0
    sets_hit = sum(1 for r in sets_rows if r.get("sets_hit") is True)
    sets_pct = sets_hit / len(sets_rows) * 100 if sets_rows else 0
    tb_count = sum(1 for r in tb_rows if r.get("actual_tiebreak") is True or r.get("tie_break_hit") is True)
    tb_pct = tb_count / len(tb_rows) * 100 if tb_rows else 0
    return f"""
<div class="results-panel"><div class="summary-title">Sets/Games Audit</div><div class="tag-list">
<span class="note">Rows with games {len(with_games)}</span><span class="note">Avg actual games {avg_games:.1f}</span><span class="note">Avg games error {avg_err:+.1f}</span><span class="note">Sets hit {sets_pct:.1f}%</span><span class="note">Tie-break rate {tb_pct:.1f}%</span>
</div></div>"""




def render_results_filter_builder(rows: List[Dict[str, Any]]) -> str:
    """One compact multi-select filter row for the whole Results page.

    It uses the same data-filter mechanism as cards/tables, so clicking multiple
    pills applies AND filtering across all result tables and analysis rows.
    """
    if not rows:
        return ""

    counts = Counter()
    for row in rows:
        for tag in result_tags(row):
            counts[tag] += 1

    groups = [
        ("Result", ["WON", "LOST", "VOID", "PENDING"]),
        ("Model", [RESULT_MODEL_CORQ_LABEL, RESULT_MODEL_CLOQ_LABEL, RESULT_MODEL_AUDIT_LABEL]),
        ("Date", [RESULT_LAST_24H_LABEL, RESULT_LAST_3_DAYS_LABEL, RESULT_LAST_7_DAYS_LABEL, RESULT_LAST_MONTH_LABEL, RESULT_THIS_YEAR_LABEL]),
        ("Signals", [AUDIT_CORQ_TOP20_LABEL, AUDIT_TIME_ODDS_LABEL, AUDIT_CLOQ_LABEL, AUDIT_OPP_WEAK_LABEL, AUDIT_PICK_STRONG_LABEL, AUDIT_POSITIVE_TAG_LABEL, AUDIT_TWO_POSITIVE_TAGS_LABEL, AUDIT_FORM_SUPPORT_LABEL, AUDIT_ELO_SUPPORT_LABEL, AUDIT_MARKET_WITH_PICK_LABEL, AUDIT_VALUE_POSITIVE_LABEL, AUDIT_SAFE_BET_LABEL, AUDIT_H2H_TOP10_LABEL]),
        ("Data notes", ["No previous H2H matches", "Recent form pending"]),
    ]

    sections: List[str] = []
    used = set()
    for title, labels in groups:
        chips: List[str] = []
        for label in labels:
            count = counts.get(label, 0)
            if not count:
                continue
            used.add(label)
            css_class = audit_note_css(label)
            chips.append(
                f'<span class="{css_class}" data-filter="{esc(label)}">'
                f'<span class="audit-pill-count">{count}</span> '
                f'<span class="audit-pill-label">{esc(label)}</span>'
                f'</span>'
            )
        if chips:
            sections.append(
                f'<div class="result-filter-group"><span class="result-filter-group-title">{esc(title)}</span>{"".join(chips)}</div>'
            )

    # Keep any future/unknown tags available, but do not let them dominate the main row.
    extra_labels = [label for label, count in counts.most_common() if label not in used and label not in {"WON", "LOST", "VOID", "PENDING"}]
    extra_chips: List[str] = []
    for label in extra_labels[:12]:
        count = counts.get(label, 0)
        if not count:
            continue
        extra_chips.append(
            f'<span class="{audit_note_css(label)}" data-filter="{esc(label)}">'
            f'<span class="audit-pill-count">{count}</span> '
            f'<span class="audit-pill-label">{esc(label)}</span>'
            f'</span>'
        )
    if extra_chips:
        sections.append(
            f'<div class="result-filter-group"><span class="result-filter-group-title">Other</span>{"".join(extra_chips)}</div>'
        )

    clear = '<span class="clear-filter tag-chip audit-pill audit-pill-clear">Clear filters</span>'
    return (
        '<div class="results-panel result-filter-builder">'
        '<div class="summary-title">Result filters</div>'
        '<div class="result-filter-help">Click multiple pills to combine filters. Example: CorQ + Last 7 days + WON.</div>'
        '<div class="result-filter-row">'
        + "".join(sections)
        + clear
        + '</div>'
        '</div>'
    )

def render_results_page(manifest: Dict[str, Any]) -> str:
    corq = json_rows(read_json(OUTPUTS / "results" / "latest_results_corq.json", []))
    cloq = json_rows(read_json(OUTPUTS / "results" / "latest_results_cloq.json", []))
    audit_rows = json_rows(read_json(OUTPUTS / "results" / "latest_results_audit.json", []))
    combined = corq + cloq + audit_rows
    # Results page must support the same audit filters as Audit page.
    # H2H Top10 is a relative daily signal, so mark it before building result tags.
    mark_audit_h2h_top10(combined)
    body = [
        render_results_filter_builder(combined),
        summary_cards_html(summarize_results(corq), "CorQ TOP7 Results"),
        summary_cards_html(summarize_results(cloq), "CloQ Results"),
        summary_cards_html(summarize_results(audit_rows), "Audit Results"),
        render_results_table(corq, "CorQ TOP7 Results"),
        render_results_table(cloq, "CloQ Results"),
        render_results_table(audit_rows, "Audit Results", limit=80),
        tag_analysis(combined),
        depth_analysis(combined),
        sets_games_audit(combined),
    ]
    return page_shell("Results", RESULTS_PATH, "\n".join(body), manifest)


def rss_items(rows: List[Dict[str, Any]], title: str) -> str:
    items = []
    for i, row in enumerate(rows[:20], 1):
        name = pick_name(row)
        desc = f"{i}. {name} | {as_pct(probability(row),1)} | {fmt_odds(pick_odds(row))}"
        items.append(f"<item><title>{esc(desc)}</title><description>{esc(desc)}</description></item>")
    return f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(title)}</title><description>AI Betting by BackstageTalks</description>{''.join(items)}</channel></rss>"""



def mark_audit_cloq_rows(all_rows: List[Dict[str, Any]], cloq_rows: List[Dict[str, Any]]) -> None:
    """Mark latest_all rows that are present in the current CloQ shortlist."""
    cloq_keys = {row_match_identity(r) for r in cloq_rows or [] if isinstance(r, dict)}
    cloq_match_ids = {str(r.get("match_id") or r.get("event_id") or r.get("id") or "") for r in cloq_rows or [] if isinstance(r, dict)}
    cloq_match_ids.discard("")
    for row in all_rows or []:
        if not isinstance(row, dict):
            continue
        row.pop("_audit_cloq", None)
        key = row_match_identity(row)
        mid = str(row.get("match_id") or row.get("event_id") or row.get("id") or "")
        if key in cloq_keys or (mid and mid in cloq_match_ids) or row.get("cloq_passed"):
            row["_audit_cloq"] = True


def sort_rows_by_match_time(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return rows sorted by nearest upcoming match time first."""
    now = datetime.now(timezone.utc)
    def key(row: Dict[str, Any]) -> Tuple[int, float, str]:
        dt = audit_match_time_utc(row)
        if dt is None:
            return (2, 10**15, pick_name(row).lower())
        delta = (dt - now).total_seconds()
        if delta >= 0:
            return (0, delta, pick_name(row).lower())
        return (1, abs(delta), pick_name(row).lower())
    return sorted(rows or [], key=key)


def render_all() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_json(OUTPUTS / "latest_manifest.json", {})
    top7 = json_rows(read_json(OUTPUTS / "latest_top7.json", []))
    all_rows = json_rows(read_json(OUTPUTS / "latest_all.json", []))
    cloq = json_rows(read_json(OUTPUTS / "cloq" / "latest_cloq.json", []))
    if not cloq:
        cloq = json_rows(read_json(OUTPUTS / "latest_cloq.json", []))
    mark_audit_cloq_rows(all_rows, cloq)
    all_rows_for_audit = sort_rows_by_match_time(all_rows)
    ensure_logs(top7 + all_rows_for_audit + cloq)

    write_text(SITE_DIR / "index.html", page_shell("CorQ", "root", '<script>location.href="' + esc(TOP7_PATH) + '/"</script>', manifest))
    write_text(SITE_DIR / TOP7_PATH / "index.html", render_cards_page("CorQ", TOP7_PATH, top7, manifest, page="corq"))
    write_text(SITE_DIR / ALL_PATH / "index.html", render_cards_page("Audit", ALL_PATH, all_rows_for_audit, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / CLOQ_PATH / "index.html", render_cards_page("CloQ", CLOQ_PATH, cloq, manifest, page="cloq"))
    write_text(SITE_DIR / THINQ_PATH / "index.html", render_cards_page("ThinQ", THINQ_PATH, all_rows_for_audit, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / RESULTS_PATH / "index.html", render_results_page(manifest))
    write_text(SITE_DIR / CORQ_RSS_PATH, rss_items(top7, "CorQ TOP7"))
    write_text(SITE_DIR / CLOQ_RSS_PATH, rss_items(cloq, "CloQ"))
    write_text(SITE_DIR / THINQ_RSS_PATH, rss_items(all_rows_for_audit[:20], "ThinQ"))
    render_manifest = {
        "rendered_at": datetime.now(tz=timezone.utc).isoformat(),
        "top7_count": len(top7),
        "all_count": len(all_rows_for_audit),
        "cloq_count": len(cloq),
        "site_root": str(SITE_DIR),
    }
    write_text(SITE_DIR / "render_manifest.json", json.dumps(render_manifest, ensure_ascii=False, indent=2))
    print(f"Rendered site: top7={len(top7)} all={len(all_rows_for_audit)} cloq={len(cloq)} root={SITE_DIR}")



# ============================================================
# Results card layout override V2
# This replaces the old table-based Results view with CorQ-style audit cards.
# ============================================================

def _result_css_block() -> str:
    return """
<style>
.results-card-grid{display:grid;gap:14px;margin-top:14px}
.result-card{display:grid;grid-template-columns:minmax(245px,1.10fr) repeat(6,minmax(165px,.95fr));gap:10px;background:rgba(10,18,32,.72);border:1px solid #20314a;border-radius:22px;padding:12px;box-shadow:0 12px 36px rgba(0,0,0,.25)}
.result-section{margin-top:16px;background:#0d1727;border:1px solid #24344d;border-radius:20px;padding:14px}
.result-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
.result-section-title{font-size:12px;color:var(--cyan);font-weight:900;text-transform:uppercase;letter-spacing:.12em}
.result-section-stats{display:flex;flex-wrap:wrap;gap:7px}
.result-stat-pill{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;background:#13243a;border:1px solid #35506f;color:#dbeafe;font-size:11px;font-weight:850}
.result-eval-row{border-radius:9px;margin:2px -4px;padding-left:4px!important;padding-right:4px!important;border-top:1px solid rgba(148,163,184,.14)!important}
.result-eval-row.result-good{background:rgba(16,185,129,.10);box-shadow:inset 3px 0 0 rgba(52,211,153,.95)}
.result-eval-row.result-good b{color:#86efac!important}
.result-eval-row.result-bad{background:rgba(248,113,113,.10);box-shadow:inset 3px 0 0 rgba(248,113,113,.95)}
.result-eval-row.result-bad b{color:#fca5a5!important}
.result-eval-row.result-neutral b{color:#dbeafe!important}
.result-box-good{border-color:rgba(52,211,153,.72)!important;box-shadow:0 0 0 1px rgba(52,211,153,.16),0 0 18px rgba(16,185,129,.11)}
.result-box-bad{border-color:rgba(248,113,113,.78)!important;box-shadow:0 0 0 1px rgba(248,113,113,.16),0 0 18px rgba(248,113,113,.10)}
.result-box-neutral{border-color:#283a55!important}
.result-status-title b.status-won,.result-status-title b.status-hit{color:#34d399!important}
.result-status-title b.status-lost,.result-status-title b.status-miss{color:#f87171!important}
.result-status-title b.status-pending{color:#facc15!important}
.result-status-title b.status-void{color:#94a3b8!important}
.result-card .note{font-size:10px;padding:3px 7px}
.result-tag-row{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.result-filter-builder{position:relative!important;top:auto!important;margin-bottom:14px}
.result-filter-group .audit-pill.active,.result-filter-builder .audit-pill.active{background:rgba(251,146,60,.24)!important;border-color:#fb923c!important;box-shadow:0 0 0 1px rgba(251,146,60,.18),0 0 16px rgba(251,146,60,.13)!important;color:#fff!important}
@media(max-width:1600px){.result-card{grid-template-columns:1fr 1fr 1fr}.result-card .pick-main{grid-column:span 1}}
@media(max-width:900px){.result-card{grid-template-columns:1fr}}
</style>
"""


def _result_eval_class(hit: Any) -> str:
    if hit is True:
        return "result-good"
    if hit is False:
        return "result-bad"
    return "result-neutral"


def _result_box_class(*hits: Any) -> str:
    vals = [h for h in hits if h is not None]
    if not vals:
        return "result-box-neutral"
    if any(v is False for v in vals):
        return "result-box-bad"
    if any(v is True for v in vals):
        return "result-box-good"
    return "result-box-neutral"


def _result_metric(label: str, value: str, hit: Any = None, info_key: Optional[str] = None) -> str:
    key = info_key or _label_info_key(label)
    cls = _result_eval_class(hit)
    return f'<div class="metric-row result-eval-row {cls}"><span class="metric-label">{esc(label)} {info_icon(key)}</span><b>{value}</b></div>'


def _num_text(value: Any, digits: int = 1, none: str = "—") -> str:
    num = as_float(value)
    if num is None:
        return none
    return f"{num:.{digits}f}"


def _prob_text(value: Any, digits: int = 1, none: str = "—") -> str:
    return as_pct(value, digits, none)


def _yes_no(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "—"


def _result_card_pick_box(row: Dict[str, Any], rank: int) -> str:
    notes = result_tags(row)[:6]
    note_html = ''.join(f'<span class="note">{esc(t)}</span>' for t in notes)
    status = result_status(row)
    status_cls = 'status-won' if status == 'WON' else 'status-lost' if status == 'LOST' else 'status-void' if status == 'VOID' else 'status-pending'
    return "\n".join([
        '<div class="pick-main compact-v3">',
        '<div class="compact-topline">',
        f'<span class="rank-num">#{rank}</span>',
        f'<div class="compact-datetime-pill"><span class="compact-date">{esc(start_date(row))}</span><span class="compact-clock">{esc(start_time(row))}</span></div>',
        f'<a class="brain goat-badge" href="{log_link(row)}" title="Open calculation log"><img class="card-goat-logo" src="{goat_badge_src()}" alt="AI"></a>',
        f'<span class="status-pill {status_cls}">{esc(status)}</span>',
        '</div>',
        '<div class="compact-player pick-side no-label">',
        '<div class="compact-name-row">',
        f'<span class="compact-name">{esc(pick_name(row))}<span class="compact-odds pick inline">@ {fmt_odds(pick_odds(row))}</span></span>',
        f'<span class="compact-rank">{esc(player_rank_display(row, "pick"))}</span>',
        '</div></div>',
        '<div class="compact-vs">TO BEAT</div>',
        '<div class="compact-player opp-side no-label">',
        '<div class="compact-name-row">',
        f'<span class="compact-name">{esc(opponent_name(row))}<span class="compact-odds opp inline">@ {fmt_odds(opponent_odds(row))}</span></span>',
        f'<span class="compact-rank">{esc(player_rank_display(row, "opponent"))}</span>',
        '</div></div>',
        '<div class="compact-match"><div class="compact-match-row">',
        f'<span class="compact-meta compact-meta-only">{esc(meta_line(row))}</span>',
        '</div></div>',
        f'<div class="compact-tags bottom-notes">{note_html}</div>' if note_html else '',
        '</div>',
    ])


def _raw_implied_prob(row: Dict[str, Any]) -> Optional[float]:
    odds = pick_odds(row)
    if not odds or odds <= 0:
        return None
    return 1.0 / odds


def _value_delta_pp(row: Dict[str, Any]) -> Optional[float]:
    explicit = result_lookup(row, 'corq_value_delta_pp', 'value_delta_pp', 'prediction_snapshot.value.corq_value_delta_pp')
    num = as_float(explicit)
    if num is not None:
        return num
    prob = probability(row)
    implied = _raw_implied_prob(row)
    if prob is None or implied is None:
        return None
    if prob > 1:
        prob /= 100.0
    return (prob - implied) * 100.0


def _ev_pct(row: Dict[str, Any]) -> Optional[float]:
    explicit = result_lookup(row, 'expected_value_pct', 'ev_pct', 'prediction_snapshot.value.expected_value_pct')
    num = as_float(explicit)
    if num is not None:
        return num
    prob = probability(row)
    odds = pick_odds(row)
    if prob is None or not odds:
        return None
    if prob > 1:
        prob /= 100.0
    return (prob * odds - 1.0) * 100.0


def _price_text(row: Dict[str, Any]) -> str:
    explicit = result_lookup(row, 'price_value_tag', 'price_value_grade', 'prediction_snapshot.value.price')
    if explicit:
        return str(explicit)
    odds = pick_odds(row)
    vd = _value_delta_pp(row)
    if not odds:
        return '—'
    price = 'Short' if odds < 1.50 else 'Fair' if odds < 2.20 else 'Long Risk'
    value = 'Value+' if vd is not None and vd >= 3.0 else 'No Value' if vd is not None and vd < -2.0 else 'Value Neutral'
    return f'{price} | {value}'


def _result_mmx_box(row: Dict[str, Any]) -> str:
    thinq_prob_value = result_lookup(row, 'corq_raw_model_probability', 'thinq_pick_probability', 'prediction_snapshot.thinq.pick_probability')
    marq_prob_value = result_lookup(row, 'corq_market_probability', 'marq_pick_probability', 'marq_crowd_pick_pct', 'prediction_snapshot.marq.pick_probability')
    thinq_input = result_lookup(row, 'corq_thinq_input_pp', 'prediction_snapshot.mmx.thinq_input_pp')
    marq_input = result_lookup(row, 'corq_marq_input_pp', 'prediction_snapshot.mmx.marq_input_pp')
    final_prob = result_lookup(row, 'corq_calibrated_probability', 'corq_probability', 'prediction_snapshot.corq.calibrated_probability')
    delta = marq_delta_pp(row)
    value_delta = _value_delta_pp(row)
    ev = _ev_pct(row)
    return "\n".join([
        '<div class="metric-box mmx-box">',
        f'<div class="box-head"><span>MMx {info_icon("mmx")}</span><b>{esc(mmx_mix_display(row))}</b></div>',
        metric_row('ThinQ P | MarQ P', f'{as_pct(thinq_prob_value,1)} | {as_pct(marq_prob_value,1)}'),
        metric_row('ThinQ In | MarQ In', f'{pp_display(thinq_input,1)} | {pp_display(marq_input,1)}'),
        metric_row('CorQ F | MarQ Δ', f'{as_pct(final_prob,1)} | {pp_display(delta,1)}', sign_class(delta)),
        metric_row('Value Δ', pp_display(value_delta,1), sign_class(value_delta)),
        metric_row('EV', signed_market_pct(ev,1), sign_class(ev)),
        metric_row('Price', esc(_price_text(row)), 'bad' if (value_delta is not None and value_delta < -2) else 'good' if (value_delta is not None and value_delta >= 3) else 'neutral'),
        '</div>',
    ])


def _result_corq_box(row: Dict[str, Any]) -> str:
    pe = pick_edge(row)
    pe_cls = 'good' if pe > 0 else 'bad' if pe < 0 else 'neutral'
    pe_state = 'Support' if pe > 0.0005 else 'Against' if pe < -0.0005 else 'Neutral'
    return "\n".join([
        '<div class="metric-box">',
        f'<div class="box-head"><span>CorQ {info_icon("corq")}</span><b>{as_pct(probability(row),1)}</b></div>',
        metric_row('P EL | S-E', esc(elo_pair_display(row)), elo_pair_class(row)),
        metric_row('O EL | S-E', esc(elo_pair_display(row, opponent=True)), elo_pair_class(row, opponent=True)),
        metric_row('H2H P-O', esc(h2h_display(row)), h2h_class(row)),
        metric_row('S-H2H P-O', esc(surface_h2h_display(row)), surface_h2h_class(row)),
        metric_row('P ThinQ Edge', esc(f'{signed_pct(pe)} | {pe_state}'), pe_cls),
        metric_row('S Data Depth', bar_html(stat_depth(row))),
        '</div>',
    ])


def _result_thinq_box(row: Dict[str, Any]) -> str:
    pf, psf = form_records(row, 'pick')
    of, osf = form_records(row, 'opponent')
    return "\n".join([
        '<div class="metric-box">',
        f'<div class="box-head"><span>ThinQ P | C {info_icon("thinq_pc")}</span><b>{as_pct(thinq_prob(row),1)} | {as_pct(thinq_conf(row),1)}</b></div>',
        metric_row('P F | S-F', esc(f'{pf} | {psf}')),
        metric_row('O F | S-F', esc(f'{of} | {osf}')),
        metric_row('P R-Edge', signed_pct_na(row.get('recent_form_edge') or row.get('short_form_edge')), sign_class(row.get('recent_form_edge') or row.get('short_form_edge'))),
        metric_row('P S-Edge', signed_pct_na(row.get('surface_recent_form_edge')), sign_class(row.get('surface_recent_form_edge'))),
        metric_row('P F Qty', signed_pct_na(row.get('opponent_quality_edge')), sign_class(row.get('opponent_quality_edge'))),
        metric_row('F Data Depth', bar_html(form_depth(row))),
        '</div>',
    ])


def _actual_triplet(row: Dict[str, Any], family: str) -> str:
    if family == 'aces':
        p = result_lookup(row, 'actual_pick_aces', 'aces_df.actual_pick_aces')
        o = result_lookup(row, 'actual_opponent_aces', 'aces_df.actual_opponent_aces')
        t = result_lookup(row, 'actual_total_aces', 'aces_df.actual_total_aces')
    else:
        p = result_lookup(row, 'actual_pick_df', 'aces_df.actual_pick_df')
        o = result_lookup(row, 'actual_opponent_df', 'aces_df.actual_opponent_df')
        t = result_lookup(row, 'actual_total_df', 'aces_df.actual_total_df')
    if p is None and o is None and t is None:
        return '— | — | —'
    return f'{esc(p if p is not None else "—")} | {esc(o if o is not None else "—")} | {esc(t if t is not None else "—")}'


def _result_sets_games_box(row: Dict[str, Any]) -> str:
    pred_sets = result_lookup(row, 'projected_sets', 'sets_games.projected_sets', 'prediction_snapshot.sets_games.projected_sets')
    pred_games = result_lookup(row, 'projected_games', 'sets_games.projected_games', 'prediction_snapshot.sets_games.projected_games')
    actual_sets = result_lookup(row, 'actual_sets', 'sets_games.actual_sets')
    actual_games = result_lookup(row, 'actual_games', 'sets_games.actual_games')
    sets_sel = result_lookup(row, 'sets_selection', 'sets_games.sets_selection', 'prediction_snapshot.sets_games.sets_selection')
    sets_prob = result_lookup(row, 'sets_probability', 'sets_games.sets_probability', 'prediction_snapshot.sets_games.sets_probability')
    games_sel = result_lookup(row, 'games_selection', 'sets_games.games_selection', 'prediction_snapshot.sets_games.games_selection')
    games_prob = result_lookup(row, 'games_probability', 'sets_games.games_probability', 'prediction_snapshot.sets_games.games_probability')
    tb_prob = result_lookup(row, 'tb_probability', 'sets_games.tb_probability', 'prediction_snapshot.sets_games.tb_probability')
    actual_tb = result_lookup(row, 'actual_tiebreak', 'sets_games.actual_tiebreak')
    sets_hit = result_lookup(row, 'sets_ou_hit', 'sets_games.sets_ou_hit')
    games_hit = result_lookup(row, 'games_ou_hit', 'sets_games.games_ou_hit')
    tb_hit = result_lookup(row, 'tb_hit', 'sets_games.tb_hit')
    aces_hit = result_lookup(row, 'total_aces_hit', 'aces_df.total_aces_hit')
    df_hit = result_lookup(row, 'total_df_hit', 'aces_df.total_df_hit')
    box_cls = _result_box_class(sets_hit, games_hit, tb_hit, aces_hit, df_hit)
    return "\n".join([
        f'<div class="metric-box sets-signal-box {box_cls}">',
        f'<div class="box-head"><span>Sets | Games {info_icon("sets_games")}</span><b>{_num_text(pred_sets,1)} | {_num_text(pred_games,1)}</b></div>',
        _result_metric('Sets o|u', f'{esc(sets_sel or "—")} {result_pct_text(sets_prob)} -> Real {esc(actual_sets if actual_sets is not None else "—")}', sets_hit, 'sets_ou'),
        _result_metric('Games o|u', f'{esc(games_sel or "—")} {result_pct_text(games_prob)} -> Real {esc(actual_games if actual_games is not None else "—")}', games_hit, 'games_ou'),
        _result_metric('TB%', f'{result_pct_text(tb_prob)} -> Real {_yes_no(actual_tb)}', tb_hit, 'tb_pct'),
        _result_metric('Aces P | O | T', f'{esc(triplet_market_display(row,"aces"))} -> Real {_actual_triplet(row,"aces")}', aces_hit, 'aces_p_o_t'),
        _result_metric('DF P | O | T', f'{esc(triplet_market_display(row,"df"))} -> Real {_actual_triplet(row,"df")}', df_hit, 'df_p_o_t'),
        metric_row('S Data Depth', bar_html(s_data_depth(row))),
        '</div>',
    ])


def _result_status_box(row: Dict[str, Any]) -> str:
    st = result_status(row)
    units = row.get('units')
    roi = None
    if st in {'WON','LOST'} and units is not None:
        roi = as_float(units)
    box_cls = 'result-box-good' if st == 'WON' else 'result-box-bad' if st == 'LOST' else 'result-box-neutral'
    b_cls = 'status-won' if st == 'WON' else 'status-lost' if st == 'LOST' else 'status-void' if st == 'VOID' else 'status-pending'
    tags = result_tags(row)[:10]
    tag_html = ''.join(f'<span class="note">{esc(t)}</span>' for t in tags)
    return "\n".join([
        f'<div class="metric-box {box_cls}">',
        f'<div class="box-head result-status-title"><span>Result {info_icon("status")}</span><b class="{b_cls}">{esc(st)}</b></div>',
        metric_row('Winner', esc(row.get('winner') or '—')),
        metric_row('Score', esc(row.get('score') or row.get('final_score') or '—')),
        metric_row('Units', esc(res_units(units))),
        metric_row('ROI', esc('—' if roi is None else f'{roi:+.2f}u')),
        f'<div class="result-tag-row">{tag_html}</div>' if tag_html else '',
        '</div>',
    ])


def render_result_card(row: Dict[str, Any], rank: int, model_title: str = '') -> str:
    tags = result_tags(row)
    data_tags = '|'.join(tags)
    return "\n".join([
        f'<div class="result-card tag-analysis-row" data-tags="{esc(data_tags)}" data-result="{esc(result_status(row))}" data-model="{esc(model_title)}">',
        _result_card_pick_box(row, rank),
        _result_mmx_box(row),
        _result_corq_box(row),
        _result_thinq_box(row),
        _result_sets_games_box(row),
        render_marq_box(row),
        _result_status_box(row),
        '</div>',
    ])


def _result_section_header(rows: List[Dict[str, Any]], title: str) -> str:
    s = summarize_results(rows)
    avg = '—' if s.get('avg_odds') is None else f'{s["avg_odds"]:.2f}'
    return "\n".join([
        '<div class="result-section-head">',
        f'<div class="result-section-title">{esc(title)}</div>',
        '<div class="result-section-stats">',
        f'<span class="result-stat-pill">Picks {s["picks"]}</span>',
        f'<span class="result-stat-pill">W-L {s["won"]}-{s["lost"]}</span>',
        f'<span class="result-stat-pill">Pending {s["pending"]}</span>',
        f'<span class="result-stat-pill">Win {s["win_pct"]:.1f}%</span>',
        f'<span class="result-stat-pill">Units {s["units"]:+.2f}u</span>',
        f'<span class="result-stat-pill">ROI {s["roi"]:+.1f}%</span>',
        f'<span class="result-stat-pill">Avg odds {avg}</span>',
        '</div></div>',
    ])


def result_card_sort_key(row: Dict[str, Any]) -> Tuple[int, int, str]:
    status_order = {
        "PENDING": 0,
        "WON": 1,
        "LOST": 2,
        "VOID": 3,
    }
    st = result_status(row)
    dt = result_row_date_value(row)
    ts = -int(dt.timestamp()) if dt is not None else 0
    return (
        ts,
        status_order.get(st, 8),
        pick_name(row).lower(),
    )


def render_results_card_section(rows: List[Dict[str, Any]], title: str, limit: Optional[int] = None) -> str:
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    if limit is not None:
        rows_sorted = rows_sorted[:limit]
    if not rows_sorted:
        cards = '<div class="empty">No results available.</div>'
    else:
        cards = '<div class="results-card-grid">' + '\n'.join(render_result_card(r, i + 1, title) for i, r in enumerate(rows_sorted)) + '</div>'
    return f'<section class="result-section">{_result_section_header(rows_sorted, title)}{cards}</section>'


def render_results_page(manifest: Dict[str, Any]) -> str:
    corq = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_rows = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    combined = corq + cloq + audit_rows

    # Results page supports the same signal tags as Audit. H2H Top10 is a
    # relative signal, so mark it before rendering both cards and long-term
    # analysis sections.
    mark_audit_h2h_top10(combined)

    body = [
        _result_css_block(),
        render_results_filter_builder(combined),
        render_results_card_section(corq, 'CorQ TOP7 Results'),
        render_results_card_section(cloq, 'CloQ Results'),
        render_results_card_section(audit_rows, 'Audit Results', limit=80),

        # Long-term analysis sections restored below the new card layout.
        # These keep the historical stats view without bringing back the old
        # row/table result layout for individual picks.
        tag_analysis(combined),
        depth_analysis(combined),
        sets_games_audit(combined),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


# ============================================================
# Unified risk/support filter override V2
# ============================================================
# Applies to CorQ, CloQ, Audit and Results.  Positive support filters and risk
# filters are intentionally separate so warning tags are never counted as
# positive support.
try:
    _ORIGINAL_AUDIT_FILTER_TAGS_FOR_ROW
except NameError:
    _ORIGINAL_AUDIT_FILTER_TAGS_FOR_ROW = audit_filter_tags_for_row
    _ORIGINAL_AUDIT_NOTE_CSS = audit_note_css

AUDIT_HIGH_RISK_LABEL = "High Risk"
AUDIT_TWO_RISK_TAGS_LABEL = "2+ risk tags"
AUDIT_OPP_STRONG_LABEL = "Opp strong"
AUDIT_PICK_WEAK_LABEL = "Pick weak"
AUDIT_MARKET_AGAINST_LABEL = "Market against pick"
AUDIT_NO_VALUE_LABEL = "No value"
AUDIT_SHORT_PRICE_LABEL = "Short price"
AUDIT_LOW_DATA_LABEL = "Low data risk"
AUDIT_MMX_CONFLICT_LABEL = "MMx conflict"


def _audit_blob(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("tags", "audit_tags", "audit_filter_tags", "public_notes", "top7_risk_tags", "top7_risk_labels", "corq_warning_flags", "risk_flags", "flags"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " | ".join(parts).lower().replace("_", " ")


def _audit_risk_tag_count(row: Dict[str, Any]) -> int:
    value = row.get("top7_risk_count")
    num = as_float(value)
    if num is not None:
        return int(num)
    tags = row.get("top7_risk_tags")
    if isinstance(tags, list):
        return len([t for t in tags if t])
    text = _audit_blob(row)
    risk_tokens = ("high risk", "opp strong", "pick weak", "market against", "no value", "short price", "low data", "mmx model market conflict", "h2h strongly against", "surface h2h against")
    return sum(1 for token in risk_tokens if token in text)


def audit_has_high_risk(row: Dict[str, Any]) -> bool:
    return bool(row.get("top7_high_risk")) or "high risk" in _audit_blob(row) or "high risk pick" in _audit_blob(row)


def audit_has_2plus_risk_tags(row: Dict[str, Any]) -> bool:
    return _audit_risk_tag_count(row) >= 2


def audit_has_opp_strong(row: Dict[str, Any]) -> bool:
    text = _audit_blob(row)
    return "opp strong" in text or "opponent strong" in text or "opp strong form" in text


def audit_has_pick_weak(row: Dict[str, Any]) -> bool:
    text = _audit_blob(row)
    return "pick weak" in text or "pick weak form" in text


def audit_has_market_against_pick(row: Dict[str, Any]) -> bool:
    text = _audit_blob(row)
    market_text = " | ".join(str(x) for x in (row.get("marq_final"), row.get("marq_final_display"), row.get("final_marq"), row.get("market_final"), row.get("marq_market_final")) if x).lower().replace("_", " ")
    delta = marq_delta_pp(row)
    return "market against pick" in text or "market against pick" in market_text or (delta is not None and delta < -3)


def audit_has_no_value(row: Dict[str, Any]) -> bool:
    text = _audit_blob(row)
    if "no value" in text or "no value price" in text:
        return True
    for key in ("corq_value_delta_pp", "value_delta_pp", "expected_value_pct", "ev_pct"):
        val = as_float(row.get(key))
        if val is not None and val < -2:
            return True
    odds = pick_odds(row)
    prob = probability(row)
    if odds and prob is not None:
        p = prob / 100.0 if prob > 1 else prob
        return (p * odds - 1.0) < -0.02
    return False


def audit_has_short_price(row: Dict[str, Any]) -> bool:
    odds = pick_odds(row)
    return bool((odds is not None and odds < 1.50) or "short price" in _audit_blob(row))


def audit_has_low_data_risk(row: Dict[str, Any]) -> bool:
    return "low data" in _audit_blob(row) or "low data confidence" in _audit_blob(row)


def audit_has_mmx_conflict(row: Dict[str, Any]) -> bool:
    return "mmx conflict" in _audit_blob(row) or "model market conflict" in _audit_blob(row)


def audit_filter_tags_for_row(row: Dict[str, Any]) -> List[str]:
    tags = list(_ORIGINAL_AUDIT_FILTER_TAGS_FOR_ROW(row))
    if audit_has_high_risk(row):
        tags.append(AUDIT_HIGH_RISK_LABEL)
    if audit_has_2plus_risk_tags(row):
        tags.append(AUDIT_TWO_RISK_TAGS_LABEL)
    if audit_has_opp_strong(row):
        tags.append(AUDIT_OPP_STRONG_LABEL)
    if audit_has_pick_weak(row):
        tags.append(AUDIT_PICK_WEAK_LABEL)
    if audit_has_market_against_pick(row):
        tags.append(AUDIT_MARKET_AGAINST_LABEL)
    if audit_has_no_value(row):
        tags.append(AUDIT_NO_VALUE_LABEL)
    if audit_has_short_price(row):
        tags.append(AUDIT_SHORT_PRICE_LABEL)
    if audit_has_low_data_risk(row):
        tags.append(AUDIT_LOW_DATA_LABEL)
    if audit_has_mmx_conflict(row):
        tags.append(AUDIT_MMX_CONFLICT_LABEL)
    out: List[str] = []
    seen = set()
    for tag in tags:
        t = str(tag or "").strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def audit_note_css(label: str) -> str:
    if label in {AUDIT_HIGH_RISK_LABEL, AUDIT_TWO_RISK_TAGS_LABEL, AUDIT_OPP_STRONG_LABEL, AUDIT_PICK_WEAK_LABEL, AUDIT_MARKET_AGAINST_LABEL, AUDIT_NO_VALUE_LABEL, AUDIT_SHORT_PRICE_LABEL, AUDIT_LOW_DATA_LABEL, AUDIT_MMX_CONFLICT_LABEL}:
        return "tag-chip audit-pill audit-pill-clear"
    return _ORIGINAL_AUDIT_NOTE_CSS(label)


def render_cards_page(title: str, active: str, rows: List[Dict[str, Any]], manifest: Dict[str, Any], page: str = "corq", dedupe: bool = False) -> str:
    rows = dedupe_matches(rows) if dedupe else rows
    for idx, row in enumerate(rows):
        if isinstance(row, dict):
            row["_corq_render_rank"] = idx + 1
    mark_audit_h2h_top10(rows)
    ensure_logs(rows)
    if not rows:
        cards = '<div class="empty">No rows available.</div>'
    else:
        cards = f'<div class="grid" data-page="{esc(page)}">' + "\n".join(render_card(r, i + 1, page=page) for i, r in enumerate(rows)) + '</div>'
    # CorQ, CloQ and Audit now share the same tag filter panel. Results has its
    # own result_filter_builder, which also uses audit_filter_tags_for_row().
    summary = render_notes_summary(rows) if page in {"corq", "cloq", "all"} else ""
    return page_shell(title, active, summary + cards, manifest)


# ============================================================
# Audit filter/time/odds override V3
# ============================================================
# Fixes audit pill filtering, adds pick odds buckets, and sorts audit cards by
# match start time. This block is intentionally placed before main().

try:
    _AUDIT_FILTER_V3_BASE_AUDIT_FILTER_TAGS_FOR_ROW
except NameError:
    _AUDIT_FILTER_V3_BASE_AUDIT_FILTER_TAGS_FOR_ROW = audit_filter_tags_for_row
    _AUDIT_FILTER_V3_BASE_AUDIT_NOTE_CSS = audit_note_css

AUDIT_PICK_ODDS_UNDER_170_LABEL = "Pick odds <1.70"
AUDIT_PICK_ODDS_OVER_170_LABEL = "Pick odds >=1.70"
AUDIT_SORT_TIME_LABEL = "Sorted by time"


def _audit_v3_datetime_from_text(value: Any, assume_local: bool = False) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text or text in {"—", "-"}:
            return None
        try:
            if re.fullmatch(r"\d{10,13}", text):
                dt = datetime.fromtimestamp(int(text[:10]), tz=timezone.utc)
            else:
                # Accept common API ISO strings and page-render strings.
                raw = text.replace("Z", "+00:00")
                dt = datetime.fromisoformat(raw)
        except Exception:
            return None
    if dt.tzinfo is None:
        tz = ZoneInfo("Europe/Bratislava") if assume_local else timezone.utc
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def audit_parse_datetime_utc(value: Any) -> Optional[datetime]:
    return _audit_v3_datetime_from_text(value, assume_local=False)


def audit_match_time_utc(row: Dict[str, Any]) -> Optional[datetime]:
    # Prefer exact UTC/API datetime fields.
    for key in (
        "match_time_utc", "start_time_utc", "commence_time", "start_time",
        "match_time", "event_start_time", "scheduled_at", "scheduled_time",
    ):
        dt = _audit_v3_datetime_from_text(row.get(key), assume_local=False)
        if dt is not None:
            return dt

    # Some rows carry date and local time separately. Treat those as Europe/Bratislava.
    date_value = _first_data_value(row, "match_date", "date", "start_date")
    time_value = _first_data_value(row, "start_time_local", "match_time_local", "time", "start_hour")
    if date_value and time_value:
        date_text = str(date_value).strip()[:10]
        time_text = str(time_value).strip()
        dt = _audit_v3_datetime_from_text(f"{date_text}T{time_text}", assume_local=True)
        if dt is not None:
            return dt

    for parent in ("market", "event", "raw", "match"):
        ctx = row.get(parent)
        if isinstance(ctx, dict):
            for key in ("commence_time", "start_time_utc", "start_time", "match_time_utc", "scheduled_at"):
                dt = _audit_v3_datetime_from_text(ctx.get(key), assume_local=False)
                if dt is not None:
                    return dt
    return None


def audit_has_up_to_2h_o15(row: Dict[str, Any]) -> bool:
    odds = pick_odds(row)
    if odds is None or odds <= 1.50:
        return False
    status = normal_status(row)
    if status and status not in {"prematch", "pre-match", "notstarted", "not_started", "scheduled", "pending", "open", ""}:
        return False
    dt = audit_match_time_utc(row)
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    return now <= dt <= now + timedelta(hours=2)


def audit_has_pick_odds_under_170(row: Dict[str, Any]) -> bool:
    odds = pick_odds(row)
    return odds is not None and odds < 1.70


def audit_has_pick_odds_over_170(row: Dict[str, Any]) -> bool:
    odds = pick_odds(row)
    return odds is not None and odds >= 1.70


def audit_positive_support_count(row: Dict[str, Any]) -> int:
    # Count positive support only. Risk/warning tags are intentionally excluded.
    checks = [
        audit_has_pick_strong(row),
        audit_has_opp_weak(row),
        audit_has_form_support(row),
        audit_has_elo_support(row),
        audit_has_surface_support(row),
        audit_has_market_with_pick(row),
        audit_has_value_positive(row),
        audit_h2h_support_score(row) > 0,
    ]
    return sum(1 for x in checks if x)


def audit_has_positive_tag(row: Dict[str, Any]) -> bool:
    return audit_positive_support_count(row) >= 1


def audit_has_2plus_positive_tags(row: Dict[str, Any]) -> bool:
    return audit_positive_support_count(row) >= 2


def audit_filter_tags_for_row(row: Dict[str, Any]) -> List[str]:
    tags = list(_AUDIT_FILTER_V3_BASE_AUDIT_FILTER_TAGS_FOR_ROW(row))
    if audit_has_positive_tag(row):
        tags.append(AUDIT_POSITIVE_TAG_LABEL)
    if audit_has_2plus_positive_tags(row):
        tags.append(AUDIT_TWO_POSITIVE_TAGS_LABEL)
    if audit_has_pick_odds_under_170(row):
        tags.append(AUDIT_PICK_ODDS_UNDER_170_LABEL)
    if audit_has_pick_odds_over_170(row):
        tags.append(AUDIT_PICK_ODDS_OVER_170_LABEL)
    dt = audit_match_time_utc(row)
    if dt is not None:
        tags.append(AUDIT_SORT_TIME_LABEL)
    out: List[str] = []
    seen = set()
    for tag in tags:
        t = str(tag or "").strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def audit_note_css(label: str) -> str:
    if label in {AUDIT_PICK_ODDS_UNDER_170_LABEL, AUDIT_PICK_ODDS_OVER_170_LABEL, AUDIT_SORT_TIME_LABEL}:
        return "tag-chip audit-pill audit-pill-signal"
    if label in {AUDIT_POSITIVE_TAG_LABEL, AUDIT_TWO_POSITIVE_TAGS_LABEL}:
        return "tag-chip audit-pill audit-pill-safe"
    return _AUDIT_FILTER_V3_BASE_AUDIT_NOTE_CSS(label)


def _audit_v3_time_sort_key(row: Dict[str, Any]) -> tuple:
    dt = audit_match_time_utc(row)
    if dt is None:
        return (1, 9999999999, audit_corq_rank(row) or 9999)
    return (0, int(dt.timestamp()), audit_corq_rank(row) or 9999)


def tag_filter_script() -> str:
    return """
<script>
(function(){
  const active = new Set();

  function getCardTags(card){
    return (card.getAttribute('data-tags') || '')
      .split('|')
      .map(x => x.trim())
      .filter(Boolean);
  }

  function sortVisibleCardsByTime(){
    document.querySelectorAll('.grid').forEach(grid => {
      if((grid.getAttribute('data-page') || '') !== 'all'){
        return;
      }
      const cards = Array.from(grid.querySelectorAll('.pick-card'));
      if(!cards.length){ return; }
      cards.sort((a,b) => {
        const av = Number(a.getAttribute('data-start-ts') || '0');
        const bv = Number(b.getAttribute('data-start-ts') || '0');
        const aa = av > 0 ? av : 9999999999;
        const bb = bv > 0 ? bv : 9999999999;
        return aa - bb;
      });
      cards.forEach(card => grid.appendChild(card));
    });
  }

  function applyFilters(){
    document.querySelectorAll('[data-filter]').forEach(chip => {
      const tag = chip.dataset.filter || '';
      chip.classList.toggle('active', active.has(tag));
    });

    document.querySelectorAll('.pick-card,.result-row,.result-card').forEach(card => {
      const tags = getCardTags(card);
      const show = Array.from(active).every(tag => tags.includes(tag));
      card.style.display = (!active.size || show) ? '' : 'none';
    });

    document.querySelectorAll('.clear-filter').forEach(x => {
      x.style.display = active.size ? 'inline-flex' : 'none';
    });

    sortVisibleCardsByTime();
  }

  document.addEventListener('click', function(e){
    const clear = e.target.closest('.clear-filter');
    if(clear){
      active.clear();
      applyFilters();
      return;
    }

    const chip = e.target.closest('[data-filter]');
    if(chip){
      const tag = chip.dataset.filter;
      if(!tag){ return; }
      if(active.has(tag)){ active.delete(tag); }
      else{ active.add(tag); }
      applyFilters();
    }
  });

  sortVisibleCardsByTime();
})();
</script>"""


def render_cards_page(title: str, active: str, rows: List[Dict[str, Any]], manifest: Dict[str, Any], page: str = "corq", dedupe: bool = False) -> str:
    rows = dedupe_matches(rows) if dedupe else rows
    for idx, row in enumerate(rows):
        if isinstance(row, dict):
            row["_corq_render_rank"] = idx + 1
    mark_audit_h2h_top10(rows)
    ensure_logs(rows)
    if page == "all":
        rows = sorted(rows, key=_audit_v3_time_sort_key)
    if not rows:
        cards = '<div class="empty">No rows available.</div>'
    else:
        cards = f'<div class="grid" data-page="{esc(page)}">' + "\n".join(render_card(r, i + 1, page=page) for i, r in enumerate(rows)) + '</div>'
    summary = render_notes_summary(rows) if page in {"corq", "cloq", "all"} else ""
    return page_shell(title, active, summary + cards, manifest)


# ============================================================
# Audit mandatory filter panel override V4
# ============================================================
# Ensures key Audit filters are always visible in the Data Notes Summary,
# not only when they happen to appear in Counter.most_common ordering.

try:
    AUDIT_PICK_ODDS_UNDER_170_LABEL
except NameError:
    AUDIT_PICK_ODDS_UNDER_170_LABEL = "Pick odds <1.70"
    AUDIT_PICK_ODDS_OVER_170_LABEL = "Pick odds >=1.70"
    AUDIT_SORT_TIME_LABEL = "Sorted by time"


def audit_has_pick_odds_under_170(row: Dict[str, Any]) -> bool:
    odds = pick_odds(row)
    return odds is not None and odds < 1.70


def audit_has_pick_odds_over_170(row: Dict[str, Any]) -> bool:
    odds = pick_odds(row)
    return odds is not None and odds >= 1.70


try:
    _AUDIT_FILTER_V4_BASE_AUDIT_FILTER_TAGS_FOR_ROW
except NameError:
    _AUDIT_FILTER_V4_BASE_AUDIT_FILTER_TAGS_FOR_ROW = audit_filter_tags_for_row
    _AUDIT_FILTER_V4_BASE_AUDIT_NOTE_CSS = audit_note_css


def audit_filter_tags_for_row(row: Dict[str, Any]) -> List[str]:
    tags = list(_AUDIT_FILTER_V4_BASE_AUDIT_FILTER_TAGS_FOR_ROW(row))
    if audit_has_pick_odds_under_170(row):
        tags.append(AUDIT_PICK_ODDS_UNDER_170_LABEL)
    if audit_has_pick_odds_over_170(row):
        tags.append(AUDIT_PICK_ODDS_OVER_170_LABEL)
    dt = audit_match_time_utc(row)
    if dt is not None:
        tags.append(AUDIT_SORT_TIME_LABEL)
    if audit_has_positive_tag(row):
        tags.append(AUDIT_POSITIVE_TAG_LABEL)
    if audit_has_2plus_positive_tags(row):
        tags.append(AUDIT_TWO_POSITIVE_TAGS_LABEL)
    out: List[str] = []
    seen = set()
    for tag in tags:
        t = str(tag or "").strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def audit_note_css(label: str) -> str:
    if label in {AUDIT_PICK_ODDS_UNDER_170_LABEL, AUDIT_PICK_ODDS_OVER_170_LABEL, AUDIT_SORT_TIME_LABEL, AUDIT_TIME_ODDS_LABEL}:
        return "tag-chip audit-pill audit-pill-signal"
    if label in {AUDIT_POSITIVE_TAG_LABEL, AUDIT_TWO_POSITIVE_TAGS_LABEL}:
        return "tag-chip audit-pill audit-pill-safe"
    return _AUDIT_FILTER_V4_BASE_AUDIT_NOTE_CSS(label)


def render_notes_summary(rows: List[Dict[str, Any]]) -> str:
    mark_audit_h2h_top10(rows)
    counts = Counter()
    missing_breakdown = Counter()

    for row in rows:
        row_notes = notes_for_row(row)
        row_audit_tags = audit_filter_tags_for_row(row)
        for note in row_notes + row_audit_tags:
            counts[note] += 1
        if "Missing odds" in row_notes:
            reason = str(row.get("odds_missing_reason_group") or row.get("no_odds_reason") or "Unknown")
            reason = reason.replace("_", " ").title()
            missing_breakdown[reason] += 1

    # Force the important controls to the front and keep them visible even if zero.
    mandatory_order = [
        AUDIT_TIME_ODDS_LABEL,
        AUDIT_PICK_ODDS_UNDER_170_LABEL,
        AUDIT_PICK_ODDS_OVER_170_LABEL,
        AUDIT_POSITIVE_TAG_LABEL,
        AUDIT_TWO_POSITIVE_TAGS_LABEL,
        AUDIT_OPP_WEAK_LABEL,
        AUDIT_PICK_STRONG_LABEL,
        AUDIT_MARKET_WITH_PICK_LABEL,
        AUDIT_VALUE_POSITIVE_LABEL,
        AUDIT_CLOQ_LABEL,
        AUDIT_H2H_TOP10_LABEL,
        AUDIT_TWO_RISK_TAGS_LABEL if 'AUDIT_TWO_RISK_TAGS_LABEL' in globals() else "2+ risk tags",
        AUDIT_NO_VALUE_LABEL if 'AUDIT_NO_VALUE_LABEL' in globals() else "No value",
        AUDIT_HIGH_RISK_LABEL if 'AUDIT_HIGH_RISK_LABEL' in globals() else "High Risk",
        AUDIT_SHORT_PRICE_LABEL if 'AUDIT_SHORT_PRICE_LABEL' in globals() else "Short price",
    ]

    items: List[Tuple[str, int]] = []
    seen_labels = set()
    for label in mandatory_order:
        if not label or label in seen_labels:
            continue
        items.append((label, counts.get(label, 0)))
        seen_labels.add(label)

    def rest_key(item: Tuple[str, int]) -> Tuple[int, str]:
        label, count = item
        return (-count, label)

    for label, count in sorted(counts.items(), key=rest_key):
        if label not in seen_labels:
            items.append((label, count))
            seen_labels.add(label)

    tags = "".join(
        f'<span class="{audit_note_css(k)}" data-filter="{esc(k)}"><span class="audit-pill-count">{v}</span> <span class="audit-pill-label">{esc(k)}</span></span>'
        for k, v in items
    )
    clear = '<span class="clear-filter tag-chip audit-pill audit-pill-clear">Clear filter</span>'

    breakdown = ""
    if missing_breakdown:
        breakdown_items = "".join(f'<span class="note">{v} {esc(k)}</span>' for k, v in missing_breakdown.most_common())
        breakdown = f'<div class="summary-panel"><div class="summary-title">Missing odds breakdown</div><div class="tag-list">{breakdown_items}</div></div>'

    return f'<div class="summary-panel data-notes-summary"><div class="summary-title">Data notes summary</div><div class="tag-list data-notes-pills">{tags}{clear}</div></div>{breakdown}'


# ============================================================
# Audit filter hard-fix override V5
# ============================================================
# Fixes chip filtering by using normalized tag keys, adds a dedicated
# "1 positive tag" filter, and keeps "Positive tag" as 1+ positive support.

AUDIT_ONE_POSITIVE_TAG_LABEL = "1 positive tag"

try:
    _AUDIT_FILTER_V5_BASE_AUDIT_FILTER_TAGS_FOR_ROW
except NameError:
    _AUDIT_FILTER_V5_BASE_AUDIT_FILTER_TAGS_FOR_ROW = audit_filter_tags_for_row
    _AUDIT_FILTER_V5_BASE_AUDIT_NOTE_CSS = audit_note_css


def audit_has_1_positive_tag(row: Dict[str, Any]) -> bool:
    return audit_positive_support_count(row) == 1


def audit_filter_tags_for_row(row: Dict[str, Any]) -> List[str]:
    tags = list(_AUDIT_FILTER_V5_BASE_AUDIT_FILTER_TAGS_FOR_ROW(row))
    if audit_has_positive_tag(row):
        tags.append(AUDIT_POSITIVE_TAG_LABEL)
    if audit_has_1_positive_tag(row):
        tags.append(AUDIT_ONE_POSITIVE_TAG_LABEL)
    if audit_has_2plus_positive_tags(row):
        tags.append(AUDIT_TWO_POSITIVE_TAGS_LABEL)
    if 'AUDIT_PICK_ODDS_UNDER_170_LABEL' in globals() and audit_has_pick_odds_under_170(row):
        tags.append(AUDIT_PICK_ODDS_UNDER_170_LABEL)
    if 'AUDIT_PICK_ODDS_OVER_170_LABEL' in globals() and audit_has_pick_odds_over_170(row):
        tags.append(AUDIT_PICK_ODDS_OVER_170_LABEL)
    dt = audit_match_time_utc(row)
    if dt is not None and 'AUDIT_SORT_TIME_LABEL' in globals():
        tags.append(AUDIT_SORT_TIME_LABEL)
    out: List[str] = []
    seen = set()
    for tag in tags:
        t = str(tag or "").strip()
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def audit_note_css(label: str) -> str:
    if label in {AUDIT_POSITIVE_TAG_LABEL, AUDIT_ONE_POSITIVE_TAG_LABEL, AUDIT_TWO_POSITIVE_TAGS_LABEL}:
        return "tag-chip audit-pill audit-pill-safe"
    return _AUDIT_FILTER_V5_BASE_AUDIT_NOTE_CSS(label)


def _audit_v5_summary_order(label: str) -> int:
    order = {
        AUDIT_TIME_ODDS_LABEL: 0,
        globals().get('AUDIT_PICK_ODDS_UNDER_170_LABEL', 'Pick odds <1.70'): 1,
        globals().get('AUDIT_PICK_ODDS_OVER_170_LABEL', 'Pick odds >=1.70'): 2,
        AUDIT_POSITIVE_TAG_LABEL: 3,
        AUDIT_ONE_POSITIVE_TAG_LABEL: 4,
        AUDIT_TWO_POSITIVE_TAGS_LABEL: 5,
        AUDIT_OPP_WEAK_LABEL: 6,
        AUDIT_PICK_STRONG_LABEL: 7,
        AUDIT_FORM_SUPPORT_LABEL: 8,
        AUDIT_ELO_SUPPORT_LABEL: 9,
        AUDIT_SURFACE_SUPPORT_LABEL: 10,
        AUDIT_MARKET_WITH_PICK_LABEL: 11,
        AUDIT_VALUE_POSITIVE_LABEL: 12,
        AUDIT_CLOQ_LABEL: 13,
        AUDIT_H2H_TOP10_LABEL: 14,
        globals().get('AUDIT_TWO_RISK_TAGS_LABEL', '2+ risk tags'): 15,
        globals().get('AUDIT_NO_VALUE_LABEL', 'No value'): 16,
        globals().get('AUDIT_HIGH_RISK_LABEL', 'High Risk'): 17,
        globals().get('AUDIT_SHORT_PRICE_LABEL', 'Short price'): 18,
    }
    return order.get(label, 100)


def render_notes_summary(rows: List[Dict[str, Any]]) -> str:
    mark_audit_h2h_top10(rows)
    counts = Counter()
    missing_breakdown = Counter()
    for row in rows:
        row_notes = notes_for_row(row)
        row_audit_tags = audit_filter_tags_for_row(row)
        for note in row_notes + row_audit_tags:
            counts[note] += 1
        if "Missing odds" in row_notes:
            reason = str(row.get("odds_missing_reason_group") or row.get("no_odds_reason") or "Unknown")
            missing_breakdown[reason.replace("_", " ").title()] += 1

    mandatory = [
        AUDIT_TIME_ODDS_LABEL,
        globals().get('AUDIT_PICK_ODDS_UNDER_170_LABEL', 'Pick odds <1.70'),
        globals().get('AUDIT_PICK_ODDS_OVER_170_LABEL', 'Pick odds >=1.70'),
        AUDIT_POSITIVE_TAG_LABEL,
        AUDIT_ONE_POSITIVE_TAG_LABEL,
        AUDIT_TWO_POSITIVE_TAGS_LABEL,
        AUDIT_OPP_WEAK_LABEL,
        AUDIT_PICK_STRONG_LABEL,
        AUDIT_FORM_SUPPORT_LABEL,
        AUDIT_ELO_SUPPORT_LABEL,
        AUDIT_SURFACE_SUPPORT_LABEL,
        AUDIT_MARKET_WITH_PICK_LABEL,
        AUDIT_VALUE_POSITIVE_LABEL,
        AUDIT_CLOQ_LABEL,
        AUDIT_H2H_TOP10_LABEL,
        globals().get('AUDIT_TWO_RISK_TAGS_LABEL', '2+ risk tags'),
        globals().get('AUDIT_NO_VALUE_LABEL', 'No value'),
        globals().get('AUDIT_HIGH_RISK_LABEL', 'High Risk'),
        globals().get('AUDIT_SHORT_PRICE_LABEL', 'Short price'),
    ]
    items: List[Tuple[str, int]] = []
    seen = set()
    for label in mandatory:
        if label and label not in seen:
            items.append((label, counts.get(label, 0)))
            seen.add(label)
    rest = [(k, v) for k, v in counts.items() if k not in seen]
    rest.sort(key=lambda kv: (_audit_v5_summary_order(kv[0]), -kv[1], kv[0]))
    items.extend(rest)

    tags = "".join(
        f'<span class="{audit_note_css(k)}" data-filter="{esc(k)}" data-filter-key="{esc(k.lower().strip())}"><span class="audit-pill-count">{v}</span> <span class="audit-pill-label">{esc(k)}</span></span>'
        for k, v in items
    )
    clear = '<span class="clear-filter tag-chip audit-pill audit-pill-clear">Clear filter</span>'
    counter = '<span class="tag-chip audit-pill audit-pill-note audit-filter-counter" data-filter-counter></span>'
    breakdown = ""
    if missing_breakdown:
        items_html = "".join(f'<span class="note">{v} {esc(k)}</span>' for k, v in missing_breakdown.most_common())
        breakdown = f'<div class="summary-panel"><div class="summary-title">Missing odds breakdown</div><div class="tag-list">{items_html}</div></div>'
    return f'<div class="summary-panel data-notes-summary"><div class="summary-title">Data notes summary</div><div class="tag-list data-notes-pills">{tags}{clear}{counter}</div></div>{breakdown}'


def tag_filter_script() -> str:
    return """
<script>
(function(){
  const active = new Map();
  const norm = value => String(value || '').trim().toLowerCase();

  function getCardTags(card){
    return (card.getAttribute('data-tags') || '')
      .split('|')
      .map(norm)
      .filter(Boolean);
  }

  function sortVisibleCardsByTime(){
    document.querySelectorAll('.grid').forEach(grid => {
      if((grid.getAttribute('data-page') || '') !== 'all'){
        return;
      }
      const cards = Array.from(grid.querySelectorAll('.pick-card'));
      if(!cards.length){ return; }
      cards.sort((a,b) => {
        const av = Number(a.getAttribute('data-start-ts') || '0');
        const bv = Number(b.getAttribute('data-start-ts') || '0');
        const aa = av > 0 ? av : 9999999999;
        const bb = bv > 0 ? bv : 9999999999;
        return aa - bb;
      });
      cards.forEach(card => grid.appendChild(card));
    });
  }

  function applyFilters(){
    document.querySelectorAll('[data-filter]').forEach(chip => {
      const key = norm(chip.dataset.filterKey || chip.dataset.filter || '');
      chip.classList.toggle('active', active.has(key));
    });

    let total = 0;
    let visible = 0;
    const wanted = Array.from(active.keys());
    document.querySelectorAll('.pick-card,.result-row,.result-card').forEach(card => {
      total += 1;
      const tags = getCardTags(card);
      const show = wanted.every(tag => tags.includes(tag));
      card.style.setProperty('display', (!wanted.length || show) ? '' : 'none', 'important');
      if(!wanted.length || show){ visible += 1; }
    });

    document.querySelectorAll('.clear-filter').forEach(x => {
      x.style.display = wanted.length ? 'inline-flex' : 'none';
    });
    document.querySelectorAll('[data-filter-counter]').forEach(x => {
      x.textContent = wanted.length ? `${visible}/${total} visible` : '';
      x.style.display = wanted.length ? 'inline-flex' : 'none';
    });
    sortVisibleCardsByTime();
  }

  document.addEventListener('click', function(e){
    const clear = e.target.closest('.clear-filter');
    if(clear){
      active.clear();
      applyFilters();
      return;
    }
    const chip = e.target.closest('[data-filter]');
    if(chip){
      const raw = chip.dataset.filter || '';
      const key = norm(chip.dataset.filterKey || raw);
      if(!key){ return; }
      if(active.has(key)){ active.delete(key); }
      else{ active.set(key, raw); }
      applyFilters();
      e.preventDefault();
    }
  });
  sortVisibleCardsByTime();
})();
</script>"""


# ============================================================
# Results tag stats full override V1
# ============================================================
# Appends a complete tag stats table to the bottom of Results and sorts it by
# decided winrate from best to worst. Includes all current Audit/Results tags.

RESULTS_TAG_STATS_TITLE = "Tag Stats by Winrate"


def _results_tag_stats_rows(rows: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "won": 0,
        "lost": 0,
        "void": 0,
        "pending": 0,
        "units": 0.0,
        "odds": [],
    })
    for row in rows or []:
        for tag in result_tags(row):
            t = str(tag or "").strip()
            if not t:
                continue
            a = agg[t]
            a["count"] += 1
            st = result_status(row)
            if st == "WON":
                a["won"] += 1
            elif st == "LOST":
                a["lost"] += 1
            elif st == "VOID":
                a["void"] += 1
            else:
                a["pending"] += 1
            a["units"] += as_float(row.get("units"), 0.0) or 0.0
            od = pick_odds(row)
            if od:
                a["odds"].append(od)
    def sort_key(item: Tuple[str, Dict[str, Any]]) -> Tuple[float, int, float, int, str]:
        tag, a = item
        decided = int(a["won"] + a["lost"])
        winrate = (a["won"] / decided) if decided else -1.0
        units = float(a.get("units") or 0.0)
        # Decided tags first, then best winrate, then sample size, then units.
        return (winrate, decided, units, int(a["count"]), tag)
    return sorted(agg.items(), key=sort_key, reverse=True)


def tag_analysis(rows: List[Dict[str, Any]]) -> str:
    tag_rows = _results_tag_stats_rows(rows)
    if not tag_rows:
        return '<div class="results-panel"><div class="summary-title">Tag Stats by Winrate</div><div class="empty">No tag data yet.</div></div>'
    body = []
    for tag, a in tag_rows:
        decided = int(a["won"] + a["lost"])
        winp = a["won"] / decided * 100 if decided else 0.0
        avg = sum(a["odds"]) / len(a["odds"]) if a["odds"] else None
        avg_txt = "—" if avg is None else f"{avg:.2f}"
        decided_txt = f"{decided}/{a['count']}"
        body.append(
            f'<tr class="result-row tag-analysis-row" data-tags="{esc(tag)}">'
            f'<td><span class="{audit_note_css(tag)}" data-filter="{esc(tag)}">{esc(tag)}</span></td>'
            f'<td>{a["count"]}</td>'
            f'<td>{a["won"]}-{a["lost"]}-{a["void"]}-{a["pending"]}</td>'
            f'<td>{decided_txt}</td>'
            f'<td><b>{winp:.1f}%</b></td>'
            f'<td>{a["units"]:+.2f}u</td>'
            f'<td>{esc(avg_txt)}</td>'
            f'</tr>'
        )
    return (
        '<div class="results-panel tag-stats-panel">'
        f'<div class="summary-title">{RESULTS_TAG_STATS_TITLE}</div>'
        '<div class="result-filter-help">Sorted by decided winrate from best to worst. W-L-V-P = Won, Lost, Void, Pending.</div>'
        '<div class="table-wrap"><table class="results-table"><thead><tr>'
        '<th>Tag</th><th>Total</th><th>W-L-V-P</th><th>Decided</th><th>Winrate</th><th>Units</th><th>Avg odds</th>'
        '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
        '<span class="clear-filter tag-chip audit-pill audit-pill-clear">Clear filter</span>'
        '</div>'
    )


def render_results_page(manifest: Dict[str, Any]) -> str:
    corq = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_rows = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    combined = corq + cloq + audit_rows
    mark_audit_h2h_top10(combined)
    body = [
        _result_css_block(),
        render_results_filter_builder(combined),
        render_results_card_section(corq, 'CorQ TOP7 Results'),
        render_results_card_section(cloq, 'CloQ Results'),
        render_results_card_section(audit_rows, 'Audit Results', limit=80),
        depth_analysis(combined),
        sets_games_audit(combined),
        tag_analysis(combined),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


# ============================================================
# Results 14-day calendar range override V1
# ============================================================
# Default Results load = today + previous 13 days in Europe/Bratislava.
# Cards and all bottom stats are computed from this filtered range only.
# Calendar inputs are styled to match the page and show the selected default range.

RESULTS_DEFAULT_RANGE_DAYS = 14
RESULTS_RANGE_TZ = "Europe/Bratislava"

try:
    _RESULTS_RANGE_BASE_FILTER_BUILDER
except NameError:
    _RESULTS_RANGE_BASE_FILTER_BUILDER = render_results_filter_builder


def _results_local_today() -> date:
    return datetime.now(ZoneInfo(RESULTS_RANGE_TZ)).date()


def results_default_date_range() -> Tuple[date, date]:
    end = _results_local_today()
    start = end - timedelta(days=RESULTS_DEFAULT_RANGE_DAYS - 1)
    return start, end


def result_row_local_date(row: Dict[str, Any]) -> Optional[date]:
    dt = result_row_date_value(row)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(RESULTS_RANGE_TZ)).date()


def result_in_date_range(row: Dict[str, Any], start: date, end: date) -> bool:
    d = result_row_local_date(row)
    return d is not None and start <= d <= end


def filter_results_date_range(rows: List[Dict[str, Any]], start: date, end: date) -> List[Dict[str, Any]]:
    return [r for r in rows or [] if result_in_date_range(r, start, end)]


def render_results_calendar_filter(start: date, end: date, total_count: int, loaded_count: int) -> str:
    range_label = f"{start.strftime('%d.%m.%y')} - {end.strftime('%d.%m.%y')}"
    return f"""
<div class="results-range-panel summary-panel">
  <div class="summary-title">Results date range</div>
  <div class="result-filter-help">Default loaded range is today + previous 13 days in Europe/Bratislava. Cards and all stats below are calculated only from this loaded range.</div>
  <div class="result-filter-row results-calendar-row">
    <label class="result-filter-group results-calendar-group">
      <span class="result-filter-group-title">From</span>
      <input class="results-date-input" type="date" value="{esc(start.isoformat())}" aria-label="Results from date" />
    </label>
    <label class="result-filter-group results-calendar-group">
      <span class="result-filter-group-title">To</span>
      <input class="results-date-input" type="date" value="{esc(end.isoformat())}" aria-label="Results to date" />
    </label>
    <span class="tag-chip audit-pill audit-pill-date"><span class="audit-pill-count">{loaded_count}</span> <span class="audit-pill-label">loaded / {total_count} total</span></span>
    <span class="tag-chip audit-pill audit-pill-signal"><span class="audit-pill-label">{esc(range_label)}</span></span>
  </div>
</div>"""


def _results_calendar_css_block() -> str:
    return """
<style>
.results-range-panel{margin-bottom:12px}.results-calendar-row{align-items:center}.results-calendar-group{gap:8px}.results-date-input{appearance:auto;background:#071629;color:#f8fafc;border:1px solid rgba(96,165,250,.45);border-radius:10px;padding:8px 10px;font-weight:900;font-size:13px;outline:none;color-scheme:dark;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.results-date-input:focus{border-color:#fb923c;box-shadow:0 0 0 2px rgba(251,146,60,.22)}
</style>"""


def render_results_filter_builder(rows: List[Dict[str, Any]], total_count: Optional[int] = None) -> str:
    start, end = results_default_date_range()
    total = len(rows or []) if total_count is None else int(total_count)
    calendar = render_results_calendar_filter(start, end, total, len(rows or []))
    return _results_calendar_css_block() + calendar + _RESULTS_RANGE_BASE_FILTER_BUILDER(rows)


def render_results_page(manifest: Dict[str, Any]) -> str:
    corq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    all_combined = corq_all + cloq_all + audit_all

    start, end = results_default_date_range()
    corq = filter_results_date_range(corq_all, start, end)
    cloq = filter_results_date_range(cloq_all, start, end)
    audit_rows = filter_results_date_range(audit_all, start, end)
    combined = corq + cloq + audit_rows

    mark_audit_h2h_top10(combined)
    body = [
        _result_css_block(),
        render_results_filter_builder(combined, total_count=len(all_combined)),
        render_results_card_section(corq, 'CorQ TOP7 Results'),
        render_results_card_section(cloq, 'CloQ Results'),
        render_results_card_section(audit_rows, 'Audit Results', limit=80),
        depth_analysis(combined),
        sets_games_audit(combined),
        tag_analysis(combined),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


# ============================================================
# Results dynamic calendar recompute override V2
# ============================================================
# Client-side date range recalculates visible cards, section summaries and tag
# stats. The DOM keeps all Results rows so changing the calendar does not need a
# new render run. Default selected range remains today + previous 13 days.

RESULTS_DYNAMIC_DEFAULT_DAYS = 14
RESULTS_DYNAMIC_TZ = "Europe/Bratislava"


def _results_dynamic_today() -> date:
    return datetime.now(ZoneInfo(RESULTS_DYNAMIC_TZ)).date()


def results_default_date_range() -> Tuple[date, date]:
    end = _results_dynamic_today()
    start = end - timedelta(days=RESULTS_DYNAMIC_DEFAULT_DAYS - 1)
    return start, end


def result_row_local_date(row: Dict[str, Any]) -> Optional[date]:
    dt = result_row_date_value(row)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(RESULTS_DYNAMIC_TZ)).date()


def result_row_local_date_iso(row: Dict[str, Any]) -> str:
    d = result_row_local_date(row)
    return d.isoformat() if d is not None else ""


def render_results_calendar_filter(start: date, end: date, total_count: int) -> str:
    range_label = f"{start.strftime('%d.%m.%y')} - {end.strftime('%d.%m.%y')}"
    return f"""
<div class="results-range-panel summary-panel" data-results-range-panel>
  <div class="summary-title">Results date range</div>
  <div class="result-filter-help">Default view is today + previous 13 days in Europe/Bratislava. Changing dates recalculates visible cards, section totals and tag stats directly in the browser.</div>
  <div class="result-filter-row results-calendar-row">
    <label class="result-filter-group results-calendar-group">
      <span class="result-filter-group-title">From</span>
      <input id="results-date-from" class="results-date-input" type="date" value="{esc(start.isoformat())}" aria-label="Results from date" />
    </label>
    <label class="result-filter-group results-calendar-group">
      <span class="result-filter-group-title">To</span>
      <input id="results-date-to" class="results-date-input" type="date" value="{esc(end.isoformat())}" aria-label="Results to date" />
    </label>
    <button type="button" class="tag-chip audit-pill audit-pill-date results-range-btn" data-range-days="7">Last 7d</button>
    <button type="button" class="tag-chip audit-pill audit-pill-date results-range-btn" data-range-days="14">Last 14d</button>
    <button type="button" class="tag-chip audit-pill audit-pill-date results-range-btn" data-range-days="30">Last 30d</button>
    <button type="button" class="tag-chip audit-pill audit-pill-note results-range-btn" data-range-all="1">All</button>
    <span class="tag-chip audit-pill audit-pill-signal" data-results-range-count><span class="audit-pill-count">0</span> <span class="audit-pill-label">visible / {total_count} total</span></span>
    <span class="tag-chip audit-pill audit-pill-signal"><span class="audit-pill-label">{esc(range_label)}</span></span>
  </div>
</div>"""


def _results_calendar_css_block() -> str:
    return """
<style>
.results-range-panel{margin-bottom:12px}.results-calendar-row{align-items:center}.results-calendar-group{gap:8px}.results-date-input{appearance:auto;background:#071629;color:#f8fafc;border:1px solid rgba(96,165,250,.45);border-radius:10px;padding:8px 10px;font-weight:900;font-size:13px;outline:none;color-scheme:dark;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.results-date-input:focus{border-color:#fb923c;box-shadow:0 0 0 2px rgba(251,146,60,.22)}.results-range-btn{cursor:pointer}.results-range-btn.active{border-color:#fb923c!important;background:rgba(251,146,60,.24)!important;color:#fff!important}
</style>"""


def render_results_filter_builder(rows: List[Dict[str, Any]], total_count: Optional[int] = None) -> str:
    start, end = results_default_date_range()
    total = len(rows or []) if total_count is None else int(total_count)
    calendar = render_results_calendar_filter(start, end, total)
    return _results_calendar_css_block() + calendar + _RESULTS_RANGE_BASE_FILTER_BUILDER(rows)


def render_result_card(row: Dict[str, Any], rank: int, model_title: str = '') -> str:
    tags = result_tags(row)
    data_tags = '|'.join(tags)
    st = result_status(row)
    units = as_float(row.get('units'), 0.0) or 0.0
    odds = pick_odds(row) or 0.0
    date_iso = result_row_local_date_iso(row)
    model = result_model_filter_tag(row, model_title) or model_title or ''
    return "\n".join([
        f'<div class="result-card tag-analysis-row" data-tags="{esc(data_tags)}" data-result="{esc(st)}" data-model="{esc(model)}" data-section="{esc(model_title)}" data-date="{esc(date_iso)}" data-units="{units:.4f}" data-odds="{odds:.4f}">',
        _result_card_pick_box(row, rank),
        _result_mmx_box(row),
        _result_corq_box(row),
        _result_thinq_box(row),
        _result_sets_games_box(row),
        render_marq_box(row),
        _result_status_box(row),
        '</div>',
    ])


def _result_section_header(rows: List[Dict[str, Any]], title: str) -> str:
    s = summarize_results(rows)
    avg = '—' if s.get('avg_odds') is None else f'{s["avg_odds"]:.2f}'
    return "\n".join([
        f'<div class="result-section-head" data-section-head="{esc(title)}">',
        f'<div class="result-section-title">{esc(title)}</div>',
        '<div class="result-section-stats">',
        f'<span class="result-stat-pill" data-stat="picks">Picks {s["picks"]}</span>',
        f'<span class="result-stat-pill" data-stat="wl">W-L {s["won"]}-{s["lost"]}</span>',
        f'<span class="result-stat-pill" data-stat="pending">Pending {s["pending"]}</span>',
        f'<span class="result-stat-pill" data-stat="win">Win {s["win_pct"]:.1f}%</span>',
        f'<span class="result-stat-pill" data-stat="units">Units {s["units"]:+.2f}u</span>',
        f'<span class="result-stat-pill" data-stat="roi">ROI {s["roi"]:+.1f}%</span>',
        f'<span class="result-stat-pill" data-stat="avg">Avg odds {avg}</span>',
        '</div></div>',
    ])


def render_results_card_section(rows: List[Dict[str, Any]], title: str, limit: Optional[int] = None) -> str:
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    # Keep all rows in DOM. Date range JS handles visibility and recalculates stats.
    if not rows_sorted:
        cards = '<div class="empty">No results available.</div>'
    else:
        cards = '<div class="results-card-grid">' + '\n'.join(render_result_card(r, i + 1, title) for i, r in enumerate(rows_sorted)) + '</div>'
    return f'<section class="result-section" data-result-section="{esc(title)}">{_result_section_header(rows_sorted, title)}{cards}</section>'


def tag_analysis(rows: List[Dict[str, Any]]) -> str:
    tag_rows = _results_tag_stats_rows(rows)
    body = []
    for tag, a in tag_rows:
        decided = int(a["won"] + a["lost"])
        winp = a["won"] / decided * 100 if decided else 0.0
        avg = sum(a["odds"]) / len(a["odds"]) if a["odds"] else None
        avg_txt = "—" if avg is None else f"{avg:.2f}"
        decided_txt = f"{decided}/{a['count']}"
        body.append(
            f'<tr class="result-row tag-analysis-row" data-tags="{esc(tag)}">'
            f'<td><span class="{audit_note_css(tag)}" data-filter="{esc(tag)}">{esc(tag)}</span></td>'
            f'<td>{a["count"]}</td><td>{a["won"]}-{a["lost"]}-{a["void"]}-{a["pending"]}</td>'
            f'<td>{decided_txt}</td><td><b>{winp:.1f}%</b></td><td>{a["units"]:+.2f}u</td><td>{esc(avg_txt)}</td></tr>'
        )
    rows_html = ''.join(body) if body else '<tr><td colspan="7">No tag data yet.</td></tr>'
    return (
        '<div class="results-panel tag-stats-panel" data-tag-stats-panel>'
        f'<div class="summary-title">{RESULTS_TAG_STATS_TITLE}</div>'
        '<div class="result-filter-help">Sorted by decided winrate from best to worst. This table updates when the date range changes.</div>'
        '<div class="table-wrap"><table class="results-table"><thead><tr>'
        '<th>Tag</th><th>Total</th><th>W-L-V-P</th><th>Decided</th><th>Winrate</th><th>Units</th><th>Avg odds</th>'
        '</tr></thead><tbody id="results-tag-stats-body">' + rows_html + '</tbody></table></div>'
        '<span class="clear-filter tag-chip audit-pill audit-pill-clear">Clear filter</span></div>'
    )


def _results_dynamic_script() -> str:
    return """
<script>
(function(){
  const fromInput = document.getElementById('results-date-from');
  const toInput = document.getElementById('results-date-to');
  if(!fromInput || !toInput){ return; }
  const cards = Array.from(document.querySelectorAll('.result-card'));
  const total = cards.length;
  const countPill = document.querySelector('[data-results-range-count] .audit-pill-count');
  const countLabel = document.querySelector('[data-results-range-count] .audit-pill-label');

  function parseDate(v){ return String(v || '').slice(0,10); }
  function inRange(card){
    const d = parseDate(card.dataset.date);
    if(!d){ return false; }
    const from = parseDate(fromInput.value);
    const to = parseDate(toInput.value);
    return (!from || d >= from) && (!to || d <= to);
  }
  function num(v){ const n = Number(v || 0); return Number.isFinite(n) ? n : 0; }
  function fmtPct(v){ return `${v.toFixed(1)}%`; }
  function fmtUnits(v){ return `${v >= 0 ? '+' : ''}${v.toFixed(2)}u`; }

  function computeSummary(list){
    const s = {picks:0, won:0, lost:0, void:0, pending:0, units:0, odds:[]};
    list.forEach(card => {
      s.picks += 1;
      const st = (card.dataset.result || 'PENDING').toUpperCase();
      if(st === 'WON') s.won += 1;
      else if(st === 'LOST') s.lost += 1;
      else if(st === 'VOID') s.void += 1;
      else s.pending += 1;
      s.units += num(card.dataset.units);
      const o = num(card.dataset.odds);
      if(o > 1) s.odds.push(o);
    });
    const decided = s.won + s.lost;
    s.win = decided ? (s.won / decided * 100) : 0;
    s.roi = decided ? (s.units / decided * 100) : 0;
    s.avg = s.odds.length ? (s.odds.reduce((a,b)=>a+b,0) / s.odds.length) : null;
    return s;
  }

  function updateSectionStats(){
    document.querySelectorAll('[data-result-section]').forEach(section => {
      const head = section.querySelector('[data-section-head]');
      if(!head){ return; }
      const visible = Array.from(section.querySelectorAll('.result-card')).filter(c => c.style.display !== 'none');
      const s = computeSummary(visible);
      const set = (key, value) => { const el = head.querySelector(`[data-stat="${key}"]`); if(el) el.textContent = value; };
      set('picks', `Picks ${s.picks}`);
      set('wl', `W-L ${s.won}-${s.lost}`);
      set('pending', `Pending ${s.pending}`);
      set('win', `Win ${fmtPct(s.win)}`);
      set('units', `Units ${fmtUnits(s.units)}`);
      set('roi', `ROI ${s.roi >= 0 ? '+' : ''}${s.roi.toFixed(1)}%`);
      set('avg', `Avg odds ${s.avg === null ? '—' : s.avg.toFixed(2)}`);
    });
  }

  function tagStatsFromVisible(){
    const agg = new Map();
    const visible = cards.filter(c => c.style.display !== 'none');
    visible.forEach(card => {
      const tags = (card.dataset.tags || '').split('|').map(x => x.trim()).filter(Boolean);
      const st = (card.dataset.result || 'PENDING').toUpperCase();
      tags.forEach(tag => {
        if(!agg.has(tag)) agg.set(tag, {tag, count:0, won:0, lost:0, void:0, pending:0, units:0, odds:[]});
        const a = agg.get(tag);
        a.count += 1;
        if(st === 'WON') a.won += 1;
        else if(st === 'LOST') a.lost += 1;
        else if(st === 'VOID') a.void += 1;
        else a.pending += 1;
        a.units += num(card.dataset.units);
        const o = num(card.dataset.odds);
        if(o > 1) a.odds.push(o);
      });
    });
    const rows = Array.from(agg.values()).sort((a,b) => {
      const ad = a.won + a.lost, bd = b.won + b.lost;
      const aw = ad ? a.won / ad : -1, bw = bd ? b.won / bd : -1;
      if(bw !== aw) return bw - aw;
      if(bd !== ad) return bd - ad;
      if(b.units !== a.units) return b.units - a.units;
      return a.tag.localeCompare(b.tag);
    });
    const tbody = document.getElementById('results-tag-stats-body');
    if(!tbody){ return; }
    if(!rows.length){ tbody.innerHTML = '<tr><td colspan="7">No tag data in selected range.</td></tr>'; return; }
    tbody.innerHTML = rows.map(a => {
      const decided = a.won + a.lost;
      const win = decided ? a.won / decided * 100 : 0;
      const avg = a.odds.length ? (a.odds.reduce((x,y)=>x+y,0)/a.odds.length).toFixed(2) : '—';
      const units = `${a.units >= 0 ? '+' : ''}${a.units.toFixed(2)}u`;
      return `<tr class="result-row tag-analysis-row" data-tags="${a.tag.replace(/"/g,'&quot;')}"><td><span class="tag-chip audit-pill" data-filter="${a.tag.replace(/"/g,'&quot;')}">${a.tag}</span></td><td>${a.count}</td><td>${a.won}-${a.lost}-${a.void}-${a.pending}</td><td>${decided}/${a.count}</td><td><b>${win.toFixed(1)}%</b></td><td>${units}</td><td>${avg}</td></tr>`;
    }).join('');
  }

  function applyDateRange(){
    let visible = 0;
    cards.forEach(card => {
      const show = inRange(card);
      card.style.display = show ? '' : 'none';
      if(show) visible += 1;
    });
    if(countPill) countPill.textContent = String(visible);
    if(countLabel) countLabel.textContent = `visible / ${total} total`;
    updateSectionStats();
    tagStatsFromVisible();
  }

  function setLastDays(days){
    const to = new Date();
    const from = new Date();
    from.setDate(to.getDate() - days + 1);
    const iso = d => d.toISOString().slice(0,10);
    fromInput.value = iso(from);
    toInput.value = iso(to);
    document.querySelectorAll('[data-range-days]').forEach(b => b.classList.toggle('active', Number(b.dataset.rangeDays) === days));
    applyDateRange();
  }

  fromInput.addEventListener('change', applyDateRange);
  toInput.addEventListener('change', applyDateRange);
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-range-days],[data-range-all]');
    if(!btn) return;
    if(btn.dataset.rangeAll){
      const dates = cards.map(c => parseDate(c.dataset.date)).filter(Boolean).sort();
      if(dates.length){ fromInput.value = dates[0]; toInput.value = dates[dates.length-1]; }
      document.querySelectorAll('[data-range-days]').forEach(b => b.classList.remove('active'));
      applyDateRange();
      return;
    }
    const days = Number(btn.dataset.rangeDays || 14);
    setLastDays(days);
  });
  document.querySelectorAll('[data-range-days="14"]').forEach(b => b.classList.add('active'));
  applyDateRange();
})();
</script>"""


def render_results_page(manifest: Dict[str, Any]) -> str:
    corq = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_rows = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    combined = corq + cloq + audit_rows
    mark_audit_h2h_top10(combined)
    start, end = results_default_date_range()
    body = [
        _result_css_block(),
        render_results_filter_builder(combined, total_count=len(combined)),
        render_results_card_section(corq, 'CorQ TOP7 Results'),
        render_results_card_section(cloq, 'CloQ Results'),
        render_results_card_section(audit_rows, 'Audit Results'),
        depth_analysis(combined),
        sets_games_audit(combined),
        tag_analysis(combined),
        _results_dynamic_script(),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


# ============================================================
# Results size-safe 14-day render override V3
# ============================================================
# GitHub rejects individual files over 100 MB. Full dynamic Results rendering
# kept all historical cards in the HTML and could exceed that limit. This final
# override renders only the default rolling 14-day window into HTML so the site
# stays publishable. Calendar controls remain visible as the selected range UI;
# wider historical exploration should be added later via paginated/lazy JSON.

RESULTS_SIZE_SAFE_DEFAULT_DAYS = 14
RESULTS_SIZE_SAFE_TZ = "Europe/Bratislava"


def _results_size_safe_today() -> date:
    return datetime.now(ZoneInfo(RESULTS_SIZE_SAFE_TZ)).date()


def results_default_date_range() -> Tuple[date, date]:
    end = _results_size_safe_today()
    start = end - timedelta(days=RESULTS_SIZE_SAFE_DEFAULT_DAYS - 1)
    return start, end


def result_row_local_date(row: Dict[str, Any]) -> Optional[date]:
    dt = result_row_date_value(row)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(RESULTS_SIZE_SAFE_TZ)).date()


def result_row_local_date_iso(row: Dict[str, Any]) -> str:
    d = result_row_local_date(row)
    return d.isoformat() if d is not None else ""


def result_in_date_range(row: Dict[str, Any], start: date, end: date) -> bool:
    d = result_row_local_date(row)
    return d is not None and start <= d <= end


def filter_results_date_range(rows: List[Dict[str, Any]], start: date, end: date) -> List[Dict[str, Any]]:
    return [r for r in rows or [] if result_in_date_range(r, start, end)]


def render_results_calendar_filter(start: date, end: date, total_count: int, loaded_count: int) -> str:
    range_label = f"{start.strftime('%d.%m.%y')} - {end.strftime('%d.%m.%y')}"
    return f"""
<div class="results-range-panel summary-panel" data-results-range-panel>
  <div class="summary-title">Results date range</div>
  <div class="result-filter-help">Rendered range is today + previous 13 days in Europe/Bratislava. This keeps the generated HTML below GitHub's file-size limit. Wider historical analysis should be rendered later through a paginated/lazy Results view.</div>
  <div class="result-filter-row results-calendar-row">
    <label class="result-filter-group results-calendar-group">
      <span class="result-filter-group-title">From</span>
      <input class="results-date-input" type="date" value="{esc(start.isoformat())}" aria-label="Results from date" readonly />
    </label>
    <label class="result-filter-group results-calendar-group">
      <span class="result-filter-group-title">To</span>
      <input class="results-date-input" type="date" value="{esc(end.isoformat())}" aria-label="Results to date" readonly />
    </label>
    <span class="tag-chip audit-pill audit-pill-signal"><span class="audit-pill-count">{loaded_count}</span> <span class="audit-pill-label">loaded / {total_count} total</span></span>
    <span class="tag-chip audit-pill audit-pill-signal"><span class="audit-pill-label">{esc(range_label)}</span></span>
  </div>
</div>"""


def _results_calendar_css_block() -> str:
    return """
<style>
.results-range-panel{margin-bottom:12px}.results-calendar-row{align-items:center}.results-calendar-group{gap:8px}.results-date-input{appearance:auto;background:#071629;color:#f8fafc;border:1px solid rgba(96,165,250,.45);border-radius:10px;padding:8px 10px;font-weight:900;font-size:13px;outline:none;color-scheme:dark;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.results-date-input:focus{border-color:#fb923c;box-shadow:0 0 0 2px rgba(251,146,60,.22)}
</style>"""


def render_results_filter_builder(rows: List[Dict[str, Any]], total_count: Optional[int] = None) -> str:
    start, end = results_default_date_range()
    total = len(rows or []) if total_count is None else int(total_count)
    return _results_calendar_css_block() + render_results_calendar_filter(start, end, total, len(rows or [])) + _RESULTS_RANGE_BASE_FILTER_BUILDER(rows)


def render_result_card(row: Dict[str, Any], rank: int, model_title: str = '') -> str:
    tags = result_tags(row)
    data_tags = '|'.join(tags)
    st = result_status(row)
    units = as_float(row.get('units'), 0.0) or 0.0
    odds = pick_odds(row) or 0.0
    date_iso = result_row_local_date_iso(row)
    model = result_model_filter_tag(row, model_title) or model_title or ''
    return "\n".join([
        f'<div class="result-card tag-analysis-row" data-tags="{esc(data_tags)}" data-result="{esc(st)}" data-model="{esc(model)}" data-section="{esc(model_title)}" data-date="{esc(date_iso)}" data-units="{units:.4f}" data-odds="{odds:.4f}">',
        _result_card_pick_box(row, rank),
        _result_mmx_box(row),
        _result_corq_box(row),
        _result_thinq_box(row),
        _result_sets_games_box(row),
        render_marq_box(row),
        _result_status_box(row),
        '</div>',
    ])


def render_results_card_section(rows: List[Dict[str, Any]], title: str, limit: Optional[int] = None) -> str:
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    if limit is not None:
        rows_sorted = rows_sorted[:limit]
    if not rows_sorted:
        cards = '<div class="empty">No results available in selected range.</div>'
    else:
        cards = '<div class="results-card-grid">' + '\n'.join(render_result_card(r, i + 1, title) for i, r in enumerate(rows_sorted)) + '</div>'
    return f'<section class="result-section" data-result-section="{esc(title)}">{_result_section_header(rows_sorted, title)}{cards}</section>'


def render_results_page(manifest: Dict[str, Any]) -> str:
    corq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    all_combined = corq_all + cloq_all + audit_all

    start, end = results_default_date_range()
    corq = filter_results_date_range(corq_all, start, end)
    cloq = filter_results_date_range(cloq_all, start, end)
    audit_rows = filter_results_date_range(audit_all, start, end)
    combined = corq + cloq + audit_rows

    mark_audit_h2h_top10(combined)
    body = [
        _result_css_block(),
        render_results_filter_builder(combined, total_count=len(all_combined)),
        render_results_card_section(corq, 'CorQ TOP7 Results'),
        render_results_card_section(cloq, 'CloQ Results'),
        render_results_card_section(audit_rows, 'Audit Results', limit=80),
        depth_analysis(combined),
        sets_games_audit(combined),
        tag_analysis(combined),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


# ============================================================
# Results History split override V4
# ============================================================
# Keep Results fast and size-safe: main Results page renders only the rolling
# 14-day window. Older rows are moved into a lightweight History index plus
# one small daily detail file per date. No full-history DOM is rendered.

HISTORY_PATH = "history"

try:
    _nav_items_list = list(NAV_ITEMS)
except Exception:
    _nav_items_list = []
if not any((isinstance(x, (list, tuple)) and len(x) > 1 and str(x[1]).strip('/') == HISTORY_PATH) or (isinstance(x, dict) and str(x.get('path') or '').strip('/') == HISTORY_PATH) for x in _nav_items_list):
    _nav_items_list.append(("History", HISTORY_PATH, "history"))
    NAV_ITEMS = _nav_items_list


def _history_all_result_rows() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    corq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    return corq_all, cloq_all, audit_all


def _history_row_date_iso(row: Dict[str, Any]) -> str:
    d = result_row_local_date(row)
    return d.isoformat() if d is not None else "unknown"


def _history_day_rows(rows: List[Dict[str, Any]], day_iso: str) -> List[Dict[str, Any]]:
    return [r for r in rows or [] if _history_row_date_iso(r) == day_iso]


def _history_rows_before_window(rows: List[Dict[str, Any]], start: date) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        d = result_row_local_date(row)
        if d is not None and d < start:
            out.append(row)
    return out


def _history_day_summary(day_iso: str, rows: List[Dict[str, Any]], corq_rows: List[Dict[str, Any]], cloq_rows: List[Dict[str, Any]], audit_rows: List[Dict[str, Any]]) -> str:
    summary = summarize_results(rows)
    decided = summary.get('won', 0) + summary.get('lost', 0)
    avg = '—' if summary.get('avg_odds') is None else f"{summary['avg_odds']:.2f}"
    try:
        display_day = datetime.fromisoformat(day_iso).strftime('%d.%m.%y')
    except Exception:
        display_day = day_iso
    return "\n".join([
        '<div class="summary-panel history-day-row">',
        f'  <div class="summary-title"><a href="{esc(day_iso)}.html">{esc(display_day)}</a></div>',
        '  <div class="tag-list">',
        f'    <span class="tag-chip">Total {summary["picks"]}</span>',
        f'    <span class="tag-chip">CorQ {len(corq_rows)}</span>',
        f'    <span class="tag-chip">CloQ {len(cloq_rows)}</span>',
        f'    <span class="tag-chip">Audit {len(audit_rows)}</span>',
        f'    <span class="tag-chip">W-L {summary["won"]}-{summary["lost"]}</span>',
        f'    <span class="tag-chip">Pending {summary["pending"]}</span>',
        f'    <span class="tag-chip">Decided {decided}/{summary["picks"]}</span>',
        f'    <span class="tag-chip">Win {summary["win_pct"]:.1f}%</span>',
        f'    <span class="tag-chip">Units {summary["units"]:+.2f}u</span>',
        f'    <span class="tag-chip">ROI {summary["roi"]:+.1f}%</span>',
        f'    <span class="tag-chip">Avg odds {esc(avg)}</span>',
        '  </div>',
        '</div>',
    ])


def render_results_history_index(manifest: Dict[str, Any]) -> str:
    corq_all, cloq_all, audit_all = _history_all_result_rows()
    all_rows = corq_all + cloq_all + audit_all
    start, end = results_default_date_range()
    history_rows = _history_rows_before_window(all_rows, start)
    days = sorted({_history_row_date_iso(r) for r in history_rows if _history_row_date_iso(r) != 'unknown'}, reverse=True)
    body: List[str] = [
        _result_css_block(),
        '<div class="summary-panel">',
        '<div class="summary-title">History</div>',
        f'<div class="hero-line">Archive contains rows older than the active Results window ({esc(start.isoformat())} to {esc(end.isoformat())}). Main Results stays limited to the latest 14 days for speed and Pages deploy safety.</div>',
        '</div>',
    ]
    if not days:
        body.append('<div class="empty">No historical result days older than the current 14-day window.</div>')
    else:
        for day in days:
            c = _history_day_rows(corq_all, day)
            cl = _history_day_rows(cloq_all, day)
            a = _history_day_rows(audit_all, day)
            body.append(_history_day_summary(day, c + cl + a, c, cl, a))
    return page_shell('History', HISTORY_PATH, '\n'.join(body), manifest)


def render_results_history_day(manifest: Dict[str, Any], day_iso: str) -> str:
    corq_all, cloq_all, audit_all = _history_all_result_rows()
    corq = _history_day_rows(corq_all, day_iso)
    cloq = _history_day_rows(cloq_all, day_iso)
    audit_rows = _history_day_rows(audit_all, day_iso)
    combined = corq + cloq + audit_rows
    mark_audit_h2h_top10(combined)
    try:
        display_day = datetime.fromisoformat(day_iso).strftime('%d.%m.%y')
    except Exception:
        display_day = day_iso
    body = [
        _result_css_block(),
        '<div class="summary-panel">',
        f'<div class="summary-title">History | {esc(display_day)}</div>',
        '<div class="tag-list"><a class="tag-chip" href="index.html">Back to History</a><a class="tag-chip" href="../' + esc(RESULTS_PATH) + '/">Latest 14 days</a></div>',
        '</div>',
        render_results_card_section(corq, 'CorQ TOP7 Results'),
        render_results_card_section(cloq, 'CloQ Results'),
        render_results_card_section(audit_rows, 'Audit Results', limit=120),
        depth_analysis(combined),
        sets_games_audit(combined),
        tag_analysis(combined),
    ]
    return page_shell(f'History {display_day}', HISTORY_PATH, '\n'.join(body), manifest)


_ORIGINAL_RENDER_ALL_FOR_HISTORY = render_all

def render_all() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_json(OUTPUTS / "latest_manifest.json", {})
    top7 = json_rows(read_json(OUTPUTS / "latest_top7.json", []))
    all_rows = json_rows(read_json(OUTPUTS / "latest_all.json", []))
    cloq = json_rows(read_json(OUTPUTS / "cloq" / "latest_cloq.json", []))
    if not cloq:
        cloq = json_rows(read_json(OUTPUTS / "latest_cloq.json", []))
    mark_audit_cloq_rows(all_rows, cloq)
    all_rows_for_audit = sort_rows_by_match_time(all_rows)
    ensure_logs(top7 + all_rows_for_audit + cloq)

    write_text(SITE_DIR / "index.html", page_shell("CorQ", "root", '<script>location.href="' + esc(TOP7_PATH) + '/"</script>', manifest))
    write_text(SITE_DIR / TOP7_PATH / "index.html", render_cards_page("CorQ", TOP7_PATH, top7, manifest, page="corq"))
    write_text(SITE_DIR / ALL_PATH / "index.html", render_cards_page("Audit", ALL_PATH, all_rows_for_audit, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / CLOQ_PATH / "index.html", render_cards_page("CloQ", CLOQ_PATH, cloq, manifest, page="cloq"))
    write_text(SITE_DIR / THINQ_PATH / "index.html", render_cards_page("ThinQ", THINQ_PATH, all_rows_for_audit, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / RESULTS_PATH / "index.html", render_results_page(manifest))
    write_text(SITE_DIR / HISTORY_PATH / "index.html", render_results_history_index(manifest))

    corq_all, cloq_all, audit_all = _history_all_result_rows()
    start, _end = results_default_date_range()
    history_rows = _history_rows_before_window(corq_all + cloq_all + audit_all, start)
    for day in sorted({_history_row_date_iso(r) for r in history_rows if _history_row_date_iso(r) != 'unknown'}, reverse=True):
        write_text(SITE_DIR / HISTORY_PATH / f"{day}.html", render_results_history_day(manifest, day))

    write_text(SITE_DIR / CORQ_RSS_PATH, rss_items(top7, "CorQ TOP7"))
    write_text(SITE_DIR / CLOQ_RSS_PATH, rss_items(cloq, "CloQ"))
    write_text(SITE_DIR / THINQ_RSS_PATH, rss_items(all_rows_for_audit[:20], "ThinQ"))
    render_manifest = {
        "rendered_at": datetime.now(tz=timezone.utc).isoformat(),
        "top7_count": len(top7),
        "all_count": len(all_rows_for_audit),
        "cloq_count": len(cloq),
        "history_path": HISTORY_PATH,
        "site_root": str(SITE_DIR),
    }
    write_text(SITE_DIR / "render_manifest.json", json.dumps(render_manifest, ensure_ascii=False, indent=2))
    print(f"Rendered site: top7={len(top7)} all={len(all_rows_for_audit)} cloq={len(cloq)} history={HISTORY_PATH} root={SITE_DIR}")

# ============================================================
# CorQ TOP7 visual rank-order override V1
# ============================================================
# CorQ/CloQ cards must preserve model rank order. Audit may still sort by start time.



# ============================================================
# Results lazy-load card chunks override V5
# ============================================================
# Main Results and History day pages now write card HTML into small chunk files
# under corq/site/assets/results_lazy/. The page shell stays lightweight and
# loads chunks on demand. This prevents one very large Results index.html file
# while preserving the existing Python card renderer and visual design.

RESULTS_LAZY_CHUNK_SIZE = int(os.getenv("RESULTS_LAZY_CHUNK_SIZE", "20") or "20")
RESULTS_LAZY_ASSET_DIRNAME = "results_lazy"
RESULTS_LAZY_ASSET_DIR = ASSET_DIR / RESULTS_LAZY_ASSET_DIRNAME


def _lazy_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "section")).strip("_").lower()
    return slug or "section"


def _lazy_section_meta(rows: List[Dict[str, Any]], title: str) -> str:
    return _result_section_header(rows, title)


def _write_results_lazy_chunks(rows: List[Dict[str, Any]], title: str, scope: str, limit: Optional[int] = None) -> List[str]:
    RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    if limit is not None:
        rows_sorted = rows_sorted[:limit]
    section_slug = _lazy_slug(f"{scope}_{title}")
    files: List[str] = []
    if not rows_sorted:
        fname = f"{section_slug}_001.html"
        write_text(RESULTS_LAZY_ASSET_DIR / fname, '<div class="empty">No results available in selected range.</div>')
        return [f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}"]
    chunk_size = max(1, int(RESULTS_LAZY_CHUNK_SIZE or 20))
    for chunk_idx in range(0, len(rows_sorted), chunk_size):
        chunk = rows_sorted[chunk_idx:chunk_idx + chunk_size]
        cards = '<div class="results-card-grid">' + '\n'.join(
            render_result_card(row, chunk_idx + local_idx + 1, title)
            for local_idx, row in enumerate(chunk)
        ) + '</div>'
        fname = f"{section_slug}_{(chunk_idx // chunk_size) + 1:03d}.html"
        write_text(RESULTS_LAZY_ASSET_DIR / fname, cards)
        files.append(f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}")
    return files


def _render_results_lazy_section(rows: List[Dict[str, Any]], title: str, scope: str, limit: Optional[int] = None) -> str:
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    if limit is not None:
        rows_sorted = rows_sorted[:limit]
    chunk_urls = _write_results_lazy_chunks(rows, title, scope, limit=limit)
    payload = html.escape(json.dumps(chunk_urls, ensure_ascii=False), quote=True)
    section_id = _lazy_slug(f"lazy_{scope}_{title}")
    count = len(rows_sorted)
    return "\n".join([
        f'<section class="result-section results-lazy-section" data-result-section="{esc(title)}" data-results-lazy-section="1">',
        _lazy_section_meta(rows_sorted, title),
        f'<div id="{esc(section_id)}" class="results-lazy-root" data-chunks="{payload}" data-loaded="0" data-total="{len(chunk_urls)}">',
        f'  <div class="empty results-lazy-placeholder">Loading {esc(title)} cards...</div>',
        '</div>',
        f'<div class="tag-list results-lazy-controls"><button class="tag-chip results-lazy-load-more" type="button" data-target="{esc(section_id)}">Load more {esc(title)} cards</button><span class="tag-chip">{count} rows | chunks {len(chunk_urls)}</span></div>',
        '</section>',
    ])


def _results_lazy_css_block() -> str:
    return """
<style>
.results-lazy-root{min-height:80px}.results-lazy-placeholder{border:1px dashed rgba(148,163,184,.35);border-radius:14px;padding:16px;color:#94a3b8;background:rgba(15,23,42,.45)}.results-lazy-controls{margin-top:10px}.results-lazy-load-more{cursor:pointer}.results-lazy-load-more[disabled]{opacity:.45;cursor:not-allowed}
</style>"""


def _results_lazy_script_block() -> str:
    return """
<script>
(function(){
  async function loadNext(root, allRemaining){
    if(!root) return;
    let chunks=[];
    try{ chunks=JSON.parse(root.getAttribute('data-chunks')||'[]'); }catch(e){ chunks=[]; }
    let loaded=parseInt(root.getAttribute('data-loaded')||'0',10)||0;
    const total=chunks.length;
    const placeholder=root.querySelector('.results-lazy-placeholder');
    if(placeholder) placeholder.remove();
    const limit=allRemaining ? total : Math.min(total, loaded+1);
    while(loaded<limit){
      const url=chunks[loaded];
      try{
        const res=await fetch(url,{cache:'no-cache'});
        const html=await res.text();
        root.insertAdjacentHTML('beforeend', html);
      }catch(e){
        root.insertAdjacentHTML('beforeend','<div class="empty">Failed to load result chunk.</div>');
        break;
      }
      loaded++;
      root.setAttribute('data-loaded', String(loaded));
    }
    document.querySelectorAll('[data-target="'+root.id+'"]').forEach(function(btn){
      if(loaded>=total){ btn.disabled=true; btn.textContent='All cards loaded'; }
    });
  }
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('.results-lazy-root').forEach(function(root){ loadNext(root,false); });
    document.querySelectorAll('.results-lazy-load-more').forEach(function(btn){
      btn.addEventListener('click', function(){ loadNext(document.getElementById(btn.getAttribute('data-target')), true); });
    });
  });
})();
</script>"""


def render_results_card_section(rows: List[Dict[str, Any]], title: str, limit: Optional[int] = None) -> str:
    return _render_results_lazy_section(rows, title, "results_default", limit=limit)


def render_results_page(manifest: Dict[str, Any]) -> str:
    corq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    all_combined = corq_all + cloq_all + audit_all

    start, end = results_default_date_range()
    corq = filter_results_date_range(corq_all, start, end)
    cloq = filter_results_date_range(cloq_all, start, end)
    audit_rows = filter_results_date_range(audit_all, start, end)
    combined = corq + cloq + audit_rows

    mark_audit_h2h_top10(combined)
    body = [
        _result_css_block(),
        _results_lazy_css_block(),
        render_results_filter_builder(combined, total_count=len(all_combined)),
        _render_results_lazy_section(corq, 'CorQ TOP7 Results', 'results_latest'),
        _render_results_lazy_section(cloq, 'CloQ Results', 'results_latest'),
        _render_results_lazy_section(audit_rows, 'Audit Results', 'results_latest', limit=80),
        depth_analysis(combined),
        sets_games_audit(combined),
        tag_analysis(combined),
        _results_lazy_script_block(),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


def render_results_history_day(manifest: Dict[str, Any], day_iso: str) -> str:
    corq_all, cloq_all, audit_all = _history_all_result_rows()
    corq = _history_day_rows(corq_all, day_iso)
    cloq = _history_day_rows(cloq_all, day_iso)
    audit_rows = _history_day_rows(audit_all, day_iso)
    combined = corq + cloq + audit_rows
    mark_audit_h2h_top10(combined)
    try:
        display_day = datetime.fromisoformat(day_iso).strftime('%d.%m.%y')
    except Exception:
        display_day = day_iso
    scope = f"history_{day_iso}"
    body = [
        _result_css_block(),
        _results_lazy_css_block(),
        '<div class="summary-panel">',
        f'<div class="summary-title">History | {esc(display_day)}</div>',
        '<div class="tag-list"><a class="tag-chip" href="index.html">Back to History</a><a class="tag-chip" href="../' + esc(RESULTS_PATH) + '/">Latest 14 days</a></div>',
        '</div>',
        _render_results_lazy_section(corq, 'CorQ TOP7 Results', scope),
        _render_results_lazy_section(cloq, 'CloQ Results', scope),
        _render_results_lazy_section(audit_rows, 'Audit Results', scope, limit=120),
        depth_analysis(combined),
        sets_games_audit(combined),
        tag_analysis(combined),
        _results_lazy_script_block(),
    ]
    return page_shell(f'History {display_day}', HISTORY_PATH, '\n'.join(body), manifest)


# ============================================================
# Results range lazy-load override V6
# ============================================================
# Default Results view renders the latest 3 days, but keeps full analytic
# cards available through reusable day chunks for L24h, week, 2 weeks,
# month, 3 months and year ranges. Cards are not simplified.

RESULTS_RANGE_TZ = "Europe/Bratislava"
RESULTS_RANGE_PRESETS = [
    {"key": "l24h", "label": "L24h", "days": None, "hours": 24},
    {"key": "d3", "label": "Last 3 days", "days": 3, "hours": None},
    {"key": "week", "label": "Last week", "days": 7, "hours": None},
    {"key": "week2", "label": "Last 2 weeks", "days": 14, "hours": None},
    {"key": "month", "label": "Last month", "days": 31, "hours": None},
    {"key": "m3", "label": "Last 3 months", "days": 92, "hours": None},
    {"key": "year", "label": "Last year", "days": 365, "hours": None},
]
RESULTS_DEFAULT_RANGE_KEY = "d3"
RESULTS_DAY_CHUNK_SIZE = int(os.getenv("RESULTS_DAY_CHUNK_SIZE", "20") or "20")
RESULTS_RANGE_INITIAL_CHUNKS = int(os.getenv("RESULTS_RANGE_INITIAL_CHUNKS", "2") or "2")
RESULTS_RANGE_BATCH_CHUNKS = int(os.getenv("RESULTS_RANGE_BATCH_CHUNKS", "3") or "3")


def _results_range_tz() -> ZoneInfo:
    return ZoneInfo(RESULTS_RANGE_TZ)


def _results_now_local() -> datetime:
    return datetime.now(_results_range_tz())


def _results_row_local_dt(row: Dict[str, Any]) -> Optional[datetime]:
    dt = result_row_date_value(row)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_results_range_tz())


def result_row_local_date(row: Dict[str, Any]) -> Optional[Any]:
    dt = _results_row_local_dt(row)
    return dt.date() if dt is not None else None


def result_row_local_date_iso(row: Dict[str, Any]) -> str:
    d = result_row_local_date(row)
    return d.isoformat() if d is not None else ""


def _results_preset_by_key(key: str) -> Dict[str, Any]:
    for preset in RESULTS_RANGE_PRESETS:
        if preset["key"] == key:
            return preset
    return RESULTS_RANGE_PRESETS[1]


def _results_range_bounds(key: str) -> Tuple[datetime, datetime]:
    now = _results_now_local()
    preset = _results_preset_by_key(key)
    if preset.get("hours"):
        return now - timedelta(hours=int(preset["hours"])), now
    days = int(preset.get("days") or 3)
    start_date = now.date() - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=_results_range_tz())
    end_dt = datetime.combine(now.date(), datetime.max.time(), tzinfo=_results_range_tz())
    return start_dt, end_dt


def results_default_date_range() -> Tuple[Any, Any]:
    start_dt, end_dt = _results_range_bounds(RESULTS_DEFAULT_RANGE_KEY)
    return start_dt.date(), end_dt.date()


def _results_row_in_range(row: Dict[str, Any], key: str) -> bool:
    dt = _results_row_local_dt(row)
    if dt is None:
        return False
    start_dt, end_dt = _results_range_bounds(key)
    return start_dt <= dt <= end_dt


def filter_results_date_range(rows: List[Dict[str, Any]], start: Any, end: Any) -> List[Dict[str, Any]]:
    return [r for r in rows or [] if result_row_local_date(r) is not None and start <= result_row_local_date(r) <= end]


def _results_rows_for_preset(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    return [r for r in rows or [] if _results_row_in_range(r, key)]


def _results_days_for_rows(rows: List[Dict[str, Any]]) -> List[str]:
    days = {result_row_local_date_iso(r) for r in rows or [] if result_row_local_date_iso(r)}
    return sorted(days, reverse=True)


def _results_day_rows(rows: List[Dict[str, Any]], day_iso: str) -> List[Dict[str, Any]]:
    return [r for r in rows or [] if result_row_local_date_iso(r) == day_iso]


def _results_section_key(title: str) -> str:
    text = str(title or "section").lower()
    if "cloq" in text:
        return "cloq"
    if "audit" in text:
        return "audit"
    return "corq"


def _result_day_chunk_filename(section: str, day_iso: str, chunk_number: int) -> str:
    safe_day = re.sub(r"[^0-9-]+", "_", str(day_iso or "unknown"))
    return f"results_{section}_{safe_day}_{chunk_number:03d}.html"


def _write_result_day_chunks(rows: List[Dict[str, Any]], title: str, day_iso: str) -> List[str]:
    RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    section = _results_section_key(title)
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    chunk_size = max(1, int(RESULTS_DAY_CHUNK_SIZE or 20))
    urls: List[str] = []
    if not rows_sorted:
        fname = _result_day_chunk_filename(section, day_iso, 1)
        write_text(RESULTS_LAZY_ASSET_DIR / fname, '<div class="empty">No results available in selected range.</div>')
        return [f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}"]
    for chunk_idx in range(0, len(rows_sorted), chunk_size):
        chunk = rows_sorted[chunk_idx:chunk_idx + chunk_size]
        cards = '<div class="grid results-card-grid">' + '\n'.join(
            render_result_card(row, chunk_idx + local_idx + 1, title)
            for local_idx, row in enumerate(chunk)
        ) + '</div>'
        fname = _result_day_chunk_filename(section, day_iso, (chunk_idx // chunk_size) + 1)
        write_text(RESULTS_LAZY_ASSET_DIR / fname, cards)
        urls.append(f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}")
    return urls


def _range_chunk_urls(rows: List[Dict[str, Any]], title: str, range_key: str) -> List[str]:
    urls: List[str] = []
    range_rows = _results_rows_for_preset(rows, range_key)
    for day_iso in _results_days_for_rows(range_rows):
        urls.extend(_write_result_day_chunks(_results_day_rows(range_rows, day_iso), title, day_iso))
    if not urls:
        RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
        section = _results_section_key(title)
        fname = f"results_{section}_{range_key}_empty.html"
        write_text(RESULTS_LAZY_ASSET_DIR / fname, '<div class="empty">No results available in selected range.</div>')
        urls.append(f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}")
    return urls


def _results_range_payload(corq_all: List[Dict[str, Any]], cloq_all: List[Dict[str, Any]], audit_all: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"default": RESULTS_DEFAULT_RANGE_KEY, "ranges": {}}
    for preset in RESULTS_RANGE_PRESETS:
        key = preset["key"]
        corq = _results_rows_for_preset(corq_all, key)
        cloq = _results_rows_for_preset(cloq_all, key)
        audit_rows = _results_rows_for_preset(audit_all, key)
        combined = corq + cloq + audit_rows
        mark_audit_h2h_top10(combined)
        start_dt, end_dt = _results_range_bounds(key)
        payload["ranges"][key] = {
            "label": preset["label"],
            "rangeLabel": f"{start_dt.strftime('%d.%m.%y %H:%M')} - {end_dt.strftime('%d.%m.%y %H:%M')}",
            "loadedLabel": f"{len(combined)} rows in {preset['label']} | total archive {len(corq_all) + len(cloq_all) + len(audit_all)} rows",
            "sections": {
                "corq": {"title": "CorQ TOP7 Results", "meta": _result_section_header(corq, "CorQ TOP7 Results"), "chunks": _range_chunk_urls(corq_all, "CorQ TOP7 Results", key)},
                "cloq": {"title": "CloQ Results", "meta": _result_section_header(cloq, "CloQ Results"), "chunks": _range_chunk_urls(cloq_all, "CloQ Results", key)},
                "audit": {"title": "Audit Results", "meta": _result_section_header(audit_rows, "Audit Results"), "chunks": _range_chunk_urls(audit_all, "Audit Results", key)},
            },
            "stats": {
                "depth": depth_analysis(combined),
                "sets": sets_games_audit(combined),
                "tags": tag_analysis(combined),
            },
        }
    return payload


def _results_range_filter_panel(payload: Dict[str, Any]) -> str:
    active = str(payload.get("default") or RESULTS_DEFAULT_RANGE_KEY)
    buttons = []
    for preset in RESULTS_RANGE_PRESETS:
        key = preset["key"]
        cls = "tag-chip audit-pill audit-pill-date results-range-btn"
        if key == active:
            cls += " active"
        buttons.append(f'<button type="button" class="{cls}" data-range-key="{esc(key)}">{esc(preset["label"])}</button>')
    active_payload = payload.get("ranges", {}).get(active, {})
    return "\n".join([
        '<div class="summary-panel result-filter-builder results-range-panel">',
        '<div class="summary-title">Results range</div>',
        '<div class="result-filter-help">Default: Last 3 days. Wider ranges load full analytic cards progressively.</div>',
        '<div class="tag-list results-range-buttons">' + ''.join(buttons) + '</div>',
        f'<div id="results-range-label" class="result-filter-help">{esc(active_payload.get("rangeLabel", ""))}</div>',
        f'<div id="results-range-loaded" class="result-filter-help">{esc(active_payload.get("loadedLabel", ""))}</div>',
        '</div>',
    ])


def _results_range_css_block() -> str:
    return """
<style>
.results-range-buttons{gap:8px}.results-range-btn{cursor:pointer}.results-range-btn.active{border-color:var(--orange)!important;background:rgba(251,146,60,.24)!important;color:#fff!important;box-shadow:0 0 0 1px rgba(251,146,60,.25),0 0 18px rgba(251,146,60,.18)!important}.results-range-section-meta{margin-bottom:10px}.results-lazy-load-more{cursor:pointer}.results-lazy-load-more[disabled]{opacity:.45;cursor:not-allowed}.results-range-stats{margin-top:14px}.results-lazy-placeholder{border:1px dashed rgba(148,163,184,.35);border-radius:14px;padding:16px;color:#94a3b8;background:rgba(15,23,42,.45)}
</style>"""


def _results_range_section(section_key: str, title: str, payload: Dict[str, Any]) -> str:
    active = str(payload.get("default") or RESULTS_DEFAULT_RANGE_KEY)
    section = payload.get("ranges", {}).get(active, {}).get("sections", {}).get(section_key, {})
    chunks = section.get("chunks", [])
    root_id = f"results-range-root-{section_key}"
    chunk_payload = html.escape(json.dumps(chunks, ensure_ascii=False), quote=True)
    return "\n".join([
        f'<section class="results-lazy-section" data-section="{esc(section_key)}">',
        f'<div class="results-range-section-meta" data-section-meta="{esc(section_key)}">{section.get("meta", _result_section_header([], title))}</div>',
        f'<div id="{esc(root_id)}" class="results-lazy-root" data-section="{esc(section_key)}" data-chunks="{chunk_payload}" data-loaded="0">',
        f'  <div class="results-lazy-placeholder">Loading {esc(title)} cards...</div>',
        '</div>',
        f'<div class="tag-list results-lazy-controls"><button class="tag-chip results-lazy-load-more" type="button" data-target="{esc(root_id)}">Load more {esc(title)} cards</button><span class="tag-chip results-lazy-counter" data-counter-for="{esc(root_id)}">0 / {len(chunks)} chunks</span></div>',
        '</section>',
    ])


def _results_range_script_block(payload: Dict[str, Any]) -> str:
    payload_text = json.dumps(payload, ensure_ascii=False).replace('</', r'<\/')
    return f"""
<script type="application/json" id="results-range-payload">{payload_text}</script>
<script>
(function(){{
  const initialChunks = {max(1, int(RESULTS_RANGE_INITIAL_CHUNKS or 2))};
  const batchChunks = {max(1, int(RESULTS_RANGE_BATCH_CHUNKS or 3))};
  function getPayload(){{
    const node=document.getElementById('results-range-payload');
    if(!node) return {{default:'d3', ranges:{{}}}};
    try{{ return JSON.parse(node.textContent||'{{}}'); }}catch(e){{ return {{default:'d3', ranges:{{}}}}; }}
  }}
  function setChunks(root, chunks){{
    root.setAttribute('data-chunks', JSON.stringify(chunks||[]));
    root.setAttribute('data-loaded','0');
    root.innerHTML='<div class="results-lazy-placeholder">Loading result cards...</div>';
    document.querySelectorAll('[data-counter-for="'+root.id+'"]').forEach(function(c){{ c.textContent='0 / '+(chunks||[]).length+' chunks'; }});
    document.querySelectorAll('[data-target="'+root.id+'"]').forEach(function(btn){{ btn.disabled=false; btn.textContent='Load more cards'; }});
  }}
  async function loadNext(root, count){{
    if(!root) return;
    let chunks=[];
    try{{ chunks=JSON.parse(root.getAttribute('data-chunks')||'[]'); }}catch(e){{ chunks=[]; }}
    let loaded=parseInt(root.getAttribute('data-loaded')||'0',10)||0;
    const total=chunks.length;
    const placeholder=root.querySelector('.results-lazy-placeholder');
    if(placeholder) placeholder.remove();
    const target=Math.min(total, loaded + Math.max(1, count||1));
    while(loaded<target){{
      const url=chunks[loaded];
      try{{
        const res=await fetch(url,{{cache:'no-cache'}});
        const html=await res.text();
        root.insertAdjacentHTML('beforeend', html);
      }}catch(e){{
        root.insertAdjacentHTML('beforeend','<div class="empty">Failed to load result chunk.</div>');
        break;
      }}
      loaded++;
      root.setAttribute('data-loaded', String(loaded));
    }}
    document.querySelectorAll('[data-counter-for="'+root.id+'"]').forEach(function(c){{ c.textContent=loaded+' / '+total+' chunks'; }});
    document.querySelectorAll('[data-target="'+root.id+'"]').forEach(function(btn){{ if(loaded>=total){{ btn.disabled=true; btn.textContent='All cards loaded'; }} }});
  }}
  function applyRange(key){{
    const payload=getPayload();
    const range=(payload.ranges||{{}})[key] || (payload.ranges||{{}})[payload.default];
    if(!range) return;
    document.querySelectorAll('.results-range-btn').forEach(function(btn){{ btn.classList.toggle('active', btn.getAttribute('data-range-key')===key); }});
    const label=document.getElementById('results-range-label'); if(label) label.textContent=range.rangeLabel||'';
    const loaded=document.getElementById('results-range-loaded'); if(loaded) loaded.textContent=range.loadedLabel||'';
    ['corq','cloq','audit'].forEach(function(sectionKey){{
      const section=(range.sections||{{}})[sectionKey]||{{meta:'',chunks:[]}};
      document.querySelectorAll('[data-section-meta="'+sectionKey+'"]').forEach(function(meta){{ meta.innerHTML=section.meta||''; }});
      document.querySelectorAll('.results-lazy-root[data-section="'+sectionKey+'"]').forEach(function(root){{ setChunks(root, section.chunks||[]); loadNext(root, initialChunks); }});
    }});
    const stats=range.stats||{{}};
    const depth=document.getElementById('results-range-depth'); if(depth) depth.innerHTML=stats.depth||'';
    const sets=document.getElementById('results-range-sets'); if(sets) sets.innerHTML=stats.sets||'';
    const tags=document.getElementById('results-range-tags'); if(tags) tags.innerHTML=stats.tags||'';
  }}
  document.addEventListener('DOMContentLoaded', function(){{
    const payload=getPayload();
    document.querySelectorAll('.results-range-btn').forEach(function(btn){{ btn.addEventListener('click', function(){{ applyRange(btn.getAttribute('data-range-key')||payload.default||'d3'); }}); }});
    document.querySelectorAll('.results-lazy-load-more').forEach(function(btn){{ btn.addEventListener('click', function(){{ loadNext(document.getElementById(btn.getAttribute('data-target')), batchChunks); }}); }});
    applyRange(payload.default||'d3');
  }});
}})();
</script>"""


def render_results_filter_builder(rows: List[Dict[str, Any]], total_count: Optional[int] = None) -> str:
    # The final Results page builds date ranges through _results_range_filter_panel().
    # Keep the original multi-filter builder for model/tag/status filters only.
    try:
        return _RESULTS_RANGE_BASE_FILTER_BUILDER(rows)
    except Exception:
        return ""


def render_results_page(manifest: Dict[str, Any]) -> str:
    # Clean stale lazy assets before writing current day chunks.
    if RESULTS_LAZY_ASSET_DIR.exists():
        shutil.rmtree(RESULTS_LAZY_ASSET_DIR, ignore_errors=True)
    RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)

    corq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    all_combined = corq_all + cloq_all + audit_all
    mark_audit_h2h_top10(all_combined)
    payload = _results_range_payload(corq_all, cloq_all, audit_all)
    active = payload.get('default', RESULTS_DEFAULT_RANGE_KEY)
    active_stats = payload.get('ranges', {}).get(active, {}).get('stats', {})
    active_rows = _results_rows_for_preset(all_combined, str(active))
    body = [
        _result_css_block(),
        _results_lazy_css_block(),
        _results_range_css_block(),
        _results_range_filter_panel(payload),
        render_results_filter_builder(active_rows, total_count=len(all_combined)),
        _results_range_section('corq', 'CorQ TOP7 Results', payload),
        _results_range_section('cloq', 'CloQ Results', payload),
        _results_range_section('audit', 'Audit Results', payload),
        f'<div id="results-range-depth" class="results-range-stats">{active_stats.get("depth", "")}</div>',
        f'<div id="results-range-sets" class="results-range-stats">{active_stats.get("sets", "")}</div>',
        f'<div id="results-range-tags" class="results-range-stats">{active_stats.get("tags", "")}</div>',
        _results_range_script_block(payload),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


def render_results_history_day(manifest: Dict[str, Any], day_iso: str) -> str:
    corq_all, cloq_all, audit_all = _history_all_result_rows()
    corq = _history_day_rows(corq_all, day_iso)
    cloq = _history_day_rows(cloq_all, day_iso)
    audit_rows = _history_day_rows(audit_all, day_iso)
    combined = corq + cloq + audit_rows
    mark_audit_h2h_top10(combined)
    try:
        display_day = datetime.fromisoformat(day_iso).strftime('%d.%m.%y')
    except Exception:
        display_day = day_iso
    # Reuse the same day chunk file names as the main Results page when possible.
    payload = {
        'default': 'day',
        'ranges': {
            'day': {
                'label': display_day,
                'rangeLabel': display_day,
                'loadedLabel': f'{len(combined)} rows for {display_day}',
                'sections': {
                    'corq': {'title': 'CorQ TOP7 Results', 'meta': _result_section_header(corq, 'CorQ TOP7 Results'), 'chunks': _write_result_day_chunks(corq, 'CorQ TOP7 Results', day_iso)},
                    'cloq': {'title': 'CloQ Results', 'meta': _result_section_header(cloq, 'CloQ Results'), 'chunks': _write_result_day_chunks(cloq, 'CloQ Results', day_iso)},
                    'audit': {'title': 'Audit Results', 'meta': _result_section_header(audit_rows, 'Audit Results'), 'chunks': _write_result_day_chunks(audit_rows, 'Audit Results', day_iso)},
                },
                'stats': {'depth': depth_analysis(combined), 'sets': sets_games_audit(combined), 'tags': tag_analysis(combined)},
            }
        }
    }
    active_stats = payload['ranges']['day']['stats']
    body = [
        _result_css_block(),
        _results_lazy_css_block(),
        _results_range_css_block(),
        '<div class="summary-panel">',
        f'<div class="summary-title">History | {esc(display_day)}</div>',
        '<div class="tag-list"><a class="tag-chip" href="index.html">Back to History</a><a class="tag-chip" href="../' + esc(RESULTS_PATH) + '/">Latest Results</a></div>',
        '</div>',
        _results_range_section('corq', 'CorQ TOP7 Results', payload),
        _results_range_section('cloq', 'CloQ Results', payload),
        _results_range_section('audit', 'Audit Results', payload),
        f'<div id="results-range-depth" class="results-range-stats">{active_stats.get("depth", "")}</div>',
        f'<div id="results-range-sets" class="results-range-stats">{active_stats.get("sets", "")}</div>',
        f'<div id="results-range-tags" class="results-range-stats">{active_stats.get("tags", "")}</div>',
        _results_range_script_block(payload),
    ]
    return page_shell(f'History {display_day}', HISTORY_PATH, '\n'.join(body), manifest)



# ============================================================
# Results stats + lazy-load final override V7
# ============================================================
# Goals:
# - default Results range is Last 3 days
# - full analytic result cards are preserved
# - each lazy chunk is small, so Results chunks do not become multi-MB blobs
# - stats are computed from exactly the active date range/preset
# - top and bottom range controls are rendered
# - old results_lazy files are cleaned before render

RESULTS_DEFAULT_RANGE_KEY = "d3"
RESULTS_DAY_CHUNK_SIZE = int(os.getenv("RESULTS_DAY_CHUNK_SIZE", "6") or "6")
RESULTS_RANGE_INITIAL_CHUNKS = int(os.getenv("RESULTS_RANGE_INITIAL_CHUNKS", "2") or "2")
RESULTS_RANGE_BATCH_CHUNKS = int(os.getenv("RESULTS_RANGE_BATCH_CHUNKS", "3") or "3")
RESULTS_RANGE_PRESETS = [
    {"key": "l24h", "label": "L24h", "days": None, "hours": 24},
    {"key": "d3", "label": "Last 3 days", "days": 3, "hours": None},
    {"key": "week", "label": "Last week", "days": 7, "hours": None},
    {"key": "week2", "label": "Last 2 weeks", "days": 14, "hours": None},
    {"key": "month", "label": "Last month", "days": 31, "hours": None},
    {"key": "m3", "label": "Last 3 months", "days": 92, "hours": None},
    {"key": "year", "label": "Last year", "days": 365, "hours": None},
]


def _results_v7_range_summary_html(corq: List[Dict[str, Any]], cloq: List[Dict[str, Any]], audit_rows: List[Dict[str, Any]], label: str) -> str:
    def one(title: str, rows: List[Dict[str, Any]]) -> str:
        s = summarize_results(rows)
        avg = "—" if s.get("avg_odds") is None else f"{s['avg_odds']:.2f}"
        decided = int(s.get("won", 0) + s.get("lost", 0))
        return "".join([
            '<div class="hero-panel results-live-summary-card">',
            f'<div class="hero-title">{esc(title)}</div>',
            f'<div class="hero-line"><b>{int(s["picks"])}</b> picks | W-L-V-P {int(s["won"])}-{int(s["lost"])}-{int(s["void"])}-{int(s["pending"])}</div>',
            f'<div class="hero-line">Decided {decided} | Win {float(s["win_pct"]):.1f}% | Units {float(s["units"]):+.2f}u | ROI {float(s["roi"]):+.1f}%</div>',
            f'<div class="hero-line">Avg odds {esc(avg)} | Range {esc(label)}</div>',
            '</div>',
        ])
    return ''.join([
        '<div class="hero results-live-summary" id="results-live-summary">',
        one('CorQ TOP7', corq),
        one('CloQ', cloq),
        one('Audit', audit_rows),
        '</div>',
    ])


def _write_result_day_chunks(rows: List[Dict[str, Any]], title: str, day_iso: str) -> List[str]:
    """Write small full-card lazy chunks for one model/section/day."""
    RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    section = _results_section_key(title)
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    chunk_size = max(1, int(RESULTS_DAY_CHUNK_SIZE or 6))
    urls: List[str] = []
    if not rows_sorted:
        fname = _result_day_chunk_filename(section, day_iso, 1)
        write_text(RESULTS_LAZY_ASSET_DIR / fname, '<div class="empty">No results available in selected range.</div>')
        return [f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}"]
    for chunk_idx in range(0, len(rows_sorted), chunk_size):
        chunk = rows_sorted[chunk_idx:chunk_idx + chunk_size]
        cards = '<div class="grid results-card-grid">' + '\n'.join(
            render_result_card(row, chunk_idx + local_idx + 1, title)
            for local_idx, row in enumerate(chunk)
        ) + '</div>'
        fname = _result_day_chunk_filename(section, day_iso, (chunk_idx // chunk_size) + 1)
        write_text(RESULTS_LAZY_ASSET_DIR / fname, cards)
        urls.append(f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}")
    return urls


def _results_range_payload(corq_all: List[Dict[str, Any]], cloq_all: List[Dict[str, Any]], audit_all: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build range payload. All stats here use exactly the rows in the range."""
    payload: Dict[str, Any] = {"default": RESULTS_DEFAULT_RANGE_KEY, "ranges": {}}
    total_archive = len(corq_all) + len(cloq_all) + len(audit_all)
    for preset in RESULTS_RANGE_PRESETS:
        key = preset["key"]
        corq = _results_rows_for_preset(corq_all, key)
        cloq = _results_rows_for_preset(cloq_all, key)
        audit_rows = _results_rows_for_preset(audit_all, key)
        combined = corq + cloq + audit_rows
        mark_audit_h2h_top10(combined)
        start_dt, end_dt = _results_range_bounds(key)
        range_label = f"{start_dt.strftime('%d.%m.%y %H:%M')} - {end_dt.strftime('%d.%m.%y %H:%M')}"
        payload["ranges"][key] = {
            "label": preset["label"],
            "rangeLabel": range_label,
            "loadedLabel": f"{len(combined)} rows in {preset['label']} | total archive {total_archive} rows | cards load in chunks of {RESULTS_DAY_CHUNK_SIZE}",
            "summary": _results_v7_range_summary_html(corq, cloq, audit_rows, preset["label"]),
            "sections": {
                "corq": {
                    "title": "CorQ TOP7 Results",
                    "meta": _result_section_header(corq, "CorQ TOP7 Results"),
                    "chunks": _range_chunk_urls(corq_all, "CorQ TOP7 Results", key),
                },
                "cloq": {
                    "title": "CloQ Results",
                    "meta": _result_section_header(cloq, "CloQ Results"),
                    "chunks": _range_chunk_urls(cloq_all, "CloQ Results", key),
                },
                "audit": {
                    "title": "Audit Results",
                    "meta": _result_section_header(audit_rows, "Audit Results"),
                    "chunks": _range_chunk_urls(audit_all, "Audit Results", key),
                },
            },
            "stats": {
                "depth": depth_analysis(combined),
                "sets": sets_games_audit(combined),
                "tags": tag_analysis(combined),
            },
        }
    return payload


def _results_range_filter_panel(payload: Dict[str, Any], placement: str = "top") -> str:
    active = str(payload.get("default") or RESULTS_DEFAULT_RANGE_KEY)
    buttons = []
    for preset in RESULTS_RANGE_PRESETS:
        key = preset["key"]
        cls = "tag-chip audit-pill audit-pill-date results-range-btn"
        if key == active:
            cls += " active"
        buttons.append(f'<button type="button" class="{cls}" data-range-key="{esc(key)}">{esc(preset["label"])}</button>')
    active_payload = payload.get("ranges", {}).get(active, {})
    return "\n".join([
        f'<div class="summary-panel result-filter-builder results-range-panel results-range-panel-{esc(placement)}">',
        f'<div class="summary-title">Results range</div>',
        '<div class="result-filter-help">Default: Last 3 days. Wider ranges load full analytic cards progressively, without simplifying card content.</div>',
        '<div class="tag-list results-range-buttons">' + ''.join(buttons) + '</div>',
        f'<div class="results-range-label result-filter-help">{esc(active_payload.get("rangeLabel", ""))}</div>',
        f'<div class="results-range-loaded result-filter-help">{esc(active_payload.get("loadedLabel", ""))}</div>',
        '</div>',
    ])


def _results_range_css_block() -> str:
    return """
<style>
.results-range-buttons{gap:8px}.results-range-btn{cursor:pointer}.results-range-btn.active{border-color:var(--orange)!important;background:rgba(251,146,60,.24)!important;color:#fff!important;box-shadow:0 0 0 1px rgba(251,146,60,.25),0 0 18px rgba(251,146,60,.18)!important}.results-range-section-meta{margin-bottom:10px}.results-lazy-load-more{cursor:pointer}.results-lazy-load-more[disabled]{opacity:.45;cursor:not-allowed}.results-range-stats{margin-top:14px}.results-lazy-placeholder{border:1px dashed rgba(148,163,184,.35);border-radius:14px;padding:16px;color:#94a3b8;background:rgba(15,23,42,.45)}.results-live-summary{grid-template-columns:1fr 1fr 1fr}.results-live-summary-card b{color:#fff}.results-range-panel-bottom{margin-top:18px}@media(max-width:960px){.results-live-summary{grid-template-columns:1fr}}
</style>"""


def _results_range_section(section_key: str, title: str, payload: Dict[str, Any]) -> str:
    active = str(payload.get("default") or RESULTS_DEFAULT_RANGE_KEY)
    section = payload.get("ranges", {}).get(active, {}).get("sections", {}).get(section_key, {})
    chunks = section.get("chunks", [])
    root_id = f"results-range-root-{section_key}"
    chunk_payload = html.escape(json.dumps(chunks, ensure_ascii=False), quote=True)
    return "\n".join([
        f'<section class="results-lazy-section" data-section="{esc(section_key)}">',
        f'<div class="results-range-section-meta" data-section-meta="{esc(section_key)}">{section.get("meta", _result_section_header([], title))}</div>',
        f'<div id="{esc(root_id)}" class="results-lazy-root" data-section="{esc(section_key)}" data-chunks="{chunk_payload}" data-loaded="0">',
        f'  <div class="results-lazy-placeholder">Loading {esc(title)} cards...</div>',
        '</div>',
        f'<div class="tag-list results-lazy-controls"><button class="tag-chip results-lazy-load-more" type="button" data-target="{esc(root_id)}">Load more {esc(title)} cards</button><span class="tag-chip results-lazy-counter" data-counter-for="{esc(root_id)}">0 / {len(chunks)} chunks</span></div>',
        '</section>',
    ])


def _results_range_script_block(payload: Dict[str, Any]) -> str:
    payload_text = json.dumps(payload, ensure_ascii=False).replace('</', r'<\/')
    return f"""
<script type="application/json" id="results-range-payload">{payload_text}</script>
<script>
(function(){{
  const initialChunks = {max(1, int(RESULTS_RANGE_INITIAL_CHUNKS or 2))};
  const batchChunks = {max(1, int(RESULTS_RANGE_BATCH_CHUNKS or 3))};
  function getPayload(){{
    const node=document.getElementById('results-range-payload');
    if(!node) return {{default:'d3', ranges:{{}}}};
    try{{ return JSON.parse(node.textContent||'{{}}'); }}catch(e){{ return {{default:'d3', ranges:{{}}}}; }}
  }}
  function setChunks(root, chunks){{
    root.setAttribute('data-chunks', JSON.stringify(chunks||[]));
    root.setAttribute('data-loaded','0');
    root.innerHTML='<div class="results-lazy-placeholder">Loading result cards...</div>';
    document.querySelectorAll('[data-counter-for="'+root.id+'"]').forEach(function(c){{ c.textContent='0 / '+(chunks||[]).length+' chunks'; }});
    document.querySelectorAll('[data-target="'+root.id+'"]').forEach(function(btn){{ btn.disabled=false; btn.textContent='Load more cards'; }});
  }}
  async function loadNext(root, count){{
    if(!root) return;
    let chunks=[];
    try{{ chunks=JSON.parse(root.getAttribute('data-chunks')||'[]'); }}catch(e){{ chunks=[]; }}
    let loaded=parseInt(root.getAttribute('data-loaded')||'0',10)||0;
    const total=chunks.length;
    const placeholder=root.querySelector('.results-lazy-placeholder');
    if(placeholder) placeholder.remove();
    const target=Math.min(total, loaded + Math.max(1, count||1));
    while(loaded<target){{
      const url=chunks[loaded];
      try{{
        const res=await fetch(url,{{cache:'no-cache'}});
        const html=await res.text();
        root.insertAdjacentHTML('beforeend', html);
      }}catch(e){{
        root.insertAdjacentHTML('beforeend','<div class="empty">Failed to load result chunk.</div>');
        break;
      }}
      loaded++;
      root.setAttribute('data-loaded', String(loaded));
    }}
    document.querySelectorAll('[data-counter-for="'+root.id+'"]').forEach(function(c){{ c.textContent=loaded+' / '+total+' chunks'; }});
    document.querySelectorAll('[data-target="'+root.id+'"]').forEach(function(btn){{ if(loaded>=total){{ btn.disabled=true; btn.textContent='All cards loaded'; }} }});
  }}
  function applyRange(key){{
    const payload=getPayload();
    const range=(payload.ranges||{{}})[key] || (payload.ranges||{{}})[payload.default];
    if(!range) return;
    document.querySelectorAll('.results-range-btn').forEach(function(btn){{ btn.classList.toggle('active', btn.getAttribute('data-range-key')===key); }});
    document.querySelectorAll('.results-range-label').forEach(function(el){{ el.textContent=range.rangeLabel||''; }});
    document.querySelectorAll('.results-range-loaded').forEach(function(el){{ el.textContent=range.loadedLabel||''; }});
    const summary=document.getElementById('results-range-summary'); if(summary) summary.innerHTML=range.summary||'';
    ['corq','cloq','audit'].forEach(function(sectionKey){{
      const section=(range.sections||{{}})[sectionKey]||{{meta:'',chunks:[]}};
      document.querySelectorAll('[data-section-meta="'+sectionKey+'"]').forEach(function(meta){{ meta.innerHTML=section.meta||''; }});
      document.querySelectorAll('.results-lazy-root[data-section="'+sectionKey+'"]').forEach(function(root){{ setChunks(root, section.chunks||[]); loadNext(root, initialChunks); }});
    }});
    const stats=range.stats||{{}};
    const depth=document.getElementById('results-range-depth'); if(depth) depth.innerHTML=stats.depth||'';
    const sets=document.getElementById('results-range-sets'); if(sets) sets.innerHTML=stats.sets||'';
    const tags=document.getElementById('results-range-tags'); if(tags) tags.innerHTML=stats.tags||'';
  }}
  document.addEventListener('DOMContentLoaded', function(){{
    const payload=getPayload();
    document.querySelectorAll('.results-range-btn').forEach(function(btn){{ btn.addEventListener('click', function(){{ applyRange(btn.getAttribute('data-range-key')||payload.default||'d3'); }}); }});
    document.querySelectorAll('.results-lazy-load-more').forEach(function(btn){{ btn.addEventListener('click', function(){{ loadNext(document.getElementById(btn.getAttribute('data-target')), batchChunks); }}); }});
    applyRange(payload.default||'d3');
  }});
}})();
</script>"""


def render_results_page(manifest: Dict[str, Any]) -> str:
    if RESULTS_LAZY_ASSET_DIR.exists():
        shutil.rmtree(RESULTS_LAZY_ASSET_DIR, ignore_errors=True)
    RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    corq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    all_combined = corq_all + cloq_all + audit_all
    mark_audit_h2h_top10(all_combined)
    payload = _results_range_payload(corq_all, cloq_all, audit_all)
    active = payload.get('default', RESULTS_DEFAULT_RANGE_KEY)
    active_payload = payload.get('ranges', {}).get(active, {})
    active_stats = active_payload.get('stats', {})
    active_rows = _results_rows_for_preset(all_combined, str(active))
    body = [
        _result_css_block(),
        _results_lazy_css_block(),
        _results_range_css_block(),
        _results_range_filter_panel(payload, 'top'),
        f'<div id="results-range-summary">{active_payload.get("summary", "")}</div>',
        render_results_filter_builder(active_rows, total_count=len(all_combined)),
        _results_range_section('corq', 'CorQ TOP7 Results', payload),
        _results_range_section('cloq', 'CloQ Results', payload),
        _results_range_section('audit', 'Audit Results', payload),
        f'<div id="results-range-depth" class="results-range-stats">{active_stats.get("depth", "")}</div>',
        f'<div id="results-range-sets" class="results-range-stats">{active_stats.get("sets", "")}</div>',
        f'<div id="results-range-tags" class="results-range-stats">{active_stats.get("tags", "")}</div>',
        _results_range_filter_panel(payload, 'bottom'),
        _results_range_script_block(payload),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


# ============================================================
# Results range/lazy-load final override V8
# ============================================================
# Fix: Last 3 days must load all chunks for the whole 3-day range, not only
# the first/current-day chunks. Range summaries are computed from the complete
# server-side row set for each selected range.

RESULTS_DEFAULT_RANGE_KEY = "d3"
RESULTS_DAY_CHUNK_SIZE = int(os.getenv("RESULTS_DAY_CHUNK_SIZE", "5") or "5")
RESULTS_RANGE_INITIAL_CHUNKS = int(os.getenv("RESULTS_RANGE_INITIAL_CHUNKS", "2") or "2")
RESULTS_RANGE_BATCH_CHUNKS = int(os.getenv("RESULTS_RANGE_BATCH_CHUNKS", "3") or "3")
RESULTS_RANGE_PRESETS = [
    {"key": "l24h", "label": "L24h", "days": None, "hours": 24},
    {"key": "d3", "label": "Last 3 days", "days": 3, "hours": None},
    {"key": "week", "label": "Last week", "days": 7, "hours": None},
    {"key": "week2", "label": "Last 2 weeks", "days": 14, "hours": None},
    {"key": "month", "label": "Last month", "days": 31, "hours": None},
    {"key": "m3", "label": "Last 3 months", "days": 92, "hours": None},
    {"key": "year", "label": "Last year", "days": 365, "hours": None},
]


def _results_v8_now_local() -> datetime:
    tz = _results_range_tz()
    return datetime.now(tz)


def _results_range_bounds(key: str) -> Tuple[datetime, datetime]:
    """Calendar-aware range bounds in Europe/Bratislava.

    Last 3 days = today + previous 2 calendar days, not now minus 72 hours.
    This makes the default filter intuitive and stable for daily snapshots.
    """
    now = _results_v8_now_local()
    preset = next((p for p in RESULTS_RANGE_PRESETS if p.get('key') == key), None)
    if not preset:
        preset = next((p for p in RESULTS_RANGE_PRESETS if p.get('key') == RESULTS_DEFAULT_RANGE_KEY), RESULTS_RANGE_PRESETS[1])
    if preset.get('hours'):
        return now - timedelta(hours=int(preset['hours'])), now
    days = max(1, int(preset.get('days') or 3))
    start_day = now.date() - timedelta(days=days - 1)
    start_dt = datetime.combine(start_day, datetime.min.time(), tzinfo=_results_range_tz())
    end_dt = datetime.combine(now.date(), datetime.max.time(), tzinfo=_results_range_tz())
    return start_dt, end_dt


def _results_row_in_range(row: Dict[str, Any], key: str) -> bool:
    dt = _results_row_local_dt(row)
    if dt is None:
        # Fall back to plain result date if detailed start datetime is not available.
        day = result_row_local_date(row)
        if day is None:
            return False
        start_dt, end_dt = _results_range_bounds(key)
        return start_dt.date() <= day <= end_dt.date()
    start_dt, end_dt = _results_range_bounds(key)
    return start_dt <= dt <= end_dt


def _results_rows_for_preset(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    return [r for r in rows or [] if _results_row_in_range(r, key)]


def _results_days_for_rows(rows: List[Dict[str, Any]]) -> List[str]:
    days = {result_row_local_date_iso(r) for r in rows or [] if result_row_local_date_iso(r)}
    return sorted(days, reverse=True)


def _write_result_day_chunks(rows: List[Dict[str, Any]], title: str, day_iso: str) -> List[str]:
    RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    section = _results_section_key(title)
    rows_sorted = sorted(rows or [], key=result_card_sort_key)
    chunk_size = max(1, int(RESULTS_DAY_CHUNK_SIZE or 5))
    urls: List[str] = []
    if not rows_sorted:
        fname = _result_day_chunk_filename(section, day_iso, 1)
        write_text(RESULTS_LAZY_ASSET_DIR / fname, '<div class="empty">No results available in selected range.</div>')
        return [f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}"]
    for chunk_idx in range(0, len(rows_sorted), chunk_size):
        chunk = rows_sorted[chunk_idx:chunk_idx + chunk_size]
        cards = '<div class="grid results-card-grid">' + '\n'.join(
            render_result_card(row, chunk_idx + local_idx + 1, title)
            for local_idx, row in enumerate(chunk)
        ) + '</div>'
        fname = _result_day_chunk_filename(section, day_iso, (chunk_idx // chunk_size) + 1)
        write_text(RESULTS_LAZY_ASSET_DIR / fname, cards)
        urls.append(f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}")
    return urls


def _range_chunk_urls(rows: List[Dict[str, Any]], title: str, range_key: str) -> List[str]:
    urls: List[str] = []
    range_rows = _results_rows_for_preset(rows, range_key)
    for day_iso in _results_days_for_rows(range_rows):
        day_rows = _results_day_rows(range_rows, day_iso)
        urls.extend(_write_result_day_chunks(day_rows, title, day_iso))
    if not urls:
        RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
        section = _results_section_key(title)
        fname = f"results_{section}_{range_key}_empty.html"
        write_text(RESULTS_LAZY_ASSET_DIR / fname, '<div class="empty">No results available in selected range.</div>')
        urls.append(f"../assets/{RESULTS_LAZY_ASSET_DIRNAME}/{fname}")
    return urls


def _results_v8_range_summary_html(corq: List[Dict[str, Any]], cloq: List[Dict[str, Any]], audit_rows: List[Dict[str, Any]], label: str) -> str:
    def one(title: str, rows: List[Dict[str, Any]]) -> str:
        s = summarize_results(rows)
        avg = "—" if s.get("avg_odds") is None else f"{s['avg_odds']:.2f}"
        decided = int(s.get("won", 0) + s.get("lost", 0))
        return "".join([
            '<div class="hero-panel results-live-summary-card">',
            f'<div class="hero-title">{esc(title)}</div>',
            f'<div class="hero-line"><b>{int(s["picks"])}</b> picks | W-L-V-P {int(s["won"])}-{int(s["lost"])}-{int(s["void"])}-{int(s["pending"])}</div>',
            f'<div class="hero-line">Decided {decided} | Win {float(s["win_pct"]):.1f}% | Units {float(s["units"]):+.2f}u | ROI {float(s["roi"]):+.1f}%</div>',
            f'<div class="hero-line">Avg odds {esc(avg)} | Range {esc(label)}</div>',
            '</div>',
        ])
    return ''.join([
        '<div class="hero results-live-summary" id="results-live-summary">',
        one('CorQ TOP7', corq),
        one('CloQ', cloq),
        one('Audit', audit_rows),
        '</div>',
    ])


def _results_range_payload(corq_all: List[Dict[str, Any]], cloq_all: List[Dict[str, Any]], audit_all: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"default": RESULTS_DEFAULT_RANGE_KEY, "ranges": {}}
    total_archive = len(corq_all) + len(cloq_all) + len(audit_all)
    for preset in RESULTS_RANGE_PRESETS:
        key = str(preset["key"])
        corq = _results_rows_for_preset(corq_all, key)
        cloq = _results_rows_for_preset(cloq_all, key)
        audit_rows = _results_rows_for_preset(audit_all, key)
        combined = corq + cloq + audit_rows
        mark_audit_h2h_top10(combined)
        start_dt, end_dt = _results_range_bounds(key)
        range_label = f"{start_dt.strftime('%d.%m.%y %H:%M')} - {end_dt.strftime('%d.%m.%y %H:%M')}"
        payload["ranges"][key] = {
            "label": preset["label"],
            "rangeLabel": range_label,
            "loadedLabel": f"{len(combined)} rows in {preset['label']} | total archive {total_archive} rows | full cards load progressively",
            "autoloadAll": key in {"l24h", "d3"},
            "summary": _results_v8_range_summary_html(corq, cloq, audit_rows, preset["label"]),
            "sections": {
                "corq": {"title": "CorQ TOP7 Results", "meta": _result_section_header(corq, "CorQ TOP7 Results"), "chunks": _range_chunk_urls(corq_all, "CorQ TOP7 Results", key)},
                "cloq": {"title": "CloQ Results", "meta": _result_section_header(cloq, "CloQ Results"), "chunks": _range_chunk_urls(cloq_all, "CloQ Results", key)},
                "audit": {"title": "Audit Results", "meta": _result_section_header(audit_rows, "Audit Results"), "chunks": _range_chunk_urls(audit_all, "Audit Results", key)},
            },
            "stats": {"depth": depth_analysis(combined), "sets": sets_games_audit(combined), "tags": tag_analysis(combined)},
        }
    return payload


def _results_range_filter_panel(payload: Dict[str, Any], placement: str = "top") -> str:
    active = str(payload.get("default") or RESULTS_DEFAULT_RANGE_KEY)
    buttons = []
    for preset in RESULTS_RANGE_PRESETS:
        key = preset["key"]
        cls = "tag-chip audit-pill audit-pill-date results-range-btn"
        if key == active:
            cls += " active"
        buttons.append(f'<button type="button" class="{cls}" data-range-key="{esc(key)}">{esc(preset["label"])}</button>')
    active_payload = payload.get("ranges", {}).get(active, {})
    return "\n".join([
        f'<div class="summary-panel result-filter-builder results-range-panel results-range-panel-{esc(placement)}">',
        '<div class="summary-title">Results range</div>',
        '<div class="result-filter-help">Default: Last 3 days. L24h and Last 3 days autoload all chunks; wider ranges load by batches.</div>',
        '<div class="tag-list results-range-buttons">' + ''.join(buttons) + '</div>',
        f'<div class="results-range-label result-filter-help">{esc(active_payload.get("rangeLabel", ""))}</div>',
        f'<div class="results-range-loaded result-filter-help">{esc(active_payload.get("loadedLabel", ""))}</div>',
        '</div>',
    ])


def _results_range_css_block() -> str:
    return """
<style>
.results-range-buttons{gap:8px}.results-range-btn{cursor:pointer}.results-range-btn.active{border-color:var(--orange)!important;background:rgba(251,146,60,.24)!important;color:#fff!important;box-shadow:0 0 0 1px rgba(251,146,60,.25),0 0 18px rgba(251,146,60,.18)!important}.results-range-section-meta{margin-bottom:10px}.results-lazy-load-more{cursor:pointer}.results-lazy-load-more[disabled]{opacity:.45;cursor:not-allowed}.results-range-stats{margin-top:14px}.results-lazy-placeholder{border:1px dashed rgba(148,163,184,.35);border-radius:14px;padding:16px;color:#94a3b8;background:rgba(15,23,42,.45)}.results-live-summary{grid-template-columns:1fr 1fr 1fr}.results-live-summary-card b{color:#fff}.results-range-panel-bottom{margin-top:18px}@media(max-width:960px){.results-live-summary{grid-template-columns:1fr}}
</style>"""


def _results_range_script_block(payload: Dict[str, Any]) -> str:
    payload_text = json.dumps(payload, ensure_ascii=False).replace('</', r'<\/')
    return f"""
<script type="application/json" id="results-range-payload">{payload_text}</script>
<script>
(function(){{
  const initialChunks = {max(1, int(RESULTS_RANGE_INITIAL_CHUNKS or 2))};
  const batchChunks = {max(1, int(RESULTS_RANGE_BATCH_CHUNKS or 3))};
  function getPayload(){{
    const node=document.getElementById('results-range-payload');
    if(!node) return {{default:'d3', ranges:{{}}}};
    try{{ return JSON.parse(node.textContent||'{{}}'); }}catch(e){{ return {{default:'d3', ranges:{{}}}}; }}
  }}
  function setChunks(root, chunks){{
    root.setAttribute('data-chunks', JSON.stringify(chunks||[]));
    root.setAttribute('data-loaded','0');
    root.innerHTML='<div class="results-lazy-placeholder">Loading result cards...</div>';
    document.querySelectorAll('[data-counter-for="'+root.id+'"]').forEach(function(c){{ c.textContent='0 / '+(chunks||[]).length+' chunks'; }});
    document.querySelectorAll('[data-target="'+root.id+'"]').forEach(function(btn){{ btn.disabled=false; btn.textContent='Load more cards'; }});
  }}
  async function loadNext(root, count){{
    if(!root) return;
    let chunks=[];
    try{{ chunks=JSON.parse(root.getAttribute('data-chunks')||'[]'); }}catch(e){{ chunks=[]; }}
    let loaded=parseInt(root.getAttribute('data-loaded')||'0',10)||0;
    const total=chunks.length;
    const placeholder=root.querySelector('.results-lazy-placeholder');
    if(placeholder) placeholder.remove();
    const target=Math.min(total, loaded + Math.max(1, count||1));
    while(loaded<target){{
      const url=chunks[loaded];
      try{{
        const res=await fetch(url,{{cache:'no-cache'}});
        const html=await res.text();
        root.insertAdjacentHTML('beforeend', html);
      }}catch(e){{
        root.insertAdjacentHTML('beforeend','<div class="empty">Failed to load result chunk.</div>');
        break;
      }}
      loaded++;
      root.setAttribute('data-loaded', String(loaded));
    }}
    document.querySelectorAll('[data-counter-for="'+root.id+'"]').forEach(function(c){{ c.textContent=loaded+' / '+total+' chunks'; }});
    document.querySelectorAll('[data-target="'+root.id+'"]').forEach(function(btn){{ if(loaded>=total){{ btn.disabled=true; btn.textContent='All cards loaded'; }} }});
  }}
  function applyRange(key){{
    const payload=getPayload();
    const range=(payload.ranges||{{}})[key] || (payload.ranges||{{}})[payload.default];
    if(!range) return;
    document.querySelectorAll('.results-range-btn').forEach(function(btn){{ btn.classList.toggle('active', btn.getAttribute('data-range-key')===key); }});
    document.querySelectorAll('.results-range-label').forEach(function(el){{ el.textContent=range.rangeLabel||''; }});
    document.querySelectorAll('.results-range-loaded').forEach(function(el){{ el.textContent=range.loadedLabel||''; }});
    const summary=document.getElementById('results-range-summary'); if(summary) summary.innerHTML=range.summary||'';
    ['corq','cloq','audit'].forEach(function(sectionKey){{
      const section=(range.sections||{{}})[sectionKey]||{{meta:'',chunks:[]}};
      document.querySelectorAll('[data-section-meta="'+sectionKey+'"]').forEach(function(meta){{ meta.innerHTML=section.meta||''; }});
      document.querySelectorAll('.results-lazy-root[data-section="'+sectionKey+'"]').forEach(function(root){{
        const chunks=section.chunks||[];
        setChunks(root, chunks);
        loadNext(root, range.autoloadAll ? chunks.length : initialChunks);
      }});
    }});
    const stats=range.stats||{{}};
    const depth=document.getElementById('results-range-depth'); if(depth) depth.innerHTML=stats.depth||'';
    const sets=document.getElementById('results-range-sets'); if(sets) sets.innerHTML=stats.sets||'';
    const tags=document.getElementById('results-range-tags'); if(tags) tags.innerHTML=stats.tags||'';
  }}
  document.addEventListener('DOMContentLoaded', function(){{
    const payload=getPayload();
    document.querySelectorAll('.results-range-btn').forEach(function(btn){{ btn.addEventListener('click', function(){{ applyRange(btn.getAttribute('data-range-key')||payload.default||'d3'); }}); }});
    document.querySelectorAll('.results-lazy-load-more').forEach(function(btn){{ btn.addEventListener('click', function(){{ loadNext(document.getElementById(btn.getAttribute('data-target')), batchChunks); }}); }});
    applyRange(payload.default||'d3');
  }});
}})();
</script>"""


def render_results_page(manifest: Dict[str, Any]) -> str:
    if RESULTS_LAZY_ASSET_DIR.exists():
        shutil.rmtree(RESULTS_LAZY_ASSET_DIR, ignore_errors=True)
    RESULTS_LAZY_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    corq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_corq.json', []))
    cloq_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_cloq.json', []))
    audit_all = json_rows(read_json(OUTPUTS / 'results' / 'latest_results_audit.json', []))
    all_combined = corq_all + cloq_all + audit_all
    mark_audit_h2h_top10(all_combined)
    payload = _results_range_payload(corq_all, cloq_all, audit_all)
    active = payload.get('default', RESULTS_DEFAULT_RANGE_KEY)
    active_payload = payload.get('ranges', {}).get(active, {})
    active_stats = active_payload.get('stats', {})
    active_rows = _results_rows_for_preset(all_combined, str(active))
    body = [
        _result_css_block(),
        _results_lazy_css_block(),
        _results_range_css_block(),
        _results_range_filter_panel(payload, 'top'),
        f'<div id="results-range-summary">{active_payload.get("summary", "")}</div>',
        render_results_filter_builder(active_rows, total_count=len(all_combined)),
        _results_range_section('corq', 'CorQ TOP7 Results', payload),
        _results_range_section('cloq', 'CloQ Results', payload),
        _results_range_section('audit', 'Audit Results', payload),
        f'<div id="results-range-depth" class="results-range-stats">{active_stats.get("depth", "")}</div>',
        f'<div id="results-range-sets" class="results-range-stats">{active_stats.get("sets", "")}</div>',
        f'<div id="results-range-tags" class="results-range-stats">{active_stats.get("tags", "")}</div>',
        _results_range_filter_panel(payload, 'bottom'),
        _results_range_script_block(payload),
    ]
    return page_shell('Results', RESULTS_PATH, '\n'.join(body), manifest)


# ============================================================
# Unified visual ordering override V2
# ============================================================
# Single render-order source for CorQ, CloQ and Audit cards.
# CorQ/CloQ are displayed from strongest to weakest model pick.
# Audit keeps the operational nearest-match-time order.

def _sort_number(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "—", "-", "N/A", "NA", "None", "null"):
            return default
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace("pp", "").replace(",", ".")
            if value.startswith("#"):
                value = value[1:]
        return float(value)
    except Exception:
        return default


def _first_numeric_value(row: Dict[str, Any], *keys: str, default: Optional[float] = None) -> Optional[float]:
    for key in keys:
        value = nested_get(row, *key.split(".")) if "." in key else row.get(key)
        parsed = _sort_number(value)
        if parsed is not None:
            return parsed
    return default


def _first_rank_value(row: Dict[str, Any], *keys: str) -> Optional[int]:
    value = _first_numeric_value(row, *keys)
    if value is None or value <= 0:
        return None
    return int(value)


def _sort_probability_value(row: Dict[str, Any]) -> float:
    value = probability(row)
    parsed = _sort_number(value, 0.0) or 0.0
    if 0.0 < parsed <= 1.0:
        parsed *= 100.0
    return parsed


def _sort_pick_time(row: Dict[str, Any]) -> int:
    dt = audit_match_time_utc(row)
    return int(dt.timestamp()) if dt is not None else 9999999999


def _corq_visual_sort_key(row: Dict[str, Any]) -> Tuple[int, int, float, float, float, float, int, str]:
    rank = _first_rank_value(
        row,
        "top7_rank",
        "corq_top7_rank",
        "snapshot_rank",
        "rank",
        "_corq_render_rank",
    )
    score = _first_numeric_value(
        row,
        "corq_top7_sort_score",
        "top7_sort_score",
        "top7_quality_score",
        "corq_quality_score",
        "quality_score",
        default=0.0,
    ) or 0.0
    value_delta = _first_numeric_value(
        row,
        "marq_v2_value_delta_pp",
        "corq_value_delta_pp",
        "value_delta_pp",
        "model_market_delta_pp",
        default=-999.0,
    ) or -999.0
    ev = _first_numeric_value(
        row,
        "marq_v2_expected_value_pct",
        "expected_value_pct",
        "ev_pct",
        "expected_value",
        default=-999.0,
    ) or -999.0
    return (
        0 if rank is not None else 1,
        rank if rank is not None else 9999,
        -score,
        -_sort_probability_value(row),
        -value_delta,
        -ev,
        _sort_pick_time(row),
        pick_name(row).lower(),
    )


def _cloq_visual_sort_key(row: Dict[str, Any]) -> Tuple[int, int, float, float, float, float, int, str]:
    rank = _first_rank_value(row, "cloq_rank", "rank", "_corq_render_rank")
    score = _first_numeric_value(
        row,
        "cloq_score",
        "cloq_sort_score",
        "cloq_quality_score",
        "corq_top7_sort_score",
        "top7_quality_score",
        default=0.0,
    ) or 0.0
    gap = _first_numeric_value(row, "cloq_odds_gap_pct", "odds_gap_pct", default=999.0) or 999.0
    value_delta = _first_numeric_value(
        row,
        "marq_v2_value_delta_pp",
        "corq_value_delta_pp",
        "value_delta_pp",
        default=-999.0,
    ) or -999.0
    ev = _first_numeric_value(row, "expected_value_pct", "ev_pct", default=-999.0) or -999.0
    return (
        0 if rank is not None else 1,
        rank if rank is not None else 9999,
        -score,
        gap,
        -value_delta,
        -ev,
        _sort_pick_time(row),
        pick_name(row).lower(),
    )


def sort_pick_rows(rows: List[Dict[str, Any]], page: str = "corq") -> List[Dict[str, Any]]:
    page_key = str(page or "").lower()
    clean_rows = [r for r in rows or [] if isinstance(r, dict)]
    if page_key == "cloq":
        return sorted(clean_rows, key=_cloq_visual_sort_key)
    if page_key in {"all", "audit", "thinq"}:
        return sorted(clean_rows, key=_audit_v3_time_sort_key)
    return sorted(clean_rows, key=_corq_visual_sort_key)


def _assign_visual_ranks(rows: List[Dict[str, Any]]) -> None:
    for idx, row in enumerate(rows or [], start=1):
        if isinstance(row, dict):
            row["_corq_render_rank"] = idx


def render_cards_page(title: str, active: str, rows: List[Dict[str, Any]], manifest: Dict[str, Any], page: str = "corq", dedupe: bool = False) -> str:
    rows = dedupe_matches(rows) if dedupe else [r for r in rows or [] if isinstance(r, dict)]
    rows = sort_pick_rows(rows, page=page)
    _assign_visual_ranks(rows)
    mark_audit_h2h_top10(rows)
    ensure_logs(rows)
    if not rows:
        cards = '<div class="empty">No rows available.</div>'
    else:
        cards = '<div class="grid">' + "\n".join(render_card(r, i + 1, page=page) for i, r in enumerate(rows)) + '</div>'
    summary = render_notes_summary(rows) if page in {"corq", "cloq", "all"} else ""
    return page_shell(title, active, summary + cards, manifest)


def render_all() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_json(OUTPUTS / "latest_manifest.json", {})
    top7_raw = json_rows(read_json(OUTPUTS / "latest_top7.json", []))
    all_rows_raw = json_rows(read_json(OUTPUTS / "latest_all.json", []))
    cloq_raw = json_rows(read_json(OUTPUTS / "cloq" / "latest_cloq.json", []))
    if not cloq_raw:
        cloq_raw = json_rows(read_json(OUTPUTS / "latest_cloq.json", []))

    top7 = sort_pick_rows(top7_raw, page="corq")
    cloq = sort_pick_rows(cloq_raw, page="cloq")
    mark_audit_cloq_rows(all_rows_raw, cloq)
    all_rows_for_audit = sort_pick_rows(all_rows_raw, page="all")
    _assign_visual_ranks(top7)
    _assign_visual_ranks(cloq)
    _assign_visual_ranks(all_rows_for_audit)
    ensure_logs(top7 + all_rows_for_audit + cloq)

    write_text(SITE_DIR / "index.html", page_shell("CorQ", "root", '<script>location.href="' + esc(TOP7_PATH) + '/"</script>', manifest))
    write_text(SITE_DIR / TOP7_PATH / "index.html", render_cards_page("CorQ", TOP7_PATH, top7, manifest, page="corq"))
    write_text(SITE_DIR / ALL_PATH / "index.html", render_cards_page("Audit", ALL_PATH, all_rows_for_audit, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / CLOQ_PATH / "index.html", render_cards_page("CloQ", CLOQ_PATH, cloq, manifest, page="cloq"))
    write_text(SITE_DIR / THINQ_PATH / "index.html", render_cards_page("ThinQ", THINQ_PATH, all_rows_for_audit, manifest, page="all", dedupe=True))
    write_text(SITE_DIR / RESULTS_PATH / "index.html", render_results_page(manifest))
    write_text(SITE_DIR / HISTORY_PATH / "index.html", render_results_history_index(manifest))

    corq_all, cloq_all, audit_all = _history_all_result_rows()
    start, _end = results_default_date_range()
    history_rows = _history_rows_before_window(corq_all + cloq_all + audit_all, start)
    for day in sorted({_history_row_date_iso(r) for r in history_rows if _history_row_date_iso(r) != "unknown"}, reverse=True):
        write_text(SITE_DIR / HISTORY_PATH / f"{day}.html", render_results_history_day(manifest, day))

    write_text(SITE_DIR / CORQ_RSS_PATH, rss_items(top7, "CorQ TOP7"))
    write_text(SITE_DIR / CLOQ_RSS_PATH, rss_items(cloq, "CloQ"))
    write_text(SITE_DIR / THINQ_RSS_PATH, rss_items(all_rows_for_audit[:20], "ThinQ"))
    render_manifest = {
        "rendered_at": datetime.now(tz=timezone.utc).isoformat(),
        "top7_count": len(top7),
        "all_count": len(all_rows_for_audit),
        "cloq_count": len(cloq),
        "render_order_policy": "corq_cloq_model_rank_audit_match_time",
        "history_path": HISTORY_PATH,
        "site_root": str(SITE_DIR),
    }
    write_text(SITE_DIR / "render_manifest.json", json.dumps(render_manifest, ensure_ascii=False, indent=2))
    print(f"Rendered site: top7={len(top7)} all={len(all_rows_for_audit)} cloq={len(cloq)} history={HISTORY_PATH} order=rank root={SITE_DIR}")



# ============================================================
# LucQ API PRO-only page override V1
# Same page shell and card grid, independent of all other project layers.
# ============================================================

def _lucq_probability(row: Dict[str, Any]) -> float:
    value = as_float(row.get("lucq_probability"), 0.0) or 0.0
    return value / 100.0 if value > 1.0 else value


def _lucq_sort_key(row: Dict[str, Any]) -> Tuple[float, int, str]:
    dt = audit_match_time_utc(row)
    timestamp = int(dt.timestamp()) if dt is not None else 9999999999
    return (-_lucq_probability(row), timestamp, pick_name(row).lower())


def _lucq_metric_box(title: str, head: str, metrics: List[Tuple[str, str]]) -> str:
    lines = [f'<section class="metric-box small-box lucq-box"><div class="box-head"><span>{esc(title)}</span><b>{esc(head)}</b></div>']
    for label, value in metrics:
        lines.append(metric_row(label, esc(value)))
    lines.append('</section>')
    return "\n".join(lines)


def render_lucq_card(row: Dict[str, Any], rank: int) -> str:
    probability_value = _lucq_probability(row)
    probability_text = as_pct(probability_value, 1)
    source = str(row.get("data_source") or row.get("source") or "API PRO")
    start = str(row.get("match_start") or row.get("start_time") or "—")
    selection = str(row.get("lucq_selection") or f"{pick_name(row)} to win")
    line = fmt_odds(row.get("lucq_line") or pick_odds(row))
    overround = as_pct(row.get("overround"), 1)
    status = str(row.get("lucq_status") or "OK")
    endpoint = str(row.get("odds_endpoint") or "Exact event odds")
    direction = str(row.get("odds_matching_direction") or "Confirmed")

    pick_box = "\n".join([
        '<section class="pick-main compact-v3">',
        '<div class="compact-topline">',
        f'<span class="rank-num">#{rank}</span>',
        f'<span class="compact-datetime-pill"><span class="compact-date">{esc(start_date(row))}</span><span class="compact-clock">{esc(start_time(row))}</span></span>',
        '<span class="compact-top-tags"><span class="insight-chip positive">API PRO</span></span>',
        '</div>',
        '<div class="compact-player pick-side no-label">',
        f'<div class="compact-name-row"><span class="compact-name">{esc(pick_name(row))}<span class="compact-odds inline pick">@ {line}</span></span></div>',
        '</div>',
        '<div class="compact-vs">TO BEAT</div>',
        '<div class="compact-player opp-side no-label">',
        f'<div class="compact-name-row"><span class="compact-name">{esc(opponent_name(row))}<span class="compact-odds inline opp">@ {fmt_odds(opponent_odds(row))}</span></span></div>',
        '</div>',
        f'<div class="compact-match"><div class="compact-meta compact-meta-only">{esc(meta_line(row))}</div></div>',
        '</section>',
    ])

    boxes = [
        _lucq_metric_box("LucQ", probability_text, [
            ("Selection", selection),
            ("Probability", probability_text),
            ("Line", line),
            ("Status", status),
        ]),
        _lucq_metric_box("API PRO", "Real data", [
            ("Source", source),
            ("Market", str(row.get("lucq_market") or "Match winner")),
            ("Real line", "Yes" if row.get("lucq_real_line") else "No"),
            ("Policy", str(row.get("source_policy") or "API_PRO_ONLY")),
        ]),
        _lucq_metric_box("Probability", probability_text, [
            ("P1 odds", fmt_odds(row.get("odds_player1"))),
            ("P2 odds", fmt_odds(row.get("odds_player2"))),
            ("No-vig", probability_text),
            ("Overround", overround),
        ]),
        _lucq_metric_box("Match", status, [
            ("Surface", str(row.get("surface") or "—")),
            ("Best of", str(row.get("best_of") or "—")),
            ("Start", start),
            ("Event ID", str(row.get("event_id") or "—")),
        ]),
        _lucq_metric_box("Audit", "Confirmed", [
            ("Match", direction),
            ("Endpoint", endpoint),
            ("Version", str(row.get("lucq_version") or "—")),
            ("Rank", str(rank)),
        ]),
    ]
    return f'<article class="pick-card lucq-card" id="lucq-match-{rank}">' + pick_box + "".join(boxes) + '</article>'


def render_lucq_page(rows: List[Dict[str, Any]], manifest: Dict[str, Any]) -> str:
    clean = sorted([row for row in rows if isinstance(row, dict)], key=_lucq_sort_key)
    if clean:
        cards = '<div class="grid">' + "\n".join(render_lucq_card(row, index) for index, row in enumerate(clean, 1)) + '</div>'
    else:
        cards = '<div class="empty">No LucQ API PRO rows available.</div>'
    intro = (
        '<section class="summary-panel data-notes-summary">'
        '<div class="summary-title">LucQ</div>'
        '<div class="hero-line">API PRO-only probability layer. Matches are sorted by LucQ probability from highest to lowest.</div>'
        '</section>'
    )
    return page_shell("LucQ", LUCQ_PATH, intro + cards, manifest)



# LucQ analytical card override V2.
def _lucq_value(value: Any, digits: int = 1, suffix: str = "") -> str:
    number = as_float(value)
    return "N/A" if number is None else f"{number:.{digits}f}{suffix}"


def _lucq_triplet(row: Dict[str, Any], family: str) -> str:
    if family == "aces":
        values = (row.get("pick_aces_projection"), row.get("opponent_aces_projection"), row.get("total_aces_projection"))
    else:
        values = (row.get("pick_df_projection"), row.get("opponent_df_projection"), row.get("total_df_projection"))
    return " | ".join(_lucq_value(value, 1) for value in values)


def _lucq_signal(selection: Any, probability_value: Any) -> str:
    text = str(selection or "").strip()
    probability_text = as_pct(probability_value, 1, "N/A")
    return f"{text} | {probability_text}" if text else "N/A"


def render_lucq_card(row: Dict[str, Any], rank: int) -> str:
    pick_box = "\n".join([
        '<section class="pick-main compact-v3">',
        '<div class="compact-topline">',
        f'<span class="rank-num">#{rank}</span>',
        f'<span class="compact-datetime-pill"><span class="compact-date">{esc(start_date(row))}</span><span class="compact-clock">{esc(start_time(row))}</span></span>',
        '<span class="compact-top-tags"><span class="insight-chip positive">API PRO</span></span>',
        '</div>',
        '<div class="compact-player pick-side no-label">',
        f'<div class="compact-name-row"><span class="compact-name">{esc(pick_name(row))}<span class="compact-odds inline pick">@ {fmt_odds(pick_odds(row))}</span></span></div>',
        '</div>',
        '<div class="compact-vs">TO BEAT</div>',
        '<div class="compact-player opp-side no-label">',
        f'<div class="compact-name-row"><span class="compact-name">{esc(opponent_name(row))}<span class="compact-odds inline opp">@ {fmt_odds(opponent_odds(row))}</span></span></div>',
        '</div>',
        f'<div class="compact-match"><div class="compact-meta compact-meta-only">{esc(meta_line(row))}</div></div>',
        '</section>',
    ])
    boxes = [
        _lucq_metric_box("LucQ", as_pct(row.get("lucq_probability"), 1, "N/A"), [
            ("Winner", pick_name(row)),
            ("Win probability", as_pct(row.get("lucq_probability"), 1, "N/A")),
            ("Data quality", str(row.get("lucq_data_quality") or "N/A")),
            ("Quality score", as_pct(row.get("lucq_data_quality_score"), 0, "N/A")),
        ]),
        _lucq_metric_box("Sets", _lucq_value(row.get("projected_sets"), 2), [
            ("Projection", _lucq_value(row.get("projected_sets"), 2)),
            ("Sets O/U", _lucq_signal(row.get("sets_selection"), row.get("sets_probability"))),
            ("Line", _lucq_value(row.get("sets_line"), 1)),
            ("Samples P/O", f'{row.get("pick_shape_sample") or 0} | {row.get("opponent_shape_sample") or 0}'),
        ]),
        _lucq_metric_box("Games", _lucq_value(row.get("projected_games"), 1), [
            ("Projection", _lucq_value(row.get("projected_games"), 1)),
            ("Games O/U", _lucq_signal(row.get("games_selection"), row.get("games_probability"))),
            ("Line", _lucq_value(row.get("games_line"), 1)),
            ("TB probability", as_pct(row.get("tb_probability"), 1, "N/A")),
        ]),
        _lucq_metric_box("Aces", _lucq_value(row.get("total_aces_projection"), 1), [
            ("P | O | Total", _lucq_triplet(row, "aces")),
            ("Status", str(row.get("aces_status") or "N/A")),
            ("Source", str(row.get("serve_source") or "N/A")),
            ("Policy", "API PRO only"),
        ]),
        _lucq_metric_box("Double faults", _lucq_value(row.get("total_df_projection"), 1), [
            ("P | O | Total", _lucq_triplet(row, "df")),
            ("Status", str(row.get("df_status") or "N/A")),
            ("Shape source", str(row.get("shape_source") or "N/A")),
            ("Version", str(row.get("lucq_version") or "N/A")),
        ]),
    ]
    return f'<article class="pick-card lucq-card" id="lucq-match-{rank}">' + pick_box + "".join(boxes) + '</article>'


def render_lucq_page(rows: List[Dict[str, Any]], manifest: Dict[str, Any]) -> str:
    clean = sorted([row for row in rows if isinstance(row, dict)], key=_lucq_sort_key)
    cards = ('<div class="grid">' + "\n".join(render_lucq_card(row, index) for index, row in enumerate(clean, 1)) + '</div>') if clean else '<div class="empty">No LucQ API PRO rows available.</div>'
    intro = '<section class="summary-panel data-notes-summary"><div class="summary-title">LucQ</div><div class="hero-line">API PRO projections for winner, sets, games, tiebreaks, aces and double faults. Missing source data is shown as N/A.</div></section>'
    return page_shell("LucQ", LUCQ_PATH, intro + cards, manifest)

_ORIGINAL_RENDER_ALL_BEFORE_LUCQ = render_all


def render_all() -> None:
    _ORIGINAL_RENDER_ALL_BEFORE_LUCQ()
    manifest = read_json(OUTPUTS / "latest_manifest.json", {})
    lucq_rows = json_rows(read_json(OUTPUTS / "lucq" / "latest_lucq.json", []))
    write_text(SITE_DIR / LUCQ_PATH / "index.html", render_lucq_page(lucq_rows, manifest))
    write_text(SITE_DIR / LUCQ_RSS_PATH, rss_items(lucq_rows, "LucQ"))
    print(f"Rendered LucQ: rows={len(lucq_rows)} path={LUCQ_PATH}")



# ============================================================
# LucQ compact analytical card + inline evaluation override V3
# ============================================================

def _lucq_status_text(value: Any) -> str:
    text = str(value or "N/A").strip().upper().replace("_", " ")
    return text if text else "N/A"


def _lucq_result_css(status: Any) -> str:
    text = _lucq_status_text(status)
    if text in {"WON", "WIN"}:
        return "good"
    if text in {"LOST", "LOSS"}:
        return "bad"
    return "neutral"


def _lucq_actual_triplet(row: Dict[str, Any], family: str) -> str:
    if family == "aces":
        values = (row.get("actual_pick_aces"), row.get("actual_opponent_aces"), row.get("actual_total_aces"))
    else:
        values = (row.get("actual_pick_df"), row.get("actual_opponent_df"), row.get("actual_total_df"))
    if all(value is None for value in values):
        return "— | — | —"
    return " | ".join(_lucq_value(value, 1) if value is not None else "—" for value in values)


def _lucq_match_box(row: Dict[str, Any], rank: int) -> str:
    return "\n".join([
        '<section class="pick-main compact-v3">',
        '<div class="compact-topline">',
        f'<span class="rank-num">#{rank}</span>',
        f'<span class="compact-datetime-pill"><span class="compact-date">{esc(start_date(row))}</span><span class="compact-clock">{esc(start_time(row))}</span></span>',
        '</div>',
        '<div class="compact-player pick-side no-label">',
        f'<div class="compact-name-row"><span class="compact-name">{esc(pick_name(row))}</span></div>',
        '</div>',
        '<div class="compact-vs">VS</div>',
        '<div class="compact-player opp-side no-label">',
        f'<div class="compact-name-row"><span class="compact-name">{esc(opponent_name(row))}</span></div>',
        '</div>',
        f'<div class="compact-match"><div class="compact-meta-only">{esc(meta_line(row))}</div></div>',
        '</section>',
    ])


def _lucq_sets_games_box(row: Dict[str, Any]) -> str:
    return _lucq_metric_box("Sets / Games / TB", as_pct(row.get("lucq_probability"), 1, "N/A"), [
        ("Sets", f'{_lucq_value(row.get("projected_sets"), 2)} | {_lucq_signal(row.get("sets_selection"), row.get("sets_probability"))}'),
        ("Games", f'{_lucq_value(row.get("projected_games"), 1)} | {_lucq_signal(row.get("games_selection"), row.get("games_probability"))}'),
        ("TB", f'{str(row.get("tb_selection") or "N/A")} | {as_pct(row.get("tb_probability"), 1, "N/A")}'),
        ("Sample P / O", f'{row.get("pick_shape_sample") or 0} / {row.get("opponent_shape_sample") or 0}'),
    ])


def _lucq_serve_box(row: Dict[str, Any]) -> str:
    return _lucq_metric_box("Aces / Double faults", _lucq_value(row.get("total_aces_projection"), 1), [
        ("Aces P | O | T", _lucq_triplet(row, "aces")),
        ("DF P | O | T", _lucq_triplet(row, "df")),
        ("Aces actual", _lucq_actual_triplet(row, "aces")),
        ("DF actual", _lucq_actual_triplet(row, "df")),
    ])


def _lucq_evaluation_box(row: Dict[str, Any]) -> str:
    overall = _lucq_status_text(row.get("lucq_result_status") or "PENDING")
    metrics = [
        ("Sets", _lucq_status_text(row.get("sets_result_status"))),
        ("Games", _lucq_status_text(row.get("games_result_status"))),
        ("TB", _lucq_status_text(row.get("tb_result_status"))),
        ("Aces", _lucq_status_text(row.get("aces_result_status"))),
        ("Double faults", _lucq_status_text(row.get("df_result_status"))),
    ]
    lines = [f'<section class="metric-box small-box"><div class="box-head">Evaluation <b class="{_lucq_result_css(overall)}">{esc(overall)}</b></div>']
    for label, value in metrics:
        lines.append(metric_row(label, esc(value), _lucq_result_css(value)))
    lines.append('</section>')
    return "\n".join(lines)


def render_lucq_card(row: Dict[str, Any], rank: int) -> str:
    return "".join([
        '<article class="pick-card lucq-card">',
        _lucq_match_box(row, rank),
        _lucq_sets_games_box(row),
        _lucq_serve_box(row),
        _lucq_evaluation_box(row),
        '</article>',
    ])


def render_lucq_page(rows: List[Dict[str, Any]], manifest: Dict[str, Any]) -> str:
    clean = sorted([row for row in rows if isinstance(row, dict)], key=_lucq_sort_key)
    cards = ('<main class="grid">' + "\n".join(render_lucq_card(row, index) for index, row in enumerate(clean, 1)) + '</main>') if clean else '<div class="empty">No LucQ rows available.</div>'
    intro = '<section class="summary-panel"><div class="summary-title">LucQ</div><div>Sets, games, tiebreak, aces and double-fault projections with evaluation on the same page.</div></section>'
    return page_shell("LucQ", LUCQ_PATH, intro + cards, manifest)


def main() -> None:
    render_all()


if __name__ == "__main__":
    main()
