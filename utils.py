"""
utils.py — Shared helpers, static data, constants.
No Streamlit imports. No API calls. Pure data and logic.
"""
import re
import math
import unicodedata
from datetime import datetime, timedelta, timezone

# ── Kalshi API base ───────────────────────────────────────────────────────────
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# ── Edge thresholds (%) by pick type ─────────────────────────────────────────
EDGE_THRESHOLDS = {
    "game":     5.0,
    "pra":      6.0,
    "points":   6.0,
    "rebounds": 6.0,
    "assists":  6.0,
    "3pm":      8.0,
    "blocks":   10.0,
    "steals":   10.0,
}

# Minimum Pick Quality Score to display a pick
MIN_PQS_DEFAULT  = 55   # default mode — only show high-confidence picks
MIN_PQS_ADVANCED = 30   # advanced mode — show more, user decides

# ── ESPN abbreviation → full team name ───────────────────────────────────────
ESPN_MAP = {
    "ATL": "Atlanta Hawks",          "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",          "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",          "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",       "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",        "GS":  "Golden State Warriors",
    "HOU": "Houston Rockets",        "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",   "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",      "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",        "MIN": "Minnesota Timberwolves",
    "NO":  "New Orleans Pelicans",   "NY":  "New York Knicks",
    "OKC": "Oklahoma City Thunder",  "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",     "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings",
    "SA":  "San Antonio Spurs",      "TOR": "Toronto Raptors",
    "UTAH":"Utah Jazz",              "WSH": "Washington Wizards",
}

# ── NBA team aliases for fuzzy text matching ──────────────────────────────────
NBA_ALIASES = {
    "thunder":       "Oklahoma City Thunder",  "cavaliers":     "Cleveland Cavaliers",
    "celtics":       "Boston Celtics",         "rockets":       "Houston Rockets",
    "warriors":      "Golden State Warriors",  "pacers":        "Indiana Pacers",
    "grizzlies":     "Memphis Grizzlies",      "nuggets":       "Denver Nuggets",
    "lakers":        "Los Angeles Lakers",     "knicks":        "New York Knicks",
    "bucks":         "Milwaukee Bucks",        "76ers":         "Philadelphia 76ers",
    "sixers":        "Philadelphia 76ers",     "timberwolves":  "Minnesota Timberwolves",
    "heat":          "Miami Heat",             "kings":         "Sacramento Kings",
    "clippers":      "Los Angeles Clippers",   "mavericks":     "Dallas Mavericks",
    "hawks":         "Atlanta Hawks",          "suns":          "Phoenix Suns",
    "bulls":         "Chicago Bulls",          "nets":          "Brooklyn Nets",
    "magic":         "Orlando Magic",          "hornets":       "Charlotte Hornets",
    "raptors":       "Toronto Raptors",        "jazz":          "Utah Jazz",
    "spurs":         "San Antonio Spurs",      "trail blazers": "Portland Trail Blazers",
    "blazers":       "Portland Trail Blazers", "pistons":       "Detroit Pistons",
    "pelicans":      "New Orleans Pelicans",   "wizards":       "Washington Wizards",
    "oklahoma city": "Oklahoma City Thunder",  "cleveland":     "Cleveland Cavaliers",
    "boston":        "Boston Celtics",         "houston":       "Houston Rockets",
    "golden state":  "Golden State Warriors",  "indiana":       "Indiana Pacers",
    "memphis":       "Memphis Grizzlies",      "denver":        "Denver Nuggets",
    "new york":      "New York Knicks",        "milwaukee":     "Milwaukee Bucks",
    "philadelphia":  "Philadelphia 76ers",     "minnesota":     "Minnesota Timberwolves",
    "miami":         "Miami Heat",             "sacramento":    "Sacramento Kings",
    "dallas":        "Dallas Mavericks",       "atlanta":       "Atlanta Hawks",
    "phoenix":       "Phoenix Suns",           "chicago":       "Chicago Bulls",
    "brooklyn":      "Brooklyn Nets",          "orlando":       "Orlando Magic",
    "charlotte":     "Charlotte Hornets",      "toronto":       "Toronto Raptors",
    "utah":          "Utah Jazz",              "san antonio":   "San Antonio Spurs",
    "portland":      "Portland Trail Blazers", "detroit":       "Detroit Pistons",
    "new orleans":   "New Orleans Pelicans",   "washington":    "Washington Wizards",
    "los angeles l": "Los Angeles Lakers",     "la lakers":     "Los Angeles Lakers",
    "los angeles c": "Los Angeles Clippers",   "la clippers":   "Los Angeles Clippers",
}

# ── NBA Net Ratings (2025-26 season) ─────────────────────────────────────────
# Update periodically from NBA.com/stats — used in game model
NBA_NET_RATINGS = {
    "Oklahoma City Thunder": 12.1,  "Cleveland Cavaliers":    11.8,
    "Boston Celtics":        10.2,  "Detroit Pistons":         9.2,
    "Houston Rockets":        7.9,  "Golden State Warriors":   7.1,
    "Indiana Pacers":         6.8,  "Memphis Grizzlies":       5.9,
    "Denver Nuggets":         5.4,  "Los Angeles Lakers":      4.8,
    "New York Knicks":        4.5,  "Milwaukee Bucks":         3.9,
    "Philadelphia 76ers":     3.4,  "Minnesota Timberwolves":  3.0,
    "Miami Heat":             2.6,  "Sacramento Kings":        1.9,
    "Los Angeles Clippers":   1.2,  "Dallas Mavericks":        0.7,
    "Atlanta Hawks":         -0.6,  "Phoenix Suns":           -1.4,
    "Chicago Bulls":         -2.1,  "Brooklyn Nets":          -2.7,
    "Orlando Magic":         -3.3,  "Charlotte Hornets":      -4.0,
    "Toronto Raptors":       -4.5,  "Utah Jazz":              -5.3,
    "San Antonio Spurs":     -6.0,  "Portland Trail Blazers": -6.8,
    "New Orleans Pelicans":  -8.1,  "Washington Wizards":     -9.5,
}

