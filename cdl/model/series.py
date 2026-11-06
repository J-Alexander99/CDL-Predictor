"""From map probabilities to a full series prediction.

1. The season's mode order per map slot is learned from played matches
   (e.g. 2027 BO5: Hardpoint, S&D, Hijack, Hardpoint, S&D).
2. For each slot the map is unknown before the veto, so we form a probability
   distribution over the season's map pool: how often each map is played in
   that mode overall, sharpened by what these two teams like to pick.
3. P(win slot) = sum over maps of P(map) * P(win | mode, map).
4. An exact dynamic programme over slots gives P(series) and the score
   distribution (3-0, 3-1, 3-2, ...).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import pandas as pd

from cdl.model.features import Engine
from cdl.model.map_model import MapModel

_DEFAULT_ORDER = ["Hardpoint", "Search & Destroy"]

# Maps within a series are not independent (momentum, adaptation), so the
# independent-maps maths is overconfident. A temperature on the series logit,
# chosen by walk-forward backtest (better log loss in both 2025 and 2026),
# corrects it.
SERIES_TEMPERATURE = 0.85


def temper(dist: dict[tuple[int, int], float], t: float = SERIES_TEMPERATURE) -> dict[tuple[int, int], float]:
    """Shrink P(series win) towards 50% and rescale the score outcomes to match."""
    p = sum(pr for (a, b), pr in dist.items() if a > b)
    if t == 1.0 or p <= 0.0 or p >= 1.0:
        return dist
    p = min(max(p, 1e-9), 1 - 1e-9)
    q = 1.0 / (1.0 + math.exp(-t * math.log(p / (1 - p))))
    return {k: pr * (q / p if k[0] > k[1] else (1 - q) / (1 - p)) for k, pr in dist.items()}


def series_format(games: pd.DataFrame, season: int, best_of: int, season_modes: list[str] | None = None) -> list[str]:
    g = games[(games.season_id == season) & (games.best_of == best_of)]
    order: list[str] = []
    for slot in range(1, best_of + 1):
        modes = g.loc[g.game_num == slot, "mode"]
        order.append(modes.mode().iloc[0] if len(modes) else "")
    if all(order):
        return order
    # Not enough data yet: standard CDL layout HP, S&D, <third mode>, repeat
    third = next((m for m in (season_modes or []) if m not in _DEFAULT_ORDER), "Control")
    base = ["Hardpoint", "Search & Destroy", third]
    return [o or base[i % 3] for i, o in enumerate(order)]


def series_distribution(p_slots: list[float], best_of: int) -> dict[tuple[int, int], float]:
    """Exact P(final score) assuming independent maps."""
    need = best_of // 2 + 1
    states = {(0, 0): 1.0}
    final: dict[tuple[int, int], float] = {}
    for p in p_slots:
        nxt: dict[tuple[int, int], float] = {}
        for (a, b), pr in states.items():
            for (na, nb), q in (((a + 1, b), p), ((a, b + 1), 1 - p)):
                if na == need or nb == need:
                    final[(na, nb)] = final.get((na, nb), 0.0) + pr * q
                else:
                    nxt[(na, nb)] = nxt.get((na, nb), 0.0) + pr * q
        states = nxt
    return final


@dataclass
class MapPool:
    """Season map usage, computed from data strictly before ``as_of``."""

    played: pd.DataFrame  # games
    picks: pd.DataFrame  # vetoes with action == Pick
    bans: pd.DataFrame

    @classmethod
    def build(cls, frames, season: int, as_of: pd.Timestamp | None) -> MapPool:
        g = frames.games[frames.games.season_id == season]
        v = frames.vetoes[frames.vetoes.season_id == season]
        if as_of is not None:
            g = g[g.datetime < as_of]
            v = v[v.datetime < as_of]
        return cls(g, v[v.action == "Pick"], v[v.action == "Ban"])

    def distribution(self, mode: str, t1: int, t2: int, exclude: set[str] = frozenset()) -> dict[str, float]:
        overall = Counter(self.played.loc[self.played["mode"] == mode, "map"].dropna())
        if not overall:
            return {}
        picks = self.picks[self.picks["mode"] == mode]
        bans = self.bans[self.bans["mode"] == mode]
        total_overall = sum(overall.values())
        weights = {}
        for m, c in overall.items():
            if m in exclude:
                continue
            w = 4.0 * c / total_overall
            for team in (t1, t2):
                tp = picks[picks.team_id == team]
                tb = bans[bans.team_id == team]
                if len(tp):
                    w += (tp["map"] == m).mean()
                if len(tb):
                    w *= 1.0 - 0.6 * (tb["map"] == m).mean()
            weights[m] = max(w, 1e-6)
        s = sum(weights.values())
        return {m: w / s for m, w in sorted(weights.items(), key=lambda kv: -kv[1])}

    def tendencies(self, team: int, mode: str, top: int = 2) -> dict[str, list[str]]:
        tp = self.picks[(self.picks.team_id == team) & (self.picks["mode"] == mode)]["map"].value_counts()
        tb = self.bans[(self.bans.team_id == team) & (self.bans["mode"] == mode)]["map"].value_counts()
        return {"picks": list(tp.index[:top]), "bans": list(tb.index[:top])}


class SeriesPredictor:
    def __init__(self, engine: Engine, model: MapModel, frames, season_modes: dict[int, list[str]] | None = None):
        self.engine, self.model, self.frames = engine, model, frames
        self.season_modes = season_modes or {}
        self._pools: dict[tuple, MapPool] = {}

    def _pool(self, season: int, as_of) -> MapPool:
        key = (season, as_of)
        if key not in self._pools:
            self._pools[key] = MapPool.build(self.frames, season, as_of)
        return self._pools[key]

    def predict(
        self,
        t1: int,
        t2: int,
        season: int,
        best_of: int = 5,
        roster1: list[int] | None = None,
        roster2: list[int] | None = None,
        as_of: pd.Timestamp | None = None,
        detail: bool = True,
    ) -> dict:
        eng = self.engine
        roster1 = roster1 if roster1 else eng.roster_for(t1)
        roster2 = roster2 if roster2 else eng.roster_for(t2)
        order = series_format(self.frames.games, season, best_of, self.season_modes.get(season))
        pool = self._pool(season, as_of)
        used: dict[str, set[str]] = {}
        slots = []
        mode_p: dict[str, list[float]] = {}
        for i, mode in enumerate(order, 1):
            dist = pool.distribution(mode, t1, t2, exclude=used.get(mode, set()))
            if dist:
                p = sum(
                    w * self.model.predict(eng.features(season, t1, t2, roster1, roster2, mode, m))
                    for m, w in dist.items()
                )
                likely = next(iter(dist))
                used.setdefault(mode, set()).add(likely)
            else:
                p = self.model.predict(eng.features(season, t1, t2, roster1, roster2, mode, None))
                likely = None
            mode_p.setdefault(mode, []).append(p)
            slots.append({
                "game_num": i, "mode": mode, "likely_map": likely, "p_team1": p,
                "map_options": [{"map": m, "prob": w} for m, w in list(dist.items())[:3]],
            })
        dist = temper(series_distribution([s["p_team1"] for s in slots], best_of))
        p_series = sum(pr for (a, b), pr in dist.items() if a > b)
        out = {
            "team1_id": t1, "team2_id": t2, "season": season, "best_of": best_of,
            "p_team1": p_series,
            "scores": {f"{a}-{b}": pr for (a, b), pr in sorted(dist.items(), key=lambda kv: (-kv[0][0], kv[0][1]))},
        }
        if detail:
            out.update({
                "likely_score": max(dist.items(), key=lambda kv: kv[1])[0],
                "slots": slots,
                "modes": {m: sum(v) / len(v) for m, v in mode_p.items()},
                "ratings": {
                    "team1": round(eng.ratings.strength(t1, roster1), 1),
                    "team2": round(eng.ratings.strength(t2, roster2), 1),
                },
                "rosters": {"team1": roster1, "team2": roster2},
                "tendencies": {
                    side: {m: pool.tendencies(t, m) for m in dict.fromkeys(order)}
                    for side, t in (("team1", t1), ("team2", t2))
                },
            })
            out["likely_score"] = f"{out['likely_score'][0]}-{out['likely_score'][1]}"
        return out
