import math
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from nsepython import nse_optionchain_scrapper
import requests

app = Flask(__name__)

INDEX_SYMBOLS = ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTY", "NIFTYFPI", "NIFTYNXT50", "SENSEX"]

STOCK_SYMBOLS = [
    "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER",
    "ALKEM", "AMBER", "AMBUJACEM", "ANANDRATHI", "ANGELONE", "APLAPOLLO", "APOLLOHOSP", "ASHOKLEY",
    "ASIANPAINT", "ASTRAL", "ATHERENERG", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV",
    "BAJFINANCE", "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG", "BHARTIARTL",
    "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BPCL", "BRITANNIA", "BSE", "CAMS", "CANBK",
    "CDSL", "CGPOWER", "CHOLAFIN", "CIPLA", "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL",
    "CONCOR", "COROMANDEL", "CROMPTON", "CUB", "CUMMINSIND", "DABUR", "DATAPATTNS", "DELHIVERY",
    "DIVISLAB", "DIXON", "DLF", "DMART", "DRREDDY", "EICHERMOT", "ENRIN", "ETERNAL", "FEDERALBNK",
    "FORCEMOT", "FORTIS", "GAIL", "GLENMARK", "GMRAIRPORT", "GODFRYPHLP", "GODREJCP", "GODREJPROP",
    "GRASIM", "GVT&D", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HYUNDAI", "ICICIBANK", "ICICIGI", "ICICILIFE",
    "IDEA", "IDFCFIRSTB", "IEX", "INDHOTEL", "INDIANB", "INDIGO", "INDUSINDBK", "INDUSTOWER",
    "INFY", "INOXWIND", "IOC", "IREDA", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JSWENERGY",
    "JSWSTEEL", "JUBLFOOD", "KALYANKJIL", "KARURVYSYA", "KAYNES", "KEI", "KFINTECH", "KOTAKBANK",
    "KPITTECH", "LAURUSLABS", "LICHSGFIN", "LICI", "LODHA", "LT", "LTF", "LTM", "LUPIN", "M&M",
    "MAHABANK", "MANAPPURAM", "MANKIND", "MARICO", "MARUTI", "MAXHEALTH", "MAZDOCK", "MCX", "MFSL",
    "MOTHERSON", "MOTILALOFS", "MPHASIS", "MUTHOOTFIN", "NAM-INDIA", "NATIONALUM", "NAUKRI",
    "NAVINFLUOR", "NBCC", "NESTLEIND", "NHPC", "NMDC", "NTPC", "NYKAA", "OBEROIRLTY", "OFSS",
    "OIL", "ONGC", "PAGEIND", "PATANJALI", "PAYTM", "PERSISTENT", "PETRONET", "PFC", "PGEL",
    "PHOENIXLTD", "PIDILITIND", "PIIND", "PNB", "PNBHOUSING", "POLICYBZR", "POLYCAB", "POWERGRID",
    "POWERINDIA", "PREMIERENE", "PRESTIGE", "RADICO", "RBLBANK", "RECLTD", "RELIANCE", "RVNL",
    "SAGILITY", "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS",
    "SOLARINDS", "SONACOMS", "SRF", "SUNPHARMA", "SUPREMEIND", "SUZLON", "SWIGGY", "SYRMA",
    "TATACONSUM", "TATAELXSI", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TIINDIA", "TITAN",
    "TMPV", "TORNTPHARM", "TRENT", "TVSMOTOR", "UJJIVANSFB", "ULTRACEMCO", "UNIONBANK", "UNITDSPR",
    "UNOMINDA", "UPL", "VBL", "VEDL", "VMM", "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK", "ZYDUSLIFE"
]

INDEX_SYMBOLS = sorted(set(INDEX_SYMBOLS))
STOCK_SYMBOLS = sorted(set(STOCK_SYMBOLS))
ALL_SYMBOLS = sorted(set(INDEX_SYMBOLS + STOCK_SYMBOLS))

