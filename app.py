"""
app.py — Streamlit entry point.
Responsibilities: page layout, tab structure, mode switching, orchestration.
All data fetching: data_layer.py
All parsing:       kalshi_layer.py
All model logic:   model_layer.py
All rendering:     ui_layer.py
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from utils import now_et, prob_to_pct, am_odds, NBA_NET_RATINGS, EDGE_THRESHOLDS, MIN_PQS_DEFAULT, MIN_PQS_ADVANCED
from data_layer import load_nba_day, load_cbb_day, get_full_event_markets
from kalshi_layer import (
    match_game_to_event, categorize_game_markets,
    get_implied_prob, discover_prop_markets,
)
from model_layer import (
    nba_game_model, nba_cover_prob, cbb_game_model, prop_model,
    calculate_edge, calculate_pick_quality, pick_passes_threshold,
    get_game_reasoning, get_cbb_reasoning, get_prop_reasoning,
    NBA_GAME_PRESETS, CBB_GAME_PRESETS, PROP_PRESETS,
    normalize_weights, get_preset_weights,
)
from ui_layer import (
    APP_CSS, render_game_pick_card, render_prop_pick_card,
    render_market_section, render_score_row, render_no_picks,
    render_nba_net_ratings, render_cbb_ratings, render_player_stats_table,
    render_model_editor, build_market_table,
)

# ── Inline helpers (avoids import-cache issues on Streamlit Cloud) ─────────
def render_model_game_row(game: dict, result: dict, sport: str = "NBA") -> None:
    """Compact model-only row when Kalshi markets are unavailable."""
    home = game.get("home", "?")
    away = game.get("away", "?")
    home_nick = home.split()[-1]
    away_nick = away.split()[-1]
    hp = result.get("home_prob", 0.5)
    ap = result.get("away_prob", 0.5)
    margin = result.get("expected_margin")
    time_et = game.get("time_et", "")
    if margin and abs(margin) > 0.5:
        fav = home_nick if margin > 0 else away_nick
        margin_str = f"&nbsp;·&nbsp; Model favors **{fav}** by {abs(margin):.1f} pts"
    else:
        margin_str = ""
    st.markdown(
        f"**{away_nick} @ {home_nick}** &nbsp;`{time_et}`&nbsp;·&nbsp;"
        f"{home_nick}: **{hp*100:.0f}%** &nbsp;/&nbsp; {away_nick}: **{ap*100:.0f}%**"
        f"{margin_str}",
        unsafe_allow_html=True,
    )

def render_player_projections_table(games: list) -> None:
    """Show season-average projections for players on tonight's NBA teams."""
    from utils import NBA_PLAYER_STATS
    tonight_teams: set = set()
    for g in games:
        if g.get("home"): tonight_teams.add(g["home"])
        if g.get("away"): tonight_teams.add(g["away"])
    rows = []
    for name, s in NBA_PLAYER_STATS.items():
        if s.get("team", "") not in tonight_teams:
            continue
        rows.append({
            "Player": name, "Team": s.get("team","").split()[-1],
            "PRA": s.get("pra","—"), "Points": s.get("pts","—"),
            "Rebounds": s.get("reb","—"), "Assists": s.get("ast","—"),
            "3-Pointers": s.get("3pm","—"),
        })
    if not rows:
        st.caption("No player data available for tonight's teams.")
        return
    df = pd.DataFrame(rows).sort_values("PRA", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)
from utils import find_nba_player

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betting Dashboard",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "advanced_mode":      False,
        "sport":              "NBA",
        "min_edge":           5.0,
        "min_pqs":            MIN_PQS_DEFAULT,
        "nba_preset":         "recommended",
        "cbb_preset":         "recommended",
        "prop_preset":        "recommended",
        "show_totals":        False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ─────────────────────────────────────────────────────────────────────────────
