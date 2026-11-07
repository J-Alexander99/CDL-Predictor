"""Build the SQLite database from the committed raw data, and load it for modelling."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import pandas as pd

from cdl import config
from cdl.scrape import discover
from cdl.store import raw

_CORE_STATS = (
    "kills", "deaths", "assists", "damage", "bp_rating", "non_traded_kills", "highest_streak",
    "hill_time", "contested_hill_time", "first_blood_count", "first_death_count",
    "plant_count", "defuse_count", "snd_rounds",
)
_SKIP = {"player_id", "player_tag", "team_id", *_CORE_STATS}


def build(db_path: Path | None = None, raw_root: Path | None = None) -> dict:
    """(Re)create the database. Returns row counts."""
    db_path = db_path or config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)

    con = sqlite3.connect(tmp)
    con.executescript(resources.files("cdl.store").joinpath("schema.sql").read_text())

    catalog = discover.load_catalog()
    index = discover.load_event_index()
    con.executemany(
        "INSERT INTO seasons VALUES (?,?,?,?)",
        [(s["id"], s["title"], s["title_short"], json.dumps(s["modes"])) for s in catalog["seasons"]],
    )

    teams: dict[int, tuple] = {}
    players: dict[int, str] = {}
    events: dict[int, tuple] = {}
    mode_names: dict[int, str] = {}
    records = sorted(raw.iter_all(raw_root), key=lambda r: (r["datetime"], r["id"]))

    for r in records:
        for g in r["games"]:
            if g.get("mode_id") is not None and g.get("mode"):
                mode_names[g["mode_id"]] = g["mode"]

    for r in records:
        ev = r["event"]
        meta = index.get(str(ev["id"]), {})
        lan = ev.get("lan")
        if lan is None and meta.get("type"):
            lan = meta["type"].lower() in ("offline", "lan")
        events[ev["id"]] = (
            ev["id"], ev.get("name") or meta.get("name") or "?", ev["season_id"], meta.get("tier"),
            meta.get("type"), None if lan is None else int(lan), meta.get("start_date"), meta.get("end_date"),
        )
        for t in r["teams"]:  # later records overwrite earlier ones -> latest branding wins
            teams[t["id"]] = (t["id"], t["name"], t.get("name_short"), t.get("logo_main"), t.get("color_hex"))
        division = ev.get("division_id") or meta.get("division_id") or config.CDL_DIVISION_ID
        con.execute(
            "INSERT INTO matches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["id"], ev["id"], ev["season_id"], r["datetime"], r.get("best_of"), r["team_1_id"],
             r["team_2_id"], r.get("winner_id"), r.get("team_1_score"), r.get("team_2_score"),
             r.get("round"), r.get("round_stage"), None if lan is None else int(lan), division),
        )
        for g in r["games"]:
            if not g.get("mode"):
                continue
            con.execute(
                "INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["id"], g["game_num"], g["mode"], g.get("map"), g["team_1_id"], g["team_2_id"],
                 g.get("winner_id"), g.get("team_1_score"), g.get("team_2_score"), g.get("duration_s")),
            )
            for p in g["players"]:
                players[p["player_id"]] = p["player_tag"]
                extra = {k: v for k, v in p.items() if k not in _SKIP and v not in (None, 0)}
                con.execute(
                    f"INSERT OR IGNORE INTO player_game_stats VALUES ({','.join('?' * (5 + len(_CORE_STATS)))})",
                    (r["id"], g["game_num"], p["player_id"], p["team_id"],
                     *(p.get(k) for k in _CORE_STATS), json.dumps(extra) if extra else None),
                )
        for v in r.get("vetoes", []):
            con.execute(
                "INSERT INTO vetoes VALUES (?,?,?,?,?,?,?)",
                (r["id"], v.get("order"), v.get("team_id"), mode_names.get(v.get("mode_id")), v.get("map"),
                 v.get("action"), v.get("map_number")),
            )

    # Teams that only appear in upcoming fixtures / catalog
    for t in catalog["teams"]:
        teams.setdefault(t["id"], (t["id"], t["name"], t.get("name_short"), t.get("logo_main"), t.get("color_hex")))
    for ev in discover.cdl_events(index):
        for m in ev.get("matches", []):
            for side in ("1", "2"):
                tid, name = m.get(f"team_{side}_id"), m.get(f"team_{side}_name")
                if tid and name:
                    teams.setdefault(tid, (tid, name, None, None, None))

    con.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)", events.values())
    con.executemany("INSERT INTO teams VALUES (?,?,?,?,?)", teams.values())
    con.executemany("INSERT INTO players VALUES (?,?)", players.items())
    con.commit()
    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("matches", "games", "player_game_stats", "vetoes", "teams", "players")
    }
    con.close()
    tmp.replace(db_path)
    return counts


@dataclass
class Frames:
    matches: pd.DataFrame
    games: pd.DataFrame
    players: pd.DataFrame  # player_game_stats
    vetoes: pd.DataFrame
    teams: pd.DataFrame
    events: pd.DataFrame
    seasons: pd.DataFrame
    player_tags: pd.DataFrame

    def team_name(self, team_id: int) -> str:
        row = self.teams.loc[self.teams.id == team_id]
        return row.name.iloc[0] if len(row) else f"Team {team_id}"


def load(db_path: Path | None = None, divisions: tuple[int, ...] = (config.CDL_DIVISION_ID,)) -> Frames:
    """Load the modelling frames. Defaults to CDL matches only; Challengers data is
    stored but excluded until there is enough of it to be useful."""
    con = sqlite3.connect(db_path or config.DB_PATH)
    div = f"m.division_id IN ({','.join(str(int(d)) for d in divisions)})"
    try:
        q = lambda sql: pd.read_sql_query(sql, con)  # noqa: E731
        matches = q(f"SELECT m.* FROM matches m WHERE {div} ORDER BY m.datetime, m.id")
        games = q(
            "SELECT g.*, m.datetime, m.season_id, m.event_id, m.lan, m.best_of FROM games g "
            f"JOIN matches m ON m.id = g.match_id WHERE {div} ORDER BY m.datetime, g.match_id, g.game_num"
        )
        players = q(
            "SELECT s.*, m.datetime, m.season_id, g.mode, g.map FROM player_game_stats s "
            "JOIN matches m ON m.id = s.match_id JOIN games g ON g.match_id = s.match_id AND g.game_num = s.game_num "
            f"WHERE {div}"
        )
        frames = Frames(
            matches=matches,
            games=games,
            players=players,
            vetoes=q(f"SELECT v.*, m.datetime, m.season_id FROM vetoes v JOIN matches m ON m.id = v.match_id WHERE {div}"),
            teams=q("SELECT * FROM teams"),
            events=q("SELECT * FROM events"),
            seasons=q("SELECT * FROM seasons"),
            player_tags=q("SELECT * FROM players"),
        )
    finally:
        con.close()
    for df in (frames.matches, frames.games, frames.players, frames.vetoes):
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True, format="ISO8601")
    return frames
