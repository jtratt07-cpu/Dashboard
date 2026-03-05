import streamlit as st
import requests, re, math, os, json
import pandas as pd
from datetime import datetime, timedelta, timezone, date

st.set_page_config(page_title="NBA Lines", page_icon="🏀", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.stApp{background:#0d1117;color:#e6edf3;}
section[data-testid="stSidebar"]{background:#161b22!important;border-right:1px solid #30363d;}
#MainMenu,footer,header{visibility:hidden;}
table{width:100%;border-collapse:collapse;margin:6px 0;}
th{font-size:0.65rem;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.06em;padding:6px 10px;border-bottom:2px solid #30363d;text-align:left;}
td{font-size:0.85rem;padding:8px 10px;border-bottom:1px solid #21262d;vertical-align:middle;}
tr:last-child td{border-bottom:none;}
.mono{font-family:'JetBrains Mono',monospace;}
.green{color:#3fb950;font-weight:700;}
.red{color:#f85149;font-weight:700;}
.grey{color:#8b949e;}
.sec{font-size:0.7rem;font-weight:700;color:#58a6ff;text-transform:uppercase;letter-spacing:.08em;margin:18px 0 6px;}
</style>
""", unsafe_allow_html=True)

BASE = "https://api.elections.kalshi.com/trade-api/v2"

# ── NET RATINGS (2025-26, pts per 100 poss) ───────────────────────────────────
NET = {
    "Oklahoma City Thunder":12.1,"Cleveland Cavaliers":11.8,
    "Boston Celtics":10.2,"Houston Rockets":7.9,
    "Golden State Warriors":7.1,"Indiana Pacers":6.8,
    "Memphis Grizzlies":5.9,"Denver Nuggets":5.4,
    "Los Angeles Lakers":4.8,"New York Knicks":4.5,
    "Milwaukee Bucks":3.9,"Philadelphia 76ers":3.4,
    "Minnesota Timberwolves":3.0,"Miami Heat":2.6,
    "Sacramento Kings":1.9,"Los Angeles Clippers":1.2,
    "Dallas Mavericks":0.7,"Atlanta Hawks":-0.6,
    "Phoenix Suns":-1.4,"Chicago Bulls":-2.1,
    "Brooklyn Nets":-2.7,"Orlando Magic":-3.3,
    "Charlotte Hornets":-4.0,"Toronto Raptors":-4.5,
    "Utah Jazz":-5.3,"San Antonio Spurs":-6.0,
    "Portland Trail Blazers":-6.8,"Detroit Pistons":-7.4,
    "New Orleans Pelicans":-8.1,"Washington Wizards":-9.5,
}
ALIASES = {
    "thunder":"Oklahoma City Thunder","cavaliers":"Cleveland Cavaliers",
    "celtics":"Boston Celtics","rockets":"Houston Rockets",
    "warriors":"Golden State Warriors","pacers":"Indiana Pacers",
    "grizzlies":"Memphis Grizzlies","nuggets":"Denver Nuggets",
    "lakers":"Los Angeles Lakers","knicks":"New York Knicks",
    "bucks":"Milwaukee Bucks","76ers":"Philadelphia 76ers","sixers":"Philadelphia 76ers",
    "timberwolves":"Minnesota Timberwolves","heat":"Miami Heat",
    "kings":"Sacramento Kings","clippers":"Los Angeles Clippers",
    "mavericks":"Dallas Mavericks","hawks":"Atlanta Hawks",
    "suns":"Phoenix Suns","bulls":"Chicago Bulls","nets":"Brooklyn Nets",
    "magic":"Orlando Magic","hornets":"Charlotte Hornets","raptors":"Toronto Raptors",
    "jazz":"Utah Jazz","spurs":"San Antonio Spurs",
    "trail blazers":"Portland Trail Blazers","blazers":"Portland Trail Blazers",
    "pistons":"Detroit Pistons","pelicans":"New Orleans Pelicans",
    "wizards":"Washington Wizards",
    "oklahoma city":"Oklahoma City Thunder","oklahoma":"Oklahoma City Thunder",
    "cleveland":"Cleveland Cavaliers","boston":"Boston Celtics",
    "houston":"Houston Rockets","golden state":"Golden State Warriors",
    "indiana":"Indiana Pacers","memphis":"Memphis Grizzlies",
    "denver":"Denver Nuggets","new york":"New York Knicks",
    "milwaukee":"Milwaukee Bucks","philadelphia":"Philadelphia 76ers",
    "minnesota":"Minnesota Timberwolves","miami":"Miami Heat",
    "sacramento":"Sacramento Kings","dallas":"Dallas Mavericks",
    "atlanta":"Atlanta Hawks","phoenix":"Phoenix Suns","chicago":"Chicago Bulls",
    "brooklyn":"Brooklyn Nets","orlando":"Orlando Magic","charlotte":"Charlotte Hornets",
    "toronto":"Toronto Raptors","utah":"Utah Jazz","san antonio":"San Antonio Spurs",
    "portland":"Portland Trail Blazers","detroit":"Detroit Pistons",
    "new orleans":"New Orleans Pelicans","washington":"Washington Wizards",
    "los angeles l":"Los Angeles Lakers","la lakers":"Los Angeles Lakers",
    "los angeles c":"Los Angeles Clippers","la clippers":"Los Angeles Clippers",
}

def team(text):
    t = (text or "").lower()
    for k in sorted(ALIASES, key=len, reverse=True):
        if re.search(r'\b' + re.escape(k) + r'\b', t):
            return ALIASES[k]
    return None

# ── MODEL ─────────────────────────────────────────────────────────────────────
def win_prob(home, away):
    h, a = NET.get(home), NET.get(away)
    if h is None or a is None: return None
    spread = (h - a) / 2.5 + 2.5      # home pts favored by
    z = spread / (11.0 * math.sqrt(2))
    import math as m2
    return 0.5 * (1 + m2.erf(z))

# ── HELPERS ───────────────────────────────────────────────────────────────────
def prob(m):
    yb = m.get("yes_bid") or 0
    ya = m.get("yes_ask") or 0
    lp = m.get("last_price") or 0
    if yb > 0 and ya > 0: return round((yb + ya) / 200, 4)
    if lp > 0:            return round(lp / 100, 4)
    return None

def odds(p):
    if p is None or p < 0.02 or p > 0.98: return "—"
    return f"-{round(p/(1-p)*100)}" if p >= 0.5 else f"+{round((1-p)/p*100)}"

def edge_str(model_p, kalshi_p):
    if model_p is None or kalshi_p is None: return "—", ""
    e = (model_p - kalshi_p) * 100
    cls = "green" if e > 2 else ("red" if e < -2 else "grey")
    return f"{e:+.1f}%", cls

def _et_off(u):
    y = u.year
    m2 = datetime(y,3,8,2,tzinfo=timezone.utc)
    while m2.weekday()!=6: m2+=timedelta(days=1)
    n1 = datetime(y,11,1,2,tzinfo=timezone.utc)
    while n1.weekday()!=6: n1+=timedelta(days=1)
    return timedelta(hours=-4) if m2<=u<n1 else timedelta(hours=-5)

def to_et(iso):
    try:
        u = datetime.fromisoformat(iso.replace("Z","+00:00"))
        return u + _et_off(u)
    except: return None

def today_et():
    u = datetime.now(timezone.utc)
    return (u + _et_off(u)).date()

def is_today(iso):
    if not iso: return False
    et = to_et(iso)
    return et is not None and et.date() == today_et()

def fmt_t(iso):
    et = to_et(iso)
    if not et: return ""
    h = int(et.strftime("%-I"))
    return f"{h}:{et.strftime('%M %p')} ET"

# ── FETCH ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def fetch():
    out = []
    for status in ["open", "closed", "unopened"]:
        cur = None
        for _ in range(20):
            p = {"status": status, "limit": 200, "mve_filter": "exclude"}
            if cur: p["cursor"] = cur
            try:
                r = requests.get(f"{BASE}/markets", params=p, timeout=20)
                if r.status_code != 200: break
                d = r.json()
                out.extend(d.get("markets", []))
                cur = d.get("cursor")
                if not cur or not d.get("markets"): break
            except: break
    return out

# ── GROUP INTO GAMES ──────────────────────────────────────────────────────────
def group(markets):
    """Group today's NBA markets by event_ticker. Return list of game dicts."""
    buckets = {}
    for m in markets:
        ct = m.get("close_time","")
        if not is_today(ct): continue
        # Only keep if at least one NBA team appears somewhere in the text
        txt = " ".join(filter(None,[m.get("title",""),
                                    m.get("yes_sub_title",""),
                                    m.get("no_sub_title",""),
                                    m.get("event_ticker","")]))
        if not team(txt): continue

        ek = m.get("event_ticker") or m.get("ticker","").split("-")[0]
        if ek not in buckets:
            buckets[ek] = {"markets":[], "close_time": ct}
        buckets[ek]["markets"].append(m)
        if ct < buckets[ek]["close_time"]: buckets[ek]["close_time"] = ct

    # For each bucket, find home/away teams
    games = []
    for ek, b in buckets.items():
        home = away = None
        for m in b["markets"]:
            ys = m.get("yes_sub_title","") or ""
            ns = m.get("no_sub_title","")  or ""
            tt = m.get("title","")
            # Try "X at Y" pattern
            hit = re.search(r'(.+?)\s+at\s+(.+?)(?:\?|$)', tt, re.I)
            if hit:
                aw = team(hit.group(1)); hm = team(hit.group(2))
                if aw and hm and aw != hm: away, home = aw, hm; break
            # Try sub_titles
            ta, tb = team(ys), team(ns)
            if ta and tb and ta != tb: home, away = ta, tb; break
            # Try vs
            hit2 = re.search(r'(.+?)\s+vs\.?\s+(.+?)(?:\?|$)', tt, re.I)
            if hit2:
                ta2 = team(hit2.group(1)); tb2 = team(hit2.group(2))
                if ta2 and tb2 and ta2 != tb2: away, home = ta2, tb2; break

        if not home and not away: continue

        # Split markets into types
        ml, sp, to, pr = [], [], [], []
        for m in b["markets"]:
            tt = (m.get("title","") or "").lower()
            ys = (m.get("yes_sub_title","") or "").lower()
            # combo
            if tt.count(",") >= 1 and re.search(r'(yes |no )', tt): continue
            # total
            if re.search(r'total points|combined|over/under', tt): to.append(m); continue
            if re.search(r'\b(over|under)\s+\d', tt) and "win by" not in tt: to.append(m); continue
            # spread
            if re.search(r'win by|cover|by more than|by at least|spread', tt): sp.append(m); continue
            if re.search(r'[-+]\d+\.?\d*\s*points?\b', tt): sp.append(m); continue
            # prop
            stat = r'\b(points?|rebounds?|assists?|steals?|blocks?|3-pointer|threes?|made)\b'
            if re.search(stat, tt) and re.search(r'\d+\.?\d*\+', tt):
                if prob(m) is not None: pr.append(m); continue
            # moneyline
            if re.search(r'will\s+.+\s+win', tt): ml.append(m); continue
            if re.search(r'\bvs\.?\b|\bat\b|\bversus\b', tt) and not re.search(r'\d', tt):
                ml.append(m); continue
            if m.get("yes_sub_title") and m.get("no_sub_title") and \
               not re.search(stat, tt) and not re.search(r'\d+\+', tt):
                ml.append(m); continue

        total_mkts = len(ml)+len(sp)+len(to)+len(pr)
        if total_mkts == 0: continue

        games.append({
            "event_ticker": ek,
            "home": home, "away": away,
            "close_time": b["close_time"],
            "ml": sorted(ml, key=lambda x: x.get("volume") or 0, reverse=True),
            "sp": sorted(sp, key=lambda x: x.get("volume") or 0, reverse=True),
            "to": sorted(to, key=lambda x: x.get("volume") or 0, reverse=True),
            "pr": sorted(pr, key=lambda x: x.get("volume") or 0, reverse=True),
        })

    games.sort(key=lambda x: x["close_time"] or "Z")
    return games

# ── RENDER ────────────────────────────────────────────────────────────────────
def tbl_header():
    return "<table><tr><th>Market</th><th>Kalshi %</th><th>Odds</th><th>Model %</th><th>Edge</th></tr>"

def tbl_row(label, kp, mp):
    kpct = f"{kp*100:.0f}%" if kp is not None else "—"
    mpct = f"{mp*100:.0f}%" if mp is not None else "—"
    o    = odds(kp)
    e, cls = edge_str(mp, kp)
    return (f"<tr><td>{label}</td>"
            f"<td class='mono'>{kpct}</td>"
            f"<td class='mono'>{o}</td>"
            f"<td class='mono'>{mpct}</td>"
            f"<td class='mono {cls}'>{e}</td></tr>")

def render(g):
    home, away = g["home"] or "?", g["away"] or "?"
    gtime = fmt_t(g["close_time"])
    mp_home = win_prob(home, away)
    mp_away = (1 - mp_home) if mp_home else None

    hn = NET.get(home,"?"); an = NET.get(away,"?")
    model_note = f"Net ratings: {home.split()[-1]} {hn:+.1f} | {away.split()[-1]} {an:+.1f} | Home court +2.5" \
                 if isinstance(hn, float) else ""

    st.markdown(f"### {away.split()[-1]} @ {home.split()[-1]}  ·  {gtime}")
    if model_note:
        st.caption(model_note)

    html = ""

    # Moneylines
    if g["ml"]:
        html += '<div class="sec">Moneyline</div>' + tbl_header()
        seen = set()
        for m in g["ml"][:4]:
            ys = m.get("yes_sub_title","") or m.get("title","")
            t_full = team(ys)
            label = ys[:50]
            if label.lower() in seen: continue
            seen.add(label.lower())
            kp = prob(m)
            mp = mp_home if t_full == home else (mp_away if t_full == away else None)
            html += tbl_row(label, kp, mp)
        html += "</table>"

    # Spreads
    if g["sp"]:
        html += '<div class="sec">Spread</div>' + tbl_header()
        seen = set()
        for m in g["sp"][:6]:
            ys = m.get("yes_sub_title","") or m.get("title","")
            label = ys[:55]
            if label.lower() in seen: continue
            seen.add(label.lower())
            kp = prob(m)
            # For spreads, model edge = does our expected margin beat the line?
            nums = re.findall(r'\d+\.?\d*', label)
            mp_sp = None
            if nums and mp_home is not None:
                try:
                    line = float(nums[-1])
                    t_lbl = team(label)
                    # P(home wins by > line) or P(away wins by > line)
                    exp_margin = (NET.get(home,0) - NET.get(away,0)) / 2.5 + 2.5
                    if t_lbl == home:
                        adj = exp_margin - line
                    else:
                        adj = -exp_margin - line
                    z = adj / (11.0 * math.sqrt(2))
                    mp_sp = 0.5 * (1 + math.erf(z))
                except: pass
            html += tbl_row(label, kp, mp_sp)
        html += "</table>"

    # Totals
    if g["to"]:
        html += '<div class="sec">Game Total</div>' + tbl_header()
        seen = set()
        for m in g["to"][:4]:
            ys = m.get("yes_sub_title","") or m.get("title","")
            label = ys[:55]
            if label.lower() in seen: continue
            seen.add(label.lower())
            kp = prob(m)
            html += tbl_row(label, kp, None)  # no total model
        html += "</table>"

    # Props
    if g["pr"]:
        html += '<div class="sec">Player Props</div>' + tbl_header()
        seen = set()
        for m in sorted(g["pr"], key=lambda x: x.get("volume") or 0, reverse=True)[:12]:
            ys = m.get("yes_sub_title","") or m.get("title","")
            label = ys[:60]
            if label.lower() in seen: continue
            seen.add(label.lower())
            kp = prob(m)
            html += tbl_row(label, kp, None)  # no player model
        html += "</table>"

    st.markdown(html, unsafe_allow_html=True)

# ── MAIN ──────────────────────────────────────────────────────────────────────
with st.spinner("Fetching Kalshi markets…"):
    all_markets = fetch()

games = group(all_markets)

n_today = sum(1 for m in all_markets if is_today(m.get("close_time","")))

with st.sidebar:
    st.markdown(f"### 🏀 NBA — {today_et().strftime('%b %-d')}")
    et_now = datetime.now(timezone.utc) + _et_off(datetime.now(timezone.utc))
    st.caption(f"{et_now.strftime('%-I:%M %p')} ET  ·  {len(all_markets)} markets  ·  {n_today} today")
    st.divider()

    if games:
        labels = [
            f"{g['away'].split()[-1]} @ {g['home'].split()[-1]}  {fmt_t(g['close_time'])}"
            for g in games
        ]
        sel = st.radio("Game", range(len(games)), format_func=lambda i: labels[i])
    else:
        sel = None
        st.warning("No NBA games found yet.")

    st.divider()
    st.caption("Edge = model − Kalshi. Model uses net rating + home court (normal dist, σ=11). Props/totals show Kalshi line only — no model.")

if sel is None:
    # Debug view
    st.info(f"No NBA games identified. {len(all_markets)} markets fetched, {n_today} close today.")
    today_raw = [m for m in all_markets if is_today(m.get("close_time",""))]
    if today_raw:
        st.dataframe(pd.DataFrame([{
            "title":      m.get("title","")[:60],
            "yes_sub":    (m.get("yes_sub_title","") or "")[:30],
            "no_sub":     (m.get("no_sub_title","")  or "")[:30],
            "close_time": m.get("close_time","")[:16],
            "status":     m.get("status",""),
        } for m in today_raw[:60]]), hide_index=True, use_container_width=True)
    else:
        st.write("No markets close today. Sample:")
        st.dataframe(pd.DataFrame([{
            "title":      m.get("title","")[:60],
            "close_time": m.get("close_time","")[:16],
            "event_tk":   m.get("event_ticker","")[:30],
        } for m in all_markets[:30]]), hide_index=True, use_container_width=True)
else:
    render(games[sel])
    st.divider()
    st.caption(f"{len(games)} games today  ·  refresh in sidebar auto-updates every 2 min")
