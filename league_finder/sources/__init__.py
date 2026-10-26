from .base import Source
from .bowlero import BowleroSource
from .leaguepals import LeaguePalsSource

SOURCES: dict[str, type[Source]] = {
    BowleroSource.name: BowleroSource,
    LeaguePalsSource.name: LeaguePalsSource,
}
