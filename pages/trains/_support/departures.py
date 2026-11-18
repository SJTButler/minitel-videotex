"""Shared train-board columns for the train pages."""

from minitel_kit import Column, Table

from pages.common.layout import SECONDARY

TRAIN_TABLE = Table(
    Column("TIME", 5),
    Column("DESTINATION", 21),
    Column("PLT", 3, align="right"),
    Column("STATUS", 8),
)

CALLS_TABLE = Table(
    Column("TIME", 5),
    Column("STATION", 12),
)

RIGHT_TABLE = Table(
    Column("TIME", 5),
    Column("DESTINATION", 11),
    Column("PLT", 3, align="right"),
)


def train_header(screen, row, *, col=0):
    TRAIN_TABLE.header(screen, row, col, attrs={"fg": SECONDARY})


def train_row(screen, row, departure, *, col=0, inverse=False):
    TRAIN_TABLE.row(
        screen,
        row,
        (
            departure.scheduled,
            departure.destination,
            departure.platform or "-",
            departure.status,
        ),
        col,
        attrs={"inverse": inverse},
    )


def calls_header(screen, row, *, col=0):
    CALLS_TABLE.header(screen, row, col, attrs={"fg": SECONDARY})


def calls_row(screen, row, stop, *, col=0, inverse=False):
    CALLS_TABLE.row(
        screen,
        row,
        (stop.scheduled, stop.name),
        col,
        attrs={"inverse": inverse},
    )


def right_header(screen, row, *, col=0):
    RIGHT_TABLE.header(screen, row, col, attrs={"fg": SECONDARY})


def right_row(screen, row, departure, *, col=0, inverse=False):
    RIGHT_TABLE.row(
        screen,
        row,
        (
            departure.scheduled,
            departure.destination,
            departure.platform or "-",
        ),
        col,
        attrs={"inverse": inverse},
    )
