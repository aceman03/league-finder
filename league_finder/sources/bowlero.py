"""Bowlero / Lucky Strike.

Each center has its own league page at
https://www.bowlero.com/location/<center-slug>/leagues (Lucky Strike centers
are being folded into the same site). The plan is:

1. Discover center slugs from the site's location directory or sitemap.
2. Fetch each center's leagues page and parse the league listings.

TODO: the page markup (or the JSON API behind it, if the page is rendered
client-side) hasn't been inspected yet, so discovery and parsing are not
written. Check the browser network tab first: a JSON endpoint is far more
reliable than parsing HTML.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..models import League
from .base import Source

BASE_URL = "https://www.bowlero.com"


class BowleroSource(Source):
    name = "bowlero"

    def center_slugs(self) -> list[str]:
        raise NotImplementedError("center discovery not written yet")

    def parse_center(self, slug: str, html: str) -> list[League]:
        raise NotImplementedError("league page parsing not written yet")

    def scrape(self) -> Iterator[League]:
        for slug in self.center_slugs():
            resp = self.fetcher.get(f"{BASE_URL}/location/{slug}/leagues")
            yield from self.parse_center(slug, resp.text)
