"""
ui_layer.py — All UI rendering functions.
Depends on: streamlit, model_layer (for pqs_label), utils (for am_odds, prob_to_pct).
No API calls. No model computation. Renders pre-computed data only.
"""
from __future__ import annotations
import streamlit as st
from utils import am_odds, prob_to_pct, normalize_weights
from model_layer import pqs_label, classify_pick, NBA_GAME_PRESETS, CBB_GAME_PRESETS, PROP_PRESETS, get_preset_weights

# ─────────────────────────────────────────────────────────────────────────────
# CSS — injected once from app.py
# ─────────────────────────────────────────────────────────────────────────────
APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.stApp{background:#0d1117;color:#e6edf3;}
section[data-testid="stSidebar"]{background:#161b22!important;border-right:1px solid #30363d;}
section[data-testid="stSidebar"] *{color:#c9d1d9;}
#MainMenu,footer,header{visibility:hidden;}

/* Pick cards */
.pick-card{
  background:#161b22;border:1px solid #30363d;border-radius:10px;
  padding:16px 20px;margin-bottom:12px;
}
.pick-card.strong{border-left:4px solid #3fb950;}
.pick-card.good{border-left:4px solid #d29922;}
.pick-card.marginal{border-left:4px solid #58a6ff;}

.card-header{font-size:.80rem;font-weight:600;color:#8b949e;text-transform:uppercase;
             letter-spacing:.07em;margin-bottom:6px;}
.card-title{font-size:1.08rem;font-weight:700;color:#e6edf3;margin-bottom:8px;}
.card-meta{display:flex;gap:16px;margin-bottom:10px;flex-wrap:wrap;}
.badge{font-size:.75rem;font-weight:700;padding:3px 10px;border-radius:20px;font-family:'JetBrains Mono',monospace;}
.badge-edge{background:#1f4e2f;color:#3fb950;}
.badge-edge-neg{background:#4e1f1f;color:#f85149;}
.badge-conf{background:#21262d;color:#c9d1d9;}
.badge-pqs-strong{background:#1f4e2f;color:#3fb950;}
.badge-pqs-good{background:#3d2f00;color:#d29922;}
.badge-pqs-marginal{background:#1c2a40;color:#58a6ff;}

/* Pick category badges */
.cat-best-bet{background:#1a3a2a;color:#3fb950;border:1px solid #2ea043;}
.cat-underdog{background:#2a1f3a;color:#a78bfa;}
.cat-good-value{background:#1c2a1c;color:#4ade80;}
.cat-sharp{background:#21262d;color:#79c0ff;}
.cat-spot-play{background:#21262d;color:#8b949e;}

/* EV / Kelly row */
.ev-val{color:#4ade80;font-family:'JetBrains Mono',monospace;font-size:.82rem;font-weight:600;}
.kelly-val{color:#f0a13a;font-family:'JetBrains Mono',monospace;font-size:.82rem;font-weight:600;}

/* Prob row */
.prob-row{margin:6px 0 3px;}
.odds-val{color:#3fb950;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:1.05rem;}
.odds-label{color:#8b949e;font-size:.78rem;margin-left:8px;}
.mkt-compare{color:#8b949e;font-size:.82rem;margin-bottom:4px;}

.reasoning{margin-top:8px;}
.reasoning ul{margin:0;padding-left:16px;}
.reasoning li{font-size:.85rem;color:#8b949e;margin-bottom:3px;line-height:1.45;}

/* Tables */
table{width:100%;border-collapse:collapse;margin:4px 0 12px;}
th{font-size:.63rem;font-weight:700;color:#8b949e;text-transform:uppercase;
   letter-spacing:.06em;padding:6px 10px;border-bottom:2px solid #30363d;text-align:left;}
td{font-size:.85rem;padding:8px 10px;border-bottom:1px solid #21262d;vertical-align:middle;}
tr:last-child td{border-bottom:none;}
.mono{font-family:'JetBrains Mono',monospace;}
.green{color:#3fb950;font-weight:700;}
.red{color:#f85149;font-weight:700;}
.yellow{color:#d29922;font-weight:700;}
.grey{color:#8b949e;}
.sec{font-size:.68rem;font-weight:700;color:#58a6ff;text-transform:uppercase;
     letter-spacing:.08em;margin:16px 0 4px;}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Pick card rendering
# ─────────────────────────────────────────────────────────────────────────────

def _edge_badge(edge_pct: float | None) -> str:
    if edge_pct is None:
        return '<span class="badge badge-conf">—</span>'
    cls = "badge-edge" if edge_pct > 0 else "badge-edge-neg"
    sign = "+" if edge_pct > 0 else ""
    return f'<span class="badge {cls}">{sign}{edge_pct:.0f}% value edge</span>'

def _pqs_badge(pqs: int, advanced: bool = False) -> str:
    label, color = pqs_label(pqs)
    cls_map = {"green": "badge-pqs-strong", "yellow": "badge-pqs-good",
               "grey": "badge-pqs-marginal", "red": "badge-conf"}
    cls = cls_map.get(color, "badge-conf")
    if advanced:
        return f'<span class="badge {cls}">PQS {pqs} · {label}</span>'
    icon_map  = {"green": "🔥", "yellow": "✅", "grey": "⚡", "red": "·"}
    label_map = {"green": "Strong Pick", "yellow": "Good Pick", "grey": "Marginal", "red": "Low Confidence"}
    return f'<span class="badge {cls}">{icon_map.get(color, "·")} {label_map.get(color, label)}</span>'

def _conf_badge(conf: float | None, advanced: bool = False) -> str:
    if not advanced or conf is None:
        return ""
    return f'<span class="badge badge-conf">Conviction: {conf:.0f}%</span>'

def _card_class(pqs: int) -> str:
    if pqs >= 75:
        return "pick-card strong"
    if pqs >= 55:
        return "pick-card good"
    return "pick-card marginal"

def _reasoning_html(bullets: list) -> str:
    if not bullets:
        return ""
    items = "".join(f"<li>{b}</li>" for b in bullets)
    return f'<div class="reasoning"><ul>{items}</ul></div>'

def _prob_row_html(
    model_p: float,
    kalshi_p: float,
    ev_pct: float | None = None,
    kelly_pct: float | None = None,
) -> str:
    """
    Render the odds + market comparison row.
    Shows Kalshi-implied odds in green (the bet we're recommending),
    EV% and Kelly bet sizing when available, then market vs model comparison.
    """
    odds_str  = am_odds(kalshi_p)
    ev_str    = (
        f'&nbsp; <span class="ev-val">EV +{ev_pct:.1f}%</span>'
        if ev_pct is not None and ev_pct > 0 else ""
    )
    kelly_str = (
        f'&nbsp;·&nbsp; <span class="kelly-val">Bet {kelly_pct:.1f}% bankroll</span>'
        if kelly_pct is not None and kelly_pct > 0 else ""
    )
    return (
        f'<div class="prob-row">'
        f'  <span class="odds-val">{odds_str}</span>'
        f'  <span class="odds-label">← bet at these odds</span>'
        f'{ev_str}'
        f'</div>'
        f'<div class="mkt-compare">'
        f'Market: <span class="mono">{kalshi_p*100:.0f}%</span>'
        f'&nbsp;·&nbsp;Model: <span class="mono">{model_p*100:.0f}%</span>'
        f'{kelly_str}'
        f'</div>'
    )


def _injury_html(injuries: list) -> str:
    """Render compact injury notes for a pick card. injuries = filtered list for one team."""
    if not injuries:
        return ""
    parts = []
    for inj in injuries[:4]:  # cap at 4 to keep cards compact
        icon   = "❌" if inj["status"] == "Out" else "⚠️"
        detail = inj.get("detail", "")
        side   = inj.get("side", "")
        loc    = f"{side} {detail}".strip() if side else detail
        parts.append(f"{icon} <b>{inj['player']}</b> — {inj['status']}{', ' + loc if loc else ''}")
    items = "".join(f"<li>{p}</li>" for p in parts)
    return (
        f'<div class="reasoning" style="margin-top:6px;">'
        f'<div style="font-size:.72rem;font-weight:700;color:#58a6ff;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:3px;">Injury Report</div>'
        f"<ul>{items}</ul></div>"
    )


def _category_badge(edge_pct: float | None, model_p: float | None, pqs: int) -> str:
    """Return a plain-English category badge for a pick."""
    if edge_pct is None or model_p is None:
        return ""
    label, icon, cls = classify_pick(edge_pct, model_p, pqs)
    return f'<span class="badge {cls}">{icon} {label}</span>'


def render_game_pick_card(pick: dict, advanced: bool = False) -> None:
    """
    Render a single game pick card.

    pick dict keys:
      sport, home, away, time_et, pick_team, pick_direction,
      model_prob, kalshi_prob, edge_pct, ev_pct, kelly_pct,
      pqs, confidence, reasoning (list[str]), model_result (full result dict),
      market_type (moneyline/spread/total),
      injuries_home, injuries_away (optional, lists of injury dicts)
    """
    pqs       = pick.get("pqs", 0)
    edge_pct  = pick.get("edge_pct")
    model_p   = pick.get("model_prob")
    kalshi_p  = pick.get("kalshi_prob")
    pick_team = pick.get("pick_team", "")
    sport     = pick.get("sport", "NBA").upper()
    reasoning = pick.get("reasoning", [])

    header = f'{sport} · {pick.get("away","")} @ {pick.get("home","")} · {pick.get("time_et","")}'
    title  = f'{pick_team} {pick.get("pick_direction","wins")}'

    cat_badge = _category_badge(edge_pct, model_p, pqs)
    badges = (
        cat_badge +
        (" " if cat_badge else "") +
        _edge_badge(edge_pct) +
        " " +
        _pqs_badge(pqs, advanced=advanced) +
        (" " + _conf_badge(pick.get("confidence"), advanced=advanced) if advanced else "")
    )

    prob_row = ""
    if model_p is not None and kalshi_p is not None:
        prob_row = _prob_row_html(
            model_p, kalshi_p,
            ev_pct=pick.get("ev_pct"),
            kelly_pct=pick.get("kelly_pct"),
        )

    # Injuries: show both teams combined (picked team first)
    inj_home = pick.get("injuries_home", [])
    inj_away = pick.get("injuries_away", [])
    all_injuries = inj_home + inj_away
    injury_block = _injury_html(all_injuries)

    html = f"""
    <div class="{_card_class(pqs)}">
      <div class="card-header">{header}</div>
      <div class="card-title">{title}</div>
      <div class="card-meta">{badges}</div>
      {prob_row}
      {_reasoning_html(reasoning)}
      {injury_block}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    if advanced:
        with st.expander("Model details", expanded=False):
            mr = pick.get("model_result", {})
            if mr:
                st.caption("Factor breakdown")
                for name, val, wt, contrib in mr.get("factors", []):
                    if contrib is not None:
                        st.caption(f"  {name}: {val:+.1f}  ×  w={wt:.2f}  →  {contrib:+.2f}")
                    else:
                        st.caption(f"  {name}: {val}")
            st.caption(f"Expected margin: {mr.get('expected_margin', '—')}")
            st.caption(f"Confidence: {mr.get('confidence', '—')}")


def render_prop_pick_card(pick: dict, advanced: bool = False) -> None:
    """
    Render a single player prop pick card.

    pick dict keys:
      player, stat_type, line, over_under, projection,
      model_prob, kalshi_prob, edge_pct, ev_pct, kelly_pct,
      pqs, confidence, reasoning (list[str]), model_result (full result dict),
      team (optional)
    """
    pqs       = pick.get("pqs", 0)
    edge_pct  = pick.get("edge_pct")
    player    = pick.get("player", "Unknown Player")
    stat_type = pick.get("stat_type", "")
    stat_lbl  = stat_type.upper()
    line      = pick.get("line", 0)
    proj      = pick.get("projection")
    model_p   = pick.get("model_prob")
    kalshi_p  = pick.get("kalshi_prob")
    reasoning = pick.get("reasoning", [])

    header = f'NBA Props · {player}'
    title  = f'Over {line} {stat_lbl}'
    if proj is not None:
        title += f'  <span style="color:#8b949e;font-size:.92rem;">(proj: {proj:.1f})</span>'

    cat_badge = _category_badge(edge_pct, model_p, pqs)
    badges = (
        cat_badge +
        (" " if cat_badge else "") +
        _edge_badge(edge_pct) +
        " " +
        _pqs_badge(pqs, advanced=advanced) +
        (" " + _conf_badge(pick.get("confidence"), advanced=advanced) if advanced else "")
    )

    prob_row = ""
    if model_p is not None and kalshi_p is not None:
        prob_row = _prob_row_html(
            model_p, kalshi_p,
            ev_pct=pick.get("ev_pct"),
            kelly_pct=pick.get("kelly_pct"),
        )

    html = f"""
    <div class="{_card_class(pqs)}">
      <div class="card-header">{header}</div>
      <div class="card-title">{title}</div>
      <div class="card-meta">{badges}</div>
      {prob_row}
      {_reasoning_html(reasoning)}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    if advanced:
        with st.expander("Model details", expanded=False):
            mr = pick.get("model_result", {})
            if mr:
                st.caption(f"Season avg: {mr.get('season_avg', '—')}")
                st.caption(f"Last-5 avg: {mr.get('recent_avg', '—')}")
                st.caption(f"Projection: {mr.get('projection', '—')}")
                st.caption(f"Sigma: ±{mr.get('sigma', '—')}")
                st.caption(f"Stability: {(mr.get('stability', 0)*100):.0f}%")
                st.caption(f"Over prob: {mr.get('over_prob', 0)*100:.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# Model-only game row (when Kalshi markets unavailable)
# ─────────────────────────────────────────────────────────────────────────────
def render_model_game_row(game: dict, result: dict, sport: str = "NBA") -> None:
    """
    Compact model-only row for when Kalshi markets aren't available.
    Shows matchup, game time, and model win probabilities.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# Player projections table (Props tab fallback)
# ─────────────────────────────────────────────────────────────────────────────
def render_player_projections_table(games: list, injuries: dict = None) -> None:
    """
    Show model season-average projections for players on tonight's NBA teams.
    injuries: optional dict {team_name: [{"player", "status", ...}]} from ESPN.
    """
    from utils import NBA_PLAYER_STATS
    import pandas as pd

    tonight_teams: set = set()
    for g in games:
        if g.get("home"):
            tonight_teams.add(g["home"])
        if g.get("away"):
            tonight_teams.add(g["away"])

    # Build a fast name→status lookup from the injuries dict
    inj_lookup: dict = {}   # lowercase player name → "❌ Out" or "⚠️ GTD"
    if injuries:
        for team_inj_list in injuries.values():
            for inj in team_inj_list:
                pname = inj.get("player", "").lower()
                status = inj.get("status", "")
                icon = "❌" if status == "Out" else "⚠️"
                inj_lookup[pname] = f"{icon} {status}"

    rows = []
    for name, s in NBA_PLAYER_STATS.items():
        team = s.get("team", "")
        if team not in tonight_teams:
            continue
        # Fuzzy match injury: check if player name appears in lookup
        name_lower = name.lower()
        status_str = inj_lookup.get(name_lower, "")
        if not status_str:
            for iname, istatus in inj_lookup.items():
                if iname in name_lower or name_lower in iname:
                    status_str = istatus
                    break
        rows.append({
            "Player":     name,
            "Team":       team.split()[-1],
            "Status":     status_str or "Active",
            "PRA":        s.get("pra", "—"),
            "Points":     s.get("pts", "—"),
            "Rebounds":   s.get("reb", "—"),
            "Assists":    s.get("ast", "—"),
            "3-Pointers": s.get("3pm", "—"),
        })

    if not rows:
        st.caption("No player data available for tonight's teams.")
        return

    df = pd.DataFrame(rows).sort_values("PRA", ascending=False)
    st.dataframe(df, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Matchup breakdown — injury report per game
# ─────────────────────────────────────────────────────────────────────────────

def render_matchup_breakdown(games: list, injuries: dict) -> None:
    """
    Show per-game injury report for tonight's matchups.
    Only renders if at least one game has reported injuries.
    injuries: {team_display_name: [{"player", "status", "detail", "side", "position"}]}
    """
    if not games or not injuries:
        return

    # Filter to only games that have at least one injured player
    games_with_inj = []
    for game in games:
        home_inj = injuries.get(game.get("home", ""), [])
        away_inj = injuries.get(game.get("away", ""), [])
        if home_inj or away_inj:
            games_with_inj.append(game)

    if not games_with_inj:
        return

    st.markdown("---")
    st.markdown("#### 🏥 Tonight's Injury Report")
    st.caption("Source: ESPN · Updates every 10 minutes")

    for game in games_with_inj:
        home     = game.get("home", "?")
        away     = game.get("away", "?")
        home_nick = home.split()[-1]
        away_nick = away.split()[-1]
        home_inj = injuries.get(home, [])
        away_inj = injuries.get(away, [])

        with st.expander(f"{away_nick} @ {home_nick}  ·  {game.get('time_et', '')}"):
            col_away, col_home = st.columns(2)

            for col, nick, inj_list in [
                (col_away, away_nick, away_inj),
                (col_home, home_nick, home_inj),
            ]:
                with col:
                    st.markdown(f"**{nick}**")
                    if not inj_list:
                        st.caption("No reported injuries")
                    else:
                        for inj in inj_list:
                            status = inj["status"]
                            icon   = "❌" if status == "Out" else ("⚠️" if status == "Day-To-Day" else "🔴")
                            detail = inj.get("detail", "")
                            side   = inj.get("side", "")
                            loc    = f"{side} {detail}".strip() if side else detail
                            pos    = inj.get("position", "")
                            pos_str = f" ({pos})" if pos else ""
                            st.markdown(f"{icon} **{inj['player']}**{pos_str}  \n&nbsp;&nbsp;{status}{', ' + loc if loc else ''}")


# ─────────────────────────────────────────────────────────────────────────────
# Raw market table (simple mode fallback)
# ─────────────────────────────────────────────────────────────────────────────
def build_market_table(rows: list) -> str:
    """
    rows: list of (label, kalshi_prob, model_prob)
    Returns HTML table string.
    """
    html = (
        "<table><tr><th>Market</th><th>Kalshi</th>"
        "<th>Odds</th><th>Model</th><th>Edge</th></tr>"
    )
    for label, kp, mp in rows:
        kpct = f"{kp*100:.0f}%" if kp is not None else "—"
        mpct = f"{mp*100:.0f}%" if mp is not None else "—"
        odds = am_odds(kp)
        if mp is not None and kp is not None:
            e     = (mp - kp) * 100
            e_str = f"{e:+.1f}%"
            cls   = "green" if e > 2 else ("red" if e < -2 else "grey")
        else:
            e_str, cls = "—", "grey"
        html += (
            f"<tr><td>{label}</td><td class='mono'>{kpct}</td>"
            f"<td class='mono'>{odds}</td><td class='mono'>{mpct}</td>"
            f"<td class='mono {cls}'>{e_str}</td></tr>"
        )
    return html + "</table>"


def render_market_section(title: str, rows: list, max_rows: int = 6) -> None:
    """Render a labeled section of a market table."""
    if not rows:
        return
    st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)
    st.markdown(build_market_table(rows[:max_rows]), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Model weight editor (Advanced Mode sidebar / expander)
# ─────────────────────────────────────────────────────────────────────────────
_PRESET_DESCRIPTIONS = {
    "recommended":  "Balanced blend of proven efficiency metrics. Best starting point.",
    "aggressive":   "Amplifies recent form and matchup signals. Higher variance.",
    "conservative": "Leans almost entirely on season-long stability. Fewer picks.",
    "custom":       "Edit weights manually below. They auto-normalize to sum to 100%.",
}

def render_model_editor(
    model_type:   str,
    stat_type:    str = "pra",
    session_key:  str = "weights",
) -> dict:
    """
    Render a model preset selector and optional weight editor in the sidebar.
    Returns the currently active weights dict (normalized).
    model_type: 'nba_game' | 'cbb_game' | 'prop'
    """
    preset_options = ["recommended", "aggressive", "conservative", "custom"]
    preset = st.selectbox(
        "Model preset",
        preset_options,
        index=0,
        key=f"{session_key}_preset",
        help="Recommended is best for most users."
    )
    st.caption(_PRESET_DESCRIPTIONS.get(preset, ""))

    base_weights = get_preset_weights(model_type, preset, stat_type)

    if preset == "custom":
        st.markdown("**Edit weights** (auto-normalized)")
        edited = {}
        for k, v in base_weights.items():
            edited[k] = st.slider(
                k.replace("_", " ").title(),
                min_value=0,
                max_value=100,
                value=int(v * 100),
                key=f"{session_key}_{k}",
            )
        # Reset button
        if st.button("Reset to recommended", key=f"{session_key}_reset"):
            for k in base_weights:
                st.session_state[f"{session_key}_{k}"] = int(base_weights[k] * 100)
        final_weights = {k: v / 100 for k, v in edited.items()}
    else:
        final_weights = base_weights

    return normalize_weights(final_weights)


# ─────────────────────────────────────────────────────────────────────────────
# No-picks message
# ─────────────────────────────────────────────────────────────────────────────
def render_no_picks(reason: str = "") -> None:
    msg = "No value picks found for today."
    if reason:
        msg += f" {reason}"
    st.info(msg)
    st.caption(
        "Picks appear when our model finds meaningful value over the market price. "
        "Try lowering filters or check back later."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Score / game status display
# ─────────────────────────────────────────────────────────────────────────────
def render_score_row(game: dict) -> None:
    """Display a live or completed game score row."""
    home       = game.get("home", "—")
    away       = game.get("away", "—")
    hs         = game.get("home_score")
    as_        = game.get("away_score")
    status     = game.get("short_status", game.get("status", ""))
    time_et    = game.get("time_et", "")

    home_nick = home.split()[-1] if home else "?"
    away_nick = away.split()[-1] if away else "?"

    if hs is not None and as_ is not None:
        score_str = f"**{away_nick}** {as_} — {hs} **{home_nick}**"
    else:
        score_str = f"{away_nick} @ {home_nick}"

    st.markdown(f"{score_str} &nbsp; `{status or time_et}`", unsafe_allow_html=False)


# ─────────────────────────────────────────────────────────────────────────────
# Stats reference table
# ─────────────────────────────────────────────────────────────────────────────
def render_nba_net_ratings() -> None:
    """Render a sortable NBA net ratings reference table."""
    from utils import NBA_NET_RATINGS
    import pandas as pd

    df = pd.DataFrame(
        [{"Team": t, "Net Rating": r} for t, r in
         sorted(NBA_NET_RATINGS.items(), key=lambda x: x[1], reverse=True)]
    )
    st.dataframe(df, hide_index=True)


def render_cbb_ratings() -> None:
    """Render CBB team ratings reference table."""
    from utils import CBB_TEAM_STATS
    import pandas as pd

    rows = []
    for team, s in CBB_TEAM_STATS.items():
        rows.append({
            "Team":        team,
            "Eff Margin":  s.get("eff_margin", "—"),
            "Adj Offense": s.get("adj_o", "—"),
            "Adj Defense": s.get("adj_d", "—"),
            "eFG%":        f"{s.get('efg', 0):.3f}",
            "TO Rate":     f"{s.get('to_rate', 0):.3f}",
            "Experience":  f"{s.get('exp', 0):.0%}",
            "Seed":        s.get("seed", "—"),
        })
    df = pd.DataFrame(rows).sort_values("Eff Margin", ascending=False)
    st.dataframe(df, hide_index=True)


def render_player_stats_table() -> None:
    """Render NBA player stats reference table."""
    from utils import NBA_PLAYER_STATS
    import pandas as pd

    rows = []
    for name, s in NBA_PLAYER_STATS.items():
        rows.append({
            "Player":    name,
            "Team":      s.get("team", "—"),
            "Pos":       s.get("pos", "—"),
            "PRA":       s.get("pra", "—"),
            "Pts":       s.get("pts", "—"),
            "Reb":       s.get("reb", "—"),
            "Ast":       s.get("ast", "—"),
            "3PM":       s.get("3pm", "—"),
            "Blk":       s.get("blk", "—"),
            "Stl":       s.get("stl", "—"),
            "Min":       s.get("min", "—"),
            "USG%":      s.get("usage", "—"),
        })
    df = pd.DataFrame(rows).sort_values("PRA", ascending=False)
    st.dataframe(df, hide_index=True)
