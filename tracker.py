"""
tracker.py — Pick Tracker: storage, logging, result entry, and P&L computation.

Writes to tracker.json in the same directory as this file.
  • Locally:           persists between sessions automatically.
  • Streamlit Cloud:   persists within a session only — use Export/Import buttons
                       to save your history across sessions.
"""
from __future__ import annotations
import json
import os
from datetime import datetime

_DIR         = os.path.dirname(os.path.abspath(__file__))
TRACKER_FILE = os.path.join(_DIR, "tracker.json")


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_tracker() -> dict:
    """Load tracker from JSON. Returns empty tracker if missing or corrupt."""
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r") as f:
                data = json.load(f)
            data.setdefault("picks", [])
            return data
        except (json.JSONDecodeError, IOError):
            pass
    return {"version": 1, "picks": []}


def save_tracker(data: dict) -> bool:
    """Write tracker to JSON. Returns True on success."""
    try:
        with open(TRACKER_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except IOError:
        return False


# ── Pick ID ───────────────────────────────────────────────────────────────────

def _pick_id(date_str: str, team: str, direction: str) -> str:
    """Stable unique ID for a pick: date + team + direction."""
    raw = f"{date_str}__{team}__{direction}"
    return "".join(c if c.isalnum() or c == "_" else "_" for c in raw)


# ── Logging ───────────────────────────────────────────────────────────────────

def log_picks(picks: list, date_str: str) -> tuple[int, int]:
    """
    Add picks to the tracker, skipping duplicates.
    Supports both game picks (have 'pick_team') and prop picks (have 'stat_type').
    Returns (added, skipped).
    """
    data     = load_tracker()
    existing = {p.get("pick_id", "") for p in data["picks"]}
    added = skipped = 0

    for pick in picks:
        is_prop = "stat_type" in pick   # prop picks have stat_type; game picks don't

        if is_prop:
            team_key  = pick.get("player", pick.get("team", ""))
        else:
            team_key  = pick.get("pick_team", pick.get("team", ""))

        direction = pick.get("pick_direction", "")
        pid       = _pick_id(date_str, team_key or "", direction)

        if pid in existing:
            skipped += 1
            continue

        entry = {
            "pick_id":        pid,
            "date":           date_str,
            "sport":          pick.get("sport", "NBA"),
            "type":           "prop" if is_prop else "game",
            # Shared display fields
            "team":           team_key or "",
            "pick_direction": direction,
            "odds_str":       pick.get("odds_str", ""),
            # Game-specific
            "home":           pick.get("home", ""),
            "away":           pick.get("away", ""),
            "time_et":        pick.get("time_et", ""),
            "market_type":    pick.get("market_type", ""),
            # Prop-specific
            "player":         pick.get("player", ""),
            "stat_type":      pick.get("stat_type", ""),
            "line":           pick.get("line"),
            # Model metrics
            "edge_pct":       pick.get("edge_pct"),
            "ev_pct":         pick.get("ev_pct"),
            "kelly_pct":      pick.get("kelly_pct"),
            "model_prob":     pick.get("model_prob"),
            "kalshi_prob":    pick.get("kalshi_prob"),
            "pqs":            pick.get("pqs"),
            "category":       pick.get("category", ""),
            # Result (set later)
            "result":         None,    # "W" | "L" | "P"
            "units_bet":      1.0,
            "logged_at":      datetime.now().isoformat(),
            "settled_at":     None,
        }

        data["picks"].append(entry)
        existing.add(pid)
        added += 1

    if added:
        save_tracker(data)

    return added, skipped


# ── Result entry ──────────────────────────────────────────────────────────────

def set_result(pick_id: str, result: str | None) -> bool:
    """
    Set result for a pick: 'W', 'L', 'P', or None to move back to pending.
    Returns True if the pick was found and saved.
    """
    data = load_tracker()
    for pick in data["picks"]:
        if pick.get("pick_id") == pick_id:
            pick["result"]     = result
            pick["settled_at"] = datetime.now().isoformat() if result else None
            return save_tracker(data)
    return False


def delete_pick(pick_id: str) -> bool:
    """Remove a pick from the tracker. Returns True if removed."""
    data   = load_tracker()
    before = len(data["picks"])
    data["picks"] = [p for p in data["picks"] if p.get("pick_id") != pick_id]
    if len(data["picks"]) < before:
        return save_tracker(data)
    return False


# ── P&L math ─────────────────────────────────────────────────────────────────

def _payout_units(odds_str: str, units: float = 1.0) -> float:
    """Profit (in units) for a winning bet at the given American odds string."""
    s = (odds_str or "").strip().replace(",", "")
    try:
        n = int(s.lstrip("+"))
        if n > 0 or s.startswith("+"):
            return units * n / 100
        return units * 100 / abs(n)
    except (ValueError, ZeroDivisionError):
        return units  # fallback: even money


def compute_pnl(picks: list) -> dict:
    """Return a stats dict: record, net units, ROI, win rate, breakdown by type."""
    settled = [p for p in picks if p.get("result") in ("W", "L", "P")]
    pending = [p for p in picks if not p.get("result")]
    wins    = [p for p in settled if p["result"] == "W"]
    losses  = [p for p in settled if p["result"] == "L"]
    pushes  = [p for p in settled if p["result"] == "P"]

    units_won    = sum(_payout_units(p.get("odds_str", ""), p.get("units_bet", 1.0)) for p in wins)
    units_lost   = sum(p.get("units_bet", 1.0) for p in losses)
    units_risked = sum(p.get("units_bet", 1.0) for p in wins + losses)
    net          = round(units_won - units_lost, 2)
    roi          = round(net / units_risked * 100, 1) if units_risked > 0 else 0.0

    # Breakdown by type
    def _sub(subset):
        w = [p for p in subset if p.get("result") == "W"]
        l = [p for p in subset if p.get("result") == "L"]
        won  = sum(_payout_units(p.get("odds_str",""), p.get("units_bet",1.0)) for p in w)
        lost = sum(p.get("units_bet", 1.0) for p in l)
        return {"wins": len(w), "losses": len(l), "net": round(won - lost, 2)}

    game_picks = [p for p in settled if p.get("type") == "game"]
    prop_picks = [p for p in settled if p.get("type") == "prop"]

    return {
        "total":        len(picks),
        "settled":      len(settled),
        "pending":      len(pending),
        "wins":         len(wins),
        "losses":       len(losses),
        "pushes":       len(pushes),
        "units_won":    round(units_won, 2),
        "units_lost":   round(units_lost, 2),
        "net_units":    net,
        "units_risked": round(units_risked, 2),
        "roi_pct":      roi,
        "win_rate":     round(len(wins) / max(len(wins) + len(losses), 1) * 100, 1),
        "by_game":      _sub(game_picks),
        "by_prop":      _sub(prop_picks),
    }