# ── CBB Team Stats (KenPom-style, 2025-26 season) ────────────────────────────
# Sourced from cbb_betting_model.py in this project — update weekly from kenpom.com
CBB_TEAM_STATS = {
    "Auburn":          {"eff_margin":28.5,"adj_o":122.1,"adj_d":93.6, "efg":0.558,"to_rate":0.158,"exp":0.85,"seed":1},
    "Duke":            {"eff_margin":27.2,"adj_o":121.8,"adj_d":94.6, "efg":0.551,"to_rate":0.162,"exp":0.60,"seed":1},
    "Houston":         {"eff_margin":26.8,"adj_o":118.4,"adj_d":91.6, "efg":0.532,"to_rate":0.170,"exp":0.90,"seed":1},
    "Florida":         {"eff_margin":25.9,"adj_o":120.2,"adj_d":94.3, "efg":0.545,"to_rate":0.165,"exp":0.75,"seed":2},
    "Tennessee":       {"eff_margin":25.4,"adj_o":117.8,"adj_d":92.4, "efg":0.528,"to_rate":0.172,"exp":0.88,"seed":2},
    "Kansas":          {"eff_margin":24.1,"adj_o":119.6,"adj_d":95.5, "efg":0.541,"to_rate":0.160,"exp":0.78,"seed":2},
    "Iowa State":      {"eff_margin":23.8,"adj_o":118.9,"adj_d":95.1, "efg":0.538,"to_rate":0.163,"exp":0.82,"seed":2},
    "Purdue":          {"eff_margin":23.2,"adj_o":120.4,"adj_d":97.2, "efg":0.555,"to_rate":0.155,"exp":0.92,"seed":3},
    "Alabama":         {"eff_margin":22.7,"adj_o":121.0,"adj_d":98.3, "efg":0.562,"to_rate":0.175,"exp":0.55,"seed":3},
    "Michigan State":  {"eff_margin":22.1,"adj_o":117.5,"adj_d":95.4, "efg":0.530,"to_rate":0.168,"exp":0.95,"seed":3},
    "Wisconsin":       {"eff_margin":21.8,"adj_o":116.8,"adj_d":95.0, "efg":0.525,"to_rate":0.155,"exp":0.98,"seed":3},
    "Arizona":         {"eff_margin":21.4,"adj_o":119.2,"adj_d":97.8, "efg":0.548,"to_rate":0.170,"exp":0.65,"seed":3},
    "Marquette":       {"eff_margin":20.8,"adj_o":118.1,"adj_d":97.3, "efg":0.540,"to_rate":0.162,"exp":0.80,"seed":4},
    "St John's":       {"eff_margin":20.5,"adj_o":117.8,"adj_d":97.3, "efg":0.536,"to_rate":0.165,"exp":0.72,"seed":4},
    "Texas Tech":      {"eff_margin":20.2,"adj_o":116.5,"adj_d":96.3, "efg":0.522,"to_rate":0.160,"exp":0.85,"seed":4},
    "Kentucky":        {"eff_margin":19.8,"adj_o":117.2,"adj_d":97.4, "efg":0.535,"to_rate":0.168,"exp":0.58,"seed":4},
    "UConn":           {"eff_margin":19.4,"adj_o":116.9,"adj_d":97.5, "efg":0.532,"to_rate":0.165,"exp":0.75,"seed":5},
    "Gonzaga":         {"eff_margin":19.1,"adj_o":118.5,"adj_d":99.4, "efg":0.545,"to_rate":0.158,"exp":0.78,"seed":5},
    "Baylor":          {"eff_margin":18.6,"adj_o":116.2,"adj_d":97.6, "efg":0.528,"to_rate":0.172,"exp":0.70,"seed":5},
    "Illinois":        {"eff_margin":18.2,"adj_o":115.8,"adj_d":97.6, "efg":0.525,"to_rate":0.170,"exp":0.82,"seed":5},
    "Oregon":          {"eff_margin":17.8,"adj_o":115.5,"adj_d":97.7, "efg":0.522,"to_rate":0.173,"exp":0.65,"seed":6},
    "Louisville":      {"eff_margin":17.4,"adj_o":115.1,"adj_d":97.7, "efg":0.519,"to_rate":0.175,"exp":0.78,"seed":6},
    "Clemson":         {"eff_margin":17.0,"adj_o":114.8,"adj_d":97.8, "efg":0.516,"to_rate":0.177,"exp":0.80,"seed":6},
    "Creighton":       {"eff_margin":16.6,"adj_o":117.2,"adj_d":100.6,"efg":0.542,"to_rate":0.155,"exp":0.75,"seed":6},
    "Memphis":         {"eff_margin":16.2,"adj_o":114.5,"adj_d":98.3, "efg":0.512,"to_rate":0.180,"exp":0.60,"seed":7},
    "Missouri":        {"eff_margin":15.8,"adj_o":114.2,"adj_d":98.4, "efg":0.510,"to_rate":0.182,"exp":0.72,"seed":7},
    "UCLA":            {"eff_margin":15.4,"adj_o":113.9,"adj_d":98.5, "efg":0.508,"to_rate":0.183,"exp":0.68,"seed":7},
    "Mississippi State":{"eff_margin":15.0,"adj_o":113.6,"adj_d":98.6,"efg":0.505,"to_rate":0.185,"exp":0.75,"seed":7},
    "Villanova":       {"eff_margin":14.6,"adj_o":113.3,"adj_d":98.7, "efg":0.502,"to_rate":0.187,"exp":0.88,"seed":8},
    "Xavier":          {"eff_margin":14.2,"adj_o":113.0,"adj_d":98.8, "efg":0.500,"to_rate":0.188,"exp":0.80,"seed":8},
    "Nebraska":        {"eff_margin":13.4,"adj_o":112.4,"adj_d":99.0, "efg":0.495,"to_rate":0.191,"exp":0.82,"seed":8},
    "Northwestern":    {"eff_margin":13.0,"adj_o":112.1,"adj_d":99.1, "efg":0.492,"to_rate":0.193,"exp":0.85,"seed":9},
    "Oklahoma":        {"eff_margin":12.5,"adj_o":111.8,"adj_d":99.3, "efg":0.490,"to_rate":0.195,"exp":0.70,"seed":9},
    "Penn State":      {"eff_margin":12.0,"adj_o":111.5,"adj_d":99.5, "efg":0.488,"to_rate":0.197,"exp":0.78,"seed":9},
    "Ohio State":      {"eff_margin":11.5,"adj_o":111.2,"adj_d":99.7, "efg":0.485,"to_rate":0.198,"exp":0.72,"seed":9},
    "San Diego State": {"eff_margin": 9.8,"adj_o":109.5,"adj_d":99.7, "efg":0.475,"to_rate":0.185,"exp":0.88,"seed":11},
    "NC State":        {"eff_margin": 9.4,"adj_o":110.2,"adj_d":100.8,"efg":0.480,"to_rate":0.192,"exp":0.75,"seed":11},
    "VCU":             {"eff_margin": 9.0,"adj_o":109.8,"adj_d":100.8,"efg":0.472,"to_rate":0.188,"exp":0.85,"seed":11},
    "Grand Canyon":    {"eff_margin": 8.6,"adj_o":110.5,"adj_d":101.9,"efg":0.485,"to_rate":0.182,"exp":0.90,"seed":12},
    "McNeese":         {"eff_margin": 8.2,"adj_o":110.2,"adj_d":102.0,"efg":0.482,"to_rate":0.185,"exp":0.88,"seed":12},
    "Yale":            {"eff_margin": 6.6,"adj_o":112.0,"adj_d":105.4,"efg":0.495,"to_rate":0.175,"exp":0.95,"seed":13},
    "Vermont":         {"eff_margin": 6.2,"adj_o":111.5,"adj_d":105.3,"efg":0.490,"to_rate":0.178,"exp":0.92,"seed":13},
    "Colgate":         {"eff_margin": 5.8,"adj_o":111.2,"adj_d":105.4,"efg":0.488,"to_rate":0.180,"exp":0.95,"seed":13},
    "Montana":         {"eff_margin": 4.5,"adj_o":108.5,"adj_d":104.0,"efg":0.468,"to_rate":0.198,"exp":0.90,"seed":14},
    "South Dakota St": {"eff_margin": 3.0,"adj_o":107.6,"adj_d":104.6,"efg":0.459,"to_rate":0.205,"exp":0.92,"seed":15},
    "Norfolk State":   {"eff_margin": 1.0,"adj_o":106.5,"adj_d":105.5,"efg":0.448,"to_rate":0.215,"exp":0.82,"seed":16},

    # ── Additional power-conference & bubble teams ────────────────────────────
    "North Carolina":  {"eff_margin":18.4,"adj_o":118.2,"adj_d":99.8, "efg":0.538,"to_rate":0.165,"exp":0.62,"seed":6},
    "Indiana":         {"eff_margin":17.2,"adj_o":115.4,"adj_d":98.2, "efg":0.520,"to_rate":0.172,"exp":0.70,"seed":7},
    "Texas A&M":       {"eff_margin":16.8,"adj_o":114.8,"adj_d":98.0, "efg":0.518,"to_rate":0.174,"exp":0.78,"seed":7},
    "Ole Miss":        {"eff_margin":15.6,"adj_o":114.0,"adj_d":98.4, "efg":0.512,"to_rate":0.178,"exp":0.68,"seed":8},
    "Michigan":        {"eff_margin":15.2,"adj_o":113.8,"adj_d":98.6, "efg":0.510,"to_rate":0.180,"exp":0.72,"seed":8},
    "Arkansas":        {"eff_margin":14.8,"adj_o":113.5,"adj_d":98.7, "efg":0.508,"to_rate":0.182,"exp":0.65,"seed":9},
    "TCU":             {"eff_margin":14.4,"adj_o":113.2,"adj_d":98.8, "efg":0.506,"to_rate":0.184,"exp":0.80,"seed":9},
    "Pittsburgh":      {"eff_margin":14.0,"adj_o":112.9,"adj_d":98.9, "efg":0.504,"to_rate":0.186,"exp":0.75,"seed":9},
    "Virginia":        {"eff_margin":13.6,"adj_o":112.6,"adj_d":99.0, "efg":0.502,"to_rate":0.155,"exp":0.88,"seed":10},
    "Wake Forest":     {"eff_margin":13.2,"adj_o":112.3,"adj_d":99.1, "efg":0.498,"to_rate":0.188,"exp":0.72,"seed":10},
    "Colorado State":  {"eff_margin":12.8,"adj_o":112.0,"adj_d":99.2, "efg":0.495,"to_rate":0.185,"exp":0.85,"seed":10},
    "St. Bonaventure": {"eff_margin":11.2,"adj_o":111.0,"adj_d":99.8, "efg":0.490,"to_rate":0.188,"exp":0.85,"seed":11},
    "New Mexico":      {"eff_margin":10.8,"adj_o":110.8,"adj_d":100.0,"efg":0.485,"to_rate":0.190,"exp":0.80,"seed":11},
    "Georgia":         {"eff_margin":10.4,"adj_o":110.5,"adj_d":100.1,"efg":0.482,"to_rate":0.192,"exp":0.68,"seed":11},

    # ── Mid-major tournament automatic bids ───────────────────────────────────
    "Saint Mary's":    {"eff_margin":14.2,"adj_o":113.8,"adj_d":99.6, "efg":0.508,"to_rate":0.155,"exp":0.92,"seed":10},
    "Drake":           {"eff_margin":11.8,"adj_o":111.5,"adj_d":99.7, "efg":0.492,"to_rate":0.175,"exp":0.90,"seed":12},
    "Dayton":          {"eff_margin":10.5,"adj_o":110.5,"adj_d":100.0,"efg":0.480,"to_rate":0.182,"exp":0.85,"seed":11},
    "Liberty":         {"eff_margin": 9.2,"adj_o":110.2,"adj_d":101.0,"efg":0.478,"to_rate":0.185,"exp":0.88,"seed":12},
    "Oral Roberts":    {"eff_margin": 8.8,"adj_o":112.0,"adj_d":103.2,"efg":0.495,"to_rate":0.178,"exp":0.88,"seed":12},
    "High Point":      {"eff_margin": 7.4,"adj_o":111.0,"adj_d":103.6,"efg":0.488,"to_rate":0.180,"exp":0.85,"seed":13},
    "Wofford":         {"eff_margin": 6.8,"adj_o":110.5,"adj_d":103.7,"efg":0.485,"to_rate":0.182,"exp":0.88,"seed":13},
    "Lipscomb":        {"eff_margin": 5.5,"adj_o":109.5,"adj_d":104.0,"efg":0.472,"to_rate":0.192,"exp":0.85,"seed":14},
    "Bryant":          {"eff_margin": 5.0,"adj_o":109.0,"adj_d":104.0,"efg":0.468,"to_rate":0.195,"exp":0.82,"seed":14},
    "UNCG":            {"eff_margin": 4.8,"adj_o":108.8,"adj_d":104.0,"efg":0.466,"to_rate":0.196,"exp":0.88,"seed":14},
    "Akron":           {"eff_margin": 4.2,"adj_o":108.0,"adj_d":103.8,"efg":0.462,"to_rate":0.200,"exp":0.85,"seed":15},
    "Longwood":        {"eff_margin": 3.5,"adj_o":107.8,"adj_d":104.3,"efg":0.460,"to_rate":0.202,"exp":0.88,"seed":15},
    "Sacred Heart":    {"eff_margin": 2.0,"adj_o":107.0,"adj_d":105.0,"efg":0.452,"to_rate":0.210,"exp":0.82,"seed":16},
    "SIUE":            {"eff_margin": 1.5,"adj_o":106.8,"adj_d":105.3,"efg":0.450,"to_rate":0.212,"exp":0.80,"seed":16},

    # ── Alternate name spellings (match ESPN display names) ───────────────────
    "UNC":                  {"eff_margin":18.4,"adj_o":118.2,"adj_d":99.8, "efg":0.538,"to_rate":0.165,"exp":0.62,"seed":6},
    "North Carolina Tar Heels": {"eff_margin":18.4,"adj_o":118.2,"adj_d":99.8,"efg":0.538,"to_rate":0.165,"exp":0.62,"seed":6},
    "UConn Huskies":        {"eff_margin":19.4,"adj_o":116.9,"adj_d":97.5, "efg":0.532,"to_rate":0.165,"exp":0.75,"seed":5},
    "Gonzaga Bulldogs":     {"eff_margin":19.1,"adj_o":118.5,"adj_d":99.4, "efg":0.545,"to_rate":0.158,"exp":0.78,"seed":5},
    "Michigan State Spartans":{"eff_margin":22.1,"adj_o":117.5,"adj_d":95.4,"efg":0.530,"to_rate":0.168,"exp":0.95,"seed":3},
    "Iowa State Cyclones":  {"eff_margin":23.8,"adj_o":118.9,"adj_d":95.1, "efg":0.538,"to_rate":0.163,"exp":0.82,"seed":2},
}

