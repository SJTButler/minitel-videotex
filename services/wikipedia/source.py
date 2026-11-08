"""Wikipedia action API source, link resolution, and reader documents."""

from dataclasses import dataclass
from urllib.parse import urlencode

from minitel.data.http import get_json
from minitel.text import sanitize

from services.common.reader import (
    Block,
    Document,
    Link,
    SearchResult,
    Span,
)

from .html import RawBlock, parse_html

CREDIT = "WIKIPEDIA. CC BY-SA."
LINK_BATCH = 50
LINK_LIMIT = 99
DEFAULT_USER_AGENT = "minitel-videotex/0.3 (linked reader)"


def to_base36(value):
    value = int(value)
    if value < 0:
        raise ValueError("base36 value must be non-negative")
    if value == 0:
        return "0"
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    while value:
        value, remainder = divmod(value, 36)
        out.append(digits[remainder])
    return "".join(reversed(out))


def from_base36(value):
    try:
        text = str(value).strip().upper()
        if not text:
            return None
        return int(text, 36)
    except (TypeError, ValueError):
        return None


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


@dataclass(frozen=True)
class ParsedArticle:
    title: str
    pageid: int
    revid: int | None
    blocks: tuple[RawBlock, ...]


def parse_search(payload, limit=20):
    if not isinstance(payload, dict):
        return ()
    query = payload.get("query")
    if not isinstance(query, dict):
        return ()
    hits = query.get("search")
    if not isinstance(hits, (list, tuple)):
        return ()
    limit = max(1, int(limit))
    results = []
    for hit in hits[:limit]:
        if not isinstance(hit, dict):
            continue
        pageid = _as_int(hit.get("pageid"), 0)
        title = sanitize(hit.get("title") or "")
        if pageid <= 0 or not title:
            continue
        results.append(
            SearchResult(
                token=to_base36(pageid),
                title=title,
                snippet=sanitize(hit.get("snippet") or ""),
            )
        )
    return tuple(results)


def parse_article(payload):
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    parse = payload.get("parse")
    if not isinstance(parse, dict):
        return None
    title = sanitize(parse.get("title") or "")
    pageid = _as_int(parse.get("pageid"), 0)
    text = parse.get("text")
    if not title or pageid <= 0 or not isinstance(text, str):
        return None
    revid = _as_int(parse.get("revid"), 0) or None
    return ParsedArticle(
        title=title,
        pageid=pageid,
        revid=revid,
        blocks=parse_html(text),
    )


def _chunks(values, size):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _case_map(entries, from_key="from", to_key="to"):
    result = {}
    if not isinstance(entries, (list, tuple)):
        return result
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get(from_key) or "").strip()
        target = str(entry.get(to_key) or "").strip()
        if source and target:
            result[source.casefold()] = target
    return result


def _resolve_titles(pages, normalized, redirects, targets):
    pages_by_title = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        title = str(page.get("title") or "").strip()
        if title:
            pages_by_title[title.casefold()] = page

    def final_title(title):
        current = normalized.get(title.casefold(), title)
        for _ in range(3):
            following = redirects.get(current.casefold())
            if not following or following == current:
                break
            current = following
        return current

    resolved = {}
    for target in targets:
        page = pages_by_title.get(final_title(target).casefold())
        if not isinstance(page, dict):
            continue
        if page.get("missing") or page.get("invalid"):
            continue
        if _as_int(page.get("ns"), -1) != 0:
            continue
        pageid = _as_int(page.get("pageid"), 0)
        if pageid <= 0:
            continue
        title = sanitize(page.get("title") or target)
        if not title:
            continue
        resolved[target] = (to_base36(pageid), title)
    return resolved


def _clean_span(text):
    """Sanitise a span without losing its boundary spaces."""
    raw = "" if text is None else str(text)
    if not raw:
        return ""
    leading = raw[0].isspace()
    trailing = raw[-1].isspace()
    clean = sanitize(raw)
    if not clean:
        return " " if not raw.strip() else ""
    if leading:
        clean = " " + clean
    if trailing:
        clean = clean + " "
    return clean


