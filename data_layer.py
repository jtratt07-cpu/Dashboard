"""
data_layer.py — All external data fetching.
Rules:
  - Every function here must use @st.cache_data(ttl=600)
  - No UI code
  - No model logic
  - No API calls anywhere else in the project
"""
import streamlit as st
import requests
from utils import ESPN_MAP, KALSHI_BASE, fmt_time

# ─────────────────────────────────────────────────────────────────────────────
# ESPN — free, no authentication
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def get_espn_games(date_str: str, sport: str = "nba") -> tuple:
    """
    Fetch today's games from ESPN free scoreboard API.
    sport: "nba" | "mens-college-basketball"
    Returns (games_list, error_str | None)
    games_list items: {away, home, time_et, status, date_iso}
    """
    sport_paths = {
        "nba":  "basketball/nba",
        "cbb":  "basketball/mens-college-basketball",
        "mlb":  "baseball/mlb",
        "nfl":  "football/nfl",
    }
    path = sport_paths.get(sport, "basketball/nba")
    url  = f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={date_str}"

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return [], str(e)

    games = []
    for ev in data.get("events", []):
        comp = ev.get("competitions", [{}])[0]
        home = away = None
        home_score = away_score = None
        for t in comp.get("competitors", []):
            abbr  = t.get("team", {}).get("abbreviation", "")
            # NBA full name lookup; fallback to ESPN display name
            full  = ESPN_MAP.get(abbr) or t.get("team", {}).get("displayName", abbr)
            score = t.get("score")
            if t.get("homeAway") == "home":
                home = full
                home_score = score
            else:
                away = full
                away_score = score

        date_iso = ev.get("date", "")
        status   = ev.get("status", {}).get("type", {}).get("description", "Scheduled")
        short_st = ev.get("status", {}).get("type", {}).get("shortDetail", "")
        games.append({
            "away":        away,
            "home":        home,
            "time_et":     fmt_time(date_iso),
            "status":      status,
            "short_status": short_st,
            "date_iso":    date_iso,
            "home_score":  home_score,
            "away_score":  away_score,
        })

    return games, None


@st.cache_data(ttl=600, show_spinner=False)
def get_espn_scoreboard(date_str: str, sport: str = "nba") -> tuple:
    """Alias of get_espn_games — kept for Scores tab clarity."""
    return get_espn_games(date_str, sport)


# ─────────────────────────────────────────────────────────────────────────────
# Kalshi — public market data, no authentication required
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def get_kalshi_events(series_ticker: str) -> list:
    """
    Fetch all events for a given Kalshi series (e.g., 'kxnbagame', 'kxcbbgame').
    Returns list of event dicts. Returns [] on any failure.
    Tries open status first; breaks after first successful batch.
    """
    events = []
    seen   = set()

    for status in ["open", None]:
        cursor = None
        for _ in range(20):
            params = {
                "series_ticker":      series_ticker,
                "with_nested_markets": "true",
                "limit":              200,
            }
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor

            try:
                r = requests.get(f"{KALSHI_BASE}/events", params=params, timeout=20)
                if r.status_code != 200:
                    break
                d = r.json()
                for ev in d.get("events", []):
                    tk = ev.get("event_ticker", "")
                    if tk and tk not in seen:
                        seen.add(tk)
                        events.append(ev)
                cursor = d.get("cursor")
                if not cursor or not d.get("events"):
                    break
            except Exception:
                break

        if events:
            break  # got results from first working status pass

    return events


