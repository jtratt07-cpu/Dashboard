"""
Unified Sports Betting Dashboard — app.py
MLB · NBA · NFL · CBB · CFB

Live data sources (all free):
  MLB  → pybaseball  (Baseball Reference / FanGraphs — standings, ERA, run diff)
  NBA  → nba_api     (official NBA stats — net rating, off/def rtg, pace)
  NFL  → nfl_data_py (nflfastR EPA, turnover margin, efficiency)
  CBB  → barttorvik.com T-Rank CSV (free KenPom equivalent — adj eff, tempo)
  CFB  → collegefootballdata.com API (SP+, off/def ratings — free key required)
  ALL  → The Odds API (live odds) + ESPN API (live scores)

Run locally:  streamlit run app.py
Deploy:       push to GitHub → Streamlit Community Cloud
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date
from io import StringIO
import json, os, time, warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betting Dashboard",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
.dataframe{font-family:'DM Mono',monospace;font-size:0.82rem;}
thead tr th{background:#131929!important;color:#7eeaff!important;font-family:'Syne',sans-serif!important;font-weight:700!important;border-bottom:2px solid #1e2a45!important;}
tbody tr:hover td{background:#1a2235!important;}
.stButton button{background:linear-gradient(135deg,#1a6fff,#0ea5e9)!important;color:white!important;border:none!important;border-radius:8px!important;font-family:'Syne',sans-serif!important;font-weight:700!important;padding:0.5rem 1.5rem!important;transition:all 0.2s ease!important;}
.stButton button:hover{transform:translateY(-1px)!important;box-shadow:0 4px 20px rgba(26,111,255,0.4)!important;}
.stTabs [data-baseweb="tab-list"]{background:#0f1525;border-radius:10px;padding:4px;gap:4px;}
.stTabs [data-baseweb="tab"]{background:transparent;color:#8892a4!important;border-radius:8px;font-family:'Syne',sans-serif;font-weight:600;}
.stTabs [aria-selected="true"]{background:#1a2640!important;color:#7eeaff!important;}
.score-card{background:#131929;border:1px solid #1e2a45;border-radius:12px;padding:14px 18px;margin-bottom:8px;}
.score-card.live{border-color:#ff6b6b44;background:#1a1020;}
.score-card.final{border-color:#4ade8033;}
.pick-card{background:#131929;border:1px solid #1e2640;border-radius:12px;padding:16px 20px;margin-bottom:10px;border-left:4px solid #1a6fff;}
.pick-card.strong{border-left-color:#4ade80;}
.pick-card.lean{border-left-color:#facc15;}
.badge-green{background:#1a3a2a;color:#4ade80;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;font-family:'DM Mono',monospace;}
.badge-yellow{background:#2a2a1a;color:#facc15;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;font-family:'DM Mono',monospace;}
.badge-red{background:#3a1a1a;color:#f87171;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;font-family:'DM Mono',monospace;}
.badge-blue{background:#1a2a3a;color:#60a5fa;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;font-family:'DM Mono',monospace;}
.badge-live{background:#3a1a1a;color:#ff6b6b;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;animation:pulse 1.5s infinite;}
.badge-final{background:#1a3a2a;color:#4ade80;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.badge-pre{background:#1e2640;color:#94a3b8;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.6}}
.dash-header{background:linear-gradient(135deg,#0f1a35 0%,#0a1228 100%);border:1px solid #1e2a45;border-radius:16px;padding:24px 32px;margin-bottom:24px;}
.dash-title{font-size:1.8rem;font-weight:800;color:#e8eaf0;letter-spacing:-0.02em;}
.dash-sub{font-size:0.85rem;color:#5a6478;font-family:'DM Mono',monospace;margin-top:4px;}
.source-pill{display:inline-block;background:#131929;border:1px solid #1e2a45;border-radius:20px;padding:2px 10px;font-size:0.72rem;font-family:'DM Mono',monospace;color:#7eeaff;margin-right:4px;}
.source-pill.live{border-color:#4ade8055;color:#4ade80;}
.source-pill.fallback{border-color:#facc1555;color:#facc15;}
hr{border-color:#1e2640!important;}
#MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
ODDS_API_KEY = "8762561865c3719f114b2d815aca3041"
TRACKER_FILE = "picks_log.json"

# Get your free key at collegefootballdata.com — takes 30 seconds
CFBD_API_KEY = os.environ.get("CFBD_API_KEY", "")

SPORT_CONFIG = {
    "⚾ MLB": {"key":"baseball_mlb",          "espn_sport":"baseball",   "espn_league":"mlb",                     "label":"MLB"},
    "🏀 NBA": {"key":"basketball_nba",         "espn_sport":"basketball", "espn_league":"nba",                     "label":"NBA"},
    "🏈 NFL": {"key":"americanfootball_nfl",   "espn_sport":"football",   "espn_league":"nfl",                     "label":"NFL"},
    "🏀 CBB": {"key":"basketball_ncaab",       "espn_sport":"basketball", "espn_league":"mens-college-basketball", "label":"CBB"},
    "🏈 CFB": {"key":"americanfootball_ncaaf", "espn_sport":"football",   "espn_league":"college-football",        "label":"CFB"},
}

CBB_SEED_HISTORY = {
    (1,16):{"upset_rate":0.03,"note":"Near-lock for favorite"},
    (2,15):{"upset_rate":0.06,"note":"Very rare upset"},
    (3,14):{"upset_rate":0.15,"note":"Occasional upset"},
    (4,13):{"upset_rate":0.21,"note":"Check model gap"},
    (5,12):{"upset_rate":0.35,"note":"⭐ Classic upset spot"},
    (6,11):{"upset_rate":0.37,"note":"⭐ Best upset matchup"},
    (7,10):{"upset_rate":0.40,"note":"⭐ Near coin flip"},
    (8, 9):{"upset_rate":0.49,"note":"True toss-up"},
}

# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK STATS  (used if live fetch fails or season is inactive)
# ─────────────────────────────────────────────────────────────────────────────
MLB_FB = {
    "LAD":{"win_pct":0.642,"run_diff_pg":1.8,"bullpen_era":3.45,"last10":0.70,"ops":0.788},
    "ATL":{"win_pct":0.617,"run_diff_pg":1.5,"bullpen_era":3.62,"last10":0.60,"ops":0.762},
    "PHI":{"win_pct":0.599,"run_diff_pg":1.3,"bullpen_era":3.55,"last10":0.60,"ops":0.758},
    "BAL":{"win_pct":0.580,"run_diff_pg":1.1,"bullpen_era":3.70,"last10":0.50,"ops":0.745},
    "HOU":{"win_pct":0.574,"run_diff_pg":1.0,"bullpen_era":3.80,"last10":0.50,"ops":0.741},
    "NYY":{"win_pct":0.568,"run_diff_pg":0.9,"bullpen_era":3.90,"last10":0.50,"ops":0.738},
    "MIL":{"win_pct":0.562,"run_diff_pg":0.8,"bullpen_era":3.95,"last10":0.50,"ops":0.735},
    "CLE":{"win_pct":0.556,"run_diff_pg":0.7,"bullpen_era":4.00,"last10":0.50,"ops":0.731},
    "MIN":{"win_pct":0.549,"run_diff_pg":0.5,"bullpen_era":4.10,"last10":0.40,"ops":0.728},
    "BOS":{"win_pct":0.543,"run_diff_pg":0.4,"bullpen_era":4.15,"last10":0.50,"ops":0.725},
    "SD": {"win_pct":0.537,"run_diff_pg":0.3,"bullpen_era":4.20,"last10":0.40,"ops":0.721},
    "SEA":{"win_pct":0.531,"run_diff_pg":0.2,"bullpen_era":4.25,"last10":0.40,"ops":0.718},
    "TOR":{"win_pct":0.525,"run_diff_pg":0.1,"bullpen_era":4.30,"last10":0.40,"ops":0.715},
    "TB": {"win_pct":0.519,"run_diff_pg":0.0,"bullpen_era":4.35,"last10":0.40,"ops":0.711},
    "SF": {"win_pct":0.512,"run_diff_pg":-0.1,"bullpen_era":4.40,"last10":0.40,"ops":0.708},
    "NYM":{"win_pct":0.506,"run_diff_pg":-0.2,"bullpen_era":4.50,"last10":0.40,"ops":0.705},
    "STL":{"win_pct":0.500,"run_diff_pg":-0.3,"bullpen_era":4.55,"last10":0.30,"ops":0.701},
    "DET":{"win_pct":0.494,"run_diff_pg":-0.4,"bullpen_era":4.60,"last10":0.30,"ops":0.698},
    "TEX":{"win_pct":0.488,"run_diff_pg":-0.5,"bullpen_era":4.70,"last10":0.30,"ops":0.695},
    "ARI":{"win_pct":0.481,"run_diff_pg":-0.6,"bullpen_era":4.75,"last10":0.30,"ops":0.691},
    "CHC":{"win_pct":0.475,"run_diff_pg":-0.7,"bullpen_era":4.80,"last10":0.30,"ops":0.688},
    "CIN":{"win_pct":0.469,"run_diff_pg":-0.8,"bullpen_era":4.90,"last10":0.30,"ops":0.685},
    "KC": {"win_pct":0.463,"run_diff_pg":-0.9,"bullpen_era":4.95,"last10":0.30,"ops":0.681},
    "MIA":{"win_pct":0.457,"run_diff_pg":-1.0,"bullpen_era":5.00,"last10":0.20,"ops":0.678},
    "PIT":{"win_pct":0.451,"run_diff_pg":-1.1,"bullpen_era":5.10,"last10":0.20,"ops":0.675},
    "LAA":{"win_pct":0.444,"run_diff_pg":-1.2,"bullpen_era":5.15,"last10":0.20,"ops":0.671},
    "OAK":{"win_pct":0.438,"run_diff_pg":-1.3,"bullpen_era":5.20,"last10":0.20,"ops":0.668},
    "COL":{"win_pct":0.420,"run_diff_pg":-1.8,"bullpen_era":5.50,"last10":0.20,"ops":0.645},
    "WSH":{"win_pct":0.432,"run_diff_pg":-1.4,"bullpen_era":5.30,"last10":0.20,"ops":0.661},
    "CWS":{"win_pct":0.400,"run_diff_pg":-2.0,"bullpen_era":5.80,"last10":0.10,"ops":0.621},
}
MLB_NAME_MAP = {
    "Arizona Diamondbacks":"ARI","Atlanta Braves":"ATL","Baltimore Orioles":"BAL",
    "Boston Red Sox":"BOS","Chicago Cubs":"CHC","Chicago White Sox":"CWS",
    "Cincinnati Reds":"CIN","Cleveland Guardians":"CLE","Colorado Rockies":"COL",
    "Detroit Tigers":"DET","Houston Astros":"HOU","Kansas City Royals":"KC",
    "Los Angeles Angels":"LAA","Los Angeles Dodgers":"LAD","Miami Marlins":"MIA",
    "Milwaukee Brewers":"MIL","Minnesota Twins":"MIN","New York Mets":"NYM",
    "New York Yankees":"NYY","Oakland Athletics":"OAK","Philadelphia Phillies":"PHI",
    "Pittsburgh Pirates":"PIT","San Diego Padres":"SD","San Francisco Giants":"SF",
    "Seattle Mariners":"SEA","St. Louis Cardinals":"STL","Tampa Bay Rays":"TB",
    "Texas Rangers":"TEX","Toronto Blue Jays":"TOR","Washington Nationals":"WSH",
    "Athletics":"OAK","Guardians":"CLE",
}

NBA_FB = {
    "Boston Celtics":        {"net_rtg":10.2,"off_rtg":122.5,"def_rtg":112.3,"pace":99.1,"last10":0.70,"wins":58,"losses":24},
    "Oklahoma City Thunder": {"net_rtg":9.8, "off_rtg":120.8,"def_rtg":111.0,"pace":100.2,"last10":0.70,"wins":57,"losses":25},
    "Cleveland Cavaliers":   {"net_rtg":9.1, "off_rtg":118.9,"def_rtg":109.8,"pace":97.5,"last10":0.60,"wins":55,"losses":27},
    "Minnesota Timberwolves":{"net_rtg":8.4, "off_rtg":116.2,"def_rtg":107.8,"pace":98.8,"last10":0.60,"wins":53,"losses":29},
    "Denver Nuggets":        {"net_rtg":7.9, "off_rtg":117.8,"def_rtg":109.9,"pace":98.2,"last10":0.60,"wins":51,"losses":31},
    "New York Knicks":       {"net_rtg":7.2, "off_rtg":115.4,"def_rtg":108.2,"pace":96.8,"last10":0.50,"wins":49,"losses":33},
    "Memphis Grizzlies":     {"net_rtg":6.8, "off_rtg":116.1,"def_rtg":109.3,"pace":101.5,"last10":0.50,"wins":48,"losses":34},
    "LA Clippers":           {"net_rtg":6.1, "off_rtg":114.8,"def_rtg":108.7,"pace":97.2,"last10":0.50,"wins":46,"losses":36},
    "Golden State Warriors": {"net_rtg":5.4, "off_rtg":116.2,"def_rtg":110.8,"pace":99.8,"last10":0.50,"wins":44,"losses":38},
    "Houston Rockets":       {"net_rtg":5.1, "off_rtg":113.5,"def_rtg":108.4,"pace":100.4,"last10":0.50,"wins":43,"losses":39},
    "Indiana Pacers":        {"net_rtg":4.8, "off_rtg":118.9,"def_rtg":114.1,"pace":104.2,"last10":0.50,"wins":42,"losses":40},
    "Dallas Mavericks":      {"net_rtg":4.2, "off_rtg":115.1,"def_rtg":110.9,"pace":98.5,"last10":0.40,"wins":40,"losses":42},
    "Milwaukee Bucks":       {"net_rtg":3.8, "off_rtg":114.8,"def_rtg":111.0,"pace":99.1,"last10":0.40,"wins":39,"losses":43},
    "Phoenix Suns":          {"net_rtg":3.1, "off_rtg":113.9,"def_rtg":110.8,"pace":98.8,"last10":0.40,"wins":37,"losses":45},
    "Sacramento Kings":      {"net_rtg":2.4, "off_rtg":115.2,"def_rtg":112.8,"pace":100.5,"last10":0.40,"wins":35,"losses":47},
    "Miami Heat":            {"net_rtg":1.8, "off_rtg":111.8,"def_rtg":110.0,"pace":96.5,"last10":0.40,"wins":34,"losses":48},
    "Orlando Magic":         {"net_rtg":1.2, "off_rtg":108.9,"def_rtg":107.7,"pace":95.8,"last10":0.40,"wins":33,"losses":49},
    "Los Angeles Lakers":    {"net_rtg":0.8, "off_rtg":112.4,"def_rtg":111.6,"pace":99.2,"last10":0.40,"wins":32,"losses":50},
    "Atlanta Hawks":         {"net_rtg":-0.5,"off_rtg":113.8,"def_rtg":114.3,"pace":101.2,"last10":0.30,"wins":30,"losses":52},
    "Brooklyn Nets":         {"net_rtg":-2.1,"off_rtg":109.5,"def_rtg":111.6,"pace":98.5,"last10":0.30,"wins":27,"losses":55},
    "Toronto Raptors":       {"net_rtg":-2.8,"off_rtg":110.2,"def_rtg":113.0,"pace":97.8,"last10":0.30,"wins":25,"losses":57},
    "Chicago Bulls":         {"net_rtg":-3.4,"off_rtg":111.8,"def_rtg":115.2,"pace":98.9,"last10":0.30,"wins":24,"losses":58},
    "Philadelphia 76ers":    {"net_rtg":-3.0,"off_rtg":110.5,"def_rtg":113.5,"pace":97.8,"last10":0.30,"wins":25,"losses":57},
    "Utah Jazz":             {"net_rtg":-5.1,"off_rtg":109.8,"def_rtg":114.9,"pace":99.5,"last10":0.20,"wins":21,"losses":61},
    "New Orleans Pelicans":  {"net_rtg":-5.8,"off_rtg":109.2,"def_rtg":115.0,"pace":98.2,"last10":0.20,"wins":20,"losses":62},
    "San Antonio Spurs":     {"net_rtg":-6.5,"off_rtg":108.5,"def_rtg":115.0,"pace":99.8,"last10":0.20,"wins":19,"losses":63},
    "Portland Trail Blazers":{"net_rtg":-7.2,"off_rtg":108.1,"def_rtg":115.3,"pace":100.1,"last10":0.20,"wins":18,"losses":64},
    "Charlotte Hornets":     {"net_rtg":-8.1,"off_rtg":107.8,"def_rtg":115.9,"pace":99.4,"last10":0.20,"wins":17,"losses":65},
    "Detroit Pistons":       {"net_rtg":-8.9,"off_rtg":107.2,"def_rtg":116.1,"pace":98.8,"last10":0.20,"wins":16,"losses":66},
    "Washington Wizards":    {"net_rtg":-10.2,"off_rtg":106.5,"def_rtg":116.7,"pace":99.2,"last10":0.10,"wins":14,"losses":68},
}

NFL_FB = {
    "Kansas City Chiefs":    {"epa_off":0.182,"epa_def":-0.145,"to_margin":8, "win_pct":0.812,"pts_diff":9.8},
    "Philadelphia Eagles":   {"epa_off":0.158,"epa_def":-0.128,"to_margin":6, "win_pct":0.750,"pts_diff":8.2},
    "San Francisco 49ers":   {"epa_off":0.142,"epa_def":-0.138,"to_margin":5, "win_pct":0.719,"pts_diff":7.5},
    "Baltimore Ravens":      {"epa_off":0.168,"epa_def":-0.082,"to_margin":4, "win_pct":0.719,"pts_diff":7.1},
    "Buffalo Bills":         {"epa_off":0.151,"epa_def":-0.095,"to_margin":5, "win_pct":0.688,"pts_diff":6.8},
    "Houston Texans":        {"epa_off":0.128,"epa_def":-0.072,"to_margin":3, "win_pct":0.656,"pts_diff":5.5},
    "Dallas Cowboys":        {"epa_off":0.112,"epa_def":-0.088,"to_margin":3, "win_pct":0.625,"pts_diff":5.2},
    "Detroit Lions":         {"epa_off":0.135,"epa_def":0.018, "to_margin":2, "win_pct":0.625,"pts_diff":5.0},
    "Miami Dolphins":        {"epa_off":0.125,"epa_def":0.042, "to_margin":1, "win_pct":0.594,"pts_diff":4.5},
    "Cincinnati Bengals":    {"epa_off":0.118,"epa_def":0.025, "to_margin":2, "win_pct":0.563,"pts_diff":4.1},
    "Los Angeles Rams":      {"epa_off":0.105,"epa_def":-0.015,"to_margin":1,"win_pct":0.563,"pts_diff":3.8},
    "Los Angeles Chargers":  {"epa_off":0.088,"epa_def":-0.022,"to_margin":2,"win_pct":0.531,"pts_diff":3.2},
    "Tampa Bay Buccaneers":  {"epa_off":0.095,"epa_def":0.028, "to_margin":1,"win_pct":0.531,"pts_diff":3.5},
    "Washington Commanders": {"epa_off":0.072,"epa_def":0.038, "to_margin":0,"win_pct":0.469,"pts_diff":1.8},
    "Cleveland Browns":      {"epa_off":0.068,"epa_def":-0.025,"to_margin":0,"win_pct":0.500,"pts_diff":2.2},
    "Pittsburgh Steelers":   {"epa_off":0.052,"epa_def":-0.055,"to_margin":1,"win_pct":0.500,"pts_diff":2.0},
    "Green Bay Packers":     {"epa_off":0.075,"epa_def":0.085, "to_margin":0,"win_pct":0.469,"pts_diff":1.1},
    "Seattle Seahawks":      {"epa_off":0.048,"epa_def":0.062, "to_margin":-1,"win_pct":0.438,"pts_diff":0.5},
    "Minnesota Vikings":     {"epa_off":0.055,"epa_def":0.088, "to_margin":-2,"win_pct":0.438,"pts_diff":0.4},
    "Jacksonville Jaguars":  {"epa_off":0.058,"epa_def":0.032, "to_margin":-1,"win_pct":0.469,"pts_diff":1.2},
    "Indianapolis Colts":    {"epa_off":0.042,"epa_def":0.082, "to_margin":-1,"win_pct":0.406,"pts_diff":0.1},
    "New York Giants":       {"epa_off":0.018,"epa_def":0.088, "to_margin":-2,"win_pct":0.375,"pts_diff":-0.8},
    "New Orleans Saints":    {"epa_off":0.012,"epa_def":0.118, "to_margin":-2,"win_pct":0.344,"pts_diff":-2.0},
    "Tennessee Titans":      {"epa_off":0.015,"epa_def":0.108, "to_margin":-3,"win_pct":0.344,"pts_diff":-1.5},
    "Chicago Bears":         {"epa_off":-0.005,"epa_def":0.108,"to_margin":-3,"win_pct":0.313,"pts_diff":-2.8},
    "Las Vegas Raiders":     {"epa_off":0.005,"epa_def":0.118, "to_margin":-4,"win_pct":0.313,"pts_diff":-2.5},
    "New England Patriots":  {"epa_off":-0.012,"epa_def":0.115,"to_margin":-3,"win_pct":0.281,"pts_diff":-3.2},
    "Denver Broncos":        {"epa_off":-0.025,"epa_def":0.102,"to_margin":-2,"win_pct":0.281,"pts_diff":-3.5},
    "Atlanta Falcons":       {"epa_off":-0.031,"epa_def":0.105,"to_margin":-5,"win_pct":0.250,"pts_diff":-4.0},
    "New York Jets":         {"epa_off":-0.042,"epa_def":0.108,"to_margin":-6,"win_pct":0.219,"pts_diff":-5.0},
    "Arizona Cardinals":     {"epa_off":-0.052,"epa_def":0.108,"to_margin":-5,"win_pct":0.188,"pts_diff":-5.8},
    "Carolina Panthers":     {"epa_off":-0.068,"epa_def":0.112,"to_margin":-7,"win_pct":0.156,"pts_diff":-7.2},
}
NFL_ABBR = {
    "KC":"Kansas City Chiefs","PHI":"Philadelphia Eagles","SF":"San Francisco 49ers",
    "BAL":"Baltimore Ravens","BUF":"Buffalo Bills","HOU":"Houston Texans",
    "DAL":"Dallas Cowboys","DET":"Detroit Lions","MIA":"Miami Dolphins",
    "CIN":"Cincinnati Bengals","LA":"Los Angeles Rams","LAC":"Los Angeles Chargers",
    "TB":"Tampa Bay Buccaneers","WAS":"Washington Commanders","CLE":"Cleveland Browns",
    "PIT":"Pittsburgh Steelers","JAX":"Jacksonville Jaguars","GB":"Green Bay Packers",
    "SEA":"Seattle Seahawks","MIN":"Minnesota Vikings","IND":"Indianapolis Colts",
    "NYG":"New York Giants","NO":"New Orleans Saints","TEN":"Tennessee Titans",
    "CHI":"Chicago Bears","LV":"Las Vegas Raiders","NE":"New England Patriots",
    "DEN":"Denver Broncos","ATL":"Atlanta Falcons","NYJ":"New York Jets",
    "ARI":"Arizona Cardinals","CAR":"Carolina Panthers",
}

CBB_FB = {
    "Auburn":         {"eff_margin":28.5,"adj_o":122.1,"adj_d":93.6,"efg":0.558,"to_rate":0.158,"exp":0.85,"tempo":72.1,"seed":1},
    "Duke":           {"eff_margin":27.2,"adj_o":121.8,"adj_d":94.6,"efg":0.551,"to_rate":0.162,"exp":0.60,"tempo":71.8,"seed":1},
    "Houston":        {"eff_margin":26.8,"adj_o":118.4,"adj_d":91.6,"efg":0.532,"to_rate":0.170,"exp":0.90,"tempo":68.5,"seed":1},
    "Florida":        {"eff_margin":25.9,"adj_o":120.2,"adj_d":94.3,"efg":0.545,"to_rate":0.165,"exp":0.75,"tempo":70.2,"seed":2},
    "Tennessee":      {"eff_margin":25.4,"adj_o":117.8,"adj_d":92.4,"efg":0.528,"to_rate":0.172,"exp":0.88,"tempo":67.8,"seed":2},
    "Kansas":         {"eff_margin":24.1,"adj_o":119.6,"adj_d":95.5,"efg":0.541,"to_rate":0.160,"exp":0.78,"tempo":71.5,"seed":2},
    "Iowa State":     {"eff_margin":23.8,"adj_o":118.9,"adj_d":95.1,"efg":0.538,"to_rate":0.163,"exp":0.82,"tempo":70.8,"seed":2},
    "Purdue":         {"eff_margin":23.2,"adj_o":120.4,"adj_d":97.2,"efg":0.555,"to_rate":0.155,"exp":0.92,"tempo":69.1,"seed":3},
    "Alabama":        {"eff_margin":22.7,"adj_o":121.0,"adj_d":98.3,"efg":0.562,"to_rate":0.175,"exp":0.55,"tempo":73.5,"seed":3},
    "Michigan State": {"eff_margin":22.1,"adj_o":117.5,"adj_d":95.4,"efg":0.530,"to_rate":0.168,"exp":0.95,"tempo":68.8,"seed":3},
    "Wisconsin":      {"eff_margin":21.8,"adj_o":116.8,"adj_d":95.0,"efg":0.525,"to_rate":0.155,"exp":0.98,"tempo":65.2,"seed":3},
    "Arizona":        {"eff_margin":21.4,"adj_o":119.2,"adj_d":97.8,"efg":0.548,"to_rate":0.170,"exp":0.65,"tempo":72.1,"seed":3},
    "Marquette":      {"eff_margin":20.8,"adj_o":118.1,"adj_d":97.3,"efg":0.540,"to_rate":0.162,"exp":0.80,"tempo":70.5,"seed":4},
    "St John's":      {"eff_margin":20.5,"adj_o":117.8,"adj_d":97.3,"efg":0.536,"to_rate":0.165,"exp":0.72,"tempo":71.2,"seed":4},
    "Texas Tech":     {"eff_margin":20.2,"adj_o":116.5,"adj_d":96.3,"efg":0.522,"to_rate":0.160,"exp":0.85,"tempo":67.5,"seed":4},
    "Kentucky":       {"eff_margin":19.8,"adj_o":117.2,"adj_d":97.4,"efg":0.535,"to_rate":0.168,"exp":0.58,"tempo":71.8,"seed":4},
    "UConn":          {"eff_margin":19.4,"adj_o":116.9,"adj_d":97.5,"efg":0.532,"to_rate":0.165,"exp":0.75,"tempo":68.2,"seed":5},
    "Gonzaga":        {"eff_margin":19.1,"adj_o":118.5,"adj_d":99.4,"efg":0.545,"to_rate":0.158,"exp":0.78,"tempo":73.8,"seed":5},
    "Baylor":         {"eff_margin":18.6,"adj_o":116.2,"adj_d":97.6,"efg":0.528,"to_rate":0.172,"exp":0.70,"tempo":70.1,"seed":5},
    "Illinois":       {"eff_margin":18.2,"adj_o":115.8,"adj_d":97.6,"efg":0.525,"to_rate":0.170,"exp":0.82,"tempo":69.5,"seed":5},
    "San Diego State":{"eff_margin":9.8,"adj_o":109.5,"adj_d":99.7,"efg":0.475,"to_rate":0.185,"exp":0.88,"tempo":65.8,"seed":11},
    "NC State":       {"eff_margin":9.4,"adj_o":110.2,"adj_d":100.8,"efg":0.480,"to_rate":0.192,"exp":0.75,"tempo":68.1,"seed":11},
    "Grand Canyon":   {"eff_margin":8.6,"adj_o":110.5,"adj_d":101.9,"efg":0.485,"to_rate":0.182,"exp":0.90,"tempo":67.2,"seed":12},
    "McNeese":        {"eff_margin":8.2,"adj_o":110.2,"adj_d":102.0,"efg":0.482,"to_rate":0.185,"exp":0.88,"tempo":66.8,"seed":12},
}

CFB_FB = {
    "Georgia":      {"sp_plus":27.8,"off_sp":38.2,"def_sp":12.5,"home_edge":3.5,"sos_rank":8, "win_pct":0.917},
    "Ohio State":   {"sp_plus":26.5,"off_sp":42.1,"def_sp":15.6,"home_edge":3.5,"sos_rank":12,"win_pct":0.875},
    "Alabama":      {"sp_plus":25.2,"off_sp":39.5,"def_sp":14.3,"home_edge":3.5,"sos_rank":15,"win_pct":0.833},
    "Michigan":     {"sp_plus":22.8,"off_sp":35.8,"def_sp":13.0,"home_edge":3.5,"sos_rank":18,"win_pct":0.833},
    "Texas":        {"sp_plus":21.5,"off_sp":36.2,"def_sp":14.7,"home_edge":3.5,"sos_rank":22,"win_pct":0.792},
    "Penn State":   {"sp_plus":20.2,"off_sp":33.5,"def_sp":13.3,"home_edge":3.5,"sos_rank":20,"win_pct":0.792},
    "Oregon":       {"sp_plus":19.8,"off_sp":35.1,"def_sp":15.3,"home_edge":3.5,"sos_rank":25,"win_pct":0.750},
    "Notre Dame":   {"sp_plus":19.1,"off_sp":32.8,"def_sp":13.7,"home_edge":3.0,"sos_rank":28,"win_pct":0.750},
    "Florida State":{"sp_plus":18.4,"off_sp":31.5,"def_sp":13.1,"home_edge":3.5,"sos_rank":30,"win_pct":0.708},
    "Clemson":      {"sp_plus":17.8,"off_sp":29.8,"def_sp":12.0,"home_edge":3.5,"sos_rank":32,"win_pct":0.708},
    "LSU":          {"sp_plus":17.2,"off_sp":30.5,"def_sp":13.3,"home_edge":3.5,"sos_rank":18,"win_pct":0.667},
    "Oklahoma":     {"sp_plus":16.5,"off_sp":32.1,"def_sp":15.6,"home_edge":3.5,"sos_rank":35,"win_pct":0.667},
    "Tennessee":    {"sp_plus":15.8,"off_sp":31.8,"def_sp":16.0,"home_edge":3.5,"sos_rank":22,"win_pct":0.625},
    "USC":          {"sp_plus":15.2,"off_sp":33.5,"def_sp":18.3,"home_edge":3.0,"sos_rank":28,"win_pct":0.625},
    "Boise State":  {"sp_plus":10.5,"off_sp":23.8,"def_sp":13.3,"home_edge":4.0,"sos_rank":55,"win_pct":0.500},
    "Iowa":         {"sp_plus":11.2,"off_sp":20.5,"def_sp":9.3, "home_edge":3.5,"sos_rank":30,"win_pct":0.500},
}

# ─────────────────────────────────────────────────────────────────────────────
# LIVE DATA FETCHERS  (cached 6 hours — refreshes once per day automatically)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=21600, show_spinner=False)
def live_mlb():
    """pybaseball → Baseball Reference standings + FanGraphs pitching."""
    try:
        import pybaseball
        pybaseball.cache.enable()
        yr = date.today().year
        standings_raw = pybaseball.standings(yr)
        pitching_raw  = pybaseball.team_pitching(yr)
        stats = {}
        if standings_raw:
            for div in standings_raw:
                for _, r in div.iterrows():
                    nm  = str(r.get("Tm",""))
                    w   = float(r.get("W",0) or 0)
                    l   = float(r.get("L",1) or 1)
                    rs  = float(r.get("RS", r.get("R",0)) or 0)
                    ra  = float(r.get("RA",0) or 0)
                    g   = max(w+l, 1)
                    ab  = _mlb_abbr(nm)
                    if ab:
                        fb = MLB_FB.get(ab, {})
                        stats[ab] = {
                            "win_pct":      w/g,
                            "run_diff_pg":  (rs-ra)/g,
                            "last10":       fb.get("last10", 0.50),
                            "bullpen_era":  fb.get("bullpen_era", 4.50),
                            "ops":          fb.get("ops", 0.720),
                        }
        if pitching_raw is not None and not pitching_raw.empty:
            for _, r in pitching_raw.iterrows():
                ab = _mlb_abbr(str(r.get("Team", r.get("Tm",""))))
                if ab and ab in stats:
                    stats[ab]["bullpen_era"] = float(r.get("ERA", stats[ab]["bullpen_era"]) or stats[ab]["bullpen_era"])
        for k,v in MLB_FB.items():
            if k not in stats: stats[k] = v
        if len(stats) >= 20:
            return stats, "live"
    except: pass
    return MLB_FB, "fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_nba():
    """nba_api → official NBA advanced stats (net rating, off/def rtg, pace)."""
    try:
        from nba_api.stats.endpoints import leaguedashteamstats
        time.sleep(0.8)
        season = _nba_season()
        adv = leaguedashteamstats.LeagueDashTeamStats(
            season=season, measure_type_detailed_defense="Advanced", per_mode_detailed="PerGame"
        ).get_data_frames()[0]
        time.sleep(0.8)
        base = leaguedashteamstats.LeagueDashTeamStats(
            season=season, measure_type_detailed_defense="Base", per_mode_detailed="PerGame"
        ).get_data_frames()[0]
        stats = {}
        for _, r in adv.iterrows():
            nm = str(r.get("TEAM_NAME",""))
            br = base[base["TEAM_NAME"]==nm]
            w  = int(br["W"].values[0]) if not br.empty else 40
            l  = int(br["L"].values[0]) if not br.empty else 42
            g  = max(w+l, 1)
            stats[nm] = {
                "net_rtg": float(r.get("NET_RATING",0) or 0),
                "off_rtg": float(r.get("OFF_RATING",110) or 110),
                "def_rtg": float(r.get("DEF_RATING",112) or 112),
                "pace":    float(r.get("PACE",99) or 99),
                "wins": w, "losses": l,
                "last10": NBA_FB.get(nm, {}).get("last10", 0.50),
            }
        if len(stats) >= 25:
            return stats, "live"
    except: pass
    return NBA_FB, "fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_nfl():
    """nfl_data_py → nflfastR EPA per play, turnover margin, win%."""
    try:
        import nfl_data_py as nfl
        yr = date.today().year if date.today().month >= 8 else date.today().year - 1
        pbp = nfl.import_pbp_data([yr], downcast=True, cache=False)
        if pbp is None or pbp.empty: raise Exception("no pbp")
        plays = pbp[pbp["play_type"].isin(["pass","run"])]
        off   = plays.groupby("posteam")["epa"].mean().reset_index()
        off.columns = ["team","epa_off"]
        def_  = plays.groupby("defteam")["epa"].mean().reset_index()
        def_.columns = ["team","epa_def"]
        pbp["to"] = pbp["interception"].fillna(0) + pbp["fumble_lost"].fillna(0)
        tog = pbp.groupby("posteam")["to"].sum().reset_index()
        tot = pbp.groupby("defteam")["to"].sum().reset_index()
        tog.columns=["team","to_given"]; tot.columns=["team","to_taken"]
        sched = nfl.import_schedules([yr])
        w_map = {}
        if sched is not None and not sched.empty:
            fin = sched[sched["game_type"]=="REG"].dropna(subset=["home_score","away_score"])
            for _, r in fin.iterrows():
                ht,at = str(r["home_team"]), str(r["away_team"])
                hs,as_ = float(r["home_score"]), float(r["away_score"])
                for t,won in [(ht,hs>as_),(at,as_>hs)]:
                    if t not in w_map: w_map[t]={"w":0,"g":0}
                    w_map[t]["g"]+=1
                    if won: w_map[t]["w"]+=1
        mg = off.merge(def_,on="team",how="outer").merge(tog,on="team",how="left").merge(tot,on="team",how="left")
        stats = {}
        for _, r in mg.iterrows():
            ab   = str(r["team"])
            full = NFL_ABBR.get(ab)
            if not full: continue
            wg   = w_map.get(ab,{"w":0,"g":1})
            fb   = NFL_FB.get(full, {})
            to_m = int(float(r.get("to_taken",8) or 8) - float(r.get("to_given",8) or 8))
            stats[full] = {
                "epa_off":  float(r.get("epa_off",0) or 0),
                "epa_def":  float(r.get("epa_def",0) or 0),
                "to_margin":to_m,
                "win_pct":  wg["w"]/max(wg["g"],1),
                "pts_diff": fb.get("pts_diff",0),
            }
        if len(stats) >= 25: return stats, "live"
    except: pass
    return NFL_FB, "fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_cbb():
    """barttorvik.com T-Rank → free KenPom equivalent (adj eff margin, adj O/D, tempo, EFG)."""
    try:
        yr  = date.today().year
        url = f"https://barttorvik.com/trank.php?year={yr}&sort=&top=0&conlimit=All&csv=1"
        r   = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        if r.status_code != 200 or len(r.text) < 500: raise Exception("bad response")
        df  = pd.read_csv(StringIO(r.text), header=0)
        stats = {}
        for _, row in df.iterrows():
            try:
                nm    = str(row.iloc[0]).strip()
                adj_o = _safe_float(row, ["AdjOE"], row.iloc[4] if len(row)>4 else 110, 110)
                adj_d = _safe_float(row, ["AdjDE"], row.iloc[5] if len(row)>5 else 102, 102)
                efg   = _safe_float(row, ["EFG%","eFG%"], 50.0, 50.0)
                tempo = _safe_float(row, ["AdjTempo","Tempo"], 70.0, 70.0)
                rec   = str(row.get("Rec", row.iloc[3] if len(row)>3 else "0-0"))
                w,l   = _parse_rec(rec)
                matched = _cbb_fuzzy(nm)
                fb    = CBB_FB.get(matched or nm, {})
                key   = matched or nm
                stats[key] = {
                    "eff_margin": adj_o - adj_d,
                    "adj_o":      adj_o,
                    "adj_d":      adj_d,
                    "efg":        efg/100 if efg > 1 else efg,
                    "to_rate":    fb.get("to_rate", 0.180),
                    "exp":        fb.get("exp", 0.75),
                    "tempo":      tempo,
                    "seed":       fb.get("seed"),
                    "win_pct":    w/max(w+l,1),
                }
            except: continue
        for k,v in CBB_FB.items():
            if k not in stats: stats[k] = v
        if len(stats) >= 50: return stats, "live"
    except: pass
    return CBB_FB, "fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_cfb():
    """collegefootballdata.com → SP+ ratings, win records (free API key needed)."""
    try:
        if not CFBD_API_KEY:
            raise Exception("no key")
        yr  = date.today().year if date.today().month >= 8 else date.today().year - 1
        hdr = {"Authorization": f"Bearer {CFBD_API_KEY}"}
        sp_r  = requests.get(f"https://api.collegefootballdata.com/ratings/sp?year={yr}", headers=hdr, timeout=10)
        rec_r = requests.get(f"https://api.collegefootballdata.com/records?year={yr}",    headers=hdr, timeout=10)
        sp_d  = sp_r.json()  if sp_r.status_code  == 200 else []
        rec_d = rec_r.json() if rec_r.status_code == 200 else []
        rec_map = {}
        for r in rec_d:
            t = str(r.get("team",""))
            tot = r.get("total",{})
            w,l = tot.get("wins",0), tot.get("losses",0)
            rec_map[t] = w/max(w+l,1)
        stats = {}
        for item in sp_d:
            nm  = str(item.get("team",""))
            sp  = float(item.get("rating",0) or 0)
            off = float(item.get("offense",{}).get("rating",0) or 0)
            deff= float(item.get("defense",{}).get("rating",0) or 0)
            fb  = CFB_FB.get(nm, {})
            stats[nm] = {
                "sp_plus":  sp,
                "off_sp":   off,
                "def_sp":   abs(deff),
                "home_edge":fb.get("home_edge", 3.5),
                "sos_rank": fb.get("sos_rank", 60),
                "win_pct":  rec_map.get(nm, fb.get("win_pct", 0.500)),
            }
        for k,v in CFB_FB.items():
            if k not in stats: stats[k] = v
        if len(stats) >= 30: return stats, "live"
    except: pass
    return CFB_FB, "fallback" if not CFBD_API_KEY else "fallback"

# helpers
def _mlb_abbr(name):
    for full,ab in MLB_NAME_MAP.items():
        if full.lower() in name.lower() or name.lower() in full.lower(): return ab
    return MLB_NAME_MAP.get(name.strip())

def _nba_season():
    t = date.today()
    return f"{t.year}-{str(t.year+1)[2:]}" if t.month >= 10 else f"{t.year-1}-{str(t.year)[2:]}"

def _safe_float(row, keys, default_val, fallback):
    for k in keys:
        try:
            v = row.get(k)
            if v is not None: return float(v)
        except: pass
    try: return float(default_val)
    except: return fallback

def _parse_rec(s):
    try: p=str(s).split("-"); return int(p[0]),int(p[1])
    except: return 0,0

def _cbb_fuzzy(name):
    nl = name.lower().strip()
    for k in CBB_FB:
        if k.lower() in nl or nl in k.lower(): return k
    return None

def _fuzzy(name, db, fallback={}):
    nl = name.lower()
    for k,v in db.items():
        if k.lower() in nl or nl in k.lower(): return k,v
    best_k,best_v,best_n = name,fallback,0
    for k,v in db.items():
        n = len(set(nl.split()) & set(k.lower().split()))
        if n > best_n: best_n,best_k,best_v = n,k,v
    return best_k, best_v

# ─────────────────────────────────────────────────────────────────────────────
# SCORING MODELS
# ─────────────────────────────────────────────────────────────────────────────
def score_mlb(s):
    wn = s.get("win_pct",0.5)
    rd = max(0,min(1,(s.get("run_diff_pg",0)+3)/6))
    bp = max(0,min(1,1-(s.get("bullpen_era",4.5)-2)/5))
    op = max(0,min(1,(s.get("ops",0.720)-0.60)/0.22))
    ln = s.get("last10",0.5)
    return round((0.15*wn + 0.28*rd + 0.25*bp + 0.22*op + 0.10*ln)*100, 1)

def score_nba(s, b2b=False):
    nr = max(0,min(1,(s.get("net_rtg",0)+15)/30))
    ao = max(0,min(1,(s.get("off_rtg",110)-95)/30))
    ad = max(0,min(1,1-(s.get("def_rtg",112)-100)/20))
    pc = max(0,min(1,(s.get("pace",99)-85)/25))
    ln = s.get("last10",0.5)
    sc = (0.38*nr + 0.25*ao + 0.25*ad + 0.07*pc + 0.05*ln)*100
    return round(max(0,min(100, sc-(8 if b2b else 0))), 1)

def score_nfl(s):
    eo = max(0,min(1,(s.get("epa_off",0)+0.3)/0.6))
    ed = max(0,min(1,(0.3-s.get("epa_def",0))/0.6))
    tm = max(0,min(1,(s.get("to_margin",0)+12)/24))
    wp = s.get("win_pct",0.5)
    pd = max(0,min(1,(s.get("pts_diff",0)+14)/28))
    return round((0.32*eo + 0.32*ed + 0.16*tm + 0.10*wp + 0.10*pd)*100, 1)

def score_cbb(s):
    em = max(0,min(1,(s.get("eff_margin",0)+30)/65))
    ao = max(0,min(1,(s.get("adj_o",100)-90)/40))
    ad = max(0,min(1,1-(s.get("adj_d",105)-85)/35))
    ef = max(0,min(1,(s.get("efg",0.5)-0.42)/0.18))
    to = max(0,min(1,1-(s.get("to_rate",0.18)-0.12)/0.12))
    ex = s.get("exp",0.7)
    tp = max(0,min(1,(s.get("tempo",70)-58)/20))
    return round((0.28*em + 0.20*ao + 0.20*ad + 0.10*ef + 0.10*to + 0.08*ex + 0.04*tp)*100, 1)

def score_cfb(s):
    sp = max(0,min(1,(s.get("sp_plus",0)+10)/50))
    op = max(0,min(1,(s.get("off_sp",0)+5)/55))
    dp = max(0,min(1,1-(s.get("def_sp",5)-5)/30))
    he = max(0,min(1,s.get("home_edge",3.5)/5))
    wp = s.get("win_pct",0.5)
    sos= max(0,min(1,1-(s.get("sos_rank",50)-1)/130))
    return round((0.35*sp + 0.20*op + 0.20*dp + 0.10*he + 0.10*wp + 0.05*sos)*100, 1)

# ─────────────────────────────────────────────────────────────────────────────
# ODDS + SCORES FETCHERS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_odds(sport_key):
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
            params={"apiKey":ODDS_API_KEY,"regions":"us","markets":"h2h,spreads","oddsFormat":"american","dateFormat":"iso"},
            timeout=10)
        d = r.json()
        return d if isinstance(d,list) else []
    except: return []

@st.cache_data(ttl=60, show_spinner=False)
def fetch_espn(espn_sport, espn_league):
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/{espn_league}/scoreboard"
            f"?dates={date.today().strftime('%Y%m%d')}&limit=100",
            timeout=10)
        return r.json().get("events",[])
    except: return []

def parse_espn(events):
    games = []
    for e in events:
        comp   = e.get("competitions",[{}])[0]
        status = comp.get("status",{})
        state  = status.get("type",{}).get("state","pre")
        detail = status.get("type",{}).get("shortDetail","")
        home=away={}
        for t in comp.get("competitors",[]):
            if t.get("homeAway")=="home": home=t
            else:                         away=t
        hn = home.get("team",{}).get("shortDisplayName", home.get("team",{}).get("abbreviation","?"))
        an = away.get("team",{}).get("shortDisplayName", away.get("team",{}).get("abbreviation","?"))
        hs = home.get("score","—");  as_ = away.get("score","—")
        hr = (home.get("records",[{}])[0].get("summary","") if home.get("records") else "")
        ar = (away.get("records",[{}])[0].get("summary","") if away.get("records") else "")
        try:
            if int(str(home.get("curatedRank",{}).get("current","99")))<=25:
                hn = f"#{home['curatedRank']['current']} {hn}"
            if int(str(away.get("curatedRank",{}).get("current","99")))<=25:
                an = f"#{away['curatedRank']['current']} {an}"
        except: pass
        winner=""
        if state=="post" and str(hs).isdigit() and str(as_).isdigit():
            winner = hn if int(hs)>int(as_) else an
        try: gt=datetime.fromisoformat(e.get("date","").replace("Z","+00:00")).strftime("%-I:%M %p")
        except: gt=""
        games.append({"away":an,"away_score":as_,"away_rec":ar,
                      "home":hn,"home_score":hs,"home_rec":hr,
                      "state":state,"detail":detail,"gametime":gt,"winner":winner})
    games.sort(key=lambda x:{"in":0,"pre":1,"post":2}.get(x["state"],3))
    return games

# ─────────────────────────────────────────────────────────────────────────────
# GAME PARSERS  (odds + live stats → ranked matchup rows)
# ─────────────────────────────────────────────────────────────────────────────
def _extract_odds(g, home, away):
    hml=aml=fsp=None
    for bk in g.get("bookmakers",[]):
        if bk["key"] in ("draftkings","fanduel","betmgm","bovada"):
            for mkt in bk.get("markets",[]):
                if mkt["key"]=="h2h":
                    for o in mkt["outcomes"]:
                        if o["name"]==home: hml=o["price"]
                        if o["name"]==away: aml=o["price"]
                if mkt["key"]=="spreads":
                    for o in mkt["outcomes"]:
                        if o["name"]==home and fsp is None: fsp=o.get("point")
            break
    return hml,aml,fsp

def _gametime(g):
    try: return datetime.fromisoformat(g.get("commence_time","").replace("Z","+00:00")).strftime("%-I:%M %p ET")
    except: return ""

def _make_row(fav,dog,fs,ds,fml,dml,sp,gt,extra):
    gap = round(fs-ds, 1)
    if gap>=28:   rating="🟢 STRONG"
    elif gap>=16: rating="🟡 LEAN"
    elif gap>=6:  rating="⚪ TOSS-UP"
    else:         rating="🔵 DOG VALUE"
    sv = abs(sp) if sp else 0
    alt = "—"
    if gap>=28 and sv>=7:  alt=f"Alt -{int(sv-4)} to -{int(sv-2)}"
    elif gap>=16 and sv>=5: alt=f"Alt -{int(sv-3)}"
    row = {"Time":gt,"Favorite":fav,"Underdog":dog,"Fav ML":fml,"Dog ML":dml,
           "Spread":f"{fav} -{sv:.1f}" if sv else "—",
           "Fav Score":fs,"Dog Score":ds,"Gap":gap,"Rating":rating,"Alt Spread":alt}
    row.update(extra)
    return row

def parse_games(odds, sl, team_stats):
    rows = []
    for g in odds:
        home=g.get("home_team",""); away=g.get("away_team","")
        hml,aml,fsp = _extract_odds(g,home,away)
        gt = _gametime(g)
        fav,dog,fml,dml = (home,away,hml,aml) if (hml and aml and hml<=aml) else \
                          (away,home,aml,hml) if (hml and aml) else (home,away,hml,aml)

        if sl=="MLB":
            fc = MLB_NAME_MAP.get(fav, fav[:3].upper())
            dc = MLB_NAME_MAP.get(dog, dog[:3].upper())
            fs_ = team_stats.get(fc, MLB_FB.get(fc, {"win_pct":0.5,"run_diff_pg":0,"bullpen_era":4.5,"last10":0.5,"ops":0.710}))
            ds_ = team_stats.get(dc, MLB_FB.get(dc, {"win_pct":0.5,"run_diff_pg":0,"bullpen_era":4.5,"last10":0.5,"ops":0.710}))
            ex = {"Win%(F)":f"{fs_.get('win_pct',0.5):.3f}","Win%(D)":f"{ds_.get('win_pct',0.5):.3f}",
                  "RD/G(F)":f"{fs_.get('run_diff_pg',0):+.2f}","RD/G(D)":f"{ds_.get('run_diff_pg',0):+.2f}",
                  "BP ERA(F)":f"{fs_.get('bullpen_era',4.5):.2f}","OPS(F)":f"{fs_.get('ops',0.720):.3f}",
                  "Your Filter":"✅" if fs_.get("win_pct",0.5)>0.5 and ds_.get("win_pct",0.5)<0.5 else "—"}
            rows.append(_make_row(fc, dc, score_mlb(fs_), score_mlb(ds_), fml, dml, fsp, gt, ex))

        elif sl=="NBA":
            fn,fs_ = _fuzzy(fav, team_stats, {})
            dn,ds_ = _fuzzy(dog, team_stats, {})
            ex = {"Net Rtg(F)":f"{fs_.get('net_rtg',0):+.1f}","Net Rtg(D)":f"{ds_.get('net_rtg',0):+.1f}",
                  "Off Rtg(F)":f"{fs_.get('off_rtg',110):.1f}","Def Rtg(F)":f"{fs_.get('def_rtg',112):.1f}",
                  "Pace(F)":f"{fs_.get('pace',99):.1f}","⚠️ B2B":"Check schedule"}
            rows.append(_make_row(fn, dn, score_nba(fs_), score_nba(ds_), fml, dml, fsp, gt, ex))

        elif sl=="NFL":
            fn,fs_ = _fuzzy(fav, team_stats, {})
            dn,ds_ = _fuzzy(dog, team_stats, {})
            ex = {"EPA Off(F)":f"{fs_.get('epa_off',0):+.3f}","EPA Def(F)":f"{fs_.get('epa_def',0):+.3f}",
                  "TO Margin(F)":f"{fs_.get('to_margin',0):+d}","Win%(F)":f"{fs_.get('win_pct',0.5):.3f}",
                  "Pts Diff(F)":f"{fs_.get('pts_diff',0):+.1f}"}
            rows.append(_make_row(fn, dn, score_nfl(fs_), score_nfl(ds_), fml, dml, fsp, gt, ex))

        elif sl=="CBB":
            fn,fs_ = _fuzzy(fav, team_stats, {})
            dn,ds_ = _fuzzy(dog, team_stats, {})
            fss=fs_.get("seed"); dss=ds_.get("seed")
            uctx = CBB_SEED_HISTORY.get((min(fss,dss),max(fss,dss)),{}) if fss and dss else {}
            ur   = uctx.get("upset_rate")
            sv   = abs(fsp) if fsp else 0
            if sv>=4 and ur and ur>=0.30:   uf="⭐ PRIME UPSET"
            elif sv>=6:                      uf="👀 UPSET WATCH"
            elif sv>=4:                      uf="🎲 BLIND DOG"
            else:                            uf="—"
            ex = {"Eff Margin(F)":f"{fs_.get('eff_margin',0):+.1f}","Eff Margin(D)":f"{ds_.get('eff_margin',0):+.1f}",
                  "Adj O(F)":f"{fs_.get('adj_o',110):.1f}","Tempo(F)":f"{fs_.get('tempo',70):.1f}",
                  "Seed(F)":fss or "—","Seed(D)":dss or "—",
                  "Upset Flag":uf,"Hist Upset Rate":f"{ur:.0%}" if ur else "—"}
            rows.append(_make_row(fn, dn, score_cbb(fs_), score_cbb(ds_), fml, dml, fsp, gt, ex))

        elif sl=="CFB":
            fn,fs_ = _fuzzy(fav, team_stats, {})
            dn,ds_ = _fuzzy(dog, team_stats, {})
            sv = abs(fsp) if fsp else 0
            home_dog = dog==home and sv<=7
            ex = {"SP+(F)":f"{fs_.get('sp_plus',0):+.1f}","SP+(D)":f"{ds_.get('sp_plus',0):+.1f}",
                  "Off SP+(F)":f"{fs_.get('off_sp',0):.1f}","Win%(F)":f"{fs_.get('win_pct',0.5):.3f}",
                  "SOS Rank(F)":fs_.get("sos_rank",60),
                  "🏠 Home Dog":"⚠️ Value spot" if home_dog else "—"}
            rows.append(_make_row(fn, dn, score_cfb(fs_), score_cfb(ds_), fml, dml, fsp, gt, ex))

    return sorted(rows, key=lambda x:x["Gap"], reverse=True)

# ─────────────────────────────────────────────────────────────────────────────
# TRACKER
# ─────────────────────────────────────────────────────────────────────────────
def load_picks():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE) as f: return json.load(f)
    return []

def save_picks(p):
    with open(TRACKER_FILE,"w") as f: json.dump(p,f,indent=2)

def a2d(ml):
    try:
        ml=float(ml); return ml/100+1 if ml>0 else 100/abs(ml)+1
    except: return 1.91

def calc_summary(picks, sport=None, btype=None):
    f = [p for p in picks
         if (not sport or p.get("sport","").upper()==sport.upper())
         and (not btype or btype.lower() in p.get("bet_type","").lower())]
    s = [p for p in f if p.get("result") in ("W","L","P")]
    wins = len([p for p in s if p["result"]=="W"])
    pl   = sum((a2d(p.get("odds"))-1)*float(p.get("units",1)) if p["result"]=="W"
               else (-float(p.get("units",1)) if p["result"]=="L" else 0) for p in s)
    wgr  = sum(float(p.get("units",1)) for p in s)
    return {"total":len(s),"wins":wins,
            "losses":len([p for p in s if p["result"]=="L"]),
            "hit_rate":round(wins/len(s)*100,1) if s else 0,
            "pl":round(pl,2),"wagered":round(wgr,2),
            "roi":round(pl/wgr*100,1) if wgr>0 else 0,
            "pending":len(f)-len(s)}

# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def cr(v):
    if "STRONG" in str(v): return "background-color:#1a3a2a;color:#4ade80;font-weight:bold"
    if "LEAN"   in str(v): return "background-color:#2a2a1a;color:#facc15;font-weight:bold"
    if "DOG"    in str(v): return "background-color:#1a2a3a;color:#60a5fa;font-weight:bold"
    return "background-color:#1e2640;color:#94a3b8"

def cg(v):
    try:
        v=float(v)
        if v>=28: return "color:#4ade80;font-weight:bold"
        if v>=16: return "color:#facc15"
        return "color:#94a3b8"
    except: return ""

def cu(v):
    if "PRIME" in str(v): return "background-color:#2a1800;color:#fb923c;font-weight:bold"
    if "WATCH" in str(v): return "background-color:#2a2a1a;color:#facc15"
    if "BLIND" in str(v): return "background-color:#1e1a2e;color:#a78bfa"
    return ""

def score_card(g):
    state=g["state"]
    cls="live" if state=="in" else ("final" if state=="post" else "")
    hs=g["home_score"]; as_=g["away_score"]
    hw=state=="post" and str(hs).isdigit() and str(as_).isdigit() and int(hs)>int(as_)
    aw=state=="post" and str(hs).isdigit() and str(as_).isdigit() and int(as_)>int(hs)
    if state=="in":     sb=f'<span class="badge-live">🔴 {g["detail"]}</span>'
    elif state=="post": sb=f'<span class="badge-final">✅ Final</span>'
    else:               sb=f'<span class="badge-pre">🕐 {g["gametime"]}</span>'
    hc="color:#4ade80;font-weight:bold" if hw else "color:#7eeaff"
    ac="color:#4ade80;font-weight:bold" if aw else "color:#7eeaff"
    return f"""<div class="score-card {cls}" style="display:flex;align-items:center;justify-content:space-between">
      <div style="flex:1"><div style="font-weight:700;color:#e8eaf0">{g['away']}</div>
        <div style="font-size:0.72rem;color:#5a6478;font-family:'DM Mono',monospace">{g['away_rec']}</div></div>
      <div style="display:flex;gap:12px;align-items:center;margin:0 16px">
        <span style="font-family:'DM Mono',monospace;font-size:1.5rem;{ac}">{as_}</span>
        <span style="color:#2a3450">–</span>
        <span style="font-family:'DM Mono',monospace;font-size:1.5rem;{hc}">{hs}</span>
      </div>
      <div style="flex:1;text-align:right"><div style="font-weight:700;color:#e8eaf0">{g['home']}</div>
        <div style="font-size:0.72rem;color:#5a6478;font-family:'DM Mono',monospace">{g['home_rec']}</div></div>
      <div style="margin-left:20px;min-width:130px;text-align:center">{sb}</div>
    </div>"""

def source_badge(label):
    cls = "live" if label.startswith("live") or "Live" in label or "T-Rank" in label or "EPA" in label else "fallback"
    icon = "🟢" if cls=="live" else "🟡"
    return f'<span class="source-pill {cls}">{icon} {label}</span>'

def tier(s, t1=70, t2=55, t3=40):
    if s>=t1: return "💎 Elite"
    if s>=t2: return "🔵 Solid"
    if s>=t3: return "🟡 Avg"
    return "🔴 Weak"

def ct(v):
    if "Elite" in str(v): return "background-color:#1a3a2a;color:#4ade80;font-weight:bold"
    if "Solid" in str(v): return "background-color:#1a2a3a;color:#60a5fa"
    if "Avg"   in str(v): return "background-color:#2a2a1a;color:#facc15"
    return "background-color:#2a1a1a;color:#f87171"

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏆 Betting Dashboard")
    st.markdown(f"*{date.today().strftime('%A, %B %d')}*")
    st.divider()
    sport = st.radio("Sport", list(SPORT_CONFIG.keys()), label_visibility="collapsed")
    st.divider()
    if st.button("🔄 Refresh All Data", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.caption("Stats cache: 6 hrs · Odds: 5 min · Scores: 60 sec")
    st.divider()
    st.markdown("**Live Data Sources**")
    st.caption("⚾ pybaseball → Baseball Ref / FanGraphs")
    st.caption("🏀 nba_api → Official NBA stats")
    st.caption("🏈 nfl_data_py → nflfastR EPA")
    st.caption("🏀 barttorvik.com → T-Rank (free KenPom)")
    st.caption("🏈 cfbd API → SP+ ratings (free key)")
    st.divider()
    if not CFBD_API_KEY:
        st.warning("⚠️ Add free CFBD key for live CFB stats → collegefootballdata.com")

# ─────────────────────────────────────────────────────────────────────────────
# LOAD LIVE STATS
# ─────────────────────────────────────────────────────────────────────────────
cfg = SPORT_CONFIG[sport]
sl  = cfg["label"]
em  = {"MLB":"⚾","NBA":"🏀","NFL":"🏈","CBB":"🏀","CFB":"🏈"}.get(sl,"🏆")

with st.spinner(f"Loading live {sl} data..."):
    if sl=="MLB":   team_stats, src_label = live_mlb()
    elif sl=="NBA": team_stats, src_label = live_nba()
    elif sl=="NFL": team_stats, src_label = live_nfl()
    elif sl=="CBB": team_stats, src_label = live_cbb()
    else:           team_stats, src_label = live_cfb()
    odds  = fetch_odds(cfg["key"])
    espn  = parse_espn(fetch_espn(cfg["espn_sport"], cfg["espn_league"]))
    games = parse_games(odds, sl, team_stats)

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-header">
  <div>
    <div class="dash-title">{em} {sl} Betting Dashboard</div>
    <div class="dash-sub" style="margin-top:8px">
      {source_badge(src_label)}
      <span class="source-pill">Odds · {len(odds)} games</span>
      <span class="source-pill">Scores · ESPN</span>
    </div>
  </div>
  <div style="text-align:right;color:#5a6478;font-family:'DM Mono',monospace;font-size:0.8rem">
    {date.today().strftime("%b %d, %Y")} · {datetime.now().strftime("%-I:%M %p")}
  </div>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
extra_tab = {"CBB":"🎲 Upset Hunter", "NFL":"🏈 Situational", "NBA":"⚠️ B2B Watch"}.get(sl)
tab_names = ["📊 Today's Picks"] + ([extra_tab] if extra_tab else []) + \
            ["📺 Scoreboard", "📋 Cheat Sheet", "📈 Tracker"]
tabs = st.tabs(tab_names)
ti = {"p":0, "x":1 if extra_tab else None,
      "s":1 if not extra_tab else 2,
      "c":2 if not extra_tab else 3,
      "t":3 if not extra_tab else 4}

# ── PICKS TAB ─────────────────────────────────────────────────────────────────
with tabs[ti["p"]]:
    strong = [g for g in games if "STRONG" in g["Rating"]]
    lean   = [g for g in games if "LEAN"   in g["Rating"]]

    if not games:
        st.info(f"No {sl} games found today. Season may be inactive or try refreshing.")
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Games Today", len(games))
        c2.metric("🟢 Strong",   len(strong))
        c3.metric("🟡 Lean",     len(lean))
        if sl=="CBB":   c4.metric("⭐ Prime Upsets", len([g for g in games if "PRIME" in g.get("Upset Flag","")]))
        elif sl=="MLB": c4.metric("✅ Your Filter",   len([g for g in games if g.get("Your Filter")=="✅"]))
        elif sl=="CFB": c4.metric("🏠 Home Dog Spots",len([g for g in games if "Value" in g.get("🏠 Home Dog","")]))
        else:           c4.metric("Analyzed", len(games))

        st.divider()
        fa,fb = st.columns([2,1])
        filt = fa.selectbox("Show", ["All","Strong only","Strong + Lean"], key=f"f{sl}")
        srt  = fb.selectbox("Sort", ["Gap (best first)","Game time"],       key=f"s{sl}")
        filtered = games
        if filt=="Strong only":    filtered=[g for g in games if "STRONG" in g["Rating"]]
        elif filt=="Strong + Lean":filtered=[g for g in games if "STRONG" in g["Rating"] or "LEAN" in g["Rating"]]
        if srt=="Game time":       filtered=sorted(filtered, key=lambda x:x["Time"])

        df = pd.DataFrame(filtered)
        styled = df.style
        if "Rating"     in df.columns: styled=styled.applymap(cr, subset=["Rating"])
        if "Gap"        in df.columns: styled=styled.applymap(cg, subset=["Gap"])
        if "Upset Flag" in df.columns: styled=styled.applymap(cu, subset=["Upset Flag"])
        st.dataframe(styled, use_container_width=True, hide_index=True, height=min(600,50+len(df)*38))

        if strong:
            st.divider()
            st.markdown("#### ⭐ Top Picks Today")
            cols = st.columns(min(3, len(strong)))
            for i,g in enumerate(strong[:3]):
                with cols[i]:
                    alt = g.get("Alt Spread","—")
                    st.markdown(f"""<div class="pick-card strong">
                      <div style="font-size:1.05rem;font-weight:700;color:#e8eaf0">{g['Favorite']} vs {g['Underdog']}</div>
                      <div style="font-size:0.8rem;color:#8892a4;font-family:'DM Mono',monospace;margin-top:4px">{g['Time']} · Gap: {g['Gap']}</div>
                      <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center">
                        <span class="badge-green">{g['Rating']}</span>
                        <span style="font-family:'DM Mono',monospace;font-size:1.1rem;color:#7eeaff">{g.get('Fav ML','—')}</span>
                      </div>
                      {"<div style='font-size:0.8rem;color:#7eeaff;margin-top:6px'>"+alt+"</div>" if alt!="—" else ""}
                    </div>""", unsafe_allow_html=True)

# ── SPORT-SPECIFIC EXTRA TAB ──────────────────────────────────────────────────
if extra_tab and ti["x"] is not None:
    with tabs[ti["x"]]:
        if sl=="CBB":
            st.markdown("#### 🎲 Blind Dog Tracker — Every Dog Getting 4+ Points")
            st.caption("Strategy: 2 units on every underdog regardless of stats. Track over 50+ games to find out if it's +EV.")
            dogs = [g for g in games if g.get("Upset Flag","—")!="—"]
            if not dogs: st.info("No qualifying underdogs today.")
            else:
                df_d = pd.DataFrame([{
                    "Underdog":g["Underdog"],"vs Fav":g["Favorite"],
                    "Spread":g["Spread"],"Dog ML":g["Dog ML"],
                    "Upset Flag":g.get("Upset Flag","—"),
                    "Hist Rate":g.get("Hist Upset Rate","—"),
                    "Eff Gap":g["Gap"],"Units":"2u"
                } for g in sorted(dogs, key=lambda x:x["Gap"])])
                st.dataframe(df_d.style.applymap(cu,subset=["Upset Flag"]),use_container_width=True,hide_index=True)
            st.divider()
            st.markdown("##### NCAA Tournament Seed History")
            st.dataframe(pd.DataFrame({
                "Matchup":["1v16","2v15","3v14","4v13","5v12","6v11","7v10","8v9"],
                "Hist Upset Rate":["1%","6%","15%","21%","35%","37%","40%","49%"],
                "Best Play":["Lock fav","Fav lean","Check gap","Check gap","⭐ Bet dog","⭐ Bet dog","⭐ Coin flip","Model edge only"]
            }), use_container_width=True, hide_index=True)

        elif sl=="NFL":
            st.markdown("#### 🏈 NFL Situational Angles")
            st.info("**Top edges:** Home dog ≤3pts · DVOA/EPA gap >15 with spread <7 · Big TO margin gaps · Short rest (3-day week) fades")
            if games:
                sits=[]
                for g in games:
                    notes=[]
                    try:
                        sp=float(str(g.get("Spread","0")).replace(g.get("Favorite",""),"").replace("-","").strip() or 0)
                        if 0<sp<=3: notes.append("🏠 Tight line — dog value spot")
                    except: pass
                    try:
                        if abs(float(str(g.get("EPA Off(F)","0"))) - float(str(g.get("EPA Off(D)","0")))) > 0.12:
                            notes.append("📊 Big EPA edge")
                    except: pass
                    try:
                        if abs(int(str(g.get("TO Margin(F)","0")).replace("+","") or 0)) >= 5:
                            notes.append("🎲 TO margin edge")
                    except: pass
                    if notes:
                        sits.append({"Game":f"{g['Favorite']} vs {g['Underdog']}","Time":g["Time"],"Rating":g["Rating"],"Angles":" · ".join(notes)})
                if sits:
                    st.dataframe(pd.DataFrame(sits).style.applymap(cr,subset=["Rating"]),use_container_width=True,hide_index=True)
                else:
                    st.info("No standout situational spots today.")

        elif sl=="NBA":
            st.markdown("#### ⚠️ Back-to-Back Watch")
            st.warning("**B2B teams cover at ~44%** — the model applies an automatic 8pt penalty. Always verify on NBA.com/schedule.")
            st.markdown("""
            **Strongest B2B angles:**
            - Road team on B2B as big favorite → **Fade**
            - Home team on B2B as underdog → **Value on dog**
            - B2B team in nationally-televised primetime spot → **Extra caution**
            """)
            if games:
                st.dataframe(pd.DataFrame([{
                    "Game":f"{g['Favorite']} vs {g['Underdog']}","Time":g["Time"],
                    "Net Rtg Gap":g.get("Gap"),"Rating":g["Rating"],
                    "Net Rtg(F)":g.get("Net Rtg(F)"),"Net Rtg(D)":g.get("Net Rtg(D)"),
                    "⚠️ B2B":"Check NBA schedule"
                } for g in games]).style.applymap(cr,subset=["Rating"]),use_container_width=True,hide_index=True)

# ── SCOREBOARD TAB ────────────────────────────────────────────────────────────
with tabs[ti["s"]]:
    live  = [g for g in espn if g["state"]=="in"]
    final = [g for g in espn if g["state"]=="post"]
    pre   = [g for g in espn if g["state"]=="pre"]
    c1,c2,c3 = st.columns(3)
    c1.metric("🔴 Live Now", len(live))
    c2.metric("✅ Final",    len(final))
    c3.metric("🕐 Upcoming", len(pre))
    if not espn:
        st.info("No games today or scoreboard unavailable. Try refreshing.")
    else:
        if live:
            st.markdown("#### 🔴 Live Now")
            for g in live:   st.markdown(score_card(g), unsafe_allow_html=True)
        if final:
            st.markdown("#### ✅ Final Scores")
            for g in final:  st.markdown(score_card(g), unsafe_allow_html=True)
        if pre:
            st.markdown("#### 🕐 Upcoming")
            for g in pre:    st.markdown(score_card(g), unsafe_allow_html=True)
    st.caption("ESPN API · Scores refresh every 60 seconds · Click Refresh for latest")

# ── CHEAT SHEET TAB ───────────────────────────────────────────────────────────
with tabs[ti["c"]]:
    st.markdown(f"#### {em} {sl} Team Ratings")
    st.markdown(source_badge(src_label), unsafe_allow_html=True)
    st.markdown("")

    if sl=="MLB":
        rows=[{"Team":k,"Score":score_mlb(v),"Win%":f"{v.get('win_pct',0.5):.3f}",
               "RD/G":f"{v.get('run_diff_pg',0):+.2f}","BP ERA":f"{v.get('bullpen_era',4.5):.2f}",
               "OPS":f"{v.get('ops',0.720):.3f}","Tier":tier(score_mlb(v))} for k,v in team_stats.items()]
    elif sl=="NBA":
        rows=[{"Team":k,"Score":score_nba(v),"Net Rtg":f"{v.get('net_rtg',0):+.1f}",
               "Off Rtg":f"{v.get('off_rtg',110):.1f}","Def Rtg":f"{v.get('def_rtg',112):.1f}",
               "Pace":f"{v.get('pace',99):.1f}","W-L":f"{v.get('wins',0)}-{v.get('losses',0)}",
               "Tier":tier(score_nba(v))} for k,v in team_stats.items()]
    elif sl=="NFL":
        rows=[{"Team":k,"Score":score_nfl(v),"EPA Off":f"{v.get('epa_off',0):+.3f}",
               "EPA Def":f"{v.get('epa_def',0):+.3f}","TO Mgn":f"{v.get('to_margin',0):+d}",
               "Win%":f"{v.get('win_pct',0.5):.3f}","Pts Diff":f"{v.get('pts_diff',0):+.1f}",
               "Tier":tier(score_nfl(v))} for k,v in team_stats.items()]
    elif sl=="CBB":
        rows=[{"Team":k,"Seed":v.get("seed","—"),"Score":score_cbb(v),
               "Eff Margin":f"{v.get('eff_margin',0):+.1f}","Adj O":f"{v.get('adj_o',110):.1f}",
               "Adj D":f"{v.get('adj_d',102):.1f}","Tempo":f"{v.get('tempo',70):.1f}",
               "EFG%":f"{v.get('efg',0.5):.3f}","Win%":f"{v.get('win_pct',0.5):.3f}",
               "Tier":tier(score_cbb(v),75,60,45)} for k,v in team_stats.items()]
    else:
        rows=[{"Team":k,"Score":score_cfb(v),"SP+":f"{v.get('sp_plus',0):+.1f}",
               "Off SP+":f"{v.get('off_sp',0):.1f}","Def SP+":f"{v.get('def_sp',0):.1f}",
               "Win%":f"{v.get('win_pct',0.5):.3f}","SOS Rank":v.get("sos_rank",60),
               "Tier":tier(score_cfb(v))} for k,v in team_stats.items()]

    df_c = pd.DataFrame(rows).sort_values("Score", ascending=False)
    st.dataframe(df_c.style.applymap(ct, subset=["Tier"]), use_container_width=True, hide_index=True)

    notes = {
        "MLB": "**Run Diff/G** = run support proxy (pybaseball) · **BP ERA** = bullpen ERA (FanGraphs) · **OPS** = offensive production",
        "NBA": "**Net Rating** = pts/100 possessions differential — most predictive NBA stat · **B2B** penalty = -8pts applied automatically",
        "NFL": "**EPA Off/Def** = Expected Points Added per play (nflfastR) · negative EPA Def = better defense · **TO Margin** is biggest swing stat",
        "CBB": "**Eff Margin** = Adj O minus Adj D (barttorvik T-Rank, updates daily) · **Tempo** affects scoring variance and spread volatility",
        "CFB": "**SP+** = Bill Connelly efficiency metric (CFBD API) · **Home edge** worth ~3.5 pts in CFB · **SOS Rank** = strength of schedule",
    }
    st.divider()
    st.caption(notes.get(sl,""))

# ── TRACKER TAB ───────────────────────────────────────────────────────────────
with tabs[ti["t"]]:
    picks = load_picks()
    ov    = calc_summary(picks)

    st.markdown("#### 📈 Season Record — All Sports")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Overall",   f"{ov['wins']}-{ov['losses']}")
    c2.metric("Hit Rate",  f"{ov['hit_rate']}%")
    c3.metric("Units P&L", f"{'+' if ov['pl']>=0 else ''}{ov['pl']}u")
    c4.metric("ROI",       f"{'+' if ov['roi']>=0 else ''}{ov['roi']}%")
    c5.metric("Pending",   ov["pending"])

    st.divider()
    sport_cols = st.columns(5)
    for i,sk in enumerate(["MLB","NBA","NFL","CBB","CFB"]):
        s  = calc_summary(picks, sport=sk)
        pc = "color:#4ade80" if s["pl"]>=0 else "color:#f87171"
        with sport_cols[i]:
            st.markdown(f"""<div style="background:#131929;border:1px solid #1e2a45;border-radius:10px;padding:12px;text-align:center">
              <div style="font-size:0.75rem;color:#8892a4">{sk}</div>
              <div style="font-size:1rem;font-weight:700;color:#e8eaf0;margin:4px 0">{s['wins']}-{s['losses']}</div>
              <div style="font-size:0.85rem;font-family:'DM Mono',monospace;{pc}">{'+' if s['pl']>=0 else ''}{s['pl']}u</div>
              <div style="font-size:0.72rem;color:#5a6478">{s['hit_rate']}% · {s['pending']} pending</div>
            </div>""", unsafe_allow_html=True)

    st.divider()
    with st.expander("➕ Log a New Pick", expanded=False):
        c1,c2,c3 = st.columns(3)
        ps = c1.selectbox("Sport",    ["MLB","NBA","NFL","CBB","CFB"], key="ps",
                          index=["MLB","NBA","NFL","CBB","CFB"].index(sl))
        pb = c2.selectbox("Bet Type", ["Alt Spread","Parlay","Stat Model","Blind Dog","Upset","ML","Other"], key="pb")
        pf = c3.text_input("Favorite", key="pf")
        c4,c5,c6 = st.columns(3)
        pd_ = c4.text_input("Underdog", key="pd")
        po  = c5.text_input("Odds (e.g. -150)", key="po")
        pu  = c6.number_input("Units", 0.1, 10.0, 0.5, 0.25, key="pu")
        pn  = st.text_input("Notes (optional)", key="pn")
        if st.button("💾 Save Pick"):
            if pf and pd_:
                picks.append({"date":date.today().isoformat(),"sport":ps,"bet_type":pb,
                               "favorite":pf,"underdog":pd_,"odds":po,"units":pu,
                               "notes":pn,"result":"Pending"})
                save_picks(picks); st.success("✅ Saved!"); st.rerun()
            else:
                st.error("Enter at least a favorite and underdog.")

    if picks:
        st.markdown("#### 📋 All Picks — Mark Results")
        st.caption("Change Result to W / L / P then click Save Results.")
        ed = st.data_editor(
            pd.DataFrame(picks)[["date","sport","bet_type","favorite","underdog","odds","units","result","notes"]],
            column_config={"result": st.column_config.SelectboxColumn("Result",
                           options=["Pending","W","L","P"], required=True)},
            use_container_width=True, num_rows="dynamic", key="ped")
        if st.button("💾 Save Results"):
            save_picks(ed.to_dict("records"))
            st.success("✅ Results saved!"); st.rerun()
    else:
        st.info("No picks logged yet. Use the form above to add your first pick.")