# ET clock
# ─────────────────────────────────────────────────────────────────────────────
et_now   = now_et()
date_str = et_now.strftime("%Y%m%d")

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 🏀 Dashboard  ·  {et_now.strftime('%b %-d')}")
    st.caption(f"{et_now.strftime('%-I:%M %p')} ET")
    st.divider()

    # Sport selector
    sport = st.radio("Sport", ["NBA", "CBB"], horizontal=True,
                     key="sport_radio")
    st.session_state["sport"] = sport

    # Date picker (allow browsing past dates)
    sel_date = st.date_input(
        "Date",
        value=et_now.date(),
        min_value=et_now.date() - timedelta(days=7),
        max_value=et_now.date() + timedelta(days=2),
        key="date_picker",
    )
    date_str = sel_date.strftime("%Y%m%d")

    st.divider()

    # Mode toggle
    st.session_state["advanced_mode"] = st.toggle(
        "Advanced Mode",
        value=st.session_state["advanced_mode"],
        help="Show full stats, model weights, and lower-confidence picks.",
    )
    advanced = st.session_state["advanced_mode"]

    st.divider()

    # Filters (always visible)
    st.markdown("**Filters**")
    min_edge = st.slider("Min edge (%)", 0, 20, int(st.session_state["min_edge"]),
                         key="min_edge_slider")
    st.session_state["min_edge"] = float(min_edge)

    min_pqs = st.slider(
        "Confidence Filter",
        0, 100,
        MIN_PQS_ADVANCED if advanced else MIN_PQS_DEFAULT,
        key="min_pqs_slider",
        help="Higher = fewer but stronger picks. Default is 55 (Good or better).",
    )
    st.session_state["min_pqs"] = min_pqs

    if advanced:
        st.divider()
        st.markdown("**Model Presets**")
        if sport == "NBA":
            nba_preset = st.selectbox("NBA Game Model", ["recommended","aggressive","conservative","custom"],
                                       key="nba_preset_sel")
            st.session_state["nba_preset"] = nba_preset
        else:
            cbb_preset = st.selectbox("CBB Game Model", ["recommended","aggressive","conservative","custom"],
                                       key="cbb_preset_sel")
            st.session_state["cbb_preset"] = cbb_preset
        prop_preset = st.selectbox("Prop Model", ["recommended","aggressive","conservative","custom"],
                                    key="prop_preset_sel")
        st.session_state["prop_preset"] = prop_preset

    st.divider()
    st.caption("Data refreshes every 10 minutes.")

# ─────────────────────────────────────────────────────────────────────────────
# Data loading — ALL fetching happens here, before any tab renders
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    if sport == "NBA":
        day_data = load_nba_day(date_str)
    else:
        day_data = load_cbb_day(date_str)

games         = day_data.get("games", [])
espn_err      = day_data.get("espn_error")
kalshi_events = day_data.get("kalshi_events", [])
prop_markets  = day_data.get("prop_markets", [])   # only for NBA

# Active model weights (from session state presets)
nba_weights  = normalize_weights(get_preset_weights("nba_game", st.session_state.get("nba_preset","recommended")))
cbb_weights  = normalize_weights(get_preset_weights("cbb_game", st.session_state.get("cbb_preset","recommended")))
prop_weights = {}   # resolved per stat type below

