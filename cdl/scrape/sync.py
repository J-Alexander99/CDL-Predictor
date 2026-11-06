"""Discover + scrape: bring ``data/raw`` up to date with the site."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cdl.scrape import discover
from cdl.scrape.client import BreakingPointClient
from cdl.scrape.next_data import SchemaError, trim_match
from cdl.store import raw

log = logging.getLogger(__name__)


@dataclass
class SyncResult:
    new: list[int] = field(default_factory=list)
    failed: dict[int, str] = field(default_factory=dict)
    requests: int = 0


def scrape_match(client: BreakingPointClient, match_id: int) -> dict:
    return trim_match(client.match_page(match_id), source=f"/match/{match_id}")


def sync(
    client: BreakingPointClient,
    seasons: list[int],
    force_events: bool = False,
    limit: int | None = None,
    progress=None,
) -> SyncResult:
    result = SyncResult()
    index = discover.refresh(client, seasons, force=force_events)
    have = raw.stored_ids()
    todo = [m for m in discover.completed_matches(index, seasons) if m["id"] not in have]
    if limit:
        todo = todo[:limit]
    log.info("sync: %d completed matches to scrape", len(todo))
    schema_failures = 0
    for i, ref in enumerate(todo, 1):
        try:
            record = scrape_match(client, ref["id"])
        except SchemaError as exc:
            schema_failures += 1
            result.failed[ref["id"]] = str(exc)
            log.error("%s", exc)
            if schema_failures >= 3:
                raise  # systematic breakage: stop and surface it
            continue
        except Exception as exc:
            result.failed[ref["id"]] = repr(exc)
            log.warning("match %s: %r", ref["id"], exc)
            continue
        if record["status"] != "complete":
            continue
        raw.save(record)
        result.new.append(ref["id"])
        if progress:
            progress(i, len(todo), ref)
    result.requests = client.requests_made
    return result
