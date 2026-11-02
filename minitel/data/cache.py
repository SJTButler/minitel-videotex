"""Non-blocking resource cache with stale-on-error semantics."""

import threading
import time
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Snapshot:
    value: object = None
    loaded_at: float | None = None
    error: BaseException | None = None
    loading: bool = False

    @property
    def has_value(self):
        return self.loaded_at is not None

    def age(self, now=None):
        if self.loaded_at is None:
            return None
        if now is None:
            now = time.monotonic()
        return max(0.0, now - self.loaded_at)


@dataclass
class _Entry:
    snapshot: Snapshot
    next_retry: float = 0.0
    last_used: float = 0.0


class ResourceCache:
    """A process-wide cache whose ``get`` never waits for the loader."""

    def __init__(self, ttl=300.0, retry_delay=60.0, max_entries=128,
                 clock=time.monotonic, thread_factory=None):
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.ttl = ttl
        self.retry_delay = retry_delay
        self.max_entries = max_entries
        self.clock = clock
        self.thread_factory = thread_factory
        self._entries = {}
        self._lock = threading.Lock()

    def snapshot(self, key):
        now = self.clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return Snapshot()
            entry.last_used = now
            return entry.snapshot

    def get(self, key, loader):
        now = self.clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._evict_for_new()
                entry = _Entry(Snapshot(), last_used=now)
                self._entries[key] = entry
            else:
                entry.last_used = now

            if self._is_fresh(entry, now):
                return entry.snapshot

            entry.snapshot = replace(entry.snapshot, loading=True)
            entry.next_retry = now + self.retry_delay
            snapshot = entry.snapshot

        self._start(key, loader)
        return snapshot

    def retry(self, key, loader):
        """Clear a failed-load backoff, then load if the entry needs it."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                entry.next_retry = 0.0
        return self.get(key, loader)

    def load_now(self, key, loader):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._evict_for_new()
                entry = _Entry(Snapshot(), last_used=self.clock())
                self._entries[key] = entry
            entry.snapshot = replace(entry.snapshot, loading=True)
            entry.last_used = self.clock()

        value = None
        error = None
        try:
            value = loader()
        except Exception as exc:
            error = exc

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry(Snapshot(), last_used=self.clock())
                self._entries[key] = entry
            snapshot = self._store(entry, value, error)
            return snapshot

    def _is_fresh(self, entry, now):
        snapshot = entry.snapshot
        if snapshot.loading:
            return True
        if entry.next_retry > now:
            return True
        if snapshot.loaded_at is None:
            return False
        if snapshot.error is not None:
            return False
        if self.ttl is None:
            return True
        return now - snapshot.loaded_at < self.ttl

    def _evict_for_new(self):
        while len(self._entries) >= self.max_entries:
            victim = min(
                self._entries,
                key=lambda key: self._entries[key].last_used,
            )
            del self._entries[victim]

    def _store(self, entry, value, error):
        old = entry.snapshot
        now = self.clock()
        if error is None:
            entry.snapshot = Snapshot(
                value=value, loaded_at=now, error=None, loading=False
            )
            entry.next_retry = 0.0
        else:
            entry.snapshot = Snapshot(
                value=old.value,
                loaded_at=old.loaded_at,
                error=error,
                loading=False,
            )
            entry.next_retry = now + self.retry_delay
        entry.last_used = now
        return entry.snapshot

    def _start(self, key, loader):
        if self.thread_factory is None:
            thread = threading.Thread(
                target=self._load, args=(key, loader), daemon=True
            )
        else:
            thread = self.thread_factory(self._load, (key, loader))
        thread.start()

    def _load(self, key, loader):
        value = None
        error = None
        try:
            value = loader()
        except Exception as exc:
            error = exc
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry(Snapshot(), last_used=self.clock())
                self._entries[key] = entry
            self._store(entry, value, error)
