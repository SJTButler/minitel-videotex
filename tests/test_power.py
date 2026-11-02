import unittest

from minitel.terminal.power import (
    POWER_OFF,
    POWER_ON,
    Power,
    PowerSignals,
    PowerWatcher,
)


class PowerWatcherTests(unittest.TestCase):
    def setUp(self):
        self.watcher = PowerWatcher()

    def test_power_off_is_detected(self):
        self.assertEqual(self.watcher.feed(POWER_OFF), [Power(False)])

    def test_power_on_is_split_safe(self):
        self.assertEqual(self.watcher.feed(POWER_ON[:1]), [])
        self.assertEqual(self.watcher.feed(POWER_ON[1:3]), [])
        self.assertEqual(self.watcher.feed(POWER_ON[3:]), [Power(True)])

    def test_plain_bytes_pass_through_in_order(self):
        self.assertEqual(self.watcher.feed(b"AB"), [b"AB"])

    def test_bytes_around_a_signal_are_preserved(self):
        self.assertEqual(
            self.watcher.feed(b"AB" + POWER_OFF + b"CD"),
            [b"AB", Power(False), b"CD"],
        )

    def test_both_signals_in_one_chunk_keep_their_order(self):
        self.assertEqual(
            self.watcher.feed(POWER_OFF + POWER_ON),
            [Power(False), Power(True)],
        )

    def test_partial_prefix_is_released_on_a_mismatch(self):
        self.assertEqual(self.watcher.feed(POWER_ON[:2]), [])
        self.assertEqual(self.watcher.feed(b"X"), [POWER_ON[:2] + b"X"])

    def test_empty_sequences_disable_matching(self):
        watcher = PowerWatcher(PowerSignals(off=b"", on=b""))
        self.assertEqual(watcher.feed(POWER_OFF + POWER_ON), [POWER_OFF + POWER_ON])

    def test_reset_drops_a_held_prefix(self):
        self.assertEqual(self.watcher.feed(POWER_ON[:2]), [])
        self.watcher.reset()
        self.assertEqual(self.watcher.feed(b"AB"), [b"AB"])


if __name__ == "__main__":
    unittest.main()