@st.cache_data(ttl=600, show_spinner=False)
def get_kalshi_markets_for_event(event_ticker: str) -> list:
    """
    Fetch all markets for a specific Kalshi event_ticker.
    Returns list of market dicts. Returns [] on failure.
    """
    markets = []
    cursor  = None
    for _ in range(10):
        params = {"event_ticker": event_ticker, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        try:
            r = requests.get(f"{KALSHI_BASE}/markets", params=params, timeout=15)
            if r.status_code != 200:
                break
            d = r.json()
            markets.extend(d.get("markets", []))
            cursor = d.get("cursor")
            if not cursor or not d.get("markets"):
                break
        except Exception:
            break

    return markets


@st.cache_data(ttl=600, show_spinner=False)
def search_kalshi_markets(keyword: str, status: str = "open", limit: int = 200) -> list:
    """
    Search Kalshi markets by keyword across all series.
    Returns list of market dicts. Returns [] on failure.
    Used for prop market discovery.
    """
    markets = []
    cursor  = None
    for _ in range(5):
        params = {"limit": limit, "status": status}
        if keyword:
            params["keyword"] = keyword
        if cursor:
            params["cursor"] = cursor
        try:
            r = requests.get(f"{KALSHI_BASE}/markets", params=params, timeout=20)
            if r.status_code != 200:
                break
            d = r.json()
            markets.extend(d.get("markets", []))
            cursor = d.get("cursor")
            if not cursor or not d.get("markets"):
                break
        except Exception:
            break

    return markets


def _get_nba_prop_markets_inner() -> list:
    """
    Discover NBA player prop markets from Kalshi.
    Tries multiple known series tickers and keyword searches.
    Returns combined, deduplicated list of market dicts.
    Not directly cached — wrapping function get_nba_prop_markets is cached.
    """
    seen    = set()
    markets = []

    def add_batch(batch):
        for m in batch:
            tk = m.get("ticker", "")
            if tk and tk not in seen:
                seen.add(tk)
                markets.append(m)

    # Try known prop series tickers
    for series in ["KXNBAPROP", "KXNBA3D", "KXNBAPRA"]:
        evs = get_kalshi_events(series)
        if evs:
            for ev in evs:
                tks = ev.get("event_ticker", ev.get("ticker", ""))
                if tks:
                    add_batch(get_kalshi_markets_for_event(tks))

    # Keyword search fallback for player props
    for kw in ["NBA points", "NBA rebounds", "NBA assists", "NBA blocks", "NBA steals", "NBA 3-pointer"]:
        add_batch(search_kalshi_markets(kw, "open", 100))

    return markets


@st.cache_data(ttl=600, show_spinner=False)
def get_nba_prop_markets() -> list:
    """Cached wrapper for NBA prop market discovery."""
    return _get_nba_prop_markets_inner()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: load all data for a given sport day
# ─────────────────────────────────────────────────────────────────────────────

def load_nba_day(date_str: str) -> dict:
    """
    Load all NBA data for a given date string (YYYYMMDD).
    Returns dict with keys: games, espn_error, kalshi_events, prop_markets.
    All fetching happens here — zero API calls during rendering.
    """
    games, espn_err = get_espn_games(date_str, "nba")
    kalshi_events   = get_kalshi_events("KXNBAGAME")
    prop_markets    = get_nba_prop_markets()

    return {
        "games":          games,
        "espn_error":     espn_err,
        "kalshi_events":  kalshi_events,
        "prop_markets":   prop_markets,
    }


def load_cbb_day(date_str: str) -> dict:
    """
    Load all CBB data for a given date.
    Returns dict with keys: games, espn_error, kalshi_events.
    """
    games, espn_err = get_espn_games(date_str, "cbb")
    kalshi_events   = get_kalshi_events("KXCBBGAME")

    return {
        "games":         games,
        "espn_error":    espn_err,
        "kalshi_events": kalshi_events,
    }


def get_full_event_markets(event_ticker: str, nested_markets: list) -> list:
    """
    Merge nested markets (from event) with fully fetched markets for that event.
    Returns deduplicated list. Safe to call — both sources are cached.
    """
    fetched = get_kalshi_markets_for_event(event_ticker)
    merged  = {m["ticker"]: m for m in nested_markets}
    for m in fetched:
        merged[m["ticker"]] = m   # fetched overwrites nested (more complete)
    return list(merged.values())
