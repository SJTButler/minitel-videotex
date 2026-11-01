"""Hacker News data source and the cached news service."""

import time
from dataclasses import dataclass

from minitel.cache import ResourceCache
from minitel.http import get_json
from minitel.text import domain

FRONT_PAGE_URL = (
    "https://hn.algolia.com/api/v1/search"
    "?tags=front_page&hitsPerPage=30"
)
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


@dataclass(frozen=True)
class Story:
    id: int
    title: str
    url: str = ""
    points: int = 0
    comments: int = 0
    author: str = ""
    created_at: int = 0

    @property
    def domain(self):
        return domain(self.url) or "HACKER NEWS"


@dataclass(frozen=True)
class Comment:
    author: str
    text: str
    created_at: int = 0


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def parse_front_page(payload, limit=30):
    if not isinstance(payload, dict):
        return []
    hits = payload.get("hits") or []
    if not isinstance(hits, (list, tuple)):
        return []
    if limit is not None and limit <= 0:
        return []

    stories = []
    for hit in (hits[:limit] if limit is not None else hits):
        if not isinstance(hit, dict):
            continue
        raw_id = hit.get("objectID") or hit.get("story_id") or hit.get("id")
        story_id = _as_int(raw_id, 0)
        if story_id <= 0:
            continue
        stories.append(
            Story(
                id=story_id,
                title=hit.get("title") or "(NO TITLE)",
                url=hit.get("url") or "",
                points=_as_int(hit.get("points"), 0),
                comments=_as_int(hit.get("num_comments"), 0),
                author=hit.get("author") or "",
                created_at=_as_int(hit.get("created_at_i"), 0),
            )
        )
    return stories


def parse_comment(payload):
    if not isinstance(payload, dict):
        return None
    if payload.get("deleted") or payload.get("dead"):
        return None
    text = payload.get("text") or ""
    if not str(text).strip():
        return None
    return Comment(
        author=payload.get("by") or "",
        text=text,
        created_at=_as_int(payload.get("time"), 0),
    )


class HackerNewsSource:
    def __init__(self, get_json=get_json, timeout=8.0):
        self._get_json = get_json
        self.timeout = timeout

    def front_page(self, limit=30):
        payload = self._get_json(FRONT_PAGE_URL, timeout=self.timeout)
        return parse_front_page(payload, limit)

    def top_comment(self, story_id):
        item = self._get_json(
            ITEM_URL.format(id=int(story_id)), timeout=self.timeout
        )
        if not isinstance(item, dict):
            return None
        kids = item.get("kids") or []
        if not isinstance(kids, (list, tuple)):
            return None
        for kid in list(kids)[:3]:
            try:
                kid_id = int(kid)
            except (TypeError, ValueError, OverflowError):
                continue
            child = self._get_json(
                ITEM_URL.format(id=kid_id), timeout=self.timeout
            )
            comment = parse_comment(child)
            if comment is not None:
                return comment
        return None


class HackerNewsService:
    def __init__(self, source=None, front_ttl=300, comment_ttl=1800,
                 retry_delay=60, max_comments=64, clock=time.monotonic,
                 thread_factory=None):
        self.source = source or HackerNewsSource()
        self.front_cache = ResourceCache(
            front_ttl, retry_delay, max_entries=1,
            clock=clock, thread_factory=thread_factory,
        )
        self.comment_cache = ResourceCache(
            comment_ttl, retry_delay, max_entries=max_comments,
            clock=clock, thread_factory=thread_factory,
        )

    async def start(self):
        self.front_page()

    async def stop(self):
        return None

    def front_page(self):
        return self.front_cache.get("front", self.source.front_page)

    def comment(self, story_id):
        story_id = int(story_id)
        return self.comment_cache.get(
            story_id, lambda: self.source.top_comment(story_id)
        )
