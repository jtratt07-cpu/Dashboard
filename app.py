"""
Unified Sports Betting Dashboard  v3.0
MLB · NBA · NFL · CBB · CFB

22 features:
 FIXES: EST/EDT timezone, St Johns dedup, decimals to hundredth,
        NFL season fix, fav/dog flip fallback, header clock
 FEATURES: logos, parlay builder, line movement, weather,
           email summary, confidence %, ML/spread pick,
           real B2B detection, injury flags, best book comparison,
           team search, implied probability, auto-refresh,
           CSV export, yesterday results, confidence bar viz,
           streak tracker, score explanations
"""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from io import StringIO
import json, os, time, warnings, re, math
warnings.filterwarnings("ignore")

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Betting Dashboard", page_icon="🏆",
                   layout="wide", initial_sidebar_state="auto")

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
.badge-blue{background:#1a2a3a;color:#60a5fa;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;font-family:'DM Mono',monospace;}
.badge-live{background:#3a1a1a;color:#ff6b6b;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;animation:pulse 1.5s infinite;}
.badge-final{background:#1a3a2a;color:#4ade80;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.badge-pre{background:#1e2640;color:#94a3b8;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;}
.badge-inj{background:#3a1a00;color:#fb923c;padding:2px 8px;border-radius:20px;font-size:0.70rem;font-weight:700;}
.badge-move-up{background:#1a3a2a;color:#4ade80;padding:2px 8px;border-radius:20px;font-size:0.70rem;font-weight:700;}
.badge-move-down{background:#3a1a1a;color:#f87171;padding:2px 8px;border-radius:20px;font-size:0.70rem;font-weight:700;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.6}}
.dash-header{background:linear-gradient(135deg,#0f1a35,#0a1228);border:1px solid #1e2a45;border-radius:16px;padding:24px 32px;margin-bottom:16px;}
.dash-title{font-size:1.8rem;font-weight:800;color:#e8eaf0;letter-spacing:-0.02em;}
.source-pill{display:inline-block;background:#131929;border:1px solid #1e2a45;border-radius:20px;padding:2px 10px;font-size:0.72rem;font-family:'DM Mono',monospace;color:#7eeaff;margin-right:4px;margin-bottom:4px;}
.source-pill.live{border-color:#4ade8055;color:#4ade80;}
.source-pill.fallback{border-color:#facc1555;color:#facc15;}
.last-night{background:#131929;border:1px solid #1e2a45;border-radius:10px;padding:10px 16px;margin-top:12px;}
.weather-card{background:#0f1a35;border:1px solid #1e3a55;border-radius:10px;padding:12px 16px;margin-bottom:8px;}
hr{border-color:#1e2640!important;}
#MainMenu,footer{visibility:hidden;}
header{visibility:visible!important;background:transparent!important;}
</style>
""", unsafe_allow_html=True)

# ── KEYS ──────────────────────────────────────────────────────────────────────
ODDS_API_KEY = "8762561865c3719f114b2d815aca3041"
CFBD_API_KEY = os.environ.get("CFBD_API_KEY", "")
WEATHER_KEY  = os.environ.get("WEATHER_API_KEY", "")
TRACKER_FILE = "picks_log.json"

SPORT_CONFIG = {
    "⚾ MLB": {"key":"baseball_mlb",          "espn_sport":"baseball",   "espn_league":"mlb",                     "label":"MLB"},
    "🏀 NBA": {"key":"basketball_nba",         "espn_sport":"basketball", "espn_league":"nba",                     "label":"NBA"},
    "🏈 NFL": {"key":"americanfootball_nfl",   "espn_sport":"football",   "espn_league":"nfl",                     "label":"NFL"},
    "🏀 CBB": {"key":"basketball_ncaab",       "espn_sport":"basketball", "espn_league":"mens-college-basketball", "label":"CBB"},
    "🏈 CFB": {"key":"americanfootball_ncaaf", "espn_sport":"football",   "espn_league":"college-football",        "label":"CFB"},
}

# ── TIMEZONE: hardcoded EST/EDT — no external library needed ──────────────────
def _is_edt(dt=None):
    """True if US Eastern Daylight Time (UTC-4). EDT: 2nd Sun Mar → 1st Sun Nov."""
    if dt is None: dt = datetime.utcnow()
    y = dt.year
    # 2nd Sunday in March
    mar = datetime(y, 3, 8)
    while mar.weekday() != 6: mar += timedelta(days=1)
    # 1st Sunday in November
    nov = datetime(y, 11, 1)
    while nov.weekday() != 6: nov += timedelta(days=1)
    return mar <= dt.replace(tzinfo=None) < nov

def utc_to_est(utc_str):
    """Convert ISO UTC string → 'H:MM AM/PM ET' in correct Eastern time."""
    try:
        utc_str = utc_str.replace("Z", "").replace("+00:00", "")
        dt = datetime.fromisoformat(utc_str)
        offset = timedelta(hours=-4) if _is_edt(dt) else timedelta(hours=-5)
        est = dt + offset
        suffix = "EDT" if _is_edt(dt) else "EST"
        return est.strftime("%-I:%M %p") + f" {suffix}"
    except:
        return ""

def now_est():
    """Current time as Eastern string for display."""
    dt = datetime.utcnow()
    offset = timedelta(hours=-4) if _is_edt(dt) else timedelta(hours=-5)
    est = dt + offset
    suffix = "EDT" if _is_edt(dt) else "EST"
    return est.strftime("%-I:%M %p") + f" {suffix}"

def today_est():
    """Today's date in Eastern time (handles UTC midnight edge case)."""
    dt = datetime.utcnow()
    offset = timedelta(hours=-4) if _is_edt(dt) else timedelta(hours=-5)
    return (dt + offset).date()

# ── TEAM NAME NORMALIZER ──────────────────────────────────────────────────────
NORM_MAP = {
    # St John's — harden all known API variants
    "st john's red storm":"St John's","saint john's":"St John's",
    "st. john's":"St John's","st johns":"St John's","st. johns":"St John's",
    "st. john's red storm":"St John's","st johns red storm":"St John's",
    "saint john's red storm":"St John's","stjohn's":"St John's",
    "unc tar heels":"North Carolina","north carolina tar heels":"North Carolina",
    "usc trojans":"USC","miami fl":"Miami","miami (fl)":"Miami",
    "ole miss rebels":"Ole Miss","mississippi rebels":"Ole Miss",
    "pitt panthers":"Pittsburgh","pitt":"Pittsburgh",
    "uconn huskies":"UConn","connecticut":"UConn",
}

def normalize_team(name):
    nl = str(name).lower().strip()
    # Extra guard: any "st/saint + john" variant that isn't Johns Hopkins
    if "john" in nl and "johns hop" not in nl and ("st" in nl or "saint" in nl):
        return "St John's"
    return NORM_MAP.get(nl, name)

# ── STADIUM / VENUE DATA ──────────────────────────────────────────────────────
MLB_STADIUMS = {
    "LAD":{"city":"Los Angeles","lat":34.0739,"lon":-118.2400,"roof":False},
    "ATL":{"city":"Atlanta","lat":33.8908,"lon":-84.4679,"roof":False},
    "PHI":{"city":"Philadelphia","lat":39.9057,"lon":-75.1665,"roof":False},
    "BAL":{"city":"Baltimore","lat":39.2838,"lon":-76.6218,"roof":False},
    "HOU":{"city":"Houston","lat":29.7573,"lon":-95.3555,"roof":True},
    "NYY":{"city":"New York","lat":40.8296,"lon":-73.9262,"roof":False},
    "MIL":{"city":"Milwaukee","lat":43.0280,"lon":-87.9712,"roof":True},
    "CLE":{"city":"Cleveland","lat":41.4962,"lon":-81.6852,"roof":False},
    "MIN":{"city":"Minneapolis","lat":44.9817,"lon":-93.2778,"roof":True},
    "BOS":{"city":"Boston","lat":42.3467,"lon":-71.0972,"roof":False},
    "SD": {"city":"San Diego","lat":32.7073,"lon":-117.1566,"roof":False},
    "SEA":{"city":"Seattle","lat":47.5915,"lon":-122.3325,"roof":True},
    "TOR":{"city":"Toronto","lat":43.6414,"lon":-79.3894,"roof":True},
    "TB": {"city":"Tampa","lat":27.7683,"lon":-82.6534,"roof":True},
    "SF": {"city":"San Francisco","lat":37.7786,"lon":-122.3893,"roof":False},
    "NYM":{"city":"New York","lat":40.7571,"lon":-73.8458,"roof":False},
    "STL":{"city":"St. Louis","lat":38.6226,"lon":-90.1928,"roof":False},
    "DET":{"city":"Detroit","lat":42.3390,"lon":-83.0485,"roof":False},
    "TEX":{"city":"Arlington","lat":32.7512,"lon":-97.0832,"roof":True},
    "ARI":{"city":"Phoenix","lat":33.4453,"lon":-112.0667,"roof":True},
    "CHC":{"city":"Chicago","lat":41.9484,"lon":-87.6553,"roof":False},
    "CIN":{"city":"Cincinnati","lat":39.0979,"lon":-84.5082,"roof":False},
    "KC": {"city":"Kansas City","lat":39.0517,"lon":-94.4803,"roof":False},
    "MIA":{"city":"Miami","lat":25.7781,"lon":-80.2197,"roof":True},
    "PIT":{"city":"Pittsburgh","lat":40.4469,"lon":-80.0057,"roof":False},
    "LAA":{"city":"Anaheim","lat":33.8003,"lon":-117.8827,"roof":False},
    "OAK":{"city":"Oakland","lat":37.7516,"lon":-122.2005,"roof":False},
    "COL":{"city":"Denver","lat":39.7559,"lon":-104.9942,"roof":False},
    "WSH":{"city":"Washington DC","lat":38.8730,"lon":-77.0074,"roof":False},
    "CWS":{"city":"Chicago","lat":41.8300,"lon":-87.6339,"roof":False},
}
NFL_STADIUMS = {
    "Buffalo Bills":        {"city":"Buffalo","lat":42.7738,"lon":-78.7870,"roof":False},
    "Green Bay Packers":    {"city":"Green Bay","lat":44.5013,"lon":-88.0622,"roof":False},
    "Chicago Bears":        {"city":"Chicago","lat":41.8623,"lon":-87.6167,"roof":False},
    "Pittsburgh Steelers":  {"city":"Pittsburgh","lat":40.4468,"lon":-80.0158,"roof":False},
    "Cleveland Browns":     {"city":"Cleveland","lat":41.5061,"lon":-81.6995,"roof":False},
    "New York Giants":      {"city":"New York","lat":40.8135,"lon":-74.0745,"roof":False},
    "New York Jets":        {"city":"New York","lat":40.8135,"lon":-74.0745,"roof":False},
    "New England Patriots": {"city":"Foxborough","lat":42.0909,"lon":-71.2643,"roof":False},
    "Denver Broncos":       {"city":"Denver","lat":39.7439,"lon":-105.0201,"roof":False},
    "Kansas City Chiefs":   {"city":"Kansas City","lat":39.0489,"lon":-94.4839,"roof":False},
    "Seattle Seahawks":     {"city":"Seattle","lat":47.5952,"lon":-122.3316,"roof":False},
    "San Francisco 49ers":  {"city":"Santa Clara","lat":37.4033,"lon":-121.9694,"roof":False},
    "Miami Dolphins":       {"city":"Miami","lat":25.9580,"lon":-80.2389,"roof":False},
    "Tampa Bay Buccaneers": {"city":"Tampa","lat":27.9759,"lon":-82.5033,"roof":False},
    "Carolina Panthers":    {"city":"Charlotte","lat":35.2258,"lon":-80.8528,"roof":False},
    "Washington Commanders":{"city":"Landover","lat":38.9076,"lon":-76.8645,"roof":False},
    "Philadelphia Eagles":  {"city":"Philadelphia","lat":39.9008,"lon":-75.1675,"roof":False},
    "Baltimore Ravens":     {"city":"Baltimore","lat":39.2780,"lon":-76.6227,"roof":False},
    "Cincinnati Bengals":   {"city":"Cincinnati","lat":39.0954,"lon":-84.5160,"roof":False},
    "Jacksonville Jaguars": {"city":"Jacksonville","lat":30.3239,"lon":-81.6373,"roof":False},
    "Tennessee Titans":     {"city":"Nashville","lat":36.1665,"lon":-86.7713,"roof":False},
    "Las Vegas Raiders":    {"city":"Las Vegas","lat":36.0909,"lon":-115.1833,"roof":True},
    "Arizona Cardinals":    {"city":"Glendale","lat":33.5276,"lon":-112.2626,"roof":True},
}

CBB_SEED_HISTORY = {
    (1,16):{"upset_rate":0.03},(2,15):{"upset_rate":0.06},
    (3,14):{"upset_rate":0.15},(4,13):{"upset_rate":0.21},
    (5,12):{"upset_rate":0.35},(6,11):{"upset_rate":0.37},
    (7,10):{"upset_rate":0.40},(8, 9):{"upset_rate":0.49},
}

# ── FALLBACK STATS ────────────────────────────────────────────────────────────
MLB_FB = {
    "LAD":{"win_pct":0.642,"run_diff_pg":1.80,"bullpen_era":3.45,"last10":0.70,"ops":0.788},
    "ATL":{"win_pct":0.617,"run_diff_pg":1.50,"bullpen_era":3.62,"last10":0.60,"ops":0.762},
    "PHI":{"win_pct":0.599,"run_diff_pg":1.30,"bullpen_era":3.55,"last10":0.60,"ops":0.758},
    "BAL":{"win_pct":0.580,"run_diff_pg":1.10,"bullpen_era":3.70,"last10":0.50,"ops":0.745},
    "HOU":{"win_pct":0.574,"run_diff_pg":1.00,"bullpen_era":3.80,"last10":0.50,"ops":0.741},
    "NYY":{"win_pct":0.568,"run_diff_pg":0.90,"bullpen_era":3.90,"last10":0.50,"ops":0.738},
    "MIL":{"win_pct":0.562,"run_diff_pg":0.80,"bullpen_era":3.95,"last10":0.50,"ops":0.735},
    "CLE":{"win_pct":0.556,"run_diff_pg":0.70,"bullpen_era":4.00,"last10":0.50,"ops":0.731},
    "MIN":{"win_pct":0.549,"run_diff_pg":0.50,"bullpen_era":4.10,"last10":0.40,"ops":0.728},
    "BOS":{"win_pct":0.543,"run_diff_pg":0.40,"bullpen_era":4.15,"last10":0.50,"ops":0.725},
    "SD": {"win_pct":0.537,"run_diff_pg":0.30,"bullpen_era":4.20,"last10":0.40,"ops":0.721},
    "SEA":{"win_pct":0.531,"run_diff_pg":0.20,"bullpen_era":4.25,"last10":0.40,"ops":0.718},
    "TOR":{"win_pct":0.525,"run_diff_pg":0.10,"bullpen_era":4.30,"last10":0.40,"ops":0.715},
    "TB": {"win_pct":0.519,"run_diff_pg":0.00,"bullpen_era":4.35,"last10":0.40,"ops":0.711},
    "SF": {"win_pct":0.512,"run_diff_pg":-0.10,"bullpen_era":4.40,"last10":0.40,"ops":0.708},
    "NYM":{"win_pct":0.506,"run_diff_pg":-0.20,"bullpen_era":4.50,"last10":0.40,"ops":0.705},
    "STL":{"win_pct":0.500,"run_diff_pg":-0.30,"bullpen_era":4.55,"last10":0.30,"ops":0.701},
    "DET":{"win_pct":0.494,"run_diff_pg":-0.40,"bullpen_era":4.60,"last10":0.30,"ops":0.698},
    "TEX":{"win_pct":0.488,"run_diff_pg":-0.50,"bullpen_era":4.70,"last10":0.30,"ops":0.695},
    "ARI":{"win_pct":0.481,"run_diff_pg":-0.60,"bullpen_era":4.75,"last10":0.30,"ops":0.691},
    "CHC":{"win_pct":0.475,"run_diff_pg":-0.70,"bullpen_era":4.80,"last10":0.30,"ops":0.688},
    "CIN":{"win_pct":0.469,"run_diff_pg":-0.80,"bullpen_era":4.90,"last10":0.30,"ops":0.685},
    "KC": {"win_pct":0.463,"run_diff_pg":-0.90,"bullpen_era":4.95,"last10":0.30,"ops":0.681},
    "MIA":{"win_pct":0.457,"run_diff_pg":-1.00,"bullpen_era":5.00,"last10":0.20,"ops":0.678},
    "PIT":{"win_pct":0.451,"run_diff_pg":-1.10,"bullpen_era":5.10,"last10":0.20,"ops":0.675},
    "LAA":{"win_pct":0.444,"run_diff_pg":-1.20,"bullpen_era":5.15,"last10":0.20,"ops":0.671},
    "OAK":{"win_pct":0.438,"run_diff_pg":-1.30,"bullpen_era":5.20,"last10":0.20,"ops":0.668},
    "COL":{"win_pct":0.420,"run_diff_pg":-1.80,"bullpen_era":5.50,"last10":0.20,"ops":0.645},
    "WSH":{"win_pct":0.432,"run_diff_pg":-1.40,"bullpen_era":5.30,"last10":0.20,"ops":0.661},
    "CWS":{"win_pct":0.400,"run_diff_pg":-2.00,"bullpen_era":5.80,"last10":0.10,"ops":0.621},
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
    # 2024-25 season stats (updated)
    "Cleveland Cavaliers":   {"net_rtg":12.10,"off_rtg":120.80,"def_rtg":108.70,"pace":97.20,"last10":0.70,"wins":48,"losses":12},
    "Oklahoma City Thunder": {"net_rtg":11.40,"off_rtg":119.50,"def_rtg":108.10,"pace":100.50,"last10":0.70,"wins":46,"losses":14},
    "Boston Celtics":        {"net_rtg":10.80,"off_rtg":121.20,"def_rtg":110.40,"pace":98.80,"last10":0.60,"wins":44,"losses":16},
    "Houston Rockets":       {"net_rtg":8.20, "off_rtg":114.80,"def_rtg":106.60,"pace":99.80,"last10":0.60,"wins":40,"losses":21},
    "Memphis Grizzlies":     {"net_rtg":7.90, "off_rtg":117.20,"def_rtg":109.30,"pace":102.10,"last10":0.60,"wins":39,"losses":22},
    "Golden State Warriors": {"net_rtg":6.50, "off_rtg":116.40,"def_rtg":109.90,"pace":100.20,"last10":0.50,"wins":36,"losses":25},
    "Denver Nuggets":        {"net_rtg":6.10, "off_rtg":117.10,"def_rtg":111.00,"pace":98.50,"last10":0.50,"wins":35,"losses":26},
    "Los Angeles Lakers":    {"net_rtg":5.80, "off_rtg":115.80,"def_rtg":110.00,"pace":99.10,"last10":0.50,"wins":35,"losses":26},
    "New York Knicks":       {"net_rtg":5.40, "off_rtg":114.90,"def_rtg":109.50,"pace":96.80,"last10":0.50,"wins":34,"losses":27},
    "Minnesota Timberwolves":{"net_rtg":4.90, "off_rtg":114.20,"def_rtg":109.30,"pace":98.40,"last10":0.50,"wins":33,"losses":28},
    "Indiana Pacers":        {"net_rtg":4.20, "off_rtg":119.50,"def_rtg":115.30,"pace":105.10,"last10":0.50,"wins":32,"losses":29},
    "LA Clippers":           {"net_rtg":3.80, "off_rtg":114.10,"def_rtg":110.30,"pace":97.50,"last10":0.40,"wins":31,"losses":30},
    "Dallas Mavericks":      {"net_rtg":3.10, "off_rtg":114.80,"def_rtg":111.70,"pace":98.80,"last10":0.40,"wins":30,"losses":31},
    "Milwaukee Bucks":       {"net_rtg":2.80, "off_rtg":115.20,"def_rtg":112.40,"pace":99.50,"last10":0.40,"wins":29,"losses":32},
    "Phoenix Suns":          {"net_rtg":1.90, "off_rtg":113.50,"def_rtg":111.60,"pace":99.20,"last10":0.40,"wins":27,"losses":34},
    "Sacramento Kings":      {"net_rtg":1.50, "off_rtg":115.80,"def_rtg":114.30,"pace":101.20,"last10":0.40,"wins":26,"losses":35},
    "Miami Heat":            {"net_rtg":0.80, "off_rtg":110.90,"def_rtg":110.10,"pace":96.50,"last10":0.40,"wins":25,"losses":36},
    "Orlando Magic":         {"net_rtg":0.40, "off_rtg":108.50,"def_rtg":108.10,"pace":95.80,"last10":0.40,"wins":24,"losses":37},
    "Atlanta Hawks":         {"net_rtg":-1.20,"off_rtg":114.20,"def_rtg":115.40,"pace":101.50,"last10":0.30,"wins":23,"losses":38},
    "Brooklyn Nets":         {"net_rtg":-3.80,"off_rtg":109.80,"def_rtg":113.60,"pace":98.80,"last10":0.30,"wins":20,"losses":41},
    "Toronto Raptors":       {"net_rtg":-4.50,"off_rtg":110.50,"def_rtg":115.00,"pace":97.20,"last10":0.30,"wins":19,"losses":42},
    "Chicago Bulls":         {"net_rtg":-4.20,"off_rtg":112.10,"def_rtg":116.30,"pace":99.20,"last10":0.30,"wins":20,"losses":41},
    "Philadelphia 76ers":    {"net_rtg":-5.10,"off_rtg":110.80,"def_rtg":115.90,"pace":97.50,"last10":0.30,"wins":18,"losses":43},
    "Utah Jazz":             {"net_rtg":-6.80,"off_rtg":109.20,"def_rtg":116.00,"pace":99.80,"last10":0.20,"wins":16,"losses":45},
    "New Orleans Pelicans":  {"net_rtg":-7.20,"off_rtg":108.80,"def_rtg":116.00,"pace":98.10,"last10":0.20,"wins":15,"losses":46},
    "San Antonio Spurs":     {"net_rtg":-5.40,"off_rtg":112.80,"def_rtg":118.20,"pace":100.50,"last10":0.40,"wins":18,"losses":43},
    "Portland Trail Blazers":{"net_rtg":-8.10,"off_rtg":108.50,"def_rtg":116.60,"pace":100.20,"last10":0.20,"wins":14,"losses":47},
    "Charlotte Hornets":     {"net_rtg":-9.20,"off_rtg":108.20,"def_rtg":117.40,"pace":99.80,"last10":0.20,"wins":13,"losses":48},
    "Detroit Pistons":       {"net_rtg":2.10, "off_rtg":113.50,"def_rtg":111.40,"pace":99.20,"last10":0.50,"wins":26,"losses":35},
    "Washington Wizards":    {"net_rtg":-11.50,"off_rtg":107.20,"def_rtg":118.70,"pace":99.40,"last10":0.10,"wins":11,"losses":50},
}
NFL_FB = {
    "Kansas City Chiefs":   {"epa_off":0.182,"epa_def":-0.145,"to_margin":8, "win_pct":0.812,"pts_diff":9.80},
    "Philadelphia Eagles":  {"epa_off":0.158,"epa_def":-0.128,"to_margin":6, "win_pct":0.750,"pts_diff":8.20},
    "San Francisco 49ers":  {"epa_off":0.142,"epa_def":-0.138,"to_margin":5, "win_pct":0.719,"pts_diff":7.50},
    "Baltimore Ravens":     {"epa_off":0.168,"epa_def":-0.082,"to_margin":4, "win_pct":0.719,"pts_diff":7.10},
    "Buffalo Bills":        {"epa_off":0.151,"epa_def":-0.095,"to_margin":5, "win_pct":0.688,"pts_diff":6.80},
    "Houston Texans":       {"epa_off":0.128,"epa_def":-0.072,"to_margin":3, "win_pct":0.656,"pts_diff":5.50},
    "Dallas Cowboys":       {"epa_off":0.112,"epa_def":-0.088,"to_margin":3, "win_pct":0.625,"pts_diff":5.20},
    "Detroit Lions":        {"epa_off":0.135,"epa_def":0.018, "to_margin":2, "win_pct":0.625,"pts_diff":5.00},
    "Miami Dolphins":       {"epa_off":0.125,"epa_def":0.042, "to_margin":1, "win_pct":0.594,"pts_diff":4.50},
    "Cincinnati Bengals":   {"epa_off":0.118,"epa_def":0.025, "to_margin":2, "win_pct":0.563,"pts_diff":4.10},
    "Los Angeles Rams":     {"epa_off":0.105,"epa_def":-0.015,"to_margin":1,"win_pct":0.563,"pts_diff":3.80},
    "Los Angeles Chargers": {"epa_off":0.088,"epa_def":-0.022,"to_margin":2,"win_pct":0.531,"pts_diff":3.20},
    "Tampa Bay Buccaneers": {"epa_off":0.095,"epa_def":0.028, "to_margin":1,"win_pct":0.531,"pts_diff":3.50},
    "Washington Commanders":{"epa_off":0.072,"epa_def":0.038, "to_margin":0,"win_pct":0.469,"pts_diff":1.80},
    "Cleveland Browns":     {"epa_off":0.068,"epa_def":-0.025,"to_margin":0,"win_pct":0.500,"pts_diff":2.20},
    "Pittsburgh Steelers":  {"epa_off":0.052,"epa_def":-0.055,"to_margin":1,"win_pct":0.500,"pts_diff":2.00},
    "Green Bay Packers":    {"epa_off":0.075,"epa_def":0.085, "to_margin":0,"win_pct":0.469,"pts_diff":1.10},
    "Seattle Seahawks":     {"epa_off":0.048,"epa_def":0.062, "to_margin":-1,"win_pct":0.438,"pts_diff":0.50},
    "Minnesota Vikings":    {"epa_off":0.055,"epa_def":0.088, "to_margin":-2,"win_pct":0.438,"pts_diff":0.40},
    "Jacksonville Jaguars": {"epa_off":0.058,"epa_def":0.032, "to_margin":-1,"win_pct":0.469,"pts_diff":1.20},
    "Indianapolis Colts":   {"epa_off":0.042,"epa_def":0.082, "to_margin":-1,"win_pct":0.406,"pts_diff":0.10},
    "New York Giants":      {"epa_off":0.018,"epa_def":0.088, "to_margin":-2,"win_pct":0.375,"pts_diff":-0.80},
    "New Orleans Saints":   {"epa_off":0.012,"epa_def":0.118, "to_margin":-2,"win_pct":0.344,"pts_diff":-2.00},
    "Tennessee Titans":     {"epa_off":0.015,"epa_def":0.108, "to_margin":-3,"win_pct":0.344,"pts_diff":-1.50},
    "Chicago Bears":        {"epa_off":-0.005,"epa_def":0.108,"to_margin":-3,"win_pct":0.313,"pts_diff":-2.80},
    "Las Vegas Raiders":    {"epa_off":0.005,"epa_def":0.118, "to_margin":-4,"win_pct":0.313,"pts_diff":-2.50},
    "New England Patriots": {"epa_off":-0.012,"epa_def":0.115,"to_margin":-3,"win_pct":0.281,"pts_diff":-3.20},
    "Denver Broncos":       {"epa_off":-0.025,"epa_def":0.102,"to_margin":-2,"win_pct":0.281,"pts_diff":-3.50},
    "Atlanta Falcons":      {"epa_off":-0.031,"epa_def":0.105,"to_margin":-5,"win_pct":0.250,"pts_diff":-4.00},
    "New York Jets":        {"epa_off":-0.042,"epa_def":0.108,"to_margin":-6,"win_pct":0.219,"pts_diff":-5.00},
    "Arizona Cardinals":    {"epa_off":-0.052,"epa_def":0.108,"to_margin":-5,"win_pct":0.188,"pts_diff":-5.80},
    "Carolina Panthers":    {"epa_off":-0.068,"epa_def":0.112,"to_margin":-7,"win_pct":0.156,"pts_diff":-7.20},
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
    "Auburn":         {"eff_margin":28.50,"adj_o":122.10,"adj_d":93.60,"efg":0.558,"to_rate":0.158,"exp":0.85,"tempo":72.10,"seed":1},
    "Duke":           {"eff_margin":27.20,"adj_o":121.80,"adj_d":94.60,"efg":0.551,"to_rate":0.162,"exp":0.60,"tempo":71.80,"seed":1},
    "Houston":        {"eff_margin":26.80,"adj_o":118.40,"adj_d":91.60,"efg":0.532,"to_rate":0.170,"exp":0.90,"tempo":68.50,"seed":1},
    "Florida":        {"eff_margin":25.90,"adj_o":120.20,"adj_d":94.30,"efg":0.545,"to_rate":0.165,"exp":0.75,"tempo":70.20,"seed":2},
    "Tennessee":      {"eff_margin":25.40,"adj_o":117.80,"adj_d":92.40,"efg":0.528,"to_rate":0.172,"exp":0.88,"tempo":67.80,"seed":2},
    "Kansas":         {"eff_margin":24.10,"adj_o":119.60,"adj_d":95.50,"efg":0.541,"to_rate":0.160,"exp":0.78,"tempo":71.50,"seed":2},
    "Iowa State":     {"eff_margin":23.80,"adj_o":118.90,"adj_d":95.10,"efg":0.538,"to_rate":0.163,"exp":0.82,"tempo":70.80,"seed":2},
    "Purdue":         {"eff_margin":23.20,"adj_o":120.40,"adj_d":97.20,"efg":0.555,"to_rate":0.155,"exp":0.92,"tempo":69.10,"seed":3},
    "Alabama":        {"eff_margin":22.70,"adj_o":121.00,"adj_d":98.30,"efg":0.562,"to_rate":0.175,"exp":0.55,"tempo":73.50,"seed":3},
    "Michigan State": {"eff_margin":22.10,"adj_o":117.50,"adj_d":95.40,"efg":0.530,"to_rate":0.168,"exp":0.95,"tempo":68.80,"seed":3},
    "Wisconsin":      {"eff_margin":21.80,"adj_o":116.80,"adj_d":95.00,"efg":0.525,"to_rate":0.155,"exp":0.98,"tempo":65.20,"seed":3},
    "Arizona":        {"eff_margin":21.40,"adj_o":119.20,"adj_d":97.80,"efg":0.548,"to_rate":0.170,"exp":0.65,"tempo":72.10,"seed":3},
    "Marquette":      {"eff_margin":20.80,"adj_o":118.10,"adj_d":97.30,"efg":0.540,"to_rate":0.162,"exp":0.80,"tempo":70.50,"seed":4},
    "St John's":      {"eff_margin":20.50,"adj_o":117.80,"adj_d":97.30,"efg":0.536,"to_rate":0.165,"exp":0.72,"tempo":71.20,"seed":4},
    "Texas Tech":     {"eff_margin":20.20,"adj_o":116.50,"adj_d":96.30,"efg":0.522,"to_rate":0.160,"exp":0.85,"tempo":67.50,"seed":4},
    "Kentucky":       {"eff_margin":19.80,"adj_o":117.20,"adj_d":97.40,"efg":0.535,"to_rate":0.168,"exp":0.58,"tempo":71.80,"seed":4},
    "UConn":          {"eff_margin":19.40,"adj_o":116.90,"adj_d":97.50,"efg":0.532,"to_rate":0.165,"exp":0.75,"tempo":68.20,"seed":5},
    "Gonzaga":        {"eff_margin":19.10,"adj_o":118.50,"adj_d":99.40,"efg":0.545,"to_rate":0.158,"exp":0.78,"tempo":73.80,"seed":5},
    "Baylor":         {"eff_margin":18.60,"adj_o":116.20,"adj_d":97.60,"efg":0.528,"to_rate":0.172,"exp":0.70,"tempo":70.10,"seed":5},
    "Illinois":       {"eff_margin":18.20,"adj_o":115.80,"adj_d":97.60,"efg":0.525,"to_rate":0.170,"exp":0.82,"tempo":69.50,"seed":5},
    "San Diego State":{"eff_margin":9.80,"adj_o":109.50,"adj_d":99.70,"efg":0.475,"to_rate":0.185,"exp":0.88,"tempo":65.80,"seed":11},
    "NC State":       {"eff_margin":9.40,"adj_o":110.20,"adj_d":100.80,"efg":0.480,"to_rate":0.192,"exp":0.75,"tempo":68.10,"seed":11},
    "Grand Canyon":   {"eff_margin":8.60,"adj_o":110.50,"adj_d":101.90,"efg":0.485,"to_rate":0.182,"exp":0.90,"tempo":67.20,"seed":12},
    "McNeese":        {"eff_margin":8.20,"adj_o":110.20,"adj_d":102.00,"efg":0.482,"to_rate":0.185,"exp":0.88,"tempo":66.80,"seed":12},
}
CFB_FB = {
    "Georgia":      {"sp_plus":27.80,"off_sp":38.20,"def_sp":12.50,"home_edge":3.5,"sos_rank":8, "win_pct":0.917},
    "Ohio State":   {"sp_plus":26.50,"off_sp":42.10,"def_sp":15.60,"home_edge":3.5,"sos_rank":12,"win_pct":0.875},
    "Alabama":      {"sp_plus":25.20,"off_sp":39.50,"def_sp":14.30,"home_edge":3.5,"sos_rank":15,"win_pct":0.833},
    "Michigan":     {"sp_plus":22.80,"off_sp":35.80,"def_sp":13.00,"home_edge":3.5,"sos_rank":18,"win_pct":0.833},
    "Texas":        {"sp_plus":21.50,"off_sp":36.20,"def_sp":14.70,"home_edge":3.5,"sos_rank":22,"win_pct":0.792},
    "Penn State":   {"sp_plus":20.20,"off_sp":33.50,"def_sp":13.30,"home_edge":3.5,"sos_rank":20,"win_pct":0.792},
    "Oregon":       {"sp_plus":19.80,"off_sp":35.10,"def_sp":15.30,"home_edge":3.5,"sos_rank":25,"win_pct":0.750},
    "Notre Dame":   {"sp_plus":19.10,"off_sp":32.80,"def_sp":13.70,"home_edge":3.0,"sos_rank":28,"win_pct":0.750},
    "Florida State":{"sp_plus":18.40,"off_sp":31.50,"def_sp":13.10,"home_edge":3.5,"sos_rank":30,"win_pct":0.708},
    "Clemson":      {"sp_plus":17.80,"off_sp":29.80,"def_sp":12.00,"home_edge":3.5,"sos_rank":32,"win_pct":0.708},
    "LSU":          {"sp_plus":17.20,"off_sp":30.50,"def_sp":13.30,"home_edge":3.5,"sos_rank":18,"win_pct":0.667},
    "Oklahoma":     {"sp_plus":16.50,"off_sp":32.10,"def_sp":15.60,"home_edge":3.5,"sos_rank":35,"win_pct":0.667},
    "Tennessee":    {"sp_plus":15.80,"off_sp":31.80,"def_sp":16.00,"home_edge":3.5,"sos_rank":22,"win_pct":0.625},
    "USC":          {"sp_plus":15.20,"off_sp":33.50,"def_sp":18.30,"home_edge":3.0,"sos_rank":28,"win_pct":0.625},
    "Boise State":  {"sp_plus":10.50,"off_sp":23.80,"def_sp":13.30,"home_edge":4.0,"sos_rank":55,"win_pct":0.500},
    "Iowa":         {"sp_plus":11.20,"off_sp":20.50,"def_sp":9.30, "home_edge":3.5,"sos_rank":30,"win_pct":0.500},
}

# ── LIVE DATA FETCHERS ────────────────────────────────────────────────────────

@st.cache_data(ttl=21600, show_spinner=False)
def live_mlb():
    try:
        import pybaseball
        pybaseball.cache.enable()
        yr = today_est().year
        standings_raw = pybaseball.standings(yr)
        pitching_raw  = pybaseball.team_pitching(yr)
        stats = {}
        if standings_raw:
            for div in standings_raw:
                for _, r in div.iterrows():
                    nm = str(r.get("Tm",""))
                    w  = float(r.get("W",0) or 0)
                    l  = float(r.get("L",1) or 1)
                    rs = float(r.get("RS", r.get("R",0)) or 0)
                    ra = float(r.get("RA",0) or 0)
                    g  = max(w+l,1)
                    ab = _mlb_abbr(nm)
                    if ab:
                        fb = MLB_FB.get(ab,{})
                        stats[ab] = {"win_pct":w/g,"run_diff_pg":(rs-ra)/g,
                                     "last10":fb.get("last10",0.50),
                                     "bullpen_era":fb.get("bullpen_era",4.50),
                                     "ops":fb.get("ops",0.720)}
        if pitching_raw is not None and not pitching_raw.empty:
            for _, r in pitching_raw.iterrows():
                ab = _mlb_abbr(str(r.get("Team",r.get("Tm",""))))
                if ab and ab in stats:
                    stats[ab]["bullpen_era"] = float(r.get("ERA",stats[ab]["bullpen_era"]) or stats[ab]["bullpen_era"])
        for k,v in MLB_FB.items():
            if k not in stats: stats[k] = v
        if len(stats) >= 20: return stats,"live"
    except: pass
    return MLB_FB,"fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_nba():
    try:
        from nba_api.stats.endpoints import leaguedashteamstats
        time.sleep(0.8)
        season = _nba_season()
        adv = leaguedashteamstats.LeagueDashTeamStats(
            season=season,measure_type_detailed_defense="Advanced",per_mode_detailed="PerGame"
        ).get_data_frames()[0]
        time.sleep(0.8)
        base = leaguedashteamstats.LeagueDashTeamStats(
            season=season,measure_type_detailed_defense="Base",per_mode_detailed="PerGame"
        ).get_data_frames()[0]
        stats = {}
        for _, r in adv.iterrows():
            nm = str(r.get("TEAM_NAME",""))
            br = base[base["TEAM_NAME"]==nm]
            w  = int(br["W"].values[0]) if not br.empty else 40
            l  = int(br["L"].values[0]) if not br.empty else 42
            stats[nm] = {
                "net_rtg":float(r.get("NET_RATING",0) or 0),
                "off_rtg":float(r.get("OFF_RATING",110) or 110),
                "def_rtg":float(r.get("DEF_RATING",112) or 112),
                "pace":float(r.get("PACE",99) or 99),
                "wins":w,"losses":l,
                "last10":NBA_FB.get(nm,{}).get("last10",0.50),
            }
        if len(stats) >= 25: return stats,"live"
    except: pass
    return NBA_FB,"fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_nfl():
    try:
        import nfl_data_py as nfl
        yr = today_est().year if today_est().month >= 9 else today_est().year-1
        pbp = nfl.import_pbp_data([yr],downcast=True,cache=False)
        if pbp is None or pbp.empty: raise Exception()
        plays = pbp[pbp["play_type"].isin(["pass","run"])]
        off = plays.groupby("posteam")["epa"].mean().reset_index(); off.columns=["team","epa_off"]
        dfn = plays.groupby("defteam")["epa"].mean().reset_index(); dfn.columns=["team","epa_def"]
        pbp["to"] = pbp["interception"].fillna(0)+pbp["fumble_lost"].fillna(0)
        tog = pbp.groupby("posteam")["to"].sum().reset_index(); tog.columns=["team","to_given"]
        tot = pbp.groupby("defteam")["to"].sum().reset_index(); tot.columns=["team","to_taken"]
        sched = nfl.import_schedules([yr])
        w_map = {}
        if sched is not None and not sched.empty:
            fin = sched[sched["game_type"]=="REG"].dropna(subset=["home_score","away_score"])
            for _, r in fin.iterrows():
                for t,won in [(str(r["home_team"]),float(r["home_score"])>float(r["away_score"])),
                               (str(r["away_team"]),float(r["away_score"])>float(r["home_score"]))]:
                    if t not in w_map: w_map[t]={"w":0,"g":0}
                    w_map[t]["g"]+=1
                    if won: w_map[t]["w"]+=1
        mg = off.merge(dfn,on="team",how="outer").merge(tog,on="team",how="left").merge(tot,on="team",how="left")
        stats = {}
        for _, r in mg.iterrows():
            ab = str(r["team"]); full = NFL_ABBR.get(ab)
            if not full: continue
            wg = w_map.get(ab,{"w":0,"g":1})
            fb = NFL_FB.get(full,{})
            to_m = int(float(r.get("to_taken",8) or 8)-float(r.get("to_given",8) or 8))
            stats[full] = {"epa_off":float(r.get("epa_off",0) or 0),
                           "epa_def":float(r.get("epa_def",0) or 0),
                           "to_margin":to_m,"win_pct":wg["w"]/max(wg["g"],1),
                           "pts_diff":fb.get("pts_diff",0)}
        if len(stats) >= 25: return stats,"live"
    except: pass
    return NFL_FB,"fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_cbb():
    try:
        yr  = today_est().year
        url = f"https://barttorvik.com/trank.php?year={yr}&sort=&top=0&conlimit=All&csv=1"
        r   = requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15)
        if r.status_code != 200 or len(r.text)<500: raise Exception()
        df  = pd.read_csv(StringIO(r.text),header=0)
        stats = {}
        seen = set()
        for _, row in df.iterrows():
            try:
                nm    = normalize_team(str(row.iloc[0]).strip())
                if nm in seen: continue
                seen.add(nm)
                adj_o = _sf(row,["AdjOE"],row.iloc[4] if len(row)>4 else 110,110)
                adj_d = _sf(row,["AdjDE"],row.iloc[5] if len(row)>5 else 102,102)
                efg   = _sf(row,["EFG%","eFG%"],50.0,50.0)
                tempo = _sf(row,["AdjTempo","Tempo"],70.0,70.0)
                rec   = str(row.get("Rec",row.iloc[3] if len(row)>3 else "0-0"))
                w,l   = _pr(rec)
                matched = _cbb_fuzzy(nm)
                fb    = CBB_FB.get(matched or nm,{})
                key   = matched or nm
                if key in stats: continue
                stats[key] = {"eff_margin":adj_o-adj_d,"adj_o":adj_o,"adj_d":adj_d,
                              "efg":efg/100 if efg>1 else efg,"to_rate":fb.get("to_rate",0.180),
                              "exp":fb.get("exp",0.75),"tempo":tempo,"seed":fb.get("seed"),
                              "win_pct":w/max(w+l,1)}
            except: continue
        for k,v in CBB_FB.items():
            if k not in stats: stats[k]=v
        if len(stats)>=50: return stats,"live"
    except: pass
    return CBB_FB,"fallback"

@st.cache_data(ttl=21600, show_spinner=False)
def live_cfb():
    try:
        if not CFBD_API_KEY: raise Exception()
        yr  = today_est().year if today_est().month>=8 else today_est().year-1
        hdr = {"Authorization":f"Bearer {CFBD_API_KEY}"}
        sp_r  = requests.get(f"https://api.collegefootballdata.com/ratings/sp?year={yr}",headers=hdr,timeout=10)
        rec_r = requests.get(f"https://api.collegefootballdata.com/records?year={yr}",headers=hdr,timeout=10)
        sp_d  = sp_r.json()  if sp_r.status_code==200 else []
        rec_d = rec_r.json() if rec_r.status_code==200 else []
        rec_map = {}
        for r in rec_d:
            t=str(r.get("team","")); tot=r.get("total",{})
            w,l=tot.get("wins",0),tot.get("losses",0)
            rec_map[t]=w/max(w+l,1)
        stats = {}
        for item in sp_d:
            nm=str(item.get("team",""))
            sp=float(item.get("rating",0) or 0)
            off=float(item.get("offense",{}).get("rating",0) or 0)
            deff=float(item.get("defense",{}).get("rating",0) or 0)
            fb=CFB_FB.get(nm,{})
            stats[nm]={"sp_plus":sp,"off_sp":off,"def_sp":abs(deff),
                       "home_edge":fb.get("home_edge",3.5),"sos_rank":fb.get("sos_rank",60),
                       "win_pct":rec_map.get(nm,fb.get("win_pct",0.500))}
        for k,v in CFB_FB.items():
            if k not in stats: stats[k]=v
        if len(stats)>=30: return stats,"live"
    except: pass
    return CFB_FB,"fallback"

# ── ESPN: SCORES + LOGOS + INJURIES + B2B ─────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def fetch_espn(espn_sport, espn_league, target_date=None):
    try:
        d = target_date or today_est()
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/{espn_league}/scoreboard"
            f"?dates={d.strftime('%Y%m%d')}&limit=100",timeout=10)
        return r.json().get("events",[])
    except: return []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_injuries(espn_sport, espn_league):
    """Pull injury report from ESPN."""
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/{espn_league}/injuries",
            timeout=10)
        data = r.json()
        inj = {}
        for item in data.get("injuries",[]):
            team = item.get("team",{}).get("displayName","")
            for p in item.get("injuries",[]):
                status = p.get("status","")
                if status.lower() in ("out","doubtful","questionable"):
                    name   = p.get("athlete",{}).get("displayName","")
                    pos    = p.get("athlete",{}).get("position",{}).get("abbreviation","")
                    if team not in inj: inj[team]=[]
                    inj[team].append(f"{name} ({pos}) {status}")
        return inj
    except: return {}

def get_b2b_teams(espn_sport, espn_league):
    """Teams that played yesterday — detected as B2B for today."""
    try:
        yesterday = today_est() - timedelta(days=1)
        events = fetch_espn(espn_sport, espn_league, yesterday)
        b2b = set()
        for e in events:
            for comp in e.get("competitions",[{}]):
                for t in comp.get("competitors",[]):
                    nm = t.get("team",{}).get("displayName","")
                    if nm: b2b.add(nm)
        return b2b
    except: return set()

def get_team_logo(team_id, abbr=""):
    """ESPN CDN logo URL."""
    if team_id:
        return f"https://a.espncdn.com/i/teamlogos/nba/500/{team_id}.png"
    return ""

def parse_espn_events(events):
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
        def tm(t):
            td = t.get("team",{})
            return {
                "name": td.get("displayName", td.get("shortDisplayName","")),
                "short": td.get("shortDisplayName", td.get("abbreviation","")),
                "abbr": td.get("abbreviation",""),
                "id":   td.get("id",""),
                "logo": td.get("logo",""),
                "score": t.get("score","—"),
                "rec":  (t.get("records",[{}])[0].get("summary","") if t.get("records") else ""),
                "rank": t.get("curatedRank",{}).get("current",""),
            }
        hd = tm(home); ad = tm(away)
        try:
            raw_time = e.get("date","")
            gt = utc_to_est(raw_time)
        except: gt=""
        winner=""
        hs,as_ = hd["score"],ad["score"]
        if state=="post" and str(hs).isdigit() and str(as_).isdigit():
            winner = hd["name"] if int(hs)>int(as_) else ad["name"]
        games.append({"home":hd,"away":ad,"state":state,"detail":detail,
                      "gametime":gt,"winner":winner,"raw_time":e.get("date","")})
    games.sort(key=lambda x:{"in":0,"pre":1,"post":2}.get(x["state"],3))
    return games

# ── WEATHER ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_weather(lat, lon, city, has_roof):
    if has_roof: return {"city":city,"roof":True}
    if not WEATHER_KEY: return None
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat":lat,"lon":lon,"appid":WEATHER_KEY,"units":"imperial"},timeout=8)
        d = r.json()
        temp  = round(d["main"]["temp"])
        wind  = round(d["wind"]["speed"])
        desc  = d["weather"][0]["description"].title()
        humid = d["main"]["humidity"]
        precip= d.get("rain",{}).get("1h",d.get("snow",{}).get("1h",0))
        impact = []
        if wind >= 15: impact.append(f"💨 Wind {wind} mph — fades total, watch flyball parks")
        if wind >= 20: impact.append("⚠️ Heavy wind — strongly fades over")
        if precip > 0: impact.append(f"🌧️ Precip {precip:.1f}mm — fades total, may cause delays")
        if temp < 40:  impact.append(f"🥶 {temp}°F — cold suppresses offense")
        if temp > 90:  impact.append(f"🌡️ {temp}°F — heat can boost offense/pitching fatigue")
        return {"city":city,"roof":False,"temp":temp,"wind":wind,"desc":desc,
                "humid":humid,"precip":precip,"impact":impact}
    except: return None

# ── ODDS ──────────────────────────────────────────────────────────────────────
BOOKS = ["draftkings","fanduel","betmgm","bovada","williamhill_us","barstool"]

@st.cache_data(ttl=300, show_spinner=False)
def fetch_odds(sport_key):
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
            params={"apiKey":ODDS_API_KEY,"regions":"us","markets":"h2h,spreads",
                    "oddsFormat":"american","dateFormat":"iso"},timeout=10)
        d = r.json()
        return d if isinstance(d,list) else []
    except: return []

def _extract_all_books(g, home, away):
    """Returns {book: {home_ml, away_ml, home_spread, away_spread}} + consensus."""
    book_data = {}
    for bk in g.get("bookmakers",[]):
        bk_key = bk["key"]
        bd = {"home_ml":None,"away_ml":None,"spread":None}
        for mkt in bk.get("markets",[]):
            if mkt["key"]=="h2h":
                for o in mkt["outcomes"]:
                    if o["name"]==home: bd["home_ml"]=o["price"]
                    if o["name"]==away: bd["away_ml"]=o["price"]
            if mkt["key"]=="spreads":
                for o in mkt["outcomes"]:
                    if o["name"]==home and bd["spread"] is None:
                        bd["spread"]=o.get("point")
        book_data[bk_key]=bd
    # Best ML for each side
    best_home = best_away = None
    best_home_book = best_away_book = ""
    for bk,bd in book_data.items():
        if bd["home_ml"] is not None:
            if best_home is None or bd["home_ml"]>best_home:
                best_home=bd["home_ml"]; best_home_book=bk
        if bd["away_ml"] is not None:
            if best_away is None or bd["away_ml"]>best_away:
                best_away=bd["away_ml"]; best_away_book=bk
    # Consensus spread (mode)
    spreads = [bd["spread"] for bd in book_data.values() if bd["spread"] is not None]
    consensus_spread = max(set(spreads),key=spreads.count) if spreads else None
    return book_data, best_home, best_home_book, best_away, best_away_book, consensus_spread

def _gametime_from_odds(g):
    try: return utc_to_est(g.get("commence_time",""))
    except: return ""

def ml_to_implied(ml):
    """Moneyline → implied win probability."""
    try:
        ml = float(ml)
        if ml < 0: return round(abs(ml)/(abs(ml)+100)*100, 2)
        else:       return round(100/(ml+100)*100, 2)
    except: return None

def gap_to_confidence(gap):
    """Model gap → confidence percentage (52% at gap=6, 82% at gap=40+)."""
    if gap <= 0:  return 50.00
    if gap >= 40: return 82.00
    return round(52.0 + (gap/40.0)*30.0, 2)

def conf_bar_html(conf, width=120):
    pct = min(max(conf,0),100)
    if pct >= 72:   col="#4ade80"
    elif pct >= 60: col="#facc15"
    else:           col="#f87171"
    # Fix 11: use percentage width instead of fixed pixels for mobile compatibility
    return (f'<div style="display:inline-flex;align-items:center;gap:6px;width:100%">'
            f'<div style="background:#1e2640;border-radius:6px;height:8px;flex:1;max-width:{width}px;overflow:hidden">'
            f'<div style="background:{col};height:8px;width:{pct:.0f}%;border-radius:6px"></div></div>'
            f'<span style="font-family:DM Mono,monospace;font-size:0.78rem;color:{col}">{pct:.0f}%</span></div>')

# ── DEFAULT WEIGHTS ───────────────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "MLB": {"Win%":15,"Run Diff/G":28,"Bullpen ERA":25,"OPS":22,"Last 10":10},
    "NBA": {"Net Rating":38,"Off Rating":25,"Def Rating":25,"Pace":7,"Last 10":5},
    "NFL": {"EPA Off":32,"EPA Def":32,"TO Margin":16,"Win%":10,"Pts Diff":10},
    "CBB": {"Eff Margin":28,"Adj O":20,"Adj D":20,"EFG%":10,"TO Rate":10,"Experience":8,"Tempo":4},
    "CFB": {"SP+":35,"Off SP+":20,"Def SP+":20,"Home Edge":10,"Win%":10,"SOS":5},
}

def _get_w(sport, key):
    """Get current weight for a stat, normalized to 0-1 fraction."""
    ss_key = f"w_{sport}_{key}"
    defaults = DEFAULT_WEIGHTS[sport]
    raw = st.session_state.get(ss_key, defaults[key])
    total = sum(st.session_state.get(f"w_{sport}_{k}", defaults[k]) for k in defaults)
    return raw / max(total, 1)

# ── SCORING MODELS (dynamic weights) ─────────────────────────────────────────
def score_mlb(s):
    wn = s.get("win_pct",0.5)
    rd = max(0,min(1,(s.get("run_diff_pg",0)+3)/6))
    bp = max(0,min(1,1-(s.get("bullpen_era",4.5)-2)/5))
    op = max(0,min(1,(s.get("ops",0.720)-0.60)/0.22))
    ln = s.get("last10",0.5)
    w  = {k:_get_w("MLB",k) for k in DEFAULT_WEIGHTS["MLB"]}
    return round((w["Win%"]*wn + w["Run Diff/G"]*rd + w["Bullpen ERA"]*bp + w["OPS"]*op + w["Last 10"]*ln)*100,2)

def score_nba(s,b2b=False):
    nr = max(0,min(1,(s.get("net_rtg",0)+15)/30))
    ao = max(0,min(1,(s.get("off_rtg",110)-95)/30))
    ad = max(0,min(1,1-(s.get("def_rtg",112)-100)/20))
    pc = max(0,min(1,(s.get("pace",99)-85)/25))
    ln = s.get("last10",0.5)
    w  = {k:_get_w("NBA",k) for k in DEFAULT_WEIGHTS["NBA"]}
    sc = (w["Net Rating"]*nr + w["Off Rating"]*ao + w["Def Rating"]*ad + w["Pace"]*pc + w["Last 10"]*ln)*100
    return round(max(0,min(100,sc-(8 if b2b else 0))),2)

def score_nfl(s):
    eo = max(0,min(1,(s.get("epa_off",0)+0.3)/0.6))
    ed = max(0,min(1,(0.3-s.get("epa_def",0))/0.6))
    tm = max(0,min(1,(s.get("to_margin",0)+12)/24))
    wp = s.get("win_pct",0.5)
    pd = max(0,min(1,(s.get("pts_diff",0)+14)/28))
    w  = {k:_get_w("NFL",k) for k in DEFAULT_WEIGHTS["NFL"]}
    return round((w["EPA Off"]*eo + w["EPA Def"]*ed + w["TO Margin"]*tm + w["Win%"]*wp + w["Pts Diff"]*pd)*100,2)

def score_cbb(s):
    em = max(0,min(1,(s.get("eff_margin",0)+30)/65))
    ao = max(0,min(1,(s.get("adj_o",100)-90)/40))
    ad = max(0,min(1,1-(s.get("adj_d",105)-85)/35))
    ef = max(0,min(1,(s.get("efg",0.5)-0.42)/0.18))
    to = max(0,min(1,1-(s.get("to_rate",0.18)-0.12)/0.12))
    ex = s.get("exp",0.7)
    tp = max(0,min(1,(s.get("tempo",70)-58)/20))
    w  = {k:_get_w("CBB",k) for k in DEFAULT_WEIGHTS["CBB"]}
    return round((w["Eff Margin"]*em + w["Adj O"]*ao + w["Adj D"]*ad + w["EFG%"]*ef +
                  w["TO Rate"]*to + w["Experience"]*ex + w["Tempo"]*tp)*100,2)

def score_cfb(s):
    sp = max(0,min(1,(s.get("sp_plus",0)+10)/50))
    op = max(0,min(1,(s.get("off_sp",0)+5)/55))
    dp = max(0,min(1,1-(s.get("def_sp",5)-5)/30))
    he = max(0,min(1,s.get("home_edge",3.5)/5))
    wp = s.get("win_pct",0.5)
    so = max(0,min(1,1-(s.get("sos_rank",50)-1)/130))
    w  = {k:_get_w("CFB",k) for k in DEFAULT_WEIGHTS["CFB"]}
    return round((w["SP+"]*sp + w["Off SP+"]*op + w["Def SP+"]*dp + w["Home Edge"]*he + w["Win%"]*wp + w["SOS"]*so)*100,2)

# ── GAME ROW BUILDER ──────────────────────────────────────────────────────────
def _make_row(fav,dog,fs,ds,bk_data,best_h,best_h_bk,best_a,best_a_bk,sp,gt,extra,
              fav_is_home,injuries,b2b_teams,fav_full,dog_full):
    gap  = round(fs-ds,2)
    conf = gap_to_confidence(gap)
    if gap>=28:   rating="🟢 STRONG"
    elif gap>=16: rating="🟡 LEAN"
    elif gap>=6:  rating="⚪ TOSS-UP"
    else:         rating="🔵 DOG VALUE"

    sv = abs(sp) if sp else 0
    alt= "—"
    if gap>=28 and sv>=7:   alt=f"Alt -{int(sv-4)} to -{int(sv-2)}"
    elif gap>=16 and sv>=5: alt=f"Alt -{int(sv-3)}"

    # Best odds
    fav_ml = best_h if fav_is_home else best_a
    dog_ml = best_a if fav_is_home else best_h
    fav_bk = best_h_bk if fav_is_home else best_a_bk
    dog_bk = best_a_bk if fav_is_home else best_h_bk

    # Implied probabilities
    fav_imp = ml_to_implied(fav_ml) if fav_ml else None
    dog_imp = ml_to_implied(dog_ml) if dog_ml else None

    # Value check: model confidence > implied prob
    fav_value = conf > fav_imp if fav_imp else False

    # General pick recommendation
    if gap >= 16:
        if sv >= 3:
            pick_rec = f"✅ {fav} -{sv:.1f}"
        else:
            pick_rec = f"✅ {fav} ML"
    elif gap >= 6:
        pick_rec = f"🟡 {fav} ML (lean)"
    else:
        pick_rec = f"🔵 {dog} ML (dog value)" if gap < 0 else "⚪ Pass"

    # Injury flags
    fav_inj = injuries.get(fav_full,[]) + injuries.get(fav,[])
    dog_inj = injuries.get(dog_full,[]) + injuries.get(dog,[])
    inj_flag = ""
    if fav_inj: inj_flag += f"⚠️{fav}: {', '.join(fav_inj[:2])} "
    if dog_inj: inj_flag += f"⚠️{dog}: {', '.join(dog_inj[:2])}"

    # B2B flag
    b2b_flag = ""
    if fav_full in b2b_teams or fav in b2b_teams: b2b_flag += f"⚠️ {fav} B2B "
    if dog_full in b2b_teams or dog in b2b_teams: b2b_flag += f"⚠️ {dog} B2B"

    # Line movement (from session state) — use sorted pair key to prevent fav/dog flip duplication
    move_flag = ""
    game_key = "_".join(sorted([fav, dog]))
    if "odds_open" not in st.session_state: st.session_state["odds_open"]={}
    if fav_ml is not None:
        if game_key not in st.session_state["odds_open"]:
            st.session_state["odds_open"][game_key] = fav_ml
        else:
            diff = fav_ml - st.session_state["odds_open"][game_key]
            if abs(diff) >= 5:
                move_flag = f"📈 Line moved {'+' if diff>0 else ''}{diff:.0f}" if diff>0 else f"📉 Line moved {diff:.0f}"

    # Book comparison string
    bk_lines = []
    for bk_nm in ["draftkings","fanduel","betmgm"]:
        bd = bk_data.get(bk_nm, {})
        fml = bd.get("home_ml") if fav_is_home else bd.get("away_ml")
        if fml is not None:
            try: bk_lines.append(f"{bk_nm[:2].upper()}: {fml:+.0f}")
            except: pass
    books_str = " · ".join(bk_lines) if bk_lines else "—"

    row = {
        "Time":gt,
        "Favorite":fav,
        "Underdog":dog,
        "Pick":pick_rec,
        "Fav Score":fs,
        "Dog Score":ds,
        "Gap":gap,
        "Conf%":conf,
        "Rating":rating,
        "Fav ML":f"{fav_ml:+.0f} ({fav_bk[:2].upper()})" if fav_ml else "—",
        "Dog ML":f"{dog_ml:+.0f} ({dog_bk[:2].upper()})" if dog_ml else "—",
        "Fav Impl%":f"{fav_imp:.2f}%" if fav_imp else "—",
        "Value":f"✅ +{conf-fav_imp:.1f}%" if fav_value and fav_imp else "—",
        "Spread":f"{fav} -{sv:.1f}" if sv else "—",
        "Alt Spread":alt,
        "Books":books_str,
        "Line Move":move_flag if move_flag else "—",
        "Injuries":inj_flag if inj_flag else "—",
        "B2B":b2b_flag if b2b_flag else "—",
    }
    row.update(extra)
    return row

# ── GAME PARSER ───────────────────────────────────────────────────────────────
# ── NBA TEAM NAME MAP (prevents fuzzy mismatch) ───────────────────────────────
NBA_NAME_MAP = {
    "Los Angeles Lakers":"Los Angeles Lakers",
    "LA Lakers":"Los Angeles Lakers",
    "Los Angeles Clippers":"LA Clippers",
    "LA Clippers":"LA Clippers",
    "Golden State Warriors":"Golden State Warriors",
    "GS Warriors":"Golden State Warriors",
    "Oklahoma City Thunder":"Oklahoma City Thunder",
    "OKC Thunder":"Oklahoma City Thunder",
    "New York Knicks":"New York Knicks",
    "NY Knicks":"New York Knicks",
    "Minnesota Timberwolves":"Minnesota Timberwolves",
    "Portland Trail Blazers":"Portland Trail Blazers",
    "San Antonio Spurs":"San Antonio Spurs",
    "New Orleans Pelicans":"New Orleans Pelicans",
    "Memphis Grizzlies":"Memphis Grizzlies",
    "Philadelphia 76ers":"Philadelphia 76ers",
    "Cleveland Cavaliers":"Cleveland Cavaliers",
    "Boston Celtics":"Boston Celtics",
    "Denver Nuggets":"Denver Nuggets",
    "Dallas Mavericks":"Dallas Mavericks",
    "Milwaukee Bucks":"Milwaukee Bucks",
    "Miami Heat":"Miami Heat",
    "Atlanta Hawks":"Atlanta Hawks",
    "Indiana Pacers":"Indiana Pacers",
    "Chicago Bulls":"Chicago Bulls",
    "Toronto Raptors":"Toronto Raptors",
    "Brooklyn Nets":"Brooklyn Nets",
    "Sacramento Kings":"Sacramento Kings",
    "Phoenix Suns":"Phoenix Suns",
    "Houston Rockets":"Houston Rockets",
    "Utah Jazz":"Utah Jazz",
    "Detroit Pistons":"Detroit Pistons",
    "Washington Wizards":"Washington Wizards",
    "Charlotte Hornets":"Charlotte Hornets",
    "Orlando Magic":"Orlando Magic",
}

def parse_games(odds_data, sl, team_stats, injuries, b2b_teams):
    rows = []
    seen_matchups = set()  # deduplicate by sorted team pair
    today_str = today_est().isoformat()  # Fix 4: filter to today's games only

    for g in odds_data:
        home_full = g.get("home_team",""); away_full = g.get("away_team","")

        # Fix 4: Skip games not scheduled for today in EST
        game_commence = g.get("commence_time","")
        if game_commence:
            try:
                utc_str = game_commence.replace("Z","").replace("+00:00","")
                game_dt = datetime.fromisoformat(utc_str)
                offset = timedelta(hours=-4) if _is_edt(game_dt) else timedelta(hours=-5)
                game_est_date = (game_dt + offset).date().isoformat()
                if game_est_date != today_str:
                    continue
            except:
                pass
        home_full = g.get("home_team",""); away_full = g.get("away_team","")

        # Deduplicate: skip if same team pair already processed
        matchup_key = tuple(sorted([home_full.lower(), away_full.lower()]))
        if matchup_key in seen_matchups:
            continue
        seen_matchups.add(matchup_key)

        gt = _gametime_from_odds(g)
        bk_data,best_h,best_h_bk,best_a,best_a_bk,sp = _extract_all_books(g,home_full,away_full)

        # Determine fav/dog using spread first, ML as fallback
        if sp is not None:
            fav_is_home = (sp < 0)
        elif best_h is not None and best_a is not None:
            fav_is_home = (best_h <= best_a)
        else:
            fav_is_home = True

        fav_full = home_full if fav_is_home else away_full
        dog_full = away_full if fav_is_home else home_full

        if sl == "MLB":
            fc = MLB_NAME_MAP.get(fav_full, fav_full[:3].upper())
            dc = MLB_NAME_MAP.get(dog_full, dog_full[:3].upper())
            fs_ = team_stats.get(fc, MLB_FB.get(fc,{}))
            ds_ = team_stats.get(dc, MLB_FB.get(dc,{}))
            if not fs_: fs_ = MLB_FB.get("NYY",{})
            if not ds_: ds_ = MLB_FB.get("CWS",{})
            ex = {"Win%(F)":f"{fs_.get('win_pct',0.5):.2f}",
                  "Win%(D)":f"{ds_.get('win_pct',0.5):.2f}",
                  "RD/G(F)":f"{fs_.get('run_diff_pg',0):+.2f}",
                  "BP ERA":f"{fs_.get('bullpen_era',4.5):.2f}",
                  "OPS(F)":f"{fs_.get('ops',0.720):.3f}",
                  "Filter":"✅" if fs_.get("win_pct",0.5)>0.5 and ds_.get("win_pct",0.5)<0.5 else "—"}
            rows.append(_make_row(fc,dc,score_mlb(fs_),score_mlb(ds_),bk_data,best_h,best_h_bk,
                                  best_a,best_a_bk,sp,gt,ex,fav_is_home,injuries,b2b_teams,fav_full,dog_full))

        elif sl == "NBA":
            # Use exact name map first, fall back to fuzzy only if needed
            fav_mapped = NBA_NAME_MAP.get(fav_full, fav_full)
            dog_mapped = NBA_NAME_MAP.get(dog_full, dog_full)
            fn,fs_ = (fav_mapped, team_stats[fav_mapped]) if fav_mapped in team_stats else _fuzzy(fav_full,team_stats,{})
            dn,ds_ = (dog_mapped, team_stats[dog_mapped]) if dog_mapped in team_stats else _fuzzy(dog_full,team_stats,{})
            b2b_f  = fav_full in b2b_teams or fn in b2b_teams
            b2b_d  = dog_full in b2b_teams or dn in b2b_teams
            ex = {"Net(F)":f"{fs_.get('net_rtg',0):+.2f}",
                  "Net(D)":f"{ds_.get('net_rtg',0):+.2f}",
                  "Off Rtg":f"{fs_.get('off_rtg',110):.2f}",
                  "Def Rtg":f"{fs_.get('def_rtg',112):.2f}",
                  "Pace":f"{fs_.get('pace',99):.2f}"}
            rows.append(_make_row(fn,dn,score_nba(fs_,b2b_f),score_nba(ds_,b2b_d),bk_data,best_h,best_h_bk,
                                  best_a,best_a_bk,sp,gt,ex,fav_is_home,injuries,b2b_teams,fav_full,dog_full))

        elif sl == "NFL":
            fn,fs_ = _fuzzy(fav_full,team_stats,{})
            dn,ds_ = _fuzzy(dog_full,team_stats,{})
            ex = {"EPA Off":f"{fs_.get('epa_off',0):+.3f}",
                  "EPA Def":f"{fs_.get('epa_def',0):+.3f}",
                  "TO Mgn":f"{fs_.get('to_margin',0):+d}",
                  "Win%":f"{fs_.get('win_pct',0.5):.2f}"}
            rows.append(_make_row(fn,dn,score_nfl(fs_),score_nfl(ds_),bk_data,best_h,best_h_bk,
                                  best_a,best_a_bk,sp,gt,ex,fav_is_home,injuries,b2b_teams,fav_full,dog_full))

        elif sl == "CBB":
            fn,fs_ = _fuzzy(normalize_team(fav_full),team_stats,{})
            dn,ds_ = _fuzzy(normalize_team(dog_full),team_stats,{})
            fss=fs_.get("seed"); dss=ds_.get("seed")
            uctx=CBB_SEED_HISTORY.get((min(fss,dss),max(fss,dss)),{}) if fss and dss else {}
            ur=uctx.get("upset_rate")
            sv2=abs(sp) if sp else 0
            if sv2>=4 and ur and ur>=0.30: uf="⭐ PRIME UPSET"
            elif sv2>=6:                   uf="👀 UPSET WATCH"
            elif sv2>=4:                   uf="🎲 BLIND DOG"
            else:                          uf="—"
            ex = {"Eff Mgn(F)":f"{fs_.get('eff_margin',0):+.2f}",
                  "Eff Mgn(D)":f"{ds_.get('eff_margin',0):+.2f}",
                  "Adj O":f"{fs_.get('adj_o',110):.2f}","Tempo":f"{fs_.get('tempo',70):.2f}",
                  "Seed(F)":fss or "—","Seed(D)":dss or "—",
                  "Upset":uf,"Hist%":f"{ur:.0%}" if ur else "—"}
            rows.append(_make_row(fn,dn,score_cbb(fs_),score_cbb(ds_),bk_data,best_h,best_h_bk,
                                  best_a,best_a_bk,sp,gt,ex,fav_is_home,injuries,b2b_teams,fav_full,dog_full))

        elif sl == "CFB":
            fn,fs_ = _fuzzy(fav_full,team_stats,{})
            dn,ds_ = _fuzzy(dog_full,team_stats,{})
            sv2=abs(sp) if sp else 0
            home_dog = (not fav_is_home) and sv2<=7
            ex = {"SP+(F)":f"{fs_.get('sp_plus',0):+.2f}",
                  "SP+(D)":f"{ds_.get('sp_plus',0):+.2f}",
                  "Win%":f"{fs_.get('win_pct',0.5):.2f}",
                  "SOS":fs_.get("sos_rank",60),
                  "HomeDog":"⚠️ Value" if home_dog else "—"}
            rows.append(_make_row(fn,dn,score_cfb(fs_),score_cfb(ds_),bk_data,best_h,best_h_bk,
                                  best_a,best_a_bk,sp,gt,ex,fav_is_home,injuries,b2b_teams,fav_full,dog_full))

    return sorted(rows,key=lambda x:x["Gap"],reverse=True)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def _mlb_abbr(name):
    for full,ab in MLB_NAME_MAP.items():
        if full.lower() in name.lower() or name.lower() in full.lower(): return ab
    return MLB_NAME_MAP.get(name.strip())

def _nba_season():
    t=today_est()
    return f"{t.year}-{str(t.year+1)[2:]}" if t.month>=10 else f"{t.year-1}-{str(t.year)[2:]}"

def _sf(row,keys,default,fallback):
    for k in keys:
        try:
            v=row.get(k)
            if v is not None: return float(v)
        except: pass
    try: return float(default)
    except: return fallback

def _pr(s):
    try: p=str(s).split("-"); return int(p[0]),int(p[1])
    except: return 0,0

def _cbb_fuzzy(name):
    nl=name.lower().strip()
    for k in CBB_FB:
        if k.lower() in nl or nl in k.lower(): return k
    return None

def _fuzzy(name,db,fallback={}):
    nl=name.lower()
    # Exact substring match (only if name is long enough to be meaningful)
    for k,v in db.items():
        kl=k.lower()
        if len(nl)>=5 and len(kl)>=5 and (kl in nl or nl in kl): return k,v
    best_k,best_v,best_n=name,fallback,0
    for k,v in db.items():
        words_nl=set(w for w in nl.split() if len(w)>2)
        words_k =set(w for w in k.lower().split() if len(w)>2)
        n=len(words_nl & words_k)
        if n>best_n: best_n,best_k,best_v=n,k,v
    return best_k,best_v

# ── TRACKER ───────────────────────────────────────────────────────────────────
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

def _safe_units(v):
    try: return float(str(v).replace("u","").strip())
    except: return 1.0

def calc_summary(picks,sport=None):
    f=[p for p in picks if not sport or p.get("sport","").upper()==sport.upper()]
    s=[p for p in f if p.get("result") in ("W","L","P")]
    wins=len([p for p in s if p["result"]=="W"])
    pl=sum((a2d(p.get("odds"))-1)*_safe_units(p.get("units",1)) if p["result"]=="W"
           else(-_safe_units(p.get("units",1)) if p["result"]=="L" else 0) for p in s)
    wgr=sum(_safe_units(p.get("units",1)) for p in s)
    return {"total":len(s),"wins":wins,
            "losses":len([p for p in s if p["result"]=="L"]),
            "hit_rate":round(wins/len(s)*100,2) if s else 0,
            "pl":round(pl,2),"wagered":round(wgr,2),
            "roi":round(pl/wgr*100,2) if wgr>0 else 0,
            "pending":len(f)-len(s)}

def calc_streak(picks,sport=None):
    f=[p for p in picks if (not sport or p.get("sport","").upper()==sport.upper())
       and p.get("result") in ("W","L")]
    if not f: return ""
    f=sorted(f,key=lambda x:x.get("date",""))
    streak=1; last=f[-1]["result"]
    for p in reversed(f[:-1]):
        if p["result"]==last: streak+=1
        else: break
    icon="🔥" if last=="W" else "❄️"
    return f"{icon} {streak}-{'W' if last=='W' else 'L'} streak"

def yesterday_summary(picks,sport=None):
    yesterday=(today_est()-timedelta(days=1)).isoformat()
    f=[p for p in picks if p.get("date","")[:10]==yesterday[:10]
       and p.get("result") in ("W","L")
       and (not sport or p.get("sport","").upper()==sport.upper())]
    if not f: return None
    w=len([p for p in f if p["result"]=="W"]); l=len(f)-w
    return {"w":w,"l":l,"picks":f}

# ── UI HELPERS ────────────────────────────────────────────────────────────────
def cr(v):
    if "STRONG" in str(v): return "background:#1a3a2a;color:#4ade80;font-weight:bold"
    if "LEAN"   in str(v): return "background:#2a2a1a;color:#facc15;font-weight:bold"
    if "DOG"    in str(v): return "background:#1a2a3a;color:#60a5fa;font-weight:bold"
    return "background:#1e2640;color:#94a3b8"

def cg(v):
    try:
        v=float(v)
        if v>=28: return "color:#4ade80;font-weight:bold"
        if v>=16: return "color:#facc15"
        return "color:#94a3b8"
    except: return ""

def cu(v):
    if "PRIME" in str(v): return "background:#2a1800;color:#fb923c;font-weight:bold"
    if "WATCH" in str(v): return "background:#2a2a1a;color:#facc15"
    if "BLIND" in str(v): return "background:#1e1a2e;color:#a78bfa"
    return ""

def cv(v):
    if "✅" in str(v): return "color:#4ade80;font-weight:bold"
    return ""

def tier(s,t1=70,t2=55,t3=40):
    if s>=t1: return "💎 Elite"
    if s>=t2: return "🔵 Solid"
    if s>=t3: return "🟡 Avg"
    return "🔴 Weak"

def ct(v):
    if "Elite" in str(v): return "background:#1a3a2a;color:#4ade80;font-weight:bold"
    if "Solid" in str(v): return "background:#1a2a3a;color:#60a5fa"
    if "Avg"   in str(v): return "background:#2a2a1a;color:#facc15"
    return "background:#2a1a1a;color:#f87171"

def source_badge(label):
    cls="live" if any(x in label for x in ["live","Live","T-Rank","EPA","CFBD"]) else "fallback"
    icon="🟢" if cls=="live" else "🟡"
    return f'<span class="source-pill {cls}">{icon} {label}</span>'

def logo_html(logo_url, name, size=28):
    if logo_url:
        return (f'<img src="{logo_url}" width="{size}" height="{size}" '
                f'style="border-radius:50%;vertical-align:middle;margin-right:4px" '
                f'onerror="this.style.display=\'none\'" />')
    return f'<span style="background:#1e2a45;color:#7eeaff;padding:2px 6px;border-radius:6px;font-size:0.7rem;font-family:DM Mono,monospace">{name[:3].upper()}</span> '

def score_card_html(g):
    hd=g["home"]; ad=g["away"]; state=g["state"]
    cls="live" if state=="in" else ("final" if state=="post" else "")
    hs=hd["score"]; as_=ad["score"]
    hw=state=="post" and str(hs).isdigit() and str(as_).isdigit() and int(hs)>int(as_)
    aw=state=="post" and str(hs).isdigit() and str(as_).isdigit() and int(as_)>int(hs)
    if state=="in":     sb=f'<span class="badge-live">🔴 {g["detail"]}</span>'
    elif state=="post": sb=f'<span class="badge-final">✅ Final</span>'
    else:               sb=f'<span class="badge-pre">🕐 {g["gametime"]}</span>'
    hc="color:#4ade80;font-weight:bold" if hw else "color:#7eeaff"
    ac="color:#4ade80;font-weight:bold" if aw else "color:#7eeaff"
    rnk_h=f"<span style='font-size:0.7rem;color:#facc15'>#{hd['rank']} </span>" if hd.get("rank") else ""
    rnk_a=f"<span style='font-size:0.7rem;color:#facc15'>#{ad['rank']} </span>" if ad.get("rank") else ""
    hl=logo_html(hd.get("logo",""),hd["short"])
    al=logo_html(ad.get("logo",""),ad["short"])
    return f"""<div class="score-card {cls}" style="display:flex;align-items:center;justify-content:space-between">
      <div style="flex:1;display:flex;align-items:center;gap:6px">{al}<div><div style="font-weight:700;color:#e8eaf0">{rnk_a}{ad['short']}</div>
        <div style="font-size:0.72rem;color:#5a6478;font-family:'DM Mono',monospace">{ad['rec']}</div></div></div>
      <div style="display:flex;gap:10px;align-items:center;margin:0 14px">
        <span style="font-family:'DM Mono',monospace;font-size:1.5rem;{ac}">{as_}</span>
        <span style="color:#2a3450">–</span>
        <span style="font-family:'DM Mono',monospace;font-size:1.5rem;{hc}">{hs}</span>
      </div>
      <div style="flex:1;text-align:right;display:flex;align-items:center;justify-content:flex-end;gap:6px">
        <div><div style="font-weight:700;color:#e8eaf0">{rnk_h}{hd['short']}</div>
        <div style="font-size:0.72rem;color:#5a6478;font-family:'DM Mono',monospace;text-align:right">{hd['rec']}</div></div>{hl}</div>
      <div style="margin-left:18px;min-width:130px;text-align:center">{sb}</div>
    </div>"""

# ── APPLY STAT OVERRIDES TO LIVE STATS ───────────────────────────────────────
def apply_overrides(stats, sport):
    """Merge any session-state overrides into the team stats dict."""
    result = {k: dict(v) for k,v in stats.items()}
    for ss_key, val in st.session_state.items():
        if not ss_key.startswith(f"override_{sport}_"): continue
        parts = ss_key.split("_")
        # format: override_SPORT_TEAM_stat  (team may have spaces → parts[3])
        # We stored as override_SPORT_TEAMNAME_statname
        team = parts[3]
        stat = "_".join(parts[4:])
        if team in result:
            result[team][stat] = val
    return result


if "odds_open"     not in st.session_state: st.session_state["odds_open"]     = {}
if "last_refresh"  not in st.session_state: st.session_state["last_refresh"]  = time.time()
if "auto_refresh"  not in st.session_state: st.session_state["auto_refresh"]  = False
if "odds_fetched"  not in st.session_state: st.session_state["odds_fetched"]  = now_est()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
# Fix 24: sync sidebar sport with session state so Today page filter can drive it too
if "active_sport" not in st.session_state:
    st.session_state["active_sport"] = "🏀 NBA"

with st.sidebar:
    st.markdown("### 🏆 Betting Dashboard")
    st.markdown(f"*{today_est().strftime('%A, %B %d')}*")
    st.markdown(f"<span style='font-size:0.75rem;color:#5a6478'>{now_est()}</span>", unsafe_allow_html=True)
    st.divider()
    sport_options = list(SPORT_CONFIG.keys())
    sport_idx = sport_options.index(st.session_state["active_sport"]) if st.session_state["active_sport"] in sport_options else 1
    sport = st.radio("Sport", sport_options, index=sport_idx, label_visibility="collapsed", key="sidebar_sport")
    st.session_state["active_sport"] = sport
    st.divider()
    if st.button("🔄 Refresh All Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state["odds_open"] = {}
        st.session_state["odds_fetched"] = now_est()
        st.rerun()
    auto_ref = st.checkbox("⏱️ Auto-refresh scores (60s)", value=st.session_state["auto_refresh"])
    st.session_state["auto_refresh"] = auto_ref
    if auto_ref:
        elapsed = int(time.time()-st.session_state["last_refresh"])
        remaining = max(0,60-elapsed)
        st.caption(f"Next refresh in {remaining}s")
        if elapsed >= 60:
            st.session_state["last_refresh"] = time.time()
            st.session_state["odds_fetched"] = now_est()
            st.toast("🔄 Auto-refreshing scores...", icon="⏱️")
            st.rerun()
    st.caption("Stats: 6hr cache · Odds: 5min · Scores: 60s")
    st.divider()
    st.markdown("**Live Data Sources**")
    st.caption("⚾ pybaseball → Baseball Ref")
    st.caption("🏀 nba_api → NBA.com stats")
    st.caption("🏈 nfl_data_py → nflfastR EPA")
    st.caption("🏀 barttorvik.com → T-Rank")
    st.caption("🏈 CFBD API → SP+ ratings")
    st.divider()
    if not CFBD_API_KEY:
        st.warning("⚠️ Add CFBD_API_KEY for live CFB → collegefootballdata.com")
    if not WEATHER_KEY:
        st.info("🌤️ Add WEATHER_API_KEY for weather → openweathermap.org")

# ── LOAD ALL DATA ─────────────────────────────────────────────────────────────
cfg = SPORT_CONFIG[sport]
sl  = cfg["label"]
em  = {"MLB":"⚾","NBA":"🏀","NFL":"🏈","CBB":"🏀","CFB":"🏈"}.get(sl,"🏆")

with st.spinner(f"Loading live {sl} data..."):
    if sl=="MLB":   team_stats,src_label = live_mlb()
    elif sl=="NBA": team_stats,src_label = live_nba()
    elif sl=="NFL": team_stats,src_label = live_nfl()
    elif sl=="CBB": team_stats,src_label = live_cbb()
    else:           team_stats,src_label = live_cfb()

    odds_raw = fetch_odds(cfg["key"])
    espn_today = parse_espn_events(fetch_espn(cfg["espn_sport"],cfg["espn_league"]))
    injuries   = fetch_injuries(cfg["espn_sport"],cfg["espn_league"])
    b2b_teams  = get_b2b_teams(cfg["espn_sport"],cfg["espn_league"]) if sl=="NBA" else set()
    team_stats = apply_overrides(team_stats, sl)
    games      = parse_games(odds_raw,sl,team_stats,injuries,b2b_teams)

picks_all = load_picks()

# ── HEADER ────────────────────────────────────────────────────────────────────
yest = yesterday_summary(picks_all,sl)
streak_str = calc_streak(picks_all,sl)

last_night_html = ""
if yest:
    picks_txt = " · ".join([f"{p.get('favorite','?')} {'✅' if p['result']=='W' else '❌'}" for p in yest["picks"][:5]])
    last_night_html = f"""<div class="last-night">
      <span style="font-size:0.75rem;color:#8892a4">LAST NIGHT</span>
      <span style="margin-left:8px;font-family:'DM Mono',monospace;font-size:0.85rem;color:#e8eaf0">
        {yest['w']}-{yest['l']} · {picks_txt}</span></div>"""

_weather_pill = '<span class="source-pill">🌤️ Weather</span>' if WEATHER_KEY else ''
_streak_pill  = f'<span class="source-pill live">🔥 {streak_str}</span>' if streak_str else ''
_date_str     = today_est().strftime("%b %d, %Y")
_time_str     = now_est()
_src_badge    = source_badge(src_label)
_odds_ct      = len(odds_raw)
_odds_ts      = st.session_state.get("odds_fetched", now_est())

st.markdown(
    f'<div class="dash-header">'
    f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
    f'<div>'
    f'<div class="dash-title">{em} {sl} Betting Dashboard</div>'
    f'<div class="dash-sub" style="margin-top:8px">'
    f'{_src_badge}'
    f'<span class="source-pill">Odds · {_odds_ct} games · as of {_odds_ts}</span>'
    f'<span class="source-pill">Scores · ESPN</span>'
    f'{_weather_pill}{_streak_pill}'
    f'</div>'
    f'{last_night_html}'
    f'</div>'
    f'<div style="text-align:right;color:#5a6478;font-family:DM Mono,monospace;font-size:0.8rem">'
    f'{_date_str}<br>{_time_str}'
    f'</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True
)

# ── SCORE MODEL EXPLANATION ───────────────────────────────────────────────────
model_info = {
    "MLB":"Win% 15% · Run Diff/G 28% · Bullpen ERA 25% · OPS 22% · Last 10 10%",
    "NBA":"Net Rating 38% · Off Rtg 25% · Def Rtg 25% · Pace 7% · Last 10 5% (B2B = −8pts)",
    "NFL":"EPA Off 32% · EPA Def 32% · TO Margin 16% · Win% 10% · Pts Diff 10%",
    "CBB":"Eff Margin 28% · Adj O 20% · Adj D 20% · EFG 10% · TO Rate 10% · Exp 8% · Tempo 4%",
    "CFB":"SP+ 35% · Off SP+ 20% · Def SP+ 20% · Home Edge 10% · Win% 10% · SOS 5%",
}
with st.expander("📖 Score model explanation", expanded=False):
    st.markdown(f"**{sl} Model:** {model_info.get(sl,'')}")
    st.markdown("**Gap → Rating:** Gap ≥28 = 🟢 STRONG · Gap ≥16 = 🟡 LEAN · Gap ≥6 = ⚪ TOSS-UP · Gap <6 = 🔵 DOG VALUE")
    st.markdown("**Confidence %:** Converts gap to win probability (52% at gap=6 → 82% at gap=40+)")
    st.markdown("**Value:** Model confidence exceeds implied market probability = edge exists")

# ── TABS ──────────────────────────────────────────────────────────────────────
has_weather = sl in ("MLB","NFL","CFB")
has_extra   = sl in ("CBB","NFL","NBA")
extra_label = {"CBB":"🎲 Upset Hunter","NFL":"🏈 Situational","NBA":"⚠️ B2B Watch"}.get(sl,"")

tab_names = ["🗓️ Today","📊 Today's Picks"]
if has_extra:   tab_names.append(extra_label)
if has_weather: tab_names.append("🌤️ Weather")
tab_names += ["📺 Scoreboard","📋 Cheat Sheet","🎯 Parlay Builder","⚙️ Model Settings","📈 Tracker"]
tabs = st.tabs(tab_names)

def ti(name):
    # Fix 6: safety guard so tabs[None] never happens
    try: return tab_names.index(name)
    except ValueError: return None

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: TODAY (unified all-sports landing page)
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[ti("🗓️ Today")]:
    st.markdown(f"#### 🗓️ Today's Games — {today_est().strftime('%A, %B %d, %Y')}")

    # Sport filter — Fix 24: selecting here syncs the sidebar
    today_sport_opts = ["All Sports","⚾ MLB","🏀 NBA","🏈 NFL","🏀 CBB","🏈 CFB"]
    tf_col1, tf_col2, tf_col3 = st.columns([2,1,1])
    today_filter = tf_col1.selectbox(
        "Filter by sport", today_sport_opts, key="today_sport_filter",
        label_visibility="collapsed"
    )
    today_sort = tf_col2.selectbox("Sort by", ["Best picks first","Game time"], key="today_sort")
    today_rating_filter = tf_col3.selectbox("Show", ["All","Strong only","Strong + Lean"], key="today_rating_filt")

    # If a specific sport is selected, sync the sidebar sport selector
    if today_filter != "All Sports" and today_filter in SPORT_CONFIG:
        st.session_state["active_sport"] = today_filter

    # Gather games from all sports for "All Sports" view
    @st.cache_data(ttl=300, show_spinner=False)
    def get_all_today_games():
        all_rows = []
        for sp_key, cfg_ in SPORT_CONFIG.items():
            sl_ = cfg_["label"]
            try:
                odds_ = fetch_odds(cfg_["key"])
                inj_  = fetch_injuries(cfg_["espn_sport"], cfg_["espn_league"])
                b2b_  = get_b2b_teams(cfg_["espn_sport"], cfg_["espn_league"]) if sl_=="NBA" else set()
                if sl_=="MLB":   ts_,_ = live_mlb()
                elif sl_=="NBA": ts_,_ = live_nba()
                elif sl_=="NFL": ts_,_ = live_nfl()
                elif sl_=="CBB": ts_,_ = live_cbb()
                else:            ts_,_ = live_cfb()
                rows_ = parse_games(odds_, sl_, ts_, inj_, b2b_)
                for r in rows_:
                    r["_sport"] = sl_
                    r["_sport_icon"] = {"MLB":"⚾","NBA":"🏀","NFL":"🏈","CBB":"🏀","CFB":"🏈"}.get(sl_,"🏆")
                all_rows.extend(rows_)
            except:
                pass
        return all_rows

    if today_filter == "All Sports":
        with st.spinner("Loading all sports..."):
            all_today = get_all_today_games()
    else:
        # Use already-loaded games for current sport
        all_today = [dict(g, _sport=sl, _sport_icon=em) for g in games]

    # Apply rating filter
    if today_rating_filter == "Strong only":
        all_today = [g for g in all_today if "STRONG" in g["Rating"]]
    elif today_rating_filter == "Strong + Lean":
        all_today = [g for g in all_today if "STRONG" in g["Rating"] or "LEAN" in g["Rating"]]

    # Apply sort
    if today_sort == "Best picks first":
        all_today = sorted(all_today, key=lambda x: x["Gap"], reverse=True)
    else:
        all_today = sorted(all_today, key=lambda x: x["Time"])

    if not all_today:
        st.info("No games found for today. Try refreshing or check back later.")
    else:
        # Summary metrics row
        _strong_ct = len([g for g in all_today if "STRONG" in g["Rating"]])
        _lean_ct   = len([g for g in all_today if "LEAN"   in g["Rating"]])
        _avg_conf  = round(sum(g["Conf%"] for g in all_today)/len(all_today),1) if all_today else 0
        _sports_ct = len(set(g.get("_sport","?") for g in all_today))
        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("Total Games", len(all_today))
        m2.metric("🟢 Strong",   _strong_ct)
        m3.metric("🟡 Lean",     _lean_ct)
        m4.metric("Avg Conf",    f"{_avg_conf}%")
        m5.metric("Sports",      _sports_ct)

        st.divider()

        # Game cards — cleaner layout
        for g in all_today:
            sp_icon = g.get("_sport_icon","🏆")
            sp_lbl  = g.get("_sport","")
            rating  = g.get("Rating","")
            conf    = g.get("Conf%",50)
            gap     = g.get("Gap",0)

            # Rating color
            if "STRONG" in rating:   border_col="#4ade80"; badge_cls="badge-green"
            elif "LEAN" in rating:   border_col="#facc15"; badge_cls="badge-yellow"
            elif "DOG"  in rating:   border_col="#60a5fa"; badge_cls="badge-blue"
            else:                    border_col="#2a3450"; badge_cls="badge-pre"

            conf_pct = min(max(conf,0),100)
            conf_col = "#4ade80" if conf_pct>=72 else ("#facc15" if conf_pct>=60 else "#94a3b8")
            conf_fill = int(conf_pct/100*100)

            inj_html  = f'<div style="font-size:0.70rem;color:#fb923c;margin-top:3px">⚠️ {g["Injuries"]}</div>' if g.get("Injuries","—") != "—" else ""
            b2b_html  = f'<div style="font-size:0.70rem;color:#f87171;margin-top:2px">{g["B2B"]}</div>' if g.get("B2B","—") != "—" else ""
            move_html = f'<div style="font-size:0.70rem;color:#a78bfa;margin-top:2px">{g["Line Move"]}</div>' if g.get("Line Move","—") != "—" else ""
            spread_str = g.get("Spread","—")
            books_str  = g.get("Books","—")

            st.markdown(f"""
            <div style="background:#131929;border:1px solid {border_col}44;border-left:4px solid {border_col};
                        border-radius:12px;padding:14px 18px;margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
                <div style="flex:2;min-width:200px">
                  <div style="font-size:0.72rem;color:#5a6478;font-family:'DM Mono',monospace;margin-bottom:4px">
                    {sp_icon} {sp_lbl} · {g['Time']}
                  </div>
                  <div style="font-size:1.05rem;font-weight:700;color:#e8eaf0">
                    {g['Favorite']} <span style="color:#2a3450;font-weight:400">vs</span> {g['Underdog']}
                  </div>
                  <div style="font-size:0.82rem;color:#4ade80;font-weight:700;margin-top:4px">{g.get('Pick','')}</div>
                  {inj_html}{b2b_html}{move_html}
                </div>
                <div style="flex:1;min-width:140px;text-align:center">
                  <div style="font-size:0.70rem;color:#8892a4;margin-bottom:4px">CONFIDENCE</div>
                  <div style="background:#1e2640;border-radius:6px;height:8px;width:100%;max-width:160px;overflow:hidden;margin:0 auto 4px">
                    <div style="background:{conf_col};height:8px;width:{conf_fill}%;border-radius:6px"></div>
                  </div>
                  <div style="font-family:'DM Mono',monospace;font-size:0.9rem;color:{conf_col};font-weight:700">{conf:.0f}%</div>
                  <div style="font-size:0.70rem;color:#5a6478;margin-top:2px">Gap {gap:.1f}</div>
                </div>
                <div style="flex:1;min-width:140px;text-align:right">
                  <span class="{badge_cls}" style="padding:3px 10px;border-radius:20px;font-size:0.75rem;font-weight:700;font-family:'DM Mono',monospace;
                    background:{'#1a3a2a' if 'STRONG' in rating else ('#2a2a1a' if 'LEAN' in rating else '#1a2a3a')};
                    color:{border_col}">{rating}</span>
                  <div style="margin-top:8px;font-family:'DM Mono',monospace;font-size:0.82rem;color:#7eeaff">
                    {g.get('Fav ML','—')}
                  </div>
                  <div style="font-size:0.70rem;color:#5a6478;margin-top:2px">{spread_str}</div>
                  <div style="font-size:0.68rem;color:#3a4a6a;margin-top:2px">{books_str}</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # Top strong picks summary at bottom
        top_strong = [g for g in all_today if "STRONG" in g["Rating"]][:5]
        if top_strong:
            st.divider()
            st.markdown("##### ⭐ Best Bets Today")
            for g in top_strong:
                sp_icon = g.get("_sport_icon","🏆")
                st.markdown(
                    f'<span style="font-family:DM Mono,monospace;font-size:0.85rem;color:#4ade80">✅ {g["Pick"]}</span>'
                    f'<span style="color:#5a6478;font-size:0.78rem"> · {sp_icon} {g.get("_sport","")} · {g["Time"]} · {g["Conf%"]:.0f}% conf</span>',
                    unsafe_allow_html=True
                )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: TODAY'S PICKS
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[ti("📊 Today's Picks")]:
    strong = [g for g in games if "STRONG" in g["Rating"]]
    lean   = [g for g in games if "LEAN"   in g["Rating"]]

    if not games:
        st.info(f"No {sl} games with odds found today. Season may be inactive or try refreshing.")
    else:
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Games",       len(games))
        c2.metric("🟢 Strong",   len(strong))
        c3.metric("🟡 Lean",     len(lean))
        c4.metric("Avg Conf",    f"{round(sum(g['Conf%'] for g in games)/len(games),1)}%")
        if sl=="CBB":   c5.metric("⭐ Upsets",   len([g for g in games if "PRIME" in g.get("Upset","")]))
        elif sl=="MLB": c5.metric("✅ Filter",    len([g for g in games if g.get("Filter")=="✅"]))
        elif sl=="CFB": c5.metric("🏠 Home Dogs",len([g for g in games if "Value" in g.get("HomeDog","")]))
        elif sl=="NBA": c5.metric("⚠️ B2B",       len([g for g in games if "B2B" in g.get("B2B","")]))
        else:           c5.metric("Analyzed",    len(games))

        st.divider()

        # Search + filter
        sc1,sc2,sc3 = st.columns([2,1.5,1.5])
        search = sc1.text_input("🔍 Search team", placeholder="e.g. Lakers, LAD, Chiefs", key=f"srch{sl}")
        filt   = sc2.selectbox("Show",["All","Strong only","Strong + Lean"], key=f"filt{sl}")
        srt    = sc3.selectbox("Sort",["Gap (best first)","Game time"],       key=f"srt{sl}")

        filtered = games
        if search:
            sq = search.lower()
            filtered = [g for g in filtered if sq in g["Favorite"].lower() or sq in g["Underdog"].lower()]
        if filt=="Strong only":     filtered=[g for g in filtered if "STRONG" in g["Rating"]]
        elif filt=="Strong + Lean": filtered=[g for g in filtered if "STRONG" in g["Rating"] or "LEAN" in g["Rating"]]
        if srt=="Game time":        filtered=sorted(filtered,key=lambda x:x["Time"])

        if not filtered:
            st.info("No games match your search/filter.")
        else:
            # Display columns for picks table
            disp_cols = ["Time","Favorite","Underdog","Pick","Gap","Conf%","Rating",
                         "Fav ML","Dog ML","Fav Impl%","Value","Spread","Books","Line Move","B2B","Injuries"]
            if sl=="MLB":   disp_cols += ["Win%(F)","Win%(D)","RD/G(F)","BP ERA","OPS(F)","Filter"]
            elif sl=="NBA": disp_cols += ["Net(F)","Net(D)","Off Rtg","Def Rtg"]
            elif sl=="NFL": disp_cols += ["EPA Off","EPA Def","TO Mgn","Win%"]
            elif sl=="CBB": disp_cols += ["Eff Mgn(F)","Seed(F)","Seed(D)","Upset","Hist%"]
            elif sl=="CFB": disp_cols += ["SP+(F)","SP+(D)","Win%","SOS","HomeDog"]

            df = pd.DataFrame(filtered)
            show_cols = [c for c in disp_cols if c in df.columns]
            df_show = df[show_cols].copy()
            styled = df_show.style
            if "Rating"    in df_show.columns: styled=styled.applymap(cr,subset=["Rating"])
            if "Gap"       in df_show.columns: styled=styled.applymap(cg,subset=["Gap"])
            if "Value"     in df_show.columns: styled=styled.applymap(cv,subset=["Value"])
            if "Upset"     in df_show.columns: styled=styled.applymap(cu,subset=["Upset"])
            st.dataframe(styled,use_container_width=True,hide_index=True,height=min(600,50+len(df_show)*38))

            # Fix 20: Quick Add to Parlay checkboxes
            st.markdown("##### ➕ Quick-Add to Parlay")
            st.caption("Check games to pre-select them in the Parlay Builder tab.")
            if "parlay_preselect" not in st.session_state:
                st.session_state["parlay_preselect"] = []
            pcols = st.columns(min(3, len(filtered)))
            for i,g in enumerate(filtered[:9]):
                lbl = f"{g['Favorite']} vs {g['Underdog']}"
                opt_str = f"{g['Favorite']} vs {g['Underdog']} — {g['Pick']} ({g['Time']})"
                checked = opt_str in st.session_state.get("parlay_preselect",[])
                if pcols[i%3].checkbox(f"{lbl} ({g['Rating'].split()[-1]})", value=checked, key=f"padd_{sl}_{i}"):
                    if opt_str not in st.session_state["parlay_preselect"]:
                        st.session_state["parlay_preselect"].append(opt_str)
                else:
                    if opt_str in st.session_state["parlay_preselect"]:
                        st.session_state["parlay_preselect"].remove(opt_str)

        # Top picks cards
        if strong:
            st.divider()
            st.markdown("#### ⭐ Top Picks Today")
            cols = st.columns(min(3,len(strong)))
            for i,g in enumerate(strong[:3]):
                with cols[i]:
                    conf=g['Conf%']; gap=g['Gap']
                    if conf>=72:    cc="#4ade80"
                    elif conf>=60:  cc="#facc15"
                    else:           cc="#f87171"
                    pbar_w=int(conf)
                    st.markdown(f"""<div class="pick-card strong">
                      <div style="font-size:1.05rem;font-weight:700;color:#e8eaf0">{g['Favorite']} vs {g['Underdog']}</div>
                      <div style="font-size:0.78rem;color:#8892a4;font-family:'DM Mono',monospace;margin-top:4px">{g['Time']} · Gap {gap:.2f}</div>
                      <div style="margin:8px 0 4px">
                        <div style="background:#1e2640;border-radius:6px;height:8px;width:100%;max-width:200px;overflow:hidden">
                          <div style="background:{cc};height:8px;width:{pbar_w}%;border-radius:6px"></div></div>
                        <span style="font-size:0.78rem;color:{cc};font-family:'DM Mono',monospace">{conf:.2f}% confidence</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
                        <span class="badge-green">{g['Rating']}</span>
                        <span style="font-family:'DM Mono',monospace;font-size:1rem;color:#7eeaff">{g.get('Fav ML','—')}</span>
                      </div>
                      <div style="font-size:0.82rem;color:#4ade80;margin-top:6px;font-weight:700">{g.get('Pick','')}</div>
                      {'<div style="font-size:0.75rem;color:#7eeaff;margin-top:4px">'+g["Alt Spread"]+'</div>' if g.get("Alt Spread","—")!="—" else ""}
                      {'<div style="font-size:0.72rem;color:#fb923c;margin-top:4px">'+g["Injuries"]+'</div>' if g.get("Injuries","—")!="—" else ""}
                      {'<div style="font-size:0.72rem;color:#f87171;margin-top:2px">'+g["B2B"]+'</div>' if g.get("B2B","—")!="—" else ""}
                    </div>""",unsafe_allow_html=True)

        # Email summary
        if games:
            st.divider()
            st.markdown("#### 📧 Daily Summary")
            top_picks = [g for g in games if "STRONG" in g["Rating"] or "LEAN" in g["Rating"]][:5]
            if top_picks:
                body_lines = [f"=== {sl} PICKS {today_est().strftime('%b %d')} ==="]
                for g in top_picks:
                    body_lines.append(f"{g['Pick']} | {g['Favorite']} vs {g['Underdog']} {g['Time']} | Conf: {g['Conf%']:.2f}% | {g['Rating']}")
                email_body = "%0D%0A".join(body_lines)
                mailto = f"mailto:?subject={sl}%20Picks%20{today_est().strftime('%b%20%d')}&body={email_body}"
                st.markdown(f'<a href="{mailto}" style="background:linear-gradient(135deg,#1a6fff,#0ea5e9);color:white;padding:8px 20px;border-radius:8px;text-decoration:none;font-family:Syne,sans-serif;font-weight:700">📧 Email Today\'s Top 5 Picks</a>',unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: SPORT-SPECIFIC EXTRA
# ═══════════════════════════════════════════════════════════════════════════════
if has_extra and extra_label in tab_names:
    with tabs[ti(extra_label)]:
        if sl=="CBB":
            st.markdown("#### 🎲 Blind Dog Tracker — Every Dog Getting 4+ Points")
            st.caption("Strategy: 2u on every underdog +4 or more regardless of model. Track separately over 50+ games.")
            dogs=[g for g in games if g.get("Upset","—")!="—"]
            if not dogs: st.info("No qualifying underdogs today.")
            else:
                df_d=pd.DataFrame([{"Dog":g["Underdog"],"vs":g["Favorite"],"Spread":g["Spread"],
                                     "Dog ML":g["Dog ML"],"Flag":g.get("Upset","—"),
                                     "Hist%":g.get("Hist%","—"),"Conf%":g["Conf%"],"Units":"2u"} for g in dogs])
                st.dataframe(df_d.style.applymap(cu,subset=["Flag"]),use_container_width=True,hide_index=True)
            st.divider()
            st.markdown("##### NCAA Tournament Seed History")
            st.caption("⚠️ These are historical upset rates from past tournaments — not current seeds for this season.")
            st.dataframe(pd.DataFrame({
                "Matchup":["1v16","2v15","3v14","4v13","5v12","6v11","7v10","8v9"],
                "Upset Rate":["3%","6%","15%","21%","35%","37%","40%","49%"],
                "Note":["Lock fav","Fav lean","Check gap","Check gap","⭐ Bet dog","⭐ Best spot","⭐ Coin flip","Model only"]
            }),use_container_width=True,hide_index=True)

        elif sl=="NFL":
            st.markdown("#### 🏈 NFL Situational Angles")
            st.info("**Best edges:** Home dog ≤3pts · Big EPA gap with spread <7 · Large TO margin · Short week fades")
            sits=[]
            for g in games:
                notes=[]
                try:
                    sp_val=float(str(g.get("Spread","0 ")).split(" ")[-1].replace("-","") or 0)
                    if 0<sp_val<=3: notes.append("🏠 Tight line — dog value")
                except: pass
                try:
                    if abs(float(str(g.get("EPA Off","0")).replace("+","") or 0))>0.10: notes.append("📊 Big EPA edge")
                except: pass
                try:
                    if abs(int(str(g.get("TO Mgn","0")).replace("+","") or 0))>=5: notes.append("🎲 TO margin edge")
                except: pass
                if notes: sits.append({"Game":f"{g['Favorite']} vs {g['Underdog']}","Time":g["Time"],"Rating":g["Rating"],"Pick":g["Pick"],"Angles":" · ".join(notes)})
            if sits:
                st.dataframe(pd.DataFrame(sits).style.applymap(cr,subset=["Rating"]),use_container_width=True,hide_index=True)
            else:
                st.info("No standout situational spots today.")

        elif sl=="NBA":
            st.markdown("#### ⚠️ Back-to-Back Watch")
            st.warning("**B2B teams cover at ~44% ATS** — auto 8pt penalty applied. Teams confirmed from yesterday's schedule.")
            if b2b_teams:
                st.success(f"**B2B Teams Today:** {', '.join(sorted(b2b_teams))}")
            else:
                st.info("No confirmed B2B teams detected today.")
            st.markdown("""
            **B2B Betting Rules:**
            - Road B2B favorite → **Fade hard**
            - Home B2B underdog → **Value on dog**
            - B2B team as big chalk → **Avoid**
            """)
            if games:
                st.dataframe(pd.DataFrame([{
                    "Game":f"{g['Favorite']} vs {g['Underdog']}","Time":g["Time"],
                    "Rating":g["Rating"],"Conf%":g["Conf%"],
                    "Net(F)":g.get("Net(F)"),"Net(D)":g.get("Net(D)"),
                    "B2B":g.get("B2B","—")
                } for g in games]).style.applymap(cr,subset=["Rating"]),use_container_width=True,hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: WEATHER
# ═══════════════════════════════════════════════════════════════════════════════
if has_weather and "🌤️ Weather" in tab_names:
    with tabs[ti("🌤️ Weather")]:
        st.markdown(f"#### 🌤️ Game Day Weather — {sl}")
        if not WEATHER_KEY:
            st.warning("Add WEATHER_API_KEY in Streamlit secrets to enable weather. Get free key at openweathermap.org")
        else:
            venue_map = MLB_STADIUMS if sl=="MLB" else NFL_STADIUMS
            shown=set()
            for g in games[:12]:
                teams=[g["Favorite"],g["Underdog"]]
                for t in teams:
                    v=venue_map.get(t)
                    if not v or v["city"] in shown: continue
                    shown.add(v["city"])
                    w=fetch_weather(v["lat"],v["lon"],v["city"],v["roof"])
                    if not w: continue
                    if w.get("roof"):
                        st.markdown(f'<div class="weather-card"><b>{t}</b> · {v["city"]} · <span style="color:#7eeaff">🏟️ Retractable Roof — weather irrelevant</span></div>',unsafe_allow_html=True)
                    else:
                        imp=" · ".join(w.get("impact",[])) or "✅ No significant weather impact"
                        col="#4ade80" if not w.get("impact") else "#facc15"
                        temp_disp = f"{w.get('temp','?')}°F" if w.get('temp') is not None else "N/A"
                        wind_disp = f"{w.get('wind','?')} mph" if w.get('wind') is not None else "N/A"
                        st.markdown(f"""<div class="weather-card">
                          <div style="display:flex;justify-content:space-between">
                            <b style="color:#e8eaf0">{t} · {v['city']}</b>
                            <span style="font-family:'DM Mono',monospace;color:#7eeaff">{temp_disp} · 💨{wind_disp} · {w.get('desc','')}</span>
                          </div>
                          <div style="font-size:0.82rem;color:{col};margin-top:6px">{imp}</div>
                        </div>""",unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: SCOREBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[ti("📺 Scoreboard")]:
    live_g  = [g for g in espn_today if g["state"]=="in"]
    final_g = [g for g in espn_today if g["state"]=="post"]
    pre_g   = [g for g in espn_today if g["state"]=="pre"]
    c1,c2,c3=st.columns(3)
    c1.metric("🔴 Live",len(live_g))
    c2.metric("✅ Final",len(final_g))
    c3.metric("🕐 Upcoming",len(pre_g))
    if not espn_today:
        st.info("No games today or scoreboard unavailable.")
    else:
        if live_g:
            st.markdown("#### 🔴 Live Now")
            for g in live_g: st.markdown(score_card_html(g),unsafe_allow_html=True)
        if final_g:
            st.markdown("#### ✅ Final")
            for g in final_g: st.markdown(score_card_html(g),unsafe_allow_html=True)
        if pre_g:
            st.markdown("#### 🕐 Upcoming")
            for g in pre_g: st.markdown(score_card_html(g),unsafe_allow_html=True)
    st.caption(f"ESPN · All times {now_est().split()[-1]} · Auto-refresh: {'ON ✅' if auto_ref else 'OFF'}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: CHEAT SHEET
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[ti("📋 Cheat Sheet")]:
    st.markdown(f"#### {em} {sl} Team Ratings — All Teams")
    st.markdown(source_badge(src_label),unsafe_allow_html=True)
    st.markdown("")

    # Fix 21: column toggle
    col_mode = st.radio("Columns", ["Key Stats", "Full Stats"], horizontal=True, key="cheat_col_mode")

    if sl=="MLB":
        rows=[{"Team":k,"Score":score_mlb(v),"Win%":f"{v.get('win_pct',0.5):.2f}",
               "RD/G":f"{v.get('run_diff_pg',0):+.2f}","BP ERA":f"{v.get('bullpen_era',4.5):.2f}",
               "OPS":f"{v.get('ops',0.720):.3f}","Tier":tier(score_mlb(v))} for k,v in team_stats.items()]
    elif sl=="NBA":
        rows=[{"Team":k,"Score":score_nba(v),"Net Rtg":f"{v.get('net_rtg',0):+.2f}",
               "Off Rtg":f"{v.get('off_rtg',110):.2f}","Def Rtg":f"{v.get('def_rtg',112):.2f}",
               "Pace":f"{v.get('pace',99):.2f}","W-L":f"{v.get('wins',0)}-{v.get('losses',0)}",
               "Tier":tier(score_nba(v))} for k,v in team_stats.items()]
    elif sl=="NFL":
        rows=[{"Team":k,"Score":score_nfl(v),"EPA Off":f"{v.get('epa_off',0):+.3f}",
               "EPA Def":f"{v.get('epa_def',0):+.3f}","TO Mgn":f"{v.get('to_margin',0):+d}",
               "Win%":f"{v.get('win_pct',0.5):.2f}","Pts Diff":f"{v.get('pts_diff',0):+.2f}",
               "Tier":tier(score_nfl(v))} for k,v in team_stats.items()]
    elif sl=="CBB":
        rows=[{"Team":k,"Seed":v.get("seed","—"),"Score":score_cbb(v),
               "Eff Margin":f"{v.get('eff_margin',0):+.2f}","Adj O":f"{v.get('adj_o',110):.2f}",
               "Adj D":f"{v.get('adj_d',102):.2f}","Tempo":f"{v.get('tempo',70):.2f}",
               "EFG%":f"{v.get('efg',0.5):.3f}","Win%":f"{v.get('win_pct',0.5):.2f}",
               "Tier":tier(score_cbb(v),75,60,45)} for k,v in team_stats.items()]
    else:
        rows=[{"Team":k,"Score":score_cfb(v),"SP+":f"{v.get('sp_plus',0):+.2f}",
               "Off SP+":f"{v.get('off_sp',0):.2f}","Def SP+":f"{v.get('def_sp',0):.2f}",
               "Win%":f"{v.get('win_pct',0.5):.2f}","SOS Rank":v.get("sos_rank",60),
               "Tier":tier(score_cfb(v))} for k,v in team_stats.items()]

    df_c=pd.DataFrame(rows).sort_values("Score",ascending=False)

    # Fix 21: Key Stats mode shows only the most important columns
    if col_mode == "Key Stats":
        key_cols = {"MLB": ["Team","Score","Tier","Win%","RD/G","BP ERA"],
                    "NBA": ["Team","Score","Tier","Net Rtg","W-L"],
                    "NFL": ["Team","Score","Tier","EPA Off","EPA Def"],
                    "CBB": ["Team","Score","Tier","Eff Margin","Seed"],
                    "CFB": ["Team","Score","Tier","SP+","Win%"]}
        keep = [c for c in key_cols.get(sl, df_c.columns.tolist()) if c in df_c.columns]
        df_c = df_c[keep]

    st.dataframe(df_c.style.applymap(ct,subset=["Tier"]),use_container_width=True,hide_index=True)
    st.divider()
    st.caption(model_info.get(sl,""))

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: PARLAY BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[ti("🎯 Parlay Builder")]:
    st.markdown("#### 🎯 Parlay Builder")
    st.caption("Select 2–5 games to build a parlay. Model uses best available ML from DraftKings/FanDuel/BetMGM.")

    if not games:
        st.info("No games available for parlay building today.")
    else:
        eligible=[g for g in games if "STRONG" in g["Rating"] or "LEAN" in g["Rating"]]
        if not eligible: eligible=games[:10]

        options=[f"{g['Favorite']} vs {g['Underdog']} — {g['Pick']} ({g['Time']})" for g in eligible]
        # Fix 20: use any pre-selected games from Today's Picks checkboxes
        preselect = [s for s in st.session_state.get("parlay_preselect",[]) if s in options]
        selected=st.multiselect("Select games for parlay",options,default=preselect,max_selections=5,key=f"par{sl}")

        if selected:
            sel_games=[eligible[options.index(s)] for s in selected]
            parlay_dec=1.0
            legs=[]
            for g in sel_games:
                ml_str=g.get("Fav ML","—")
                try:
                    ml=float(ml_str.split(" ")[0].replace("+",""))
                    dec=ml/100+1 if ml>0 else 100/abs(ml)+1
                except:
                    dec=1.91
                parlay_dec*=dec
                legs.append({"Leg":g["Pick"],"ML":ml_str,"Conf%":g["Conf%"],"Rating":g["Rating"]})

            parlay_ml=round((parlay_dec-1)*100) if parlay_dec>=2 else round(-(100/(parlay_dec-1)))
            imp_prob=round(1/parlay_dec*100,2)
            model_prob=round(math.prod([g["Conf%"]/100 for g in sel_games])*100,2)

            st.divider()
            pc1,pc2,pc3,pc4=st.columns(4)
            pc1.metric("Parlay Odds",   f"+{parlay_ml}" if parlay_ml>0 else str(parlay_ml))
            pc2.metric("Book Impl%",    f"{imp_prob:.2f}%")
            pc3.metric("Model Hit%",    f"{model_prob:.2f}%")
            pc4.metric("Edge",          f"{'+' if model_prob>imp_prob else ''}{round(model_prob-imp_prob,2)}%")
            st.caption(f"⚠️ Book implied probability ({imp_prob:.1f}%) already includes the vig — true fair probability is slightly higher. "
                       f"Model edge is real only when model probability meaningfully exceeds the book implied.")

            st.markdown("##### Legs")
            df_legs=pd.DataFrame(legs)
            st.dataframe(df_legs.style.applymap(cr,subset=["Rating"]),use_container_width=True,hide_index=True)

            if model_prob > imp_prob:
                st.success(f"✅ Model shows positive edge: model {model_prob:.2f}% vs implied {imp_prob:.2f}%")
                units=round(min(3.0,(model_prob-imp_prob)/5),1)
                st.info(f"Suggested stake: **{units}u** (scale with edge size)")
            else:
                st.warning("⚠️ No model edge on this parlay. Consider individual bets instead.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: MODEL SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[ti("⚙️ Model Settings")]:
    st.markdown("#### ⚙️ Model Settings — Customize Weights & Stats")
    st.caption("Drag sliders to adjust how much each stat contributes to the score. "
               "Weights auto-normalize to 100% so the total always balances. "
               "Changes apply instantly to all picks — no reload needed.")

    # Reset button
    rc1, rc2 = st.columns([1,4])
    if rc1.button("🔄 Reset All to Defaults", key="reset_weights"):
        for sport_key, stats in DEFAULT_WEIGHTS.items():
            for stat_name, default_val in stats.items():
                st.session_state[f"w_{sport_key}_{stat_name}"] = default_val
        st.success("✅ All weights reset to defaults.")
        st.rerun()

    st.divider()

    # Show settings for current sport only (cleaner UX)
    # But let user switch between sports via selectbox
    settings_sport = st.selectbox(
        "Configure weights for sport:",
        ["MLB","NBA","NFL","CBB","CFB"],
        index=["MLB","NBA","NFL","CBB","CFB"].index(sl),
        key="settings_sport_sel"
    )

    defaults = DEFAULT_WEIGHTS[settings_sport]
    sport_labels = {
        "MLB": {
            "Win%":        ("Win %",        "Season win percentage — overall team quality"),
            "Run Diff/G":  ("Run Diff/G",   "Runs scored minus allowed per game — best overall proxy"),
            "Bullpen ERA": ("Bullpen ERA",   "Relief ERA — critical in close late-game situations"),
            "OPS":         ("OPS",           "On-base + slugging — offensive firepower"),
            "Last 10":     ("Last 10 Form",  "Win rate over last 10 games — recent momentum"),
        },
        "NBA": {
            "Net Rating":  ("Net Rating",   "Points per 100 possessions diff — single best NBA predictor"),
            "Off Rating":  ("Off Rating",   "Points scored per 100 possessions"),
            "Def Rating":  ("Def Rating",   "Points allowed per 100 possessions"),
            "Pace":        ("Pace",          "Possessions per 48 min — affects variance and total"),
            "Last 10":     ("Last 10 Form",  "Win rate over last 10 games — momentum"),
        },
        "NFL": {
            "EPA Off":     ("EPA Offense",  "Expected points added per offensive play — best NFL predictor"),
            "EPA Def":     ("EPA Defense",  "EPA allowed per defensive play — lower is better"),
            "TO Margin":   ("TO Margin",    "Turnover differential — biggest swing stat in NFL"),
            "Win%":        ("Win %",        "Season win percentage"),
            "Pts Diff":    ("Pts Diff/G",   "Average point differential per game"),
        },
        "CBB": {
            "Eff Margin":  ("Eff Margin",   "Adj O minus Adj D — T-Rank's single best predictor"),
            "Adj O":       ("Adj Offense",  "Adjusted offensive efficiency per 100 possessions"),
            "Adj D":       ("Adj Defense",  "Adjusted defensive efficiency per 100 possessions"),
            "EFG%":        ("Eff FG%",      "Effective field goal % — accounts for 3-pointers"),
            "TO Rate":     ("TO Rate",      "Turnover rate — teams that protect ball win more"),
            "Experience":  ("Experience",   "Roster experience rating — matters heavily in March"),
            "Tempo":       ("Tempo",        "Possessions per 40 min — affects scoring variance"),
        },
        "CFB": {
            "SP+":         ("SP+",          "Bill Connelly's overall efficiency — best CFB predictor"),
            "Off SP+":     ("Off SP+",      "Offensive SP+ rating"),
            "Def SP+":     ("Def SP+",      "Defensive SP+ rating"),
            "Home Edge":   ("Home Edge",    "Home field advantage value in points"),
            "Win%":        ("Win %",        "Season win percentage"),
            "SOS":         ("SOS Rank",     "Strength of schedule rank — 1=hardest"),
        },
    }

    labels = sport_labels[settings_sport]

    # Current effective weights (normalized)
    raw_vals = {k: st.session_state.get(f"w_{settings_sport}_{k}", defaults[k]) for k in defaults}
    total_raw = max(sum(raw_vals.values()), 1)
    eff_weights = {k: round(v/total_raw*100, 1) for k,v in raw_vals.items()}

    st.markdown(f"##### {settings_sport} Weight Sliders")
    st.caption("Raw values are relative — the app normalizes them automatically. "
               "Set a stat to 0 to remove it entirely from the model.")

    # Two-column layout for sliders
    stat_list = list(defaults.keys())
    col_a, col_b = st.columns(2)

    for i, stat_key in enumerate(stat_list):
        col = col_a if i % 2 == 0 else col_b
        label, desc = labels.get(stat_key, (stat_key, ""))
        default_val = defaults[stat_key]
        ss_key = f"w_{settings_sport}_{stat_key}"
        current = st.session_state.get(ss_key, default_val)
        eff = eff_weights.get(stat_key, 0)

        with col:
            new_val = st.slider(
                f"**{label}** — effective {eff:.1f}%",
                min_value=0, max_value=100,
                value=int(current),
                step=1,
                help=desc,
                key=f"slider_{settings_sport}_{stat_key}"
            )
            st.session_state[ss_key] = new_val

    # Live weight summary bar chart
    st.divider()
    st.markdown("##### Current Effective Weights (auto-normalized to 100%)")

    # Recompute after slider interaction
    raw_vals2 = {k: st.session_state.get(f"w_{settings_sport}_{k}", defaults[k]) for k in defaults}
    total2 = max(sum(raw_vals2.values()), 1)
    eff2 = {k: round(v/total2*100, 1) for k,v in raw_vals2.items()}

    bar_cols = st.columns(len(eff2))
    colors = ["#7eeaff","#4ade80","#facc15","#fb923c","#a78bfa","#f87171","#60a5fa"]
    for i, (k,v) in enumerate(eff2.items()):
        lbl, _ = labels.get(k,(k,""))
        bar_cols[i].markdown(
            f'<div style="text-align:center">'
            f'<div style="background:#1e2640;border-radius:6px;height:80px;width:100%;'
            f'display:flex;align-items:flex-end;justify-content:center;overflow:hidden">'
            f'<div style="background:{colors[i%len(colors)]};width:100%;'
            f'height:{int(v/max(eff2.values(),default=1)*80)}px;border-radius:4px 4px 0 0"></div></div>'
            f'<div style="font-size:0.72rem;color:#8892a4;margin-top:4px">{lbl}</div>'
            f'<div style="font-family:DM Mono,monospace;font-size:0.85rem;color:{colors[i%len(colors)]}">{v:.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.divider()

    # Team stat override section
    st.markdown("##### Manual Stat Overrides — Adjust Individual Team Stats")
    st.caption("Use this to manually correct a stat you know is wrong — e.g. a team's ace just got injured "
               "and their ERA should be higher, or a team is on a hot streak not reflected yet.")

    override_sport = settings_sport
    if override_sport == "MLB":
        override_teams = sorted(MLB_FB.keys())
        override_stats = ["win_pct","run_diff_pg","bullpen_era","ops","last10"]
    elif override_sport == "NBA":
        override_teams = sorted(NBA_FB.keys())
        override_stats = ["net_rtg","off_rtg","def_rtg","pace","last10"]
    elif override_sport == "NFL":
        override_teams = sorted(NFL_FB.keys())
        override_stats = ["epa_off","epa_def","to_margin","win_pct","pts_diff"]
    elif override_sport == "CBB":
        override_teams = sorted(CBB_FB.keys())
        override_stats = ["eff_margin","adj_o","adj_d","efg","tempo"]
    else:
        override_teams = sorted(CFB_FB.keys())
        override_stats = ["sp_plus","off_sp","def_sp","win_pct"]

    ov1, ov2, ov3, ov4 = st.columns(4)
    sel_team = ov1.selectbox("Team", override_teams, key="ov_team")
    sel_stat = ov2.selectbox("Stat", override_stats, key="ov_stat")

    # Get current value (from override or fallback)
    fb_map = {"MLB":MLB_FB,"NBA":NBA_FB,"NFL":NFL_FB,"CBB":CBB_FB,"CFB":CFB_FB}[override_sport]
    current_base = fb_map.get(sel_team,{}).get(sel_stat,0.0)
    override_key  = f"override_{override_sport}_{sel_team}_{sel_stat}"
    current_ov    = st.session_state.get(override_key, current_base)

    new_ov = ov3.number_input(
        f"Value (base: {current_base:.3f})",
        value=float(current_ov),
        step=0.001, format="%.3f",
        key=f"ovinput_{override_sport}_{sel_team}_{sel_stat}"
    )
    if ov4.button("✅ Apply Override", key="apply_ov"):
        st.session_state[override_key] = new_ov
        st.success(f"✅ {sel_team} {sel_stat} → {new_ov:.3f} (was {current_base:.3f})")

    # Show active overrides
    active_ovs = {k:v for k,v in st.session_state.items()
                  if k.startswith(f"override_{override_sport}_")
                  and v != fb_map.get(k.split("_")[3],{}).get("_".join(k.split("_")[4:]),None)}
    if active_ovs:
        st.markdown("**Active overrides:**")
        ov_rows = []
        for k,v in active_ovs.items():
            parts = k.split("_")
            team = parts[3]; stat = "_".join(parts[4:])
            base = fb_map.get(team,{}).get(stat,0)
            ov_rows.append({"Team":team,"Stat":stat,"Original":round(base,3),"Override":round(v,3)})
        st.dataframe(pd.DataFrame(ov_rows), use_container_width=True, hide_index=True)
        if st.button("🗑️ Clear All Overrides", key="clear_ovs"):
            for k in list(active_ovs.keys()):
                del st.session_state[k]
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: TRACKER
# ═══════════════════════════════════════════════════════════════════════════════
with tabs[ti("📈 Tracker")]:
    picks_all = load_picks()
    ov = calc_summary(picks_all)

    # Fix 14: Storage warning
    st.warning("⚠️ **Picks are stored locally** in `picks_log.json`. If running on Streamlit Cloud, picks may be lost on restart. Use the CSV export below to back up your data.", icon="💾")

    st.markdown("#### 📈 Season Record — All Sports")
    tc1,tc2,tc3,tc4,tc5=st.columns(5)
    tc1.metric("Overall",  f"{ov['wins']}-{ov['losses']}")
    tc2.metric("Hit Rate", f"{ov['hit_rate']:.2f}%")
    tc3.metric("P&L",      f"{'+' if ov['pl']>=0 else ''}{ov['pl']}u")
    tc4.metric("ROI",      f"{'+' if ov['roi']>=0 else ''}{ov['roi']:.2f}%")
    tc5.metric("Pending",  ov["pending"])

    st.divider()
    sport_cols=st.columns(5)
    for i,sk in enumerate(["MLB","NBA","NFL","CBB","CFB"]):
        s=calc_summary(picks_all,sk); streak=calc_streak(picks_all,sk)
        pc="color:#4ade80" if s["pl"]>=0 else "color:#f87171"
        with sport_cols[i]:
            st.markdown(f"""<div style="background:#131929;border:1px solid #1e2a45;border-radius:10px;padding:12px;text-align:center">
              <div style="font-size:0.75rem;color:#8892a4">{sk}</div>
              <div style="font-size:1rem;font-weight:700;color:#e8eaf0;margin:4px 0">{s['wins']}-{s['losses']}</div>
              <div style="font-size:0.85rem;font-family:'DM Mono',monospace;{pc}">{'+' if s['pl']>=0 else ''}{s['pl']}u</div>
              <div style="font-size:0.72rem;color:#5a6478">{s['hit_rate']:.2f}% · {s['pending']} pending</div>
              <div style="font-size:0.72rem;color:#facc15;margin-top:2px">{streak}</div>
            </div>""",unsafe_allow_html=True)

    # ── FIX 2: Model Accuracy — Right vs Wrong by tier ──────────────────────────
    st.divider()
    st.markdown("#### 🎯 Model Accuracy — Right vs Wrong")
    st.caption("How often is the model's pick correct? Broken down by confidence tier and sport.")

    settled = [p for p in picks_all if p.get("result") in ("W","L")]
    if not settled:
        st.info("No settled picks yet. Log some picks and mark results to see model accuracy here.")
    else:
        # Overall accuracy
        acc_total = len([p for p in settled if p["result"]=="W"])
        acc_pct   = round(acc_total/len(settled)*100,1) if settled else 0

        # By confidence tier (uses Rating field if present, else bet_type as proxy)
        def tier_from_pick(p):
            r = p.get("bet_type","").upper()
            if "ALT SPREAD" in r or r=="SPREAD": return "Strong (Spread)"
            if r=="ML": return "ML"
            if r=="PARLAY": return "Parlay"
            if "DOG" in r or "UPSET" in r: return "Dog/Upset"
            return "Other"

        tier_data = {}
        for p in settled:
            t = tier_from_pick(p)
            if t not in tier_data: tier_data[t] = {"W":0,"L":0}
            tier_data[t][p["result"]] += 1

        # By sport
        sport_acc = {}
        for sp_ in ["MLB","NBA","NFL","CBB","CFB"]:
            sp_picks = [p for p in settled if p.get("sport","").upper()==sp_]
            if sp_picks:
                w_ = len([p for p in sp_picks if p["result"]=="W"])
                sport_acc[sp_] = {"W":w_,"L":len(sp_picks)-w_,"pct":round(w_/len(sp_picks)*100,1)}

        # Display overall accuracy prominently
        acc_col = "#4ade80" if acc_pct >= 55 else ("#facc15" if acc_pct >= 50 else "#f87171")
        st.markdown(f"""
        <div style="background:#131929;border:1px solid #1e2a45;border-radius:16px;padding:20px 28px;margin-bottom:16px;
                    display:flex;align-items:center;gap:24px;">
          <div style="text-align:center">
            <div style="font-size:2.8rem;font-weight:800;color:{acc_col};font-family:'DM Mono',monospace">{acc_pct}%</div>
            <div style="font-size:0.78rem;color:#8892a4">Overall Model Hit Rate</div>
            <div style="font-size:0.72rem;color:#5a6478">{acc_total}W – {len(settled)-acc_total}L of {len(settled)} settled picks</div>
          </div>
          <div style="flex:1">
            <div style="background:#1e2640;border-radius:8px;height:14px;overflow:hidden;margin-bottom:6px">
              <div style="background:{acc_col};height:14px;width:{acc_pct:.0f}%;border-radius:8px;transition:width 0.3s"></div>
            </div>
            <div style="font-size:0.72rem;color:#5a6478">
              {'🟢 Above breakeven (55%+)' if acc_pct>=55 else ('🟡 Near breakeven (50–54%)' if acc_pct>=50 else '🔴 Below breakeven (<50%)')}
              · Need ~52.4% to break even at -110
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # By sport
        if sport_acc:
            st.markdown("##### Hit Rate by Sport")
            sa_cols = st.columns(len(sport_acc))
            for i,(sp_,sd) in enumerate(sport_acc.items()):
                c_ = "#4ade80" if sd["pct"]>=55 else ("#facc15" if sd["pct"]>=50 else "#f87171")
                sa_cols[i].markdown(f"""
                <div style="background:#131929;border:1px solid #1e2a45;border-radius:10px;padding:12px;text-align:center">
                  <div style="font-size:0.75rem;color:#8892a4">{sp_}</div>
                  <div style="font-size:1.4rem;font-weight:700;color:{c_};font-family:'DM Mono',monospace">{sd['pct']}%</div>
                  <div style="font-size:0.70rem;color:#5a6478">{sd['W']}W–{sd['L']}L</div>
                </div>""", unsafe_allow_html=True)

        # By bet type / tier
        if tier_data:
            st.markdown("##### Hit Rate by Bet Type")
            tier_rows = []
            for t,td in tier_data.items():
                total_t = td["W"]+td["L"]
                pct_t   = round(td["W"]/total_t*100,1) if total_t else 0
                tier_rows.append({"Type":t,"W":td["W"],"L":td["L"],
                                  "Hit Rate":f"{pct_t}%","Picks":total_t})
            df_tier = pd.DataFrame(tier_rows).sort_values("Picks",ascending=False)
            st.dataframe(df_tier, use_container_width=True, hide_index=True)

        # Recent form: last 10 settled picks
        last10_s = sorted(settled, key=lambda x:x.get("date",""), reverse=True)[:10]
        if last10_s:
            st.markdown("##### Last 10 Settled Picks")
            form_html = '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">'
            for p in reversed(last10_s):
                col_ = "#4ade80" if p["result"]=="W" else "#f87171"
                form_html += f'<div style="background:{col_}22;border:1px solid {col_}55;border-radius:6px;padding:4px 10px;font-family:DM Mono,monospace;font-size:0.78rem;color:{col_}">{p["result"]} {p.get("sport","")}</div>'
            form_html += "</div>"
            st.markdown(form_html, unsafe_allow_html=True)

    st.divider()
    with st.expander("➕ Log a New Pick",expanded=False):
        lc1,lc2,lc3=st.columns(3)
        ps=lc1.selectbox("Sport",["MLB","NBA","NFL","CBB","CFB"],key="ps",
                         index=["MLB","NBA","NFL","CBB","CFB"].index(sl))
        pb=lc2.selectbox("Bet Type",["Alt Spread","Spread","ML","Parlay","Blind Dog","Upset","Other"],key="pb")
        pf=lc3.text_input("Favorite",key="pf")
        lc4,lc5,lc6=st.columns(3)
        und_=lc4.text_input("Underdog",key="und")   # Fix 9: renamed from pd_ to avoid shadowing pandas
        po=lc5.text_input("Odds (e.g. -150 or +220)",key="po")
        pu=lc6.number_input("Units",0.1,10.0,0.5,0.25,key="pu")
        pn=st.text_input("Notes (optional)",key="pn")
        if st.button("💾 Save Pick"):
            if pf and und_:
                picks_all.append({"date":today_est().isoformat(),"sport":ps,"bet_type":pb,
                                   "favorite":pf,"underdog":und_,"odds":po,"units":pu,
                                   "notes":pn,"result":"Pending"})
                save_picks(picks_all); st.success("✅ Saved!"); st.rerun()
            else:
                st.error("Enter at least a favorite and underdog.")

    if picks_all:
        st.markdown("#### 📋 All Picks — Mark Results")
        st.caption("Set Result to W / L / P (push) then Save Results.")
        try:
            df_p=pd.DataFrame(picks_all)[["date","sport","bet_type","favorite","underdog","odds","units","result","notes"]]
        except:
            df_p=pd.DataFrame(picks_all)
        ed=st.data_editor(df_p,column_config={
            "result":st.column_config.SelectboxColumn("Result",options=["Pending","W","L","P"],required=True)},
            use_container_width=True,num_rows="dynamic",key="ped")
        cc1,cc2=st.columns(2)
        if cc1.button("💾 Save Results"):
            save_picks(ed.to_dict("records"))
            st.success("✅ Saved!"); st.rerun()
        # CSV Export
        csv_data=ed.to_csv(index=False).encode("utf-8")
        cc2.download_button("📥 Download CSV",data=csv_data,
                            file_name=f"picks_{today_est().isoformat()}.csv",
                            mime="text/csv")
    else:
        st.info("No picks logged yet. Use the form above to add your first pick.")
