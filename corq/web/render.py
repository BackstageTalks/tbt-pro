from __future__ import annotations

import base64
import html
import json
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
        "marq": "MarQ summarises market-facing signals: crowd split, market edge, movement, CLV and final market read.",
        "marq_edge": "MarQ Edge is Pick Marq minus 50%. Pick Marq is the median no-vig market probability for the displayed pick across usable bookmaker quotes.",
        "marq_move": "Range | Move: Range is opening pick odds -> latest pick odds. Move is the market direction from the implied-probability change. Stable means the move is below the configured movement threshold.",
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
        "marq_delta": "MarQ Delta: difference between final CorQ and MarQ market probability, shown in percentage points. Positive means CorQ is above market, negative means below market.",
        "value_delta": "Value Delta: CorQ probability minus raw break-even probability from the current decimal odds. Positive means model value versus price; negative means short/no value at the offered odds.",
        "ev": "EV: expected value using CorQ probability and current decimal odds. Formula: CorQ * odds - 1. It is an audit indicator, not a hard filter.",
        "price": "Price: compact price/value tag. Short means low odds, Fair means mid odds, Long Risk means higher price. No Value/Value+/Neutral comes from Value Delta.",
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

def player_rank_display(row: Dict[str, Any], side: str) -> str:
    keys = [f"{side}_ta_rank_display", f"{side}_rank_display", f"{side}_ta_rank", f"{side}_rank"]
    for key in keys:
        val = row.get(key)
        if val is None or val == "":
            continue
        txt = str(val).strip()
        if txt.startswith("(") and txt.endswith(")"):
            return txt
        try:
            return f"({int(float(txt))})"
        except Exception:
            if txt and txt.lower() != "none":
                return f"({txt})"
    return "(X)"


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


def meta_line(row: Dict[str, Any]) -> str:
    bits = []
    for key in ("tournament", "category", "surface", "best_of"):
        val = row.get(key)
        if val:
            bits.append(str(val))
    return " · ".join(bits) if bits else "—"


def log_link(row: Dict[str, Any]) -> str:
    return f'../logs/{esc(match_key(row))}/index.html'


def ensure_logs(rows: List[Dict[str, Any]]) -> None:
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
        f'<article class="pick-card" data-tags="{esc(data_tags)}">',
        '<section class="pick-main compact-v3">',
        '<div class="compact-topline">',
        (rank_badge or f'<div class="rank-num">#{rank or "—"}</div>'),
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
        f'<div class="compact-match"><div class="compact-match-row"><span class="compact-time">{esc(start_time(row))}</span><span class="compact-meta">{esc(meta_line(row))}</span></div></div>',
        f'<div class="compact-tags bottom-notes">{note_html}</div>' if note_html else '',
        '</section>',
        render_mmx_box(row),
        '<section class="metric-box corq-box">',
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


