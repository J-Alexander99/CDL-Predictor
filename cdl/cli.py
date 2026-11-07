"""``cdl`` command line interface."""
from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timedelta, timezone

import typer
from rich.console import Console
from rich.table import Table

from cdl import config

app = typer.Typer(add_completion=False, no_args_is_help=True, help="CDL data pipeline and match predictor.")
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def _parse_seasons(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(int(part))
    return out


def _backtest_path():
    return config.META_DIR / "backtest.json"


def _run_backtest(bundle, eval_from: str = "2025-01-01") -> dict:
    from cdl import pipeline
    from cdl.model import backtest

    res = backtest.run(bundle.frames, pipeline.PARAMS, pipeline.MODEL_KWARGS, eval_from=eval_from,
                       season_modes=bundle.season_modes)
    summary = {**res.summary, "model_version": pipeline.MODEL_VERSION,
               "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
    pipeline.write_json(_backtest_path(), summary)
    return summary


# --------------------------------------------------------------------------
@app.command()
def backfill(
    seasons: str = typer.Option("2024-2027", help="Seasons, e.g. 2024-2027 or 2026"),
    limit: int = typer.Option(0, help="Scrape at most N matches (0 = all)"),
    force_events: bool = typer.Option(False, help="Re-fetch every event page"),
    verbose: bool = False,
):
    """Discover and scrape all completed CDL matches for the given seasons."""
    _setup_logging(verbose)
    from cdl.scrape.client import BreakingPointClient
    from cdl.scrape.sync import sync

    config.ensure_dirs()

    def prog(i, n, ref):
        if i % 20 == 0 or i == n:
            console.print(f"[dim]{i}/{n}[/] {ref['season_id']} {ref['team_1_name']} vs {ref['team_2_name']}")

    with BreakingPointClient() as c:
        res = sync(c, _parse_seasons(seasons), force_events=force_events, limit=limit or None, progress=prog)
    console.print(f"[green]{len(res.new)} new matches[/], {len(res.failed)} failed, {res.requests} requests")
    for mid, err in res.failed.items():
        console.print(f"[red]{mid}[/] {err[:200]}")


@app.command("scrape-match")
def scrape_match_cmd(match_id: int, save: bool = typer.Option(False, help="Store in data/raw")):
    """Scrape one match and print what was parsed."""
    _setup_logging(False)
    from cdl.scrape.client import BreakingPointClient
    from cdl.scrape.sync import scrape_match
    from cdl.store import raw

    with BreakingPointClient() as c:
        r = scrape_match(c, match_id)
    names = {t["id"]: t["name"] for t in r["teams"]}
    console.print(f"[bold]{names.get(r['team_1_id'])} {r['team_1_score']}-{r['team_2_score']} "
                  f"{names.get(r['team_2_id'])}[/]  {r['event']['name']} ({r['event']['season_id']}) · {r['status']}")
    for g in r["games"]:
        console.print(f"  Map {g['game_num']}: {g['mode']:<17} {g['map'] or '?':<12} {g['team_1_score']}-{g['team_2_score']}"
                      f"  ({len(g['players'])} players)")
    if save:
        console.print(f"saved {raw.save(r)}")


@app.command()
def rebuild():
    """Rebuild the SQLite database (build/cdl.db) from data/raw."""
    from cdl.store import db

    console.print(db.build())


@app.command()
def predict(
    team1: str,
    team2: str,
    best_of: int = typer.Option(5, "--bo", help="Best of N maps"),
    graphic: bool = typer.Option(False, "--graphic", "-g", help="Write a PNG card to site/graphics"),
):
    """Predict a hypothetical (or upcoming) series between two teams."""
    from cdl import pipeline

    b = pipeline.build_bundle()
    t1, t2 = pipeline.resolve_team(b, team1), pipeline.resolve_team(b, team2)
    p = pipeline.predict_match(b, {"team_1_id": t1, "team_2_id": t2, "best_of": best_of,
                                   "season_id": pipeline.current_season(b), "id": 0})
    n1, n2 = p["team1"]["name"], p["team2"]["name"]
    console.print(f"\n[bold]{n1}[/] {p['p_team1']:.1%}  vs  {1 - p['p_team1']:.1%} [bold]{n2}[/]")
    console.print(f"Most likely: [bold]{p['likely_score_label']}[/]")
    t = Table("Score", "Prob")
    for s, pr in p["scores"].items():
        t.add_row(s, f"{pr:.1%}")
    console.print(t)
    t = Table("Map", "Mode", "Likely map", f"{n1}", f"{n2}")
    for s in p["slots"]:
        t.add_row(str(s["game_num"]), s["mode"], s["likely_map"] or "?", f"{s['p_team1']:.0%}", f"{1 - s['p_team1']:.0%}")
    console.print(t)
    console.print(f"[dim]Rosters: {', '.join(p['rosters']['team1'])} vs {', '.join(p['rosters']['team2'])}[/]")
    console.print(f"[dim]Ratings: {p['ratings']['team1']} vs {p['ratings']['team2']}[/]")
    if graphic:
        from cdl.publish.graphics import prediction_card

        console.print(f"graphic: {prediction_card(p)}")


@app.command()
def ratings(season: int = typer.Option(0, help="Season (default: current)")):
    """Show power rankings."""
    from cdl import pipeline

    b = pipeline.build_bundle()
    season = season or pipeline.current_season(b)
    rows = pipeline.power_rankings(b, season)
    modes = b.season_modes.get(season, [])
    t = Table("#", "Team", "Rating", *modes, "Series", "Roster", title=f"Power rankings {season}")
    for r in rows:
        t.add_row(str(r["rank"]), r["name"], f"{r['rating']:.0f}", *(f"{r['modes'][m]:.0f}" for m in modes),
                  r["record"], ", ".join(r["roster"]))
    console.print(t)


@app.command("backtest")
def backtest_cmd(eval_from: str = typer.Option("2025-01-01", "--from", help="Evaluate matches from this date")):
    """Walk-forward backtest against baselines; saves data/meta/backtest.json."""
    _setup_logging(False)
    from cdl import pipeline

    s = _run_backtest(pipeline.build_bundle(), eval_from)
    t = Table("Season", "Series", "Acc", "LogLoss", "Elo LogLoss", "Coin", "Exact", "Map LogLoss",
              title="Walk-forward backtest")
    for name, v in s["seasons"].items():
        m, e = v["series_model"], v["series_elo"]
        t.add_row(name, str(m["n"]), f"{m['accuracy']:.1%}", f"{m['log_loss']:.4f}", f"{e['log_loss']:.4f}", "0.6931",
                  f"{v['exact_score']:.1%}", f"{v['maps_model'].get('log_loss', float('nan')):.4f}")
    console.print(t)
    t = Table("Favourite p", "N", "Predicted", "Actual", title="Calibration")
    for c in s.get("calibration", []):
        t.add_row(f"{c['lo']:.0%}-{c['hi']:.0%}", str(c["n"]), f"{c['predicted']:.1%}", f"{c['actual']:.1%}")
    console.print(t)


@app.command()
def site(serve: bool = typer.Option(False, help="Serve site/ on http://localhost:8000 afterwards")):
    """Render the dashboard from current data without scraping."""
    _setup_logging(False)
    _update(scrape=False, notify=False, record=False)
    if serve:
        import functools
        import http.server

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.SITE_DIR))
        console.print("Serving on http://localhost:8000 (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()


@app.command()
def update(
    scrape: bool = typer.Option(True, help="Fetch new data from breakingpoint.gg"),
    notify: bool = typer.Option(True, help="Post to Discord (if DISCORD_WEBHOOK_URL is set)"),
    verbose: bool = False,
):
    """The full automated run: discover, scrape, rebuild, retrain, predict, grade, publish, notify."""
    _setup_logging(verbose)
    try:
        _update(scrape=scrape, notify=notify, record=True)
    except Exception as exc:
        if notify:
            from cdl.publish import discord

            discord.post_alert(f"`cdl update` failed:\n```{traceback.format_exc()[-1800:]}```")
        raise typer.Exit(1) from exc


def _update(scrape: bool, notify: bool, record: bool) -> None:
    from cdl import pipeline
    from cdl.predictions import ledger
    from cdl.publish import discord, graphics
    from cdl.publish import site as site_mod
    from cdl.scrape.next_data import parse_rosters
    from cdl.store import db

    log = logging.getLogger("cdl.update")
    config.ensure_dirs()
    now = datetime.now(timezone.utc)
    new_matches: list[int] = []
    client = None
    if scrape:
        from cdl.scrape.client import BreakingPointClient
        from cdl.scrape.sync import sync

        client = BreakingPointClient()
        res = sync(client, list(config.DEFAULT_SEASONS))
        new_matches = res.new
        log.info("scraped %d new matches (%d failed)", len(res.new), len(res.failed))
        from cdl.scrape import discover

        discover.refresh_rosters(client)

    counts = db.build()
    log.info("database: %s", counts)
    bundle = pipeline.build_bundle()

    if new_matches or not _backtest_path().exists():
        log.info("running backtest")
        backtest_summary = _run_backtest(bundle)
    else:
        backtest_summary = json.loads(_backtest_path().read_text(encoding="utf-8"))

    upcoming_refs = pipeline.upcoming_in_horizon(now)
    preds = []
    for ref in upcoming_refs:
        rosters = None
        if client is not None:
            try:
                rosters = parse_rosters(client.match_page(ref["id"]))
            except Exception as exc:
                log.warning("rosters for %s: %s", ref["id"], exc)
        p = pipeline.predict_match(bundle, ref, rosters)
        try:
            graphics.prediction_card(p)
            p["graphic"] = f"graphics/{p['match_id']}.png"
        except Exception as exc:
            log.warning("graphic for %s: %s", ref["id"], exc)
        preds.append(p)
    if client is not None:
        client.close()
    log.info("predicted %d upcoming matches", len(preds))

    written = ledger.record(preds, now) if record else []
    graded = ledger.grade(pipeline.results_by_match(bundle))
    live = ledger.summarize(graded)
    site_mod.render(bundle, preds, graded, live, backtest_summary, pipeline.current_season(bundle))
    from cdl.publish import feed
    from cdl.scrape import discover as discover_mod

    pipeline.write_json(
        config.SITE_DIR / "api" / "predictions.json",
        feed.build_feed(ledger.load(), feed.schedule_from_index(discover_mod.load_event_index()), live, now,
                        config.SITE_URL),
    )
    log.info("site rendered to %s", config.SITE_DIR)

    if notify and config.DISCORD_WEBHOOK_URL:
        state = ledger.load_notified()
        fresh = [e for e in written if str(e["match_id"]) not in state["predictions"]]
        for mid in discord.post_predictions(fresh):
            state["predictions"][str(mid)] = now.isoformat()
        recent_cut = now - timedelta(days=3)
        new_results = [g for g in graded if g.entry["match_id"] not in state["results"]
                       and datetime.fromisoformat(g.entry["datetime"].replace("Z", "+00:00")) >= recent_cut]
        if new_results and discord.post_results(new_results):
            state["results"].extend(g.entry["match_id"] for g in new_results)
        ledger.save_notified(state)


if __name__ == "__main__":
    app()
