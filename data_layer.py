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

        date_iso     = ev.get("date", "")
        status       = ev.get("status", {}).get("type", {}).get("description", "Scheduled")
        short_st     = ev.get("status", {}).get("type", {}).get("shortDetail", "")
        neutral_site = comp.get("neutralSite", False)
        games.append({
            "away":         away,
            "home":         home,
            "time_et":      fmt_time(date_iso),
            "status":       status,
            "short_status": short_st,
            "date_iso":     date_iso,
            "home_score":   home_score,
            "away_score":   away_score,
            "neutral_site": neutral_site,
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
    Tries known series tickers for individual over/under prop markets.
    Returns combined, deduplicated list of market dicts.
    Not directly cached — wrapping function get_nba_prop_markets is cached.

    Note: Kalshi's multi-outcome KXMVECROSSCATEGORY bundle markets have no individual
    pricing (bid/ask/last_price all 0) and cannot be used for edge calculation.
    Keyword searches return cross-category bundles and game spreads — both useless.
    Only individual over/under series are attempted here.
    """
    seen    = set()
    markets = []

    def add_batch(batch):
        for m in batch:
            tk = m.get("ticker", "")
            if tk and tk not in seen:
                seen.add(tk)
                markets.append(m)

    # Try known prop series tickers (individual over/under format)
    # KXNBAPTS/KXNBAREB/KXNBAAST use "Player: N+ stat" format (live today)
    # KXNBAPROP/KXNBA3D/KXNBAPRA use "NBA: Player — Over N Stat" format (less common)
    for series in [
        "KXNBAPTS",   # Player Points  — e.g. "Deandre Ayton: 10+ points"
        "KXNBAREB",   # Player Rebounds — e.g. "Rudy Gobert: 14+ rebounds"
        "KXNBAAST",   # Player Assists  — e.g. "LeBron James: 7+ assists"
        "KXNBA3PM",   # 3-Pointers Made (when available)
        "KXNBABLK",   # Blocks (when available)
        "KXNBASTL",   # Steals (when available)
        "KXNBAPROP",  # Legacy individual props
        "KXNBA3D",    # Legacy 3-point props
        "KXNBAPRA",   # Legacy PRA props
    ]:
        evs = get_kalshi_events(series)
        for ev in evs:
            tks = ev.get("event_ticker", ev.get("ticker", ""))
            if tks:
                add_batch(get_kalshi_markets_for_event(tks))

    return markets


@st.cache_data(ttl=600, show_spinner=False)
def get_nba_prop_markets() -> list:
    """Cached wrapper for NBA prop market discovery."""
    return _get_nba_prop_markets_inner()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: load all data for a given sport day
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def get_nba_injuries() -> dict:
    """
    Fetch NBA injury report from ESPN's public injuries endpoint.
    Returns dict: {team_display_name: [{"player", "status", "position", "detail", "side", "comment"}]}
    Status values: "Out", "Day-To-Day", "Suspension"
    Single call covers all 30 teams — fast and cacheable.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}

    result = {}
    for team_entry in data.get("injuries", []):
        team_name = team_entry.get("team", {}).get("displayName", "")
        if not team_name:
            continue
        team_inj = []
        for inj in team_entry.get("injuries", []):
            status = inj.get("status", "")
            if status not in ("Out", "Day-To-Day", "Suspension"):
                continue
            athlete = inj.get("athlete", {})
            details = inj.get("details", {})
            side    = details.get("side", "")
            team_inj.append({
                "player":   athlete.get("displayName", ""),
                "status":   status,
                "position": athlete.get("position", {}).get("abbreviation", ""),
                "detail":   details.get("type", ""),
                "side":     "" if side in ("Not Specified", "") else side,
                "comment":  inj.get("shortComment", ""),
            })
        if team_inj:
            result[team_name] = team_inj
    return result


@st.cache_data(ttl=600, show_spinner=False)
def get_nba_spread_events() -> list:
    """
    Fetch NBA alt-spread events from KXNBASPREAD series.
    Each event holds multiple markets: "Team wins by over N.N Points?"
    with live bid/ask pricing for multiple lines per team per game.
    Returns list of event dicts (same structure as get_kalshi_events).
    """
    return get_kalshi_events("KXNBASPREAD")


def load_nba_day(date_str: str) -> dict:
    """
    Load all NBA data for a given date string (YYYYMMDD).
    Returns dict with keys: games, espn_error, kalshi_events,
    spread_events, prop_markets, injuries.
    All fetching happens here — zero API calls during rendering.
    """
    games, espn_err = get_espn_games(date_str, "nba")
    kalshi_events   = get_kalshi_events("KXNBAGAME")
    spread_events   = get_nba_spread_events()
    prop_markets    = get_nba_prop_markets()
    injuries        = get_nba_injuries()

    return {
        "games":          games,
        "espn_error":     espn_err,
        "kalshi_events":  kalshi_events,
        "spread_events":  spread_events,
        "prop_markets":   prop_markets,
        "injuries":       injuries,
    }


@st.cache_data(ttl=600, show_spinner=False)
def _search_cbb_events_by_keyword() -> list:
    """
    Fallback CBB market discovery via keyword search.
    Catches any NCAA/conference tournament games that appear under an
    unexpected series ticker (Kalshi renames series occasionally).
    Returns a synthetic list of event-like dicts keyed by event_ticker.
    """
    markets = search_kalshi_markets("college basketball winner", "open", 200)
    events: dict = {}
    for m in markets:
        ev_tk = m.get("event_ticker", "")
        if not ev_tk:
            continue
        if ev_tk not in events:
            events[ev_tk] = {
                "event_ticker": ev_tk,
                "title":        m.get("title", ""),
                "markets":      [],
            }
        events[ev_tk]["markets"].append(m)
    return list(events.values())


def load_cbb_day(date_str: str) -> dict:
    """
    Load all CBB data for a given date.
    Returns dict with keys: games, espn_error, kalshi_events.

    Kalshi renamed the CBB game series from KXCBBGAME → KXNCAAMBGAME (Mar 2026).
    We fetch both + keyword search so any future renames are still caught.
    """
    games, espn_err   = get_espn_games(date_str, "cbb")
    primary_events    = get_kalshi_events("KXNCAAMBGAME")   # current series (renamed Mar 2026)
    legacy_events     = get_kalshi_events("KXCBBGAME")       # old series — keep as fallback
    keyword_events    = _search_cbb_events_by_keyword()

    # Merge all sources — deduplicate by event_ticker
    seen: set = set()
    kalshi_events: list = []
    for ev in primary_events + legacy_events + keyword_events:
        tk = ev.get("event_ticker", "")
        if tk and tk not in seen:
            seen.add(tk)
            kalshi_events.append(ev)

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
