"""A selectable window over a paged list.

The outer Pager decides which page is visible; the Choice adds one selected
article. SUITE/RETOUR move the selection; when it crosses a page boundary the
outer Pager follows, so the user pages through articles rather than through
pages.
"""

from dataclasses import dataclass, replace

from .pager import Pager


def _pager_for(pager, selected):
    page = selected // pager.page_size
    while pager.page_index < page:
        pager = pager.next()
    while pager.page_index > page:
        pager = pager.prev()
    return pager


@dataclass(frozen=True)
class Choice:
    pager: Pager
    selected: int | None = None
    wrap: bool = False

    @property
    def total(self):
        return self.pager.total

    @property
    def page_size(self):
        return self.pager.page_size

    @property
    def page_count(self):
        return self.pager.page_count

    @property
    def page_index(self):
        return self.pager.page_index

    @property
    def offset(self):
        return self.pager.clamp().offset

    @property
    def label(self):
        return self.pager.label

    @property
    def selected_index(self):
        return self.selected

    def clamp(self):
        pager = self.pager.clamp()
        if not pager.total:
            return replace(self, pager=pager, selected=None)
        selected = (
            0 if self.selected is None
            else min(max(int(self.selected), 0), pager.total - 1)
        )
        return replace(
            self, pager=_pager_for(pager, selected), selected=selected
        )

    def window(self, items):
        return self.pager.window(items)

    def next(self):
        view = self.clamp()
        if not view.total:
            return view
        if view.selected is None:
            selected = 0
        elif view.selected + 1 < view.total:
            selected = view.selected + 1
        elif view.wrap:
            selected = 0
        else:
            selected = view.total - 1
        return replace(
            view, selected=selected, pager=_pager_for(view.pager, selected)
        )

    def prev(self):
        view = self.clamp()
        if not view.total:
            return view
        if view.selected is None or view.selected <= 0:
            selected = view.total - 1 if view.wrap else 0
        else:
            selected = view.selected - 1
        return replace(
            view, selected=selected, pager=_pager_for(view.pager, selected)
        )
