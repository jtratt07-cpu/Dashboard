"""
kalshi_layer.py — Kalshi-specific parsing logic.
No API calls. No model logic. No Streamlit.
Receives raw market dicts from data_layer and produces structured data.

Supported Kalshi title formats (examples):
  Game winner: "NBA: Lakers vs Warriors — Will the Lakers win?"
  Spread:      "NBA: Celtics vs Knicks — Will the Celtics win by more than 5.5 points?"
  PRA:         "NBA: Nikola Jokic — Over 28.5 Points + Rebounds + Assists"
  Points:      "NBA: Jayson Tatum — Over 30.5 Points"
  Rebounds:    "NBA: Rudy Gobert — Over 11.5 Rebounds"
  Assists:     "NBA: Tyrese Haliburton — Over 10.5 Assists"
  3PM:         "NBA: Stephen Curry — Over 4.5 3-Pointers Made"
  Blocks:      "NBA: Victor Wembanyama — Over 2.5 Blocks"
  Steals:      "NBA: Jimmy Butler — Over 1.5 Steals"

Defensive parsing: if a market cannot be reliably classified, skip it.
"""
import re
from utils import find_nba_team, team_text_match, city_of, nick_of

# ── Implied probability from a Kalshi market dict ────────────────────────────
def get_implied_prob(market: dict):
    """
    Extract implied probability from a Kalshi market.
    Prefers mid-market (bid+ask)/2; falls back to last_price.
    Returns float in [0,1] or None.
    """
    yb = market.get("yes_bid")  or 0
    ya = market.get("yes_ask")  or 0
    lp = market.get("last_price") or 0

    if yb > 0 and ya > 0:
        return round((yb + ya) / 200, 4)
    if lp > 0:
        return round(lp / 100, 4)
    return None


# ── Market type classification ────────────────────────────────────────────────
def classify_market(title: str) -> str:
    """
    Classify a Kalshi market title into one of:
      'moneyline' | 'spread' | 'total' | 'prop' | 'unknown'

    Uses specific patterns — prefers false-negative (unknown) over false-positive.
    """
    t = (title or "").lower()

    # Spread signals
    if re.search(r'win(s)?\s+by\s+more\s+than|win(s)?\s+by\s+at\s+least|\bcover\b|\bspread\b', t):
        return "spread"
    if re.search(r'[-+]\d+\.?\d*\s*points?\b', t):
        return "spread"

    # Total / combined
    if re.search(r'\btotal\s+points?\b|\bcombined\s+(score|points?)\b|\bover[/\\]under\b', t):
        return "total"

    # Player props — require both a stat keyword AND a number+
    stat_kw  = r'\b(points?\s*\+\s*rebounds?\s*\+\s*assists?|pra|points?|rebounds?|assists?|steals?|blocks?|3-pointers?|3\s*pointers?|threes?\s+made|3pm)\b'
    over_kw  = r'\b(over|under)\b'
    line_kw  = r'\d+\.?\d*\s*\+'   # e.g. "28.5+"  or "28+"
    line_kw2 = r'\b(over|under)\s+\d+\.?\d*\b'

    if re.search(stat_kw, t) and (re.search(line_kw, t) or re.search(line_kw2, t)):
        return "prop"

    # Moneyline signals — old format: "Will the X win?", new format: "X at Y Winner?"
    if re.search(r'\bwill\s+the\b.*\bwin\b|\bmoneyline\b|\bml\b|\bwinner\b', t):
        return "moneyline"

    return "unknown"


# ── Prop market parser ────────────────────────────────────────────────────────
_STAT_PATTERNS = [
    # Order matters — check compound first
    (r'points?\s*\+\s*rebounds?\s*\+\s*assists?',   "pra"),
    (r'\bpra\b',                                     "pra"),
    (r'\b3-pointers?\s+made\b|\b3\s*pm\b|\bthrees?\s+made\b', "3pm"),
    (r'\b3-pointers?\b|\bthree-pointers?\b',         "3pm"),
    (r'\bpoints?\b',                                 "points"),
    (r'\brebounds?\b',                               "rebounds"),
    (r'\bassists?\b',                                "assists"),
    (r'\bblocks?\b',                                 "blocks"),
    (r'\bsteals?\b',                                 "steals"),
]

