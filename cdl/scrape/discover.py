"""Discover CDL events and matches without any hand-maintained URL list.

1. ``/matches`` embeds the full catalog: seasons (with their mode sets),
   every event (id, name, season) and the current teams.
2. Each event page lists all of its matches (complete, live and upcoming).
   CDL events are those with ``division_id == 3``.

Both are cached in ``data/meta``. Events that are over and fully complete are
"final" and never fetched again, so routine runs make only a few requests.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cdl import config
from cdl.scrape.client import BreakingPointClient
from cdl.scrape.next_data import SchemaError, page_props

log = logging.getLogger(__name__)

# Event-name prefixes that are never CDL league events (saves ~80 requests/season)
_NON_CDL_PREFIXES = ("CDC ", "Challengers", "Challenger ")


def _collects_challengers(season_id: int | None) -> bool:
    return season_id is not None and season_id >= config.CHALLENGERS_FROM_SEASON


def _collected(ev: dict) -> bool:
    """Events whose matches we track: all CDL events, plus Challengers from the cutoff season."""
    div = ev.get("division_id")
    return div == config.CDL_DIVISION_ID or (
        div == config.CHALLENGERS_DIVISION_ID and _collects_challengers(ev.get("season_id"))
    )
_EVENT_WINDOW_BEFORE = timedelta(days=10)
_EVENT_WINDOW_AFTER = timedelta(days=3)


def _read_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def catalog_path() -> Path:
    return config.META_DIR / "catalog.json"


def event_index_path() -> Path:
    return config.META_DIR / "events.json"


def load_catalog() -> dict:
    return _read_json(catalog_path(), {"seasons": [], "events": [], "teams": []})


def load_event_index() -> dict[str, dict]:
    return _read_json(event_index_path(), {})


# --------------------------------------------------------------------------
def parse_catalog(next_data: dict) -> dict:
    props = page_props(next_data, "/matches")
    for key in ("allSeasons", "allEvents", "allTeams"):
        if not isinstance(props.get(key), list):
            raise SchemaError(f"/matches: pageProps.{key} missing")
    seasons = [
        {
            "id": s["id"],
            "year": s.get("year"),
            "title": (s.get("title") or {}).get("name"),
            "title_short": (s.get("title") or {}).get("name_short"),
            "start_date": s.get("start_date"),
            "end_date": s.get("end_date"),
            "modes": sorted(
                (sm.get("modes") or {}).get("name")
                for sm in s.get("season_modes") or []
                if (sm.get("modes") or {}).get("name")
            ),
        }
        for s in props["allSeasons"]
    ]
    events = [
        {"id": e["id"], "name": (e.get("name") or "").strip(), "season_id": e.get("season_id"), "end_date": e.get("end_date")}
        for e in props["allEvents"]
    ]
    teams = [
        {k: t.get(k) for k in ("id", "name", "name_short", "logo_main", "color_hex")} for t in props["allTeams"]
    ]
    return {
        "seasons": sorted(seasons, key=lambda s: s["id"]),
        "events": sorted(events, key=lambda e: e["id"]),
        "teams": sorted(teams, key=lambda t: t["id"]),
    }


def parse_event(next_data: dict, event_id: int) -> dict:
    props = page_props(next_data, f"/events/{event_id}")
    ev = props.get("event")
    if not isinstance(ev, dict) or not isinstance(props.get("matches"), list):
        raise SchemaError(f"/events/{event_id}: missing event or matches")
    teams = {t["id"]: t.get("name") for t in props.get("teams") or [] if t.get("id") is not None}
    matches = []
    for m in props["matches"]:
        if m.get("deleted_at"):
            continue
        t1, t2 = m.get("team1") or {}, m.get("team2") or {}
        matches.append(
            {
                "id": m["id"],
                "status": m.get("status"),
                "datetime": m.get("datetime"),
                "best_of": m.get("best_of"),
                "team_1_id": m.get("team_1_id"),
                "team_2_id": m.get("team_2_id"),
                "team_1_name": t1.get("name") or teams.get(m.get("team_1_id")),
                "team_2_name": t2.get("name") or teams.get(m.get("team_2_id")),
                "team_1_score": m.get("team_1_score"),
                "team_2_score": m.get("team_2_score"),
                "winner_id": m.get("winner_id"),
                "round": (m.get("round") or {}).get("name"),
            }
        )
    return {
        "id": ev["id"],
        "name": (ev.get("name") or "").strip(),
        "season_id": ev.get("season_id"),
        "division_id": ev.get("division_id"),
        "tier": ev.get("tier"),
        "type": ev.get("type"),
        "start_date": ev.get("start_date"),
        "end_date": ev.get("end_date"),
        "matches": sorted(matches, key=lambda x: (x["datetime"] or "", x["id"])),
    }


# --------------------------------------------------------------------------
def _is_final(ev: dict, today: date) -> bool:
    if not _collected(ev):
        return True  # we only needed its division
    end = ev.get("end_date")
    if not end or date.fromisoformat(end[:10]) + _EVENT_WINDOW_AFTER > today:
        return False
    return all(m["status"] == "complete" for m in ev.get("matches", []))


def _needs_refresh(entry: dict | None, today: date) -> bool:
    if entry is None:
        return True
    if entry.get("final"):
        return False
    start, end = entry.get("start_date"), entry.get("end_date")
    if not start or not end:
        return True
    return (
        date.fromisoformat(start[:10]) - _EVENT_WINDOW_BEFORE
        <= today
        <= date.fromisoformat(end[:10]) + _EVENT_WINDOW_AFTER
    )


def refresh(client: BreakingPointClient, seasons: list[int], force: bool = False, today: date | None = None) -> dict:
    """Update the catalog and event index for ``seasons``. Returns the event index."""
    today = today or datetime.now(timezone.utc).date()
    catalog = parse_catalog(client.matches_page())
    _write_json(catalog_path(), catalog)

    index = load_event_index()
    candidates = [
        e
        for e in catalog["events"]
        if e["season_id"] in seasons
        and (_collects_challengers(e["season_id"]) or not e["name"].startswith(_NON_CDL_PREFIXES))
    ]
    fetched = 0
    for e in candidates:
        key = str(e["id"])
        if not force and not _needs_refresh(index.get(key), today):
            continue
        try:
            ev = parse_event(client.event_page(e["id"]), e["id"])
        except SchemaError:
            raise
        except Exception as exc:  # network trouble on one event shouldn't kill the run
            log.warning("event %s (%s): %s", e["id"], e["name"], exc)
            continue
        fetched += 1
        if not _collected(ev):
            index[key] = {"id": ev["id"], "name": ev["name"], "season_id": ev["season_id"],
                          "division_id": ev["division_id"], "final": True}
            continue
        ev["final"] = _is_final(ev, today)
        index[key] = ev
    log.info("discovery: fetched %d event pages", fetched)
    _write_json(event_index_path(), index)
    return index


def cdl_events(index: dict, seasons: list[int] | None = None) -> list[dict]:
    evs = [
        e for e in index.values()
        if e.get("division_id") == config.CDL_DIVISION_ID and (seasons is None or e.get("season_id") in seasons)
    ]
    return sorted(evs, key=lambda e: (e.get("start_date") or "", e["id"]))


def collected_events(index: dict, seasons: list[int] | None = None) -> list[dict]:
    """CDL events plus the Challengers events we collect."""
    evs = [e for e in index.values() if _collected(e) and (seasons is None or e.get("season_id") in seasons)]
    return sorted(evs, key=lambda e: (e.get("start_date") or "", e["id"]))


def completed_matches(index: dict, seasons: list[int] | None = None, challengers: bool = False) -> list[dict]:
    out = []
    events = collected_events(index, seasons) if challengers else cdl_events(index, seasons)
    for ev in events:
        for m in ev.get("matches", []):
            if m["status"] == "complete":
                out.append({**m, "event_id": ev["id"], "season_id": ev["season_id"]})
    return out


def upcoming_matches(index: dict) -> list[dict]:
    out = []
    for ev in cdl_events(index):
        for m in ev.get("matches", []):
            if m["status"] in ("upcoming", "live") and m["team_1_id"] and m["team_2_id"]:
                out.append({**m, "event_id": ev["id"], "event_name": ev["name"], "season_id": ev["season_id"],
                            "lan": (ev.get("type") or "").lower() in ("offline", "lan")})
    return sorted(out, key=lambda m: (m["datetime"] or "", m["id"]))


# --------------------------------------------------------------------------
def rosters_path() -> Path:
    return config.META_DIR / "rosters.json"


def load_rosters() -> dict[int, list[dict]]:
    data = _read_json(rosters_path(), {"teams": {}})
    return {int(k): v for k, v in data.get("teams", {}).items()}


def refresh_rosters(client: BreakingPointClient, max_age_h: float = 20.0, now: datetime | None = None) -> dict:
    """Current rosters of the franchise teams in the catalog (one page per team, ~daily)."""
    from cdl.scrape.next_data import parse_team_roster

    now = now or datetime.now(timezone.utc)
    data = _read_json(rosters_path(), {"fetched_at": None, "teams": {}})
    fetched = data.get("fetched_at")
    if fetched and now - datetime.fromisoformat(fetched) < timedelta(hours=max_age_h):
        return {int(k): v for k, v in data["teams"].items()}
    teams = {}
    for t in load_catalog()["teams"]:
        try:
            teams[str(t["id"])] = parse_team_roster(client.next_data(f"/teams/{t['id']}"), t["id"])
        except SchemaError:
            raise
        except Exception as exc:
            log.warning("roster for team %s: %s", t["id"], exc)
            if str(t["id"]) in data["teams"]:
                teams[str(t["id"])] = data["teams"][str(t["id"])]
    _write_json(rosters_path(), {"fetched_at": now.replace(microsecond=0).isoformat(), "teams": teams})
    return {int(k): v for k, v in teams.items()}