CBB_SEED_HISTORY = {
    (1, 16): {"upset_rate": 0.03, "note": "Near-lock for 1-seed"},
    (2, 15): {"upset_rate": 0.06, "note": "Rare but happens"},
    (3, 14): {"upset_rate": 0.15, "note": "Occasional upset"},
    (4, 13): {"upset_rate": 0.21, "note": "Decent upset spot"},
    (5, 12): {"upset_rate": 0.35, "note": "Classic 5v12 upset matchup"},
    (6, 11): {"upset_rate": 0.37, "note": "Best historical upset matchup"},
    (7, 10): {"upset_rate": 0.40, "note": "Nearly a coin flip"},
    (8,  9): {"upset_rate": 0.49, "note": "True toss-up"},
}

# ── NBA Player Stats (2025-26 season estimates) ───────────────────────────────
# Fields: pts, reb, ast, pra, pts_l5, reb_l5, ast_l5, pra_l5,
#         min, usage, 3pa, 3pct, 3pm, blk, stl, pos, team
# FRAGILE: Hardcoded estimates. For production, replace with live ESPN player stats API.
# These represent typical 2025-26 season averages for top NBA players.
NBA_PLAYER_STATS = {
    "Nikola Jokic":            {"pts":28.1,"reb":13.2,"ast":9.4, "pra":50.7,"pts_l5":29.4,"reb_l5":12.8,"ast_l5":10.1,"pra_l5":52.3,"min":35.2,"usage":32.1,"3pa":4.2, "3pct":0.358,"3pm":1.5,"blk":0.9,"stl":1.4,"pos":"C","team":"Denver Nuggets"},
    "Shai Gilgeous-Alexander": {"pts":32.8,"reb":5.4, "ast":6.2, "pra":44.4,"pts_l5":34.1,"reb_l5":5.0, "ast_l5":6.5, "pra_l5":45.6,"min":34.8,"usage":35.2,"3pa":4.9, "3pct":0.352,"3pm":1.7,"blk":0.8,"stl":2.0,"pos":"G","team":"Oklahoma City Thunder"},
    "Giannis Antetokounmpo":   {"pts":30.4,"reb":11.8,"ast":6.1, "pra":48.3,"pts_l5":31.2,"reb_l5":12.0,"ast_l5":5.8, "pra_l5":49.0,"min":35.0,"usage":34.8,"3pa":1.2, "3pct":0.278,"3pm":0.3,"blk":1.4,"stl":1.2,"pos":"F","team":"Milwaukee Bucks"},
    "Jayson Tatum":            {"pts":28.9,"reb":8.3, "ast":4.8, "pra":42.0,"pts_l5":29.5,"reb_l5":8.1, "ast_l5":4.9, "pra_l5":42.5,"min":36.1,"usage":31.2,"3pa":7.4, "3pct":0.381,"3pm":2.8,"blk":0.7,"stl":1.1,"pos":"F","team":"Boston Celtics"},
    "LeBron James":            {"pts":22.8,"reb":7.6, "ast":8.2, "pra":38.6,"pts_l5":23.4,"reb_l5":7.8, "ast_l5":8.0, "pra_l5":39.2,"min":34.2,"usage":29.4,"3pa":5.1, "3pct":0.362,"3pm":1.8,"blk":0.6,"stl":1.3,"pos":"F","team":"Los Angeles Lakers"},
    "Stephen Curry":           {"pts":26.4,"reb":4.8, "ast":6.1, "pra":37.3,"pts_l5":27.8,"reb_l5":4.5, "ast_l5":6.3, "pra_l5":38.6,"min":33.2,"usage":30.1,"3pa":11.2,"3pct":0.428,"3pm":4.8,"blk":0.2,"stl":0.9,"pos":"G","team":"Golden State Warriors"},
    "Luka Doncic":             {"pts":31.2,"reb":8.7, "ast":8.5, "pra":48.4,"pts_l5":32.0,"reb_l5":8.4, "ast_l5":8.8, "pra_l5":49.2,"min":35.8,"usage":37.1,"3pa":8.4, "3pct":0.374,"3pm":3.1,"blk":0.5,"stl":1.4,"pos":"G","team":"Los Angeles Lakers"},
    "Joel Embiid":             {"pts":26.2,"reb":11.4,"ast":5.6, "pra":43.2,"pts_l5":27.1,"reb_l5":11.8,"ast_l5":5.4, "pra_l5":44.3,"min":33.8,"usage":35.4,"3pa":3.8, "3pct":0.321,"3pm":1.2,"blk":1.6,"stl":1.0,"pos":"C","team":"Philadelphia 76ers"},
    "Tyrese Haliburton":       {"pts":18.9,"reb":4.2, "ast":11.8,"pra":34.9,"pts_l5":19.4,"reb_l5":4.0, "ast_l5":12.1,"pra_l5":35.5,"min":33.4,"usage":22.8,"3pa":6.2, "3pct":0.384,"3pm":2.4,"blk":0.3,"stl":1.2,"pos":"G","team":"Indiana Pacers"},
    "Anthony Edwards":         {"pts":27.8,"reb":5.4, "ast":5.1, "pra":38.3,"pts_l5":28.9,"reb_l5":5.2, "ast_l5":5.3, "pra_l5":39.4,"min":35.4,"usage":33.2,"3pa":8.1, "3pct":0.364,"3pm":2.9,"blk":0.6,"stl":1.4,"pos":"G","team":"Minnesota Timberwolves"},
    "Kevin Durant":            {"pts":27.1,"reb":6.8, "ast":4.2, "pra":38.1,"pts_l5":27.8,"reb_l5":7.0, "ast_l5":4.1, "pra_l5":38.9,"min":36.2,"usage":31.8,"3pa":4.8, "3pct":0.388,"3pm":1.9,"blk":1.4,"stl":0.9,"pos":"F","team":"Houston Rockets"},
    "Damian Lillard":          {"pts":24.8,"reb":4.2, "ast":7.4, "pra":36.4,"pts_l5":25.4,"reb_l5":4.0, "ast_l5":7.6, "pra_l5":37.0,"min":34.8,"usage":31.0,"3pa":8.8, "3pct":0.374,"3pm":3.3,"blk":0.2,"stl":0.8,"pos":"G","team":"Milwaukee Bucks"},
    "Donovan Mitchell":        {"pts":26.2,"reb":4.8, "ast":4.9, "pra":35.9,"pts_l5":27.1,"reb_l5":4.6, "ast_l5":5.0, "pra_l5":36.7,"min":34.2,"usage":31.4,"3pa":6.8, "3pct":0.378,"3pm":2.6,"blk":0.4,"stl":1.8,"pos":"G","team":"Cleveland Cavaliers"},
    "Trae Young":              {"pts":23.4,"reb":3.4, "ast":11.2,"pra":38.0,"pts_l5":24.1,"reb_l5":3.2, "ast_l5":11.8,"pra_l5":39.1,"min":34.6,"usage":31.2,"3pa":7.2, "3pct":0.354,"3pm":2.5,"blk":0.2,"stl":0.9,"pos":"G","team":"Atlanta Hawks"},
    "Devin Booker":            {"pts":26.8,"reb":4.6, "ast":5.8, "pra":37.2,"pts_l5":27.4,"reb_l5":4.4, "ast_l5":6.0, "pra_l5":37.8,"min":35.2,"usage":32.4,"3pa":5.8, "3pct":0.374,"3pm":2.2,"blk":0.4,"stl":1.0,"pos":"G","team":"Phoenix Suns"},
    "Jaylen Brown":            {"pts":23.1,"reb":5.4, "ast":3.4, "pra":31.9,"pts_l5":23.8,"reb_l5":5.2, "ast_l5":3.5, "pra_l5":32.5,"min":34.8,"usage":28.4,"3pa":5.4, "3pct":0.368,"3pm":2.0,"blk":0.6,"stl":1.2,"pos":"G","team":"Boston Celtics"},
    "De'Aaron Fox":            {"pts":25.8,"reb":4.2, "ast":7.8, "pra":37.8,"pts_l5":26.4,"reb_l5":4.0, "ast_l5":8.1, "pra_l5":38.5,"min":34.4,"usage":30.8,"3pa":4.2, "3pct":0.334,"3pm":1.4,"blk":0.4,"stl":1.6,"pos":"G","team":"San Antonio Spurs"},
    "Bam Adebayo":             {"pts":21.4,"reb":10.8,"ast":4.8, "pra":37.0,"pts_l5":21.9,"reb_l5":11.0,"ast_l5":4.6, "pra_l5":37.5,"min":34.6,"usage":26.8,"3pa":0.8, "3pct":0.268,"3pm":0.2,"blk":1.2,"stl":1.4,"pos":"C","team":"Miami Heat"},
    "Karl-Anthony Towns":      {"pts":24.2,"reb":13.8,"ast":3.2, "pra":41.2,"pts_l5":24.8,"reb_l5":14.1,"ast_l5":3.0, "pra_l5":41.9,"min":34.8,"usage":28.4,"3pa":5.6, "3pct":0.401,"3pm":2.2,"blk":1.0,"stl":0.6,"pos":"C","team":"New York Knicks"},
    "Domantas Sabonis":        {"pts":19.8,"reb":14.2,"ast":8.4, "pra":42.4,"pts_l5":20.4,"reb_l5":14.8,"ast_l5":8.6, "pra_l5":43.8,"min":34.2,"usage":24.8,"3pa":0.8, "3pct":0.294,"3pm":0.2,"blk":0.6,"stl":1.4,"pos":"C","team":"Sacramento Kings"},
    "Ja Morant":               {"pts":26.4,"reb":5.8, "ast":8.4, "pra":40.6,"pts_l5":27.2,"reb_l5":5.6, "ast_l5":8.8, "pra_l5":41.6,"min":33.8,"usage":32.4,"3pa":3.4, "3pct":0.294,"3pm":1.0,"blk":0.5,"stl":1.2,"pos":"G","team":"Memphis Grizzlies"},
    "Zion Williamson":         {"pts":24.8,"reb":7.4, "ast":4.8, "pra":37.0,"pts_l5":25.4,"reb_l5":7.6, "ast_l5":4.6, "pra_l5":37.6,"min":32.8,"usage":32.4,"3pa":0.8, "3pct":0.264,"3pm":0.2,"blk":0.8,"stl":1.0,"pos":"F","team":"New Orleans Pelicans"},
    "Victor Wembanyama":       {"pts":24.6,"reb":10.8,"ast":4.0, "pra":39.4,"pts_l5":25.4,"reb_l5":11.2,"ast_l5":4.2, "pra_l5":40.8,"min":33.8,"usage":29.4,"3pa":4.8, "3pct":0.338,"3pm":1.6,"blk":4.2,"stl":1.4,"pos":"C","team":"San Antonio Spurs"},
    "Evan Mobley":             {"pts":18.2,"reb":9.8, "ast":3.4, "pra":31.4,"pts_l5":18.8,"reb_l5":10.1,"ast_l5":3.5, "pra_l5":32.4,"min":34.2,"usage":22.8,"3pa":2.4, "3pct":0.334,"3pm":0.8,"blk":2.4,"stl":1.0,"pos":"C","team":"Cleveland Cavaliers"},
    "Alperen Sengun":          {"pts":22.8,"reb":9.4, "ast":5.8, "pra":38.0,"pts_l5":23.4,"reb_l5":9.8, "ast_l5":6.0, "pra_l5":39.2,"min":32.8,"usage":28.4,"3pa":1.4, "3pct":0.278,"3pm":0.4,"blk":1.8,"stl":1.2,"pos":"C","team":"Houston Rockets"},
    "Cade Cunningham":         {"pts":26.8,"reb":5.8, "ast":9.2, "pra":41.8,"pts_l5":27.4,"reb_l5":5.6, "ast_l5":9.5, "pra_l5":42.5,"min":35.4,"usage":30.8,"3pa":5.8, "3pct":0.354,"3pm":2.0,"blk":0.6,"stl":1.4,"pos":"G","team":"Detroit Pistons"},
    "Franz Wagner":            {"pts":23.8,"reb":5.4, "ast":5.2, "pra":34.4,"pts_l5":24.4,"reb_l5":5.2, "ast_l5":5.4, "pra_l5":35.0,"min":34.8,"usage":27.4,"3pa":5.2, "3pct":0.348,"3pm":1.8,"blk":0.6,"stl":1.2,"pos":"F","team":"Orlando Magic"},
    "Darius Garland":          {"pts":18.8,"reb":3.4, "ast":7.8, "pra":30.0,"pts_l5":19.4,"reb_l5":3.2, "ast_l5":8.0, "pra_l5":30.6,"min":33.4,"usage":24.8,"3pa":5.8, "3pct":0.388,"3pm":2.2,"blk":0.2,"stl":1.0,"pos":"G","team":"Cleveland Cavaliers"},
    "Anthony Davis":           {"pts":25.8,"reb":12.4,"ast":3.4, "pra":41.6,"pts_l5":26.4,"reb_l5":12.8,"ast_l5":3.3, "pra_l5":42.5,"min":35.4,"usage":29.8,"3pa":1.4, "3pct":0.284,"3pm":0.4,"blk":2.4,"stl":1.2,"pos":"C","team":"Los Angeles Lakers"},
    "Rudy Gobert":             {"pts":14.2,"reb":12.8,"ast":1.8, "pra":28.8,"pts_l5":14.8,"reb_l5":13.1,"ast_l5":1.7, "pra_l5":29.6,"min":32.8,"usage":17.4,"3pa":0.2, "3pct":0.148,"3pm":0.0,"blk":2.2,"stl":0.8,"pos":"C","team":"Minnesota Timberwolves"},
    "Jalen Brunson":           {"pts":26.2,"reb":3.4, "ast":7.4, "pra":37.0,"pts_l5":27.0,"reb_l5":3.2, "ast_l5":7.6, "pra_l5":37.8,"min":34.8,"usage":32.4,"3pa":5.4, "3pct":0.378,"3pm":2.0,"blk":0.2,"stl":0.8,"pos":"G","team":"New York Knicks"},
    "Paolo Banchero":          {"pts":23.8,"reb":7.4, "ast":5.8, "pra":37.0,"pts_l5":24.4,"reb_l5":7.2, "ast_l5":6.0, "pra_l5":37.6,"min":34.4,"usage":28.8,"3pa":4.4, "3pct":0.334,"3pm":1.5,"blk":0.8,"stl":1.0,"pos":"F","team":"Orlando Magic"},
    "Jimmy Butler":            {"pts":21.4,"reb":5.8, "ast":4.8, "pra":32.0,"pts_l5":22.0,"reb_l5":5.6, "ast_l5":5.0, "pra_l5":32.6,"min":34.2,"usage":26.8,"3pa":2.4, "3pct":0.248,"3pm":0.6,"blk":0.6,"stl":1.6,"pos":"F","team":"Golden State Warriors"},
    "Mikal Bridges":           {"pts":19.8,"reb":4.4, "ast":3.8, "pra":28.0,"pts_l5":20.4,"reb_l5":4.2, "ast_l5":3.9, "pra_l5":28.5,"min":34.8,"usage":22.4,"3pa":6.4, "3pct":0.384,"3pm":2.5,"blk":0.6,"stl":0.8,"pos":"F","team":"New York Knicks"},
    "Scottie Barnes":          {"pts":20.4,"reb":8.8, "ast":6.4, "pra":35.6,"pts_l5":21.0,"reb_l5":9.0, "ast_l5":6.6, "pra_l5":36.6,"min":35.2,"usage":24.8,"3pa":3.4, "3pct":0.318,"3pm":1.1,"blk":1.0,"stl":1.4,"pos":"F","team":"Toronto Raptors"},
    "Tyrese Maxey":            {"pts":26.4,"reb":3.8, "ast":6.4, "pra":36.6,"pts_l5":27.0,"reb_l5":3.6, "ast_l5":6.6, "pra_l5":37.2,"min":35.4,"usage":30.8,"3pa":7.4, "3pct":0.378,"3pm":2.8,"blk":0.4,"stl":1.0,"pos":"G","team":"Philadelphia 76ers"},
    "Jalen Green":             {"pts":22.8,"reb":4.4, "ast":4.8, "pra":32.0,"pts_l5":23.4,"reb_l5":4.2, "ast_l5":5.0, "pra_l5":32.6,"min":33.8,"usage":28.4,"3pa":7.8, "3pct":0.348,"3pm":2.7,"blk":0.4,"stl":1.0,"pos":"G","team":"Houston Rockets"},
    "Jaren Jackson Jr.":       {"pts":22.4,"reb":6.8, "ast":2.4, "pra":31.6,"pts_l5":23.0,"reb_l5":7.0, "ast_l5":2.5, "pra_l5":32.5,"min":32.4,"usage":26.8,"3pa":5.4, "3pct":0.388,"3pm":2.1,"blk":3.2,"stl":0.8,"pos":"F","team":"Memphis Grizzlies"},
    "Desmond Bane":            {"pts":21.2,"reb":4.4, "ast":4.4, "pra":30.0,"pts_l5":21.8,"reb_l5":4.4, "ast_l5":4.5, "pra_l5":30.7,"min":33.8,"usage":25.4,"3pa":8.4, "3pct":0.398,"3pm":3.3,"blk":0.4,"stl":1.0,"pos":"G","team":"Memphis Grizzlies"},
    "Pascal Siakam":           {"pts":22.8,"reb":6.4, "ast":4.8, "pra":34.0,"pts_l5":23.4,"reb_l5":6.4, "ast_l5":4.9, "pra_l5":34.7,"min":34.8,"usage":27.8,"3pa":3.8, "3pct":0.334,"3pm":1.3,"blk":0.8,"stl":1.4,"pos":"F","team":"Indiana Pacers"},
    "Kawhi Leonard":           {"pts":22.4,"reb":6.8, "ast":3.8, "pra":33.0,"pts_l5":23.0,"reb_l5":6.8, "ast_l5":3.9, "pra_l5":33.7,"min":32.8,"usage":27.8,"3pa":4.2, "3pct":0.384,"3pm":1.6,"blk":0.8,"stl":1.6,"pos":"F","team":"Los Angeles Clippers"},
    "Lauri Markkanen":         {"pts":24.4,"reb":8.4, "ast":1.8, "pra":34.6,"pts_l5":25.0,"reb_l5":8.6, "ast_l5":1.8, "pra_l5":35.4,"min":33.8,"usage":27.4,"3pa":6.4, "3pct":0.388,"3pm":2.5,"blk":0.8,"stl":0.6,"pos":"F","team":"Utah Jazz"},
    "Kristaps Porzingis":      {"pts":20.4,"reb":7.4, "ast":2.4, "pra":30.2,"pts_l5":21.0,"reb_l5":7.6, "ast_l5":2.4, "pra_l5":31.0,"min":31.8,"usage":24.8,"3pa":4.4, "3pct":0.364,"3pm":1.6,"blk":2.0,"stl":0.6,"pos":"C","team":"Golden State Warriors"},
    "Jrue Holiday":            {"pts":13.8,"reb":4.8, "ast":5.4, "pra":24.0,"pts_l5":14.2,"reb_l5":4.8, "ast_l5":5.5, "pra_l5":24.5,"min":33.4,"usage":17.8,"3pa":4.8, "3pct":0.388,"3pm":1.9,"blk":0.8,"stl":1.8,"pos":"G","team":"Boston Celtics"},
    "Derrick White":           {"pts":15.8,"reb":4.8, "ast":4.8, "pra":25.4,"pts_l5":16.2,"reb_l5":4.8, "ast_l5":4.9, "pra_l5":25.9,"min":33.8,"usage":19.8,"3pa":6.4, "3pct":0.398,"3pm":2.5,"blk":1.4,"stl":0.9,"pos":"G","team":"Boston Celtics"},
    "Immanuel Quickley":       {"pts":17.4,"reb":4.8, "ast":6.4, "pra":28.6,"pts_l5":18.0,"reb_l5":4.8, "ast_l5":6.6, "pra_l5":29.4,"min":32.8,"usage":22.8,"3pa":5.8, "3pct":0.368,"3pm":2.1,"blk":0.4,"stl":1.2,"pos":"G","team":"Toronto Raptors"},
    "OG Anunoby":              {"pts":16.4,"reb":5.8, "ast":2.8, "pra":25.0,"pts_l5":16.8,"reb_l5":5.8, "ast_l5":2.8, "pra_l5":25.4,"min":33.8,"usage":19.8,"3pa":5.8, "3pct":0.384,"3pm":2.2,"blk":0.8,"stl":1.4,"pos":"F","team":"New York Knicks"},
    "Klay Thompson":           {"pts":16.8,"reb":3.4, "ast":2.4, "pra":22.6,"pts_l5":17.4,"reb_l5":3.4, "ast_l5":2.4, "pra_l5":23.2,"min":30.8,"usage":21.8,"3pa":9.2, "3pct":0.408,"3pm":3.7,"blk":0.6,"stl":0.6,"pos":"G","team":"Dallas Mavericks"},
    "Kyrie Irving":            {"pts":24.4,"reb":4.8, "ast":5.4, "pra":34.6,"pts_l5":25.0,"reb_l5":4.6, "ast_l5":5.6, "pra_l5":35.2,"min":34.4,"usage":30.8,"3pa":6.8, "3pct":0.394,"3pm":2.7,"blk":0.4,"stl":1.2,"pos":"G","team":"Dallas Mavericks"},
    "Brook Lopez":             {"pts":14.8,"reb":5.4, "ast":2.0, "pra":22.2,"pts_l5":15.2,"reb_l5":5.5, "ast_l5":2.0, "pra_l5":22.7,"min":28.8,"usage":18.8,"3pa":4.4, "3pct":0.374,"3pm":1.6,"blk":2.4,"stl":0.6,"pos":"C","team":"Milwaukee Bucks"},
    "Myles Turner":            {"pts":16.8,"reb":7.4, "ast":1.8, "pra":26.0,"pts_l5":17.2,"reb_l5":7.6, "ast_l5":1.8, "pra_l5":26.6,"min":30.4,"usage":20.8,"3pa":5.4, "3pct":0.388,"3pm":2.1,"blk":2.4,"stl":0.6,"pos":"C","team":"Indiana Pacers"},
    # ── 2025-26 additions / transfers ─────────────────────────────────────────
    # LAL (Luka trade additions)
    "Austin Reaves":           {"pts":17.8,"reb":4.2, "ast":4.8, "pra":26.8,"pts_l5":18.4,"reb_l5":4.0, "ast_l5":4.9, "pra_l5":27.3,"min":33.4,"usage":22.4,"3pa":6.8, "3pct":0.392,"3pm":2.7,"blk":0.4,"stl":1.2,"pos":"G","team":"Los Angeles Lakers"},
    "Deandre Ayton":           {"pts":16.8,"reb":9.8, "ast":1.6, "pra":28.2,"pts_l5":17.4,"reb_l5":10.1,"ast_l5":1.5, "pra_l5":29.0,"min":30.8,"usage":21.4,"3pa":0.4, "3pct":0.218,"3pm":0.1,"blk":1.4,"stl":0.8,"pos":"C","team":"Los Angeles Lakers"},
    "Marcus Smart":            {"pts":10.8,"reb":3.8, "ast":6.4, "pra":21.0,"pts_l5":11.2,"reb_l5":3.6, "ast_l5":6.6, "pra_l5":21.4,"min":28.4,"usage":18.4,"3pa":4.2, "3pct":0.334,"3pm":1.4,"blk":0.4,"stl":1.6,"pos":"G","team":"Los Angeles Lakers"},
    "Max Christie":            {"pts":11.8,"reb":3.4, "ast":2.2, "pra":17.4,"pts_l5":12.4,"reb_l5":3.2, "ast_l5":2.2, "pra_l5":17.8,"min":26.4,"usage":16.8,"3pa":5.4, "3pct":0.374,"3pm":2.0,"blk":0.4,"stl":0.8,"pos":"G","team":"Los Angeles Lakers"},
    # MIN (Randle/DiVincenzo trade additions)
    "Julius Randle":           {"pts":21.8,"reb":9.4, "ast":4.6, "pra":35.8,"pts_l5":22.4,"reb_l5":9.6, "ast_l5":4.8, "pra_l5":36.8,"min":33.8,"usage":27.4,"3pa":5.2, "3pct":0.342,"3pm":1.8,"blk":0.6,"stl":1.0,"pos":"F","team":"Minnesota Timberwolves"},
    "Donte DiVincenzo":        {"pts":12.8,"reb":3.4, "ast":3.2, "pra":19.4,"pts_l5":13.4,"reb_l5":3.2, "ast_l5":3.4, "pra_l5":20.0,"min":28.8,"usage":18.4,"3pa":6.8, "3pct":0.388,"3pm":2.6,"blk":0.3,"stl":1.0,"pos":"G","team":"Minnesota Timberwolves"},
    "Jaden McDaniels":         {"pts":17.4,"reb":4.8, "ast":2.4, "pra":24.6,"pts_l5":18.0,"reb_l5":5.0, "ast_l5":2.5, "pra_l5":25.5,"min":32.4,"usage":20.8,"3pa":5.4, "3pct":0.364,"3pm":2.0,"blk":1.2,"stl":1.2,"pos":"F","team":"Minnesota Timberwolves"},
    # GSW
    "Draymond Green":          {"pts":9.4, "reb":7.4, "ast":7.8, "pra":24.6,"pts_l5":9.8, "reb_l5":7.6, "ast_l5":8.0, "pra_l5":25.4,"min":30.4,"usage":14.8,"3pa":1.4, "3pct":0.288,"3pm":0.4,"blk":0.8,"stl":1.2,"pos":"F","team":"Golden State Warriors"},
    "Al Horford":              {"pts":7.8, "reb":5.8, "ast":2.6, "pra":16.2,"pts_l5":8.0, "reb_l5":5.8, "ast_l5":2.6, "pra_l5":16.4,"min":25.4,"usage":12.4,"3pa":3.8, "3pct":0.348,"3pm":1.3,"blk":1.2,"stl":0.6,"pos":"C","team":"Golden State Warriors"},
    # SAS
    "Devin Vassell":           {"pts":20.2,"reb":4.4, "ast":3.8, "pra":28.4,"pts_l5":20.8,"reb_l5":4.4, "ast_l5":3.9, "pra_l5":29.1,"min":33.4,"usage":24.8,"3pa":6.4, "3pct":0.374,"3pm":2.4,"blk":0.6,"stl":1.2,"pos":"G","team":"San Antonio Spurs"},
    "Stephon Castle":          {"pts":12.8,"reb":3.8, "ast":4.2, "pra":20.8,"pts_l5":13.4,"reb_l5":3.8, "ast_l5":4.4, "pra_l5":21.6,"min":28.4,"usage":18.4,"3pa":3.8, "3pct":0.344,"3pm":1.3,"blk":0.4,"stl":1.2,"pos":"G","team":"San Antonio Spurs"},
    "Dylan Harper":            {"pts":14.2,"reb":3.4, "ast":5.2, "pra":22.8,"pts_l5":14.8,"reb_l5":3.4, "ast_l5":5.4, "pra_l5":23.6,"min":29.8,"usage":20.4,"3pa":3.4, "3pct":0.334,"3pm":1.1,"blk":0.4,"stl":1.0,"pos":"G","team":"San Antonio Spurs"},
    "Neemias Queta":           {"pts":8.4, "reb":6.8, "ast":1.4, "pra":16.6,"pts_l5":8.8, "reb_l5":7.0, "ast_l5":1.4, "pra_l5":17.2,"min":21.8,"usage":12.8,"3pa":0.2, "3pct":0.178,"3pm":0.0,"blk":1.8,"stl":0.4,"pos":"C","team":"Boston Celtics"},
    # DAL
    "Cooper Flagg":            {"pts":15.4,"reb":7.2, "ast":4.4, "pra":27.0,"pts_l5":16.2,"reb_l5":7.4, "ast_l5":4.6, "pra_l5":28.2,"min":30.8,"usage":20.4,"3pa":4.8, "3pct":0.338,"3pm":1.6,"blk":1.4,"stl":1.6,"pos":"F","team":"Dallas Mavericks"},
    "Daniel Gafford":          {"pts":13.4,"reb":7.8, "ast":1.4, "pra":22.6,"pts_l5":13.8,"reb_l5":8.0, "ast_l5":1.4, "pra_l5":23.2,"min":26.8,"usage":16.8,"3pa":0.2, "3pct":0.188,"3pm":0.0,"blk":2.2,"stl":0.8,"pos":"C","team":"Dallas Mavericks"},
    "P.J. Washington":         {"pts":14.8,"reb":6.4, "ast":2.4, "pra":23.6,"pts_l5":15.2,"reb_l5":6.6, "ast_l5":2.4, "pra_l5":24.2,"min":30.4,"usage":18.4,"3pa":5.8, "3pct":0.354,"3pm":2.0,"blk":1.0,"stl":0.8,"pos":"F","team":"Dallas Mavericks"},
    "Naji Marshall":           {"pts":9.8, "reb":4.2, "ast":2.8, "pra":16.8,"pts_l5":10.2,"reb_l5":4.2, "ast_l5":2.8, "pra_l5":17.2,"min":24.4,"usage":14.8,"3pa":4.4, "3pct":0.354,"3pm":1.6,"blk":0.4,"stl":1.0,"pos":"F","team":"Dallas Mavericks"},
    # ATL
    "Jalen Johnson":           {"pts":20.8,"reb":8.2, "ast":5.8, "pra":34.8,"pts_l5":21.4,"reb_l5":8.4, "ast_l5":6.0, "pra_l5":35.8,"min":33.4,"usage":24.8,"3pa":3.4, "3pct":0.318,"3pm":1.1,"blk":0.8,"stl":1.4,"pos":"F","team":"Atlanta Hawks"},
    "Dyson Daniels":           {"pts":14.2,"reb":4.8, "ast":4.4, "pra":23.4,"pts_l5":14.8,"reb_l5":4.8, "ast_l5":4.6, "pra_l5":24.2,"min":31.4,"usage":18.4,"3pa":4.8, "3pct":0.348,"3pm":1.7,"blk":0.4,"stl":2.2,"pos":"G","team":"Atlanta Hawks"},
    "Onyeka Okongwu":          {"pts":16.4,"reb":8.8, "ast":3.0, "pra":28.2,"pts_l5":16.8,"reb_l5":9.0, "ast_l5":3.0, "pra_l5":28.8,"min":29.8,"usage":20.4,"3pa":0.4, "3pct":0.228,"3pm":0.1,"blk":1.6,"stl":1.0,"pos":"C","team":"Atlanta Hawks"},
    "Nickeil Alexander-Walker": {"pts":14.4,"reb":3.4, "ast":4.2, "pra":22.0,"pts_l5":14.8,"reb_l5":3.4, "ast_l5":4.4, "pra_l5":22.6,"min":28.8,"usage":18.8,"3pa":5.8, "3pct":0.364,"3pm":2.1,"blk":0.4,"stl":1.2,"pos":"G","team":"Dallas Mavericks"},
    # HOU
    "Jabari Smith Jr.":        {"pts":16.8,"reb":7.4, "ast":2.2, "pra":26.4,"pts_l5":17.4,"reb_l5":7.6, "ast_l5":2.2, "pra_l5":27.2,"min":31.4,"usage":20.8,"3pa":5.8, "3pct":0.368,"3pm":2.1,"blk":1.4,"stl":0.8,"pos":"F","team":"Houston Rockets"},
    "Amen Thompson":           {"pts":18.4,"reb":8.8, "ast":5.4, "pra":32.6,"pts_l5":19.0,"reb_l5":9.0, "ast_l5":5.6, "pra_l5":33.6,"min":32.4,"usage":22.4,"3pa":2.4, "3pct":0.298,"3pm":0.7,"blk":0.8,"stl":1.6,"pos":"F","team":"Houston Rockets"},
    "Tari Eason":              {"pts":13.8,"reb":5.8, "ast":2.4, "pra":22.0,"pts_l5":14.2,"reb_l5":6.0, "ast_l5":2.4, "pra_l5":22.6,"min":28.4,"usage":17.8,"3pa":3.4, "3pct":0.338,"3pm":1.1,"blk":1.0,"stl":1.4,"pos":"F","team":"Houston Rockets"},
    "Reed Sheppard":           {"pts":13.4,"reb":3.4, "ast":4.8, "pra":21.6,"pts_l5":13.8,"reb_l5":3.4, "ast_l5":5.0, "pra_l5":22.2,"min":28.4,"usage":17.8,"3pa":6.4, "3pct":0.404,"3pm":2.6,"blk":0.2,"stl":1.2,"pos":"G","team":"Houston Rockets"},
    # SAC / IND cross-overs
    "DeMar DeRozan":           {"pts":20.4,"reb":4.4, "ast":4.2, "pra":29.0,"pts_l5":21.0,"reb_l5":4.4, "ast_l5":4.2, "pra_l5":29.6,"min":32.8,"usage":26.4,"3pa":1.4, "3pct":0.274,"3pm":0.4,"blk":0.4,"stl":1.0,"pos":"G","team":"Sacramento Kings"},
    "Precious Achiuwa":        {"pts":11.4,"reb":8.2, "ast":1.8, "pra":21.4,"pts_l5":11.8,"reb_l5":8.4, "ast_l5":1.8, "pra_l5":22.0,"min":24.8,"usage":14.8,"3pa":0.6, "3pct":0.218,"3pm":0.1,"blk":1.2,"stl":0.6,"pos":"C","team":"Indiana Pacers"},
    "Aaron Nesmith":           {"pts":13.8,"reb":4.2, "ast":2.4, "pra":20.4,"pts_l5":14.2,"reb_l5":4.2, "ast_l5":2.4, "pra_l5":20.8,"min":28.4,"usage":17.4,"3pa":5.4, "3pct":0.354,"3pm":1.9,"blk":0.4,"stl":1.0,"pos":"F","team":"Indiana Pacers"},
    "Russell Westbrook":       {"pts":8.4, "reb":4.4, "ast":5.8, "pra":18.6,"pts_l5":8.8, "reb_l5":4.4, "ast_l5":6.0, "pra_l5":19.2,"min":20.8,"usage":16.4,"3pa":2.8, "3pct":0.288,"3pm":0.8,"blk":0.2,"stl":1.0,"pos":"G","team":"Sacramento Kings"},
    # CHI
    "Isaac Okoro":             {"pts":11.2,"reb":3.4, "ast":2.8, "pra":17.4,"pts_l5":11.6,"reb_l5":3.4, "ast_l5":2.8, "pra_l5":17.8,"min":27.4,"usage":14.8,"3pa":4.4, "3pct":0.328,"3pm":1.4,"blk":0.6,"stl":1.4,"pos":"F","team":"Chicago Bulls"},
    # TOR
    "RJ Barrett":              {"pts":21.4,"reb":5.8, "ast":4.4, "pra":31.6,"pts_l5":22.0,"reb_l5":5.8, "ast_l5":4.4, "pra_l5":32.2,"min":33.8,"usage":25.8,"3pa":5.4, "3pct":0.354,"3pm":1.9,"blk":0.6,"stl":1.0,"pos":"F","team":"Toronto Raptors"},
    "Jakob Poeltl":            {"pts":12.8,"reb":9.4, "ast":3.2, "pra":25.4,"pts_l5":13.2,"reb_l5":9.6, "ast_l5":3.2, "pra_l5":26.0,"min":26.8,"usage":16.8,"3pa":0.2, "3pct":0.188,"3pm":0.0,"blk":2.2,"stl":0.8,"pos":"C","team":"Toronto Raptors"},
    "Sam Hauser":              {"pts":12.8,"reb":3.8, "ast":2.2, "pra":18.8,"pts_l5":13.2,"reb_l5":3.8, "ast_l5":2.2, "pra_l5":19.2,"min":26.4,"usage":16.4,"3pa":7.4, "3pct":0.424,"3pm":3.1,"blk":0.2,"stl":0.6,"pos":"F","team":"Boston Celtics"},
    # CJ McCollum likely with DAL or elsewhere
    "CJ McCollum":             {"pts":17.8,"reb":3.8, "ast":5.4, "pra":27.0,"pts_l5":18.2,"reb_l5":3.8, "ast_l5":5.6, "pra_l5":27.6,"min":31.4,"usage":23.8,"3pa":7.4, "3pct":0.394,"3pm":2.9,"blk":0.4,"stl":0.8,"pos":"G","team":"Dallas Mavericks"},
}

