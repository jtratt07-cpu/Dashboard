"""
model_layer.py — All prediction logic.
No API calls. No Streamlit. No UI code.

Exports:
  NBA_GAME_PRESETS, CBB_GAME_PRESETS, PROP_PRESETS
  nba_game_model(home, away, weights) -> ModelResult
  cbb_game_model(home, away, weights) -> ModelResult
  prop_model(player_stats, stat_type, line, weights) -> PropResult
  calculate_edge(model_prob, kalshi_prob) -> float
  calculate_pick_quality(edge_pct, stat_type, model_prob, ...) -> int
  get_game_reasoning(result, home, away) -> list[str]
  get_prop_reasoning(result, player_name) -> list[str]
  normalize_weights(weights) -> dict
"""
import math
from utils import (
    NBA_NET_RATINGS, CBB_TEAM_STATS, CBB_SEED_HISTORY, EDGE_THRESHOLDS,
    normalize_weights, find_cbb_team,
)

# ─────────────────────────────────────────────────────────────────────────────
# Pick Quality Score (PQS) — 0 to 100
# ─────────────────────────────────────────────────────────────────────────────
"""
PQS is a composite score that measures how trustworthy a pick is beyond raw edge.
Not all edges are created equal: a +6% edge on a stable PRA pick is very different
from a +6% edge on a volatile blocks prop.

Components:
  Edge Strength  (40%): How much the edge exceeds the minimum threshold for this pick type.
                         Scales from 0 (at threshold) to 100 (at 2× threshold).
  Confidence     (25%): Distance of model probability from 50/50.
                         70% model prob → higher confidence than 55%.
  Stat Stability (20%): Inherent stability of the stat type.
                         PRA is very stable; blocks/steals are volatile.
  Market Quality (15%): Reliability of the Kalshi price.
                         Tight bid-ask = high quality; last price only = lower quality.

Interpretation:
  75-100: Strong pick — show prominently
  55-74:  Good pick — show in default mode
  35-54:  Marginal — advanced mode only
  < 35:   Weak — suppress entirely
"""

# Inherent volatility / stability by stat type (0=volatile, 100=stable)
_STAT_STABILITY = {
    "game":     78,
    "pra":      82,
    "points":   72,
    "rebounds": 68,
    "assists":  68,
    "3pm":      48,
    "blocks":   38,
    "steals":   38,
}

def calculate_pick_quality(
    edge_pct:        float,
    stat_type:       str,
    model_prob:      float,
    market_quality:  float = 1.0,   # 0.5–1.0; 1.0 = bid-ask available, 0.7 = last price only
) -> int:
    """
    Returns Pick Quality Score 0–100.
    edge_pct:       raw edge percentage (e.g., 8.4)
    stat_type:      one of game/pra/points/rebounds/assists/3pm/blocks/steals
    model_prob:     model's predicted probability (0–1)
    market_quality: 1.0 if bid+ask available, 0.7 if last_price only
    """
    threshold = EDGE_THRESHOLDS.get(stat_type, 6.0)

    # Edge score: 0 at threshold, 100 at 2× threshold
    raw_edge_score = ((edge_pct - threshold) / threshold) * 100
    edge_score = max(0.0, min(100.0, raw_edge_score))

    # Confidence: distance from 50% → 0 to 100
    confidence_score = min(100.0, abs(model_prob - 0.5) * 200)

    # Stability: hardcoded by stat type
    stability_score = float(_STAT_STABILITY.get(stat_type, 60))

    # Market quality: 0–100
    market_score = min(100.0, max(0.0, market_quality * 100))

    pqs = (
        0.40 * edge_score +
        0.25 * confidence_score +
        0.20 * stability_score +
        0.15 * market_score
    )
    return round(max(0, min(100, pqs)))


def pqs_label(pqs: int) -> tuple:
    """Returns (label, color_class) for a PQS score."""
    if pqs >= 75:
        return "Strong", "green"
    if pqs >= 55:
        return "Good", "yellow"
    if pqs >= 35:
        return "Marginal", "grey"
    return "Weak", "red"


