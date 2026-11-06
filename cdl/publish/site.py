"""Render the static dashboard into ``site/`` (deployed to GitHub Pages)."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from cdl import config
from cdl.pipeline import MODEL_VERSION, Bundle, power_rankings, write_json
from cdl.predictions.ledger import Graded


def _env() -> Environment:
    return Environment(loader=PackageLoader("cdl.publish", "templates"), autoescape=select_autoescape(["html"]))


def _when(iso: str) -> str:
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%a %d %b · %H:%M UTC")


def calibration_svg(bins: list[dict], w: int = 640, h: int = 340) -> str:
    """Predicted vs actual for the favourite. One series + dashed reference."""
    if not bins:
        return '<p class="muted">Not enough data.</p>'
    left, right, top, bottom = 52, 16, 12, 40
    pw, ph = w - left - right, h - top - bottom
    lo = 0.4
    x = lambda v: left + (v - 0.5) / 0.5 * pw  # noqa: E731
    y = lambda v: top + (1 - (v - lo) / (1 - lo)) * ph  # noqa: E731
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Calibration chart: predicted versus actual win rate">']
    for t in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        parts.append(f'<line class="gridline" x1="{left}" x2="{w - right}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        parts.append(f'<text class="axis-label" x="{left - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{t:.0%}</text>')
    for t in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        parts.append(f'<text class="axis-label" x="{x(t):.1f}" y="{h - 18}" text-anchor="middle">{t:.0%}</text>')
    parts.append(f'<text class="axis-label" x="{left + pw / 2:.1f}" y="{h - 2}" text-anchor="middle">Predicted win probability of favourite</text>')
    parts.append(f'<line class="ref" x1="{x(0.5):.1f}" y1="{y(0.5):.1f}" x2="{x(1.0):.1f}" y2="{y(1.0):.1f}"/>')
    pts = [(x(b["predicted"]), y(max(b["actual"], lo))) for b in bins]
    parts.append('<polyline class="series" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
    for (px, py), b in zip(pts, bins, strict=True):
        tip = (f"Favourite at {b['lo']:.0%}–{b['hi']:.0%}<br>Predicted {b['predicted']:.1%} · "
               f"actual {b['actual']:.1%}<br>{b['n']} series")
        parts.append(f'<circle class="dot" cx="{px:.1f}" cy="{py:.1f}" r="5"/>')
        parts.append(f'<circle class="hit" cx="{px:.1f}" cy="{py:.1f}" r="16" data-tip="{tip}"/>')
    parts.append("</svg>")
    return "".join(parts)


def _graded_rows(graded: list[Graded], limit: int = 40) -> list[dict]:
    rows = []
    for g in graded[:limit]:
        e = g.entry
        fav_is_1 = e["p_team1"] >= 0.5
        rows.append({
            "when": _when(e["datetime"]), "team1": e["team1"]["name"], "team2": e["team2"]["name"],
            "fav": e["team1"]["name"] if fav_is_1 else e["team2"]["name"],
            "fav_p": e["p_team1"] if fav_is_1 else 1 - e["p_team1"],
            "score": g.score, "correct": g.correct, "exact": g.exact,
        })
    return rows


def _team_recent(bundle: Bundle, team_id: int, limit: int = 15) -> list[dict]:
    m = bundle.frames.matches
    m = m[(m.team_1_id == team_id) | (m.team_2_id == team_id)].tail(limit).iloc[::-1]
    events = dict(zip(bundle.frames.events.id, bundle.frames.events.name, strict=True))
    out = []
    for r in m.itertuples(index=False):
        is1 = r.team_1_id == team_id
        opp = r.team_2_id if is1 else r.team_1_id
        a, b = (r.team_1_score, r.team_2_score) if is1 else (r.team_2_score, r.team_1_score)
        event = " · ".join(x for x in (events.get(r.event_id, ""), r.round or "") if x)
        out.append({"when": r.datetime.strftime("%d %b %Y"), "event": event, "opponent": bundle.team(int(opp))["name"],
                    "score": f"{a}-{b}", "won": r.winner_id == team_id})
    return out


def render(
    bundle: Bundle,
    upcoming: list[dict],
    graded: list[Graded],
    live_summary: dict,
    backtest_summary: dict | None,
    season: int,
    out_dir: Path | None = None,
) -> Path:
    out = out_dir or config.SITE_DIR
    out.mkdir(parents=True, exist_ok=True)
    static = out / "static"
    static.mkdir(exist_ok=True)
    shutil.copyfile(resources.files("cdl.publish").joinpath("static/style.css"), static / "style.css")

    env = _env()
    common = {
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        "model_version": MODEL_VERSION,
        "horizon": config.PREDICTION_HORIZON_H,
    }
    for p in upcoming:
        p["when"] = _when(p["datetime"])
    rankings = power_rankings(bundle, season)
    season_row = bundle.frames.seasons.loc[bundle.frames.seasons.id == season]
    season_title = f"{season} · {season_row.title.iloc[0]}" if len(season_row) else str(season)
    modes = bundle.season_modes.get(season, [])
    backtest_summary = backtest_summary or {"seasons": {}, "calibration": []}

    pages = {
        "index.html": ("index.html", {"page": "index", "upcoming": upcoming, "graded": _graded_rows(graded)}),
        "rankings.html": ("rankings.html", {"page": "rankings", "rankings": rankings, "modes": modes,
                                            "season_title": season_title}),
        "record.html": ("record.html", {"page": "record", "live": live_summary, "backtest": backtest_summary,
                                        "calibration_svg": calibration_svg(backtest_summary.get("calibration", []))}),
    }
    for name, (tpl, ctx) in pages.items():
        (out / name).write_text(env.get_template(tpl).render(root="", **common, **ctx), encoding="utf-8")

    teams_dir = out / "teams"
    teams_dir.mkdir(exist_ok=True)
    rank_by_id = {r["id"]: r for r in rankings}
    team_ids = set(rank_by_id) | {p["team1"]["id"] for p in upcoming} | {p["team2"]["id"] for p in upcoming}
    for tid in team_ids:
        ctx = {
            "page": "team", "team": bundle.team(tid), "rank": rank_by_id.get(tid),
            "roster": [bundle.player_tag(p) for p in bundle.roster(tid)],
            "recent": _team_recent(bundle, tid),
        }
        (teams_dir / f"{tid}.html").write_text(env.get_template("team.html").render(root="../", **common, **ctx),
                                              encoding="utf-8")

    write_json(out / "data.json", {
        "generated": common["generated"], "upcoming": upcoming, "rankings": rankings,
        "live": live_summary, "backtest": backtest_summary,
    })
    (out / ".nojekyll").write_text("")
    return out