def triplet_market_display(row: Dict[str, Any], family: str) -> str:
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
        "corq_thinq_weight",
        "thinq_weight",
        "model_mix_thinq_weight",
        "corq_model_mix_thinq_weight",
    )
    marq_weight = _first_data_value(
        row,
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


def _probability_ratio_from_value(value: Any) -> Optional[float]:
    num = as_float(value)
    if num is None:
        return None
    if abs(num) > 1.0:
        num /= 100.0
    if 0.0 <= num <= 1.0:
        return num
    return None


def _raw_implied_probability(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(_first_data_value(row, "raw_implied_probability", "break_even_probability"))
    if explicit is not None:
        return explicit / 100.0 if explicit > 1.0 else explicit
    odds = pick_odds(row)
    if odds is None or odds <= 0:
        return None
    return 1.0 / odds


def _value_delta_pp(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(_first_data_value(row, "corq_value_delta_pp", "value_delta_pp", "price_value_delta_pp"))
    if explicit is not None:
        return explicit
    corq = _probability_ratio_from_value(_first_data_value(row, "corq_calibrated_probability", "corq_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "probability"))
    raw = _raw_implied_probability(row)
    if corq is None or raw is None:
        return None
    return (corq - raw) * 100.0


def _expected_value_pct(row: Dict[str, Any]) -> Optional[float]:
    explicit = as_float(_first_data_value(row, "expected_value_pct", "ev_pct"))
    if explicit is not None:
        return explicit if abs(explicit) > 1.0 else explicit * 100.0
    explicit_ratio = as_float(_first_data_value(row, "expected_value", "ev"))
    if explicit_ratio is not None:
        return explicit_ratio * 100.0 if abs(explicit_ratio) <= 1.0 else explicit_ratio
    odds = pick_odds(row)
    corq = _probability_ratio_from_value(_first_data_value(row, "corq_calibrated_probability", "corq_probability", "corq_estimated_win_probability", "win_probability", "estimated_win_probability", "probability"))
    if odds is None or corq is None:
        return None
    return ((corq * odds) - 1.0) * 100.0


def _price_value_text(row: Dict[str, Any]) -> str:
    explicit = str(_first_data_value(row, "price_value_display", "price_value_label") or "").strip()
    if explicit:
        return explicit
    odds = pick_odds(row)
    delta = _value_delta_pp(row)
    if odds is None or delta is None:
        return "—"
    price = "Short" if odds < 1.50 else "Fair" if odds <= 2.20 else "Long Risk"
    value = "Value+" if delta >= 3.0 else "Neutral" if delta >= -2.0 else "No Value"
    return f"{price} | {value}"


def _value_metric_class(value: Any) -> str:
    return sign_class(value)

def render_mmx_box(row: Dict[str, Any]) -> str:
    """Compact CorQ Model Mix diagnostics box with value audit."""
    thinq_prob_value = _first_data_value(row, "corq_raw_model_probability", "thinq_pick_probability", "thinq_probability", "top7_thinq_pick_probability")
    marq_prob_value = _first_data_value(row, "corq_market_probability", "marq_pick_probability", "marq_crowd_pick_pct", "market_pick_probability")
    thinq_input = row.get("corq_thinq_input_pp")
    marq_input = row.get("corq_marq_input_pp")
    final_prob = _first_data_value(row, "corq_calibrated_probability", "corq_probability", "corq_estimated_win_probability")
    delta = marq_delta_pp(row)
    value_delta = _value_delta_pp(row)
    ev_pct = _expected_value_pct(row)
    price_text = _price_value_text(row)
    return "\n".join(
        [
            '<section class="metric-box mmx-box">',
            f'<div class="box-head"><span>MMx {info_icon("mmx")}</span><b>{esc(mmx_mix_display(row))}</b></div>',
            metric_row("ThinQ P | MarQ P", esc(f"{as_pct(thinq_prob_value, 1)} | {as_pct(marq_prob_value, 1)}")),
            metric_row("ThinQ In | MarQ In", esc(f"{pp_display(thinq_input, 1)} | {pp_display(marq_input, 1)}"), sign_class(thinq_input)),
            metric_row("CorQ F | MarQ Δ", esc(f"{as_pct(final_prob, 1)} | {pp_display(delta, 1)}"), sign_class(delta)),
            metric_row("Value Δ", pp_display(value_delta, 1), _value_metric_class(value_delta)),
            metric_row("EV", signed_market_pct(ev_pct, 1), _value_metric_class(ev_pct)),
            metric_row("Price", esc(price_text), "bad" if "No Value" in price_text else "good" if "Value+" in price_text else "neutral"),
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
        metric_row("Aces P | O | T", esc(triplet_market_display(row, "aces"))),
        metric_row("DF P | O | T", esc(triplet_market_display(row, "df"))),
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
        metric_row("Aces P | O | T", esc(triplet_market_display(row, "aces"))),
        metric_row("DF P | O | T", esc(triplet_market_display(row, "df"))),
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


def render_marq_box(row: Dict[str, Any]) -> str:
    rows = [
        '<section class="metric-box small-box marq-box">',
        f'<div class="box-head"><span>MarQ {info_icon("marq")}</span><b></b></div>',
        metric_row("Pick Marq", market_pct(_first_data_value(row, "marq_crowd_pick_pct", "pick_marq", "marq_pick_pct"))),
        metric_row("Opp Marq", market_pct(_first_data_value(row, "marq_crowd_opponent_pct", "opponent_marq", "opp_marq", "marq_opponent_pct"))),
        metric_row_info("MarQ Edge", signed_market_pct(_first_data_value(row, "marq_edge_pct", "marq_edge", "edge_pct")), "marq_edge"),
        metric_row_info("Range | Move", esc(marq_range_move_display(row)), "marq_move"),
    ]
    clv_value = marq_clv_display(row)
    rows.append(metric_row("CLV", esc(clv_value), sign_class(row.get("marq_internal_clv_pp") or row.get("marq_clv_pct"))))
    rows.append(metric_row("MarQ Final", esc(final_marq_display(row))))
    rows.append('</section>')
    return "\n".join(rows)

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

.thinq-box .box-head b{font-size:13px!important;line-height:1.15!important;color:var(--green)!important;white-space:nowrap!important}.thinq-box .box-head{gap:10px!important}.mmx-box .metric-row b{white-space:nowrap}
/* Compact pick panel final override: reduce free space in player boxes, keep top tags unchanged, put match meta on one row. */
.pick-main.compact-v3{padding:10px!important;gap:7px!important;min-height:0!important}.compact-v3 .compact-player{min-height:0!important;padding:8px 10px!important;justify-content:center!important}.compact-v3 .pick-side{min-height:0!important;padding-top:8px!important;padding-bottom:8px!important}.compact-player.no-label{padding-top:8px!important;padding-bottom:8px!important}.compact-label{margin-bottom:5px!important;font-size:9px!important;line-height:1!important}.compact-name-row{align-items:center!important;gap:7px!important}.compact-name{display:flex!important;align-items:center!important;gap:6px!important;min-width:0!important;font-size:13px!important;line-height:1.12!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}.compact-name .compact-odds.inline{flex:0 0 auto!important;margin-left:2px!important;transform:none!important;padding:2px 7px!important;font-size:10px!important;line-height:1.1!important}.compact-rank{font-size:11px!important;line-height:1!important;flex:0 0 auto!important}.compact-vs{height:14px!important;min-height:14px!important;margin:-1px 0!important;font-size:9px!important;line-height:1!important}.compact-match{padding:7px 9px!important;border-radius:12px!important}.compact-match-row{display:flex!important;align-items:center!important;gap:8px!important;min-width:0!important;white-space:nowrap!important;overflow:hidden!important}.compact-time{font-size:12px!important;line-height:1!important;flex:0 0 auto!important}.compact-meta{font-size:10px!important;line-height:1.15!important;margin-top:0!important;min-width:0!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}.compact-tags.bottom-notes{padding-top:4px!important;margin-top:auto!important}@media(max-width:760px){.compact-name{font-size:13px!important}.compact-match-row{gap:6px!important}.compact-meta{font-size:10px!important}}

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
RESULT_LAST_3_DAYS_LABEL = "Last 3 days"
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

def get_existing_public_tags(row: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    for key in ("tags", "audit_tags", "audit_filter_tags", "data_notes", "notes", "flags"):
        value = row.get(key)
        if isinstance(value, list):
            tags.extend(str(x) for x in value if x)
        elif isinstance(value, str) and value.strip():
            tags.append(value.strip())
    return tags



def price_value_filter_tags_for_row(row: Dict[str, Any]) -> List[str]:
    """Non-selective price/value tags for Audit and Results filtering."""
    tags: List[str] = []
    odds = pick_odds(row)
    delta = _value_delta_pp(row)
    if odds is not None and odds < 1.50:
        tags.append("Short Price")
    if delta is not None:
        if delta >= 3.0:
            tags.append("Value+")
        elif delta < -2.0:
            tags.append("No Value")
        else:
            tags.append("Value Neutral")
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
    tags.extend(price_value_filter_tags_for_row(row))
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
    if label in {"Short Price", "No Value", "Value Neutral"}:
        return "tag-chip audit-pill audit-pill-signal"
    if label == "Value+":
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
        cards = '<div class="grid">' + "\n".join(render_card(r, i + 1, page=page) for i, r in enumerate(rows)) + '</div>'
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
            AUDIT_SAFE_BET_LABEL: 3,
            AUDIT_H2H_TOP10_LABEL: 4,
        }.get(label, 10)
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
    for key in ("date", "snapshot_date", "run_date", "match_date", "start_time_utc", "match_time_utc", "start_time", "match_time"):
        value = row.get(key)
        if not value:
            continue
        raw = str(value).strip()
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw[:10]):
                return datetime.fromisoformat(raw[:10]).replace(tzinfo=timezone.utc)
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def result_date_filter_tags(row: Dict[str, Any]) -> List[str]:
    dt = result_row_date_value(row)
    if dt is None:
        return []

    today = datetime.now(timezone.utc).date()
    d = dt.date()
    tags: List[str] = []

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
        ("Date", [RESULT_LAST_3_DAYS_LABEL, RESULT_LAST_7_DAYS_LABEL, RESULT_LAST_MONTH_LABEL, RESULT_THIS_YEAR_LABEL]),
        ("Signals", [AUDIT_CORQ_TOP20_LABEL, AUDIT_TIME_ODDS_LABEL, AUDIT_CLOQ_LABEL, AUDIT_SAFE_BET_LABEL, AUDIT_H2H_TOP10_LABEL]),
        ("Value", ["Value+", "No Value", "Value Neutral", "Short Price"]),
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


def main() -> None:
    render_all()


if __name__ == "__main__":
    main()