# ── Time helpers ──────────────────────────────────────────────────────────────
def _et_offset(utc_dt):
    """Return ET UTC offset considering DST."""
    y = utc_dt.year
    dst_start = datetime(y, 3, 8, 2, tzinfo=timezone.utc)
    while dst_start.weekday() != 6:
        dst_start += timedelta(days=1)
    dst_end = datetime(y, 11, 1, 2, tzinfo=timezone.utc)
    while dst_end.weekday() != 6:
        dst_end += timedelta(days=1)
    return timedelta(hours=-4) if dst_start <= utc_dt < dst_end else timedelta(hours=-5)

def now_et():
    u = datetime.now(timezone.utc)
    return u + _et_offset(u)

def fmt_time(iso_str):
    if not iso_str:
        return ""
    try:
        u = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        et = u + _et_offset(u)
        h = int(et.strftime("%-I"))
        return f"{h}:{et.strftime('%M %p')} ET"
    except Exception:
        return ""

# ── Odds / probability helpers ────────────────────────────────────────────────
def am_odds(p):
    """Convert win probability to American odds string."""
    if p is None or p < 0.02 or p > 0.98:
        return "—"
    if p >= 0.5:
        return f"-{round(p / (1 - p) * 100)}"
    return f"+{round((1 - p) / p * 100)}"

