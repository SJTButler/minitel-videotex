"""Pages 111 and 112: the Hacker News headline list and story detail."""

import time

from minitel import codec, Carousel
from minitel.pages import page
from minitel.screen import Screen
from minitel.text import age, fit, sanitize, wrap

from ..common.layout import (
    ACCENT,
    SECONDARY,
    WARNING,
    key_footer,
    status,
)
from ..common.messages import MessageLatch
from ..common.service_status import ServiceState, classify, describe
from ..common.widgets import page_input

NEWS_PAGE = "111"
STORY_PAGE = "112"
PAGE_SIZE = 4


def _service(ctx):
    return ctx.service("hackernews")


def _snapshot(ctx):
    service = _service(ctx)
    if service is None:
        return None
    return service.front_page()


def _stories(snapshot):
    if snapshot is None or not snapshot.has_value or not snapshot.value:
        return []
    return list(snapshot.value)


def _status(snapshot):
    return describe(
        snapshot,
        missing_text="NEWS UNAVAILABLE.",
        loading_text="FETCHING HACKER NEWS",
        unavailable_text="NEWS UNAVAILABLE.",
        stale_prefix="FRONT PAGE  OFFLINE",
        updated_prefix="FRONT PAGE  UPDATED",
    )


def _stats(story):
    points = story.points or 0
    comments = story.comments or 0
    stats = f"{points}P  {comments}C"
    if story.created_at:
        stats += "  " + age(max(0, int(time.time()) - story.created_at))
    return stats


def _draw_metadata(s, row, story):
    width = codec.COLS - 2
    stats = fit(_stats(story), width)
    host = sanitize(story.domain) or "HACKER NEWS"
    host = fit(host, max(0, width - len(stats) - 2))
    if host:
        s.text(row, 2, host, fg=SECONDARY, underline=True)
        s.text(row, 2 + len(host) + 2, stats, fg=ACCENT, underline=True)
    else:
        s.text(row, 2, stats, fg=ACCENT, underline=True)


def _state(snapshot):
    empty = bool(snapshot and snapshot.has_value and not snapshot.value)
    return classify(snapshot, empty=empty)


def _hint_colour(ctx, snapshot):
    if MessageLatch(ctx).get():
        return WARNING
    return _status(snapshot).colour


def _empty_lines(snapshot):
    state = _state(snapshot)
    if state in (
        ServiceState.MISSING,
        ServiceState.UNAVAILABLE,
        ServiceState.STALE,
    ):
        return ["CHECK CONNECTION, THEN", "RETRYING AUTOMATICALLY."]
    if state is ServiceState.LOADING:
        return ["LOADING NEWS..."]
    return ["NO HEADLINES RIGHT NOW."]


def _hint(ctx, snapshot, stories):
    error = MessageLatch(ctx).text()
    if error:
        return error
    state = _state(snapshot)
    if state is ServiceState.MISSING:
        return "NEWS UNAVAILABLE."
    if state is ServiceState.STALE and stories:
        return "OFFLINE. 1-4 + ENVOI"
    if not stories:
        if state in (ServiceState.UNAVAILABLE, ServiceState.STALE):
            return "CHECK CONNECTION, THEN"
        if state in (ServiceState.READY, ServiceState.EMPTY) and not snapshot.loading:
            return "NO HEADLINES RIGHT NOW."
        return "LOADING NEWS..."
    return "TYPE 1-4, THEN ENVOI"

def _list_pager(ctx, stories):
    return ctx.set_pager(
        len(stories),
        PAGE_SIZE,
        carousel=Carousel(hold=30.0, wrap=True)
    )

def list_screen(ctx):
    snapshot = _snapshot(ctx)
    stories = _stories(snapshot)
    pager = _list_pager(ctx, stories)
    MessageLatch(ctx).clear_if_moved(pager.offset)

    s = Screen()
    page_status = _status(snapshot)
    status(s, f"111 {pager.label}" if pager.total else "111")
    s.text(1, 0, "HACKER NEWS", inverse=True, size=codec.DOUBLE_WIDTH)
    s.text(
        2, 0, fit(page_status.text, codec.COLS),
        fg=page_status.colour,
    )

    window = pager.window(stories)
    for index, story in enumerate(window):
        row = 3 + index * 4
        title = wrap(
            sanitize(story.title) or "(NO TITLE)",
            codec.COLS - 2,
            max_lines=2,
        )
        if title:
            s.text(row, 0, f"{index + 1}", fg=ACCENT, inverse=True)
            s.text(row, 2, title[0])
        if len(title) > 1:
            s.text(row + 1, 2, title[1])
        _draw_metadata(s, row + 2, story)

    if not window:
        for index, line in enumerate(_empty_lines(snapshot)):
            s.text(3 + index, 0, fit(line, codec.COLS), fg=page_status.colour)

    s.text(
        18, 0, fit(_hint(ctx, snapshot, stories), codec.COLS),
        fg=_hint_colour(ctx, snapshot),
    )
    page_input(s, ctx, cursor="auto")
    key_footer(s, ("SUITE=NEXT", "RETOUR=BACK", "SOMMAIRE=HOME"))
    s.text(23, 0, "1-4 + ENVOI = STORY", fg=SECONDARY)
    return s