# ─────────────────────────────────────────────────────────────────────────────
# Build picks — all model computation before rendering
# ─────────────────────────────────────────────────────────────────────────────
def _build_nba_game_picks(games, kalshi_events, weights, min_edge, min_pqs, advanced):
    """Build list of qualified NBA game picks."""
    picks = []
    seen_matchups = set()

    for game in games:
        home = game.get("home")
        away = game.get("away")
        if not home or not away:
            continue

        matchup_key = f"{away}@{home}"
        if matchup_key in seen_matchups:
            continue
        seen_matchups.add(matchup_key)

        # Get model result
        result = nba_game_model(home, away, weights)
        if not result.get("valid"):
            continue

        # Find Kalshi event and markets
        event_tk = match_game_to_event(game, kalshi_events)
        if not event_tk:
            continue

        ev = next((e for e in kalshi_events if e.get("event_ticker") == event_tk), {})
        nested = ev.get("markets", [])
        all_markets = get_full_event_markets(event_tk, nested)
        cats = categorize_game_markets(all_markets, home, away)

        # Moneyline picks
        for ml in cats["moneyline"]:
            kp = ml.get("kalshi_prob")
            if kp is None:
                continue
            ti = ml.get("team_info") or {}
            team = ti.get("team")
            if team == home:
                model_p = result["home_prob"]
            elif team == away:
                model_p = result["away_prob"]
            else:
                continue

            edge = calculate_edge(model_p, kp)
            if edge is None or edge < min_edge:
                continue

            mq = 1.0 if ml["market_dict"].get("yes_bid") else 0.7
            pqs = calculate_pick_quality(edge, "game", model_p, mq)
            if pqs < min_pqs:
                continue

            bullets = get_game_reasoning(result, home, away, kp if team == home else (1 - kp))
            picks.append({
                "sport":          "NBA",
                "home":           home,
                "away":           away,
                "time_et":        game.get("time_et", ""),
                "pick_team":      team or "",
                "pick_direction": "to win  ·  Moneyline",
                "market_type":    "moneyline",
                "model_prob":     model_p,
                "kalshi_prob":    kp,
                "edge_pct":       edge,
                "pqs":            pqs,
                "confidence":     result.get("confidence"),
                "reasoning":      bullets,
                "model_result":   result,
            })

        # Spread picks (first qualifying spread)
        for sp in cats["spread"][:3]:
            kp = sp.get("kalshi_prob")
            si = sp.get("spread_info") or {}
            team = si.get("team")
            line = si.get("line")
            if kp is None or team is None or line is None:
                continue

            model_p = nba_cover_prob(team, line, home, away)
            if model_p is None:
                continue

            edge = calculate_edge(model_p, kp)
            if edge is None or edge < min_edge:
                continue

            mq = 1.0 if sp["market_dict"].get("yes_bid") else 0.7
            pqs = calculate_pick_quality(edge, "game", model_p, mq)
            if pqs < min_pqs:
                continue

            bullets = get_game_reasoning(result, home, away)
            picks.append({
                "sport":          "NBA",
                "home":           home,
                "away":           away,
                "time_et":        game.get("time_et", ""),
                "pick_team":      team or "",
                "pick_direction": f"to cover {line:+.1f}  ·  Spread",
                "market_type":    "spread",
                "model_prob":     model_p,
                "kalshi_prob":    kp,
                "edge_pct":       edge,
                "pqs":            pqs,
                "confidence":     result.get("confidence"),
                "reasoning":      bullets,
                "model_result":   result,
            })

    # Sort: PQS descending
    return sorted(picks, key=lambda x: x["pqs"], reverse=True)


def _build_cbb_game_picks(games, kalshi_events, weights, min_edge, min_pqs):
    """Build list of qualified CBB game picks."""
    picks = []
    seen  = set()

    for game in games:
        home = game.get("home")
        away = game.get("away")
        if not home or not away:
            continue
        key = f"{away}@{home}"
        if key in seen:
            continue
        seen.add(key)

        result = cbb_game_model(home, away, weights)
        if not result.get("valid"):
            continue

        event_tk = match_game_to_event(game, kalshi_events)
        if not event_tk:
            continue

        ev = next((e for e in kalshi_events if e.get("event_ticker") == event_tk), {})
        nested = ev.get("markets", [])
        all_markets = get_full_event_markets(event_tk, nested)
        cats = categorize_game_markets(all_markets, home, away)

        for ml in cats["moneyline"]:
            kp = ml.get("kalshi_prob")
            if kp is None:
                continue
            ti = ml.get("team_info") or {}
            team = ti.get("team")
            if not team:
                continue

            if team == home:
                model_p = result["home_prob"]
            else:
                model_p = result["away_prob"]

            edge = calculate_edge(model_p, kp)
            if edge is None or edge < min_edge:
                continue

            pqs = calculate_pick_quality(edge, "game", model_p)
            if pqs < min_pqs:
                continue

            bullets = get_cbb_reasoning(result, home, away, kp if team == home else (1 - kp))
            picks.append({
                "sport":          "CBB",
                "home":           home,
                "away":           away,
                "time_et":        game.get("time_et", ""),
                "pick_team":      team,
                "pick_direction": "to win  ·  Moneyline",
                "market_type":    "moneyline",
                "model_prob":     model_p,
                "kalshi_prob":    kp,
                "edge_pct":       edge,
                "pqs":            pqs,
                "confidence":     result.get("confidence"),
                "reasoning":      bullets,
                "model_result":   result,
            })

    return sorted(picks, key=lambda x: x["pqs"], reverse=True)


