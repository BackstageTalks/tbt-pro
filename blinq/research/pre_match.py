"""Offline, point-in-time Sackmann-compatible tennis feature builder.

Research-only: no CDB writes, no production prediction side effects.
Sackmann tourney_date is tournament START, not match start.
Conservatively embargo an entire tournament for 21 calendar days.
"""
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, date as Date
from math import pow
from typing import Any, Iterable

SURFACES = {"hard", "clay", "grass", "carpet"}
REQUIRED = ("tourney_date", "tourney_id", "winner_id", "loser_id", "winner_name", "loser_name", "surface", "score")
STAT_FIELDS = ("svpt", "1stIn", "1stWon", "2ndWon", "bpSaved", "bpFaced")
RETIREMENT = ("RET", "W/O", "WALKOVER", "DEF", "ABD", "ABANDON", "CANCEL")


def _int(v: Any) -> int | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        x = float(v)
        if not x.is_integer() or x < 0:
            return None
        return int(x)
    except (ValueError, TypeError, OverflowError):
        return None


def _float(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x == x and abs(x) < 1e12 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _date(raw: Any) -> str | None:
    s = str(raw or "").strip()
    try:
        return datetime.strptime(s, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _get_stats(row: dict, prefix: str) -> dict | None:
    values = {k: _int(row.get(f"{prefix}_{k}")) for k in STAT_FIELDS}
    if any(v is None for v in values.values()):
        return None
    sv, first, firstwon, secondwon, saved, faced = (values[k] for k in STAT_FIELDS)
    if not (0 < sv and 0 <= first <= sv and firstwon <= first and secondwon <= sv - first and saved <= faced):
        return None
    won = firstwon + secondwon
    if won > sv:
        return None
    return {"total": sv, "won": won, "first_in": first, "first_won": firstwon, "second_won": secondwon,
            "bp_saved": saved, "bp_faced": faced}


@dataclass
class Observation:
    date: str
    surface: str
    won: int
    spw: float | None
    rpw: float | None
    adj_spw: float | None
    first_serve_won: float | None
    second_serve_won: float | None
    bp_saved_rate: float | None
    bp_converted_rate: float | None
    age: float | None
    svpt: int | None = None
    rvpt: int | None = None
    adj_rpw: float | None = None


class PlayerState:
    def __init__(self):
        self.elo = 1500.0
        self.matches = 0
        self.surface_elo = {key: 1500.0 for key in SURFACES}
        self.surface_matches = {key: 0 for key in SURFACES}
        self.history: deque[Observation] = deque(maxlen=120)

    def summarize(self, surface: str) -> dict[str, float | int | None]:
        recent = list(self.history)[-20:]
        same = [x for x in self.history if x.surface == surface][-20:]
        def mean(rows: list[Observation], key: str) -> float | None:
            xs = [getattr(x, key) for x in rows]
            xs = [x for x in xs if x is not None]
            return round(sum(xs) / len(xs), 7) if xs else None
        surface_n = self.surface_matches[surface]
        # Bayesian-style shrinkage of sparse surface evidence to player's
        # own overall prior. Hyperparameters fixed before any held-out tests.
        def shrink(specific: float | None, overall: float | None, n: int, pseudo: int = 8) -> float | None:
            if overall is None:
                return None
            if specific is None:
                return overall
            return (n * specific + pseudo * overall) / (n + pseudo)
        smooth_elo = (self.elo + surface_n/(surface_n+12) *
                      (self.surface_elo[surface] - self.elo))
        def point_posterior(rate: str, denominator: str, prior: float, pseudo_points: int = 500) -> float | None:
            observations = [(getattr(x, rate), getattr(x, denominator)) for x in recent]
            valid = [(value, pts) for value, pts in observations if value is not None and pts is not None and pts > 0]
            if not valid:
                return None
            return (sum(value*pts for value,pts in valid) + pseudo_points*prior) / (sum(pts for _,pts in valid) + pseudo_points)
        return {"matches": self.matches, "elo": round(self.elo, 6) if self.matches else None,
                "bayes_serve20": point_posterior("spw", "svpt", .62),
                "bayes_return20": point_posterior("rpw", "rvpt", .38),
                "adj_serve_points20": point_posterior("adj_spw", "svpt", .62),
                "adj_return_points20": point_posterior("adj_rpw", "rvpt", .38),
                "surface_elo_shrunk": round(smooth_elo, 6) if self.matches else None,
                "shrunk_surface_form": shrink(mean(same, "won"),mean(recent, "won"),len(same)),
                "shrunk_surface_serve": shrink(mean(same, "spw"),mean(recent, "spw"),len(same)),
                "shrunk_surface_return": shrink(mean(same, "rpw"),mean(recent, "rpw"),len(same)),
                "form20": mean(recent, "won"), "form_surface20": mean(same, "won"),
                "serve20": mean(recent, "spw"), "return20": mean(recent, "rpw"),
                "adjusted_serve20": mean(recent, "adj_spw"),
                "first_serve_won20": mean(recent, "first_serve_won"),
                "second_serve_won20": mean(recent, "second_serve_won"),
                "bp_saved20": mean(recent, "bp_saved_rate"),
                "bp_converted20": mean(recent, "bp_converted_rate"),
                "surface_serve20": mean(same, "spw"), "surface_return20": mean(same, "rpw"),
                "surface_adjusted_serve20": mean(same, "adj_spw"),
                "form_n": len(recent), "surface_n": len(same)}


def _delta(a: dict, b: dict, key: str) -> float | None:
    x, y = a[key], b[key]
    return round(x-y, 7) if x is not None and y is not None else None


def build_features(rows: Iterable[dict], tour: str) -> tuple[list[dict], list[dict]]:
    """Generate research features and quarantined rows, never modify CDB.

    Only rows with provider player IDs are linked. Names are non-identity display.
    Date-strict batches and 21-day release embargo protect against tournament-start
    timestamps being mistaken for exact match timestamps. An unusually prolonged
    competition requires exact match times for a stronger guarantee.
    """
    tour = str(tour).strip().upper()
    if tour not in {"ATP", "WTA"}:
        raise ValueError("Tour must be ATP or WTA; mixed files require separate runs")
    matches, rejected, seen = [], [], set()
    for index, raw in enumerate(rows, start=2):
        row = dict(raw)
        missing = [field for field in REQUIRED if not str(row.get(field) or "").strip()]
        date = _date(row.get("tourney_date"))
        surf = str(row.get("surface") or "").strip().lower()
        score = str(row.get("score") or "").upper()
        if missing or not date or surf not in SURFACES or any(x in score for x in RETIREMENT):
            rejected.append({"line": index, "reason": "INCOMPLETE_UNDATED_SURFACE_OR_RETIRED", "missing": missing})
            continue
        wid, lid = str(row["winner_id"]).strip(), str(row["loser_id"]).strip()
        if wid == lid:
            rejected.append({"line": index, "reason": "SAME_PLAYER_ID"})
            continue
        match_num = str(row.get("match_num") or "").strip()
        if match_num:
            event_match_id = match_num
        else:
            round_name = str(row.get("round") or "").strip().upper()
            if not round_name:
                rejected.append({"line": index, "reason": "MISSING_MATCH_NUM_AND_ROUND"})
                continue
            # Provider match number is absent: deterministic within-tournament
            # identity using two verified IDs and round, never player names.
            # Ambiguous repeated pairs collapse into DUPLICATE_MATCH_ID quarantine.
            event_match_id = f"AUTO:{round_name}:{min(wid,lid)}:{max(wid,lid)}"
        mid = (tour, str(row["tourney_id"]), event_match_id)
        if mid in seen:
            rejected.append({"line": index, "reason": "DUPLICATE_MATCH_ID"})
            continue
        seen.add(mid)
        stats_w, stats_l = _get_stats(row, "w"), _get_stats(row, "l")
        if stats_w is None or stats_l is None:
            stats_w = stats_l = None
        matches.append((date, surf, mid, wid, lid, row, stats_w, stats_l))
    matches.sort(key=lambda x: (x[0], x[2]))
    players: dict[str, PlayerState] = defaultdict(PlayerState)
    output = []
    pending: deque[tuple[Date, list[tuple]]] = deque()

    def commit(pre: list[tuple]) -> None:
        """Only mature tournament batches may update the history snapshot."""
        for date, surf, wid, lid, row, ws, ls, pw, pl in pre:
            ew, el = players[wid].elo, players[lid].elo
            expected = 1 / (1 + pow(10, (el - ew) / 400))
            k = 24.0
            players[wid].elo += k * (1 - expected)
            players[lid].elo -= k * (1 - expected)
            sew = players[wid].surface_elo[surf]
            sel = players[lid].surface_elo[surf]
            se = 1 / (1 + pow(10, (sel-sew)/400))
            players[wid].surface_elo[surf] += k*(1-se)
            players[lid].surface_elo[surf] -= k*(1-se)
            players[wid].surface_matches[surf] += 1
            players[lid].surface_matches[surf] += 1
            players[wid].matches += 1
            players[lid].matches += 1
            for pid, won, st, opp_st, old_opp, agekey in (
                (wid, 1, ws, ls, pl, "winner_age"), (lid, 0, ls, ws, pw, "loser_age")
            ):
                spw = st["won"]/st["total"] if st else None
                rpw = (opp_st["total"]-opp_st["won"])/opp_st["total"] if opp_st else None
                opp_return = old_opp["return20"]
                # Opponent return ability was measured before this old match.
                # 0.38 is a research hyperparameter, not a factual league rate.
                adj_spw = min(1.0,max(0.0,spw + opp_return - 0.38)) if spw is not None and opp_return is not None else None
                opp_serve = old_opp["serve20"]
                adj_rpw = min(1.0,max(0.0,rpw + opp_serve - 0.62)) if rpw is not None and opp_serve is not None else None
                first_rate = st["first_won"]/st["first_in"] if st and st["first_in"] else None
                second_n = st["total"]-st["first_in"] if st else 0
                second_rate = st["second_won"]/second_n if second_n else None
                bp_saved = st["bp_saved"]/st["bp_faced"] if st and st["bp_faced"] else None
                bp_converted = (opp_st["bp_faced"]-opp_st["bp_saved"])/opp_st["bp_faced"] if opp_st and opp_st["bp_faced"] else None
                players[pid].history.append(Observation(date,surf,won,spw,rpw,adj_spw,first_rate,second_rate,bp_saved,bp_converted,_float(row.get(agekey)),
                    svpt=st["total"] if st else None, rvpt=opp_st["total"] if opp_st else None, adj_rpw=adj_rpw))

    i = 0
    while i < len(matches):
        current_date = Date.fromisoformat(matches[i][0])
        while pending and pending[0][0] < current_date:
            _, mature = pending.popleft()
            commit(mature)
        j = i
        while j < len(matches) and matches[j][0] == matches[i][0]:
            j += 1
        current = matches[i:j]
        pre: list[tuple] = []
        for date, surf, mid, wid, lid, row, ws, ls in current:
            p1, p2 = sorted((wid, lid))
            s1, s2 = players[p1].summarize(surf), players[p2].summarize(surf)
            winner_is_p1 = int(p1 == wid)
            ranking = {wid: _float(row.get("winner_rank")), lid: _float(row.get("loser_rank"))}
            ages = {wid: _float(row.get("winner_age")), lid: _float(row.get("loser_age"))}
            def age30(pid: str) -> float | None:
                a = ages[pid]
                return abs(a - 30.0) if a is not None and 14 <= a <= 55 else None
            def age_interval(pid: str) -> float | None:
                a = ages[pid]
                return max(28.0 - a, 0.0, a - 32.0) if a is not None and 14 <= a <= 55 else None
            out = {"date": date, "match_id": "|".join(mid), "tour": tour, "surface": surf,
                   "player1_id": p1, "player2_id": p2, "y": winner_is_p1,
                   "feature_asof_before": date,
                   "p1_history_n": s1["matches"], "p2_history_n": s2["matches"],
                   "p1_surface_n": s1["surface_n"], "p2_surface_n": s2["surface_n"],
                   "rank_diff": (ranking[p2] - ranking[p1]) if all(ranking[p] is not None for p in (p1,p2)) else None,
                   "age30_diff": (age30(p2)-age30(p1)) if age30(p1) is not None and age30(p2) is not None else None,
                   "age_interval_diff": (age_interval(p2)-age_interval(p1)) if age_interval(p1) is not None and age_interval(p2) is not None else None}
            for name in ("elo", "bayes_serve20", "bayes_return20",
                         "adj_serve_points20", "adj_return_points20",
                         "surface_elo_shrunk", "shrunk_surface_form",
                         "shrunk_surface_serve", "shrunk_surface_return",
                         "form20", "form_surface20", "serve20", "return20", "adjusted_serve20",
                         "surface_serve20", "surface_return20", "surface_adjusted_serve20",
                         "first_serve_won20", "second_serve_won20", "bp_saved20", "bp_converted20"):
                out[f"{name}_diff"] = _delta(s1, s2, name)
            output.append(out)
            pre.append((date, surf, wid, lid, row, ws, ls,
                        players[wid].summarize(surf), players[lid].summarize(surf)))
        pending.append((Date.fromisoformat(current[0][0]) + timedelta(days=21), pre))
        i = j
    return output, rejected
