from datetime import datetime, timezone

from cdl.publish import feed

SITE = "https://example.github.io/CDL-Predictor/"


def entry(mid, made_at, p, kickoff="2026-11-07T18:00:00+00:00", **kw):
    return {
        "match_id": mid, "made_at": made_at, "datetime": kickoff, "p_team1": p,
        "team1": {"id": 1, "name": "Paris Gentle Mates", "short": "M8", "logo": "l1"},
        "team2": {"id": 2, "name": "G2 Minnesota", "short": "MIN", "logo": "l2"},
        "likely_score": "3-0", "likely_score_label": "3-0 Paris Gentle Mates",
        "event_name": "Launch", "event_id": 9, "round": "R1", "best_of": 5,
        "graphic": f"graphics/{mid}.png", "model_version": "3.0",
        "slots": [{"game_num": 1, "mode": "Hardpoint", "likely_map": "Sentry", "p_team1": 0.69}],
        **kw,
    }


NOW = datetime(2026, 11, 7, 17, 0, tzinfo=timezone.utc)


def test_feed_uses_locked_snapshot_and_absolute_urls():
    entries = [
        entry(1, "2026-11-07T10:00:00+00:00", 0.70),
        entry(1, "2026-11-07T16:00:00+00:00", 0.78),
        entry(1, "2026-11-07T18:30:00+00:00", 0.10),  # made after kickoff: never the locked one
    ]
    f = feed.build_feed(entries, {}, {"n": 10, "accuracy": 0.6, "exact_score": 0.2}, NOW, SITE)
    assert f["schema"] == 1 and f["record"] == {"n": 10, "accuracy": 0.6, "exact_score": 0.2, "correct": 6}
    (m,) = f["matches"]
    assert m["prediction"]["p_team1"] == 0.78
    assert m["prediction"]["favorite"] == "Paris Gentle Mates" and m["prediction"]["favorite_p"] == 0.78
    assert m["prediction"]["maps"] == [
        {"game_num": 1, "mode": "Hardpoint", "mode_short": "HP", "map": "Sentry", "p_team1": 0.69}
    ]
    assert m["graphic_url"] == SITE + "graphics/1.png"
    assert m["page_url"] == SITE + "#m1"


def test_feed_favourite_can_be_team2():
    f = feed.build_feed([entry(1, "2026-11-07T10:00:00+00:00", 0.3)], {}, {"n": 0}, NOW, SITE)
    pred = f["matches"][0]["prediction"]
    assert pred["favorite_id"] == 2 and pred["favorite_p"] == 0.7
    assert f["record"] == {"n": 0}


def test_feed_window_and_current_schedule():
    entries = [
        entry(1, "2026-11-06T08:00:00+00:00", 0.6, kickoff="2026-11-06T09:00:00+00:00"),  # long over
        entry(2, "2026-11-07T08:00:00+00:00", 0.6, kickoff="2026-11-07T12:00:00+00:00"),  # 5h ago: kept
        entry(3, "2026-11-07T08:00:00+00:00", 0.6, kickoff="2026-11-07T18:00:00+00:00"),
    ]
    # match 3 was pushed back an hour on the site and is still upcoming
    schedule = {3: {"datetime": "2026-11-07T19:00:00+00:00", "status": "upcoming"},
                2: {"datetime": "2026-11-07T12:00:00+00:00", "status": "live"}}
    f = feed.build_feed(entries, schedule, {"n": 0}, NOW, SITE)
    assert [(m["match_id"], m["status"], m["start_utc"]) for m in f["matches"]] == [
        (2, "live", "2026-11-07T12:00:00+00:00"),
        (3, "upcoming", "2026-11-07T19:00:00+00:00"),
    ]