def prob_to_pct(p, decimals=0):
    """Format probability as percentage string."""
    if p is None:
        return "—"
    return f"{p * 100:.{decimals}f}%"

def normalize_weights(weights: dict) -> dict:
    """Normalize weight dict so values sum to 1.0."""
    total = sum(abs(v) for v in weights.values())
    if total <= 0:
        return {k: 1.0 / len(weights) for k in weights}
    return {k: v / total for k, v in weights.items()}

# ── Team name matching ────────────────────────────────────────────────────────
def find_nba_team(text: str):
    """Fuzzy match text to an NBA full team name. Returns name string or None."""
    t = (text or "").lower()
    for k in sorted(NBA_ALIASES, key=len, reverse=True):
        if re.search(r'\b' + re.escape(k) + r'\b', t):
            return NBA_ALIASES[k]
    return None

def city_of(full_name: str) -> str:
    """'Dallas Mavericks' → 'dallas'"""
    parts = (full_name or "").split()
    return " ".join(parts[:-1]).lower()

def nick_of(full_name: str) -> str:
    """'Dallas Mavericks' → 'mavericks'"""
    return (full_name or "").split()[-1].lower()

def team_text_match(full_name: str, text: str) -> bool:
    """True if text contains the city OR nickname of full_name."""
    t = text.lower()
    city = city_of(full_name)
    nick = nick_of(full_name)
    if city and re.search(r'\b' + re.escape(city) + r'\b', t):
        return True
    if nick and re.search(r'\b' + re.escape(nick) + r'\b', t):
        return True
    return False

