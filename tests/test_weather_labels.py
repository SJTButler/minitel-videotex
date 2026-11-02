import unittest

from pages.weather.labels import condition_label


class WeatherLabelTests(unittest.TestCase):
    def test_known_codes(self):
        self.assertEqual(condition_label(0), "CLEAR")
        self.assertEqual(condition_label(3), "OVERCAST")
        self.assertEqual(condition_label(95), "THUNDERSTORM")

    def test_unknown_codes(self):
        self.assertEqual(condition_label(None), "UNKNOWN")
        self.assertEqual(condition_label(999), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
