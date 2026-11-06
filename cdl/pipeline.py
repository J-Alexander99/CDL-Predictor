"""High-level operations shared by the CLI and the scheduled GitHub Action."""
from __future__ import annotations

import difflib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from cdl import config
from cdl.model.features import Engine, replay
from cdl.model.map_model import MapModel
from cdl.model.ratings import RatingParams
from cdl.model.series import SeriesPredictor
from cdl.scrape import discover
from cdl.store import db

log = logging.getLogger(__name__)

PARAMS = RatingParams()
MODEL_KWARGS: dict = {"C": 0.5, "half_life_days": 720.0}  # chosen by walk-forward backtest
MODEL_VERSION = "3.0"


@dataclass
class Bundle:
    frames: db.Frames
    engine: Engine
    model: MapModel
    predictor: SeriesPredictor
    dataset: pd.DataFrame
    season_modes: dict[int, list[str]]
    current_rosters: dict[int, list[dict]]

    def roster(self, team_id: int, listed: list[dict] | None = None) -> list[int]:
        return choose_roster(self, team_id, listed if listed else self.current_rosters.get(team_id))

    def team(self, team_id: int) -> dict:
        row = self.frames.teams.loc[self.frames.teams.id == team_id]
        if not len(row):
            return {"id": team_id, "name": f"Team {team_id}", "short": None, "logo": None}
        r = row.iloc[0]
        clean = lambda v: None if v is None or (isinstance(v, float) and v != v) else v  # noqa: E731
        return {"id": int(team_id), "name": r["name"], "short": clean(r["name_short"]), "logo": clean(r["logo"])}

    def player_tag(self, pid: int) -> str:
        row = self.frames.player_tags.loc[self.frames.player_tags.id == pid]
        return row.tag.iloc[0] if len(row) else str(pid)


def season_modes() -> dict[int, list[str]]:
    return {s["id"]: s["modes"] for s in discover.load_catalog()["seasons"]}


def build_bundle() -> Bundle:
    frames = db.load()
    modes = season_modes()
    engine, dataset = replay(frames, PARAMS)
    model = MapModel(**MODEL_KWARGS).fit(dataset)
    return Bundle(frames, engine, model, SeriesPredictor(engine, model, frames, modes), dataset, modes,
                  discover.load_rosters())


def current_season(bundle: Bundle) -> int:
    cat = discover.load_catalog()
    today = datetime.now(timezone.utc).date().isoformat()
    for s in sorted(cat["seasons"], key=lambda s: -s["id"]):
        if s.get("start_date") and s["start_date"] <= today:
            return int(s["id"])
    return int(bundle.frames.matches.season_id.max())


def resolve_team(bundle: Bundle, query: str) -> int:
    """Fuzzy team lookup by name, short name or id; prefers teams active recently."""
    if query.isdigit():
        return int(query)
    teams = bundle.frames.teams
    recent = set(bundle.frames.matches.tail(300)[["team_1_id", "team_2_id"]].to_numpy().ravel())
    q = query.lower().strip()
    cands = []
    for r in teams.itertuples(index=False):
        names = [str(r.name).lower()] + ([str(r.name_short).lower()] if r.name_short else [])
        score = max(
            1.0 if q == n else 0.9 if q in n.split() else 0.8 if q in n else difflib.SequenceMatcher(None, q, n).ratio()
            for n in names
        )
        cands.append((score + (0.05 if r.id in recent else 0.0), int(r.id), r.name))
    cands.sort(reverse=True)
    if not cands or cands[0][0] < 0.6:
        raise ValueError(f"No team matches {query!r}")
    return cands[0][1]


def choose_roster(bundle: Bundle, team_id: int, listed: list[dict] | None) -> list[int]:
    """Pick four starters from a listed roster, falling back to the last lineup played.

    Players from the last lineup who are now listed on another team are never used.
    """
    elsewhere = {p["id"] for tid, ps in bundle.current_rosters.items() if tid != team_id for p in ps}
    last = [p for p in bundle.engine.roster_for(team_id) if p not in elsewhere]
    if not listed:
        return last
    ids = [p["id"] for p in listed]
    if len(ids) <= 4:
        extra = [p for p in last if p not in ids]
        return (ids + extra)[:4]
    games = bundle.engine.ratings.players.games
    ids.sort(key=lambda pid: (pid in last, games.get(pid, 0)), reverse=True)
    return ids[:4]


