"""Shared two-column score grid for sports pages."""

from dataclasses import dataclass

from minitel.text import fit

from ...common.layout import ACCENT, SECONDARY

SCORE_TOP = 4
SCORE_ROWS = 11
COLUMN_WIDTH = 20
MAX_MATCHES = SCORE_ROWS * 2


@dataclass(frozen=True)
class MatchCard:
    code: str
    kickoff: object
    home: str
    away: str
    score: str
    status: str
    live: bool = False
    order: object = 0
    source: object = None


@dataclass(frozen=True)
class ScoreRow:
    label: str = ""
    left: object = None
    right: object = None


@dataclass(frozen=True)
class LeaguePage:
    code: str
    number: int
    count: int
    rows: tuple
    matches: tuple


def match_cell(card, number):
    home = str(card.home)[:3]
    away = str(card.away)[:3]
    return (
        f"{number:>2} {home:<3} {card.score:>3} {away:<3} "
    )


def status_suffix(card):
    return f"{card.status[:5]:<5}" if card.status else "     "


def draw_cell(screen, row, col, card, number):
    screen.text(row, col, fit(match_cell(card, number), COLUMN_WIDTH))
    suffix = status_suffix(card)
    if suffix.strip():
        colour = ACCENT if card.live else SECONDARY
        screen.text(row, col + 15, suffix, fg=colour)


def league_rows(cards, kickoff_label, sort_key=None):
    groups = {}
    for card in cards:
        groups.setdefault(kickoff_label(card.kickoff), []).append(card)
    ordered = sorted(
        groups.items(),
        key=lambda item: min(card.kickoff for card in item[1]),
    )
    key = sort_key or (lambda card: (card.home, card.away, card.order))
    pages = []
    current = []
    for label, group in ordered:
        group.sort(key=key)
        pairs = [group[index:index + 2] for index in range(0, len(group), 2)]
        chunk_size = SCORE_ROWS - 1
        chunks = [
            pairs[index:index + chunk_size]
            for index in range(0, len(pairs), chunk_size)
        ]
        for chunk in chunks:
            needed = 1 + len(chunk)
            if len(current) + needed > SCORE_ROWS:
                if current:
                    pages.append(current)
                current = []
            current.append(ScoreRow(label=label))
            for pair in chunk:
                current.append(
                    ScoreRow(
                        left=pair[0],
                        right=pair[1] if len(pair) > 1 else None,
                    )
                )
    if current:
        pages.append(current)
    return tuple(pages)


def build_pages(code, cards, kickoff_label, sort_key=None):
    rows_pages = league_rows(cards, kickoff_label, sort_key=sort_key)
    pages = []
    for index, rows in enumerate(rows_pages):
        matches = tuple(
            card
            for row in rows
            for card in (row.left, row.right)
            if card is not None
        )
        pages.append(
            LeaguePage(
                code=code,
                number=index + 1,
                count=len(rows_pages),
                rows=rows,
                matches=matches,
            )
        )
    return tuple(pages)


def draw_rows(screen, page, *, top=SCORE_TOP, start_number=1):
    if page is None or not page.rows:
        return start_number
    number = start_number
    for index, item in enumerate(page.rows):
        row = top + index
        if item.label:
            screen.text(row, 0, item.label, fg=ACCENT, underline=True)
            continue
        if item.left is not None:
            draw_cell(screen, row, 0, item.left, number)
            number += 1
        if item.right is not None:
            draw_cell(screen, row, COLUMN_WIDTH, item.right, number)
            number += 1
    return number
