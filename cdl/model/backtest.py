"""Honest walk-forward evaluation.

For every match in the evaluation window the model is refit on maps played
before that match's event started, ratings are taken as of the moment before
the match, and the series is predicted *without knowing the maps*. Results are
compared against two baselines: a coin flip and plain team Elo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from cdl.model.features import Engine, MatchCtx, replay
from cdl.model.map_model import MapModel
from cdl.model.ratings import RatingParams, expected
from cdl.model.series import SeriesPredictor, series_distribution, series_format


def _logloss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def metrics(p, y) -> dict:
    p, y = np.asarray(p, float), np.asarray(y, float)
    if len(p) == 0:
        return {"n": 0}
    return {
        "n": int(len(p)),
        "log_loss": round(_logloss(p, y), 4),
        "brier": round(float(np.mean((p - y) ** 2)), 4),
        "accuracy": round(float(np.mean((p >= 0.5) == (y == 1))), 4),
    }


def calibration(p, y, bins: int = 10) -> list[dict]:
    """Bins on the favourite's probability (0.5-1.0)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    fav = np.where(p >= 0.5, p, 1 - p)
    won = np.where(p >= 0.5, y, 1 - y)
    edges = np.linspace(0.5, 1.0, bins // 2 + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (fav >= lo) & (fav < hi if hi < 1.0 else fav <= hi)
        if mask.sum():
            out.append({"lo": round(lo, 2), "hi": round(hi, 2), "n": int(mask.sum()),
                        "predicted": round(float(fav[mask].mean()), 4), "actual": round(float(won[mask].mean()), 4)})
    return out


@dataclass
class BacktestResult:
    series: pd.DataFrame
    maps: pd.DataFrame
    summary: dict = field(default_factory=dict)


def run(
    frames,
    params: RatingParams | None = None,
    model_kwargs: dict | None = None,
    eval_from: str = "2025-01-01",
    season_modes: dict[int, list[str]] | None = None,
) -> BacktestResult:
    model_kwargs = model_kwargs or {}
    eval_start = pd.Timestamp(eval_from, tz="UTC")
    _, dataset = replay(frames, params)
    event_start = dataset.groupby("event_id").datetime.min()

    models: dict[int, MapModel] = {}
    series_rows: list[dict] = []
    map_parts: list[pd.DataFrame] = []

    def on_match(eng: Engine, ctx: MatchCtx) -> None:
        if ctx.datetime < eval_start or ctx.t1_won is None:
            return
        cut = event_start[ctx.event_id]
        if ctx.event_id not in models:
            models[ctx.event_id] = MapModel(**model_kwargs).fit(dataset, as_of=cut)
            ev_rows = dataset[dataset.event_id == ctx.event_id]
            map_parts.append(ev_rows.assign(p=models[ctx.event_id].predict(ev_rows)))
        model = models[ctx.event_id]
        bo = ctx.best_of or 5
        pred = SeriesPredictor(eng, model, frames, season_modes).predict(
            ctx.t1, ctx.t2, ctx.season, bo, ctx.roster1, ctx.roster2, as_of=ctx.datetime, detail=False
        )
        # Baseline: plain team Elo, same series maths
        order = series_format(frames.games, ctx.season, bo, (season_modes or {}).get(ctx.season))
        p_elo_map = [expected(eng.ratings.team(ctx.t1, m) - eng.ratings.team(ctx.t2, m)) for m in order]
        dist = series_distribution(p_elo_map, bo)
        p_elo = sum(pr for (a, b), pr in dist.items() if a > b)
        a = sum(g.t1_won for g in ctx.games)
        b = len(ctx.games) - a
        series_rows.append({
            "match_id": ctx.match_id, "datetime": ctx.datetime, "season": ctx.season, "event_id": ctx.event_id,
            "t1": ctx.t1, "t2": ctx.t2, "y": int(ctx.t1_won), "p": pred["p_team1"], "p_elo": p_elo,
            "pred_score": max(pred["scores"].items(), key=lambda kv: kv[1])[0],
            "score": f"{a}-{b}",
        })

    replay(frames, params, on_match=on_match)
    series = pd.DataFrame(series_rows)
    maps = pd.concat(map_parts, ignore_index=True) if map_parts else pd.DataFrame()

    summary: dict = {"eval_from": eval_from, "seasons": {}}
    if len(series):
        for season, s in [("all", series), *series.groupby("season")]:
            m = maps if season == "all" else maps[maps.season == season]
            summary["seasons"][str(season)] = {
                "series_model": metrics(s.p, s.y),
                "series_elo": metrics(s.p_elo, s.y),
                "series_coinflip": {"n": len(s), "log_loss": round(math.log(2), 4), "brier": 0.25, "accuracy": 0.5},
                "exact_score": round(float((s.pred_score == s.score).mean()), 4),
                "maps_model": metrics(m.p, m.y) if len(m) else {"n": 0},
            }
        summary["calibration"] = calibration(series.p, series.y)
    return BacktestResult(series=series, maps=maps, summary=summary)
