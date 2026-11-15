"""Realtime Trains NG source and parser."""

import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from minitel.data.http import HttpError, get_json

from .models import Departure, DepartureBoard

LONDON = ZoneInfo("Europe/London")
DEFAULT_BASE = "https://data.rtt.io"
TOKEN_SAFETY = 300.0
REFERENCE_TTL = 86400.0


def _timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _hhmm(value):
    stamp = _timestamp(value)
    if stamp is None:
        return None
    return datetime.fromtimestamp(stamp, LONDON).strftime("%H:%M")


def _location_name(pair):
    location = (pair or {}).get("location") or {}
    name = location.get("description")
    if name:
        return name
    codes = location.get("shortCodes") or ()
    return codes[0] if codes else "UNKNOWN"


def _degraded(system):
    parts = []
    realtime = system.get("realtimeNetworkRail")
    if realtime and realtime != "OK":
        parts.append(
            "REALTIME LIMITED"
            if realtime == "REALTIME_DATA_LIMITED"
            else "NO REALTIME"
        )
    core = system.get("rttCore")
    if core and core != "OK":
        parts.append(
            "SCHEDULE ONLY" if core == "SCHEDULE_ONLY" else "RTT DEGRADED"
        )
    return " / ".join(parts) or None


def _status(departure, display):
    if departure.get("isCancelled") or display == "CANCELLED":
        return "CANCEL"
    if departure.get("realtimeNoReport"):
        return "NO REPORT"
    lateness = departure.get("realtimeAdvertisedLateness")
    if isinstance(lateness, (int, float)) and lateness != 0:
        return f"{int(lateness):+d}"
    expected = (
        departure.get("realtimeForecast")
        or departure.get("realtimeEstimate")
        or departure.get("realtimeActual")
    )
    return "ON TIME" if expected else "SCHEDULED"


