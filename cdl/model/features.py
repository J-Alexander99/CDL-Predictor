"""Point-in-time features.

The :class:`Engine` replays history match by match. Features for every map of
a match are computed from the state *before the match starts* and only then is
the state updated, so training rows never contain information from the future
(and never from earlier maps of the same series). The same engine state is
used to predict upcoming matches.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import pandas as pd

from cdl.model.ratings import RatingParams, RatingSystem

FEATURES = ["team_diff", "roster_diff", "form_diff", "bp_diff", "map_diff"]
_FORM_ALPHA = 0.12
_BP_ALPHA = 0.15
_BP_DEFAULT = 0.95


@dataclass
class GameRow:
    game_num: int
    mode: str
    map: str | None
    t1_won: bool
    s1: int | None
    s2: int | None


@dataclass
class MatchCtx:
    match_id: int
    datetime: pd.Timestamp
    season: int
    event_id: int
    lan: bool
    best_of: int | None
    t1: int
    t2: int
    roster1: list[int]
    roster2: list[int]
    games: list[GameRow] = field(default_factory=list)
    player_rows: list[dict] = field(default_factory=list)
    t1_won: bool | None = None


def iter_matches(frames) -> Iterator[MatchCtx]:
    games_by_match = {mid: g for mid, g in frames.games.groupby("match_id", sort=False)}
    players_by_match = {mid: p for mid, p in frames.players.groupby("match_id", sort=False)}
    for m in frames.matches.itertuples(index=False):
        g = games_by_match.get(m.id)
        if g is None or g.empty:
            continue
        p = players_by_match.get(m.id)
        rosters = {m.team_1_id: [], m.team_2_id: []}
        rows = []
        if p is not None:
            for tid in rosters:
                counts = p.loc[p.team_id == tid, "player_id"].value_counts()
                rosters[tid] = [int(x) for x in counts.index[:4]]
            rows = p.to_dict("records")
        ctx = MatchCtx(
            match_id=int(m.id), datetime=m.datetime, season=int(m.season_id), event_id=int(m.event_id),
            lan=bool(m.lan) if m.lan == m.lan and m.lan is not None else False,
            best_of=None if pd.isna(m.best_of) else int(m.best_of),
            t1=int(m.team_1_id), t2=int(m.team_2_id),
            roster1=rosters[m.team_1_id], roster2=rosters[m.team_2_id],
            player_rows=rows,
            t1_won=None if pd.isna(m.winner_id) else int(m.winner_id) == int(m.team_1_id),
        )
        for r in g.itertuples(index=False):
            if pd.isna(r.winner_id):
                continue
            s1 = None if pd.isna(r.team_1_score) else int(r.team_1_score)
            s2 = None if pd.isna(r.team_2_score) else int(r.team_2_score)
            if int(r.team_1_id) != int(m.team_1_id):  # game listed from the other side
                s1, s2 = s2, s1
            ctx.games.append(
                GameRow(
                    game_num=int(r.game_num), mode=r.mode, map=r.map,
                    t1_won=int(r.winner_id) == int(m.team_1_id), s1=s1, s2=s2,
                )
            )
        if ctx.games:
            yield ctx


class Engine:
    def __init__(self, params: RatingParams | None = None):
        self.ratings = RatingSystem(params)
        self.form: dict[int, float] = {}
        self.bp: dict[int, dict[str | None, float]] = defaultdict(dict)
        self.map_rec: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        self.mode_rec: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        self.last_roster: dict[int, list[int]] = {}
        self.last_played: dict[int, pd.Timestamp] = {}
        self.season_team_maps: dict[tuple, int] = defaultdict(int)

    # ---- features ----------------------------------------------------------
    def _bp(self, roster: list[int], mode: str) -> float:
        if not roster:
            return _BP_DEFAULT
        vals = []
        for pid in roster:
            d = self.bp.get(pid, {})
            vals.append(d.get(mode, d.get(None, _BP_DEFAULT)))
        return sum(vals) / len(vals)

    def _map_spec(self, season: int, team: int, mode: str, map_name: str | None) -> float:
        if map_name is None:
            return 0.0
        w, n = self.map_rec[(season, team, mode, map_name)]
        mw, mn = self.mode_rec[(season, team, mode)]
        return (w + 1) / (n + 2) - (mw + 1) / (mn + 2)

    def features(
        self, season: int, t1: int, t2: int, roster1: list[int], roster2: list[int], mode: str, map_name: str | None
    ) -> dict[str, float]:
        R = self.ratings
        team_diff = (R.team(t1, mode) - R.team(t2, mode)) / 100.0
        r1, r2 = R.roster(roster1, mode), R.roster(roster2, mode)
        roster_diff = team_diff if r1 is None or r2 is None else (r1 - r2) / 100.0
        return {
            "team_diff": team_diff,
            "roster_diff": roster_diff,
            "form_diff": self.form.get(t1, 0.5) - self.form.get(t2, 0.5),
            "bp_diff": self._bp(roster1, mode) - self._bp(roster2, mode),
            "map_diff": self._map_spec(season, t1, mode, map_name) - self._map_spec(season, t2, mode, map_name),
        }

    def roster_for(self, team: int) -> list[int]:
        return self.last_roster.get(team, [])

    # ---- state updates -----------------------------------------------------
    def update(self, ctx: MatchCtx) -> None:
        R = self.ratings
        R.start_match(ctx.season, [ctx.t1, ctx.t2], [ctx.roster1, ctx.roster2])
        for g in ctx.games:
            R.update_game(g.mode, ctx.t1, ctx.t2, ctx.roster1, ctx.roster2, g.t1_won, g.s1, g.s2)
            for team, won in ((ctx.t1, g.t1_won), (ctx.t2, not g.t1_won)):
                self.form[team] = (1 - _FORM_ALPHA) * self.form.get(team, 0.5) + _FORM_ALPHA * float(won)
                mr = self.mode_rec[(ctx.season, team, g.mode)]
                mr[0] += int(won)
                mr[1] += 1
                if g.map:
                    rec = self.map_rec[(ctx.season, team, g.mode, g.map)]
                    rec[0] += int(won)
                    rec[1] += 1
                self.season_team_maps[(ctx.season, team)] += 1
        modes = {g.game_num: g.mode for g in ctx.games}
        for row in ctx.player_rows:
            bp = row.get("bp_rating")
            if bp is None or bp != bp:
                continue
            d = self.bp[int(row["player_id"])]
            for key in (modes.get(int(row["game_num"])), None):
                d[key] = (1 - _BP_ALPHA) * d.get(key, _BP_DEFAULT) + _BP_ALPHA * float(bp)
        for team, roster in ((ctx.t1, ctx.roster1), (ctx.t2, ctx.roster2)):
            if roster:
                self.last_roster[team] = roster
            self.last_played[team] = ctx.datetime


def replay(
    frames,
    params: RatingParams | None = None,
    on_match: Callable[[Engine, MatchCtx], None] | None = None,
) -> tuple[Engine, pd.DataFrame]:
    """Replay all history. Returns the final engine and one feature row per map."""
    eng = Engine(params)
    rows = []
    for ctx in iter_matches(frames):
        if on_match:
            on_match(eng, ctx)
        for g in ctx.games:
            f = eng.features(ctx.season, ctx.t1, ctx.t2, ctx.roster1, ctx.roster2, g.mode, g.map)
            rows.append({
                "match_id": ctx.match_id, "datetime": ctx.datetime, "season": ctx.season,
                "event_id": ctx.event_id, "game_num": g.game_num, "mode": g.mode, "map": g.map,
                "t1": ctx.t1, "t2": ctx.t2, "y": int(g.t1_won), **f,
            })
        eng.update(ctx)
    return eng, pd.DataFrame(rows)
