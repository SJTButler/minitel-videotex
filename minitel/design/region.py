"""A focusable pane region with its boundary edges."""

from dataclasses import dataclass

MAIN_REGION = "main"
ACTIVATE_MODES = ("submit", "stay")


@dataclass(frozen=True)
class Region:
    """One focusable pane region.

    The page owns the drawing. The region only names a cursor, the edges to
    follow when that cursor cannot move, and the content key for remembered
    state. The first slice supports a form region and a pager region.
    """

    name: str
    next: str | None = None
    prev: str | None = None
    activate: str = "submit"
    key: object | None = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("region name must be a non-empty string")
        if self.name == MAIN_REGION:
            raise ValueError(
                f"region name {MAIN_REGION!r} is reserved for the implicit region"
            )
        if self.activate not in ACTIVATE_MODES:
            raise ValueError(
                f"region activate must be one of {ACTIVATE_MODES}"
            )
        for edge in (self.next, self.prev):
            if edge is not None:
                if not isinstance(edge, str) or not edge:
                    raise ValueError("region edges must be non-empty names")
                if edge == self.name:
                    raise ValueError("a region cannot point at itself")
        if self.key is not None:
            try:
                hash(self.key)
            except TypeError as exc:
                raise TypeError("region key must be hashable") from exc
