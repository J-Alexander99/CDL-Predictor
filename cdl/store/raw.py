"""Append-only store of trimmed match payloads: ``data/raw/{season}/{match_id}.json.gz``.

Files are written deterministically (sorted keys, gzip mtime=0) so re-scraping
an unchanged match produces no git diff.
"""
from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from pathlib import Path

from cdl import config


def _path(season: int, match_id: int, root: Path | None = None) -> Path:
    return (root or config.RAW_DIR) / str(season) / f"{match_id}.json.gz"


def stored_ids(root: Path | None = None) -> set[int]:
    base = root or config.RAW_DIR
    if not base.exists():
        return set()
    return {int(p.name.split(".")[0]) for p in base.glob("*/*.json.gz")}


def _dump(record: dict) -> bytes:
    body = {k: v for k, v in record.items() if k != "scraped_at"}
    body["scraped_at"] = record.get("scraped_at")
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def save(record: dict, root: Path | None = None) -> Path:
    path = _path(record["event"]["season_id"], record["id"], root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ignore scraped_at when deciding whether anything changed
    if path.exists():
        old = load_path(path)
        if {k: v for k, v in old.items() if k != "scraped_at"} == {
            k: v for k, v in record.items() if k != "scraped_at"
        }:
            return path
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
        gz.write(_dump(record))
    return path


def load_path(path: Path) -> dict:
    with gzip.open(path, "rb") as gz:
        return json.loads(gz.read())


def iter_all(root: Path | None = None) -> Iterator[dict]:
    base = root or config.RAW_DIR
    for path in sorted(base.glob("*/*.json.gz")):
        yield load_path(path)
