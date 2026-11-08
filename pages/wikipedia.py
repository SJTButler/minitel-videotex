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
    find_results,
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
    buffer = ctx.input_value
    filtered = find_results(results, buffer)
    reset = ctx.state.pop(READER_RESET, False)
    pager = ctx.set_pager(
        len(filtered), PAGE_SIZE, offset=0 if reset else None
    )
    if snapshot.error is not None and not snapshot.has_value:
        status_text = "SEARCH UNAVAILABLE"
    elif not snapshot.has_value:
        status_text = "SEARCHING..."
    elif not filtered:
        status_text = "NO RESULTS"
    else:
        word = "RESULT" if len(filtered) == 1 else "RESULTS"
        status_text = f"{len(filtered)} {word}"
    screen = index_screen(
        ctx, filtered, pager,
        title="WIKIPEDIA",
        query=query,
        status_text=status_text,
        hint="TYPE WORDS. ENVOI SEARCHES OR OPENS A UNIQUE RESULT.",
        source="FIXTURE PAGES. REAL WIKIPEDIA NEXT.",
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


def _submit_index(ctx, line):
    value = line.strip()
    if not value:
        ctx.state[READER_QUERY] = ""
        ctx.state[READER_RESET] = True
        return PAGE
    results = ctx.state.get(READER_RESULTS, ())
    filtered = find_results(results, value)
    if len(filtered) == 1:
        return f"{PAGE}#{filtered[0].token}"
    ctx.state[READER_QUERY] = value
    ctx.state[READER_RESET] = True
    return PAGE


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