# ESPN display name → CBB_TEAM_STATS key (handles mascot suffixes and alt names)
_CBB_ESPN_ALIASES = {
    "connecticut": "UConn", "uconn huskies": "UConn",
    "duke blue devils": "Duke",
    "auburn tigers": "Auburn",
    "houston cougars": "Houston",
    "florida gators": "Florida",
    "tennessee volunteers": "Tennessee",
    "kansas jayhawks": "Kansas",
    "iowa state cyclones": "Iowa State",
    "purdue boilermakers": "Purdue",
    "alabama crimson tide": "Alabama",
    "michigan state spartans": "Michigan State",
    "wisconsin badgers": "Wisconsin",
    "arizona wildcats": "Arizona",
    "marquette golden eagles": "Marquette",
    "st. john's red storm": "St John's", "saint john's red storm": "St John's",
    "texas tech red raiders": "Texas Tech",
    "kentucky wildcats": "Kentucky",
    "north carolina tar heels": "North Carolina", "unc tar heels": "North Carolina",
    "baylor bears": "Baylor",
    "illinois fighting illini": "Illinois",
    "san diego state aztecs": "San Diego State", "sdsu": "San Diego State",
    "nc state wolfpack": "NC State",
    "vcu rams": "VCU",
    "saint mary's gaels": "Saint Mary's",
    "michigan wolverines": "Michigan",
    "indiana hoosiers": "Indiana",
    "nebraska cornhuskers": "Nebraska",
    "northwestern wildcats": "Northwestern",
    "oklahoma sooners": "Oklahoma",
    "penn state nittany lions": "Penn State",
    "ohio state buckeyes": "Ohio State",
    "memphis tigers": "Memphis",
    "missouri tigers": "Missouri",
    "ucla bruins": "UCLA",
    "mississippi state bulldogs": "Mississippi State",
    "villanova wildcats": "Villanova",
    "xavier musketeers": "Xavier",
    "creighton bluejays": "Creighton",
    "oregon ducks": "Oregon",
    "louisville cardinals": "Louisville",
    "clemson tigers": "Clemson",
    "gonzaga bulldogs": "Gonzaga",
    "drake bulldogs": "Drake",
    "dayton flyers": "Dayton",
    "liberty flames": "Liberty",
    "oral roberts golden eagles": "Oral Roberts",
    "wofford terriers": "Wofford",
    "colgate raiders": "Colgate",
    "vermont catamounts": "Vermont",
    "yale bulldogs": "Yale",
    "montana grizzlies": "Montana",
    "south dakota state jackrabbits": "South Dakota St",
    "norfolk state spartans": "Norfolk State",
    "grand canyon antelopes": "Grand Canyon",
    "mcneese cowboys": "McNeese", "mcneese state cowboys": "McNeese",
    "colorado state rams": "Colorado State",
    "new mexico lobos": "New Mexico",
}