# ─────────────────────────────────────────────────────────────────────────────
# Model Presets
# ─────────────────────────────────────────────────────────────────────────────
"""
Each preset is a dict of signal weights.
normalize_weights() is called before use so they don't need to sum to 1.

Preset philosophy:
  Recommended  — balanced, emphasizes proven efficiency metrics
  Aggressive   — amplifies recent form and matchup signals
  Conservative — leans heavily on season-long stability metrics only
  Custom       — user-editable in Advanced Mode
"""

NBA_GAME_PRESETS = {
    "recommended": {
        "net_rating":    0.50,   # most predictive single signal
        "home_court":    0.20,   # home court advantage (~2.5 pts)
        "pace":          0.10,   # pace of play interaction
        "fatigue":       0.10,   # back-to-back penalty
        "recent_form":   0.10,   # last 10 game net rating (not used if unavailable)
    },
    "aggressive": {
        "net_rating":    0.30,
        "home_court":    0.15,
        "pace":          0.15,
        "fatigue":       0.20,
        "recent_form":   0.20,
    },
    "conservative": {
        "net_rating":    0.70,
        "home_court":    0.20,
        "pace":          0.05,
        "fatigue":       0.03,
        "recent_form":   0.02,
    },
}

CBB_GAME_PRESETS = {
    "recommended": {
        "eff_margin":   0.35,   # KenPom-style adjusted efficiency margin
        "adj_offense":  0.20,
        "adj_defense":  0.20,
        "efg":          0.10,
        "to_rate":      0.08,
        "experience":   0.07,
    },
    "aggressive": {
        "eff_margin":   0.20,
        "adj_offense":  0.20,
        "adj_defense":  0.20,
        "efg":          0.15,
        "to_rate":      0.15,
        "experience":   0.10,
    },
    "conservative": {
        "eff_margin":   0.55,
        "adj_offense":  0.18,
        "adj_defense":  0.18,
        "efg":          0.05,
        "to_rate":      0.02,
        "experience":   0.02,
    },
}

# Prop presets — keys match stat fields in NBA_PLAYER_STATS
PROP_PRESETS = {
    "pra": {
        "recommended": {"season_avg": 0.50, "recent_avg": 0.35, "matchup_adj": 0.10, "pace_adj": 0.05},
        "aggressive":  {"season_avg": 0.20, "recent_avg": 0.55, "matchup_adj": 0.15, "pace_adj": 0.10},
        "conservative":{"season_avg": 0.70, "recent_avg": 0.20, "matchup_adj": 0.08, "pace_adj": 0.02},
    },
    "points": {
        "recommended": {"season_avg": 0.45, "recent_avg": 0.35, "matchup_adj": 0.12, "pace_adj": 0.08},
        "aggressive":  {"season_avg": 0.20, "recent_avg": 0.55, "matchup_adj": 0.15, "pace_adj": 0.10},
        "conservative":{"season_avg": 0.65, "recent_avg": 0.22, "matchup_adj": 0.10, "pace_adj": 0.03},
    },
    "rebounds": {
        "recommended": {"season_avg": 0.55, "recent_avg": 0.30, "matchup_adj": 0.10, "pace_adj": 0.05},
        "aggressive":  {"season_avg": 0.25, "recent_avg": 0.55, "matchup_adj": 0.12, "pace_adj": 0.08},
        "conservative":{"season_avg": 0.70, "recent_avg": 0.20, "matchup_adj": 0.08, "pace_adj": 0.02},
    },
    "assists": {
        "recommended": {"season_avg": 0.50, "recent_avg": 0.30, "matchup_adj": 0.12, "pace_adj": 0.08},
        "aggressive":  {"season_avg": 0.25, "recent_avg": 0.50, "matchup_adj": 0.15, "pace_adj": 0.10},
        "conservative":{"season_avg": 0.68, "recent_avg": 0.22, "matchup_adj": 0.08, "pace_adj": 0.02},
    },
    "3pm": {
        "recommended": {"season_avg": 0.40, "recent_avg": 0.40, "matchup_adj": 0.12, "pace_adj": 0.08},
        "aggressive":  {"season_avg": 0.20, "recent_avg": 0.60, "matchup_adj": 0.12, "pace_adj": 0.08},
        "conservative":{"season_avg": 0.60, "recent_avg": 0.25, "matchup_adj": 0.10, "pace_adj": 0.05},
    },
    "blocks": {
        "recommended": {"season_avg": 0.55, "recent_avg": 0.25, "matchup_adj": 0.12, "pace_adj": 0.08},
        "aggressive":  {"season_avg": 0.30, "recent_avg": 0.50, "matchup_adj": 0.12, "pace_adj": 0.08},
        "conservative":{"season_avg": 0.72, "recent_avg": 0.18, "matchup_adj": 0.07, "pace_adj": 0.03},
    },
    "steals": {
        "recommended": {"season_avg": 0.55, "recent_avg": 0.25, "matchup_adj": 0.12, "pace_adj": 0.08},
        "aggressive":  {"season_avg": 0.30, "recent_avg": 0.50, "matchup_adj": 0.12, "pace_adj": 0.08},
        "conservative":{"season_avg": 0.72, "recent_avg": 0.18, "matchup_adj": 0.07, "pace_adj": 0.03},
    },
}


