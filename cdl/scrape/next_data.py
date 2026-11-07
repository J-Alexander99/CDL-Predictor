"""Extract and validate the ``__NEXT_DATA__`` payload of breakingpoint.gg pages.

The site's schema can change at any time. Everything we depend on is declared
in the pydantic models below, so a breaking change fails loudly with a
:class:`SchemaError` naming the page, instead of silently producing bad data.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

RAW_SCHEMA_VERSION = 1

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class SchemaError(RuntimeError):
    """The site no longer looks like what the scraper expects."""


def extract_next_data(html: str, source: str = "?") -> dict:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise SchemaError(f"{source}: no __NEXT_DATA__ script found (site layout changed?)")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{source}: __NEXT_DATA__ is not valid JSON: {exc}") from exc


def page_props(next_data: dict, source: str = "?") -> dict:
    try:
        return next_data["props"]["pageProps"]
    except (KeyError, TypeError) as exc:
        raise SchemaError(f"{source}: missing props.pageProps") from exc


def trpc_query(props: dict, name: str) -> Any:
    """Return the data of a dehydrated tRPC query whose key ends with ``name``."""
    for q in props.get("trpcState", {}).get("json", {}).get("queries", []):
        key = q.get("queryKey") or [[]]
        if key and key[0] and key[0][-1] == name:
            data = q.get("state", {}).get("data")
            if isinstance(data, dict) and "data" in data and "error" in data:
                return data["data"]
            return data
    return None


# --------------------------------------------------------------------------
# Validated raw record (what we store in data/raw)
# --------------------------------------------------------------------------
class _Model(BaseModel):
    model_config = ConfigDict(extra="allow")


class RawTeam(_Model):
    id: int
    name: str
    name_short: str | None = None
    logo_main: str | None = None
    color_hex: str | None = None


class RawPlayerStat(_Model):
    player_id: int
    player_tag: str
    team_id: int
    kills: int
    deaths: int
    assists: int | None = None
    damage: int | None = None
    bp_rating: float | None = None


class RawGame(_Model):
    game_num: int
    map_id: int | None
    map: str | None
    mode_id: int
    mode: str
    team_1_id: int
    team_2_id: int
    winner_id: int | None
    team_1_score: int | None
    team_2_score: int | None
    duration_s: int | None = None
    players: list[RawPlayerStat]


class RawVeto(_Model):
    team_id: int | None
    mode_id: int | None
    map_id: int | None
    map: str | None = None
    action: str
    order: int | None = None


class RawEvent(_Model):
    id: int
    name: str
    season_id: int
    division_id: int | None = None
    lan: bool | None = None


class RawMatch(_Model):
    schema_version: int
    scraped_at: str
    id: int
    status: str
    datetime: str
    best_of: int | None
    team_1_id: int
    team_2_id: int
    winner_id: int | None
    team_1_score: int | None
    team_2_score: int | None
    round: str | None = None
    round_stage: str | None = None
    event: RawEvent
    teams: list[RawTeam]
    games: list[RawGame]
    vetoes: list[RawVeto] = []


_TEAM_KEYS = ("id", "name", "name_short", "logo_main", "color_hex")
_PLAYER_DROP = {
    "id", "game_id", "created_at", "updated_at", "deleted_at", "datetime", "event_id",
    "match_id", "season_id", "map_id", "mode_id", "spreadsheet_identifier", "stats",
    "data_count", "event_type", "gametime_min", "gametime_sec",
}


def _game_duration(g: dict) -> int | None:
    mins, secs = g.get("gametime_min"), g.get("gametime_sec")
    if mins is None and secs is None:
        return None
    return int(mins or 0) * 60 + int(secs or 0)


def trim_match(next_data: dict, source: str = "?") -> dict:
    """Reduce a match page payload to the stable, useful core and validate it."""
    props = page_props(next_data, source)
    m = props.get("initialMatchState")
    if not isinstance(m, dict) or "games" not in m:
        raise SchemaError(f"{source}: initialMatchState missing or has no games")

    ev = m.get("events") or {}
    games_raw = m.get("games") or []
    event_types = {
        ps.get("event_type") for g in games_raw for ps in (g.get("player_stats") or []) if ps.get("event_type")
    }
    lan = None
    if event_types:
        lan = "Offline" in event_types or "LAN" in event_types

    map_names = {mp.get("id"): mp.get("name") for mp in (trpc_query(props, "fetchMapsForEvent") or [])}
    for g in games_raw:
        if g.get("map_id") is not None and (g.get("maps") or {}).get("name"):
            map_names.setdefault(g["map_id"], g["maps"]["name"])

    games = []
    for g in sorted(games_raw, key=lambda x: x.get("game_num") or 0):
        if g.get("mode_id") is None:
            continue  # placeholder for a map that was never played (e.g. forfeits)
        players = []
        for ps in g.get("player_stats") or []:
            if ps.get("deleted_at"):
                continue
            players.append({k: v for k, v in ps.items() if k not in _PLAYER_DROP})
        games.append(
            {
                "game_num": g.get("game_num"),
                "map_id": g.get("map_id"),
                "map": (g.get("maps") or {}).get("name"),
                "mode_id": g.get("mode_id"),
                "mode": (g.get("modes") or {}).get("name"),
                "team_1_id": g.get("team_1_id"),
                "team_2_id": g.get("team_2_id"),
                "winner_id": g.get("winner_id"),
                "team_1_score": g.get("team_1_score"),
                "team_2_score": g.get("team_2_score"),
                "duration_s": _game_duration(g),
                "players": players,
            }
        )

    vetoes = []
    for v in trpc_query(props, "fetchMapPicksAndVetoes") or []:
        vetoes.append(
            {
                "team_id": v.get("team_id"),
                "mode_id": v.get("mode_id"),
                "map_id": v.get("map_id"),
                "map": map_names.get(v.get("map_id")),
                "action": v.get("action"),
                "order": v.get("order"),
                "map_number": v.get("map_number"),
            }
        )

    rnd = m.get("round") or {}
    record = {
        "schema_version": RAW_SCHEMA_VERSION,
        "scraped_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "id": m.get("id"),
        "status": m.get("status"),
        "datetime": m.get("datetime"),
        "completed_at": m.get("completed_at"),
        "best_of": m.get("best_of"),
        "team_1_id": m.get("team_1_id"),
        "team_2_id": m.get("team_2_id"),
        "winner_id": m.get("winner_id"),
        "team_1_score": m.get("team_1_score"),
        "team_2_score": m.get("team_2_score"),
        "is_tiebreaker": m.get("is_tiebreaker"),
        "round": rnd.get("name"),
        "round_stage": rnd.get("stage"),
        "event": {
            "id": ev.get("id", m.get("event_id")),
            "name": ev.get("name"),
            "season_id": ev.get("season_id") or (ev.get("seasons") or {}).get("id"),
            "division_id": ev.get("division_id"),
            "lan": lan,
        },
        "teams": [
            {k: t.get(k) for k in _TEAM_KEYS} for t in (m.get("team1"), m.get("team2")) if isinstance(t, dict)
        ],
        "games": games,
        "vetoes": vetoes,
    }
    validate_match(record, source)
    return record


def _active_players(team: dict) -> list[dict]:
    """Players only: excludes coaches, content creators, streamers, retired members."""
    players = []
    for p in team.get("players") or []:
        role = ((p.get("role") or {}).get("role") or "").lower()
        if p.get("retired") or not ("player" in role or "sub" in role):
            continue
        players.append({"id": p["id"], "tag": p.get("tag"), "role": role})
    return players


def parse_rosters(next_data: dict) -> dict[int, list[dict]]:
    """Rosters of both teams embedded in a match page."""
    props = page_props(next_data)
    out: dict[int, list[dict]] = {}
    for q in props.get("trpcState", {}).get("json", {}).get("queries", []):
        key = q.get("queryKey") or [[]]
        if not (key and key[0] and key[0][-1] == "fetchTeamWithPlayers"):
            continue
        data = q.get("state", {}).get("data") or {}
        team = data.get("data", data) if isinstance(data, dict) else {}
        if not team or "id" not in team:
            continue
        out[int(team["id"])] = _active_players(team)
    return out


def parse_team_roster(next_data: dict, team_id: int) -> list[dict]:
    """Current roster from a ``/teams/{id}`` page."""
    team = page_props(next_data, f"/teams/{team_id}").get("team")
    if not isinstance(team, dict):
        raise SchemaError(f"/teams/{team_id}: pageProps.team missing")
    return _active_players(team)


def validate_match(record: dict, source: str = "?") -> RawMatch:
    try:
        return RawMatch.model_validate(record)
    except ValidationError as exc:
        raise SchemaError(f"{source}: match payload failed validation:\n{exc}") from exc
