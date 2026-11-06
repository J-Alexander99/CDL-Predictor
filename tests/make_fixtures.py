"""Refresh the saved page fixtures used by the parser tests.

Run:  python tests/make_fixtures.py
Only the __NEXT_DATA__ script is kept (gzipped) to keep fixtures small.
"""
import gzip
import re
from pathlib import Path

from cdl.scrape.client import BreakingPointClient

FIXTURES = Path(__file__).parent / "fixtures"
PAGES = {
    "match_214951.html.gz": "/match/214951/x",   # 2026 BO5, Overload, Riyadh 3-1 Miami
    "match_358722.html.gz": "/match/358722/x",   # 2027 MW4, Hijack, KOI 3-0 M80
    "match_35633.html.gz": "/match/35633/x",     # 2024 MWIII, Control, LAN
    "event_104.html.gz": "/events/104",          # CDL Major 3 Qualifier 2026 (final)
    "event_1244.html.gz": "/events/1244",        # Launch Invitational 2027 (live)
    "event_187.html.gz": "/events/187",          # CDC EMEA (non-CDL division)
    "matches.html.gz": "/matches",
    "team_4.html.gz": "/teams/4",                # OpTic Texas: players + creators/retired members
}

if __name__ == "__main__":
    FIXTURES.mkdir(exist_ok=True)
    with BreakingPointClient() as c:
        for name, path in PAGES.items():
            html = c.get_html(path)
            script = re.search(r'<script id="__NEXT_DATA__"[^>]*>.*?</script>', html, re.S).group(0)
            with open(FIXTURES / name, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
                gz.write(f"<html><body>{script}</body></html>".encode())
            print(name, (FIXTURES / name).stat().st_size)
