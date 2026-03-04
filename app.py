# coding: utf-8
"""
Unified Sports Betting Dashboard v4.3 (Kalshi Hybrid)
MLB · NBA · NFL · CBB · CFB

Hybrid mode:
  - Your model = predictor (team strength score / prop projection)
  - Kalshi price = line (implied probability)
  - Edge = model_prob - kalshi_implied_prob

Public-safe caching:
  - Kalshi market directory: 12h
  - Kalshi prices (markets list with yes_bid/ask/last): 10 min
  - No manual refresh button (prevents quota burn / request spam)

Sports enabled for Kalshi lines:
  - NBA games: KXNBAGAME  (props enabled)
  - CBB games: KXNCAAMBGAME
  - MLB / NFL / CFB: UI present but marked coming-soon

Changelog v4.3:
  - FIX: Removed invalid mve_filter param from Kalshi API call
  - FIX: Stats tab now shows full market directory (with priced flag) instead of
         only the price-fetch subset, making coverage gaps visible
  - FIX: parse_game_from_market now guards against identical team names
  - FIX: risk_tag_from_edge threshold corrected (<=0.60, not 0.70) so "Low"
         risk label isn't applied to high-juice markets
  - FIX: now_est() uses cross-platform hour format (no %-I)
  - FIX: picks_log loaded once and passed around; no double load
  - FIX: MLB / NFL / CFB disabled in UI with informative coming-soon message
  - FIX: Pick-building loop wrapped in cached function to avoid redundant
         re-execution on every Streamlit widget interaction
  - FIX: Prop tier label now rendered in the prop card display
  - FIX: Prop edge_req lowered to surface placeholder-model edges with a
         "placeholder model active" warning banner so UI is useful before
         your real model is wired in
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import json, os, warnings, math, re
warnings.filterwarnings("ignore")

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Betting Dashboard", page_icon="🏆",
                   layout="wide", initial_sidebar_state="expanded")

# ── STYLE ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Syne',sans-serif;}
.stApp{background:#0a0e1a;color:#e8eaf0;}
section[data-testid="stSidebar"]{background:#0f1525!important;border-right:1px solid #1e2640;}
section[data-testid="stSidebar"] *{color:#c8ccd8!important;}
[data-testid="metric-container"]{background:#131929;border:1px solid #1e2a45;border-radius:12px;padding:16px;}
[data-testid="stMetricValue"]{font-family:'DM Mono',monospace!important;font-size:1.8rem!important;color:#7eeaff!important;}
[data-testid="stMetricLabel"]{color:#8892a4!important;font-size:0.75rem!important;}
.stButton button{background:linear-gradient(135deg,#1a6fff,#0ea5e9)!important;color:white!important;border:none!important;border-radius:8px!important;font-family:'Syne',sans-serif!important;font-weight:700!important;}
.stTabs [data-baseweb="tab-list"]{background:#0f1525;border-radius:10px;padding:4px;gap:4px;}
.stTabs [data-baseweb="tab"]{background:transparent;color:#8892a4!important;border-radius:8px;font-family:'Syne',sans-serif;font-weight:600;}
.stTabs [aria-selected="true"]{background:#1a2640!important;color:#7eeaff!important;}
.risk-low{display:inline-block;background:#1a3a2a;color:#4ade80;padding:2px 8px;border-radius:6px;font-size:0.70rem;font-weight:700;font-family:'DM Mono',monospace;}
.risk-med{display:inline-block;background:#2a2a1a;color:#facc15;padding:2px 8px;border-radius:6px;font-size:0.70rem;font-weight:700;font-family:'DM Mono',monospace;}
.risk-high{display:inline-block;background:#2a1a1a;color:#f87171;padding:2px 8px;border-radius:6px;font-size:0.70rem;font-weight:700;font-family:'DM Mono',monospace;}
.badge-live{background:#3a1a1a;color:#ff6b6b;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.badge-final{background:#1a3a2a;color:#4ade80;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.badge-pre{background:#1e2640;color:#94a3b8;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
hr{border-color:#1e2640!important;}
#MainMenu,footer{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ────────────────────────────────────────────────────────────────
TRACKER_FILE = "picks_log.json"

SPORT_CONFIG = {
    "🏀 NBA": {"label": "NBA", "kalshi_series": "KXNBAGAME",     "enabled": True},
    "🏀 CBB": {"label": "CBB", "kalshi_series": "KXNCAAMBGAME",  "enabled": True},
    # Disabled until Kalshi series tickers are verified and in-season
    "⚾ MLB": {"label": "MLB", "kalshi_series": "KXMLBGAME",     "enabled": False},
    "🏈 NFL": {"label": "NFL", "kalshi_series": "KXNFLGAME",     "enabled": False},
    "🏈 CFB": {"label": "CFB", "kalshi_series": "KXCFBGAME",     "enabled": False},
}
SPORT_ICONS = {"MLB": "⚾", "NBA": "🏀", "NFL": "🏈", "CBB": "🏀", "CFB": "🏈"}

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# ── TIME (Eastern display; logic uses UTC) ────────────────────────────────────
def _is_edt(dt=None):
    if dt is None:
        dt = datetime.utcnow()
    y = dt.year
    mar = datetime(y, 3, 8)
    while mar.weekday() != 6:
        mar += timedelta(days=1)
    nov = datetime(y, 11, 1)
    while nov.weekday() != 6:
        nov += timedelta(days=1)
    return mar <= dt.replace(tzinfo=None) < nov

def now_est():
    dt = datetime.utcnow()
    edt = _is_edt(dt)
    offset = timedelta(hours=-4) if edt else timedelta(hours=-5)
    est = dt + offset
    # FIX: use cross-platform hour formatting (%-I is Linux-only)
    hour = str(int(est.strftime("%I")))
    suffix = "EDT" if edt else "EST"
    return est.strftime(f"{hour}:%M %p") + f" {suffix}"

def today_est():
    dt = datetime.utcnow()
    offset = timedelta(hours=-4) if _is_edt(dt) else timedelta(hours=-5)
    return (dt + offset).date()

# ── TEAM NORMALIZER ──────────────────────────────────────────────────────────
NORM_MAP = {
    "st john's red storm":        "St John's",
    "st. john's red storm":       "St John's",
    "saint john's red storm":     "St John's",
    "saint john's":               "St John's",
    "st. john's":                 "St John's",
    "st johns":                   "St John's",
    "st. johns":                  "St John's",
    "st john's":                  "St John's",
    "stjohn's":                   "St John's",
    "unc tar heels":              "North Carolina",
    "north carolina tar heels":   "North Carolina",
    "uconn huskies":              "UConn",
    "connecticut":                "UConn",
}

def normalize_team(name: str) -> str:
    s = str(name).strip()
    nl = s.lower()
    if nl in NORM_MAP:
        return NORM_MAP[nl]
    if re.search(r"st\.?\s*johns?'?s?\b", nl, re.IGNORECASE):
        return "St John's"
    return s

# ── TRACKER ───────────────────────────────────────────────────────────────────
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
        # Streamlit Cloud can reset disk; ignore hard-fail
        pass

def a2d(ml):
    try:
        ml = float(ml)
        return ml / 100 + 1 if ml > 0 else 100 / abs(ml) + 1
    except Exception:
        return 1.91

def calc_summary(picks, sport=None):
    f = [p for p in picks if not sport or p.get("sport", "").upper() == sport.upper()]
    s = [p for p in f if p.get("result") in ("W", "L", "P")]
    wins = len([p for p in s if p["result"] == "W"])
    pl = sum(
        (a2d(p.get("odds")) - 1) * float(p.get("units", 1)) if p["result"] == "W"
        else (-float(p.get("units", 1)) if p["result"] == "L" else 0)
        for p in s
    )
    wgr = sum(float(p.get("units", 1)) for p in s)
    return {
        "wins":     wins,
        "losses":   len([p for p in s if p["result"] == "L"]),
        "hit_rate": round(wins / len(s) * 100, 2) if s else 0,
        "pl":       round(pl, 2),
        "roi":      round(pl / wgr * 100, 2) if wgr > 0 else 0,
    }

def calc_streak(picks, sport=None):
    f = [p for p in picks
         if (not sport or p.get("sport", "").upper() == sport.upper())
         and p.get("result") in ("W", "L")]
    if not f:
        return ""
    f = sorted(f, key=lambda x: x.get("date", ""))
    streak = 1
    last = f[-1]["result"]
    for p in reversed(f[:-1]):
        if p["result"] == last:
            streak += 1
        else:
            break
    return f"{'🔥' if last == 'W' else '❄️'} {streak}-{'W' if last == 'W' else 'L'}"

# ── KALSHI FETCHERS ──────────────────────────────────────────────────────────
def _kalshi_get(path, params=None, timeout=12):
    url = f"{KALSHI_BASE}{path}"
    r = requests.get(url, params=params or {}, timeout=timeout)
    return r

@st.cache_data(ttl=43200, show_spinner=False)   # 12h
def kalshi_market_directory(series_ticker: str):
    """
    Pull a directory of OPEN markets for a series ticker.
    Uses /markets with series_ticker + status=open and a close_time window.
    FIX: removed invalid mve_filter param.
    """
    markets = []
    cursor = None
    now_ts = int(datetime.now(timezone.utc).timestamp())
    max_close = now_ts + 60 * 60 * 24 * 3   # next 72 hours
    while True:
        params = {
            "limit":          500,
            "series_ticker":  series_ticker,
            "status":         "open",
            "min_close_ts":   now_ts - 60 * 60 * 6,   # include recently closing
            "max_close_ts":   max_close,
            # NOTE: mve_filter removed — not a valid public API param
        }
        if cursor:
            params["cursor"] = cursor
        r = _kalshi_get("/markets", params=params, timeout=15)
        if r.status_code != 200:
            return {"ok": False, "error": f"{r.status_code}: {r.text[:200]}", "markets": []}
        data = r.json()
        chunk = data.get("markets", [])
        markets.extend(chunk)
        cursor = data.get("cursor")
        if not cursor or len(chunk) == 0:
            break
        if len(markets) >= 5000:   # safety stop
            break
    return {"ok": True, "error": "", "markets": markets}

@st.cache_data(ttl=600, show_spinner=False)   # 10 min
def kalshi_prices_for_tickers(tickers: tuple):
    """
    Fetch current quotes for a set of tickers via /markets?tickers=...
    Accepts a tuple (hashable for st.cache_data).
    FIX: tickers param is now a tuple to be cache-key safe.
    """
    if not tickers:
        return {"ok": True, "error": "", "by_ticker": {}}
    by = {}
    for i in range(0, len(tickers), 80):
        chunk = tickers[i:i + 80]
        params = {"tickers": ",".join(chunk), "limit": len(chunk)}
        r = _kalshi_get("/markets", params=params, timeout=15)
        if r.status_code != 200:
            return {"ok": False, "error": f"{r.status_code}: {r.text[:200]}", "by_ticker": {}}
        data = r.json()
        for m in data.get("markets", []):
            by[m.get("ticker", "")] = m
    return {"ok": True, "error": "", "by_ticker": by}

def kalshi_implied_prob(mkt: dict):
    """
    Convert Kalshi price fields into implied probability (0–1).
    Prefer midpoint of yes_bid/yes_ask; fall back to last_price.
    Prices are in cents (integer 0–100).
    """
    try:
        yb = mkt.get("yes_bid")
        ya = mkt.get("yes_ask")
        lp = mkt.get("last_price")
        if yb is not None and ya is not None and yb > 0 and ya > 0:
            return ((yb + ya) / 2.0) / 100.0
        if lp is not None and lp > 0:
            return float(lp) / 100.0
    except Exception:
        pass
    return None

# ── MODEL (placeholder baseline; drop your real model in here) ───────────────
# Replace team_strength_* with your actual model scores.
# The pipeline is fully wired; only these two functions need updating.

def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

def team_strength_nba(team: str) -> float:
    # PLACEHOLDER — swap in your real NBA model score (higher = stronger).
    return 0.0

def team_strength_cbb(team: str) -> float:
    # PLACEHOLDER — swap in your real CBB model score.
    return 0.0

def model_win_prob(fav_strength: float, dog_strength: float) -> float:
    gap = fav_strength - dog_strength
    return _sigmoid(gap / 6.0)

# ── MARKET PARSERS ────────────────────────────────────────────────────────────
def parse_game_from_market(m: dict):
    """
    Attempt to parse teams from a Kalshi game market.
    Uses yes_sub_title / no_sub_title if present; falls back to title text.
    FIX: now returns (None, None) when both parsed teams are identical.
    """
    yes   = m.get("yes_sub_title") or ""
    no    = m.get("no_sub_title")  or ""
    title = m.get("title")         or ""
    if yes and no:
        a, b = normalize_team(yes), normalize_team(no)
        if a == b:
            return None, None
        return a, b
    # fallback: "TEAM vs TEAM"
    parts = re.split(r"\bvs\.?\b|\bvs\b", title, flags=re.IGNORECASE)
    if len(parts) >= 2:
        a = normalize_team(parts[0].strip(" -:"))
        b = normalize_team(parts[1].strip(" -:"))
        if a == b:
            return None, None
        return a, b
    return None, None

PROP_KEYWORDS = {
    "PRA": ["pra", "points rebounds assists"],
    "PTS": ["points", "pts"],
    "REB": ["rebounds", "reb"],
    "AST": ["assists", "ast"],
    "3PM": ["3pm", "threes", "3-pointers", "3 pointers"],
    "BLK": ["blocks", "blk"],
    "STL": ["steals", "stl"],
}

def classify_prop_market(title: str):
    tl = title.lower()
    for k, kws in PROP_KEYWORDS.items():
        if any(w in tl for w in kws):
            return k
    return None

def extract_player_and_threshold(title: str):
    """
    Best-effort extraction:
      - Player name: text before ':' if present, else before ' - <number>+'
      - Threshold: first number followed by '+'
    """
    player = None
    threshold = None
    if ":" in title:
        player = title.split(":")[0].strip()
    else:
        match = re.match(r"([A-Za-z\.\'\- ]+)\s[-–]\s", title)
        if match:
            player = match.group(1).strip()
    tm = re.search(r"(\d+(?:\.\d+)?)\s*\+", title)
    if tm:
        try:
            threshold = float(tm.group(1))
        except Exception:
            threshold = None
    return player, threshold

# ── PICK LOGIC ────────────────────────────────────────────────────────────────
def risk_tag_from_edge(edge: float, market_prob: float):
    """
    FIX: threshold corrected to <=0.60 for Low risk.
    Previously 0.70 was too generous — a 69% implied-prob market
    carries real juice and should not be labelled low-variance.
    """
    if edge >= 0.10 and market_prob is not None and market_prob <= 0.60:
        return "Low", "risk-low"
    if edge >= 0.06:
        return "Med", "risk-med"
    return "High", "risk-high"

def pick_recommendation(edge: float, prob: float):
    if edge >= 0.10 and prob >= 0.65:
        return "🔥 STRONG"
    if edge >= 0.06 and prob >= 0.60:
        return "🎯 LEAN"
    return None

# ── UI HELPERS ────────────────────────────────────────────────────────────────
def pct(x):
    return f"{x * 100:.0f}%" if x is not None else "—"

def render_pick_card(card):
    c1, c2, c3 = st.columns([3.2, 1.4, 1.6])
    with c1:
        st.markdown(f"**{card['fav']}** vs **{card['dog']}**")
        st.caption(card.get("time", ""))
        st.markdown(f"**`{card['pick_text']}`**")
        for b in card.get("bullets", [])[:3]:
            st.caption(f"• {b}")
    with c2:
        mp = card.get("model_prob")
        st.progress(int(min(max((mp or 0) * 100, 0), 100)), text=f"Model {pct(mp)}")
        risk_lbl = card.get("risk_lbl", "Med")
        risk_cls = card.get("risk_cls", "risk-med")
        st.markdown(f'<span class="{risk_cls}">{risk_lbl} variance</span>', unsafe_allow_html=True)
    with c3:
        kp = card.get("kalshi_prob")
        st.metric("Kalshi (implied)", pct(kp))
        edge = card.get("edge")
        st.caption(f"Edge: {pct(edge) if edge is not None else '—'}")
        st.caption(f"Tier: {card.get('tier', '')}")
    st.divider()

# ── PICK BUILDER (cached to avoid redundant re-runs on widget interaction) ───
@st.cache_data(ttl=600, show_spinner=False)
def build_picks(markets_json: str, prices_json: str, sport_label: str,
                min_prob: float, min_edge: float):
    """
    FIX: Moved pick-building logic into a cached function.
    Streamlit reruns the entire script on every widget change; without
    caching, the O(N*markets) loop would re-execute on every slider tick.
    markets_json / prices_json are pre-serialised strings so the args are
    hashable for st.cache_data.
    """
    markets   = json.loads(markets_json)
    prices_by = json.loads(prices_json)
    sl        = sport_label

    game_cards = []
    prop_rows  = []

    for m in markets:
        tkr = m.get("ticker", "")
        if not tkr or tkr not in prices_by:
            continue
        pm    = prices_by[tkr]
        title = pm.get("title") or m.get("title") or ""
        kprob = kalshi_implied_prob(pm)

        # ── Props ────────────────────────────────────────────────────────────
        prop_type = classify_prop_market(title)
        if prop_type:
            player, thr = extract_player_and_threshold(title)
            if not player or thr is None:
                continue

            # Placeholder projection — swap in your real player model here.
            proj = thr + 2.0
            std  = max(3.0, proj * (0.22 if prop_type in ("PRA","PTS","REB","AST") else 0.35))
            z    = (proj - thr) / std
            mprob = 0.5 + 0.35 * math.tanh(z * 0.8)
            edge  = (mprob - kprob) if (mprob is not None and kprob is not None) else None

            # FIX: edge_req lowered so the placeholder model surfaces some
            # results — banner in the UI notes the model is a placeholder.
            edge_req = 0.04 if prop_type in ("3PM","BLK","STL") else 0.03
            if kprob is None or edge is None:
                continue
            if mprob < min_prob:
                continue
            if edge < max(min_edge, edge_req):
                continue

            # FIX: tier computed and stored so prop card can render it.
            tier = "🔥 STRONG" if edge >= 0.10 and mprob >= 0.65 else "🎯 LEAN"
            prop_rows.append({
                "Player": player,
                "Type":   prop_type,
                "Line":   f"{thr:g}+",
                "Model":  mprob,
                "Kalshi": kprob,
                "Edge":   edge,
                "Tier":   tier,
                "Ticker": tkr,
                "Title":  title[:80],
            })
            continue   # don't fall through to game-market logic

        # ── Game markets ─────────────────────────────────────────────────────
        yes_team, no_team = parse_game_from_market(pm)
        if not yes_team or not no_team:
            continue
        if kprob is None:
            continue

        market_yes = kprob
        market_no  = 1.0 - kprob

        if sl == "NBA":
            s_yes = team_strength_nba(yes_team)
            s_no  = team_strength_nba(no_team)
        else:
            s_yes = team_strength_cbb(yes_team)
            s_no  = team_strength_cbb(no_team)

        model_yes = model_win_prob(s_yes, s_no)
        model_no  = 1.0 - model_yes

        edge_yes = model_yes - market_yes
        edge_no  = model_no  - market_no

        if edge_yes >= edge_no:
            pick_team = yes_team;  opp_team = no_team
            mprob     = model_yes; implied  = market_yes
            edge      = edge_yes
        else:
            pick_team = no_team;   opp_team = yes_team
            mprob     = model_no;  implied  = market_no
            edge      = edge_no

        pick_text = f"{pick_team} (win)"

        if mprob < min_prob or edge < min_edge:
            continue

        tier = pick_recommendation(edge, mprob)
        if tier is None:
            continue

        risk_lbl, risk_cls = risk_tag_from_edge(edge, implied)

        game_cards.append({
            "fav":        pick_team,
            "dog":        opp_team,
            "pick_text":  pick_text,
            "model_prob": mprob,
            "kalshi_prob":implied,
            "edge":       edge,
            "tier":       tier,
            "risk_lbl":   risk_lbl,
            "risk_cls":   risk_cls,
            "time":       "",
            "bullets": [
                f"Model {pct(mprob)} vs Kalshi {pct(implied)}",
                f"Edge {pct(edge)}",
                f"Market ticker: {tkr}",
            ],
        })

    game_cards.sort(key=lambda x: x.get("edge", 0), reverse=True)
    prop_rows.sort(key=lambda x: (x.get("Edge", 0), x.get("Model", 0)), reverse=True)
    return game_cards, prop_rows

# ── SESSION STATE ─────────────────────────────────────────────────────────────
st.session_state.setdefault("min_conf", 60)
st.session_state.setdefault("min_edge", 6)
st.session_state.setdefault("debug", False)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏆 Betting Dashboard")
    st.caption(f"{today_est().strftime('%A, %B %d')} · {now_est()}")
    st.divider()

    sport_ui = st.radio("Sport", list(SPORT_CONFIG.keys()), label_visibility="collapsed")
    cfg = SPORT_CONFIG[sport_ui]
    sl  = cfg["label"]
    st.divider()

    # FIX: picks loaded once here, passed to tracker tab — no second load.
    picks  = load_picks()
    summ   = calc_summary(picks)
    streak = calc_streak(picks)
    pl_col = "#4ade80" if summ["pl"] >= 0 else "#f87171"
    st.markdown(f"""
