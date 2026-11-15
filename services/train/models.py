"""Normalised train departure data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Departure:
    scheduled: str
    expected: str | None
    destination: str
    platform: str | None
    operator: str
    status: str
    cancelled: bool
    unique_identity: str


@dataclass(frozen=True)
class DepartureBoard:
    station: str
    filter_to: str | None
    departures: tuple[Departure, ...]
    degraded: str | None = None
