"""Page 160: linked reader over the wikipedia service.

Phase 2 serves fixture documents; Phase 3 replaces the service source with the
real Wikipedia API without changing this page.
"""

from minitel.pagemodel import LINE_FIELD, page

from services.common.reader import match_prefix

from .common.reader import (
    Line,
    LineSpan,
    article_screen,
    build_stops,
    index_screen,
    render_lines,
    starts_for,
    visible_matches,
)

PAGE = "160"
PAGE_SIZE = 7
READER_QUERY = "reader_query"
READER_RESET = "reader_reset"
READER_RESULTS = "reader_results"
READER_LINES = "reader_lines"
READER_SEARCH_LOADED = "reader_search_loaded"
READER_FIND = "reader_find"
READER_VISIBLE = "reader_visible"
READER_LOADED = "reader_loaded"
READER_RETURN = "reader_return"
READER_RETURN_SELECTED = "reader_return_selected"


def _current(ctx):
    return f"{PAGE}#{ctx.extension}" if ctx.extension else PAGE


def _message(ctx, text):
    lines = (Line("body", (LineSpan(text),)),)
    view = ctx.set_viewport(1, 24, step=8, follow=False)
    ctx.set_stops(())
    return article_screen(
        ctx, lines, view, buffer=ctx.input_value,
        status_text="GUIDE=INDEX",
    )


def _lines(ctx, document):
    cache = ctx.state.setdefault(READER_LINES, {})
    key = (document.token, document.revision)
    lines = cache.get(key)
    if lines is None:
        lines = render_lines(document)
        cache[key] = lines
        while len(cache) > 2:
            cache.pop(next(iter(cache)))
    return lines


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
        page=PAGE,
    )
    if snapshot.has_value and ctx.state.get(READER_SEARCH_LOADED) != query:
        screen.force_full = True
        ctx.state[READER_SEARCH_LOADED] = query
    return screen


def _article(ctx, service, token):
    snapshot = service.document(token)
    document = snapshot.value if snapshot.has_value else None
    if document is None:
        if snapshot.error is not None:
            return _message(ctx, "DATA UNAVAILABLE. RETRYING...")
        if not snapshot.has_value:
            return _message(ctx, "LOADING ARTICLE...")
        return _message(ctx, "ARTICLE NOT FOUND. USE GUIDE FOR SEARCH.")

    lines = _lines(ctx, document)
    buffer = ctx.input_value
    prefix, matches = match_prefix(document, buffer)
    if prefix != buffer:
        ctx.values[LINE_FIELD] = prefix
        buffer = prefix
    view = ctx.set_viewport(len(lines), 24, step=8, follow=False)
    window = view.window(lines)
    visible = visible_matches(matches, window)
    stops = build_stops(matches, lines, view.offset, view.height)
    start_next, start_prev = starts_for(
        stops, visible, offset=view.offset, height=view.height
    )
    find_state = ctx.state.get(READER_FIND)
    reset = find_state != (token, buffer)
    current = ctx.set_stops(
        stops, start_next=start_next, start_prev=start_prev, reset=reset
    )
    ctx.state[READER_FIND] = (token, buffer)
    ctx.state[READER_VISIBLE] = (token, visible)

    selected = current.selected_stop
    selected_link = (
        selected.link if selected is not None
        else visible[0] if len(visible) == 1 else None
    )
    if selected is not None:
        status_text = f"{current.selected + 1}/{len(stops)}"
    elif not matches:
        status_text = "GUIDE=INDEX"
    elif len(visible) == 1:
        status_text = "1 ON SCREEN"
    elif len(visible) > 1:
        status_text = f"{len(visible)} ON SCREEN"
    else:
        status_text = f"{len(matches)} OFF SCREEN"

    screen = article_screen(
        ctx, lines, view,
        buffer=buffer,
        status_text=status_text,
        matches=matches,
        selected_link=selected_link,
    )
    loaded = f"{token}:{document.revision}"
    if ctx.state.get(READER_LOADED) != loaded:
        screen.force_full = True
        ctx.state[READER_LOADED] = loaded
    return screen


def _render(ctx):
    service = ctx.service("wikipedia")
    if service is None:
        return _message(ctx, "READER NOT CONFIGURED")
    if ctx.extension:
        return _article(ctx, service, ctx.extension)
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
    return f"{PAGE}#{results[index].token}"


def _submit_index(ctx, line):
    value = line.strip()
    query = str(ctx.state.get(READER_QUERY, ""))
    if not value:
        route = _selected_result(ctx)
        if route is not None:
            return route
        ctx.state[READER_QUERY] = ""
        ctx.state[READER_RESET] = True
        return PAGE
    if value != query:
        ctx.state[READER_QUERY] = value
        ctx.state[READER_RESET] = True
        return PAGE
    return _selected_result(ctx) or PAGE


def _submit_article(ctx, line):
    current = _current(ctx)
    value = line.strip()
    if not value:
        return current
    service = ctx.service("wikipedia")
    snapshot = service.document(ctx.extension)
    document = snapshot.value if snapshot.has_value else None
    if document is None:
        return current
    prefix, matches = match_prefix(document, value)
    if prefix != value:
        ctx.values[LINE_FIELD] = prefix
        return current
    selected = ctx.stops.selected_stop if ctx.stops else None
    if selected is not None:
        return f"{PAGE}#{document.links[selected.link].token}"
    visible_state = ctx.state.get(READER_VISIBLE)
    visible = (
        visible_state[1]
        if visible_state and visible_state[0] == ctx.extension
        else ()
    )
    if len(visible) == 1:
        return f"{PAGE}#{document.links[visible[0]].token}"
    return current


def _submit(ctx, line):
    if ctx.extension:
        return _submit_article(ctx, line)
    return _submit_index(ctx, line)


def _on_key(ctx, key):
    if key == "GUIDE" and ctx.extension:
        ctx.state[READER_RETURN] = True
        return PAGE
    return None


def _tick(ctx):
    return _render(ctx)


@page(
    PAGE,
    title="WIKIPEDIA",
    requires=("wikipedia",),
    extensions=True,
    scroll=True,
    tick_interval=1.0,
    on_submit=_submit,
    on_key=_on_key,
    on_tick=_tick,
)
def wikipedia(ctx):
    return _render(ctx)