def find_cbb_team(name: str):
    """
    Fuzzy match a team name to CBB_TEAM_STATS.
    Handles ESPN full display names (e.g. 'Duke Blue Devils' → 'Duke').
    Returns (key, stats_dict).
    """
    if not name:
        return name, {"eff_margin": 8.0, "adj_o": 110.0, "adj_d": 102.0,
                      "efg": 0.480, "to_rate": 0.190, "exp": 0.75, "seed": None}
    nl = name.lower().strip()

    # 1. Direct alias lookup (ESPN display names, mascot suffixes)
    if nl in _CBB_ESPN_ALIASES:
        key = _CBB_ESPN_ALIASES[nl]
        if key in CBB_TEAM_STATS:
            return key, CBB_TEAM_STATS[key]

    # 2. Exact / substring match on CBB_TEAM_STATS keys
    for key, stats in CBB_TEAM_STATS.items():
        kl = key.lower()
        if kl == nl or kl in nl or nl in kl:
            return key, stats

    # 3. Word-overlap match (handles "Duke Blue Devils" → "Duke")
    nw = set(nl.split())
    best_key = best_stats = None
    best_ratio = 0.0
    for key, stats in CBB_TEAM_STATS.items():
        kw = set(key.lower().split())
        overlap = nw & kw
        if overlap:
            ratio = len(overlap) / max(len(kw), 1)
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key
                best_stats = stats
    if best_ratio >= 0.5:
        return best_key, best_stats

    # 4. Unknown team — return neutral defaults
    return name, {"eff_margin": 8.0, "adj_o": 110.0, "adj_d": 102.0,
                  "efg": 0.480, "to_rate": 0.190, "exp": 0.75, "seed": None}