GROWW_SENSEX_URL = "https://groww.in/v1/api/option_chain_service/v1/option_chain/sp-bse-sensex"
GROWW_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://groww.in/options/options-nifty",
}
_GROWW_SESSION = None


def num(val, as_int=False):
    try:
        n = float(val)
        return int(n) if as_int else n
    except (TypeError, ValueError):
        return 0 if as_int else 0.0


def fmt_num(n):
    a, s = abs(n), ("-" if n < 0 else "")
    return f"{s}{a/1e6:.2f}M" if a >= 1e6 else (f"{s}{a/1e3:.1f}K" if a >= 1e3 else str(n))


def bs_price(opt, s, k, t, r, sig):
    if t <= 0 or sig <= 0 or s <= 0 or k <= 0:
        return max(0.0, s - k) if opt == "CE" else max(0.0, k - s)
    d1 = (math.log(s / k) + (r + 0.5 * sig * sig) * t) / (sig * math.sqrt(t))
    d2 = d1 - sig * math.sqrt(t)
    cdf = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    return (s * cdf(d1) - k * math.exp(-r * t) * cdf(d2)) if opt == "CE" else (k * math.exp(-r * t) * cdf(-d2) - s * cdf(-d1))


def estimate_iv(opt, ltp, spot, strike, expiry_str, r=0.07):
    if min(ltp, spot, strike) <= 0 or not expiry_str:
        return 0.0
    try:
        days = max(0.25, (datetime.strptime(expiry_str, "%d-%b-%Y").replace(hour=15, minute=30) - datetime.now()).total_seconds() / 86400.0)
    except ValueError:
        return 0.0
    lo, hi, t = 0.01, 2.50, days / 365.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        p = bs_price(opt, spot, strike, t, r, mid)
        if abs(p - ltp) < 0.01:
            return round(mid * 100.0, 2)
        hi, lo = (mid, lo) if p > ltp else (hi, mid)
    return round(0.5 * (lo + hi) * 100.0, 2)


def _get_groww_session():
    global _GROWW_SESSION
    if _GROWW_SESSION is None:
        s = requests.Session()
        s.headers.update(GROWW_HEADERS)
        try:
            s.get("https://groww.in/options/options-nifty", timeout=10)
        except Exception:
            pass
        _GROWW_SESSION = s
    return _GROWW_SESSION


