"""Page 160: search index for the linked Wikipedia reader."""

from minitel.pagemodel import LINE_FIELD, page

from ..common.header import AnnouncementHeader
from ..common.reader import index_screen
from ._support.state import (
    ARTICLE_PAGE,
    INDEX_PAGE,
    PAGE_SIZE,
    READER_QUERY,
    READER_RESET,
    READER_RESULTS,
    READER_RETURN,
    READER_RETURN_SELECTED,
    READER_SEARCH_LOADED,
)


def _index(ctx, service):
    query = str(ctx.state.get(READER_QUERY, ""))
    snapshot = service.search(query)
    results = tuple(snapshot.value or ()) if snapshot.has_value else ()
    ctx.state[READER_RESULTS] = results
    returning = ctx.state.pop(READER_RETURN, False)
    saved = ctx.state.pop(READER_RETURN_SELECTED, None)
    if returning:
        ctx.values[LINE_FIELD] = query
    reset = ctx.state.pop(READER_RESET, False)
    choice = ctx.set_choice(
        len(results), PAGE_SIZE,
        selected=saved if returning else None,
        reset=reset,
    )
    if snapshot.error is not None and not snapshot.has_value:
        status_text = "SEARCH UNAVAILABLE"
    elif not snapshot.has_value:
        status_text = "SEARCHING..."
    elif not results:
        status_text = "TYPE TO SEARCH" if not query else "NO RESULTS"
    else:
        word = "RESULT" if len(results) == 1 else "RESULTS"
        status_text = f"{len(results)} {word}"
    screen = index_screen(
        ctx, results, choice,
        title="WIKIPEDIA",
        query=query,
        status_text=status_text,
        hint="TYPE+ENVOI=SEARCH  SUITE/RETOUR=SELECT",
        source="WIKIPEDIA. CC BY-SA.",
        page=INDEX_PAGE,
    )
    if snapshot.has_value and ctx.state.get(READER_SEARCH_LOADED) != query:
        screen.force_full = True
        ctx.state[READER_SEARCH_LOADED] = query
    return screen


def _render(ctx):
    service = ctx.service("wikipedia")
    if service is None:
        choice = ctx.set_choice(0, PAGE_SIZE)
        return index_screen(
            ctx, (), choice,
            title="WIKIPEDIA",
            query="",
            status_text="READER NOT CONFIGURED",
            hint="TYPE+ENVOI=SEARCH  SUITE/RETOUR=SELECT",
            source="WIKIPEDIA. CC BY-SA.",
            page=INDEX_PAGE,
        )
    return _index(ctx, service)


def _selected_result(ctx):
    results = ctx.state.get(READER_RESULTS, ())
    choice = ctx.choice
    if choice is None or not choice.total or not results:
        return None
    index = choice.selected if choice.selected is not None else 0
    if not 0 <= index < len(results):
        return None
    ctx.state[READER_RETURN] = True
    ctx.state[READER_RETURN_SELECTED] = index
    return f"{ARTICLE_PAGE}#{results[index].token}"


def _submit(ctx, line):
    value = line.strip()
    query = str(ctx.state.get(READER_QUERY, ""))
    if not value:
        route = _selected_result(ctx)
        if route is not None:
            return route
        ctx.state[READER_QUERY] = ""
        ctx.state[READER_RESET] = True
        return INDEX_PAGE
    if value != query:
        ctx.state[READER_QUERY] = value
        ctx.state[READER_RESET] = True
        return INDEX_PAGE
    return _selected_result(ctx) or INDEX_PAGE


@page(
    INDEX_PAGE,
    title="WIKIPEDIA",
    aliases=("6",),
    requires=("wikipedia",),
    tick_interval=1.0,
    header=AnnouncementHeader(),
    on_submit=_submit,
    on_tick=_render,
)
def wikipedia_index(ctx):
    return _render(ctx)