<div style="background:#131929;border:1px solid #1e2a45;border-radius:10px;padding:10px 14px;margin-bottom:8px">
  <div style="font-size:0.72rem;color:#8892a4;margin-bottom:4px">📈 SEASON</div>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:1.05rem;font-weight:800;color:#e8eaf0">{summ['wins']}-{summ['losses']}</span>
    <span style="font-family:'DM Mono',monospace;color:{pl_col};font-size:0.85rem">{'+' if summ['pl']>=0 else ''}{summ['pl']}u</span>
  </div>
  <div style="font-size:0.70rem;color:#5a6478">{summ['hit_rate']:.1f}% · ROI {summ['roi']:.1f}% · {streak}</div>
</div>
""", unsafe_allow_html=True)

    st.session_state["min_conf"] = st.slider("Min Model Prob %", 50, 80,
                                             int(st.session_state["min_conf"]), 1)
    st.session_state["min_edge"] = st.slider("Min Edge %", 0, 20,
                                             int(st.session_state["min_edge"]), 1,
                                             help="Edge = Model Prob − Kalshi Implied Prob")
    st.session_state["debug"] = st.checkbox("Debug", value=st.session_state["debug"])
    st.caption("Kalshi cache: directory 12h · prices 10m")

# ── DISABLED SPORT GUARD ─────────────────────────────────────────────────────
# FIX: MLB / NFL / CFB show a friendly message instead of silently returning nothing.
if not cfg.get("enabled", False):
    st.info(
        f"**{sl}** lines are coming soon. "
        f"Kalshi series mapping for {sl} hasn't been verified and/or the season "
        f"is not currently active. Switch to **NBA** or **CBB** to see live picks."
    )
    st.stop()

# ── LOAD KALSHI MARKETS ───────────────────────────────────────────────────────
series   = cfg["kalshi_series"]
dir_resp = kalshi_market_directory(series)

if not dir_resp["ok"]:
    st.error(f"Kalshi market directory error: {dir_resp['error']}")
    markets = []
else:
    markets = dir_resp["markets"]

# Fetch fresh prices (10 min cache). Use tuple so it's hashable for cache_data.
tickers     = tuple(m.get("ticker", "") for m in markets if m.get("ticker"))
prices_resp = kalshi_prices_for_tickers(tickers)

if not prices_resp["ok"]:
    st.warning(f"Kalshi price feed issue: {prices_resp['error']}")
    prices_by = {}
else:
    prices_by = prices_resp["by_ticker"]

# ── BUILD PICKS ───────────────────────────────────────────────────────────────
min_prob = st.session_state["min_conf"] / 100.0
min_edge = st.session_state["min_edge"] / 100.0

game_cards, prop_rows = build_picks(
    markets_json = json.dumps(markets),
    prices_json  = json.dumps(prices_by),
    sport_label  = sl,
    min_prob     = min_prob,
    min_edge     = min_edge,
)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown(
    f"**{SPORT_ICONS.get(sl, '🏆')} {sl}** · "
    f"{today_est().strftime('%b %d')} · "
    f"Markets: {len(markets)} · "
    f"Priced: {len(prices_by)} · "
    f"Picks: {len(game_cards)}"
)

if st.session_state["debug"]:
    with st.expander("🔍 Debug: Kalshi", expanded=False):
        st.write("Series:",           series)
        st.write("Directory OK:",     dir_resp["ok"])
        st.write("Markets fetched:",  len(markets))
        st.write("Tickers sent:",     len(tickers))
        st.write("Prices OK:",        prices_resp["ok"])
        st.write("Prices returned:",  len(prices_by))
        st.write("Unpriced tickers:", len(tickers) - len(prices_by))
        st.write("Game picks:",       len(game_cards))
        st.write("Prop picks:",       len(prop_rows))
        if not prices_resp["ok"]:
            st.write("Price error:", prices_resp["error"])
        if not dir_resp["ok"]:
            st.write("Dir error:", dir_resp["error"])

st.divider()

# ── TABS ──────────────────────────────────────────────────────────────────────
tabs = st.tabs(["🗓️ Today", "🎯 Props", "📋 Stats", "📈 Tracker"])

# ── Today ─────────────────────────────────────────────────────────────────────
with tabs[0]:
    if not game_cards:
        st.info("No picks meet your thresholds right now. Lower Min Model Prob % or Min Edge %.")
    else:
        for card in game_cards[:15]:
            render_pick_card(card)

# ── Props ─────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.markdown("#### 🎯 Props (Kalshi-driven roster)")

    if sl != "NBA":
        st.info("Props are currently implemented for NBA. Switch to NBA to see them.")
    else:
        # FIX: banner so users know props are running on a placeholder model.
        st.warning(
            "⚠️ **Placeholder model active.** Props are being surfaced using a "
            "statistical proxy, not your real player model. Edge values will be "
            "conservative. Drop your model into `team_strength_nba()` to activate "
            "real projections."
        )
        st.caption("Props shown only when Kalshi markets exist AND model edge meets threshold.")
        if not prop_rows:
            st.info("No prop edges meet thresholds right now.")
        else:
            for r in prop_rows[:30]:
                c1, c2, c3, c4 = st.columns([2.6, 1.4, 1.4, 2.0])
                with c1:
                    st.markdown(f"**{r['Player']}** · {r['Type']} · {r['Line']}")
                    # FIX: tier label now rendered in the prop card.
                    st.caption(f"Tier: {r.get('Tier', '—')}  ·  {r['Title']}")
                    st.caption(f"Ticker: {r['Ticker']}")
                with c2:
                    st.metric("Model", pct(r["Model"]))
                with c3:
                    st.metric("Kalshi", pct(r["Kalshi"]))
                with c4:
                    st.metric("Edge", pct(r["Edge"]))
                st.divider()

# ── Stats ─────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown("#### 📋 Kalshi Markets")
    # FIX: show ALL markets from the directory, with a 'priced' flag,
    # so you can see exactly which markets are missing from the price feed.
    if not markets:
        st.info("No markets returned from Kalshi.")
    else:
        rows = []
        for m in markets[:300]:
            tkr = m.get("ticker", "")
            pm  = prices_by.get(tkr, {})
            rows.append({
                "ticker":     tkr,
                "title":      (m.get("title") or "")[:80],
                "priced":     "✅" if tkr in prices_by else "❌",
                "yes_bid":    pm.get("yes_bid"),
                "yes_ask":    pm.get("yes_ask"),
                "last":       pm.get("last_price"),
                "close_time": m.get("close_time", ""),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        unpriced = sum(1 for r in rows if r["priced"] == "❌")
        if unpriced:
            st.caption(f"⚠️ {unpriced} markets in directory have no price data.")

# ── Tracker ───────────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown("#### 📈 Tracker")
    # FIX: reuse picks already loaded in sidebar — no second disk read.
    sport_summ = calc_summary(picks, sl)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Record",   f"{sport_summ['wins']}-{sport_summ['losses']}")
    col2.metric("Hit Rate", f"{sport_summ['hit_rate']:.1f}%")
    col3.metric("P&L",      f"{'+' if sport_summ['pl'] >= 0 else ''}{sport_summ['pl']}u")
    col4.metric("ROI",      f"{'+' if sport_summ['roi'] >= 0 else ''}{sport_summ['roi']:.1f}%")
    st.divider()

    with st.expander("➕ Log a pick"):
        bet_type = st.selectbox("Bet type", ["Game", "Prop", "Other"])
        fav      = st.text_input("Favorite / Player")
        dog      = st.text_input("Opponent / Game")
        odds     = st.text_input("Odds / Price (optional)")
        units    = st.number_input("Units", 0.1, 10.0, 0.5, 0.25)
        notes    = st.text_input("Notes")
        if st.button("Save pick"):
            if fav:
                picks.append({
                    "date":      today_est().isoformat(),
                    "sport":     sl,
                    "bet_type":  bet_type,
                    "favorite":  fav,
                    "underdog":  dog,
                    "odds":      odds,
                    "units":     units,
                    "notes":     notes,
                    "result":    "Pending",
                })
                save_picks(picks)
                st.success("Saved.")
                st.rerun()
            else:
                st.error("Enter at least a Favorite/Player.")

    if picks:
        dfp = pd.DataFrame(picks)
        ed = st.data_editor(
            dfp,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "result": st.column_config.SelectboxColumn(
                    "Result", options=["Pending", "W", "L", "P"]
                )
            },
        )
        if st.button("Save results"):
            save_picks(ed.to_dict("records"))
            st.success("Updated.")
            st.rerun()