def predict_match(bundle: Bundle, ref: dict, rosters: dict[int, list[dict]] | None = None) -> dict:
    t1, t2 = int(ref["team_1_id"]), int(ref["team_2_id"])
    rosters = rosters or {}
    r1 = bundle.roster(t1, rosters.get(t1))
    r2 = bundle.roster(t2, rosters.get(t2))
    season = int(ref.get("season_id") or current_season(bundle))
    pred = bundle.predictor.predict(t1, t2, season, int(ref.get("best_of") or 5), r1, r2)
    team1, team2 = bundle.team(t1), bundle.team(t2)
    if ref.get("team_1_name"):
        team1["name"] = ref["team_1_name"]
    if ref.get("team_2_name"):
        team2["name"] = ref["team_2_name"]
    a, b = (int(x) for x in pred["likely_score"].split("-"))
    winner = team1["name"] if a > b else team2["name"]
    return {
        "match_id": int(ref.get("id") or 0),
        "datetime": ref.get("datetime") or datetime.now(timezone.utc).isoformat(),
        "season": season,
        "event_id": ref.get("event_id"),
        "event_name": ref.get("event_name"),
        "round": ref.get("round"),
        "best_of": pred["best_of"],
        "team1": team1,
        "team2": team2,
        "p_team1": round(pred["p_team1"], 4),
        "scores": {k: round(v, 4) for k, v in pred["scores"].items()},
        "likely_score": pred["likely_score"],
        "likely_score_label": f"{max(a, b)}-{min(a, b)} {winner}",
        "slots": [
            {**s, "p_team1": round(s["p_team1"], 4),
             "map_options": [{"map": o["map"], "prob": round(o["prob"], 3)} for o in s["map_options"]]}
            for s in pred["slots"]
        ],
        "modes": {k: round(v, 4) for k, v in pred["modes"].items()},
        "ratings": pred["ratings"],
        "rosters": {side: [bundle.player_tag(p) for p in ids] for side, ids in pred["rosters"].items()},
        "tendencies": pred["tendencies"],
        "model_version": MODEL_VERSION,
    }


def upcoming_in_horizon(now: datetime, hours: int = config.PREDICTION_HORIZON_H) -> list[dict]:
    index = discover.load_event_index()
    end = now + timedelta(hours=hours)
    out = []
    for m in discover.upcoming_matches(index):
        if m["status"] != "upcoming" or not m["datetime"]:
            continue
        dt = datetime.fromisoformat(m["datetime"].replace("Z", "+00:00"))
        if now - timedelta(hours=6) < dt <= end:  # still "upcoming" after its slot = delayed
            out.append(m)
    return out


def results_by_match(bundle: Bundle) -> dict[int, dict]:
    m = bundle.frames.matches
    return {
        int(r.id): {"winner_id": None if pd.isna(r.winner_id) else int(r.winner_id), "team_1_id": int(r.team_1_id),
                    "team_1_score": r.team_1_score, "team_2_score": r.team_2_score,
                    "datetime": r.datetime.isoformat()}
        for r in m.itertuples(index=False)
    }


def power_rankings(bundle: Bundle, season: int, min_maps: int = 1) -> list[dict]:
    eng = bundle.engine
    m = bundle.frames.matches
    m = m[m.season_id == season]
    # The site's team catalog is the current CDL franchise list; fall back to who played.
    franchise = {int(t["id"]) for t in discover.load_catalog().get("teams", [])}
    if season == current_season(bundle) and franchise:
        teams = franchise
        min_maps = 0
    else:
        teams = set(m.team_1_id) | set(m.team_2_id)
    modes = bundle.season_modes.get(season, [])
    rows = []
    for t in teams:
        t = int(t)
        played = m[(m.team_1_id == t) | (m.team_2_id == t)]
        wins = int((played.winner_id == t).sum())
        maps = eng.season_team_maps.get((season, t), 0)
        if maps < min_maps and len(m):
            continue
        roster = bundle.roster(t)
        rows.append({
            **bundle.team(t),
            "rating": round(eng.ratings.strength(t, roster), 1),
            "modes": {md: round(eng.ratings.strength(t, roster, md), 1) for md in modes},
            "record": f"{wins}-{len(played) - wins}",
            "roster": [bundle.player_tag(p) for p in roster],
            "maps": maps,
        })
    rows.sort(key=lambda r: -r["rating"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
