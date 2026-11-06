from datetime import datetime, timezone

from cdl.predictions import ledger


def pred(mid=1, p=0.6, dt="2027-01-10T18:00:00+00:00"):
    return {"match_id": mid, "datetime": dt, "p_team1": p, "likely_score": "3-1",
            "team1": {"id": 10, "name": "A"}, "team2": {"id": 20, "name": "B"}}


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_record_only_before_start_and_on_change(tmp_path):
    path = tmp_path / "ledger.jsonl"
    w = ledger.record([pred()], t("2027-01-09T12:00:00"), path)
    assert len(w) == 1 and w[0]["first"]
    # tiny change: no new snapshot
    assert ledger.record([pred(p=0.61)], t("2027-01-09T14:00:00"), path) == []
    # meaningful change: new snapshot, not "first"
    w = ledger.record([pred(p=0.70)], t("2027-01-09T16:00:00"), path)
    assert len(w) == 1 and not w[0]["first"]
    # after the start: never recorded
    assert ledger.record([pred(p=0.20)], t("2027-01-10T18:30:00"), path) == []
    assert len(ledger.load(path)) == 2


def test_grade_uses_latest_snapshot_before_start(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record([pred(p=0.40)], t("2027-01-09T12:00:00"), path)
    ledger.record([pred(p=0.65)], t("2027-01-10T10:00:00"), path)
    results = {1: {"winner_id": 10, "team_1_id": 10, "team_1_score": 3, "team_2_score": 1,
                   "datetime": "2027-01-10T18:00:00+00:00"}}
    [g] = ledger.grade(results, path=path)
    assert g.entry["p_team1"] == 0.65
    assert g.correct and g.exact and g.score == "3-1"
    s = ledger.summarize([g])
    assert s["n"] == 1 and s["accuracy"] == 1.0


def test_grade_handles_flipped_team_order(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record([pred(p=0.30)], t("2027-01-09T12:00:00"), path)
    # Site lists team 20 first in the result
    results = {1: {"winner_id": 20, "team_1_id": 20, "team_1_score": 3, "team_2_score": 0,
                   "datetime": "2027-01-10T18:00:00+00:00"}}
    [g] = ledger.grade(results, path=path)
    assert g.score == "0-3" and g.correct
