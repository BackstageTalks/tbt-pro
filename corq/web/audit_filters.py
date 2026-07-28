# corq/web/audit_filters.py

from datetime import datetime, timezone, timedelta
from html import escape
from urllib.parse import urlencode


def parse_float_safe(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip().replace(',', '.')
        return float(value)
    except Exception:
        return default


def parse_int_safe(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip()
            if value.startswith('#'):
                value = value[1:]
        return int(float(value))
    except Exception:
        return default


def clean_text(value):
    if value is None:
        return ''
    return ' '.join(str(value).strip().split())


def get_nested_value(data: dict, paths: list, default=None):
    if not isinstance(data, dict):
        return default
    for path in paths:
        current = data
        ok = True
        for part in path:
            if isinstance(current, dict) and part in current:
                current = current.get(part)
            else:
                ok = False
                break
        if ok and current is not None:
            return current
    return default


def get_pick_odds(match: dict):
    return get_nested_value(match, [
        ['pick', 'odds'], ['pick', 'price'], ['selection', 'odds'], ['selection', 'price'],
        ['pick_odds'], ['odds'], ['price'], ['market', 'pick_odds'], ['market', 'odds'],
        ['market', 'price'], ['book', 'odds'],
    ])


def get_match_time_utc(match: dict):
    return get_nested_value(match, [
        ['match_time_utc'], ['start_time_utc'], ['commence_time'], ['start_time'], ['match_time'],
        ['market', 'commence_time'], ['market', 'start_time_utc'], ['event', 'commence_time'],
        ['event', 'start_time_utc'],
    ])


def get_corq_rank(match: dict):
    return get_nested_value(match, [
        ['corq', 'rank'], ['corq', 'corq_rank'], ['corq_rank'], ['rank'], ['pick_rank'],
        ['top_rank'], ['meta', 'corq_rank'], ['audit', 'corq_rank'],
    ])


def get_pick_l10(match: dict):
    return get_nested_value(match, [
        ['pick', 'l10'], ['pick', 'last10'], ['pick', 'last_10'], ['pick_l10'], ['pick_last10'],
        ['pick_last_10'], ['form', 'pick_l10'], ['form', 'pick_last10'], ['thinq', 'pick_l10'],
        ['thinq', 'pick_last10'], ['audit', 'pick_l10'],
    ])


def get_opp_l10(match: dict):
    return get_nested_value(match, [
        ['opponent', 'l10'], ['opponent', 'last10'], ['opponent', 'last_10'], ['opp_l10'],
        ['opp_last10'], ['opp_last_10'], ['form', 'opp_l10'], ['form', 'opp_last10'],
        ['thinq', 'opp_l10'], ['thinq', 'opp_last10'], ['audit', 'opp_l10'],
    ])


def get_existing_tags(match: dict):
    tags = []
    for key in ['tags', 'audit_tags', 'audit_filter_tags', 'data_notes', 'notes', 'flags']:
        value = match.get(key) if isinstance(match, dict) else None
        if isinstance(value, list):
            tags.extend(value)
        elif isinstance(value, str):
            tags.append(value)
    return [clean_text(tag) for tag in tags if clean_text(tag)]


def parse_datetime_utc(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            raw = value.strip()
            if raw.endswith('Z'):
                raw = raw[:-1] + '+00:00'
            dt = datetime.fromisoformat(raw)
        except Exception:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_match_within_next_hours(match_time_utc, hours=2, now_utc=None):
    match_dt = parse_datetime_utc(match_time_utc)
    if match_dt is None:
        return False
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    return now_utc <= match_dt <= now_utc + timedelta(hours=hours)


def get_l10_record_from_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if '|' in raw:
            raw = raw.split('|')[-1].strip()
        if '-' not in raw:
            return None
        left, right = raw.split('-', 1)
        wins = parse_int_safe(left.strip())
        losses = parse_int_safe(right.strip())
        if wins is None or losses is None:
            return None
        return wins, losses
    if isinstance(value, dict):
        wins = value.get('wins')
        losses = value.get('losses')
        if wins is None:
            wins = value.get('w')
        if losses is None:
            losses = value.get('l')
        wins = parse_int_safe(wins)
        losses = parse_int_safe(losses)
        if wins is None or losses is None:
            return None
        return wins, losses
    if isinstance(value, (list, tuple)):
        if len(value) < 2:
            return None
        wins = parse_int_safe(value[0])
        losses = parse_int_safe(value[1])
        if wins is None or losses is None:
            return None
        return wins, losses
    return None


def is_pick_strong_l10(record) -> bool:
    parsed = get_l10_record_from_value(record)
    if parsed is None:
        return False
    wins, losses = parsed
    return wins >= 7 and losses <= 3


def is_opp_weak_l10(record) -> bool:
    parsed = get_l10_record_from_value(record)
    if parsed is None:
        return False
    wins, losses = parsed
    return wins <= 3 and losses >= 7


def existing_pick_strong_tag(match: dict) -> bool:
    text = ' '.join(get_existing_tags(match)).lower().replace('last 10', 'l10')
    return 'pick strong' in text and 'l10' in text


def existing_opp_weak_tag(match: dict) -> bool:
    text = ' '.join(get_existing_tags(match)).lower().replace('last 10', 'l10')
    return 'opp weak' in text and 'l10' in text


def has_corq_top20_signal(match: dict) -> bool:
    rank = parse_int_safe(get_corq_rank(match))
    return rank is not None and rank <= 20


def has_up_to_2h_o15_signal(match: dict) -> bool:
    odds = parse_float_safe(get_pick_odds(match))
    if odds is None:
        return False
    return odds > 1.50 and is_match_within_next_hours(get_match_time_utc(match), hours=2)


def has_safe_bet_signal(match: dict) -> bool:
    pick_ok = is_pick_strong_l10(get_pick_l10(match)) or existing_pick_strong_tag(match)
    opp_ok = is_opp_weak_l10(get_opp_l10(match)) or existing_opp_weak_tag(match)
    return pick_ok and opp_ok


def has_no_previous_h2h_signal(match: dict) -> bool:
    text = ' '.join(get_existing_tags(match)).lower()
    if 'no previous h2h' in text:
        return True
    h2h = get_nested_value(match, [['h2h'], ['thinq', 'h2h'], ['audit', 'h2h']])
    if isinstance(h2h, dict):
        total = parse_int_safe(h2h.get('total'))
        matches = parse_int_safe(h2h.get('matches'))
        return total == 0 or matches == 0
    return False


def has_recent_form_pending_signal(match: dict) -> bool:
    text = ' '.join(get_existing_tags(match)).lower()
    return 'recent form pending' in text or 'recent_form_pending' in text


AUDIT_FILTER_DEFINITIONS = [
    {'key': 'no_previous_h2h', 'label': 'No previous H2H matches', 'css_class': 'audit-pill audit-pill-note', 'predicate': has_no_previous_h2h_signal},
    {'key': 'recent_form_pending', 'label': 'Recent form pending', 'css_class': 'audit-pill audit-pill-note', 'predicate': has_recent_form_pending_signal},
    {'key': 'corq_top20', 'label': 'CorQ Top20', 'css_class': 'audit-pill audit-pill-corq', 'predicate': has_corq_top20_signal},
    {'key': 'up_to_2h_o15', 'label': 'Up to 2H | O>1.5', 'css_class': 'audit-pill audit-pill-signal', 'predicate': has_up_to_2h_o15_signal},
    {'key': 'safe_bet_signal', 'label': 'Safe Bet Signal', 'css_class': 'audit-pill audit-pill-safe', 'predicate': has_safe_bet_signal},
]


def build_audit_filter_summary(matches: list) -> list:
    summary = []
    for filter_def in AUDIT_FILTER_DEFINITIONS:
        predicate = filter_def['predicate']
        count = 0
        for match in matches or []:
            if not isinstance(match, dict):
                continue
            try:
                if predicate(match):
                    count += 1
            except Exception:
                continue
        if count > 0:
            summary.append({'key': filter_def['key'], 'label': filter_def['label'], 'count': count, 'css_class': filter_def['css_class']})
    return summary


def filter_matches_by_audit_filter(matches: list, filter_key: str) -> list:
    if not filter_key:
        return matches or []
    selected = next((x for x in AUDIT_FILTER_DEFINITIONS if x['key'] == filter_key), None)
    if selected is None:
        return matches or []
    predicate = selected['predicate']
    out = []
    for match in matches or []:
        if not isinstance(match, dict):
            continue
        try:
            if predicate(match):
                out.append(match)
        except Exception:
            continue
    return out


def enrich_matches_with_audit_filter_tags(matches: list) -> list:
    enriched = []
    for match in matches or []:
        if not isinstance(match, dict):
            continue
        filter_tags = []
        for filter_def in AUDIT_FILTER_DEFINITIONS:
            try:
                if filter_def['predicate'](match):
                    filter_tags.append(filter_def['label'])
            except Exception:
                continue
        match['audit_filter_tags'] = filter_tags
        enriched.append(match)
    return enriched


def render_audit_filter_summary(summary: list, active_filter: str = '', base_url: str = '?') -> str:
    if not summary:
        return ''
    pills_html = []
    for item in summary:
        key = str(item.get('key', ''))
        label = str(item.get('label', ''))
        count = str(item.get('count', 0))
        css_class = str(item.get('css_class', 'audit-pill'))
        active_class = ' is-active' if key == active_filter else ''
        href = base_url
        separator = '&' if '?' in href and not href.endswith('?') else ''
        href = f"{href}{separator}{urlencode({'audit_filter': key})}"
        pills_html.append(
            f'<a class="{escape(css_class)}{active_class}" href="{escape(href)}">'
            f'<span class="audit-pill-count">{escape(count)}</span>'
            f'<span class="audit-pill-label">{escape(label)}</span>'
            f'</a>'
        )
    clear_html = ''
    if active_filter:
        clear_html = '<a class="audit-pill audit-pill-clear" href="?"><span class="audit-pill-label">Clear filter</span></a>'
    return (
        '<section class="data-notes-summary corq-audit-summary">'
        '<div class="data-notes-title">DATA NOTES SUMMARY</div>'
        '<div class="data-notes-pills">'
        + ''.join(pills_html)
        + clear_html
        + '</div></section>'
    )
