"""Normalised train departure data."""

from dataclasses import dataclass
from datetime import datetime


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
    scheduled_at: datetime | None = None


@dataclass(frozen=True)
class DepartureBoard:
    station: str
    filter_to: str | None
    departures: tuple[Departure, ...]
    degraded: str | None = None


@dataclass(frozen=True)
class ServiceStop:
    code: str
    name: str
    scheduled: str
    arrival: str
    arrival_at: datetime | None
    platform: str | None
    cancelled: bool


@dataclass(frozen=True)
class ServiceDetail:
    unique_identity: str
    stops: tuple[ServiceStop, ...]
