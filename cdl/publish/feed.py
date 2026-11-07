"""Machine-readable prediction feed: ``site/api/predictions.json``.

Consumed by other tools (e.g. the Project Clarity Discord bot, which posts the
prediction with its "match starting now" announcement). The shape is versioned
by ``schema``; only add fields, never rename or remove them.

Each match carries the *locked* prediction (the latest snapshot made before
kickoff, the same one that gets graded) and stays in the feed until
``KEEP_AFTER_KICKOFF`` has passed, so a consumer polling around kickoff always
finds it even if the match has already gone live on the site.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from cdl.predictions import ledger

SCHEMA_VERSION = 1
KEEP_AFTER_KICKOFF = timedelta(hours=6)
_MODE_SHORT = {"Hardpoint": "HP", "Search & Destroy": "SnD", "Control": "CTL", "Overload": "OVL", "Hijack": "HJK"}


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _abs(site_url: str, path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http"):
        return path
    return f"{site_url.rstrip('/')}/{path.lstrip('/')}" if site_url else path


def _prediction(e: dict) -> dict:
    p1 = float(e["p_team1"])
    fav, fav_p = (e["team1"], p1) if p1 >= 0.5 else (e["team2"], 1 - p1)
    return {
        "p_team1": round(p1, 4),
        "p_team2": round(1 - p1, 4),
        "favorite_id": fav["id"],
        "favorite": fav["name"],
        "favorite_p": round(fav_p, 4),
        "likely_score": e.get("likely_score"),
        "likely_score_label": e.get("likely_score_label"),
        "scores": e.get("scores", {}),
        "maps": [
            {
                "game_num": s.get("game_num"),
                "mode": s.get("mode"),
                "mode_short": _MODE_SHORT.get(s.get("mode"), s.get("mode")),
                "map": s.get("likely_map"),
                "p_team1": s.get("p_team1"),
            }
            for s in e.get("slots", [])
        ],
        "made_at": e.get("made_at"),
        "model_version": e.get("model_version"),
    }


def build_feed(
    entries: list[dict],
    schedule: dict[int, dict],
    live_summary: dict,
    now: datetime,
    site_url: str = "",
) -> dict:
    """``schedule``: match_id -> {"datetime", "status"} from the current event index."""
    by_match: dict[int, list[dict]] = {}
    for e in entries:
        by_match.setdefault(e["match_id"], []).append(e)

    kickoff: dict[int, str] = {}
    for mid, es in by_match.items():
        current = schedule.get(mid, {}).get("datetime")
        kickoff[mid] = current or max(es, key=lambda x: x["made_at"])["datetime"]
    locked = ledger.latest_by_match(entries, before=kickoff)

    matches = []
    for mid, e in locked.items():
        start = kickoff[mid]
        if _ts(start) < now - KEEP_AFTER_KICKOFF:
            continue
        team = lambda t: {k: t.get(k) for k in ("id", "name", "short", "logo")}  # noqa: E731
        matches.append({
            "match_id": mid,
            "start_utc": start,
            "status": schedule.get(mid, {}).get("status", "upcoming"),
            "event": e.get("event_name"),
            "event_id": e.get("event_id"),
            "round": e.get("round"),
            "best_of": e.get("best_of"),
            "team1": team(e["team1"]),
            "team2": team(e["team2"]),
            "prediction": _prediction(e),
            "graphic_url": _abs(site_url, e.get("graphic")),
            "page_url": f"{site_url.rstrip('/')}/#m{mid}" if site_url else None,
            "match_url": f"https://breakingpoint.gg/match/{mid}/x",
        })
    matches.sort(key=lambda m: (m["start_utc"], m["match_id"]))
    record = {k: live_summary.get(k) for k in ("n", "accuracy", "exact_score") if k in live_summary}
    if "accuracy" in record and record.get("n"):
        record["correct"] = round(record["accuracy"] * record["n"])
    return {
        "schema": SCHEMA_VERSION,
        "generated": now.replace(microsecond=0).isoformat(),
        "site": site_url or None,
        "record": record,
        "matches": matches,
    }


def schedule_from_index(index: dict) -> dict[int, dict]:
    from cdl.scrape import discover

    return {
        m["id"]: {"datetime": m.get("datetime"), "status": m.get("status")}
        for ev in discover.cdl_events(index)
        for m in ev.get("matches", [])
    }
