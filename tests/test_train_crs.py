import unittest

from pages.trains._support.crs import parse_route, valid_crs


class CrsTests(unittest.TestCase):
    def test_valid_crs(self):
        self.assertTrue(valid_crs("PAD"))
        self.assertFalse(valid_crs("PADX"))
        self.assertFalse(valid_crs("pad"))
        self.assertFalse(valid_crs("P4D"))
        self.assertFalse(valid_crs(""))

    def test_parse_route_single_station(self):
        self.assertEqual(parse_route("PAD"), ("PAD", ""))
        self.assertEqual(parse_route(" pad "), ("PAD", ""))

    def test_parse_route_pair(self):
        self.assertEqual(parse_route("PADBRI"), ("PAD", "BRI"))
        self.assertEqual(parse_route("padbri"), ("PAD", "BRI"))

    def test_parse_route_rejects_invalid_tokens(self):
        self.assertIsNone(parse_route(None))
        self.assertIsNone(parse_route(""))
        self.assertIsNone(parse_route("PA"))
        self.assertIsNone(parse_route("PADX"))
        self.assertIsNone(parse_route("PADBR"))
        self.assertIsNone(parse_route("P4DBRI"))
        self.assertIsNone(parse_route("PADB4I"))


if __name__ == "__main__":
    unittest.main()
