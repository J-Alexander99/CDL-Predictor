"""Shareable PNG prediction cards (successor of the legacy graphics generator).

Team 1 is always palette slot 1 (blue) and team 2 slot 2 (orange): a
colour-blind-safe pair validated on the dark surface. Brand identity comes
from the logos and names, never from colour alone.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path

import httpx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from PIL import Image  # noqa: E402

from cdl import config  # noqa: E402

log = logging.getLogger(__name__)

SURFACE = "#1a1a19"
PANEL = "#232322"
TEXT = "#f0efec"
TEXT_2 = "#c3c2b7"
MUTED = "#8a8980"
GRID = "#383835"
TEAM1 = "#3987e5"
TEAM2 = "#d95926"


def _logo(url: str | None) -> Image.Image | None:
    if not url:
        return None
    cache = config.BUILD_DIR / "logos"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (url.rsplit("/", 1)[-1].split("?")[0] or "logo")
    try:
        if not path.exists():
            r = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": config.USER_AGENT})
            r.raise_for_status()
            path.write_bytes(r.content)
        return Image.open(io.BytesIO(path.read_bytes())).convert("RGBA")
    except Exception as exc:  # a missing logo must never break the pipeline
        log.debug("logo %s: %s", url, exc)
        return None


def _split_bar(ax, y: float, p: float, height: float, label: bool = True, fontsize: int = 11) -> None:
    """One whole split in two: team1 share | 2px surface gap | team2 share."""
    gap = 0.004
    ax.add_patch(FancyBboxPatch((0, y - height / 2), max(p - gap / 2, 0), height,
                                boxstyle="round,pad=0,rounding_size=0.01", fc=TEAM1, ec="none"))
    ax.add_patch(FancyBboxPatch((p + gap / 2, y - height / 2), max(1 - p - gap / 2, 0), height,
                                boxstyle="round,pad=0,rounding_size=0.01", fc=TEAM2, ec="none"))
    if label:
        ax.text(0.012, y, f"{p:.0%}", va="center", ha="left", color=TEXT, fontsize=fontsize, fontweight="bold")
        ax.text(0.988, y, f"{1 - p:.0%}", va="center", ha="right", color=TEXT, fontsize=fontsize, fontweight="bold")


def prediction_card(pred: dict, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or config.GRAPHICS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    t1, t2 = pred["team1"], pred["team2"]
    p = pred["p_team1"]

    fig = plt.figure(figsize=(12, 7.2), dpi=150, facecolor=SURFACE)
    fig.text(0.5, 0.94, f"{t1['name']}  vs  {t2['name']}", ha="center", va="center",
             color=TEXT, fontsize=21, fontweight="bold")
    when = datetime.fromisoformat(pred["datetime"].replace("Z", "+00:00")).strftime("%a %d %b %Y · %H:%M UTC")
    sub = " · ".join(x for x in (pred.get("event_name"), pred.get("round"), when) if x)
    fig.text(0.5, 0.895, sub, ha="center", va="center", color=TEXT_2, fontsize=10.5)

    for img, x in ((_logo(t1.get("logo")), 0.035), (_logo(t2.get("logo")), 0.865)):
        if img is not None:
            ax = fig.add_axes([x, 0.80, 0.10, 0.17])
            ax.imshow(img)
            ax.axis("off")

    # Hero: series win probability
    ax = fig.add_axes([0.06, 0.66, 0.88, 0.17])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fav, fav_p = (t1["name"], p) if p >= 0.5 else (t2["name"], 1 - p)
    ax.text(0.5, 0.86, f"{fav} {fav_p:.0%} to win · most likely {pred['likely_score_label']}",
            ha="center", va="center", color=TEXT, fontsize=14)
    _split_bar(ax, 0.38, p, 0.36, fontsize=14)
    # Legend keys: colour swatch + name (identity is never colour alone)
    ax.add_patch(FancyBboxPatch((0.0, -0.06), 0.012, 0.12, boxstyle="round,pad=0,rounding_size=0.003", fc=TEAM1, ec="none"))
    ax.text(0.018, 0.0, t1["name"], ha="left", va="center", color=TEXT_2, fontsize=10)
    ax.add_patch(FancyBboxPatch((0.988, -0.06), 0.012, 0.12, boxstyle="round,pad=0,rounding_size=0.003", fc=TEAM2, ec="none"))
    ax.text(0.982, 0.0, t2["name"], ha="right", va="center", color=TEXT_2, fontsize=10)

    # Score distribution
    ax = fig.add_axes([0.06, 0.12, 0.36, 0.45], facecolor=SURFACE)
    scores = list(pred["scores"].items())
    labels = [s for s, _ in scores]
    vals = [v for _, v in scores]
    colors = [TEAM1 if int(s.split("-")[0]) > int(s.split("-")[1]) else TEAM2 for s in labels]
    ys = list(range(len(labels)))[::-1]
    ax.barh(ys, vals, color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    for y, v in zip(ys, vals, strict=True):
        ax.text(v + 0.01, y, f"{v:.0%}", va="center", ha="left", color=TEXT, fontsize=10)
    ax.set_yticks(ys, [f"{s}" for s in labels], color=TEXT_2, fontsize=10)
    ax.set_xlim(0, max(vals) * 1.25 if vals else 1)
    ax.set_xticks([])
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Series score (team 1 first)", color=TEXT, fontsize=12, loc="left", pad=8)

    # Map-by-map
    ax = fig.add_axes([0.50, 0.12, 0.44, 0.45])
    ax.set_xlim(0, 1)
    slots = pred.get("slots", [])
    n = max(len(slots), 1)
    ax.set_ylim(-0.5, n - 0.5)
    ax.axis("off")
    ax.set_title("Map by map (likely map from veto history)", color=TEXT, fontsize=12, loc="left", pad=8)
    for i, s in enumerate(slots):
        y = n - 1 - i
        name = f"Map {s['game_num']} · {s['mode']}" + (f" · {s['likely_map']}" if s.get("likely_map") else "")
        ax.text(0, y + 0.28, name, ha="left", va="center", color=TEXT_2, fontsize=9.5)
        _split_bar(ax, y - 0.08, s["p_team1"], 0.34, fontsize=9)

    ratings = pred.get("ratings", {})
    foot = (f"Ratings {t1['name']} {ratings.get('team1', '–')} · {t2['name']} {ratings.get('team2', '–')}   "
            f"|   Model {pred.get('model_version', '')} · data: breakingpoint.gg")
    fig.text(0.5, 0.035, foot, ha="center", va="center", color=MUTED, fontsize=8.5)

    path = out_dir / f"{pred['match_id']}.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path