def _build_prop_picks(prop_markets, min_edge, min_pqs, prop_preset):
    """Build list of qualified NBA player prop picks from Kalshi markets."""
    parsed_props = discover_prop_markets(prop_markets)
    picks = []
    stat_order = ["pra", "points", "rebounds", "assists", "3pm", "blocks", "steals"]

    for pp in parsed_props:
        player_name = pp.get("player", "")
        stat_type   = pp.get("stat_type", "pra")
        line        = pp.get("line", 0)
        over_under  = pp.get("over_under", "over")
        kp          = pp.get("kalshi_prob")

        player_stats = find_nba_player(player_name)
        if player_stats is None:
            continue   # unknown player — skip rather than guess

        w = normalize_weights(get_preset_weights("prop", prop_preset, stat_type))
        result = prop_model(player_stats, stat_type, line, w)
        if not result.get("valid"):
            continue

        # Use the probability for the predicted direction
        if over_under == "over":
            model_p = result["over_prob"]
        else:
            model_p = result["under_prob"]

        if model_p is None or kp is None:
            continue

        edge = calculate_edge(model_p, kp)
        if edge is None:
            continue

        # Check stat-specific edge threshold
        threshold = EDGE_THRESHOLDS.get(stat_type, 6.0)
        if edge < max(min_edge, threshold):
            continue

        mq  = 1.0 if pp["market_dict"].get("yes_bid") else 0.7
        pqs = calculate_pick_quality(edge, stat_type, model_p, mq)
        if pqs < min_pqs:
            continue

        bullets = get_prop_reasoning(result, player_name, stat_type, line, over_under, kp)
        picks.append({
            "player":       player_stats.get("name", player_name),
            "team":         player_stats.get("team", ""),
            "stat_type":    stat_type,
            "line":         line,
            "over_under":   over_under,
            "projection":   result.get("projection"),
            "model_prob":   model_p,
            "kalshi_prob":  kp,
            "edge_pct":     edge,
            "pqs":          pqs,
            "confidence":   result.get("confidence"),
            "reasoning":    bullets,
            "model_result": result,
            "_stat_order":  stat_order.index(stat_type) if stat_type in stat_order else 99,
        })

    # Sort: PQS desc, then by stat order (PRA first)
    return sorted(picks, key=lambda x: (-x["pqs"], x["_stat_order"]))


# ─────────────────────────────────────────────────────────────────────────────
# Compute all picks (before rendering any tab)
# ─────────────────────────────────────────────────────────────────────────────
min_edge_val = st.session_state["min_edge"]
min_pqs_val  = st.session_state["min_pqs"]
advanced     = st.session_state["advanced_mode"]

if sport == "NBA":
    game_picks = _build_nba_game_picks(
        games, kalshi_events, nba_weights,
        min_edge_val, min_pqs_val, advanced,
    )
    prop_picks = _build_prop_picks(
        prop_markets, min_edge_val, min_pqs_val,
        st.session_state.get("prop_preset", "recommended"),
    )
else:
    game_picks = _build_cbb_game_picks(
        games, kalshi_events, cbb_weights,
        min_edge_val, min_pqs_val,
    )
    prop_picks = []

# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
tabs = st.tabs(["🏆 Today", "🎯 Props", "📺 Scores", "📊 Stats", "⚙️ Settings", "📓 Tracker"])