class RttSource:
    """Fetch and normalise departures from the Realtime Trains NG API."""

    def __init__(
        self,
        *,
        access_token=None,
        refresh_token=None,
        base_url=DEFAULT_BASE,
        get_json=get_json,
        clock=time.time,
        timeout=10.0,
        window_minutes=60,
    ):
        self.base_url = base_url.rstrip("/")
        self._get_json = get_json
        self.clock = clock
        self.timeout = timeout
        self.window_minutes = int(window_minutes)
        self._access_token = (access_token or "").strip() or None
        self._refresh_token = (refresh_token or "").strip() or None
        self._access_until = None
        self._lock = threading.Lock()
        self._names = {}
        self._names_until = 0.0
        self._names_loading = False
        self._names_lock = threading.Lock()

    @property
    def configured(self):
        return bool(self._access_token or self._refresh_token)

    def _invalidate(self):
        with self._lock:
            self._access_token = None
            self._access_until = None

    def _access(self):
        with self._lock:
            now = self.clock()
            if self._access_token and (
                self._access_until is None
                or now < self._access_until - TOKEN_SAFETY
            ):
                return self._access_token
            if not self._refresh_token:
                if self._access_token:
                    return self._access_token
                raise RuntimeError("TRAIN DATA NOT CONFIGURED")
            url = f"{self.base_url}/api/get_access_token"
            payload = self._get_json(
                url,
                headers={
                    "Authorization": f"Bearer {self._refresh_token}"
                },
                timeout=self.timeout,
            )
            token = payload.get("token") if isinstance(payload, dict) else None
            if not token:
                raise RuntimeError("TRAIN TOKEN REFRESH FAILED")
            self._access_token = token
            self._access_until = _timestamp(payload.get("validUntil"))
            return self._access_token

    def station_name(self, code):
        code = str(code).strip().upper()
        if not code:
            return None
        self._ensure_names()
        with self._names_lock:
            return self._names.get(code)

    def _ensure_names(self):
        with self._names_lock:
            if self._names and self.clock() < self._names_until:
                return
            if self._names_loading:
                return
            self._names_loading = True
        threading.Thread(
            target=self._load_names, daemon=True
        ).start()

    def _load_names(self):
        try:
            token = self._access()
            payload = self._get_json(
                f"{self.base_url}/data/locations_ungrouped",
                headers={"Authorization": f"Bearer {token}"},
                timeout=max(self.timeout, 20.0),
            )
            names = {}
            for location in payload.get("locations") or ():
                short = location.get("shortCode")
                description = location.get("description")
                if short and description:
                    names[str(short).upper()] = description
            with self._names_lock:
                self._names = names
                self._names_until = self.clock() + REFERENCE_TTL
        except Exception:
            with self._names_lock:
                self._names_until = self.clock() + 300.0
        finally:
            with self._names_lock:
                self._names_loading = False

    def _location_url(self, origin, destination):
        params = {"code": origin, "timeWindow": self.window_minutes}
        if destination:
            params["filterTo"] = destination
        return f"{self.base_url}/gb-nr/location?{urlencode(params)}"

    def _fetch(self, url):
        token = self._access()
        try:
            return self._get_json(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except HttpError as exc:
            if exc.status in (401, 403):
                self._invalidate()
            raise

    def departures(self, origin, destination=None):
        origin = str(origin).strip().upper()
        destination = (
            str(destination).strip().upper() if destination else None
        )
        if not origin:
            raise ValueError("origin CRS code is required")
        url = self._location_url(origin, destination)
        empty = DepartureBoard(origin, destination, ())
        payload = None
        for attempt in (0, 1):
            try:
                payload = self._fetch(url)
                break
            except HttpError as exc:
                if exc.status == 204:
                    return empty
                if (
                    exc.status in (401, 403)
                    and attempt == 0
                    and self._refresh_token
                ):
                    continue
                raise
        if payload is None:
            return empty
        return self._parse(payload, origin, destination)

    def _parse(self, payload, origin, destination):
        services = payload.get("services") or ()
        system = payload.get("systemStatus") or {}
        query = payload.get("query") or {}
        location = query.get("location") or {}
        station = location.get("description") or origin
        rows = []
        for service in services:
            metadata = service.get("scheduleMetadata") or {}
            temporal = service.get("temporalData") or {}
            departure = temporal.get("departure") or {}
            display = temporal.get("displayAs")
            if not departure or display in (
                "PASS", "DIVERTED", "TERMINATES",
            ):
                continue
            scheduled_iso = (
                departure.get("scheduleAdvertised")
                or departure.get("scheduleInternal")
            )
            scheduled = _hhmm(scheduled_iso)
            if scheduled is None:
                continue
            expected = _hhmm(
                departure.get("realtimeForecast")
                or departure.get("realtimeEstimate")
                or departure.get("realtimeActual")
            )
            destinations = service.get("destination") or ()
            platform_data = (
                (service.get("locationMetadata") or {}).get("platform") or {}
            )
            platform = (
                platform_data.get("actual")
                or platform_data.get("planned")
            )
            operator_data = metadata.get("operator") or {}
            operator = (
                operator_data.get("name")
                or operator_data.get("code")
                or ""
            )
            rows.append(
                (
                    scheduled_iso,
                    Departure(
                        scheduled=scheduled,
                        expected=expected,
                        destination=(
                            _location_name(destinations[0])
                            if destinations else "UNKNOWN"
                        ),
                        platform=str(platform) if platform else None,
                        operator=operator,
                        status=_status(departure, display),
                        cancelled=(
                            bool(departure.get("isCancelled"))
                            or display == "CANCELLED"
                        ),
                        unique_identity=metadata.get("uniqueIdentity") or "",
                    ),
                )
            )
        rows.sort(key=lambda row: row[0])
        return DepartureBoard(
            station=station,
            filter_to=destination,
            departures=tuple(row[1] for row in rows),
            degraded=_degraded(system),
        )
