"""Page 161: linked Wikipedia article reader."""

from minitel import LINE_FIELD, page

from services.common.reader import match_prefix

from ..common.header import AnnouncementHeader
from ..common.reader import (
    Line,
    LineSpan,
    article_screen,
    build_stops,
    render_lines,
    starts_for,
    visible_matches,
)
from ._support.state import (
    ARTICLE_PAGE,
    INDEX_PAGE,
    READER_FIND,
    READER_LINES,
    READER_LOADED,
    READER_RETURN,
    READER_VISIBLE,
)


def _current(ctx):
    return f"{ARTICLE_PAGE}#{ctx.extension}" if ctx.extension else ARTICLE_PAGE


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
    if not ctx.extension:
        return _message(ctx, "USE 160 TO SEARCH.")
    return _article(ctx, service, ctx.extension)


def _submit(ctx, line):
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
        return f"{ARTICLE_PAGE}#{document.links[selected.link].token}"
    visible_state = ctx.state.get(READER_VISIBLE)
    visible = (
        visible_state[1]
        if visible_state and visible_state[0] == ctx.extension
        else ()
    )
    if len(visible) == 1:
        return f"{ARTICLE_PAGE}#{document.links[visible[0]].token}"
    return current


def _on_key(ctx, key):
    if key == "GUIDE":
        ctx.state[READER_RETURN] = True
        return INDEX_PAGE
    return None


@page(
    ARTICLE_PAGE,
    title="WIKIPEDIA",
    requires=("wikipedia",),
    extensions=True,
    scroll=True,
    tick_interval=30.0,
    header=AnnouncementHeader(),
    back_page=INDEX_PAGE,
    extension_back_page=INDEX_PAGE,
    on_submit=_submit,
    on_key=_on_key,
    on_tick=_render,
)
def wikipedia_article(ctx):
    return _render(ctx)