# ────────── TAB 1: TODAY (game picks) ────────────────────────────────────────
with tabs[0]:
    sport_lbl = "NBA" if sport == "NBA" else "CBB"
    date_lbl  = sel_date.strftime("%A, %B %-d")
    st.markdown(f"### {sport_lbl} · {date_lbl}")

    if espn_err:
        st.error(f"ESPN error: {espn_err}")

    if not games:
        st.info(f"No {sport_lbl} games found on ESPN for this date.")
    elif not kalshi_events:
        # Show model-only rows — no Kalshi prices available
        st.warning("No Kalshi markets found for today — showing model projections only.")
        for game in games:
            home = game.get("home", "?")
            away = game.get("away", "?")
            if sport == "NBA":
                result = nba_game_model(home, away, nba_weights)
            else:
                result = cbb_game_model(home, away, cbb_weights)
            if result.get("valid"):
                render_model_game_row(game, result, sport)
    elif not game_picks:
        render_no_picks()

        # In advanced mode, show all games with model lines even without edge
        if advanced:
            st.markdown("---")
            st.markdown("**All games (no qualifying edge):**")
            for game in games:
                home = game.get("home", "?")
                away = game.get("away", "?")
                if sport == "NBA":
                    result = nba_game_model(home, away, nba_weights)
                else:
                    result = cbb_game_model(home, away, cbb_weights)
                if result.get("valid"):
                    ev_tk = match_game_to_event(game, kalshi_events)
                    kp_str = "—"
                    if ev_tk:
                        ev = next((e for e in kalshi_events if e.get("event_ticker") == ev_tk), {})
                        nested = ev.get("markets", [])
                        all_mkts = get_full_event_markets(ev_tk, nested)
                        cats = categorize_game_markets(all_mkts, home, away)
                        for ml in cats["moneyline"][:1]:
                            kp_v = ml.get("kalshi_prob")
                            if kp_v:
                                kp_str = f"{kp_v*100:.0f}%"
                    st.markdown(
                        f"**{away} @ {home}**  ·  {game.get('time_et','')}  |  "
                        f"Model: {result['home_prob']*100:.0f}% / {result['away_prob']*100:.0f}%  ·  "
                        f"Market (home): {kp_str}"
                    )
    else:
        st.caption(
            f"{len(game_picks)} qualifying pick{'s' if len(game_picks) != 1 else ''} for {date_lbl}"
        )
        for pick in game_picks:
            render_game_pick_card(pick, advanced=advanced)

        # Full market view (advanced)
        if advanced:
            st.markdown("---")
            st.markdown("#### All Markets by Game")
            seen_adv = set()
            for game in games:
                home = game.get("home", "?")
                away = game.get("away", "?")
                key  = f"{away}@{home}"
                if key in seen_adv:
                    continue
                seen_adv.add(key)

                ev_tk = match_game_to_event(game, kalshi_events)
                if not ev_tk:
                    continue
                ev = next((e for e in kalshi_events if e.get("event_ticker") == ev_tk), {})
                nested = ev.get("markets", [])
                all_mkts = get_full_event_markets(ev_tk, nested)
                cats = categorize_game_markets(all_mkts, home, away)

                if sport == "NBA":
                    result = nba_game_model(home, away, nba_weights)
                else:
                    result = cbb_game_model(home, away, cbb_weights)

                with st.expander(f"{away} @ {home}  ·  {game.get('time_et','')}"):
                    # Moneyline
                    ml_rows = []
                    for ml in cats["moneyline"]:
                        kp = ml.get("kalshi_prob")
                        ti = ml.get("team_info") or {}
                        team = ti.get("team")
                        if team == home:
                            mp = result.get("home_prob") if result.get("valid") else None
                        elif team == away:
                            mp = result.get("away_prob") if result.get("valid") else None
                        else:
                            mp = None
                        ml_rows.append((ml["label"], kp, mp))
                    render_market_section("Moneyline", ml_rows, 3)

                    # Spread
                    sp_rows = []
                    for sp in cats["spread"]:
                        kp = sp.get("kalshi_prob")
                        si = sp.get("spread_info") or {}
                        team = si.get("team")
                        line = si.get("line")
                        mp = None
                        if sport == "NBA" and team and line is not None:
                            mp = nba_cover_prob(team, line, home, away)
                        sp_rows.append((sp["label"], kp, mp))
                    render_market_section("Spread", sp_rows, 6)

                    # Totals
                    if st.session_state.get("show_totals", False):
                        to_rows = [(m["label"], m.get("kalshi_prob"), None) for m in cats["total"]]
                        render_market_section("Game Total", to_rows, 3)

                    st.caption(f"{len(all_mkts)} markets from Kalshi")