def submit_list(ctx, line):
    value = line.strip()
    snapshot = _snapshot(ctx)
    stories = _stories(snapshot)
    pager = _list_pager(ctx, stories)
    window = pager.window(stories)
    latch = MessageLatch(ctx)

    if value.isdigit() and len(value) == 1 and int(value) != 0:
        number = int(value)
        if number <= PAGE_SIZE and number <= len(window):
            ctx.state["news_story"] = window[number - 1]
            latch.clear()
            return STORY_PAGE
        latch.set(f"NO STORY {number}.", pager.offset)
        ctx.clear_input()
        return NEWS_PAGE

    if ctx.page_for(value) is not None:
        latch.clear()
        return None

    latch.set(
        fit(f"NO STORY {sanitize(value)}.", codec.COLS),
        pager.offset,
    )
    ctx.clear_input()
    return NEWS_PAGE


@page(
    NEWS_PAGE,
    title="HACKER NEWS",
    requires=("hackernews",),
    tick_interval=2.0,
    on_submit=submit_list,
    on_tick=list_screen,
    no_screensaver=True
)
def hacker_news(ctx):
    return list_screen(ctx)


def _comment_lines(ctx, story):
    if (story.comments or 0) <= 0:
        return ["NO COMMENTS YET."], ""
    service = _service(ctx)
    if service is None:
        return ["COMMENT UNAVAILABLE."], ""

    snapshot = service.comment(story.id)
    if snapshot.has_value:
        comment = snapshot.value
        if comment is None:
            return ["NO COMMENT AVAILABLE."], ""
        body = sanitize(comment.text)
        if not body:
            return ["NO COMMENT AVAILABLE."], ""
        return wrap(body, codec.COLS, max_lines=9), sanitize(comment.author)
    if snapshot.error:
        return ["COMMENT UNAVAILABLE."], ""
    return ["LOADING COMMENT..."], ""


def detail_screen(ctx):
    s = Screen()
    status(s, "PAGE 112")
    s.text(1, 0, "STORY", inverse=True, size=codec.DOUBLE_WIDTH)

    story = ctx.state.get("news_story")
    if story is None:
        s.text(3, 0, "NO STORY SELECTED.", fg=WARNING)
        s.text(4, 0, "OPEN NEWS, PICK 1-4.", fg=SECONDARY)
        page_input(s, ctx, cursor="auto")
        key_footer(s, ("RETOUR=BACK", "SOMMAIRE=HOME"))
        return s

    for index, line in enumerate(
        wrap(sanitize(story.title) or "(NO TITLE)", codec.COLS, max_lines=3)
    ):
        s.text(3 + index, 0, line)

    host = sanitize(story.domain) or "HACKER NEWS"
    points = fit(f"{story.points or 0} POINTS", codec.COLS)
    host = fit(host, max(0, codec.COLS - len(points) - 2))
    if host:
        s.text(6, 0, host, fg=SECONDARY, underline=True)
        s.text(6, len(host) + 2, points, fg=ACCENT, underline=True)
    else:
        s.text(6, 0, points, fg=ACCENT, underline=True)

    comments = fit(f"{story.comments or 0} COMMENTS", codec.COLS)
    rest = ""
    author = sanitize(story.author)
    if author:
        rest += f"  BY {author}"
    if story.created_at:
        rest += "  " + age(max(0, int(time.time()) - story.created_at))
    rest = fit(rest, max(0, codec.COLS - len(comments)))
    s.text(7, 0, comments, fg=ACCENT, underline=True)
    if rest:
        s.text(7, len(comments), rest, fg=SECONDARY, underline=True)

    s.fill(9, 0, codec.COLS, " ", inverse=True)
    s.text(9, 0, "TOP COMMENT", inverse=True)

    lines, comment_author = _comment_lines(ctx, story)
    for index, line in enumerate(lines[:9]):
        s.text(10 + index, 0, fit(line, codec.COLS))
    if comment_author:
        s.text(
            19, 0, fit(f"- {comment_author}", codec.COLS),
            fg=SECONDARY, underline=True,
        )

    page_input(s, ctx, cursor="auto")
    key_footer(s, ("RETOUR=BACK", "SOMMAIRE=HOME"))
    return s


@page(
    STORY_PAGE,
    title="STORY",
    requires=("hackernews",),
    back_page=NEWS_PAGE,
    tick_interval=1.0,
    on_tick=detail_screen,
)
def story(ctx):
    return detail_screen(ctx)
