"""Streaming HTML to reader blocks for the Wikipedia action API output."""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import unquote


@dataclass(frozen=True)
class RawSpan:
    text: str
    target: str | None = None


@dataclass(frozen=True)
class RawBlock:
    kind: str
    spans: tuple[RawSpan, ...]
    level: int = 0


SKIP_TAGS = {"style", "script", "noscript", "table", "figure", "math"}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
SKIP_CLASSES = {
    "reference", "mw-editsection", "navbox", "navbox-styles", "infobox",
    "metadata", "hatnote", "rellink", "dablink", "thumb", "gallery",
    "reflist", "references", "refbegin", "mw-references-wrap",
    "mw-cite-backlink", "mw-file-description", "mwe-math-element",
    "printfooter", "catlinks", "mw-authority-control", "mw-jump-link",
    "vector-toc", "toc", "shortdescription", "ambox", "mbox", "sidebar",
    "vertical-navbox", "succession-box", "sistersitebox", "side-box",
    "mw-empty-elt", "noprint",
}
NAMESPACES = {
    "file", "image", "category", "help", "special", "talk", "user",
    "wikipedia", "template", "portal", "draft", "module", "mediawiki",
    "book", "timedtext", "gadget", "gadget definition", "education program",
    "mos", "w",
}
HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
BLOCK_START = {
    "p", "div", "section", "article", "main", "header", "footer",
    "ul", "ol", "blockquote", "pre", "li", "dd", "hr",
}
BLOCK_END = BLOCK_START - {"hr"}


def _classes(attrs):
    value = attrs.get("class") or ""
    return set(value.split())


def _skip(tag, attrs):
    if tag in SKIP_TAGS:
        return True
    if tag == "sup" and "reference" in _classes(attrs):
        return True
    return bool(_classes(attrs) & SKIP_CLASSES)


class _ReaderHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.spans = []
        self.kind = "body"
        self.level = 0
        self.skip = 0
        self.containers = []
        self.link_stack = []

    @property
    def current_target(self):
        return self.link_stack[-1] if self.link_stack else None

    def _container_kind(self):
        return self.containers[-1] if self.containers else "body"

    def _flush(self):
        if self.spans:
            spans = []
            for span in self.spans:
                text = span.text
                if text:
                    spans.append(span)
            if spans and any(span.text.strip() for span in spans):
                self.blocks.append(
                    RawBlock(self.kind, tuple(spans), self.level)
                )
        self.spans = []
        self.level = 0
        self.kind = self._container_kind()

    def _append(self, text):
        if not text:
            return
        if "code" in self.containers:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        else:
            text = re.sub(r"\s+", " ", text)
            if not text:
                return
        if (
            self.spans
            and self.spans[-1].target == self.current_target
        ):
            last = self.spans[-1]
            self.spans[-1] = RawSpan(last.text + text, last.target)
        else:
            self.spans.append(RawSpan(text, self.current_target))

    def _target(self, attrs):
        href = (attrs.get("href") or "").strip()
        if not href or href.startswith("#"):
            return None
        if (
            href.startswith("http:")
            or href.startswith("https:")
            or href.startswith("//")
        ):
            return None
        if href.startswith("/wiki/"):
            path = href[6:]
        elif href.startswith("./"):
            path = href[2:]
        else:
            return None
        path = path.split("#", 1)[0]
        title = unquote(path).replace("_", " ").strip()
        if not title:
            return None
        prefix = title.split(":", 1)[0].strip().casefold()
        if prefix in NAMESPACES:
            return None
        return title

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        attrs = dict(attrs)
        if self.skip:
            if tag not in VOID_TAGS:
                self.skip += 1
            return
        if _skip(tag, attrs):
            if tag not in VOID_TAGS:
                self.skip = 1
            return
        if tag == "a":
            self.link_stack.append(self._target(attrs))
            return
        if tag == "br":
            self._append("\n" if "code" in self.containers else " ")
            return
        if tag in HEADING_TAGS:
            self._flush()
            self.kind = "heading"
            self.level = HEADING_TAGS[tag]
            return
        if tag in ("li", "dd"):
            self._flush()
            self.containers.append("bullet")
            self.kind = "bullet"
            return
        if tag == "blockquote":
            self._flush()
            self.containers.append("quote")
            self.kind = "quote"
            return
        if tag == "pre":
            self._flush()
            self.containers.append("code")
            self.kind = "code"
            return
        if tag == "hr":
            self._flush()
            self.blocks.append(RawBlock("rule", ()))
            return
        if tag in BLOCK_START:
            self._flush()
            self.kind = self._container_kind()

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if self.skip:
            if tag not in VOID_TAGS:
                self.skip -= 1
            return
        if tag == "a":
            if self.link_stack:
                self.link_stack.pop()
            return
        if tag in HEADING_TAGS or tag == "p":
            self._flush()
            return
        if tag in ("li", "dd"):
            self._flush()
            if self.containers and self.containers[-1] == "bullet":
                self.containers.pop()
            self.kind = self._container_kind()
            return
        if tag in ("blockquote", "pre"):
            self._flush()
            if self.containers:
                self.containers.pop()
            self.kind = self._container_kind()
            return
        if tag in BLOCK_END:
            self._flush()

    def handle_data(self, data):
        if self.skip or not data:
            return
        if data.strip():
            self._append(data)
        elif self.spans:
            self._append(" ")

    def close(self):
        super().close()
        self._flush()


def parse_html(html):
    """Return reader RawBlocks from a page's action=parse HTML."""
    parser = _ReaderHTMLParser()
    parser.feed(html or "")
    parser.close()
    return tuple(parser.blocks)