# ────────── TAB 2: PROPS ─────────────────────────────────────────────────────
with tabs[1]:
    st.markdown(f"### NBA Props · {sel_date.strftime('%B %-d')}")

    if sport != "NBA":
        st.info("Player props are currently available for NBA only.")
    elif not prop_markets:
        st.info("No Kalshi player prop markets available today.")
        st.markdown("#### Tonight's Player Projections")
        st.caption("Model estimates based on season averages for players in tonight's games. No market comparison available.")
        render_player_projections_table(games)
    elif not prop_picks:
        render_no_picks(
            "No props with sufficient edge today. "
            "Props require a higher edge threshold — "
            "PRA/Pts/Reb/Ast need 6%+, 3PM needs 8%+, blocks/steals need 10%+."
        )
        st.markdown("#### Tonight's Player Projections")
        st.caption("Model estimates based on season averages.")
        render_player_projections_table(games)
    else:
        stat_labels = {
            "pra":"PRA","points":"Points","rebounds":"Rebounds","assists":"Assists",
            "3pm":"3PM","blocks":"Blocks","steals":"Steals",
        }
        # Group by stat type for readability
        by_stat: dict = {}
        for p in prop_picks:
            st_key = p["stat_type"]
            by_stat.setdefault(st_key, []).append(p)

        st.caption(
            f"{len(prop_picks)} qualifying prop{'s' if len(prop_picks) != 1 else ''} for {sel_date.strftime('%B %-d')}"
        )

        for stat_key in ["pra", "points", "rebounds", "assists", "3pm", "blocks", "steals"]:
            group = by_stat.get(stat_key, [])
            if not group:
                continue
            st.markdown(f'<div class="sec">{stat_labels[stat_key]}</div>', unsafe_allow_html=True)
            for pick in group:
                render_prop_pick_card(pick, advanced=advanced)

    # In advanced mode, show all parsed markets even without edge
    if advanced and sport == "NBA" and prop_markets:
        st.markdown("---")
        with st.expander("All parsed prop markets (no edge filter)"):
            parsed = discover_prop_markets(prop_markets)
            if parsed:
                rows = []
                for pp in parsed[:50]:
                    rows.append({
                        "Player":    pp.get("player",""),
                        "Stat":      pp.get("stat_type","").upper(),
                        "Line":      pp.get("line",""),
                        "Direction": pp.get("over_under","").capitalize(),
                        "Market%":   f"{pp.get('kalshi_prob',0)*100:.0f}%",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No prop markets could be parsed from Kalshi today.")


# ────────── TAB 3: SCORES ────────────────────────────────────────────────────
with tabs[2]:
    score_lbl = "NBA" if sport == "NBA" else "CBB"
    st.markdown(f"### {score_lbl} Scores · {sel_date.strftime('%B %-d')}")

    if espn_err:
        st.error(f"ESPN error: {espn_err}")
    elif not games:
        st.info("No games found.")
    else:
        in_progress = [g for g in games if "progress" in g.get("status","").lower()
                       or "quarter" in g.get("short_status","").lower()
                       or "half" in g.get("short_status","").lower()]
        final       = [g for g in games if "final" in g.get("status","").lower()]
        sched       = [g for g in games if g not in in_progress and g not in final]

        if in_progress:
            st.markdown("**In Progress**")
            for g in in_progress:
                render_score_row(g)
            st.divider()
        if final:
            st.markdown("**Final**")
            for g in final:
                render_score_row(g)
            st.divider()
        if sched:
            st.markdown("**Upcoming**")
            for g in sched:
                render_score_row(g)


# ────────── TAB 4: STATS ─────────────────────────────────────────────────────
with tabs[3]:
    stat_tabs = st.tabs(["NBA Teams", "CBB Teams", "NBA Players"])

    with stat_tabs[0]:
        st.markdown("#### NBA Net Ratings (2025-26)")
        st.caption("Source: hardcoded estimates — update periodically from NBA.com/stats")
        render_nba_net_ratings()

    with stat_tabs[1]:
        st.markdown("#### CBB KenPom-Style Ratings (2025-26)")
        st.caption("Source: cbb_betting_model.py — update weekly from kenpom.com or barttorvik.com")
        render_cbb_ratings()

    with stat_tabs[2]:
        st.markdown("#### NBA Player Season Averages")
        st.caption("Source: hardcoded estimates — marked FRAGILE, replace with live ESPN API for production")
        render_player_stats_table()


# ────────── TAB 5: SETTINGS ──────────────────────────────────────────────────
with tabs[4]:
    st.markdown("### Settings")

    st.markdown("**Display**")
    show_totals = st.checkbox("Show game totals in advanced market view",
                              value=st.session_state.get("show_totals", False),
                              key="show_totals_chk")
    st.session_state["show_totals"] = show_totals

    st.divider()
    st.markdown("**Edge Thresholds** (read-only, defined in utils.py)")
    thresh_data = [{"Pick Type": k.upper(), "Min Edge": f"{v:.0f}%"}
                   for k, v in EDGE_THRESHOLDS.items()]
    st.dataframe(pd.DataFrame(thresh_data), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**How Picks Are Scored**")
    st.info(
        "Each pick gets a score from 0–100 based on how trustworthy it is — not just raw edge. "
        "A big edge on a volatile stat like blocks is worth less than the same edge on a stable stat like PRA.\n\n"
        "**What goes into the score:**\n"
        "- **Edge strength (40%):** How far the model disagrees with the market\n"
        "- **Conviction (25%):** How confident the model is (far from 50/50)\n"
        "- **Stat stability (20%):** How predictable the stat type is (PRA is most stable, blocks least)\n"
        "- **Market quality (15%):** How reliable the market price is\n\n"
        "**Score guide:** 75+ Strong  ·  55–74 Good  ·  35–54 Marginal  ·  <35 Suppressed"
    )

    st.divider()
    st.markdown("**Data Sources**")
    st.markdown(
        "- **ESPN:** Free scoreboard API, no key required\n"
        "- **Kalshi:** Public market data, no auth required\n"
        "- **NBA stats:** Hardcoded estimates in utils.py (`NBA_NET_RATINGS`, `NBA_PLAYER_STATS`)\n"
        "- **CBB stats:** Hardcoded in utils.py (`CBB_TEAM_STATS`), sourced from cbb_betting_model.py\n"
        "- **Cache:** All external calls cached 10 minutes (TTL=600)"
    )

    if advanced:
        st.divider()
        st.markdown("**Model Preset Descriptions**")
        for name, desc in {
            "recommended":  "Balanced blend. Best starting point for most users.",
            "aggressive":   "Amplifies recent form. Higher picks count, more variance.",
            "conservative": "Season-long efficiency only. Fewer, higher-conviction picks.",
            "custom":       "Manually set weights in sidebar. Auto-normalized.",
        }.items():
            st.markdown(f"**{name.title()}:** {desc}")


# ────────── TAB 6: TRACKER ───────────────────────────────────────────────────
with tabs[5]:
    st.markdown("### Pick Tracker")
    st.info(
        "Manual pick tracking coming soon.\n\n"
        "Record your bets here to track P&L, win rate by stat type, "
        "and model calibration over time."
    )

    # Placeholder structure
    st.markdown("**Today's picks summary**")
    total_today = len(game_picks) + len(prop_picks)
    if total_today:
        cols = st.columns(4)
        cols[0].metric("Total Picks", total_today)
        cols[1].metric("Game Picks",  len(game_picks))
        cols[2].metric("Prop Picks",  len(prop_picks))
        avg_pqs = round(sum(p["pqs"] for p in game_picks + prop_picks) / total_today)
        cols[3].metric("Avg Score",   avg_pqs)
    else:
        st.caption("No qualifying picks today.")
