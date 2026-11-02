"""Shared presentation for cached service snapshots."""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .layout import SECONDARY, WARNING


class SnapshotLike(Protocol):
    loaded_at: float | None
    error: object | None
    loading: bool

    @property
    def has_value(self) -> bool: ...

    def age(self) -> float | None: ...


class ServiceState(str, Enum):
    MISSING = "missing"
    LOADING = "loading"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    EMPTY = "empty"
    READY = "ready"


@dataclass(frozen=True)
class ServiceStatus:
    state: ServiceState
    text: str
    colour: int


def updated_label(snapshot):
    age = snapshot.age()
    if age is None:
        return ""
    try:
        return time.strftime("%H:%M", time.localtime(time.time() - age))
    except (OSError, OverflowError, ValueError):
        return "--:--"


def classify(snapshot, *, empty=False):
    if snapshot is None:
        return ServiceState.MISSING
    if snapshot.error is not None:
        if snapshot.has_value:
            return ServiceState.STALE
        return ServiceState.UNAVAILABLE
    if not snapshot.has_value:
        return ServiceState.LOADING
    if empty:
        return ServiceState.EMPTY
    return ServiceState.READY


def classify_many(snapshots, *, empty=False):
    snapshots = tuple(snapshots)
    if not snapshots:
        return ServiceState.MISSING
    values = [snapshot for snapshot in snapshots if snapshot.has_value]
    if values:
        if any(snapshot.error is not None for snapshot in values):
            return ServiceState.STALE
        if empty:
            return ServiceState.EMPTY
        return ServiceState.READY
    if any(snapshot.loading for snapshot in snapshots):
        return ServiceState.LOADING
    if any(snapshot.error is not None for snapshot in snapshots):
        return ServiceState.UNAVAILABLE
    return ServiceState.LOADING


def colour_for(state):
    if state in (
        ServiceState.MISSING,
        ServiceState.UNAVAILABLE,
        ServiceState.STALE,
    ):
        return WARNING
    return SECONDARY


def _text_for(state, snapshot, *, missing_text, loading_text,
              unavailable_text, empty_text, stale_prefix, updated_prefix,
              stale_time=True, updated_time=True):
    if state is ServiceState.MISSING:
        return missing_text
    if state is ServiceState.LOADING:
        return loading_text
    if state is ServiceState.UNAVAILABLE:
        return unavailable_text
    if state is ServiceState.EMPTY:
        return empty_text
    prefix = stale_prefix if state is ServiceState.STALE else updated_prefix
    if state is ServiceState.STALE and not stale_time:
        return prefix
    if state is ServiceState.READY and not updated_time:
        return prefix
    return f"{prefix} {updated_label(snapshot)}".strip()


def describe(snapshot, *, empty=False, missing_text="NOT CONFIGURED",
             loading_text="LOADING", unavailable_text="UNAVAILABLE",
             empty_text="NO DATA", stale_prefix="OFFLINE - CACHED",
             updated_prefix="UPDATED", stale_time=True, updated_time=True):
    state = classify(snapshot, empty=empty)
    return ServiceStatus(
        state,
        _text_for(
            state,
            snapshot,
            missing_text=missing_text,
            loading_text=loading_text,
            unavailable_text=unavailable_text,
            empty_text=empty_text,
            stale_prefix=stale_prefix,
            updated_prefix=updated_prefix,
            stale_time=stale_time,
            updated_time=updated_time,
        ),
        colour_for(state),
    )


def describe_many(snapshots, *, empty=False, missing_text="NOT CONFIGURED",
                  loading_text="LOADING", unavailable_text="UNAVAILABLE",
                  empty_text="NO DATA", stale_prefix="OFFLINE - CACHED",
                  updated_prefix="UPDATED"):
    snapshots = tuple(snapshots)
    state = classify_many(snapshots, empty=empty)
    latest = None
    if state in (ServiceState.STALE, ServiceState.READY):
        latest = max(
            (snapshot for snapshot in snapshots if snapshot.has_value),
            key=lambda snapshot: snapshot.loaded_at or 0,
        )
    return ServiceStatus(
        state,
        _text_for(
            state,
            latest,
            missing_text=missing_text,
            loading_text=loading_text,
            unavailable_text=unavailable_text,
            empty_text=empty_text,
            stale_prefix=stale_prefix,
            updated_prefix=updated_prefix,
        ),
        colour_for(state),
    )
