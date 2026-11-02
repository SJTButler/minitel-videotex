import time
import unittest

from pages.common.clock import (
    clock_hm,
    clock_seconds,
    clock_text,
    date_text,
    local_now,
)


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.now = time.strptime("2026-11-02 09:05:07", "%Y-%m-%d %H:%M:%S")

    def test_formats_a_given_time(self):
        self.assertEqual(clock_text(self.now), "09:05:07")
        self.assertEqual(clock_hm(self.now), "09:05")
        self.assertEqual(clock_seconds(self.now), "07")
        self.assertEqual(date_text(self.now), "02/11/2026")

    def test_local_now_returns_a_time_struct(self):
        self.assertIsInstance(local_now(), time.struct_time)


if __name__ == "__main__":
    unittest.main()