def get_preset_weights(model_type: str, preset_name: str, stat_type: str = "pra") -> dict:
    """
    Return the weight dict for a given model/preset combination.
    model_type: 'nba_game' | 'cbb_game' | 'prop'
    preset_name: 'recommended' | 'aggressive' | 'conservative' | 'custom'
    stat_type: for props, which stat (pra/points/rebounds/etc.)
    """
    if model_type == "nba_game":
        presets = NBA_GAME_PRESETS
    elif model_type == "cbb_game":
        presets = CBB_GAME_PRESETS
    elif model_type == "prop":
        presets = PROP_PRESETS.get(stat_type, PROP_PRESETS["pra"])
    else:
        presets = NBA_GAME_PRESETS

    return dict(presets.get(preset_name, presets.get("recommended", {})))


# ─────────────────────────────────────────────────────────────────────────────
# Math helpers
# ─────────────────────────────────────────────────────────────────────────────
def _normal_cdf(x):
    """Standard normal CDF using math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _win_prob_from_z(z):
    """Convert a z-score to a win probability via normal CDF."""
    return _normal_cdf(z)

def calculate_edge(model_prob: float | None, kalshi_prob: float | None) -> float | None:
    """Return edge in percentage points (model_prob - kalshi_prob) * 100, or None."""
    if model_prob is None or kalshi_prob is None:
        return None
    return round((model_prob - kalshi_prob) * 100, 2)


# ─────────────────────────────────────────────────────────────────────────────
# NBA Game Model
# ─────────────────────────────────────────────────────────────────────────────
_NBA_SPREAD_SIGMA = 11.0    # points std dev of NBA game spread
_NBA_HOME_COURT   = 2.5     # home court advantage in points

def nba_game_model(home: str, away: str, weights: dict | None = None) -> dict:
    """
    Predict NBA game outcome using net ratings + home court.

    Returns:
      {home_prob, away_prob, expected_margin, confidence, factors, valid}
      factors: list of (signal_name, value, weight, contribution) tuples
    """
    if weights is None:
        weights = normalize_weights(NBA_GAME_PRESETS["recommended"])
    else:
        weights = normalize_weights(weights)

    hn = NBA_NET_RATINGS.get(home)
    an = NBA_NET_RATINGS.get(away)

    if hn is None or an is None:
        return {"valid": False, "home_prob": None, "away_prob": None,
                "expected_margin": None, "confidence": None, "factors": []}

    # Expected home margin (raw net rating diff + home court)
    net_diff      = hn - an
    home_court_pt = _NBA_HOME_COURT * weights.get("home_court", 0.20) / 0.20
    expected_margin = (net_diff / 2.5) + home_court_pt

    # Build factor breakdown
    factors = [
        ("Home Net Rating",    hn,      weights.get("net_rating", 0.50),  hn  * weights.get("net_rating", 0.50)),
        ("Away Net Rating",    an,      weights.get("net_rating", 0.50), -an  * weights.get("net_rating", 0.50)),
        ("Home Court",         2.5,     weights.get("home_court", 0.20),  2.5 * weights.get("home_court", 0.20)),
    ]

    # Win probability via normal distribution
    z         = expected_margin / (_NBA_SPREAD_SIGMA * math.sqrt(2))
    home_prob = _win_prob_from_z(z)
    away_prob = 1.0 - home_prob

    # Confidence = distance from 50/50
    confidence = round(abs(home_prob - 0.5) * 200, 1)   # 0–100

    return {
        "valid":            True,
        "home_prob":        round(home_prob, 4),
        "away_prob":        round(away_prob, 4),
        "expected_margin":  round(expected_margin, 1),
        "confidence":       confidence,
        "home_net":         hn,
        "away_net":         an,
        "factors":          factors,
    }


def nba_cover_prob(team: str, line: float, home: str, away: str) -> float | None:
    """Probability that `team` covers `line` points."""
    hn = NBA_NET_RATINGS.get(home)
    an = NBA_NET_RATINGS.get(away)
    if hn is None or an is None:
        return None
    margin      = (hn - an) / 2.5 + _NBA_HOME_COURT
    team_margin = margin if team == home else -margin
    adj         = team_margin - line
    z           = adj / (_NBA_SPREAD_SIGMA * math.sqrt(2))
    return round(_win_prob_from_z(z), 4)


# ─────────────────────────────────────────────────────────────────────────────
# CBB Game Model (KenPom-style)
# ─────────────────────────────────────────────────────────────────────────────
_CBB_SPREAD_SIGMA = 10.0   # CBB std dev (slightly tighter than NBA)
_CBB_HOME_COURT   = 3.5   # college home court stronger

def _score_cbb_team(stats: dict, weights: dict) -> float:
    """Composite team score 0–100 using weighted efficiency metrics."""
    em_norm  = max(0, min(1, (stats.get("eff_margin", 0) + 30) / 65))
    ao_norm  = max(0, min(1, (stats.get("adj_o", 100) - 90) / 40))
    ad_norm  = max(0, min(1, 1 - (stats.get("adj_d", 105) - 85) / 35))
    efg_norm = max(0, min(1, (stats.get("efg", 0.50) - 0.42) / 0.18))
    to_norm  = max(0, min(1, 1 - (stats.get("to_rate", 0.18) - 0.12) / 0.12))
    exp_norm = max(0, min(1, stats.get("exp", 0.70)))

    w = weights
    score = (
        w.get("eff_margin",  0.35) * em_norm  +
        w.get("adj_offense", 0.20) * ao_norm  +
        w.get("adj_defense", 0.20) * ad_norm  +
        w.get("efg",         0.10) * efg_norm +
        w.get("to_rate",     0.08) * to_norm  +
        w.get("experience",  0.07) * exp_norm
    ) * 100
    return round(score, 1)


def cbb_game_model(home: str, away: str, weights: dict | None = None) -> dict:
    """
    Predict CBB game outcome using KenPom-style efficiency ratings.

    Returns:
      {home_prob, away_prob, expected_margin, confidence, factors,
       home_score, away_score, gap, upset_context, valid}
    """
    if weights is None:
        weights = normalize_weights(CBB_GAME_PRESETS["recommended"])
    else:
        weights = normalize_weights(weights)

    home_key, home_stats = find_cbb_team(home)
    away_key, away_stats = find_cbb_team(away)

    home_score = _score_cbb_team(home_stats, weights)
    away_score = _score_cbb_team(away_stats, weights)
    gap        = round(home_score - away_score, 1)

    # Expected margin: ~3.5 composite pts ≈ 1 real point spread
    raw_margin       = gap / 3.5
    expected_margin  = raw_margin + _CBB_HOME_COURT

    z         = expected_margin / (_CBB_SPREAD_SIGMA * math.sqrt(2))
    home_prob = _win_prob_from_z(z)
    away_prob = 1.0 - home_prob
    confidence = round(abs(home_prob - 0.5) * 200, 1)

    # Upset context
    h_seed = home_stats.get("seed")
    a_seed = away_stats.get("seed")
    upset_ctx = {}
    if h_seed and a_seed:
        key = (min(h_seed, a_seed), max(h_seed, a_seed))
        upset_ctx = CBB_SEED_HISTORY.get(key, {})

    factors = [
        ("Home Eff Margin",  home_stats.get("eff_margin", 0), weights.get("eff_margin", 0.35), None),
        ("Away Eff Margin",  away_stats.get("eff_margin", 0), weights.get("eff_margin", 0.35), None),
        ("Home Composite",   home_score, 1.0, None),
        ("Away Composite",   away_score, 1.0, None),
    ]

    return {
        "valid":           True,
        "home_prob":       round(home_prob, 4),
        "away_prob":       round(away_prob, 4),
        "expected_margin": round(expected_margin, 1),
        "confidence":      confidence,
        "home_score":      home_score,
        "away_score":      away_score,
        "gap":             gap,
        "home_key":        home_key,
        "away_key":        away_key,
        "home_stats":      home_stats,
        "away_stats":      away_stats,
        "upset_context":   upset_ctx,
        "factors":         factors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Player Prop Model
# ─────────────────────────────────────────────────────────────────────────────
# Stat sigma (typical game-to-game std dev) — used in probability calculations
_PROP_SIGMA = {
    "pra":      8.5,
    "points":   6.5,
    "rebounds": 3.5,
    "assists":  2.5,
    "3pm":      1.8,
    "blocks":   1.2,
    "steals":   0.9,
}

# Avg field keys in NBA_PLAYER_STATS
_SEASON_AVG_KEY = {"pra":"pra","points":"pts","rebounds":"reb","assists":"ast",
                   "3pm":"3pm","blocks":"blk","steals":"stl"}
_L5_AVG_KEY     = {"pra":"pra_l5","points":"pts_l5","rebounds":"reb_l5","assists":"ast_l5",
                   "3pm":"3pm","blocks":"blk","steals":"stl"}

def prop_model(
    player_stats: dict,
    stat_type:    str,
    line:         float,
    weights:      dict | None = None,
) -> dict:
    """
    Predict probability that a player goes OVER a given line.

    player_stats: dict from NBA_PLAYER_STATS (via find_nba_player)
    stat_type:    pra | points | rebounds | assists | 3pm | blocks | steals
    line:         Kalshi threshold (e.g., 28.5)
    weights:      prop weight dict; defaults to PROP_PRESETS[stat_type]['recommended']

    Returns:
      {over_prob, under_prob, projection, sigma, confidence, factors, valid}
    """
    if weights is None:
        preset_group = PROP_PRESETS.get(stat_type, PROP_PRESETS["pra"])
        weights = normalize_weights(preset_group.get("recommended", {}))
    else:
        weights = normalize_weights(weights)

    s_key  = _SEASON_AVG_KEY.get(stat_type, "pra")
    l5_key = _L5_AVG_KEY.get(stat_type, "pra_l5")

    season_avg = player_stats.get(s_key)
    recent_avg = player_stats.get(l5_key)

    if season_avg is None:
        return {"valid": False, "over_prob": None, "under_prob": None,
                "projection": None, "sigma": None, "confidence": None, "factors": []}

    if recent_avg is None:
        recent_avg = season_avg   # fallback

    w_season  = weights.get("season_avg",  0.50)
    w_recent  = weights.get("recent_avg",  0.35)
    w_matchup = weights.get("matchup_adj", 0.10)
    w_pace    = weights.get("pace_adj",    0.05)

    # Projection: weighted blend of season and recent averages
    # matchup_adj and pace_adj are currently neutral (future: pull opponent defense rank)
    projection = (
        w_season  * season_avg +
        w_recent  * recent_avg +
        w_matchup * season_avg +   # placeholder — neutral matchup
        w_pace    * season_avg     # placeholder — neutral pace
    )

    sigma = _PROP_SIGMA.get(stat_type, 5.0)

    # P(actual > line) using normal distribution
    z         = (projection - line) / sigma
    over_prob = _win_prob_from_z(z)
    under_prob = 1.0 - over_prob

    # Stability: how consistent is projection vs season avg?
    stability = 1.0 - min(1.0, abs(recent_avg - season_avg) / max(season_avg, 1))

    confidence = round(abs(over_prob - 0.5) * 200, 1)

    factors = [
        ("Season Average",  season_avg,  w_season,  round(w_season * season_avg, 2)),
        ("Last-5 Average",  recent_avg,  w_recent,  round(w_recent * recent_avg, 2)),
        ("Projection",      round(projection, 1), 1.0, None),
        ("Kalshi Line",     line,        0,   None),
        ("Stability",       round(stability * 100, 1), 0, None),
        ("Minutes (avg)",   player_stats.get("min", "N/A"), 0, None),
        ("Usage Rate",      player_stats.get("usage", "N/A"), 0, None),
    ]

    return {
        "valid":      True,
        "over_prob":  round(over_prob, 4),
        "under_prob": round(under_prob, 4),
        "projection": round(projection, 1),
        "sigma":      sigma,
        "confidence": confidence,
        "stability":  round(stability, 3),
        "season_avg": season_avg,
        "recent_avg": recent_avg,
        "factors":    factors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Reasoning Bullet Generator
# ─────────────────────────────────────────────────────────────────────────────
def get_game_reasoning(result: dict, home: str, away: str, kalshi_prob: float | None = None) -> list:
    """Generate 2-3 reasoning bullets for an NBA moneyline pick."""
    bullets = []
    hn  = result.get("home_net", 0)
    an  = result.get("away_net", 0)
    home_nick = home.split()[-1]
    away_nick = away.split()[-1]

    # Bullet 1: Actual net rating numbers — concrete, not just the gap
    if hn >= an:
        bullets.append(
            f"{home_nick} net rating {hn:+.1f} vs {away_nick} {an:+.1f} "
            f"({abs(hn - an):.1f} pt gap)"
        )
    else:
        bullets.append(
            f"{away_nick} net rating {an:+.1f} vs {home_nick} {hn:+.1f} "
            f"({abs(hn - an):.1f} pt gap)"
        )

    # Bullet 2: Model projected margin
    margin = result.get("expected_margin")
    if margin is not None:
        dir_team = home_nick if margin > 0 else away_nick
        bullets.append(f"Model projects {dir_team} by {abs(margin):.1f} pts (includes home court)")

    # Bullet 3: Why market is mispriced
    if kalshi_prob is not None:
        model_prob = result.get("home_prob") or result.get("away_prob")
        if model_prob:
            pick_nick = away_nick if model_prob == result.get("away_prob") else home_nick
            edge = round((model_prob - kalshi_prob) * 100, 0)
            bullets.append(
                f"Market prices {pick_nick} at {kalshi_prob*100:.0f}% — "
                f"net ratings imply {model_prob*100:.0f}% ({edge:+.0f}% gap)"
            )

    return bullets[:3]


def get_spread_reasoning(
    result: dict, home: str, away: str,
    team: str, line: float, model_p: float,
    kalshi_prob: float | None = None,
) -> list:
    """Generate reasoning bullets for a spread pick."""
    bullets = []
    hn = result.get("home_net", 0)
    an = result.get("away_net", 0)
    home_nick = home.split()[-1]
    away_nick = away.split()[-1]
    team_nick = team.split()[-1]

    # Bullet 1: Model margin vs line — core of the value case
    margin = result.get("expected_margin")
    if margin is not None:
        team_margin = margin if team == home else -margin
        cover_by = team_margin - line
        if cover_by > 0:
            bullets.append(
                f"Model margin: {team_nick} {team_margin:+.1f} pts — "
                f"covers {line:+.1f} by {cover_by:.1f} pts in expectation"
            )
        else:
            bullets.append(
                f"Model margin: {team_nick} {team_margin:+.1f} pts vs line {line:+.1f} — "
                f"still a value play vs market price"
            )

    # Bullet 2: Raw net ratings
    if hn >= an:
        bullets.append(f"{home_nick} net rating {hn:+.1f} vs {away_nick} {an:+.1f}")
    else:
        bullets.append(f"{away_nick} net rating {an:+.1f} vs {home_nick} {hn:+.1f}")

    # Bullet 3: Market mispricing
    if kalshi_prob is not None:
        edge = round((model_p - kalshi_prob) * 100, 0)
        bullets.append(
            f"Market prices cover at {kalshi_prob*100:.0f}% — "
            f"model says {model_p*100:.0f}% ({edge:+.0f}% gap)"
        )

    return bullets[:3]


def get_cbb_reasoning(result: dict, home: str, away: str, kalshi_prob: float | None = None) -> list:
    """Generate 2-3 reasoning bullets for a CBB game pick."""
    bullets = []
    home_score = result.get("home_score", 0)
    away_score = result.get("away_score", 0)
    gap        = result.get("gap", 0)
    upset_ctx  = result.get("upset_context", {})

    home_nick = home.split()[-1]
    away_nick = away.split()[-1]

    if abs(gap) >= 5:
        favored = home_nick if gap > 0 else away_nick
        bullets.append(f"Rating model strongly favors {favored} ({abs(gap):.0f}-point composite advantage)")

    home_stats = result.get("home_stats", {})
    away_stats = result.get("away_stats", {})
    em_diff = round(home_stats.get("eff_margin", 0) - away_stats.get("eff_margin", 0), 1)
    if abs(em_diff) >= 3:
        better = home_nick if em_diff > 0 else away_nick
        bullets.append(f"{better} is rated {abs(em_diff):.1f} pts better overall by efficiency metrics")

    if upset_ctx.get("upset_rate") and upset_ctx["upset_rate"] >= 0.30:
        bullets.append(f"Historical upset rate for this seed matchup: {upset_ctx['upset_rate']:.0%} — {upset_ctx.get('note', '')}")
    elif kalshi_prob:
        model_prob = result.get("home_prob", 0.5)
        bullets.append(f"Market prices at {kalshi_prob*100:.0f}% — our model says {model_prob*100:.0f}%")

    return bullets[:3]


def get_prop_reasoning(result: dict, player_name: str, stat_type: str,
                       line: float, over_under: str, kalshi_prob: float | None = None) -> list:
    """Generate 2-3 reasoning bullets for a player prop pick."""
    bullets = []
    proj   = result.get("projection")
    s_avg  = result.get("season_avg")
    r_avg  = result.get("recent_avg")
    ovrprb = result.get("over_prob")
    stab   = result.get("stability", 1.0)

    stat_labels = {
        "pra":      "PRA",
        "points":   "Points",
        "rebounds": "Rebounds",
        "assists":  "Assists",
        "3pm":      "3PM",
        "blocks":   "Blocks",
        "steals":   "Steals",
    }
    stat_lbl = stat_labels.get(stat_type, stat_type.upper())

    if proj is not None:
        direction = "Over" if over_under == "over" else "Under"
        bullets.append(f"Our projection: {proj:.1f} {stat_lbl}  ·  Bet line: {line} ({direction})")

    if s_avg is not None and r_avg is not None:
        trend = "trending up" if r_avg > s_avg + 0.5 else ("trending down" if r_avg < s_avg - 0.5 else "consistent")
        bullets.append(f"Season avg {s_avg:.1f}  ·  Last-5 avg {r_avg:.1f}  ·  {trend}")

    if kalshi_prob is not None and ovrprb is not None:
        model_side = ovrprb if over_under == "over" else (1 - ovrprb)
        stab_note = " (volatile stat — higher bar applied)" if stab < 0.7 else ""
        bullets.append(f"Market says {kalshi_prob*100:.0f}% — our model says {model_side*100:.0f}%{stab_note}")

    return bullets[:3]


# ─────────────────────────────────────────────────────────────────────────────
# Kelly Criterion + Expected Value (functional, not cosmetic)
# ─────────────────────────────────────────────────────────────────────────────
def kelly_criterion(
    model_prob:     float,
    kalshi_prob:    float,
    kelly_fraction: float = 0.5,
) -> float | None:
    """
    Half-Kelly bet sizing as % of bankroll.
    formula: [(b·p − q) / b] × kelly_fraction
    where b = decimal odds − 1 = (1/kalshi_prob) − 1,  p = model_prob,  q = 1 − p.
    Returns None if edge is zero or negative (no bet).
    Default kelly_fraction=0.5 (half-Kelly) for risk management.
    """
    if not model_prob or not kalshi_prob or kalshi_prob <= 0 or kalshi_prob >= 1:
        return None
    b = (1.0 / kalshi_prob) - 1.0   # decimal odds − 1
    p = model_prob
    q = 1.0 - p
    kelly_raw = (b * p - q) / b
    if kelly_raw <= 0:
        return None                  # negative Kelly = no positive edge, no bet
    return round(kelly_raw * kelly_fraction * 100, 1)   # expressed as % of bankroll


def expected_value_pct(
    model_prob:  float,
    kalshi_prob: float,
) -> float | None:
    """
    Expected value as % of stake.
    EV% = [p × (payout − 1) − q] × 100
    payout = decimal odds = 1 / kalshi_prob.
    Positive EV means the bet has long-run value; negative means it doesn't.
    """
    if not model_prob or not kalshi_prob or kalshi_prob <= 0 or kalshi_prob >= 1:
        return None
    payout = 1.0 / kalshi_prob
    ev = model_prob * (payout - 1.0) - (1.0 - model_prob)
    return round(ev * 100, 1)   # % of stake


# ─────────────────────────────────────────────────────────────────────────────
# Pick Classification (plain-English categories)
# ─────────────────────────────────────────────────────────────────────────────
def classify_pick(edge_pct: float, model_prob: float, pqs: int) -> tuple:
    """
    Classify a pick into a plain-English category.
    Returns (label, icon, css_class).

    Categories (in priority order):
      Best Bet      — massive edge + high confidence
      Value Underdog— model backs underdog the market is sleeping on
      Good Value    — solid edge on a reliable signal
      Sharp Pick    — strong model signal with modest edge
      Spot Play     — positive edge but smaller or volatile context
    """
    # Favour-agnostic: is the model backing the underdog?
    is_underdog = model_prob < 0.48

    if edge_pct >= 12 and pqs >= 70:
        return ("Best Bet", "🎯", "cat-best-bet")
    if is_underdog and edge_pct >= 8:
        return ("Value Underdog", "🐕", "cat-underdog")
    if edge_pct >= 8 and pqs >= 55:
        return ("Good Value", "📈", "cat-good-value")
    if pqs >= 65 and edge_pct >= 5:
        return ("Sharp Pick", "⚡", "cat-sharp")
    return ("Spot Play", "💡", "cat-spot-play")


# ─────────────────────────────────────────────────────────────────────────────
# Pick validation helpers
# ─────────────────────────────────────────────────────────────────────────────
def pick_passes_threshold(edge_pct: float | None, stat_type: str) -> bool:
    """True if edge_pct meets the minimum threshold for this stat type."""
    if edge_pct is None:
        return False
    return edge_pct >= EDGE_THRESHOLDS.get(stat_type, 6.0)


def model_prob_beats_market(model_prob: float | None, kalshi_prob: float | None) -> bool:
    """True if model probability directionally exceeds market implied probability."""
    if model_prob is None or kalshi_prob is None:
        return False
    return model_prob > kalshi_prob
