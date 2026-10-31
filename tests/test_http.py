import io
import json
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from minitel.http import HttpError, get_json


class Response:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class HttpTests(unittest.TestCase):
    def test_success(self):
        seen = {}

        def fake_urlopen(request, timeout):
            seen["url"] = request.full_url
            seen["agent"] = request.get_header("User-agent")
            seen["timeout"] = timeout
            return Response(json.dumps({"ok": True}).encode("utf-8"))

        with patch("minitel.http.urlopen", fake_urlopen):
            result = get_json("https://example.test/data", timeout=3.0)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(seen["url"], "https://example.test/data")
        self.assertTrue(seen["agent"].startswith("minitel-videotex/"))
        self.assertEqual(seen["timeout"], 3.0)

    def test_caller_headers_merge(self):
        seen = {}

        def fake_urlopen(request, timeout):
            seen["header"] = request.get_header("X-test")
            return Response(b"{}")

        with patch("minitel.http.urlopen", fake_urlopen):
            get_json("https://example.test/", headers={"X-Test": "yes"})
        self.assertEqual(seen["header"], "yes")

    def test_http_error_with_retry_after(self):
        headers = Message()
        headers["Retry-After"] = "120"
        error = HTTPError(
            "https://example.test/",
            429,
            "Too Many Requests",
            headers,
            io.BytesIO(b"slow down"),
        )

        with patch("minitel.http.urlopen", side_effect=error):
            with self.assertRaises(HttpError) as caught:
                get_json("https://example.test/")

        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(caught.exception.retry_after, 120)
        self.assertEqual(caught.exception.body, b"slow down")

    def test_url_error(self):
        with patch("minitel.http.urlopen", side_effect=URLError("no route")):
            with self.assertRaises(HttpError) as caught:
                get_json("https://example.test/")
        self.assertIsNone(caught.exception.status)
        self.assertIn("no route", caught.exception.message)

    def test_invalid_json(self):
        with patch("minitel.http.urlopen", return_value=Response(b"not json")):
            with self.assertRaises(HttpError) as caught:
                get_json("https://example.test/")
        self.assertEqual(caught.exception.status, 200)
        self.assertEqual(caught.exception.message, "invalid JSON")


if __name__ == "__main__":
    unittest.main()