def _strip_accents(s: str) -> str:
    """Normalize unicode and strip accent characters (e.g. Dončić → Doncic)."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")

def find_nba_player(name: str):
    """Fuzzy match player name to NBA_PLAYER_STATS. Returns stats dict or None."""
    if not name:
        return None
    nl  = name.lower().strip()
    nla = _strip_accents(nl)   # accent-stripped version for fallback matching
    # Exact
    for key, stats in NBA_PLAYER_STATS.items():
        if key.lower() == nl:
            return {**stats, "name": key}
    # Exact accent-stripped
    for key, stats in NBA_PLAYER_STATS.items():
        if _strip_accents(key.lower()) == nla:
            return {**stats, "name": key}
    # Substring
    for key, stats in NBA_PLAYER_STATS.items():
        kl = key.lower()
        if nl in kl or kl in nl:
            return {**stats, "name": key}
    # Substring accent-stripped
    for key, stats in NBA_PLAYER_STATS.items():
        kla = _strip_accents(key.lower())
        if nla in kla or kla in nla:
            return {**stats, "name": key}
    # Last-name match (accent-stripped)
    nl_parts = nla.split()
    if nl_parts:
        last = nl_parts[-1]
        for key, stats in NBA_PLAYER_STATS.items():
            if _strip_accents(key.lower()).split()[-1] == last:
                return {**stats, "name": key}
    return None
