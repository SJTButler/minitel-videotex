"""Cached Realtime Trains departure service."""

import os
import time
from typing import Protocol

from minitel.data.cache import ResourceCache
from minitel.data.services import ChangeNotifier, service

from services.common.config import env_seconds, load_env_file

from .source import RttSource


class TrainSource(Protocol):
    configured: bool

    def departures(self, origin, destination=None, *, time_from=None): ...


class TrainService(ChangeNotifier):
    def __init__(
        self,
        source,
        *,
        ttl=60.0,
        retry_delay=30.0,
        max_entries=16,
        clock=time.monotonic,
    ):
        super().__init__()
        self.source = source
        self.configured = bool(
            source is not None and getattr(source, "configured", True)
        )
        self.cache = ResourceCache(
            ttl,
            retry_delay,
            max_entries=max_entries,
            clock=clock,
            notify=self._changed,
        )
        self.service_cache = ResourceCache(
            300.0,
            retry_delay,
            max_entries=max_entries,
            clock=clock,
            notify=self._changed,
        )

    def departures(self, origin, destination=None, *, time_from=None):
        if not self.configured:
            raise RuntimeError("TRAIN DATA NOT CONFIGURED")
        key = (origin, destination, time_from)
        return self.cache.get(
            key,
            lambda: self.source.departures(
                origin, destination, time_from=time_from
            ),
        )

    def service(self, unique_identity):
        if not self.configured:
            raise RuntimeError("TRAIN DATA NOT CONFIGURED")
        return self.service_cache.get(
            unique_identity,
            lambda: self.source.service(unique_identity),
        )

    def station_name(self, code):
        resolver = getattr(self.source, "station_name", None)
        if resolver is None:
            return None
        return resolver(code)


@service("train", description="Realtime Trains NG departures")
def build_train_service():
    load_env_file()
    access = (os.environ.get("TRAINS_API_KEY") or "").strip()
    refresh = (os.environ.get("TRAINS_REFRESH_TOKEN") or "").strip()
    timeout = env_seconds(
        os.environ.get("TRAINS_TIMEOUT"), 10.0, minimum=1.0
    )
    return TrainService(
        RttSource(
            access_token=access or None,
            refresh_token=refresh or None,
            timeout=timeout,
        )
    )
