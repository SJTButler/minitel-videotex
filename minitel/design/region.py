"""A focusable pane region with its boundary edges."""

from dataclasses import dataclass, field

MAIN_REGION = "main"
PAGE_BACK = "page_back"
ACTIVATE_MODES = ("submit", "stay")
REGION_KINDS = ("form", "pager", "choice")


@dataclass(frozen=True)
class Region:
    """One focusable pane region.

    The page owns the drawing. The region only names a cursor kind, the edges to
    follow when that cursor cannot move, and the layout policy. Runtime content
    (items, key, commit) is bound in ``render(ctx)``.
    """

    name: str
    kind: str = "choice"
    next: str | None = None
    prev: str | None = None
    activate: str = "submit"
    page_size: int | None = None
    optional: bool = False
    wrap: bool = False

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("region name must be a non-empty string")
        if self.name == MAIN_REGION:
            raise ValueError(
                f"region name {MAIN_REGION!r} is reserved for the implicit region"
            )
        if self.kind not in REGION_KINDS:
            raise ValueError(
                f"region kind must be one of {REGION_KINDS}"
            )
        if self.activate not in ACTIVATE_MODES:
            raise ValueError(
                f"region activate must be one of {ACTIVATE_MODES}"
            )
        if self.page_size is not None:
            if not isinstance(self.page_size, int) or self.page_size < 1:
                raise ValueError("region page_size must be a positive integer")
            if self.kind == "form":
                raise ValueError("a form region cannot declare page_size")
        if not isinstance(self.optional, bool):
            raise TypeError("region optional must be a bool")
        if self.wrap:
            raise ValueError("named regions do not support wrap")
        for edge in (self.next, self.prev):
            if edge is not None:
                if not isinstance(edge, str) or not edge:
                    raise ValueError("region edges must be non-empty names")
                if edge == self.name:
                    raise ValueError("a region cannot point at itself")
        if self.next == PAGE_BACK:
            raise ValueError("page_back is only valid as a prev edge")


@dataclass(frozen=True)
class MainRegion:
    """The implicit single-cursor region used by pane pages without regions."""

    kind: str
    page_size: int | None = None
    name: str = field(default=MAIN_REGION, init=False)
    next: str | None = None
    prev: str | None = None
    activate: str = "submit"
    optional: bool = False
    wrap: bool = True

    def __post_init__(self):
        if self.kind not in REGION_KINDS:
            raise ValueError(
                f"main region kind must be one of {REGION_KINDS}"
            )
        if self.page_size is not None and (
            not isinstance(self.page_size, int) or self.page_size < 1
        ):
            raise ValueError("main region page_size must be positive")


def validate_regions(regions, *, default_focus=None, form=False, scroll=False):
    """Validate a static page region graph at page-definition time."""
    regions = tuple(regions)
    if not regions:
        return
    if scroll:
        raise ValueError("named regions are pane-only")
    names = []
    form_regions = []
    for region in regions:
        if not isinstance(region, Region):
            raise TypeError("regions must be Region values")
        if region.name in names:
            raise ValueError(f"duplicate region name {region.name!r}")
        names.append(region.name)
        if region.kind == "form":
            form_regions.append(region.name)
    for region in regions:
        for edge in (region.next, region.prev):
            if edge is None or edge == PAGE_BACK:
                continue
            if edge not in names:
                raise ValueError(
                    f"region {region.name!r} points at unknown region {edge!r}"
                )
    if default_focus is not None and default_focus not in names:
        raise ValueError(f"unknown default focus {default_focus!r}")
    if len(form_regions) > 1:
        raise ValueError("a page may declare at most one form region")
    if form_regions and not form:
        raise ValueError("a named form region requires form=True")
    if form and not form_regions:
        raise ValueError("form=True requires a form region")
