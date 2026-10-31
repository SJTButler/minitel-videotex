"""Content-free text helpers for remote data.

The Minitel codec can only encode ASCII, a small set of accented letters, and a
few special symbols. Fetched titles and comments go through these helpers so a
remote string can never crash the renderer.
"""

import html
import re
import unicodedata
from urllib.parse import urlsplit

_TAG = re.compile(r"<[^>]*>")

_PUNCTUATION = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u2032": "'", "\u2039": "'", "\u203a": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2033": '"', "\u00ab": '"', "\u00bb": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
    "\u2014": "-", "\u2015": "-", "\u2212": "-",
    "\u2026": "...",
    "\u2022": "*", "\u00b7": "*", "\u2023": "*", "\u2043": "*",
    "\u00a9": "(C)", "\u00ae": "(R)", "\u2122": "(TM)",
    "\u20ac": "EUR", "\u00a3": "GBP", "\u00a5": "JPY",
    "\u00a2": "c", "\u20bd": "RUB", "\u20b9": "INR",
    "\u00bc": "1/4", "\u00bd": "1/2", "\u00be": "3/4",
    "\u2153": "1/3", "\u2154": "2/3", "\u215b": "1/8",
    "\u215c": "3/8", "\u215d": "5/8", "\u215e": "7/8",
    "\u00d7": "x", "\u00f7": "/", "\u00b1": "+/-",
    "\u2248": "~", "\u2264": "<=", "\u2265": ">=", "\u2260": "!=",
    "\u00b0": " DEG",
    "\u2190": "<-", "\u2191": "^", "\u2192": "->", "\u2193": "v",
    "\u0153": "oe", "\u0152": "OE", "\u00e6": "ae", "\u00c6": "AE",
    "\u00df": "SS",
}


def plain(value):
    """Strip HTML tags, unescape entities, and collapse whitespace."""
    if value is None:
        return ""
    text = str(value)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def sanitize(value, uppercase=True):
    """Return a Minitel-safe ASCII rendering of remote text."""
    text = plain(value)
    text = "".join(_PUNCTUATION.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFKD", text)

    out = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        code = ord(ch)
        if ch.isspace() or code in (0x0A, 0x0D, 0x09):
            out.append(" ")
        elif 0x20 <= code <= 0x7E:
            out.append(ch)
        elif ch.isalpha() or ch.isdigit():
            out.append("?")
    result = " ".join("".join(out).split())
    return result.upper() if uppercase else result


def fit(value, width):
    """Truncate to width, using an ellipsis when there is room."""
    if width <= 0:
        return ""
    text = "" if value is None else str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def wrap(value, width, max_lines=None):
    """Word-wrap text, hard-splitting words longer than width."""
    if width <= 0 or (max_lines is not None and max_lines <= 0):
        return []
    words = ("" if value is None else str(value)).split()
    if not words:
        return []

    lines = []
    current = ""
    for word in words:
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        if not word:
            continue
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = current + " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        if width > 3:
            last = last[: width - 3].rstrip() + "..."
        else:
            last = last[:width]
        lines[-1] = last
    return lines


def domain(url):
    """Return a hostname without a leading www., or an empty string."""
    if not url:
        return ""
    value = str(url).strip()
    if not value:
        return ""
    if "://" not in value:
        value = "//" + value
    try:
        host = urlsplit(value).hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def age(seconds):
    """Compact age label: NOW, 5M, 2H, 3D, 2W, 1Y."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError, OverflowError):
        return ""
    if seconds < 60:
        return "NOW"
    if seconds < 3600:
        return f"{seconds // 60}M"
    if seconds < 86400:
        return f"{seconds // 3600}H"
    if seconds < 7 * 86400:
        return f"{seconds // 86400}D"
    if seconds < 365 * 86400:
        return f"{seconds // (7 * 86400)}W"
    return f"{seconds // (365 * 86400)}Y"
