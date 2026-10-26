from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from ..http import Fetcher
from ..models import League


class Source(ABC):
    """One site we scrape. Subclasses yield every league currently listed.

    `scrape` must either finish a complete pass or raise: the store treats a
    completed pass as the full truth and retires leagues that didn't appear,
    so a partial pass that returns normally would wrongly drop leagues.
    """

    name: str

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    @abstractmethod
    def scrape(self) -> Iterator[League]: ...
