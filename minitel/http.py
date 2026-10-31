"""Small synchronous JSON client for cache loader threads."""

import json
import time
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_USER_AGENT = "minitel-videotex/0.2"


class HttpError(Exception):
    def __init__(self, url, status=None, message="", body=b"", retry_after=None):
        super().__init__(message or f"HTTP error for {url}")
        self.url = url
        self.status = status
        self.message = message
        self.body = body
        self.retry_after = retry_after


def _retry_after(value):
    if not value:
        return None
    value = value.strip()
    try:
        return int(value)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    return max(0, int(when.timestamp() - time.time()))


def get_json(url, headers=None, timeout=10.0):
    request_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)

    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            body = response.read()
    except HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        raise HttpError(
            url,
            status=exc.code,
            message=str(exc),
            body=body,
            retry_after=_retry_after(
                exc.headers.get("Retry-After") if exc.headers else None
            ),
        ) from exc
    except URLError as exc:
        raise HttpError(url, message=str(exc.reason), body=b"") from exc
    except TimeoutError as exc:
        raise HttpError(url, message=str(exc), body=b"") from exc

    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HttpError(
            url, status=status, message="invalid JSON", body=body
        ) from exc
