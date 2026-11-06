"""Discord webhook notifications: new predictions, graded results, pipeline alerts."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from cdl import config
from cdl.predictions.ledger import Graded

log = logging.getLogger(__name__)

BLUE = 0x3987E5
GREEN = 0x0CA30C
RED = 0xD03B3B


def _post(payload: dict, file: Path | None = None, url: str | None = None) -> bool:
    url = url or config.DISCORD_WEBHOOK_URL
    if not url:
        return False
    for attempt in range(3):
        try:
            if file and file.exists():
                resp = httpx.post(url, data={"payload_json": json.dumps(payload)},
                                  files={"files[0]": (file.name, file.read_bytes(), "image/png")}, timeout=30)
            else:
                resp = httpx.post(url, json=payload, timeout=30)
            if resp.status_code == 429:
                time.sleep(float(resp.json().get("retry_after", 2)))
                continue
            resp.raise_for_status()
            time.sleep(1.0)  # stay well under webhook rate limits
            return True
        except httpx.HTTPError as exc:
            log.warning("discord post failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(2)
    return False


def prediction_embed(p: dict, image_name: str | None = None) -> dict:
    t1, t2 = p["team1"]["name"], p["team2"]["name"]
    fav, fav_p = (t1, p["p_team1"]) if p["p_team1"] >= 0.5 else (t2, 1 - p["p_team1"])
    lines = [
        f"Map {s['game_num']} · {s['mode']}{(' · ' + s['likely_map']) if s.get('likely_map') else ''}: "
        f"{t1} {s['p_team1']:.0%} – {1 - s['p_team1']:.0%} {t2}"
        for s in p.get("slots", [])
    ]
    embed = {
        "title": f"{t1} vs {t2}",
        "description": f"**{fav} {fav_p:.0%}** to win · most likely **{p['likely_score_label']}**",
        "color": BLUE,
        "fields": [
            {"name": "When", "value": f"<t:{_unix(p['datetime'])}:F>", "inline": True},
            {"name": "Event", "value": " · ".join(x for x in (p.get("event_name"), p.get("round")) if x) or "–",
             "inline": True},
            {"name": "Map by map", "value": "\n".join(lines)[:1024] or "–", "inline": False},
        ],
        "footer": {"text": f"CDL Predictor v{p.get('model_version', '')} · locked at match start"},
    }
    if config.SITE_URL:
        embed["url"] = config.SITE_URL
    if image_name:
        embed["image"] = {"url": f"attachment://{image_name}"}
    return embed


def _unix(iso: str) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def post_predictions(preds: list[dict], graphics_dir: Path | None = None) -> list[int]:
    sent = []
    for p in preds:
        img = (graphics_dir or config.GRAPHICS_DIR) / f"{p['match_id']}.png"
        ok = _post({"embeds": [prediction_embed(p, img.name if img.exists() else None)]},
                   file=img if img.exists() else None)
        if ok:
            sent.append(p["match_id"])
    return sent


def post_results(graded: list[Graded]) -> bool:
    if not graded:
        return True
    lines = []
    for g in graded[:20]:
        e = g.entry
        fav_is_1 = e["p_team1"] >= 0.5
        fav = e["team1"]["name"] if fav_is_1 else e["team2"]["name"]
        fav_p = e["p_team1"] if fav_is_1 else 1 - e["p_team1"]
        mark = "✅" if g.correct else "❌"
        lines.append(f"{mark} {e['team1']['name']} {g.score} {e['team2']['name']} · predicted {fav} {fav_p:.0%}"
                     + (" · exact score!" if g.exact else ""))
    correct = sum(g.correct for g in graded)
    embed = {
        "title": f"Results: {correct}/{len(graded)} called correctly",
        "description": "\n".join(lines)[:4000],
        "color": GREEN if correct * 2 >= len(graded) else RED,
    }
    if config.SITE_URL:
        embed["url"] = config.SITE_URL + "record.html"
    return _post({"embeds": [embed]})


def post_alert(message: str) -> bool:
    return _post({"embeds": [{"title": "⚠️ CDL Predictor pipeline problem", "description": message[:4000], "color": RED}]})
