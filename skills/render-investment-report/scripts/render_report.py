#!/usr/bin/env python3
"""Deterministic HTML report renderer.

Reads JSON product files from a run directory, fills the report template
with data, and writes investment-report.html. All external strings are
html.escape()'d to prevent XSS.
"""

import html
import json
import os
import re
import sys


TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'assets',
    'report-template.html',
)


def _esc(value):
    """html.escape a value, returning empty string for None."""
    if value is None:
        return ''
    return html.escape(str(value), quote=False)


def _maybe_change(val):
    """Render a change_percent value with colour class, or '' if missing."""
    if val is None:
        return ''
    v = float(val)
    cls = 'change-up' if v >= 0 else 'change-down'
    sign = '+' if v >= 0 else ''
    return f'<span class="card-change {cls}">({sign}{v:.2f}%)</span>'


def _market_badge(market):
    """Return a market badge HTML snippet, or empty string."""
    badges = {
        'a': '<span class="badge-market-a">A</span>',
        'us': '<span class="badge-market-us">US</span>',
        'hk': '<span class="badge-market-hk">HK</span>',
    }
    return badges.get(market, '')


def load_json(path):
    """Load a JSON file, returning None on failure."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def render_market_overview(data):
    """Render market overview sections from market-overview.json data."""
    if data is None:
        # Fallback: try loading from the envelope
        return '', '', ''

    # If data has an envelope (schema_version, etc.), extract .data
    inner = data.get('data', data) if isinstance(data, dict) else data

    indices_html = ''
    hot_stocks_html = ''
    sectors_html = ''

    # Indices
    indices = inner.get('indices', []) if isinstance(inner, dict) else []
    if indices:
        items = []
        for idx in indices:
            name = _esc(idx.get('name', ''))
            price = _esc(idx.get('price', ''))
            change = idx.get('change_percent')
            items.append(
                f'<div class="card">'
                f'<div class="card-title">{name}</div>'
                f'<div class="card-value">{price} {_maybe_change(change)}</div>'
                f'</div>'
            )
        indices_html = (
            '<div class="card-title" style="margin-bottom:6px">指数</div>'
            f'<div class="grid">{"".join(items)}</div>'
        )

    # Hot stocks
    hot_list = inner.get('hot_stocks', []) if isinstance(inner, dict) else []
    if hot_list:
        rows = []
        for stk in hot_list:
            name = _esc(stk.get('name', ''))
            code = _esc(stk.get('code', ''))
            rank = stk.get('rank', '')
            change = stk.get('change_percent')
            heat = stk.get('heat_score', '')
            badge = _market_badge(stk.get('market', ''))
            rows.append(
                f'<tr><td>#{_esc(str(rank))}</td>'
                f'<td>{name} {badge}</td>'
                f'<td>{_esc(code)}</td>'
                f'<td>{_maybe_change(change)}</td>'
                f'<td>{_esc(str(heat))}</td></tr>'
            )
        hot_stocks_html = (
            '<div class="card-title" style="margin-bottom:6px">热门股票</div>'
            '<table><tr><th>#</th><th>名称</th><th>代码</th><th>涨跌幅</th><th>热度</th></tr>'
            f'{"".join(rows)}</table>'
        )

    # Sectors
    sector_list = inner.get('sectors', []) if isinstance(inner, dict) else []
    if sector_list:
        rows = []
        for sec in sector_list:
            name = _esc(sec.get('name', ''))
            code = _esc(sec.get('code', ''))
            change = sec.get('change_percent')
            inflow = sec.get('main_net_inflow')
            lead = sec.get('lead_stock', '')
            rows.append(
                f'<tr><td>{name}</td>'
                f'<td>{_esc(code)}</td>'
                f'<td>{_maybe_change(change)}</td>'
                f'<td>{_esc(str(inflow)) if inflow is not None else "-"}</td>'
                f'<td>{_esc(lead)}</td></tr>'
            )
        sectors_html = (
            '<div class="card-title" style="margin-bottom:6px">板块</div>'
            '<table><tr><th>板块</th><th>代码</th><th>涨跌幅</th><th>主力净流入(亿)</th><th>领涨</th></tr>'
            f'{"".join(rows)}</table>'
        )

    return indices_html, hot_stocks_html, sectors_html


def render_signals(data):
    """Render signal analysis sections from investment-signals.json data."""
    if data is None:
        return '', '', ''

    inner = data.get('data', data) if isinstance(data, dict) else data
    dimensions_html = ''
    confidence_html = ''
    invalidate_html = ''

    # Dimensions
    dimensions = inner.get('dimensions', []) if isinstance(inner, dict) else []
    if dimensions:
        blocks = []
        for dim in dimensions:
            name = _esc(dim.get('name', ''))
            conclusion = _esc(dim.get('conclusion', ''))
            supporting = dim.get('supporting_evidence', [])
            opposing = dim.get('opposing_evidence', [])
            missing = dim.get('missing_data', [])

            parts = [f'<div class="dimension-name">{name}</div>']

            if conclusion:
                parts.append(f'<div style="color:#d2d6dc;margin-bottom:6px">结论：{conclusion}</div>')

            if supporting:
                parts.append('<div class="evidence-block">')
                parts.append('<div class="evidence-label">支撑证据</div>')
                for ev in supporting:
                    claim = _esc(ev.get('claim', '')) if isinstance(ev, dict) else _esc(str(ev))
                    parts.append(f'<div class="evidence-item">{claim}</div>')
                parts.append('</div>')

            if opposing:
                parts.append('<div class="evidence-block">')
                parts.append('<div class="evidence-label">反对证据</div>')
                for ev in opposing:
                    claim = _esc(ev.get('claim', '')) if isinstance(ev, dict) else _esc(str(ev))
                    parts.append(f'<div class="evidence-item">{claim}</div>')
                parts.append('</div>')

            if missing:
                parts.append('<div class="evidence-block">')
                parts.append('<div class="evidence-label">缺失数据</div>')
                for m in missing:
                    parts.append(f'<span class="tag">{_esc(m)}</span>')
                parts.append('</div>')

            blocks.append(f'<div class="dimension-card">{"".join(parts)}</div>')

        dimensions_html = ''.join(blocks)

    # Confidence
    confidence = inner.get('confidence', '') if isinstance(inner, dict) else ''
    if confidence:
        confidence_html = (
            f'<p><strong>分析置信度：</strong> <span class="advice-{confidence}">{_esc(confidence)}</span></p>'
        )

    # Invalidation conditions
    invalidate = inner.get('失效条件', []) if isinstance(inner, dict) else []
    if invalidate:
        tags = ''.join(f'<span class="tag">{_esc(c)}</span>' for c in invalidate)
        invalidate_html = (
            f'<p><strong>失效条件：</strong></p>'
            f'<div>{tags}</div>'
        )

    return dimensions_html, confidence_html, invalidate_html


def render_scenarios(data):
    """Render scenarios section from investment-scenarios.json data."""
    if data is None:
        return False, ''

    inner = data.get('data', data) if isinstance(data, dict) else data
    scenarios = inner.get('scenarios', []) if isinstance(inner, dict) else []

    if not scenarios:
        return False, ''

    blocks = []
    for sc in scenarios:
        name = _esc(sc.get('name', ''))
        desc = _esc(sc.get('description', ''))
        triggers = sc.get('trigger_conditions', [])
        indicators = sc.get('observation_indicators', [])
        fail_cond = sc.get('失效条件', [])
        risks = sc.get('risks', [])
        price_range = sc.get('price_range', {})
        position = _esc(sc.get('position_suggestion', ''))

        parts = [f'<div class="scenario-title">{name}</div>']
        if desc:
            parts.append(f'<p style="font-size:0.9em;color:#8b949e;margin-bottom:6px">{desc}</p>')

        if triggers:
            tags = ''.join(f'<span class="tag">{_esc(t)}</span>' for t in triggers)
            parts.append(f'<div>触发条件：{tags}</div>')

        if indicators:
            tags = ''.join(f'<span class="tag">{_esc(i)}</span>' for i in indicators)
            parts.append(f'<div>观测指标：{tags}</div>')

        if fail_cond:
            tags = ''.join(f'<span class="tag">{_esc(c)}</span>' for c in fail_cond)
            parts.append(f'<div>失效条件：{tags}</div>')

        if risks:
            tags = ''.join(f'<span class="tag">{_esc(r)}</span>' for r in risks)
            parts.append(f'<div>风险因素：{tags}</div>')

        if price_range:
            if isinstance(price_range, dict):
                entry = _esc(price_range.get('entry', ''))
                target = _esc(price_range.get('target', ''))
                if entry or target:
                    parts.append(f'<div>价格区间：进场 {entry} | 目标 {target}</div>')
            else:
                parts.append(f'<div>价格区间：{_esc(str(price_range))}</div>')

        if position:
            parts.append(f'<div>仓位建议：{position}</div>')

        blocks.append(f'<div class="scenario-block card">{"".join(parts)}</div>')

    return True, ''.join(blocks)


def build_source_links(run_dir, files_loaded):
    """Build a human-readable source links string."""
    parts = []
    for fname in files_loaded:
        parts.append(fname)
    if not parts:
        return 'N/A'
    return ', '.join(parts)


def render_report(run_dir, template_path=None):
    """Main render function. Reads JSON files and writes investment-report.html.

    Returns the output file path on success, or raises on failure.
    """
    if template_path is None:
        template_path = TEMPLATE_PATH

    if not os.path.isdir(run_dir):
        raise ValueError(f"Run directory not found: {run_dir}")

    # Load template
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
    with open(template_path, encoding='utf-8') as f:
        template = f.read()

    # Load all available JSON product files
    files_to_check = [
        'market-overview.json',
        'investment-signals.json',
        'investment-scenarios.json',
    ]
    loaded = {}
    files_loaded = []
    for fname in files_to_check:
        fpath = os.path.join(run_dir, fname)
        data = load_json(fpath)
        loaded[fname] = data
        if data is not None:
            files_loaded.append(fname)

    # Render sections
    mo = loaded.get('market-overview.json')
    indices_html, hot_stocks_html, sectors_html = render_market_overview(mo)

    sig = loaded.get('investment-signals.json')
    dims_html, conf_html, inval_html = render_signals(sig)

    sc = loaded.get('investment-scenarios.json')
    has_scenarios, scenarios_html = render_scenarios(sc)

    # Source links and generation time
    source_links = build_source_links(run_dir, files_loaded)
    generated_at = ''
    # Try to get a timestamp from any loaded file
    for fname in files_loaded:
        data = loaded[fname]
        if isinstance(data, dict) and 'generated_at' in data:
            generated_at = _esc(data['generated_at'])
            break
    if not generated_at:
        generated_at = 'N/A'

    # Fill template
    replacements = {
        'MARKET_OVERVIEW_INDICES': indices_html,
        'MARKET_OVERVIEW_HOT_STOCKS': hot_stocks_html,
        'MARKET_OVERVIEW_SECTORS': sectors_html,
        'SIGNALS_DIMENSIONS': dims_html,
        'SIGNALS_CONFIDENCE': conf_html,
        'SIGNALS_INVALIDATE_CONDITIONS': inval_html,
        'GENERATED_AT': generated_at,
        'SOURCE_LINKS': source_links,
    }

    if has_scenarios:
        replacements['SCENARIOS_TITLE'] = '<h2>情景分析</h2>'
        replacements['SCENARIOS_CONTENT'] = scenarios_html
    else:
        replacements['SCENARIOS_TITLE'] = '<h2>市场观察摘要</h2>'
        replacements['SCENARIOS_CONTENT'] = '<p class="empty-state">暂无情景分析数据，请参考信号分析部分。</p>'

    # Apply replacements
    result = template
    for key, value in replacements.items():
        result = result.replace('{{' + key + '}}', value)

    # Verify no residual placeholders
    residuals = re.findall(r'\{\{[^}]+\}\}', result)
    if residuals:
        raise RuntimeError(
            f"Residual placeholders found: {residuals}"
        )

    # Write output
    output_path = os.path.join(run_dir, 'investment-report.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: render_report.py <run-directory>", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]
    try:
        output_path = render_report(run_dir)
        print(f"Report written to: {output_path}")
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()