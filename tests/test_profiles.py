import unittest

from minitel.terminal import profiles


class ProfileTests(unittest.TestCase):
    def test_m1_types(self):
        self.assertIs(profiles.by_type(0x62), profiles.M1)
        self.assertIs(profiles.by_type(0x63), profiles.M1)
        self.assertIs(profiles.by_type(0x72), profiles.M1)

    def test_m1_colour(self):
        self.assertIs(profiles.by_type(0x73), profiles.M1C)
        self.assertTrue(profiles.M1C.colour)

    def test_m2_defaults_to_mono(self):
        self.assertIs(profiles.by_type(0x76), profiles.M2_MONO)
        self.assertFalse(profiles.M2_MONO.colour)
        self.assertTrue(profiles.M2_MONO.drcs)

    def test_m2_colour_override(self):
        self.assertIs(profiles.by_type(0x76, colour=True), profiles.M2_COLOUR)
        self.assertTrue(profiles.M2_COLOUR.colour)

    def test_unknown_falls_back_to_m1(self):
        self.assertIs(profiles.by_type(0x99), profiles.UNKNOWN)
        self.assertIs(profiles.UNKNOWN, profiles.M1)

    def test_cps(self):
        self.assertAlmostEqual(profiles.cps(1200), 133.333, places=2)
        self.assertAlmostEqual(profiles.cps(4800), 533.333, places=2)
        self.assertAlmostEqual(profiles.cps(9600), 1066.667, places=2)


if __name__ == "__main__":
    unittest.main()