def parse_prop_market(title: str) -> dict | None:
    """
    Parse a Kalshi player prop market title.
    Returns dict: {player, stat_type, line, over_under, raw_title}
    Returns None if parsing fails or is ambiguous.

    Defensive: skip rather than return wrong data.
    """
    t = (title or "").strip()
    tl = t.lower()

    # ── Extract over/under direction ──────────────────────────────────────────
    if "over" in tl:
        over_under = "over"
    elif "under" in tl:
        over_under = "under"
    else:
        return None   # can't determine direction, skip

    # ── Extract numeric line ──────────────────────────────────────────────────
    # Look for patterns like "28.5+" or "Over 28.5" or "28+" at the end of segments
    line = None
    line_match = re.search(r'(?:over|under)\s+(\d+\.?\d*)', tl)
    if not line_match:
        line_match = re.search(r'(\d+\.?\d*)\s*\+\s*(?:points?|rebounds?|assists?|pra)', tl)
    if not line_match:
        line_match = re.search(r'(\d+\.?\d*)\+', tl)
    if line_match:
        try:
            line = float(line_match.group(1))
        except ValueError:
            return None
    else:
        return None   # no numeric line found

    # ── Extract stat type ─────────────────────────────────────────────────────
    stat_type = None
    for pattern, stype in _STAT_PATTERNS:
        if re.search(pattern, tl):
            stat_type = stype
            break

    if stat_type is None:
        return None   # can't classify stat type

    # ── Extract player name ───────────────────────────────────────────────────
    # Kalshi format: "NBA: <Player Name> — Over X <Stat>"
    # or:            "NBA: <Player Name> Over X <Stat>"
    # Try dash separator first
    player = None
    dash_match = re.match(
        r'^[A-Z]{2,4}[:\s]+(.+?)(?:\s*[—–-]{1,2}\s*)(?:over|under)',
        t, re.IGNORECASE
    )
    if dash_match:
        player = dash_match.group(1).strip()

    if not player:
        # Try "NBA: Player Name Over X"
        colon_match = re.match(
            r'^[A-Z]{2,4}[:\s]+(.+?)\s+(?:over|under)\s+\d',
            t, re.IGNORECASE
        )
        if colon_match:
            raw = colon_match.group(1).strip()
            # Remove trailing vs/@ game info
            raw = re.split(r'\s+(?:vs\.?|@)\s+', raw)[0].strip()
            player = raw if raw else None

    if not player or len(player) < 3:
        return None   # couldn't extract player name

    # Sanity: player name should look like a name (no digits, reasonable length)
    if re.search(r'\d', player) or len(player) > 40:
        return None

    return {
        "player":     player,
        "stat_type":  stat_type,
        "line":       line,
        "over_under": over_under,
        "raw_title":  t,
    }


# ── Game market parser ────────────────────────────────────────────────────────
def parse_game_moneyline(market: dict, home: str, away: str) -> dict | None:
    """
    Extract which team's moneyline a market represents.
    Returns {team, is_home} or None.

    New Kalshi format: title="Away at Home Winner?", yes_sub_title="Team Name"
    Old Kalshi format: title="NBA: X vs Y — Will the X win?"
    """
    # New format: yes_sub_title contains only the specific team for this market
    subtitle = (market.get("yes_sub_title") or "").strip()
    team = find_nba_team(subtitle) if subtitle else None

    # Old format / fallback: try ticker suffix (e.g. KXNBAGAME-26MAR09PHICLE-CLE → "CLE")
    if not team:
        ticker = market.get("ticker", "")
        parts = ticker.rsplit("-", 1)
        if len(parts) == 2 and len(parts[1]) <= 4:
            from utils import ESPN_MAP
            team_full = ESPN_MAP.get(parts[1])
            if team_full:
                team = team_full

    # Last resort: scan full title (old format)
    if not team:
        team = find_nba_team(market.get("title", ""))

    if not team:
        return None
    is_home = (team == home)
    return {"team": team, "is_home": is_home}


