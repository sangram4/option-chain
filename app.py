from flask import Flask, render_template_string, request, jsonify
from nsepython import nse_optionchain_scrapper
from datetime import datetime

app = Flask(__name__

# Complete List of Major Indices & F&O Stocks
FNO_SYMBOLS = [
    # Indices
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYIT", "NIFTYNEXT50",
    # Major F&O Stocks (A-Z)
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", 
    "ITC", "KOTAKBANK", "LT", "AXISBANK", "HINDUNILVR", "BAJFINANCE", "MARUTI", 
    "SUNPHARMA", "TITAN", "TATAMOTORS", "TATASTEEL", "NTPC", "POWERGRID", 
    "ASIANPAINT", "BAJAJFINSV", "ADANIENT", "ADANIPORTS", "COALINDIA", "GRASIM", 
    "HCLTECH", "TECHM", "WIPRO", "ONGC", "BPCL", "HEROMOTOCO", "EICHERMOT", 
    "DRREDDY", "CIPLA", "BRITANNIA", "NESTLEIND", "TATACONSUM", "SBILIFE", 
    "HDFCLIFE", "BAJAJ-AUTO", "M&M", "HINDALCO", "JSWSTEEL", "DIVISLAB", "APOLLOHOSP"
]
FNO_SYMBOLS = sorted(list(set(FNO_SYMBOLS)))

def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

def safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0

def format_num(num):
    abs_num = abs(num)
    sign = "-" if num < 0 else ""
    if abs_num >= 1_000_000:
        return f"{sign}{abs_num / 1_000_000:.2f}M"
    elif abs_num >= 1_000:
        return f"{sign}{abs_num / 1_000:.1f}K"
    return str(num)

def sort_dates(date_list):
    def parse_dt(d):
        try:
            return datetime.strptime(d, "%d-%b-%Y")
        except ValueError:
            return datetime.max
    return sorted(date_list, key=parse_dt)

def get_highlight_class(pct, side):
    if pct >= 99.9:
        return f"max-{side}"
    elif pct >= 75.0:
        return "second-max"
    elif pct >= 50.0:
        return "third-max"
    return ""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AOC | Complete Option Chain Analyzer</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #eef2f6; margin: 0; padding: 10px; font-size: 12px; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; background: #ffffff; padding: 8px 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 8px; }
        .brand { font-size: 16px; font-weight: bold; color: #1e293b; }
        .brand span { color: #2563eb; }
        .controls select, .controls button, .controls label { font-size: 12px; padding: 4px 8px; border-radius: 4px; }
        .controls select { border: 1px solid #cbd5e1; font-weight: bold; }
        .btn-refresh { background: #2563eb; color: white; border: none; cursor: pointer; font-weight: bold; }
        
        .summary-strip { display: flex; width: 100%; font-weight: bold; color: white; border-radius: 4px; overflow: hidden; margin-bottom: 8px; text-align: center; }
        .sum-ce { flex: 5; background: #b91c1c; padding: 7px; display: flex; justify-content: space-around; }
        .sum-mid { flex: 1.5; background: #1e3a8a; padding: 7px; }
        .sum-pe { flex: 5; background: #15803d; padding: 7px; display: flex; justify-content: space-around; }

        .table-wrap { overflow-x: auto; background: white; border-radius: 5px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
        table { width: 100%; border-collapse: collapse; text-align: right; }
        th, td { border: 1px solid #cbd5e1; padding: 5px 6px; white-space: nowrap; }
        
        th.ce-th { background: #991b1b; color: white; text-align: center; font-size: 11px; }
        th.sp-th { background: #1d4ed8; color: white; text-align: center; font-size: 11px; }
        th.pe-th { background: #166534; color: white; text-align: center; font-size: 11px; }

        .pct-val { display: block; font-size: 11px; font-weight: bold; }
        .raw-val { display: block; font-size: 10px; opacity: 0.85; }

        .max-ce { background-color: #dc2626 !important; color: #ffffff !important; }
        .max-pe { background-color: #16a34a !important; color: #ffffff !important; }
        .second-max { background-color: #fde047 !important; color: #0f172a !important; }
        .third-max { background-color: #fef9c3 !important; color: #0f172a !important; }
        .itm-bg { background-color: #fffbeb; }

        td.strike-col { background-color: #dbeafe; text-align: center; font-weight: bold; color: #1e3a8a; font-size: 13px; }
        .pcr-sub { display: block; font-size: 10px; color: #dc2626; font-weight: normal; }

        tr.spot-divider td { background-color: #b91c1c !important; color: white !important; text-align: center !important; font-weight: bold; padding: 5px; font-size: 12px; letter-spacing: 0.5px; }
        .pos { color: #15803d; }
        .neg { color: #dc2626; }
        .max-ce .pos, .max-ce .neg, .max-pe .pos, .max-pe .neg { color: #ffffff; }
        
        #loading-indicator { font-size: 11px; color: #38bdf8; margin-left: 10px; display: none; }
    </style>
</head>
<body>

    <div class="top-bar">
        <div class="brand">AOC <span>⚡</span> | Option Chain Analyzer <span id="loading-indicator">Updating...</span></div>
        <div class="controls">
            <div style="display:inline-flex; align-items:center; gap:8px;">
                <label>Symbol:</label>
                <select id="symbol-select" onchange="reloadPage()">
                    {% for sym in symbols %}
                        <option value="{{ sym }}" {% if sym == selected_symbol %}selected{% endif %}>{{ sym }}</option>
                    {% endfor %}
                </select>

                <label>Expiry:</label>
                <select id="expiry-select" onchange="reloadPage()">
                    {% for exp in expiries %}
                        <option value="{{ exp }}" {% if exp == selected_expiry %}selected{% endif %}>{{ exp }}</option>
                    {% endfor %}
                </select>
                <button onclick="fetchData()" class="btn-refresh">Refresh Now</button>
            </div>
        </div>
    </div>

    <!-- Summary Strip -->
    <div class="summary-strip" id="summary-strip">
        {{ summary_html | safe }}
    </div>

    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th class="ce-th">IV / Delta</th>
                    <th class="ce-th">OI Chg</th>
                    <th class="ce-th">OI</th>
                    <th class="ce-th">Volume</th>
                    <th class="ce-th">LTP / Chg</th>
                    <th class="ce-th">Rev.</th>
                    <th class="sp-th">SP / PCR</th>
                    <th class="pe-th">Rev.</th>
                    <th class="pe-th">LTP / Chg</th>
                    <th class="pe-th">Volume</th>
                    <th class="pe-th">OI</th>
                    <th class="pe-th">OI Chg</th>
                    <th class="pe-th">IV / Delta</th>
                </tr>
            </thead>
            <tbody id="table-body">
                {{ table_html | safe }}
            </tbody>
        </table>
    </div>

    <script>
        function reloadPage() {
            const symbol = document.getElementById('symbol-select').value;
            const expiry = document.getElementById('expiry-select').value;
            window.location.href = `/?symbol=${symbol}&expiry=${expiry}`;
        }

        function fetchData() {
            const symbol = document.getElementById('symbol-select').value;
            const expiry = document.getElementById('expiry-select').value;
            document.getElementById('loading-indicator').style.display = 'inline';

            fetch(`/api/data?symbol=${symbol}&expiry=${expiry}`)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('table-body').innerHTML = data.table_html;
                    document.getElementById('summary-strip').innerHTML = data.summary_html;
                    document.getElementById('loading-indicator').style.display = 'none';
                })
                .catch(err => {
                    console.error('Error fetching data:', err);
                    document.getElementById('loading-indicator').style.display = 'none';
                });
        }

        setInterval(fetchData, 30000);
    </script>
</body>
</html>
"""

def generate_html_parts(symbol, selected_expiry):
    try:
        response = nse_optionchain_scrapper(symbol)
    except Exception:
        response = {}

    data_list = response.get('data', [])
    timestamp = response.get('timestamp', datetime.now().strftime("%H:%M:%S"))

    raw_expiries = []
    records = response.get('records', {})
    if records and 'expiryDates' in records:
        raw_expiries = records['expiryDates']
    
    if not raw_expiries and data_list:
        raw_expiries = list(set(item['expiryDate'] for item in data_list if 'expiryDate' in item))

    expiries = sort_dates(raw_expiries)

    if not selected_expiry or selected_expiry not in expiries:
        selected_expiry = expiries[0] if expiries else ""

    spot = 0.0
    for item in data_list:
        for side in ['CE', 'PE']:
            if item.get(side) and item[side].get('underlyingValue'):
                spot = safe_float(item[side]['underlyingValue'])
                break
        if spot > 0:
            break

    filtered = [item for item in data_list if item.get('expiryDate') == selected_expiry]
    filtered = sorted(filtered, key=lambda x: safe_float(x.get('strikePrice', 0)))

    total_ce_oi = sum(safe_int((i.get('CE') or {}).get('openInterest', 0)) for i in filtered)
    total_pe_oi = sum(safe_int((i.get('PE') or {}).get('openInterest', 0)) for i in filtered)
    overall_pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0.0

    if spot > 0 and filtered:
        closest_idx = min(range(len(filtered)), key=lambda i: abs(safe_float(filtered[i].get('strikePrice', 0)) - spot))
        start_idx = max(0, closest_idx - 12)
        end_idx = min(len(filtered), closest_idx + 13)
        display_data = filtered[start_idx:end_idx]
    else:
        display_data = filtered

    max_ce_oi = max([safe_int((i.get('CE') or {}).get('openInterest', 0)) for i in display_data] or [1])
    max_ce_chg = max([safe_int((i.get('CE') or {}).get('changeinOpenInterest', 0)) for i in display_data] or [1])
    max_ce_vol = max([safe_int((i.get('CE') or {}).get('totalTradedVolume', 0)) for i in display_data] or [1])

    max_pe_oi = max([safe_int((i.get('PE') or {}).get('openInterest', 0)) for i in display_data] or [1])
    max_pe_chg = max([safe_int((i.get('PE') or {}).get('changeinOpenInterest', 0)) for i in display_data] or [1])
    max_pe_vol = max([safe_int((i.get('PE') or {}).get('totalTradedVolume', 0)) for i in display_data] or [1])

    resistance_strike = "N/A"
    support_strike = "N/A"
    if display_data:
        res_item = max(display_data, key=lambda i: safe_int((i.get('CE') or {}).get('openInterest', 0)))
        sup_item = max(display_data, key=lambda i: safe_int((i.get('PE') or {}).get('openInterest', 0)))
        resistance_strike = f"{safe_float(res_item.get('strikePrice', 0)):.0f}"
        support_strike = f"{safe_float(sup_item.get('strikePrice', 0)):.0f}"

    rows = []
    spot_line_inserted = False

    for item in display_data:
        strike = safe_float(item.get('strikePrice', 0))
        ce = item.get('CE') or {}
        pe = item.get('PE') or {}

        ce_oi = safe_int(ce.get('openInterest', 0))
        ce_chg_oi = safe_int(ce.get('changeinOpenInterest', 0))
        ce_vol = safe_int(ce.get('totalTradedVolume', 0))
        ce_ltp = safe_float(ce.get('lastPrice', 0))
        ce_chg = safe_float(ce.get('change', 0))
        ce_iv = safe_float(ce.get('impliedVolatility', 0))

        pe_oi = safe_int(pe.get('openInterest', 0))
        pe_chg_oi = safe_int(pe.get('changeinOpenInterest', 0))
        pe_vol = safe_int(pe.get('totalTradedVolume', 0))
        pe_ltp = safe_float(pe.get('lastPrice', 0))
        pe_chg = safe_float(pe.get('change', 0))
        pe_iv = safe_float(pe.get('impliedVolatility', 0))

        ce_oi_pct = (ce_oi / max_ce_oi * 100) if max_ce_oi > 0 else 0
        ce_chg_pct = (ce_chg_oi / max_ce_chg * 100) if (max_ce_chg > 0 and ce_chg_oi > 0) else 0
        ce_vol_pct = (ce_vol / max_ce_vol * 100) if max_ce_vol > 0 else 0

        pe_oi_pct = (pe_oi / max_pe_oi * 100) if max_pe_oi > 0 else 0
        pe_chg_pct = (pe_chg_oi / max_pe_chg * 100) if (max_pe_chg > 0 and pe_chg_oi > 0) else 0
        pe_vol_pct = (pe_vol / max_pe_vol * 100) if max_pe_vol > 0 else 0

        ce_rev = strike + ce_ltp
        pe_rev = strike - pe_ltp
        strike_pcr = round(pe_oi / ce_oi, 2) if ce_oi > 0 else 0.0

        show_spot_line = False
        if not spot_line_inserted and spot > 0 and strike >= spot:
            show_spot_line = True
            spot_line_inserted = True

        rows.append({
            'strike': strike,
            'show_spot_line': show_spot_line,
            'strike_pcr': strike_pcr,
            'ce_iv': ce_iv,
            'ce_oi_pct': ce_oi_pct,
            'ce_oi_fmt': format_num(ce_oi),
            'ce_oi_cls': get_highlight_class(ce_oi_pct, 'ce'),
            'ce_chg_pct': ce_chg_pct,
            'ce_chg_fmt': format_num(ce_chg_oi),
            'ce_chg_cls': get_highlight_class(ce_chg_pct, 'ce'),
            'ce_vol_pct': ce_vol_pct,
            'ce_vol_fmt': format_num(ce_vol),
            'ce_vol_cls': get_highlight_class(ce_vol_pct, 'ce'),
            'ce_ltp': ce_ltp,
            'ce_chg': ce_chg,
            'ce_rev': ce_rev,
            'pe_rev': pe_rev,
            'pe_ltp': pe_ltp,
            'pe_chg': pe_chg,
            'pe_vol_pct': pe_vol_pct,
            'pe_vol_fmt': format_num(pe_vol),
            'pe_vol_cls': get_highlight_class(pe_vol_pct, 'pe'),
            'pe_oi_pct': pe_oi_pct,
            'pe_oi_fmt': format_num(pe_oi),
            'pe_oi_cls': get_highlight_class(pe_oi_pct, 'pe'),
            'pe_chg_pct': pe_chg_pct,
            'pe_chg_fmt': format_num(pe_chg_oi),
            'pe_chg_cls': get_highlight_class(pe_chg_pct, 'pe'),
            'pe_iv': pe_iv,
            'spot': spot
        })

    ROWS_TEMPLATE = """
    {% for row in rows %}
        {% if row.show_spot_line %}
        <tr class="spot-divider">
            <td colspan="13">
                ▼ IMAGINARY LINE — SPOT: {{ row.spot }} | PCR: {{ overall_pcr }} | Support: {{ support_strike }} | Resistance: {{ resistance_strike }} ▼
            </td>
        </tr>
        {% endif %}
        <tr>
            <td class="{% if row.strike < spot %}itm-bg{% endif %}">
                <span class="pct-val">{{ "%.2f"|format(row.ce_iv) }}</span>
            </td>
            <td class="{% if row.strike < spot %}itm-bg{% endif %} {{ row.ce_chg_cls }}">
                <span class="pct-val">{{ "%.1f"|format(row.ce_chg_pct) }}%</span>
                <span class="raw-val">{{ row.ce_chg_fmt }}</span>
            </td>
            <td class="{% if row.strike < spot %}itm-bg{% endif %} {{ row.ce_oi_cls }}">
                <span class="pct-val">{{ "%.1f"|format(row.ce_oi_pct) }}%</span>
                <span class="raw-val">{{ row.ce_oi_fmt }}</span>
            </td>
            <td class="{% if row.strike < spot %}itm-bg{% endif %} {{ row.ce_vol_cls }}">
                <span class="pct-val">{{ "%.1f"|format(row.ce_vol_pct) }}%</span>
                <span class="raw-val">{{ row.ce_vol_fmt }}</span>
            </td>
            <td class="{% if row.strike < spot %}itm-bg{% endif %}">
                <span class="pct-val">{{ "%.2f"|format(row.ce_ltp) }}</span>
                <span class="raw-val {% if row.ce_chg >= 0 %}pos{% else %}neg{% endif %}">{{ "%+.2f"|format(row.ce_chg) }}</span>
            </td>
            <td class="{% if row.strike < spot %}itm-bg{% endif %}">
                <span class="pct-val">{{ "%.0f"|format(row.ce_rev) }}</span>
            </td>

            <td class="strike-col">
                {{ "%.0f"|format(row.strike) }}
                <span class="pcr-sub">PCR: {{ row.strike_pcr }}</span>
            </td>

            <td class="{% if row.strike > spot %}itm-bg{% endif %}">
                <span class="pct-val">{{ "%.0f"|format(row.pe_rev) }}</span>
            </td>
            <td class="{% if row.strike > spot %}itm-bg{% endif %}">
                <span class="pct-val">{{ "%.2f"|format(row.pe_ltp) }}</span>
                <span class="raw-val {% if row.pe_chg >= 0 %}pos{% else %}neg{% endif %}">{{ "%+.2f"|format(row.pe_chg) }}</span>
            </td>
            <td class="{% if row.strike > spot %}itm-bg{% endif %} {{ row.pe_vol_cls }}">
                <span class="pct-val">{{ "%.1f"|format(row.pe_vol_pct) }}%</span>
                <span class="raw-val">{{ row.pe_vol_fmt }}</span>
            </td>
            <td class="{% if row.strike > spot %}itm-bg{% endif %} {{ row.pe_oi_cls }}">
                <span class="pct-val">{{ "%.1f"|format(row.pe_oi_pct) }}%</span>
                <span class="raw-val">{{ row.pe_oi_fmt }}</span>
            </td>
            <td class="{% if row.strike > spot %}itm-bg{% endif %} {{ row.pe_chg_cls }}">
                <span class="pct-val">{{ "%.1f"|format(row.pe_chg_pct) }}%</span>
                <span class="raw-val">{{ row.pe_chg_fmt }}</span>
            </td>
            <td class="{% if row.strike > spot %}itm-bg{% endif %}">
                <span class="pct-val">{{ "%.2f"|format(row.pe_iv) }}</span>
            </td>
        </tr>
    {% endfor %}
    """

    SUMMARY_TEMPLATE = """
    <div class="sum-ce">
        <span>Total CE OI: {{ total_ce_oi_fmt }}</span>
        <span>(CE) Resistance: {{ resistance_strike }}</span>
    </div>
    <div class="sum-mid">
        <span id="lbl-timestamp">{{ timestamp }}</span><br>Overall PCR: <span id="lbl-pcr">{{ overall_pcr }}</span>
    </div>
    <div class="sum-pe">
        <span>(PE) Support: {{ support_strike }}</span>
        <span>Total PE OI: {{ total_pe_oi_fmt }}</span>
    </div>
    """

    table_html = render_template_string(ROWS_TEMPLATE, rows=rows, spot=spot, overall_pcr=overall_pcr, support_strike=support_strike, resistance_strike=resistance_strike)
    summary_html = render_template_string(SUMMARY_TEMPLATE, total_ce_oi_fmt=format_num(total_ce_oi), total_pe_oi_fmt=format_num(total_pe_oi), resistance_strike=resistance_strike, support_strike=support_strike, timestamp=timestamp, overall_pcr=overall_pcr)

    return expiries, selected_expiry, table_html, summary_html, format_num(total_ce_oi), format_num(total_pe_oi), overall_pcr, resistance_strike, support_strike, timestamp, spot

@app.route("/")
def index():
    selected_symbol = request.args.get('symbol', 'NIFTY')
    selected_expiry = request.args.get('expiry')
    expiries, selected_expiry, table_html, summary_html, total_ce_oi_fmt, total_pe_oi_fmt, overall_pcr, resistance_strike, support_strike, timestamp, spot = generate_html_parts(selected_symbol, selected_expiry)
    
    return render_template_string(
        HTML_TEMPLATE,
        symbols=FNO_SYMBOLS,
        selected_symbol=selected_symbol,
        expiries=expiries,
        selected_expiry=selected_expiry,
        table_html=table_html,
        summary_html=summary_html,
        total_ce_oi_fmt=total_ce_oi_fmt,
        total_pe_oi_fmt=total_pe_oi_fmt,
        overall_pcr=overall_pcr,
        resistance_strike=resistance_strike,
        support_strike=support_strike,
        timestamp=timestamp,
        spot=spot
    )

@app.route("/api/data")
def api_data():
    selected_symbol = request.args.get('symbol', 'NIFTY')
    selected_expiry = request.args.get('expiry')
    _, _, table_html, summary_html, _, _, _, _, _, _, _ = generate_html_parts(selected_symbol, selected_expiry)
    return jsonify({
        'table_html': table_html,
        'summary_html': summary_html
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
