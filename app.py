# coding: utf-8
"""
Sports Betting Dashboard v5.1
FIXES:
1. Fetch status=open AND status=unopened (NBA games listed before tipoff are "unopened")
2. Use mve_filter=exclude to strip ALL combo/parlay markets server-side — no client filtering needed
3. Simplified team matching — Kalshi uses city OR nickname in titles
"""

import streamlit as st
import requests
import pandas as pd
import math, json, os, re
from datetime import datetime, timedelta, timezone

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Betting Dashboard", page_icon="🏆",
                   layout="wide", initial_sidebar_state="expanded")
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
.badge-watch{display:inline-block;background:#1e2640;color:#94a3b8;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.prob-bar-bg{background:#1e2640;border-radius:8px;height:10px;width:100%;margin:4px 0 12px 0;}
.prob-bar-fill{background:linear-gradient(90deg,#1a6fff,#7eeaff);border-radius:8px;height:10px;}
hr{border-color:#1e2640!important;}
#MainMenu,footer{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
KALSHI_BASE  = "https://api.elections.kalshi.com/trade-api/v2"
TRACKER_FILE = "picks_log.json"

# Every NBA team: canonical name → list of strings Kalshi might use in titles
NBA_TEAMS = {
    "Cavaliers":    ["cavaliers","cleveland"],
    "Thunder":      ["thunder","oklahoma city","oklahoma"],
    "Celtics":      ["celtics","boston"],
    "Warriors":     ["warriors","golden state"],
    "Rockets":      ["rockets","houston"],
    "Pacers":       ["pacers","indiana"],
    "Grizzlies":    ["grizzlies","memphis"],
    "Nuggets":      ["nuggets","denver"],
    "Lakers":       ["lakers","los angeles l","lal"],
    "Knicks":       ["knicks","new york"],
    "Bucks":        ["bucks","milwaukee"],
    "76ers":        ["76ers","sixers","philadelphia"],
    "Timberwolves": ["timberwolves","minnesota"],
    "Heat":         ["heat","miami"],
    "Kings":        ["kings","sacramento"],
    "Clippers":     ["clippers","los angeles c","lac"],
    "Mavericks":    ["mavericks","dallas"],
    "Hawks":        ["hawks","atlanta"],
    "Suns":         ["suns","phoenix"],
    "Bulls":        ["bulls","chicago"],
    "Nets":         ["nets","brooklyn"],
    "Magic":        ["magic","orlando"],
    "Hornets":      ["hornets","charlotte"],
    "Raptors":      ["raptors","toronto"],
    "Jazz":         ["jazz","utah"],
    "Spurs":        ["spurs","san antonio"],
    "Trail Blazers":["trail blazers","blazers","portland"],
    "Pistons":      ["pistons","detroit"],
    "Pelicans":     ["pelicans","new orleans"],
    "Wizards":      ["wizards","washington"],
}

CBB_TEAMS = {
    "Duke":["duke"], "Auburn":["auburn"], "Tennessee":["tennessee"],
    "Alabama":["alabama"], "Houston":["houston cougars","houston (ncaa)"],
    "Florida":["florida gators","florida (ncaa)"], "Kentucky":["kentucky"],
    "Iowa State":["iowa st","iowa state"], "Michigan State":["michigan st","michigan state"],
    "Texas Tech":["texas tech"], "Wisconsin":["wisconsin"],
    "Purdue":["purdue"], "Arizona":["arizona wildcats","arizona (ncaa)"],
    "Maryland":["maryland"], "Michigan":["michigan wolverines","michigan (ncaa)"],
    "Gonzaga":["gonzaga"], "Illinois":["illinois"], "Kansas":["kansas"],
    "UConn":["uconn","connecticut"], "Marquette":["marquette"],
    "Creighton":["creighton"], "UCLA":["ucla"], "Baylor":["baylor"],
    "Arkansas":["arkansas"], "St John's":["st john","st. john","saint john"],
    "Xavier":["xavier"], "Ole Miss":["ole miss"],
    "North Carolina":["north carolina","unc"],
    "NC State":["nc state","n.c. state"],
    "BYU":["byu","brigham young"], "Clemson":["clemson"],
    "Notre Dame":["notre dame"], "Georgetown":["georgetown"],
    "Villanova":["villanova"], "Cincinnati":["cincinnati bearcats"],
}

# Build flat lookup: variant → canonical
def build_lookup(teams_dict):
    lkp = {}
    for canon, variants in teams_dict.items():
        lkp[canon.lower()] = canon
        for v in variants:
            lkp[v.lower()] = canon
    return lkp

NBA_LOOKUP = build_lookup(NBA_TEAMS)
CBB_LOOKUP = build_lookup(CBB_TEAMS)

# ─── TIME HELPERS ─────────────────────────────────────────────────────────────
def _is_edt():
    dt = datetime.utcnow()
    y  = dt.year
    mar = datetime(y,3,8)
    while mar.weekday()!=6: mar+=timedelta(days=1)
    nov = datetime(y,11,1)
    while nov.weekday()!=6: nov+=timedelta(days=1)
    return mar<=dt<nov

def now_eastern():
    off = timedelta(hours=-4 if _is_edt() else -5)
    est = datetime.utcnow()+off
    return est.strftime(f"{str(int(est.strftime('%I')))}:%M %p ")+("EDT" if _is_edt() else "EST")

def today_eastern():
    off = timedelta(hours=-4 if _is_edt() else -5)
    return (datetime.utcnow()+off).date()

def pct(x):   return f"{x*100:.0f}%" if x is not None else "—"
def to_am(p):
    if not p or p<=0.01 or p>=0.99: return "—"
    return f"-{round((p/(1-p))*100)}" if p>=0.5 else f"+{round(((1-p)/p)*100)}"

# ─── KALSHI FETCH ─────────────────────────────────────────────────────────────
def _fetch_page(status: str, cursor=None):
    params = {
        "status":     status,
        "limit":      200,
        "mve_filter": "exclude",   # ← KEY FIX: strips all combo/parlay markets server-side
    }
    if cursor:
        params["cursor"] = cursor
    try:
        r = requests.get(f"{KALSHI_BASE}/markets", params=params, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_markets() -> dict:
    """
    Fetch non-combo markets in two passes: open + unopened status.
    NBA game-winner markets may be 'unopened' until shortly before tip.
    mve_filter=exclude removes all KXMVECROSSCATEGORY combo markets server-side.
    """
    markets = []
    errors  = []

    for status in ["open", "unopened"]:
        cursor = None
        for _ in range(15):   # up to 3000 per status
            data = _fetch_page(status, cursor)
            if data is None:
                errors.append(f"Fetch failed ({status})")
                break
            chunk  = data.get("markets", [])
            markets.extend(chunk)
            cursor = data.get("cursor")
            if not cursor or not chunk:
                break

    return {
        "markets": markets,
        "error":   "; ".join(errors) if errors else "",
        "count":   len(markets),
    }

@st.cache_data(ttl=60, show_spinner=False)
def fetch_diagnostic():
    """Raw unfiltered call for the debug tab."""
    try:
        r = requests.get(f"{KALSHI_BASE}/markets",
                         params={"status":"open","limit":20}, timeout=15)
        if r.status_code==200:
            return {"ok":True,"markets":r.json().get("markets",[]),"error":""}
        return {"ok":False,"markets":[],"error":f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok":False,"markets":[],"error":str(e)}

# ─── TEAM MATCHING ────────────────────────────────────────────────────────────
def find_team(text: str, lookup: dict):
    """Return canonical team name if found in text, else None."""
    tl = text.lower().strip()
    # Longest variant first to prevent partial matches
    for variant in sorted(lookup.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(variant) + r'\b', tl):
            return lookup[variant]
    return None

def get_teams(m: dict, lookup: dict):
    """
    Extract two distinct team names from a market dict.
    Tries: yes_sub_title/no_sub_title → title regex → combined brute-force.
    """
    yes_sub = (m.get("yes_sub_title") or "").strip()
    no_sub  = (m.get("no_sub_title")  or "").strip()

    # Primary: sub-titles (most reliable — Kalshi puts team there directly)
    if yes_sub and no_sub:
        ta = find_team(yes_sub, lookup)
        tb = find_team(no_sub, lookup)
        if ta and tb and ta != tb:
            return ta, tb

    # Secondary: parse title
    title = (m.get("title") or "")
    for pat in [
        r"will\s+(?:the\s+)?(.+?)\s+win",
        r"(.+?)\s+(?:vs?\.?|at|@|versus)\s+(.+?)(?:\?|$|\s*[-–(])",
    ]:
        hit = re.search(pat, title, re.IGNORECASE)
        if hit:
            ta = find_team(hit.group(1).strip(), lookup)
            if ta:
                if len(hit.groups()) >= 2:
                    tb = find_team(hit.group(2).strip().split("(")[0], lookup)
                    if tb and tb != ta:
                        return ta, tb
                # For "Will X win?" grab opponent from sub_titles
                for sub in [yes_sub, no_sub]:
                    tb = find_team(sub, lookup)
                    if tb and tb != ta:
                        return ta, tb

    # Fallback: find any 2 distinct teams in all text combined
    combined = f"{title} {yes_sub} {no_sub}"
    found = []
    for variant in sorted(lookup.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(variant) + r'\b', combined.lower()):
            canon = lookup[variant]
            if canon not in found:
                found.append(canon)
        if len(found) == 2:
            return found[0], found[1]

    return None, None

def filter_game_markets(markets: list, lookup: dict):
    """Return list of (market, team_a, team_b) for single-game moneylines."""
    results = []
    for m in markets:
        # Skip markets with no pricing (no trades yet = no signal)
        # Allow last_price even if bid/ask are 0
        yb = m.get("yes_bid",0) or 0
        ya = m.get("yes_ask",0) or 0
        lp = m.get("last_price",0) or 0
        has_price = (yb>0 and ya>0) or lp>0
        if not has_price:
            continue

        ta, tb = get_teams(m, lookup)
        if ta and tb:
            results.append((m, ta, tb))
    return results

# ─── PRICE EXTRACTION ─────────────────────────────────────────────────────────
def kalshi_prob(m: dict):
    try:
        yb = m.get("yes_bid",0) or 0
        ya = m.get("yes_ask",0) or 0
        lp = m.get("last_price",0) or 0
        if yb>0 and ya>0: return (yb+ya)/200.0
        if lp>0:          return lp/100.0
    except: pass
    return None

# ─── MODEL ────────────────────────────────────────────────────────────────────
NBA_RATINGS = {
    "Cavaliers":14.2,"Thunder":12.1,"Celtics":10.8,"Warriors":9.3,
    "Rockets":8.1,"Pacers":7.4,"Grizzlies":6.2,"Nuggets":5.8,
    "Lakers":5.1,"Knicks":4.9,"Bucks":4.2,"76ers":3.7,
    "Timberwolves":3.1,"Heat":2.8,"Kings":2.1,"Clippers":1.4,
    "Mavericks":0.8,"Hawks":-0.5,"Suns":-1.2,"Bulls":-1.8,
    "Nets":-2.4,"Magic":-3.1,"Hornets":-3.8,"Raptors":-4.2,
    "Jazz":-5.1,"Spurs":-5.8,"Trail Blazers":-6.4,
    "Pistons":-7.1,"Pelicans":-7.8,"Wizards":-9.2,
}
CBB_RATINGS = {
    "Duke":28.4,"Auburn":26.1,"Houston":25.8,"Florida":24.9,
    "Alabama":23.7,"Tennessee":22.8,"Iowa State":22.1,"Michigan State":21.4,
    "Texas Tech":20.8,"St John's":20.2,"Wisconsin":19.7,"Kentucky":19.1,
    "Memphis":18.6,"Purdue":18.1,"Arizona":17.9,"Ole Miss":17.4,
    "Maryland":17.1,"Michigan":16.8,"Gonzaga":16.4,"Illinois":16.1,
    "Xavier":15.8,"Kansas":15.4,"UConn":15.1,"North Carolina":14.7,
    "Texas":14.2,"Arkansas":13.8,"Marquette":13.0,"BYU":13.1,
    "Creighton":12.8,"UCLA":12.4,"Clemson":12.1,"Baylor":10.4,
    "Notre Dame":9.8,"Georgetown":9.0,"NC State":11.0,"Villanova":11.5,
    "Cincinnati":9.5,
}

def _sig(x):
    try: return 1/(1+math.exp(-x))
    except: return 0.5

def get_rating(team, sport):
    r = NBA_RATINGS if sport=="NBA" else CBB_RATINGS
    if team in r: return r[team]
    tl = team.lower()
    for k,v in r.items():
        if k.lower() in tl or tl in k.lower(): return v
    return 0.0

def model_win_prob(ta, tb, sport):
    """ta = YES side. +2.5 home-court for ta."""
    return _sig((get_rating(ta,sport)+2.5-get_rating(tb,sport))/6.0)

# ─── PICKS ────────────────────────────────────────────────────────────────────
def make_picks(game_markets, sport, min_edge):
    picks = []
    for m, ta, tb in game_markets:
        kp = kalshi_prob(m)
        if kp is None: continue
        mp_a = model_win_prob(ta, tb, sport)
        mp_b = 1.0 - mp_a
        kp_a, kp_b = kp, 1.0-kp
        ea, eb = mp_a-kp_a, mp_b-kp_b
        if ea>=eb: pick,opp,mp,kp_s,edge = ta,tb,mp_a,kp_a,ea
        else:      pick,opp,mp,kp_s,edge = tb,ta,mp_b,kp_b,eb
        if edge < min_edge: continue
        tier = ("STRONG" if edge>=0.10 and mp>=0.65
                else "LEAN" if edge>=0.05 and mp>=0.58
                else "WATCH")
        picks.append({"pick":pick,"opp":opp,"model":mp,"kalshi":kp_s,
                      "edge":edge,"tier":tier,"american":to_am(kp_s),
                      "title":m.get("title",""),"ticker":m.get("ticker",""),
                      "status":m.get("status","")})
    picks.sort(key=lambda x: x["edge"], reverse=True)
    return picks

# ─── TRACKER ──────────────────────────────────────────────────────────────────
def load_picks():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE) as f: return json.load(f)
        except: pass
    return []

def save_picks(p):
    try:
        with open(TRACKER_FILE,"w") as f: json.dump(p,f,indent=2)
    except: pass

def a2d(ml):
    try:
        ml=float(ml); return ml/100+1 if ml>0 else 100/abs(ml)+1
    except: return 1.91

def summary(picks, sport=None):
    f=[p for p in picks if not sport or p.get("sport","").upper()==sport.upper()]
    s=[p for p in f if p.get("result") in ("W","L","P")]
    wins=len([p for p in s if p["result"]=="W"])
    pl=sum((a2d(p.get("odds"))-1)*float(p.get("units",1)) if p["result"]=="W"
           else (-float(p.get("units",1)) if p["result"]=="L" else 0) for p in s)
    wgr=sum(float(p.get("units",1)) for p in s)
    return {"wins":wins,"losses":len([p for p in s if p["result"]=="L"]),
            "hit":round(wins/len(s)*100,1) if s else 0.0,
            "pl":round(pl,2),"roi":round(pl/wgr*100,1) if wgr else 0.0}

# ─── RENDER ───────────────────────────────────────────────────────────────────
def tier_badge(t):
    if t=="STRONG": return '<span class="badge-strong">🔥 Strong Pick</span>'
    if t=="LEAN":   return '<span class="badge-lean">🎯 Lean</span>'
    return '<span class="badge-watch">👀 Watch</span>'

def render_card(p, sport):
    bw = int(p["model"]*100)
    conf = "strongly" if p["model"]>=0.70 else ("moderately" if p["model"]>=0.60 else "slightly")
    diff = abs(p["model"]-p["kalshi"])*100
    stat_type = "net rating (points scored vs. allowed per 100 possessions)" if sport=="NBA" \
                else "adjusted efficiency margin (KenPom-style power rating)"
    expl = (f"Our model {conf} favors <b>{p['pick']}</b> "
            f"({pct(p['model'])} win chance) vs Kalshi crowd ({pct(p['kalshi'])}). "
            f"<b>{diff:.0f}pt gap</b> — market may be underrating {p['pick']}. "
            f"Based on {stat_type}.")
    css = "strong-pick" if p["tier"]=="STRONG" else ("lean-pick" if p["tier"]=="LEAN" else "")
    st.markdown(f"""
<div class="card {css}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
    <div>
      <span style="font-size:1.2rem;font-weight:800">{p['pick']}</span>
      <span style="color:#5a6478;font-size:0.9rem"> vs {p['opp']}</span>
      <span style="color:#5a6478;font-size:0.70rem;margin-left:8px">({p['status']})</span>
    </div>
    {tier_badge(p['tier'])}
  </div>
  <div style="display:flex;gap:32px;margin:12px 0 10px 0">
    <div><div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">MODEL WIN %</div>
         <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#7eeaff;font-weight:700">{pct(p['model'])}</div></div>
    <div><div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">KALSHI LINE</div>
         <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#e8eaf0;font-weight:700">{pct(p['kalshi'])}</div></div>
    <div><div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">EDGE</div>
         <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#4ade80;font-weight:700">+{pct(p['edge'])}</div></div>
    <div><div style="color:#8892a4;font-size:0.70rem;margin-bottom:2px">AMERICAN ODDS</div>
         <div style="font-family:'DM Mono',monospace;font-size:1.3rem;color:#facc15;font-weight:700">{p['american']}</div></div>
  </div>
  <div class="prob-bar-bg"><div class="prob-bar-fill" style="width:{bw}%"></div></div>
  <div style="color:#8892a4;font-size:0.80rem;line-height:1.5">{expl}</div>
</div>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
st.session_state.setdefault("sport",    "NBA")
st.session_state.setdefault("min_edge", 3)

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
all_picks = load_picks()
with st.sidebar:
    st.markdown("### 🏆 Betting Dashboard")
    st.caption(f"{today_eastern().strftime('%A, %B %d')} · {now_eastern()}")
    st.divider()
    sport = st.radio("Sport", ["NBA","CBB"], index=0, label_visibility="collapsed")
    st.session_state["sport"] = sport
    st.divider()
    st.session_state["min_edge"] = st.slider(
        "Min Edge %", 0, 20, st.session_state["min_edge"], 1,
        help="Edge = Model Win% − Kalshi Market%. 0% shows everything.")
    st.caption("Refreshes every 5 min · includes upcoming (unopened) games")
    st.divider()
    summ   = summary(all_picks)
    pl_col = "#4ade80" if summ["pl"]>=0 else "#f87171"
    st.markdown(f"""
<div style="background:#131929;border:1px solid #1e2a45;border-radius:10px;padding:12px 16px">
  <div style="font-size:0.70rem;color:#8892a4;margin-bottom:6px">📈 ALL-TIME RECORD</div>
  <div style="font-size:1.1rem;font-weight:800">{summ['wins']}-{summ['losses']} <span style="font-size:0.80rem;color:#8892a4">({summ['hit']}%)</span></div>
  <div style="font-family:'DM Mono',monospace;color:{pl_col};font-size:0.90rem;margin-top:4px">{'+' if summ['pl']>=0 else ''}{summ['pl']}u · ROI {summ['roi']}%</div>
</div>""", unsafe_allow_html=True)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
sport    = st.session_state["sport"]
min_edge = st.session_state["min_edge"] / 100.0
lookup   = NBA_LOOKUP if sport=="NBA" else CBB_LOOKUP

st.markdown(f"### {'🏀' if sport in ('NBA','CBB') else '🏆'} {sport} · {today_eastern().strftime('%b %d, %Y')}")

with st.spinner("Loading Kalshi markets…"):
    result = fetch_markets()

all_markets  = result["markets"]
fetch_error  = result["error"]
game_markets = filter_game_markets(all_markets, lookup)
picks        = make_picks(game_markets, sport, min_edge)

# Status breakdown for header
open_count     = sum(1 for m in all_markets if m.get("status")=="open")
unopened_count = sum(1 for m in all_markets if m.get("status")=="unopened")

st.caption(
    f"Kalshi: **{open_count}** open + **{unopened_count}** upcoming markets "
    f"(combos excluded) · **{len(game_markets)}** {sport} games identified · "
    f"**{len(picks)}** picks"
)
if fetch_error:
    st.warning(f"Fetch note: {fetch_error}")

tabs = st.tabs([
    f"🗓️ Picks ({len(picks)})",
    f"📋 {sport} Games ({len(game_markets)})",
    f"🔍 Raw Markets ({len(all_markets)})",
    "📈 Tracker",
    "❓ How it works",
])

# ── PICKS ─────────────────────────────────────────────────────────────────────
with tabs[0]:
    strong = [p for p in picks if p["tier"]=="STRONG"]
    lean   = [p for p in picks if p["tier"]=="LEAN"]
    watch  = [p for p in picks if p["tier"]=="WATCH"]

    if not picks:
        no_game_msg = (
            f"No {sport} games identified yet in Kalshi's markets.\n\n"
            "Kalshi typically opens game-winner markets a few hours before tip-off. "
            "Check the **Raw Markets** tab to see what's currently available, "
            "and check back closer to game time (usually 3–6pm ET)."
            if not game_markets else
            f"No picks meet the **{st.session_state['min_edge']}% edge** threshold. "
            "Lower the Min Edge % slider in the sidebar to see all games."
        )
        st.info(no_game_msg)
    else:
        with st.expander("📖 What do these numbers mean?", expanded=False):
            st.markdown("""
**Model Win %** — Based on season stats (net rating for NBA, efficiency margin for CBB).

**Kalshi Line** — What real money is trading at on Kalshi (crowd's implied probability).

**Edge** — Model % minus Kalshi %. Positive = we think the team is underpriced by the market.

**American Odds** — Traditional format. `-150` = bet $150 to win $100. `+130` = bet $100 to win $130.

🔥 **Strong** = Edge ≥10%, Model ≥65% · 🎯 **Lean** = Edge ≥5%, Model ≥58% · 👀 **Watch** = smaller edge
""")
        if strong:
            st.markdown("#### 🔥 Strong Picks")
            for p in strong: render_card(p, sport)
        if lean:
            st.markdown("#### 🎯 Leans")
            for p in lean: render_card(p, sport)
        if watch:
            st.markdown("#### 👀 Watch List")
            for p in watch[:6]: render_card(p, sport)

# ── GAMES TAB ────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown(f"#### {sport} game markets found")
    if not game_markets:
        st.warning(
            f"0 {sport} games found in {len(all_markets)} non-combo Kalshi markets. "
            "Check Raw Markets tab — if you see NBA team names there, the team matcher "
            "needs updating. Otherwise games haven't been listed yet today."
        )
        # Show a sample of what we DO have so user can debug
        if all_markets:
            st.markdown("**Sample of what Kalshi has right now:**")
            for m in all_markets[:8]:
                st.code(
                    f"Title:   {m.get('title','')}\n"
                    f"Yes sub: {m.get('yes_sub_title','')}\n"
                    f"No sub:  {m.get('no_sub_title','')}\n"
                    f"Status:  {m.get('status','')}  Ticker: {m.get('ticker','')[:40]}"
                )
    else:
        rows=[]
        for m,ta,tb in game_markets:
            kp=kalshi_prob(m)
            mp=model_win_prob(ta,tb,sport)
            rows.append({
                "Match":    f"{ta} vs {tb}",
                "Status":   m.get("status",""),
                "Kalshi %": pct(kp) if kp else "—",
                "Model %":  pct(mp),
                "Edge":     f"{(mp-(kp or 0.5))*100:+.1f}%",
                "American": to_am(kp) if kp else "—",
                "Ticker":   m.get("ticker","")[:45],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── RAW MARKETS ──────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown(f"#### Raw Kalshi markets ({len(all_markets)}, combos excluded)")
    st.caption("mve_filter=exclude already strips combo/parlay markets server-side")
    if all_markets:
        raw=[{
            "status":  m.get("status",""),
            "ticker":  m.get("ticker","")[:50],
            "title":   (m.get("title",""))[:80],
            "yes_sub": (m.get("yes_sub_title","") or "")[:40],
            "no_sub":  (m.get("no_sub_title","") or "")[:40],
            "yes_bid": m.get("yes_bid"),
            "yes_ask": m.get("yes_ask"),
            "last":    m.get("last_price"),
        } for m in all_markets[:300]]
        st.dataframe(pd.DataFrame(raw), use_container_width=True, hide_index=True)

# ── TRACKER ──────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown("#### 📈 Pick Tracker")
    ss=summary(all_picks,sport)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Record",  f"{ss['wins']}-{ss['losses']}")
    c2.metric("Hit Rate",f"{ss['hit']}%")
    c3.metric("P&L",     f"{'+' if ss['pl']>=0 else ''}{ss['pl']}u")
    c4.metric("ROI",     f"{'+' if ss['roi']>=0 else ''}{ss['roi']}%")
    st.divider()
    with st.expander("➕ Log a pick"):
        bt=st.text_input("Team you're picking")
        bo=st.text_input("Opponent")
        bx=st.text_input("Odds (e.g. -150 or +120)","")
        bu=st.number_input("Units",0.1,10.0,0.5,0.25)
        bn=st.text_input("Notes (optional)","")
        if st.button("Save Pick"):
            if bt:
                all_picks.append({"date":today_eastern().isoformat(),"sport":sport,
                    "team":bt,"opp":bo,"odds":bx,"units":bu,"notes":bn,"result":"Pending"})
                save_picks(all_picks); st.success("Saved!"); st.rerun()
            else: st.error("Enter the team name.")
    if all_picks:
        dfp=pd.DataFrame(all_picks)
        ed=st.data_editor(dfp,use_container_width=True,num_rows="dynamic",
            column_config={"result":st.column_config.SelectboxColumn(
                "Result",options=["Pending","W","L","P"])})
        if st.button("Save Results"):
            save_picks(ed.to_dict("records")); st.success("Updated."); st.rerun()

# ── HOW IT WORKS ─────────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown("""
### ❓ How This App Works

**Where do the odds come from?**
All lines come from **Kalshi** — a CFTC-regulated U.S. prediction market where real money trades on game outcomes.

**What is the model?**
- **NBA**: Net rating = points scored minus points allowed per 100 possessions. Best teams ~+12, worst ~-9.
- **CBB**: Adjusted efficiency margin (similar to KenPom). Both include a +2.5pt home-court adjustment.

**What is Edge?** Model Win% minus Kalshi Market%. Positive = our model thinks the team is underpriced.

| Tier | Edge | Model Confidence | Meaning |
|------|------|-----------------|---------|
| 🔥 Strong | ≥10% | ≥65% | High conviction bet |
| 🎯 Lean | ≥5% | ≥58% | Worth considering |
| 👀 Watch | <5% | Any | Monitor, don't bet heavy |

*For educational/entertainment purposes only. Bet responsibly.*
""")
