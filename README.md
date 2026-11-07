# CDL Predictor

Automated Call of Duty League data pipeline and match predictor.

Every two hours a GitHub Action:

1. **discovers** new CDL events and matches on [breakingpoint.gg](https://breakingpoint.gg) (no URL lists to maintain),
2. **scrapes** every newly completed match (maps, modes, scores, picks and bans, ~40 stats per player per map),
3. **rebuilds** the database and **retrains** the model,
4. **predicts** every CDL match starting in the next 72 hours, and **locks** each prediction before kickoff,
5. **grades** finished predictions into a public track record,
6. **publishes** a dashboard to GitHub Pages, writes PNG prediction cards, and posts to Discord.

## How it works

| Step | Module | Notes |
|---|---|---|
| Fetch | `cdl/scrape/client.py` | Plain HTTP (no Selenium). Every page embeds its data as JSON in `<script id="__NEXT_DATA__">`. Requests are throttled to 1 per second, with retries. |
| Parse | `cdl/scrape/next_data.py` | Validated with pydantic. If the site changes shape, the run fails loudly and Discord gets an alert. |
| Discover | `cdl/scrape/discover.py` | `/matches` lists every season and event. Event pages list their matches. CDL events have `division_id == 3`. Challengers events (`division_id == 1`) are also collected from the 2027 season on, but the model doesn't use them yet: `db.load()` returns CDL matches only. Finished events are never fetched again. |
| Store | `data/raw/{season}/{match}.json.gz` | Committed, append-only, deterministic. Everything else is rebuilt from it. |
| Database | `cdl/store/db.py` → `build/cdl.db` | SQLite keyed by Breaking Point ids. Rebrands like Breach → M80 don't split history. |
| Ratings | `cdl/model/ratings.py` | Map-level Elo for teams and players, with per-mode offsets and carry-over between seasons. |
| Features | `cdl/model/features.py` | Point-in-time only: team and roster rating diffs, form, BP-rating form, map specialisation. |
| Map model | `cdl/model/map_model.py` | Symmetric logistic regression with recency weighting. |
| Series | `cdl/model/series.py` | Season mode order, map distribution from veto history, then an exact score distribution. |
| Backtest | `cdl/model/backtest.py` | Walk-forward: refit before every event, blind to the maps played, compared against Elo-only and coin-flip baselines. |
| Ledger | `data/predictions/ledger.jsonl` | Append-only. Grading uses the last snapshot made before the match started. |
| Publish | `cdl/publish/` | Static site (`site/`), PNG cards, Discord webhook. |

## Usage

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows (source .venv/bin/activate elsewhere)
pip install -e ".[dev]"

cdl backfill --seasons 2024-2027     # one-off: scrape history (~880 matches, ~35 min)
cdl update --no-notify               # the full automated run, locally
cdl predict "OpTic" "FaZe" -g        # any matchup, with a PNG card
cdl ratings                          # power rankings
cdl backtest                         # walk-forward evaluation
cdl scrape-match 214951              # inspect a single match
cdl site --serve                     # render the dashboard and serve it on localhost:8000
pytest                               # tests run on saved page fixtures (offline)
```

## One-time GitHub setup

1. **Settings → Pages → Source: GitHub Actions.**
2. **Settings → Secrets and variables → Actions:**
   - secret `DISCORD_WEBHOOK_URL`: a channel webhook. Optional; without it Discord is skipped.
   - variable `CDL_SITE_URL`: your Pages URL, e.g. `https://<user>.github.io/CDL-Predictor/`. Optional, used for links.
3. **Actions → "Update data & predictions" → Run workflow.** Use the backfill input once if `data/raw` is empty.

## Layout

```
cdl/            the package (scrape, store, model, predictions, publish, cli)
data/raw/       scraped matches (committed)
data/meta/      catalog, event index, latest backtest (committed)
data/predictions/  prediction ledger + notification state (committed)
tests/          offline tests + saved page fixtures (tests/make_fixtures.py refreshes them)
legacy/         the v2 code (Selenium scraper, CLI, models), kept for reference
```
