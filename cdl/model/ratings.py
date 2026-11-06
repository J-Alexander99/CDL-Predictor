"""Map-level Elo ratings for teams *and* players, with per-mode offsets.

Why both:
- Team (org) ratings capture coaching/synergy but reset meaningfully when a
  roster is rebuilt or an org rebrands (new Breaking Point team id).
- Player ratings follow people across teams, so a roster's strength is known
  from day one of a new season even if the org is new.

Each entity has an overall rating plus a small offset per mode (Hardpoint,
Search & Destroy, Control/Overload/Hijack...). Ratings update once per *map*,
scaled by how decisive the map was. At a season boundary (new game) ratings
regress towards the mean, mode offsets more strongly.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class RatingParams:
    base: float = 1500.0
    newcomer: float = 1450.0  # unseen players/teams start slightly below average
    k_team: float = 18.0
    k_team_mode: float = 10.0
    k_player: float = 14.0
    k_player_mode: float = 8.0
    margin_weight: float = 0.8  # 0 = ignore score margin
    provisional_games: int = 15  # extra K for entities with few maps
    season_carry: float = 0.75  # fraction of (rating - base) kept across seasons
    season_mode_carry: float = 0.4
    lan_bonus: float = 0.0


def expected(diff: float) -> float:
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def margin(s1: int | None, s2: int | None) -> float:
    if s1 is None or s2 is None:
        return 0.5
    hi = max(s1, s2, 1)
    return abs(s1 - s2) / hi


class _Pool:
    """Overall + per-mode ratings for one kind of entity."""

    def __init__(self, init: float, base: float):
        self.init, self.base = init, base
        self.overall: dict[int, float] = {}
        self.mode: dict[int, dict[str, float]] = defaultdict(dict)
        self.games: dict[int, int] = defaultdict(int)
        self.season: dict[int, int] = {}

    def get(self, eid: int, mode: str | None = None) -> float:
        r = self.overall.get(eid, self.init)
        if mode is not None:
            r += self.mode[eid].get(mode, 0.0)
        return r

    def known(self, eid: int) -> bool:
        return eid in self.overall

    def touch_season(self, eid: int, season: int, carry: float, mode_carry: float) -> None:
        last = self.season.get(eid)
        if last is not None and last != season:
            gap = max(1, season - last)
            self.overall[eid] = self.base + (self.overall[eid] - self.base) * carry**gap
            self.mode[eid] = {m: v * mode_carry**gap for m, v in self.mode[eid].items()}
            self.games[eid] = min(self.games[eid], 10)  # partially provisional again
        self.season[eid] = season

    def apply(self, eid: int, mode: str, delta_overall: float, delta_mode: float) -> None:
        self.overall[eid] = self.overall.get(eid, self.init) + delta_overall
        self.mode[eid][mode] = self.mode[eid].get(mode, 0.0) + delta_mode
        self.games[eid] += 1


class RatingSystem:
    def __init__(self, params: RatingParams | None = None):
        self.p = params or RatingParams()
        self.teams = _Pool(self.p.newcomer, self.p.base)
        self.players = _Pool(self.p.newcomer, self.p.base)

    # ---- reads -------------------------------------------------------------
    def team(self, team_id: int, mode: str | None = None) -> float:
        return self.teams.get(team_id, mode)

    def roster(self, players: list[int], mode: str | None = None) -> float | None:
        if not players:
            return None
        return sum(self.players.get(p, mode) for p in players) / len(players)

    def strength(self, team_id: int, players: list[int], mode: str | None = None) -> float:
        """Blend used when one number is needed (rankings, quick odds)."""
        r = self.roster(players, mode)
        t = self.team(team_id, mode)
        return t if r is None else 0.5 * t + 0.5 * r

    # ---- writes ------------------------------------------------------------
    def team_seeded(self, team_id: int, roster: list[int], mode: str | None = None) -> float:
        """Team rating; a brand-new org (new id) starts from its roster's rating, not a newcomer default."""
        if self.teams.known(team_id) or not roster:
            return self.team(team_id, mode)
        return self.roster(roster, None)

    def start_match(self, season: int, team_ids: list[int], rosters: list[list[int]]) -> None:
        for t, roster in zip(team_ids, rosters, strict=True):
            if not self.teams.known(t) and roster:
                self.teams.overall[t] = self.roster(roster, None)
            self.teams.touch_season(t, season, self.p.season_carry, self.p.season_mode_carry)
        for roster in rosters:
            for pid in roster:
                self.players.touch_season(pid, season, self.p.season_carry, self.p.season_mode_carry)

    def _k(self, pool: _Pool, eid: int, k: float) -> float:
        n = pool.games[eid]
        return k * (1.0 + 1.5 * max(0.0, 1.0 - n / self.p.provisional_games))

    def update_game(
        self,
        mode: str,
        t1: int,
        t2: int,
        roster1: list[int],
        roster2: list[int],
        t1_won: bool,
        s1: int | None,
        s2: int | None,
    ) -> None:
        y = 1.0 if t1_won else 0.0
        mult = (1.0 - self.p.margin_weight / 2) + self.p.margin_weight * margin(s1, s2)

        # teams
        e = expected(self.team(t1, mode) - self.team(t2, mode))
        err = (y - e) * mult
        for tid, sign in ((t1, 1), (t2, -1)):
            self.teams.apply(
                tid, mode,
                sign * self._k(self.teams, tid, self.p.k_team) * err,
                sign * self.p.k_team_mode * err,
            )

        # players
        r1, r2 = self.roster(roster1, mode), self.roster(roster2, mode)
        if r1 is None or r2 is None:
            return
        e = expected(r1 - r2)
        err = (y - e) * mult
        for roster, sign in ((roster1, 1), (roster2, -1)):
            for pid in roster:
                self.players.apply(
                    pid, mode,
                    sign * self._k(self.players, pid, self.p.k_player) * err,
                    sign * self.p.k_player_mode * err,
                )


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))
