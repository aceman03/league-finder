from .base import Source
from .bowlero import BowleroSource

SOURCES: dict[str, type[Source]] = {
    BowleroSource.name: BowleroSource,
}
