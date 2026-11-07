import gzip
from datetime import date
from pathlib import Path

import pytest

from cdl.scrape import discover
from cdl.scrape.next_data import SchemaError, extract_next_data, trim_match
from cdl.store import raw

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return extract_next_data(gzip.decompress((FIX / name).read_bytes()).decode(), name)


def test_missing_next_data_raises():
    with pytest.raises(SchemaError):
        extract_next_data("<html>Just a moment...</html>")


def test_trim_match_2026_overload():
    r = trim_match(load("match_214951.html.gz"))
    assert r["event"] == {"id": 104, "name": "CDL Major 3 Qualifier", "season_id": 2026, "division_id": 3, "lan": False}
    assert (r["team_1_score"], r["team_2_score"]) == (3, 1)
    names = {t["id"]: t["name"] for t in r["teams"]}
    assert names[r["winner_id"]] == "Riyadh Falcons"
    got = [(g["mode"], g["map"], g["team_1_score"], g["team_2_score"]) for g in r["games"]]
    assert got == [
        ("Hardpoint", "Sake", 250, 209),
        ("Search & Destroy", "Plaza", 4, 6),
        ("Overload", "Den", 8, 2),
        ("Hardpoint", "Gridlock", 250, 191),
    ]
    for g in r["games"]:
        assert len(g["players"]) == 8
        assert {p["team_id"] for p in g["players"]} == {r["team_1_id"], r["team_2_id"]}
    assert any(v["action"] == "Pick" for v in r["vetoes"])
    assert all(v["map"] for v in r["vetoes"])


def test_trim_match_2027_hijack():
    r = trim_match(load("match_358722.html.gz"))
    assert r["event"]["season_id"] == 2027
    assert [g["mode"] for g in r["games"]] == ["Hardpoint", "Search & Destroy", "Hijack"]
    assert r["games"][2]["map"] == "Munition"


def test_trim_match_2024_lan_control():
    r = trim_match(load("match_35633.html.gz"))
    assert r["event"]["season_id"] == 2024
    assert r["event"]["lan"] is True
    assert "Control" in [g["mode"] for g in r["games"]]


def test_raw_store_roundtrip_is_stable(tmp_path):
    r = trim_match(load("match_214951.html.gz"))
    p = raw.save(r, tmp_path)
    first = p.read_bytes()
    raw.save({**r, "scraped_at": "2099-01-01T00:00:00+00:00"}, tmp_path)  # unchanged content
    assert p.read_bytes() == first
    assert raw.stored_ids(tmp_path) == {214951}
    assert next(raw.iter_all(tmp_path))["games"] == r["games"]


def test_catalog():
    cat = discover.parse_catalog(load("matches.html.gz"))
    seasons = {s["id"]: s for s in cat["seasons"]}
    assert set(seasons[2027]["modes"]) == {"Hardpoint", "Search & Destroy", "Hijack"}
    assert "Overload" in seasons[2026]["modes"]
    assert any(e["id"] == 1244 for e in cat["events"])
    assert len(cat["teams"]) >= 12


def test_event_pages_and_finality():
    ev = discover.parse_event(load("event_104.html.gz"), 104)
    assert ev["division_id"] == 3 and ev["season_id"] == 2026
    assert ev["matches"] and all(m["status"] == "complete" for m in ev["matches"])
    assert discover._is_final(ev, date(2026, 11, 6))

    live = discover.parse_event(load("event_1244.html.gz"), 1244)
    assert not discover._is_final(live, date(2026, 11, 6))
    statuses = {m["status"] for m in live["matches"]}
    assert "upcoming" in statuses

    cdc = discover.parse_event(load("event_187.html.gz"), 187)
    assert cdc["division_id"] != 3
    assert discover._is_final(cdc, date(2026, 11, 6))


def test_needs_refresh_window():
    entry = {"final": False, "start_date": "2027-01-15", "end_date": "2027-02-07"}
    assert not discover._needs_refresh(entry, date(2026, 11, 6))
    assert discover._needs_refresh(entry, date(2027, 1, 10))
    assert discover._needs_refresh(None, date(2026, 11, 6))
    assert not discover._needs_refresh({"final": True}, date(2027, 1, 20))


def test_team_roster_excludes_non_players():
    from cdl.scrape.next_data import parse_team_roster

    roster = parse_team_roster(load("team_4.html.gz"), 4)
    tags = {p["tag"] for p in roster}
    assert len(roster) == 4
    assert {"Dashy", "Shotzzy"} <= tags
    assert "Scump" not in tags and "Crimsix" not in tags  # streamer / content creator


def test_challengers_collected_from_cutoff_season_only():
    cdc = lambda season: {"division_id": 1, "season_id": season}  # noqa: E731
    assert not discover._collected(cdc(2026))
    assert discover._collected(cdc(2027))
    assert discover._collected({"division_id": 3, "season_id": 2024})
    assert not discover._collected({"division_id": 2, "season_id": 2027})

    m = {"status": "complete", "id": 1}
    index = {
        "1": {"id": 1, "division_id": 3, "season_id": 2027, "matches": [{**m, "id": 10}]},
        "2": {"id": 2, "division_id": 1, "season_id": 2027, "matches": [{**m, "id": 20}]},
        "3": {"id": 3, "division_id": 1, "season_id": 2026, "matches": [{**m, "id": 30}]},
    }
    assert [x["id"] for x in discover.completed_matches(index)] == [10]
    assert sorted(x["id"] for x in discover.completed_matches(index, challengers=True)) == [10, 20]
    assert discover.upcoming_matches(index) == []  # predictions stay CDL-only


def test_trim_match_skips_unplayed_games():
    nd = load("match_358722.html.gz")
    games = nd["props"]["pageProps"]["initialMatchState"]["games"]
    games.append({**games[-1], "game_num": 99, "mode_id": None, "modes": None, "player_stats": []})
    r = trim_match(nd)
    assert [g["mode"] for g in r["games"]] == ["Hardpoint", "Search & Destroy", "Hijack"]
