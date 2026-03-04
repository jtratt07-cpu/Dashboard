# coding: utf-8
"""
Sports Betting Dashboard
Pulls live NBA + CBB markets from Kalshi and generates picks using a
weighted-stats model. Simple, beginner-friendly UI.
"""

import streamlit as st
import requests
import pandas as pd
import math
import json
import os
import re
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betting Dashboard",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Syne',sans-serif;}
.stApp{background:#0a0e1a;color:#e8eaf0;}
section[data-testid="stSidebar"]{background:#0f1525!important;border-right:1px solid #1e2640;}
section[data-testid="stSidebar"] *{color:#c8ccd8!important;}
[data-testid="metric-container"]{background:#131929;border:1px solid #1e2a45;border-radius:12px;padding:16px;}
[data-testid="stMetricValue"]{font-family:'DM Mono',monospace!important;font-size:1.6rem!important;color:#7eeaff!important;}
[data-testid="stMetricLabel"]{color:#8892a4!important;font-size:0.75rem!important;}
.card{background:#131929;border:1px solid #1e2a45;border-radius:14px;padding:20px 24px;margin-bottom:16px;}
.strong-pick{border-left:4px solid #4ade80;}
.lean-pick{border-left:4px solid #facc15;}
.badge-strong{display:inline-block;background:#1a3a2a;color:#4ade80;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.badge-lean{display:inline-block;background:#2a2a1a;color:#facc15;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.badge-market{display:inline-block;background:#1e2640;color:#94a3b8;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.prob-bar-bg{background:#1e2640;border-radius:8px;height:10px;width:100%;margin:4px 0 12px 0;}
.prob-bar-fill{background:linear-gradient(90deg,#1a6fff,#7eeaff);border-radius:8px;height:10px;}
hr{border-color:#1e2640!important;}
#MainMenu,footer{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
KALSHI_BASE  = "https://api.elections.kalshi.com/trade-api/v2"
TRACKER_FILE = "picks_log.json"

# These are the series tickers Kalshi actually uses for game markets.
# We try multiple because Kalshi has changed naming conventions.
NBA_SERIES = ["KXNBASPREAD", "KXNBAWIN", "KXNBAGAME", "KXNBAMONEYLINE"]
CBB_SERIES = ["KXNCAAMBGAME", "KXNCAAMWIN", "KXNCAAMBSPREAD"]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _is_edt():
    dt = datetime.utcnow()
    y  = dt.year
    mar = datetime(y, 3, 8)
    while mar.weekday() != 6: mar += timedelta(days=1)
    nov = datetime(y, 11, 1)
    while nov.weekday() != 6: nov += timedelta(days=1)
    return mar <= dt < nov

def now_eastern():
    dt  = datetime.utcnow()
    off = timedelta(hours=-4 if _is_edt() else -5)
    est = dt + off
    hr  = str(int(est.strftime("%I")))
    suf = "EDT" if _is_edt() else "EST"
    return est.strftime(f"{hr}:%M %p") + f" {suf}"

def today_eastern():
    dt  = datetime.utcnow()
    off = timedelta(hours=-4 if _is_edt() else -5)
    return (dt + off).date()

def pct(x):
    return f"{x*100:.0f}%" if x is not None else "—"

def to_american(prob: float) -> str:
    """Convert implied probability to American odds string."""
    if prob is None or prob <= 0 or prob >= 1:
        return "—"
    if prob >= 0.5:
        return f"-{round((prob / (1-prob)) * 100)}"
    else:
        return f"+{round(((1-prob) / prob) * 100)}"

# ─────────────────────────────────────────────────────────────────────────────
# KALSHI API
# ─────────────────────────────────────────────────────────────────────────────
def kalshi_get(path, params=None):
    try:
        r = requests.get(f"{KALSHI_BASE}{path}", params=params or {}, timeout=12)
        return r
    except Exception as e:
        return None

@st.cache_data(ttl=600, show_spinner=False)  # 10 min cache
def fetch_kalshi_markets(series_tickers: tuple) -> dict:
    """
    Try each series ticker in order and return the first one that
    comes back with actual markets. Returns:
      {"ok": bool, "markets": [...], "series_used": str, "error": str}
    """
    now_ts  = int(datetime.now(timezone.utc).timestamp())
    # Wide window: 12 hours ago → 5 days out (catches today + coming days)
    win_min = now_ts - 60*60*12
    win_max = now_ts + 60*60*24*5

    for series in series_tickers:
        markets = []
        cursor  = None
        error   = ""
        while True:
            params = {
                "series_ticker": series,
                "status":        "open",
                "limit":         200,
                "min_close_ts":  win_min,
                "max_close_ts":  win_max,
            }
            if cursor:
                params["cursor"] = cursor
            r = kalshi_get("/markets", params)
            if r is None:
                error = "Request failed (timeout or network error)"
                break
            if r.status_code != 200:
                error = f"HTTP {r.status_code}: {r.text[:150]}"
                break
            data   = r.json()
            chunk  = data.get("markets", [])
            markets.extend(chunk)
            cursor = data.get("cursor")
            if not cursor or not chunk or len(markets) >= 2000:
                break

        if markets:
            return {"ok": True, "markets": markets, "series_used": series, "error": ""}

    # Nothing worked — return last error and empty
    return {"ok": False, "markets": [], "series_used": "", "error": error or "No markets found for any series ticker tried."}

def kalshi_prob(mkt: dict):
    """
    Extract implied probability from a Kalshi market dict.
    Prices are in cents (0-100).  Midpoint of bid/ask is most accurate.
    """
    try:
        yb = mkt.get("yes_bid")
        ya = mkt.get("yes_ask")
        lp = mkt.get("last_price")
        if yb and ya and yb > 0 and ya > 0:
            return (yb + ya) / 200.0
        if lp and lp > 0:
            return lp / 100.0
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────────────────────────────────────
# TEAM PARSING
# ─────────────────────────────────────────────────────────────────────────────
# Short alias → full name for common abbreviations in Kalshi titles
TEAM_ALIASES = {
    "lal": "Lakers", "lak": "Lakers", "los angeles l": "Lakers",
    "bkn": "Nets",   "bro": "Nets",   "brooklyn": "Nets",
    "gsw": "Warriors", "golden state": "Warriors",
    "bos": "Celtics", "boston": "Celtics",
    "phi": "76ers",  "76ers": "76ers", "philadelphia": "76ers",
    "mil": "Bucks",  "milwaukee": "Bucks",
    "den": "Nuggets","denver": "Nuggets",
    "mem": "Grizzlies","memphis":"Grizzlies",
    "sac": "Kings",  "sacramento": "Kings",
    "dal": "Mavericks","dallas":"Mavericks",
    "min": "Timberwolves","minnesota":"Timberwolves",
    "okc": "Thunder","oklahoma":"Thunder",
    "cle": "Cavaliers","cleveland":"Cavaliers",
    "nyk": "Knicks", "new york k": "Knicks","knicks":"Knicks",
    "mia": "Heat",   "miami": "Heat",
    "ind": "Pacers", "indiana": "Pacers",
    "atl": "Hawks",  "atlanta": "Hawks",
    "cha": "Hornets","charlotte":"Hornets",
    "det": "Pistons","detroit": "Pistons",
    "orl": "Magic",  "orlando": "Magic",
    "was": "Wizards","washington":"Wizards",
    "chi": "Bulls",  "chicago": "Bulls",
    "tor": "Raptors","toronto": "Raptors",
    "nop": "Pelicans","new orleans":"Pelicans",
    "hou": "Rockets","houston": "Rockets",
    "sas": "Spurs",  "san antonio":"Spurs",
    "por": "Blazers","portland": "Blazers",
    "lac": "Clippers","los angeles c":"Clippers","la clippers":"Clippers",
    "pho": "Suns",   "phx": "Suns","phoenix":"Suns",
    "uta": "Jazz",   "utah": "Jazz",
}

def parse_teams(mkt: dict):
    """
    Return (team_a, team_b) from a Kalshi market dict.
    Tries yes_sub_title / no_sub_title first, then title regex.
    Returns (None, None) if parsing fails.
    """
    def clean(s):
        s = str(s).strip()
        sl = s.lower()
        for alias, full in TEAM_ALIASES.items():
            if alias in sl:
                return full
        return s.title()

    yes_sub = mkt.get("yes_sub_title", "")
    no_sub  = mkt.get("no_sub_title", "")
    if yes_sub and no_sub:
        a, b = clean(yes_sub), clean(no_sub)
        if a != b:
            return a, b

    title = mkt.get("title", "")
    # Try "A vs B", "A at B", "A @ B"
    for sep in [r"\bvs\.?\b", r"\bat\b", r"@"]:
        parts = re.split(sep, title, flags=re.IGNORECASE)
        if len(parts) >= 2:
            a = clean(parts[0].strip(" -:()"))
            b = clean(parts[1].strip(" -:()").split("(")[0].strip())
            if a and b and a != b and len(a) > 1 and len(b) > 1:
                return a, b

    return None, None

# ─────────────────────────────────────────────────────────────────────────────
# MODEL — weighted-stats win probability
# ─────────────────────────────────────────────────────────────────────────────
# 2024-25 season stats (net rating scale, updated periodically).
# Format:  "Team name": net_rating
# Net rating = points scored per 100 possessions MINUS points allowed.
# Higher is better. Elite teams run +8 to +12. Average is 0. Bad is -8 to -12.
NBA_RATINGS = {
    "Cavaliers":    14.2,
    "Thunder":      12.1,
    "Celtics":      10.8,
    "Warriors":      9.3,
    "Rockets":       8.1,
    "Pacers":        7.4,
    "Grizzlies":     6.2,
    "Nuggets":       5.8,
    "Lakers":        5.1,
    "Knicks":        4.9,
    "Bucks":         4.2,
    "76ers":         3.7,
    "Timberwolves":  3.1,
    "Heat":          2.8,
    "Kings":         2.1,
    "Clippers":      1.4,
    "Mavericks":     0.8,
    "Hawks":        -0.5,
    "Suns":         -1.2,
    "Bulls":        -1.8,
    "Nets":         -2.4,
    "Magic":        -3.1,
    "Hornets":      -3.8,
    "Raptors":      -4.2,
    "Jazz":         -5.1,
    "Spurs":        -5.8,
    "Blazers":      -6.4,
    "Pistons":      -7.1,
    "Pelicans":     -7.8,
    "Wizards":      -9.2,
}

CBB_RATINGS = {
    # KenPom-style adjusted efficiency margins (AEM)
    # Top 25-ish teams
    "Duke":         28.4, "Auburn":       26.1, "Houston":      25.8,
    "Florida":      24.9, "Alabama":      23.7, "Tennessee":    22.8,
    "Iowa St":      22.1, "Michigan St":  21.4, "Texas Tech":   20.8,
    "St John's":    20.2, "Wisconsin":    19.7, "Kentucky":     19.1,
    "Memphis":      18.6, "Purdue":       18.1, "Arizona":      17.9,
    "Ole Miss":     17.4, "Maryland":     17.1, "Michigan":     16.8,
    "Gonzaga":      16.4, "Illinois":     16.1, "Xavier":       15.8,
    "Kansas":       15.4, "UConn":        15.1, "North Carolina":14.7,
    "Texas":        14.2, "Arkansas":     13.8, "Oklahoma":     13.4,
    "BYU":          13.1, "Creighton":    12.8, "UCLA":         12.4,
    "Clemson":      12.1, "Missouri":     11.7, "Oregon":       11.4,
    "Louisville":   11.1, "Pittsburgh":   10.8, "Baylor":       10.4,
    "Wake Forest":  10.1, "Notre Dame":    9.8, "USC":           9.4,
    "Utah":          9.1, "Nebraska":      8.8, "Cincinnati":    8.4,
    "TCU":           8.1, "Virginia":      7.8, "NC State":      7.4,
    "Mississippi St":7.1, "Indiana":       6.8, "Georgetown":    6.4,
}

def _sigmoid(x):
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0

def model_prob(team_a: str, team_b: str, sport: str) -> float:
    """
    Convert net rating difference to win probability via sigmoid.
    Home-court adjustment: +3.0 rating points for the home side.
    We treat team_a as the "yes" side (home or listed first).
    """
    ratings = NBA_RATINGS if sport == "NBA" else CBB_RATINGS

    def get_rating(name):
        # Exact match first
        if name in ratings:
            return ratings[name]
        # Partial match fallback
        nl = name.lower()
        for k, v in ratings.items():
            if k.lower() in nl or nl in k.lower():
                return v
        return 0.0   # unknown team — league average

    ra = get_rating(team_a)
    rb = get_rating(team_b)

    # Home-court bump: assume team_a is home (listed first in Kalshi title)
    # This adds a modest tilt; your picks will still rely on the rating gap.
    HOME_ADJ = 2.5
    gap = (ra + HOME_ADJ) - rb

    # Scale factor: 6.0 means a 6-point gap → ~73% win prob
    return _sigmoid(gap / 6.0)

# ─────────────────────────────────────────────────────────────────────────────
# PICK GENERATION
# ─────────────────────────────────────────────────────────────────────────────
def make_picks(markets: list, sport: str, min_edge: float) -> list:
    picks = []
    for mkt in markets:
        kp = kalshi_prob(mkt)
        if kp is None:
            continue

        team_a, team_b = parse_teams(mkt)
        if not team_a or not team_b:
            continue

        # Model probabilities
        mp_a = model_prob(team_a, team_b, sport)
        mp_b = 1.0 - mp_a

        # Market probabilities
        kp_a = kp
        kp_b = 1.0 - kp

        edge_a = mp_a - kp_a
        edge_b = mp_b - kp_b

        # Pick the better edge side
        if edge_a >= edge_b:
            pick, opp, mp, kp_side, edge = team_a, team_b, mp_a, kp_a, edge_a
        else:
            pick, opp, mp, kp_side, edge = team_b, team_a, mp_b, kp_b, edge_b

        if edge < min_edge:
            continue

        if edge >= 0.10 and mp >= 0.65:
            tier = "STRONG"
        elif edge >= 0.05 and mp >= 0.58:
            tier = "LEAN"
        else:
            tier = "WATCH"

        picks.append({
            "pick":      pick,
            "opp":       opp,
            "model":     mp,
            "kalshi":    kp_side,
            "edge":      edge,
            "tier":      tier,
            "american":  to_american(kp_side),
            "title":     mkt.get("title", ""),
            "ticker":    mkt.get("ticker", ""),
        })

    picks.sort(key=lambda x: x["edge"], reverse=True)
    return picks

# ─────────────────────────────────────────────────────────────────────────────
# PICK TRACKER
# ─────────────────────────────────────────────────────────────────────────────
def load_picks():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_picks(p):
    try:
        with open(TRACKER_FILE, "w") as f:
            json.dump(p, f, indent=2)
    except Exception:
        pass

def a2d(ml):
    try:
        ml = float(ml)
        return ml/100+1 if ml > 0 else 100/abs(ml)+1
    except Exception:
        return 1.91

def summary(picks, sport=None):
    f = [p for p in picks if not sport or p.get("sport","").upper()==sport.upper()]
    s = [p for p in f if p.get("result") in ("W","L","P")]
    wins = len([p for p in s if p["result"]=="W"])
    pl   = sum(
        (a2d(p.get("odds"))-1)*float(p.get("units",1)) if p["result"]=="W"
        else (-float(p.get("units",1)) if p["result"]=="L" else 0)
        for p in s
    )
    wgr = sum(float(p.get("units",1)) for p in s)
    return {
        "wins":     wins,
        "losses":   len([p for p in s if p["result"]=="L"]),
        "hit":      round(wins/len(s)*100,1) if s else 0.0,
        "pl":       round(pl,2),
        "roi":      round(pl/wgr*100,1) if wgr else 0.0,
    }

# ─────────────────────────────────────────────────────────────────────────────
# RENDER A PICK CARD
# ─────────────────────────────────────────────────────────────────────────────
def tier_badge(tier):
    if tier == "STRONG":
        return '<span class="badge-strong">🔥 Strong Pick</span>'
    if tier == "LEAN":
        return '<span class="badge-lean">🎯 Lean</span>'
    return '<span class="badge-market">👀 Watch</span>'

def explain_pick(pick_name, opp_name, model_p, kalshi_p, edge, sport):
    """Plain-English explanation for beginner bettors."""
    diff = abs(model_p - kalshi_p) * 100
    market_side = "favored" if kalshi_p >= 0.5 else "underdog"
    model_conf  = "strongly" if model_p >= 0.70 else ("moderately" if model_p >= 0.60 else "slightly")

    lines = [
        f"**Why {pick_name}?** Our model {model_conf} likes {pick_name} "
        f"({pct(model_p)} win chance) vs. Kalshi's market ({pct(kalshi_p)}).",
        f"That's a **{diff:.0f}-point edge** — the market may be underrating {pick_name}.",
    ]
    if sport == "NBA":
        lines.append("Based on: net rating (points scored vs. allowed per 100 possessions).")
    else:
        lines.append("Based on: adjusted efficiency margin (KenPom-style power rating).")
    return " ".join(lines)

def render_card(p, sport):
    tier   = p["tier"]
    css    = "strong-pick" if tier=="STRONG" else ("lean-pick" if tier=="LEAN" else "")
    bar_w  = int(p["model"] * 100)
    explanation = explain_pick(p["pick"], p["opp"], p["model"], p["kalshi"], p["edge"], sport)

    st.markdown(f"""
<div class="card {css}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
    <div>
      <span style="font-size:1.2rem;font-weight:800">{p['pick']}</span>
      <span style="color:#5a6478;font-size:0.9rem"> vs {p['opp']}</span>
    </div>
    {tier_badge(tier)}
  </div>

  <div style="display:flex;gap:32px;margin:12px 0 10px 0">
    <div>
      <div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">MODEL WIN PROB</div>
      <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#7eeaff;font-weight:700">{pct(p['model'])}</div>
    </div>
    <div>
      <div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">KALSHI LINE</div>
      <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#e8eaf0;font-weight:700">{pct(p['kalshi'])}</div>
    </div>
    <div>
      <div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">EDGE</div>
      <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#4ade80;font-weight:700">+{pct(p['edge'])}</div>
    </div>
    <div>
      <div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">AMERICAN ODDS</div>
      <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#facc15;font-weight:700">{p['american']}</div>
    </div>
  </div>

  <div class="prob-bar-bg"><div class="prob-bar-fill" style="width:{bar_w}%"></div></div>

  <div style="color:#8892a4;font-size:0.80rem;line-height:1.5">{explanation}</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
st.session_state.setdefault("sport",    "NBA")
st.session_state.setdefault("min_edge", 3)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
all_picks = load_picks()

with st.sidebar:
    st.markdown("### 🏆 Betting Dashboard")
    st.caption(f"{today_eastern().strftime('%A, %B %d')} · {now_eastern()}")
    st.divider()

    sport = st.radio("Sport", ["NBA", "CBB"], index=0, label_visibility="collapsed",
                     key="sport_radio")
    st.session_state["sport"] = sport
    st.divider()

    st.session_state["min_edge"] = st.slider(
        "Min Edge %",
        min_value=0, max_value=20,
        value=st.session_state["min_edge"], step=1,
        help="Edge = Model Win% − Kalshi Market%. Higher = fewer but stronger picks."
    )
    st.caption("🔵 Model updates with each season. Kalshi lines refresh every 10 min.")
    st.divider()

    summ = summary(all_picks)
    pl_col = "#4ade80" if summ["pl"] >= 0 else "#f87171"
    st.markdown(f"""
<div style="background:#131929;border:1px solid #1e2a45;border-radius:10px;padding:12px 16px">
  <div style="font-size:0.70rem;color:#8892a4;margin-bottom:6px">📈 ALL-TIME RECORD</div>
  <div style="font-size:1.1rem;font-weight:800">{summ['wins']}-{summ['losses']} <span style="font-size:0.80rem;color:#8892a4">({summ['hit']}%)</span></div>
  <div style="font-family:'DM Mono',monospace;color:{pl_col};font-size:0.90rem;margin-top:4px">{'+' if summ['pl']>=0 else ''}{summ['pl']}u · ROI {summ['roi']}%</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# FETCH MARKETS
# ─────────────────────────────────────────────────────────────────────────────
sport         = st.session_state["sport"]
min_edge_pct  = st.session_state["min_edge"] / 100.0
series_list   = tuple(NBA_SERIES if sport == "NBA" else CBB_SERIES)

with st.spinner(f"Loading {sport} markets from Kalshi…"):
    result = fetch_kalshi_markets(series_list)

markets     = result["markets"]
series_used = result["series_used"]
fetch_ok    = result["ok"]
fetch_err   = result["error"]

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    f"### {'🏀' if sport in ('NBA','CBB') else '🏆'} {sport} · "
    f"{today_eastern().strftime('%b %d, %Y')}"
)

if not fetch_ok or not markets:
    st.error(
        f"**Couldn't load {sport} markets from Kalshi.**\n\n"
        f"Tried series: {', '.join(series_list)}\n\n"
        f"Error: {fetch_err}\n\n"
        "This usually means:\n"
        "- No games today / Kalshi hasn't opened tonight's markets yet (try after noon ET)\n"
        "- The Kalshi API changed their series ticker name\n\n"
        "Check the **Raw Markets** tab to see what the API is returning."
    )
    tabs = st.tabs(["📋 Raw Markets", "📈 Tracker"])
    with tabs[0]:
        # Diagnostic: show bare API response with NO filters
        st.markdown("#### Diagnostic — Unfiltered API call")
        with st.spinner("Running diagnostic…"):
            r = kalshi_get("/markets", {"status": "open", "limit": 10})
        if r and r.status_code == 200:
            sample = r.json().get("markets", [])
            if sample:
                st.success(f"API is up. {len(sample)} sample markets (unfiltered):")
                st.dataframe(pd.DataFrame([{
                    "ticker": m.get("ticker",""),
                    "title":  m.get("title","")[:80],
                    "yes_bid":m.get("yes_bid"),
                    "yes_ask":m.get("yes_ask"),
                    "close":  m.get("close_time",""),
                } for m in sample]), use_container_width=True, hide_index=True)
                st.info("👆 Look at the ticker column — the series name is the part before the first dash. Use that to update the NBA_SERIES/CBB_SERIES list at the top of app.py.")
            else:
                st.warning("API is up but returned 0 markets even without filters.")
        elif r:
            st.error(f"API error: {r.status_code} {r.text[:200]}")
        else:
            st.error("Could not reach Kalshi API at all (timeout).")

    with tabs[1]:
        st.markdown("#### 📈 Pick Tracker")
        sport_summ = summary(all_picks, sport)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Record",   f"{sport_summ['wins']}-{sport_summ['losses']}")
        c2.metric("Hit Rate", f"{sport_summ['hit']}%")
        c3.metric("P&L",      f"{'+' if sport_summ['pl']>=0 else ''}{sport_summ['pl']}u")
        c4.metric("ROI",      f"{'+' if sport_summ['roi']>=0 else ''}{sport_summ['roi']}%")

    st.stop()

# Build picks
picks = make_picks(markets, sport, min_edge_pct)
strong = [p for p in picks if p["tier"]=="STRONG"]
lean   = [p for p in picks if p["tier"]=="LEAN"]
watch  = [p for p in picks if p["tier"]=="WATCH"]

tabs = st.tabs([
    f"🗓️ Picks ({len(picks)})",
    f"📋 All Markets ({len(markets)})",
    "📈 Tracker",
    "❓ How it works",
])

# ── PICKS TAB ────────────────────────────────────────────────────────────────
with tabs[0]:
    if not picks:
        st.info(
            f"No picks meet the current **{st.session_state['min_edge']}% edge** threshold.\n\n"
            "Try lowering the **Min Edge %** slider in the sidebar, "
            "or check back later when tonight's games open on Kalshi."
        )
    else:
        # Beginner glossary
        with st.expander("📖 What do these numbers mean?", expanded=False):
            st.markdown("""
**Model Win %** — Our statistical model's estimate of how likely this team is to win,
based on how well they score and defend per possession this season.

**Kalshi Line** — The crowd's prediction on Kalshi's market, expressed as a probability.
This is equivalent to the "implied probability" you'd find at a sportsbook.

**Edge** — The gap between what our model thinks and what the market thinks.
A positive edge means our model believes the team is *more likely to win* than the market does.

**American Odds** — The Kalshi line converted to traditional sportsbook format.
`-150` means bet $150 to win $100. `+130` means bet $100 to win $130.

**Tiers:**
- 🔥 **Strong** — Edge ≥ 10% and model confidence ≥ 65%. High conviction.
- 🎯 **Lean** — Edge ≥ 5% and model confidence ≥ 58%. Moderate conviction.
- 👀 **Watch** — Smaller edge but worth monitoring.
""")

        if strong:
            st.markdown("#### 🔥 Strong Picks")
            for p in strong:
                render_card(p, sport)
        if lean:
            st.markdown("#### 🎯 Leans")
            for p in lean:
                render_card(p, sport)
        if watch:
            st.markdown("#### 👀 Watch List")
            for p in watch[:5]:
                render_card(p, sport)

# ── ALL MARKETS TAB ───────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown(f"#### All {sport} markets from Kalshi")
    st.caption(f"Series used: `{series_used}` · {len(markets)} markets")
    rows = []
    for m in markets:
        ta, tb = parse_teams(m)
        kp     = kalshi_prob(m)
        rows.append({
            "Ticker":    m.get("ticker",""),
            "Title":     (m.get("title",""))[:70],
            "Team A":    ta or "—",
            "Team B":    tb or "—",
            "Kalshi %":  f"{kp*100:.0f}%" if kp else "—",
            "American":  to_american(kp) if kp else "—",
            "Close":     m.get("close_time","")[:16],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── TRACKER TAB ───────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown("#### 📈 Pick Tracker")
    sport_summ = summary(all_picks, sport)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Record",   f"{sport_summ['wins']}-{sport_summ['losses']}")
    c2.metric("Hit Rate", f"{sport_summ['hit']}%")
    c3.metric("P&L",      f"{'+' if sport_summ['pl']>=0 else ''}{sport_summ['pl']}u")
    c4.metric("ROI",      f"{'+' if sport_summ['roi']>=0 else ''}{sport_summ['roi']}%")
    st.divider()

    with st.expander("➕ Log a pick"):
        b_team  = st.text_input("Team you're picking")
        b_opp   = st.text_input("Opponent")
        b_odds  = st.text_input("Odds (e.g. -150 or +120)", "")
        b_units = st.number_input("Units", 0.1, 10.0, 0.5, 0.25)
        b_notes = st.text_input("Notes (optional)", "")
        if st.button("Save Pick"):
            if b_team:
                all_picks.append({
                    "date":   today_eastern().isoformat(),
                    "sport":  sport,
                    "team":   b_team,
                    "opp":    b_opp,
                    "odds":   b_odds,
                    "units":  b_units,
                    "notes":  b_notes,
                    "result": "Pending",
                })
                save_picks(all_picks)
                st.success("Saved!")
                st.rerun()
            else:
                st.error("Enter the team name.")

    if all_picks:
        dfp = pd.DataFrame(all_picks)
        ed  = st.data_editor(
            dfp, use_container_width=True, num_rows="dynamic",
            column_config={"result": st.column_config.SelectboxColumn(
                "Result", options=["Pending","W","L","P"]
            )},
        )
        if st.button("Save Results"):
            save_picks(ed.to_dict("records"))
            st.success("Updated.")
            st.rerun()

# ── HOW IT WORKS TAB ─────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown("""
### ❓ How This App Works

#### Where do the odds come from?
All odds come directly from **Kalshi** — a regulated U.S. prediction market.
Kalshi lets people trade on sports outcomes like stocks, so the prices reflect real money
and what the crowd actually believes will happen.

#### What is the model?
Our model uses **net rating** (NBA) and **adjusted efficiency margin** (CBB) — the same
stats used by ESPN and professional analysts — to estimate each team's true win probability.

- **Net rating** = points scored per 100 possessions minus points allowed. The best teams are around +10, the worst around -10.
- We also add a small **home-court adjustment** (+2.5 points) for the home team.

#### What is Edge?
Edge = **(Model Win%)** − **(Kalshi Market%)**.

If our model says a team has a 62% chance of winning, but Kalshi is pricing them at 50%,
the edge is **+12%**. That gap is where value bets come from.

#### What do the tiers mean?
| Tier | Edge | Model Confidence | Meaning |
|------|------|-----------------|---------|
| 🔥 Strong | ≥ 10% | ≥ 65% | High conviction — model strongly disagrees with the market |
| 🎯 Lean | ≥ 5% | ≥ 58% | Moderate conviction — worth considering |
| 👀 Watch | < 5% | Any | Small edge — monitor but don't bet heavy |

#### Important Disclaimer
This app is for educational and entertainment purposes. No model is perfect.
Always bet responsibly and only what you can afford to lose.
""")
