import random

import numpy as np
import pandas as pd
import pytest

from cdl.model.features import FEATURES, replay
from cdl.model.map_model import MapModel
from cdl.model.series import SeriesPredictor, series_distribution, series_format
from cdl.store.db import Frames

MODES = ["Hardpoint", "Search & Destroy", "Hijack", "Hardpoint", "Search & Destroy"]
MAPS = {"Hardpoint": ["Rooftops", "Lotus", "Coal"], "Search & Destroy": ["Coal", "Plaza", "Munition"],
        "Hijack": ["Munition", "Lotus"]}


def test_series_distribution_sums_to_one_and_matches_coinflip():
    d = series_distribution([0.5] * 5, 5)
    assert sum(d.values()) == pytest.approx(1.0)
    assert d[(3, 0)] == pytest.approx(1 / 8)
    assert d[(3, 2)] == pytest.approx(6 / 32)
    assert sum(v for (a, b), v in d.items() if a > b) == pytest.approx(0.5)


def test_series_distribution_favourite():
    d = series_distribution([0.7] * 5, 5)
    p = sum(v for (a, b), v in d.items() if a > b)
    assert 0.80 < p < 0.85  # amplification of a 70% map edge over a BO5


def synthetic_frames(n_matches=240, seed=0) -> Frames:
    """Six teams with fixed true strengths, four players each."""
    rng = random.Random(seed)
    strength = {t: s for t, s in zip(range(1, 7), [1.2, 0.8, 0.4, 0.0, -0.5, -1.0], strict=True)}
    start = pd.Timestamp("2026-11-01", tz="UTC")
    matches, games, players = [], [], []
    for i in range(n_matches):
        t1, t2 = rng.sample(list(strength), 2)
        dt = start + pd.Timedelta(hours=8 * i)
        event = 100 + i // 30
        w1 = w2 = 0
        for gnum, mode in enumerate(MODES, 1):
            p = 1 / (1 + np.exp(-(strength[t1] - strength[t2])))
            t1_wins = rng.random() < p
            w1, w2 = w1 + t1_wins, w2 + (not t1_wins)
            mp = rng.choice(MAPS[mode])
            games.append({"match_id": i, "game_num": gnum, "mode": mode, "map": mp, "team_1_id": t1, "team_2_id": t2,
                          "winner_id": t1 if t1_wins else t2, "team_1_score": 250 if t1_wins else 200,
                          "team_2_score": 200 if t1_wins else 250, "duration_s": 600, "datetime": dt,
                          "season_id": 2027, "event_id": event, "lan": 0, "best_of": 5})
            for team in (t1, t2):
                for k in range(4):
                    players.append({"match_id": i, "game_num": gnum, "player_id": team * 10 + k, "team_id": team,
                                    "bp_rating": 1.0 + 0.1 * strength[team] + rng.gauss(0, 0.1), "datetime": dt,
                                    "season_id": 2027, "mode": mode, "map": mp})
            if max(w1, w2) == 3:
                break
        matches.append({"id": i, "event_id": event, "season_id": 2027, "datetime": dt, "best_of": 5,
                        "team_1_id": t1, "team_2_id": t2, "winner_id": t1 if w1 > w2 else t2,
                        "team_1_score": w1, "team_2_score": w2, "round": "R", "round_stage": "x", "lan": 0})
    teams = pd.DataFrame({"id": list(strength), "name": [f"T{t}" for t in strength], "name_short": None,
                          "logo": None, "color": None})
    return Frames(
        matches=pd.DataFrame(matches), games=pd.DataFrame(games), players=pd.DataFrame(players),
        vetoes=pd.DataFrame(columns=["match_id", "ord", "team_id", "mode", "map", "action", "map_number",
                                     "datetime", "season_id"]),
        teams=teams, events=pd.DataFrame({"id": [], "name": []}), seasons=pd.DataFrame({"id": [2027], "title": ["MW4"]}),
        player_tags=pd.DataFrame({"id": [t * 10 + k for t in strength for k in range(4)],
                                  "tag": [f"P{t}{k}" for t in strength for k in range(4)]}),
    )


def test_replay_features_are_point_in_time_and_model_learns():
    frames = synthetic_frames()
    engine, ds = replay(frames)
    assert set(FEATURES) <= set(ds.columns)
    # first match: nobody has history yet
    first = ds[ds.match_id == 0]
    assert (first.team_diff == 0).all() and (first.roster_diff == 0).all()
    # maps of the same mode within one match share the same pre-match ratings
    # (no leakage from earlier maps of the series)
    m5 = ds[ds.match_id == 5]
    assert (m5.groupby("mode").team_diff.nunique() == 1).all()

    model = MapModel().fit(ds)
    assert model.coefficients()["roster_diff"] > 0 or model.coefficients()["team_diff"] > 0
    # strongest team rated above weakest
    assert engine.ratings.team(1) > engine.ratings.team(6)

    sp = SeriesPredictor(engine, model, frames, {2027: ["Hardpoint", "Search & Destroy", "Hijack"]})
    ab = sp.predict(1, 6, 2027)
    ba = sp.predict(6, 1, 2027)
    assert ab["p_team1"] > 0.75
    assert ab["p_team1"] == pytest.approx(1 - ba["p_team1"], abs=1e-6)  # symmetry
    assert sum(ab["scores"].values()) == pytest.approx(1.0)
    assert [s["mode"] for s in ab["slots"]] == MODES
    assert series_format(frames.games, 2027, 5) == MODES


def test_temper_shrinks_and_stays_normalised():
    from cdl.model.series import temper

    d = series_distribution([0.75] * 5, 5)
    t = temper(d, 0.85)
    p = sum(v for (a, b), v in d.items() if a > b)
    q = sum(v for (a, b), v in t.items() if a > b)
    assert 0.5 < q < p
    assert sum(t.values()) == pytest.approx(1.0)
    assert temper(series_distribution([0.5] * 5, 5), 0.85)[(3, 0)] == pytest.approx(1 / 8)