def fetch_sensex_current_chain():
    """Fetches SENSEX current expiry option chain from Groww and normalizes to NSE-like records."""
    sess = _get_groww_session()
    resp = sess.get(GROWW_SENSEX_URL, timeout=10)
    resp.raise_for_status()
    oc = (resp.json() or {}).get("optionChain") or {}
    exp_dto = oc.get("expiryDetailsDto") or {}
    chains = oc.get("optionChains") or []

    curr_raw = exp_dto.get("currentExpiry") or ((exp_dto.get("expiryDates") or [None])[0])
    try:
        exp_fmt = datetime.strptime(str(curr_raw)[:10], "%Y-%m-%d").strftime("%d-%b-%Y") if curr_raw else ""
    except ValueError:
        exp_fmt = str(curr_raw or "")

    raw_rows = []
    for item in chains:
        ce = item.get("callOption") or {}
        pe = item.get("putOption") or {}
        raw_strike = ce.get("strikePrice") or pe.get("strikePrice") or item.get("strikePrice")
        if not raw_strike:
            continue
        strike = num(raw_strike) / 100.0
        ce_ltp = num(ce.get("ltp"))
        pe_ltp = num(pe.get("ltp"))
        ce_oi = num(ce.get("openInterest"), True)
        pe_oi = num(pe.get("openInterest"), True)
        ce_prev_oi = num(ce.get("prevOpenInterest"), True)
        pe_prev_oi = num(pe.get("prevOpenInterest"), True)
        ce_vol = num(ce.get("volume"), True)
        pe_vol = num(pe.get("volume"), True)
        raw_rows.append({
            "strike": strike,
            "ce_ltp": ce_ltp, "ce_oi": ce_oi, "ce_oi_chg": ce_oi - ce_prev_oi, "ce_vol": ce_vol,
            "pe_ltp": pe_ltp, "pe_oi": pe_oi, "pe_oi_chg": pe_oi - pe_prev_oi, "pe_vol": pe_vol,
            "diff": abs(ce_ltp - pe_ltp),
        })

    if not raw_rows:
        return {"records": {"expiryDates": [exp_fmt] if exp_fmt else [], "data": []}}

    raw_rows.sort(key=lambda r: r["strike"])
    active = [r for r in raw_rows if (r["ce_oi"] + r["pe_oi"] + r["ce_vol"] + r["pe_vol"]) > 0] or raw_rows
    atm = min(active, key=lambda r: r["diff"])
    spot = round(atm["strike"] + atm["ce_ltp"] - atm["pe_ltp"], 2)

    data_out = []
    for r in raw_rows:
        ce_iv = estimate_iv("CE", r["ce_ltp"], spot, r["strike"], exp_fmt)
        pe_iv = estimate_iv("PE", r["pe_ltp"], spot, r["strike"], exp_fmt)
        data_out.append({
            "strikePrice": r["strike"],
            "expiryDate": exp_fmt,
            "CE": {
                "strikePrice": r["strike"],
                "expiryDate": exp_fmt,
                "underlyingValue": spot,
                "openInterest": r["ce_oi"],
                "changeinOpenInterest": r["ce_oi_chg"],
                "totalTradedVolume": r["ce_vol"],
                "lastPrice": r["ce_ltp"],
                "change": 0.0,
                "impliedVolatility": ce_iv,
            },
            "PE": {
                "strikePrice": r["strike"],
                "expiryDate": exp_fmt,
                "underlyingValue": spot,
                "openInterest": r["pe_oi"],
                "changeinOpenInterest": r["pe_oi_chg"],
                "totalTradedVolume": r["pe_vol"],
                "lastPrice": r["pe_ltp"],
                "change": 0.0,
                "impliedVolatility": pe_iv,
            },
        })

    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "records": {
            "expiryDates": [exp_fmt] if exp_fmt else [],
            "data": data_out,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        },
    }


def hl_class(pct, side):
    return f"max-{side}" if pct >= 99.9 else ("second-max" if pct >= 75.0 else ("third-max" if pct >= 50.0 else ""))