def parse_game_spread(market: dict, home: str, away: str) -> dict | None:
    """
    Extract team and spread line from a spread market.
    Returns {team, line, is_home} or None.
    """
    subtitle = (market.get("yes_sub_title") or "").strip()
    team = find_nba_team(subtitle) if subtitle else None
    if not team:
        team = find_nba_team(market.get("title", ""))

    title = market.get("title", "") + " " + subtitle
    tl = title.lower()

    if not team:
        return None

    nums = re.findall(r'\d+\.?\d*', title)
    if not nums:
        return None
    try:
        line = float(nums[-1])
    except ValueError:
        return None

    is_home = (team == home)
    return {"team": team, "line": line, "is_home": is_home}


# ── Kalshi event → ESPN game matching ────────────────────────────────────────
def match_game_to_event(game: dict, kalshi_events: list) -> str | None:
    """
    Find the best-matching Kalshi event_ticker for an ESPN game.
    Requires both teams to match (score = 4). Returns ticker or None.
    """
    home = game.get("home")
    away = game.get("away")
    if not home or not away:
        return None

    best_tk    = None
    best_score = 0

    for ev in kalshi_events:
        title = ev.get("title", "")
        h = team_text_match(home, title)
        a = team_text_match(away, title)
        score = (2 if h else 0) + (2 if a else 0)
        if score > best_score:
            best_score = score
            best_tk    = ev.get("event_ticker")

    # Require both teams matched
    return best_tk if best_score >= 4 else None


# ── Prop market discovery from a list of raw market dicts ────────────────────
def discover_prop_markets(raw_markets: list) -> list:
    """
    Filter and parse a list of raw Kalshi market dicts for player props.
    Returns list of dicts: {player, stat_type, line, over_under, kalshi_prob,
                             raw_title, ticker, market_dict}
    Skips markets that cannot be parsed reliably.
    """
    results = []
    seen_keys = set()

    for m in raw_markets:
        title = m.get("title", "")
        if classify_market(title) != "prop":
            continue

        parsed = parse_prop_market(title)
        if parsed is None:
            continue

        kp = get_implied_prob(m)
        if kp is None:
            continue   # no price — skip

        # Deduplicate by player + stat + line
        dedup_key = f"{parsed['player'].lower()}_{parsed['stat_type']}_{parsed['line']}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        results.append({
            **parsed,
            "kalshi_prob":  kp,
            "ticker":       m.get("ticker", ""),
            "market_dict":  m,
        })

    return results


# ── Game market breakdown for a matched event ─────────────────────────────────
def categorize_game_markets(markets: list, home: str, away: str) -> dict:
    """
    Given a list of raw Kalshi market dicts and the two team names,
    categorize them into moneyline, spread, total, and prop buckets.
    Returns dict: {moneyline: [...], spread: [...], total: [...], prop: [...]}
    Each entry has: {label, kalshi_prob, market_type, ...extra}
    """
    result = {"moneyline": [], "spread": [], "total": [], "prop": []}
    seen   = set()

    for m in markets:
        title = m.get("title", "")
        key   = title.lower().strip()
        if key in seen:
            continue
        seen.add(key)

        kp   = get_implied_prob(m)
        mtype = classify_market(title)
        label = (m.get("yes_sub_title") or title)[:65]

        base = {"label": label, "kalshi_prob": kp, "raw_title": title, "market_dict": m}

        if mtype == "moneyline":
            parsed = parse_game_moneyline(m, home, away)
            result["moneyline"].append({**base, "team_info": parsed})

        elif mtype == "spread":
            parsed = parse_game_spread(m, home, away)
            result["spread"].append({**base, "spread_info": parsed})

        elif mtype == "total":
            result["total"].append(base)

        elif mtype == "prop" and kp is not None:
            parsed_prop = parse_prop_market(title)
            if parsed_prop:
                result["prop"].append({**base, "prop_info": parsed_prop})

    return result
