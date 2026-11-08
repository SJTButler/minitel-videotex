"""Structured reader documents, sources, and the cached reader service."""

import time
from dataclasses import dataclass
from typing import Protocol

from minitel.data.cache import ResourceCache, Snapshot


@dataclass(frozen=True)
class Span:
    text: str
    link: int | None = None


@dataclass(frozen=True)
class Block:
    kind: str
    spans: tuple[Span, ...] = ()
    level: int = 0


@dataclass(frozen=True)
class Link:
    token: str
    title: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class Document:
    token: str
    title: str
    blocks: tuple[Block, ...]
    links: tuple[Link, ...] = ()
    credit: str = ""
    revision: str = ""


@dataclass(frozen=True)
class SearchResult:
    token: str
    title: str
    snippet: str = ""
    tag: str = ""


class ReaderSource(Protocol):
    label: str

    def search(self, query, limit=20): ...
    def document(self, token): ...


def find_links(document, buffer):
    """Return unique matching link indices for a substring buffer."""
    text = "" if buffer is None else str(buffer)
    if not text:
        return ()
    folded = text.casefold()
    matches = []
    for index, link in enumerate(document.links):
        labels = link.labels or (link.title,)
        if any(folded in label.casefold() for label in labels):
            matches.append(index)
            continue
        if folded in link.title.casefold():
            matches.append(index)
    return tuple(matches)


def match_prefix(document, buffer):
    """Return the longest matching prefix of ``buffer`` and its link indices."""
    text = "" if buffer is None else str(buffer)
    while text:
        matches = find_links(document, text)
        if matches:
            return text, matches
        text = text[:-1]
    return "", ()


class ReaderService:
    """Cache a ReaderSource with one loader per document or search query."""

    def __init__(self, source, *, ttl=3600.0, retry_delay=300.0,
                 max_entries=64, clock=time.monotonic, thread_factory=None):
        self.source = source
        self.cache = ResourceCache(
            ttl, retry_delay, max_entries=max_entries,
            clock=clock, thread_factory=thread_factory,
        )

    def document(self, token):
        token = str(token).strip().upper()
        if not token:
            return Snapshot()
        return self.cache.get(
            ("document", token), lambda: self.source.document(token)
        )

    def search(self, query="", limit=20):
        query = " ".join(str(query or "").split())
        limit = max(1, int(limit))
        if not query:
            return Snapshot(value=(), loaded_at=time.monotonic())
        return self.cache.get(
            ("search", query.casefold(), limit),
            lambda: tuple(self.source.search(query, limit)),
        )


class StaticReaderService:
    """A synchronous reader service for fixtures and local sources."""

    def __init__(self, documents, results=()):
        self._documents = {
            str(token).upper(): document
            for token, document in documents.items()
        }
        self._results = tuple(results)

    @staticmethod
    def _snapshot(value):
        return Snapshot(value=value, loaded_at=time.monotonic())

    def document(self, token):
        return self._snapshot(
            self._documents.get(str(token).strip().upper())
        )

    def search(self, query="", limit=20):
        folded = " ".join(str(query or "").split()).casefold()
        results = tuple(
            result for result in self._results
            if not folded
            or folded in result.title.casefold()
            or folded in result.snippet.casefold()
            or folded in result.tag.casefold()
        )
        return self._snapshot(results[:max(1, int(limit))])
