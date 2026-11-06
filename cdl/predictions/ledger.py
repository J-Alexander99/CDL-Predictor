"""Append-only prediction ledger -> an honest public track record.

``data/predictions/ledger.jsonl`` gets one line per prediction snapshot. A
prediction only counts if it was made *before* the match's scheduled start:
grading uses the latest snapshot with ``made_at < datetime``. Snapshots are
only appended when the probability moves meaningfully, so the file stays small.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cdl import config

_MIN_CHANGE = 0.02


def ledger_path() -> Path:
    return config.PREDICTIONS_DIR / "ledger.jsonl"


def notified_path() -> Path:
    return config.PREDICTIONS_DIR / "notified.json"


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(path: Path | None = None) -> list[dict]:
    path = path or ledger_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_by_match(entries: Iterable[dict], before: dict[int, str] | None = None) -> dict[int, dict]:
    """Latest snapshot per match.

    With ``before``: the latest snapshot made before that time; if none exists
    (a delayed match first predicted after its scheduled time, while the site
    still listed it as upcoming) the *first* snapshot is used.
    """
    entries = list(entries)
    out: dict[int, dict] = {}
    first: dict[int, dict] = {}
    for e in entries:
        mid = e["match_id"]
        if mid not in first or e["made_at"] < first[mid]["made_at"]:
            first[mid] = e
        if before is not None:
            cutoff = before.get(mid, e["datetime"])
            if _ts(e["made_at"]) >= _ts(cutoff):
                continue
        if mid not in out or e["made_at"] >= out[mid]["made_at"]:
            out[mid] = e
    if before is not None:
        for mid, e in first.items():
            out.setdefault(mid, e)
    return out


def record(predictions: list[dict], now: datetime, path: Path | None = None) -> list[dict]:
    """Append snapshots for upcoming matches. Returns entries that are new or changed."""
    path = path or ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    latest = latest_by_match(load(path))
    written = []
    lines = []
    for p in predictions:
        prev = latest.get(p["match_id"])
        if _ts(p["datetime"]) <= now and prev is not None:
            # Past the scheduled time: only a delayed, still-upcoming match without
            # any prediction may get one (callers pass only status == "upcoming").
            continue
        if prev and abs(prev["p_team1"] - p["p_team1"]) < _MIN_CHANGE and prev.get("team2", {}).get("id") == p["team2"]["id"]:
            continue
        entry = {**p, "made_at": now.replace(microsecond=0).isoformat(), "first": prev is None}
        lines.append(json.dumps(entry, sort_keys=True, ensure_ascii=False))
        written.append(entry)
    if lines:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return written


@dataclass
class Graded:
    entry: dict
    winner_id: int
    score: str  # from team1's perspective, e.g. "3-1"

    @property
    def p_winner(self) -> float:
        p = self.entry["p_team1"]
        return p if self.winner_id == self.entry["team1"]["id"] else 1 - p

    @property
    def correct(self) -> bool:
        return self.p_winner > 0.5

    @property
    def exact(self) -> bool:
        return self.entry.get("likely_score") == self.score

    @property
    def log_loss(self) -> float:
        return -math.log(min(max(self.p_winner, 1e-6), 1 - 1e-6))

    @property
    def brier(self) -> float:
        return (1 - self.p_winner) ** 2


def grade(results: dict[int, dict], scheduled: dict[int, str] | None = None, path: Path | None = None) -> list[Graded]:
    """``results``: match_id -> {winner_id, team_1_id, team_1_score, team_2_score, datetime}."""
    entries = load(path)
    cut = {mid: r["datetime"] for mid, r in results.items()}
    if scheduled:
        cut.update({k: v for k, v in scheduled.items() if k in cut})
    locked = latest_by_match(entries, before=cut)
    out = []
    for mid, e in locked.items():
        r = results.get(mid)
        if not r or r.get("winner_id") is None:
            continue
        s1, s2 = r["team_1_score"], r["team_2_score"]
        if r["team_1_id"] != e["team1"]["id"]:
            s1, s2 = s2, s1
        out.append(Graded(entry=e, winner_id=int(r["winner_id"]), score=f"{s1}-{s2}"))
    return sorted(out, key=lambda g: g.entry["datetime"], reverse=True)


def summarize(graded: list[Graded]) -> dict:
    if not graded:
        return {"n": 0}
    n = len(graded)
    return {
        "n": n,
        "accuracy": round(sum(g.correct for g in graded) / n, 4),
        "exact_score": round(sum(g.exact for g in graded) / n, 4),
        "log_loss": round(sum(g.log_loss for g in graded) / n, 4),
        "brier": round(sum(g.brier for g in graded) / n, 4),
    }


def load_notified() -> dict:
    p = notified_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"predictions": {}, "results": []}


def save_notified(state: dict) -> None:
    notified_path().parent.mkdir(parents=True, exist_ok=True)
    notified_path().write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
