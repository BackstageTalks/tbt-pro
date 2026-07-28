# corq/web/audit_page_integration.py

from corq.web.audit_filters import (
    build_audit_filter_summary,
    enrich_matches_with_audit_filter_tags,
    filter_matches_by_audit_filter,
    render_audit_filter_summary,
)


def prepare_audit_page(matches: list, active_filter: str = ''):
    total_count = len(matches or [])
    enriched_matches = enrich_matches_with_audit_filter_tags(matches or [])
    summary = build_audit_filter_summary(enriched_matches)
    visible_matches = filter_matches_by_audit_filter(enriched_matches, active_filter)
    summary_html = render_audit_filter_summary(summary, active_filter=active_filter, base_url='?')
    return {
        'visible_matches': visible_matches,
        'summary_html': summary_html,
        'total_count': total_count,
        'visible_count': len(visible_matches),
    }


def render_audit_page_shell(matches: list, active_filter: str, render_cards_fn):
    prepared = prepare_audit_page(matches, active_filter=active_filter)
    cards_html = render_cards_fn(prepared['visible_matches'])
    count_html = ''
    if active_filter:
        count_html = (
            f'<div class="audit-filtered-count">'
            f"Showing {prepared['visible_count']} of {prepared['total_count']} matches"
            f'</div>'
        )
    return f'''<div class="corq-audit-page">
    {prepared['summary_html']}
    {count_html}
    {cards_html}
</div>'''