def parse_leg(leg, side, spot, strike, expiry, maxs):
    leg = leg if isinstance(leg, dict) else {}
    oi = num(leg.get("openInterest"), True)
    chg_oi = num(leg.get("changeinOpenInterest"), True)
    vol = num(leg.get("totalTradedVolume"), True)
    ltp = num(leg.get("lastPrice"))
    chg = num(leg.get("change"))
    iv = num(leg.get("impliedVolatility"))
    if iv <= 0 and ltp > 0:
        iv = estimate_iv(side, ltp, spot, strike, expiry)
    oi_p = (oi / maxs["oi"] * 100) if maxs["oi"] > 0 else 0
    chg_p = (chg_oi / maxs["chg"] * 100) if (maxs["chg"] > 0 and chg_oi > 0) else 0
    vol_p = (vol / maxs["vol"] * 100) if maxs["vol"] > 0 else 0
    return {
        "iv": iv, "ltp": ltp, "chg": chg,
        "oi_p": oi_p, "oi_f": fmt_num(oi), "oi_c": hl_class(oi_p, side.lower()),
        "chg_p": chg_p, "chg_f": fmt_num(chg_oi), "chg_c": hl_class(chg_p, side.lower()),
        "vol_p": vol_p, "vol_f": fmt_num(vol), "vol_c": hl_class(vol_p, side.lower()),
        "h_oi": False, "h_chg": False, "h_vol": False,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pravas | Option Chain Analyzer</title>
<style>
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', sans-serif; background: #eef2f6; margin: 0; padding: 10px; font-size: 12px; }
.top-bar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; background: #fff; padding: 8px 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 8px; }
.brand { font-size: 16px; font-weight: bold; color: #1e293b; } .brand span { color: #2563eb; }
.controls { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.controls select, .controls input { font-size: 12px; padding: 4px 8px; border-radius: 4px; border: 1px solid #cbd5e1; background: #fff; }
.controls select { font-weight: bold; } .controls input { width: 140px; }
.btn-refresh { font-size: 12px; padding: 4px 10px; border-radius: 4px; background: #2563eb !important; color: #fff !important; border: none !important; cursor: pointer; font-weight: bold; }
.summary-strip { display: flex; width: 100%; font-weight: bold; color: #fff; border-radius: 4px; overflow: hidden; margin-bottom: 8px; text-align: center; }
.sum-ce { flex: 5; background: #b91c1c; padding: 7px; display: flex; justify-content: space-around; }
.sum-mid { flex: 1.5; background: #1e3a8a; padding: 7px; }
.sum-pe { flex: 5; background: #15803d; padding: 7px; display: flex; justify-content: space-around; }
.table-wrap { overflow-x: auto; background: #fff; border-radius: 5px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
table { width: 100%; border-collapse: collapse; text-align: center; }
th, td { border: 1px solid #cbd5e1; padding: 5px 6px; white-space: nowrap; text-align: center; }
th.ce-th { background: #991b1b; color: #fff; text-align: center; font-size: 11px; }
th.sp-th { background: #1d4ed8; color: #fff; text-align: center; font-size: 11px; }
th.pe-th { background: #166534; color: #fff; text-align: center; font-size: 11px; }
.pct-val { display: block; font-size: 11px; font-weight: bold; }
.raw-val { display: block; font-size: 10px; opacity: 0.85; }
.h-badge { display: inline-block; margin-left: 3px; padding: 0 3px; border-radius: 3px; font-size: 9px; font-weight: 800; line-height: 1.2; background: #ffffff; color: #0f172a; vertical-align: middle; }
.max-ce { background: #dc2626 !important; color: #fff !important; }
.max-pe { background: #16a34a !important; color: #fff !important; }
.second-max { background: #fde047 !important; color: #0f172a !important; }
.third-max { background: #fef9c3 !important; color: #0f172a !important; }
.itm-bg { background: #fffbeb; }
td.strike-col { background: #dbeafe; text-align: center; font-weight: bold; color: #1e3a8a; font-size: 13px; }
.pcr-sub { display: block; font-size: 10px; color: #dc2626; font-weight: normal; }
tr.spot-divider td { background: #b91c1c !important; color: #fff !important; text-align: center !important; font-weight: bold; padding: 5px; font-size: 12px; }
.pos { color: #15803d; } .neg { color: #dc2626; }
.max-ce .pos, .max-ce .neg, .max-pe .pos, .max-pe .neg { color: #fff; }
#loading-indicator { font-size: 11px; color: #2563eb; margin-left: 8px; display: none; }
</style>
</head>
<body>
<div class="top-bar">
  <div class="brand">Pravas <span>⚡</span> | Option Chain Analyzer <span id="loading-indicator">Updating...</span></div>
  <div class="controls">
    <label>Category:</label>
    <select id="category-select" onchange="updateSymbolList(true)">
      <option value="ALL" {% if selected_category=='ALL' %}selected{% endif %}>All ({{ all_count }})</option>
      <option value="INDEX" {% if selected_category=='INDEX' %}selected{% endif %}>Indices ({{ index_count }})</option>
      <option value="STOCK" {% if selected_category=='STOCK' %}selected{% endif %}>Stocks ({{ stock_count }})</option>
    </select>
    <input type="text" id="symbol-search" placeholder="Search symbol..." oninput="updateSymbolList(false)" onkeydown="if(event.key==='Enter') reloadPage()">
    <label>Symbol:</label>
    <select id="symbol-select" onchange="reloadPage()"></select>
    <label>Expiry:</label>
    <select id="expiry-select" onchange="reloadPage()">
      {% for exp in expiries %}<option value="{{ exp }}" {% if exp==selected_expiry %}selected{% endif %}>{{ exp }}</option>{% endfor %}
    </select>
    <button onclick="fetchData()" class="btn-refresh">Refresh Now</button>
  </div>
</div>
<div class="summary-strip" id="summary-strip">{{ summary_html | safe }}</div>
<div class="table-wrap">
  <table>
    <thead><tr>
      <th class="ce-th">IV / Delta</th><th class="ce-th">OI Chg</th><th class="ce-th">OI</th><th class="ce-th">Volume</th><th class="ce-th">LTP / Chg</th><th class="ce-th">Rev.</th>
      <th class="sp-th">SP / PCR</th>
      <th class="pe-th">Rev.</th><th class="pe-th">LTP / Chg</th><th class="pe-th">Volume</th><th class="pe-th">OI</th><th class="pe-th">OI Chg</th><th class="pe-th">IV / Delta</th>
    </tr></thead>
    <tbody id="table-body">{{ table_html | safe }}</tbody>
  </table>
</div>
<script>
const GROUPS = { ALL: {{ all_symbols|tojson }}, INDEX: {{ index_symbols|tojson }}, STOCK: {{ stock_symbols|tojson }} };
const INIT_SYM = {{ selected_symbol|tojson }};
function updateSymbolList(autoReload) {
  const cat = document.getElementById('category-select').value;
  const pool = GROUPS[cat] || GROUPS.ALL;
  const q = document.getElementById('symbol-search').value.trim().toUpperCase();
  const sel = document.getElementById('symbol-select');
  const prev = sel.value || INIT_SYM;
  const list = q ? pool.filter(s => s.includes(q)) : pool;
  sel.innerHTML = list.length ? list.map(s => `<option value="${s}">${s}</option>`).join('') : `<option value="">No match</option>`;
  if (list.includes(prev)) sel.value = prev;
  else if (list.length) {
    sel.value = list[0];
    if (autoReload && document.activeElement !== document.getElementById('symbol-search')) reloadPage();
  }
}
function reloadPage() {
  const cat = document.getElementById('category-select').value;
  const sym = document.getElementById('symbol-select').value;
  const exp = document.getElementById('expiry-select').value;
  if (sym) window.location.href = `/?category=${encodeURIComponent(cat)}&symbol=${encodeURIComponent(sym)}&expiry=${encodeURIComponent(exp)}`;
}
function fetchData() {
  const sym = document.getElementById('symbol-select').value;
  const exp = document.getElementById('expiry-select').value;
  if (!sym) return;
  const ind = document.getElementById('loading-indicator');
  ind.style.display = 'inline';
  fetch(`/api/data?symbol=${encodeURIComponent(sym)}&expiry=${encodeURIComponent(exp)}`)
    .then(r => r.json()).then(d => {
      document.getElementById('table-body').innerHTML = d.table_html;
      document.getElementById('summary-strip').innerHTML = d.summary_html;
      ind.style.display = 'none';
    }).catch(() => { ind.style.display = 'none'; });
}
(function(){
  const catEl = document.getElementById('category-select');
  if (!(GROUPS[catEl.value] || GROUPS.ALL).includes(INIT_SYM)) catEl.value = 'ALL';
  updateSymbolList(false);
  document.getElementById('symbol-select').value = INIT_SYM;
})();
setInterval(fetchData, 30000);
</script>
</body>
</html>"""

ROWS_TEMPLATE = """
{% if not rows %}
<tr><td colspan="13" style="text-align:center; padding:12px; color:#b91c1c; font-weight:bold;">{{ status_msg or "Koi option chain data nahi mila" }}</td></tr>
{% endif %}
{% for r in rows %}
  {% if r.show_spot %}
  <tr class="spot-divider"><td colspan="13">▼ IMAGINARY LINE — SPOT: {{ r.spot }} | PCR: {{ overall_pcr }} | Support: {{ support }} | Resistance: {{ resistance }} ▼</td></tr>
  {% endif %}
  <tr>
    <td class="{% if r.strike < spot %}itm-bg{% endif %}"><span class="pct-val">{{ "%.2f"|format(r.ce.iv) }}</span></td>
    <td class="{% if r.strike < spot %}itm-bg{% endif %} {{ r.ce.chg_c }}"><span class="pct-val">{{ "%.1f"|format(r.ce.chg_p) }}%{% if r.ce.h_chg %}<span class="h-badge">H</span>{% endif %}</span><span class="raw-val">{{ r.ce.chg_f }}</span></td>
    <td class="{% if r.strike < spot %}itm-bg{% endif %} {{ r.ce.oi_c }}"><span class="pct-val">{{ "%.1f"|format(r.ce.oi_p) }}%{% if r.ce.h_oi %}<span class="h-badge">H</span>{% endif %}</span><span class="raw-val">{{ r.ce.oi_f }}</span></td>
    <td class="{% if r.strike < spot %}itm-bg{% endif %} {{ r.ce.vol_c }}"><span class="pct-val">{{ "%.1f"|format(r.ce.vol_p) }}%{% if r.ce.h_vol %}<span class="h-badge">H</span>{% endif %}</span><span class="raw-val">{{ r.ce.vol_f }}</span></td>
    <td class="{% if r.strike < spot %}itm-bg{% endif %}"><span class="pct-val">{{ "%.2f"|format(r.ce.ltp) }}</span><span class="raw-val {% if r.ce.chg >= 0 %}pos{% else %}neg{% endif %}">{{ "%+.2f"|format(r.ce.chg) }}</span></td>
    <td class="{% if r.strike < spot %}itm-bg{% endif %}"><span class="pct-val">{{ "%.0f"|format(r.ce_rev) }}</span></td>
    <td class="strike-col">{{ "%.0f"|format(r.strike) }}<span class="pcr-sub">PCR: {{ r.pcr }}</span></td>
    <td class="{% if r.strike > spot %}itm-bg{% endif %}"><span class="pct-val">{{ "%.0f"|format(r.pe_rev) }}</span></td>
    <td class="{% if r.strike > spot %}itm-bg{% endif %}"><span class="pct-val">{{ "%.2f"|format(r.pe.ltp) }}</span><span class="raw-val {% if r.pe.chg >= 0 %}pos{% else %}neg{% endif %}">{{ "%+.2f"|format(r.pe.chg) }}</span></td>
    <td class="{% if r.strike > spot %}itm-bg{% endif %} {{ r.pe.vol_c }}"><span class="pct-val">{{ "%.1f"|format(r.pe.vol_p) }}%{% if r.pe.h_vol %}<span class="h-badge">H</span>{% endif %}</span><span class="raw-val">{{ r.pe.vol_f }}</span></td>
    <td class="{% if r.strike > spot %}itm-bg{% endif %} {{ r.pe.oi_c }}"><span class="pct-val">{{ "%.1f"|format(r.pe.oi_p) }}%{% if r.pe.h_oi %}<span class="h-badge">H</span>{% endif %}</span><span class="raw-val">{{ r.pe.oi_f }}</span></td>
    <td class="{% if r.strike > spot %}itm-bg{% endif %} {{ r.pe.chg_c }}"><span class="pct-val">{{ "%.1f"|format(r.pe.chg_p) }}%{% if r.pe.h_chg %}<span class="h-badge">H</span>{% endif %}</span><span class="raw-val">{{ r.pe.chg_f }}</span></td>
    <td class="{% if r.strike > spot %}itm-bg{% endif %}"><span class="pct-val">{{ "%.2f"|format(r.pe.iv) }}</span></td>
  </tr>
{% endfor %}
"""

SUMMARY_TEMPLATE = """
<div class="sum-ce"><span>Total CE OI: {{ ce_oi }}</span><span>(CE) Resistance: {{ resistance }}</span></div>
<div class="sum-mid"><span id="lbl-timestamp">{{ ts }}</span><br>Overall PCR: <span id="lbl-pcr">{{ pcr }}</span></div>
<div class="sum-pe"><span>(PE) Support: {{ support }}</span><span>Total PE OI: {{ pe_oi }}</span></div>
"""


def generate_html_parts(symbol, selected_expiry):
    status_msg, resp = "", {}
    try:
        if symbol.upper() == "SENSEX":
            raw = fetch_sensex_current_chain()
        else:
            raw = nse_optionchain_scrapper(symbol)
        resp = raw if isinstance(raw, dict) else {}
        if not resp:
            status_msg = f"{symbol} ke liye invalid response aaya"
    except Exception as e:
        status_msg = f"{symbol} fetch error: {e}"

    records = resp.get("records") if isinstance(resp.get("records"), dict) else {}
    data_list = resp.get("data") or records.get("data") or []
    data_list = data_list if isinstance(data_list, list) else []
    ts = resp.get("timestamp") or records.get("timestamp") or datetime.now().strftime("%H:%M:%S")
    if not data_list and not status_msg:
        status_msg = f"{symbol} ke liye koi option chain data nahi mila"

    raw_exp = records.get("expiryDates") if isinstance(records.get("expiryDates"), list) else list({
        i["expiryDate"] for i in data_list if isinstance(i, dict) and i.get("expiryDate")
    })
    expiries = sorted(raw_exp, key=lambda d: datetime.strptime(d, "%d-%b-%Y"))
    if not selected_expiry or selected_expiry not in expiries:
        selected_expiry = expiries[0] if expiries else ""

    spot = next((num(i[s]["underlyingValue"]) for i in data_list if isinstance(i, dict) for s in ("CE", "PE") if isinstance(i.get(s), dict) and i[s].get("underlyingValue")), 0.0)
    filtered = sorted([i for i in data_list if isinstance(i, dict) and i.get("expiryDate") == selected_expiry], key=lambda x: num(x.get("strikePrice")))

    tot_ce = sum(num((i.get("CE") or {}).get("openInterest"), True) for i in filtered)
    tot_pe = sum(num((i.get("PE") or {}).get("openInterest"), True) for i in filtered)
    pcr = round(tot_pe / tot_ce, 2) if tot_ce > 0 else 0.0

    if spot > 0 and filtered:
        idx = min(range(len(filtered)), key=lambda i: abs(num(filtered[i].get("strikePrice")) - spot))
        disp = filtered[max(0, idx - 12):min(len(filtered), idx + 13)]
    else:
        disp = filtered

    max_s = {
        "CE": {
            "oi": max([num((i.get("CE") or {}).get("openInterest"), True) for i in disp] or [1]),
            "chg": max([num((i.get("CE") or {}).get("changeinOpenInterest"), True) for i in disp] or [1]),
            "vol": max([num((i.get("CE") or {}).get("totalTradedVolume"), True) for i in disp] or [1]),
        },
        "PE": {
            "oi": max([num((i.get("PE") or {}).get("openInterest"), True) for i in disp] or [1]),
            "chg": max([num((i.get("PE") or {}).get("changeinOpenInterest"), True) for i in disp] or [1]),
            "vol": max([num((i.get("PE") or {}).get("totalTradedVolume"), True) for i in disp] or [1]),
        },
    }

    h_oi_side = "CE" if max_s["CE"]["oi"] > max_s["PE"]["oi"] else ("PE" if max_s["PE"]["oi"] > max_s["CE"]["oi"] else None)
    h_chg_side = "CE" if max_s["CE"]["chg"] > max_s["PE"]["chg"] else ("PE" if max_s["PE"]["chg"] > max_s["CE"]["chg"] else None)
    h_vol_side = "CE" if max_s["CE"]["vol"] > max_s["PE"]["vol"] else ("PE" if max_s["PE"]["vol"] > max_s["CE"]["vol"] else None)

    res = f"{num(max(disp, key=lambda i: num((i.get('CE') or {}).get('openInterest'), True)).get('strikePrice')):.0f}" if disp else "N/A"
    sup = f"{num(max(disp, key=lambda i: num((i.get('PE') or {}).get('openInterest'), True)).get('strikePrice')):.0f}" if disp else "N/A"

    rows, spot_done = [], False
    for item in disp:
        strike = num(item.get("strikePrice"))
        ce = parse_leg(item.get("CE"), "CE", spot, strike, selected_expiry, max_s["CE"])
        pe = parse_leg(item.get("PE"), "PE", spot, strike, selected_expiry, max_s["PE"])

        ce["h_oi"] = (h_oi_side == "CE" and ce["oi_p"] >= 99.9)
        pe["h_oi"] = (h_oi_side == "PE" and pe["oi_p"] >= 99.9)

        ce["h_chg"] = (h_chg_side == "CE" and ce["chg_p"] >= 99.9)
        pe["h_chg"] = (h_chg_side == "PE" and pe["chg_p"] >= 99.9)

        ce["h_vol"] = (h_vol_side == "CE" and ce["vol_p"] >= 99.9)
        pe["h_vol"] = (h_vol_side == "PE" and pe["vol_p"] >= 99.9)

        ce_oi_raw = num((item.get("CE") or {}).get("openInterest"), True)
        pe_oi_raw = num((item.get("PE") or {}).get("openInterest"), True)
        show_spot = False
        if not spot_done and spot > 0 and strike >= spot:
            show_spot = spot_done = True
        rows.append({
            "strike": strike, "spot": spot, "show_spot": show_spot,
            "ce": ce, "pe": pe,
            "ce_rev": strike + ce["ltp"], "pe_rev": strike - pe["ltp"],
            "pcr": round(pe_oi_raw / ce_oi_raw, 2) if ce_oi_raw > 0 else 0.0,
        })

    table_html = render_template_string(ROWS_TEMPLATE, rows=rows, spot=spot, overall_pcr=pcr, support=sup, resistance=res, status_msg=status_msg)
    summary_html = render_template_string(SUMMARY_TEMPLATE, ce_oi=fmt_num(tot_ce), pe_oi=fmt_num(tot_pe), resistance=res, support=sup, ts=ts, pcr=pcr)
    return expiries, selected_expiry, table_html, summary_html


@app.route("/")
def index():
    cat = request.args.get("category", "ALL")
    cat = cat if cat in ("ALL", "INDEX", "STOCK") else "ALL"
    sym = request.args.get("symbol", "NIFTY")
    sym = sym if sym in ALL_SYMBOLS else "NIFTY"
    expiries, exp, table_html, summary_html = generate_html_parts(sym, request.args.get("expiry"))
    return render_template_string(
        HTML_TEMPLATE, all_symbols=ALL_SYMBOLS, index_symbols=INDEX_SYMBOLS, stock_symbols=STOCK_SYMBOLS,
        all_count=len(ALL_SYMBOLS), index_count=len(INDEX_SYMBOLS), stock_count=len(STOCK_SYMBOLS),
        selected_category=cat, selected_symbol=sym, expiries=expiries, selected_expiry=exp,
        table_html=table_html, summary_html=summary_html
    )


@app.route("/api/data")
def api_data():
    _, _, table_html, summary_html = generate_html_parts(request.args.get("symbol", "NIFTY"), request.args.get("expiry"))
    return jsonify({"table_html": table_html, "summary_html": summary_html})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

