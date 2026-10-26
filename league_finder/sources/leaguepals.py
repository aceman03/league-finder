"""LeaguePals.

LeaguePals lets bowlers search for leagues by zip code and join them. The
search is backed by an app API rather than static pages, so the likely
approach is to call the same endpoint the web app uses, sweeping a grid of
zip codes / coordinates to cover the area we care about.

TODO: the endpoint, its parameters, and whether it needs a login haven't
been checked yet. If league details require an account, ask LeaguePals
about a data feed or partnership before going further; scraping behind a
login is where terms-of-service trouble starts.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..models import League
from .base import Source


class LeaguePalsSource(Source):
    name = "leaguepals"

    def scrape(self) -> Iterator[League]:
        raise NotImplementedError("LeaguePals scraping not written yet")