def _build_document(article, resolved):
    target_tokens = {
        target: token for target, (token, _title) in resolved.items()
    }
    token_titles = {}
    for token, title in resolved.values():
        token_titles.setdefault(token, title)

    link_order = []
    link_index = {}
    labels = {}

    for block in article.blocks:
        for span in block.spans:
            if span.target is None:
                continue
            token = target_tokens.get(span.target)
            if token is None:
                continue
            if token not in link_index:
                if len(link_order) >= LINK_LIMIT:
                    continue
                link_index[token] = len(link_order)
                link_order.append(token)
                labels[token] = []
            label = sanitize(span.text)
            if label and label.casefold() not in {
                existing.casefold() for existing in labels[token]
            }:
                labels[token].append(label)

    links = tuple(
        Link(
            token=token,
            title=token_titles.get(token, token),
            labels=tuple(labels[token]),
        )
        for token in link_order
    )

    blocks = []
    for raw in article.blocks:
        spans = []
        for span in raw.spans:
            text = _clean_span(span.text)
            if not text:
                continue
            token = (
                target_tokens.get(span.target)
                if span.target is not None else None
            )
            spans.append(
                Span(text, link_index.get(token) if token else None)
            )
        if spans:
            blocks.append(Block(raw.kind, tuple(spans), raw.level))

    if blocks:
        first = blocks[0]
        first_text = "".join(span.text for span in first.spans)
        if (
            first.kind == "heading"
            and first.level == 1
            and first_text.casefold() == article.title.casefold()
        ):
            blocks = blocks[1:]

    return Document(
        token=to_base36(article.pageid),
        title=article.title,
        blocks=tuple(blocks),
        links=links,
        credit=CREDIT,
        revision=str(article.revid or ""),
    )


class WikipediaSource:
    label = "wikipedia"

    def __init__(self, *, lang="en", user_agent=DEFAULT_USER_AGENT,
                 timeout=8.0, get_json=get_json):
        self.lang = lang
        self.user_agent = user_agent
        self.timeout = timeout
        self._get_json = get_json

    def _api(self, params):
        query = {"format": "json", "formatversion": "2"}
        query.update(params)
        url = (
            f"https://{self.lang}.wikipedia.org/w/api.php?"
            + urlencode(query)
        )
        return self._get_json(
            url,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )

    def search(self, query, limit=20):
        query = " ".join(str(query or "").split())
        if not query:
            return ()
        payload = self._api({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": min(max(1, int(limit)), 50),
            "srprop": "snippet",
        })
        return parse_search(payload, limit)

    def document(self, token):
        pageid = from_base36(token)
        if pageid is None or pageid <= 0:
            return None
        payload = self._api({
            "action": "parse",
            "pageid": str(pageid),
            "prop": "text|displaytitle|revid",
            "redirects": "1",
        })
        article = parse_article(payload)
        if article is None:
            return None
        resolved = self._resolve_links(article)
        return _build_document(article, resolved)

    def _resolve_links(self, article):
        targets = []
        seen = set()
        own = article.title.casefold()
        for block in article.blocks:
            for span in block.spans:
                target = span.target
                if not target:
                    continue
                folded = target.casefold()
                if folded == own or folded in seen:
                    continue
                seen.add(folded)
                targets.append(target)
        if not targets:
            return {}

        resolved = {}
        for chunk in _chunks(targets, LINK_BATCH):
            payload = self._api({
                "action": "query",
                "prop": "info",
                "titles": "|".join(chunk),
                "redirects": "1",
            })
            query = (
                payload.get("query")
                if isinstance(payload, dict) else None
            )
            if not isinstance(query, dict):
                continue
            pages = query.get("pages")
            if isinstance(pages, dict):
                pages = list(pages.values())
            if not isinstance(pages, (list, tuple)):
                pages = []
            resolved.update(
                _resolve_titles(
                    pages,
                    _case_map(query.get("normalized")),
                    _case_map(query.get("redirects")),
                    chunk,
                )
            )
        return resolved
