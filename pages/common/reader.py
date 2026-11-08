"""Shared reader presentation: document lines, matches, stops, and screens."""

from dataclasses import dataclass

from minitel.design.stops import Stop
from minitel.protocol import codec
from minitel.render import Screen
from minitel.text import fit, sanitize

from .layout import SECONDARY, WARNING, key_footer, status

WIDTH = 39
HEIGHT = 24
MAX_LINES = 5000
FIELD_ROW = 0
FIELD_WIDTH = 32


@dataclass(frozen=True)
class LineSpan:
    text: str
    link: int | None = None


@dataclass(frozen=True)
class Line:
    kind: str
    spans: tuple[LineSpan, ...] = ()

    @property
    def text(self):
        return "".join(span.text for span in self.spans)


def _tokens(spans):
    tokens = []
    space_before = False
    for span in spans:
        text = span.text
        index = 0
        while index < len(text):
            if text[index].isspace():
                space_before = True
                index += 1
                continue
            end = index
            while end < len(text) and not text[end].isspace():
                end += 1
            tokens.append((text[index:end], span.link, space_before))
            space_before = False
            index = end
    return tokens


def _wrap_tokens(tokens, width, *, first_prefix="", next_prefix=""):
    if not tokens:
        return []
    lines = []
    prefix = first_prefix
    spans = []
    length = 0
    has_content = False

    def start_line():
        nonlocal spans, length, has_content
        spans = []
        length = 0
        has_content = False
        if prefix:
            spans.append(LineSpan(prefix))
            length = len(prefix)

    def flush():
        nonlocal spans, length, has_content, prefix
        if has_content:
            lines.append(tuple(spans))
        prefix = next_prefix
        start_line()

    start_line()
    for text, link, space_before in tokens:
        while True:
            remaining = width - length
            separator = 1 if has_content and space_before else 0
            if len(text) + separator <= remaining:
                if separator:
                    spans.append(LineSpan(" "))
                    length += 1
                spans.append(LineSpan(text, link))
                length += len(text)
                has_content = True
                break
            if has_content:
                flush()
                continue
            chunk = text[:max(1, remaining)]
            spans.append(LineSpan(chunk, link))
            length += len(chunk)
            has_content = True
            text = text[len(chunk):]
            if not text:
                break
            flush()
    if has_content:
        lines.append(tuple(spans))
    return lines


def _append(lines, kind, spans, width, **prefixes):
    for spans_line in _wrap_tokens(
        _tokens(spans), width, **prefixes
    ):
        lines.append(Line(kind, spans_line))


def _blank(lines):
    if not lines or lines[-1].kind != "blank":
        lines.append(Line("blank"))


def render_lines(document, *, width=WIDTH, max_lines=MAX_LINES):
    """Render a reader document into styled lines for the viewport."""
    lines = []
    title = sanitize(document.title)
    if title:
        _append(lines, "title", (LineSpan(title),), width)
        _blank(lines)

    for block in document.blocks:
        kind = block.kind
        if kind == "heading":
            _blank(lines)
            _append(lines, "heading", block.spans, width)
            _blank(lines)
        elif kind == "bullet":
            _append(
                lines, "bullet", block.spans, width,
                first_prefix="- ", next_prefix="  ",
            )
            _blank(lines)
        elif kind == "quote":
            _append(
                lines, "quote", block.spans, width,
                first_prefix="> ", next_prefix="> ",
            )
            _blank(lines)
        elif kind == "code":
            text = "".join(span.text for span in block.spans)
            for part in text.splitlines() or [""]:
                for spans_line in _wrap_tokens(
                    [(part, None, False)], width
                ) if part else []:
                    lines.append(Line("code", spans_line))
            _blank(lines)
        elif kind == "rule":
            lines.append(Line("rule", (LineSpan("=" * width),)))
            _blank(lines)
        else:
            _append(lines, "body", block.spans, width)
            _blank(lines)

    if document.links:
        _blank(lines)
        lines.append(Line("heading", (LineSpan("LINKS"),)))
        for index, link in enumerate(document.links):
            title = sanitize(link.title)
            _append(
                lines, "links", (LineSpan(f"- {title}", index),), width,
            )
        _blank(lines)

    if document.credit:
        _append(
            lines, "credit",
            (LineSpan(sanitize(document.credit)),), width,
        )

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = Line(
            "warning", (LineSpan("ARTICLE TRUNCATED."),)
        )
    return tuple(lines)


def visible_matches(matches, window_lines):
    wanted = set(matches)
    seen = set()
    found = []
    for line in window_lines:
        for span in line.spans:
            if span.link in wanted and span.link not in seen:
                seen.add(span.link)
                found.append(span.link)
    return tuple(found)


