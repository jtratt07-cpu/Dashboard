"""
ui_layer.py — All UI rendering functions.
Depends on: streamlit, model_layer (for pqs_label), utils (for am_odds, prob_to_pct).
No API calls. No model computation. Renders pre-computed data only.
"""
import streamlit as st
from utils import am_odds, prob_to_pct, normalize_weights
from model_layer import pqs_label, NBA_GAME_PRESETS, CBB_GAME_PRESETS, PROP_PRESETS, get_preset_weights

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
    return f'<span class="badge {cls}">{sign}{edge_pct:.1f}% edge</span>'

def _pqs_badge(pqs: int) -> str:
    label, color = pqs_label(pqs)
    cls_map = {"green": "badge-pqs-strong", "yellow": "badge-pqs-good",
               "grey": "badge-pqs-marginal", "red": "badge-conf"}
    cls = cls_map.get(color, "badge-conf")
    return f'<span class="badge {cls}">PQS {pqs} · {label}</span>'

def _conf_badge(conf: float | None) -> str:
    if conf is None:
        return ""
    return f'<span class="badge badge-conf">{conf:.0f}% conf</span>'

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


def render_game_pick_card(pick: dict, advanced: bool = False) -> None:
    """
    Render a single game pick card.

    pick dict keys:
      sport, home, away, time_et, pick_team, pick_direction,
      model_prob, kalshi_prob, edge_pct, pqs, confidence,
      reasoning (list[str]), model_result (full result dict),
      market_type (moneyline/spread/total)
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

    badges = (
        _edge_badge(edge_pct) +
        " " +
        _pqs_badge(pqs) +
        " " +
        _conf_badge(pick.get("confidence"))
    )

    prob_row = ""
    if model_p is not None and kalshi_p is not None:
        odds_str = am_odds(kalshi_p)
        prob_row = (
            f'<span class="grey" style="font-size:.82rem;">'
            f'Model: <span class="mono">{model_p*100:.0f}%</span> &nbsp;·&nbsp; '
            f'Kalshi: <span class="mono">{kalshi_p*100:.0f}%</span> '
            f'(<span class="mono">{odds_str}</span>)'
            f'</span>'
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
      model_prob, kalshi_prob, edge_pct, pqs, confidence,
      reasoning (list[str]), model_result (full result dict),
      team (optional)
    """
    pqs       = pick.get("pqs", 0)
    edge_pct  = pick.get("edge_pct")
    player    = pick.get("player", "Unknown Player")
    stat_lbl  = pick.get("stat_type", "").upper()
    line      = pick.get("line", 0)
    direction = pick.get("over_under", "over").capitalize()
    proj      = pick.get("projection")
    model_p   = pick.get("model_prob")
    kalshi_p  = pick.get("kalshi_prob")
    reasoning = pick.get("reasoning", [])

    header = f'NBA Props · {player}'
    title  = f'{direction} {line} {stat_lbl}'
    if proj is not None:
        title += f'  <span style="color:#8b949e;font-size:.92rem;">(proj: {proj:.1f})</span>'

    badges = (
        _edge_badge(edge_pct) +
        " " +
        _pqs_badge(pqs) +
        " " +
        _conf_badge(pick.get("confidence"))
    )

    prob_row = ""
    if model_p is not None and kalshi_p is not None:
        odds_str = am_odds(kalshi_p)
        prob_row = (
            f'<span class="grey" style="font-size:.82rem;">'
            f'Model: <span class="mono">{model_p*100:.0f}%</span> &nbsp;·&nbsp; '
            f'Kalshi: <span class="mono">{kalshi_p*100:.0f}%</span> '
            f'(<span class="mono">{odds_str}</span>)'
            f'</span>'
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
    msg = "No qualifying picks found."
    if reason:
        msg += f" {reason}"
    st.info(msg)
    st.caption(
        "Picks only appear when the model finds a meaningful edge over Kalshi implied probability "
        "and the Pick Quality Score is sufficient. Try Advanced Mode to lower thresholds."
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
    st.dataframe(df, use_container_width=True, hide_index=True)


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
    st.dataframe(df, use_container_width=True, hide_index=True)


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
    st.dataframe(df, use_container_width=True, hide_index=True)