def build_stops(matches, lines, offset, height):
    """Build one stop per matching target, ordered by first occurrence."""
    stops = []
    for link in dict.fromkeys(matches):
        first = None
        visible = None
        for index, line in enumerate(lines):
            if not any(span.link == link for span in line.spans):
                continue
            if first is None:
                first = index
            if (
                visible is None
                and offset <= index < offset + height
            ):
                visible = index
        if first is not None:
            stops.append(
                Stop(first, visible if visible is not None else first, link)
            )
    stops.sort(key=lambda stop: (stop.first_line, stop.link))
    return tuple(stops)


def starts_for(stops, visible, *, offset=0, height=HEIGHT):
    """Return ``(start_next, start_prev)`` for the visible set."""
    if not stops:
        return 0, 0
    if visible:
        top = visible[0]
        for index, stop in enumerate(stops):
            if stop.link == top:
                return index, index
    next_index = 0
    for index, stop in enumerate(stops):
        if stop.first_line >= offset + height:
            next_index = index
            break
    prev_index = len(stops) - 1
    for index in range(len(stops) - 1, -1, -1):
        if stops[index].first_line < offset:
            prev_index = index
            break
    return next_index, prev_index


def find_results(results, buffer):
    text = "" if buffer is None else str(buffer).casefold()
    if not text:
        return tuple(results)
    return tuple(
        result for result in results
        if text in result.title.casefold()
        or text in result.snippet.casefold()
        or text in result.tag.casefold()
    )


def _line_attrs(kind):
    if kind == "title":
        return {"inverse": True}
    if kind == "heading":
        return {"inverse": True}
    if kind == "warning":
        return {"inverse": True}
    return {}


def _draw_line(screen, row, line, matches, selected_link):
    if line.kind == "blank":
        return
    attrs = _line_attrs(line.kind)
    col = 0
    for span in line.spans:
        text = span.text
        if not text or col >= codec.COLS:
            continue
        text = text[:codec.COLS - col]
        cell = dict(attrs)
        if span.link is not None:
            cell["fg"] = SECONDARY
            if span.link in matches:
                if span.link == selected_link:
                    cell["inverse"] = True
                else:
                    cell["fg"] = WARNING
        screen.text(row, col, text, **cell)
        col += len(text)


def _status_row(screen, buffer, view, status_text):
    screen.fill(0, 0, codec.COLS, " ", inverse=True)
    screen.text(0, 0, "FIND:", inverse=True)
    screen.text(0, 5, fit(buffer, 12), inverse=True)
    screen.text(0, 18, fit(f"{view.line_number}/{view.total}", 6),
                inverse=True)
    screen.text(0, 25, fit(status_text, 12), inverse=True)


def article_screen(ctx, lines, view, *, buffer, status_text,
                   matches=(), selected_link=None):
    screen = Screen()
    _status_row(screen, buffer, view, status_text)
    ctx.set_input(
        FIELD_ROW, 0, FIELD_WIDTH, live=True, visible=False
    )
    for row, line in enumerate(view.window(lines), start=1):
        _draw_line(screen, row, line, matches, selected_link)
    return screen


def index_screen(ctx, results, choice, *, title, query, status_text,
                 hint="", source="", page="160"):
    screen = Screen()
    status(screen, page)
    screen.text(1, 0, title, inverse=True, size=codec.DOUBLE_WIDTH)
    line = f"QUERY: {query}" if query else "ALL PAGES"
    screen.text(2, 0, fit(line, codec.COLS))
    screen.text(3, 0, "SEARCH:")
    screen.field(3, 8, 28)
    screen.text(3, 8, ctx.input_value[:28], inverse=True)
    ctx.set_input(3, 8, 28, live=True)
    screen.text(4, 0, fit(status_text, codec.COLS))

    window = choice.window(results)
    offset = choice.offset
    for index, result in enumerate(window):
        row = 6 + index * 2
        tag_text = result.tag[:8]
        title_width = codec.COLS - (
            len(tag_text) + 1 if tag_text else 0
        )
        selected = choice.selected == offset + index
        screen.text(
            row, 0, fit(result.title, max(1, title_width)),
            fg=SECONDARY, inverse=selected,
        )
        if tag_text:
            screen.text(
                row, codec.COLS - len(tag_text), tag_text
            )
        if result.snippet:
            screen.text(
                row + 1, 2, fit(result.snippet, codec.COLS - 2)
            )
    if not window:
        screen.text(6, 0, "NO RESULTS", inverse=True)
    pager_text = f"PAGE {choice.label}" if choice.page_count else ""
    screen.text(20, 0, pager_text)
    screen.text(21, 0, fit(hint, codec.COLS))
    key_footer(screen, ("ENVOI=OPEN", "SOMMAIRE=HOME"))
    screen.text(23, 0, fit(source, codec.COLS))
    return screen
