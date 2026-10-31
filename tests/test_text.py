import unittest

from minitel.text import age, domain, fit, plain, sanitize, wrap


class PlainTests(unittest.TestCase):
    def test_strips_tags_and_unescapes(self):
        self.assertEqual(
            plain("<p>Hello &amp; <b>goodbye</b></p>"),
            "Hello & goodbye",
        )

    def test_collapses_whitespace(self):
        self.assertEqual(plain("  a\n\t b   c  "), "a b c")

    def test_none_is_empty(self):
        self.assertEqual(plain(None), "")


class SanitizeTests(unittest.TestCase):
    def test_typographic_punctuation(self):
        self.assertEqual(
            sanitize("\u2018one\u2019 \u201ctwo\u201d \u2013 three\u2026"),
            "'ONE' \"TWO\" - THREE...",
        )

    def test_entities_are_unescaped(self):
        self.assertEqual(sanitize("Tom &amp; Jerry &#x27;live&#x27;"),
                         "TOM & JERRY 'LIVE'")

    def test_accents_are_transliterated(self):
        self.assertEqual(sanitize("caf\u00e9 na\u00efve \u00c9LAN"), "CAFE NAIVE ELAN")

    def test_symbols_become_ascii(self):
        self.assertEqual(
            sanitize("\u20ac5 \u00a33 \u00bd cup \u0153uvre \u00df"),
            "EUR5 GBP3 1/2 CUP OEUVRE SS",
        )

    def test_emoji_are_dropped(self):
        self.assertEqual(sanitize("hello \U0001f680 world \u2764"), "HELLO WORLD")

    def test_non_latin_letters_become_question_marks(self):
        self.assertEqual(sanitize("\u65e5\u672c\u8a9e"), "???")

    def test_uppercase_can_be_disabled(self):
        self.assertEqual(sanitize("Hello", uppercase=False), "Hello")


class FitTests(unittest.TestCase):
    def test_short_value_is_unchanged(self):
        self.assertEqual(fit("HELLO", 10), "HELLO")

    def test_long_value_is_truncated(self):
        self.assertEqual(fit("HELLO WORLD", 8), "HELLO...")

    def test_tiny_width(self):
        self.assertEqual(fit("HELLO", 2), "HE")

    def test_zero_width(self):
        self.assertEqual(fit("HELLO", 0), "")


class WrapTests(unittest.TestCase):
    def test_words_wrap(self):
        self.assertEqual(wrap("HELLO WORLD AGAIN", 11), ["HELLO WORLD", "AGAIN"])

    def test_long_word_is_hard_split(self):
        self.assertEqual(wrap("ABCDEFGHIJ", 4), ["ABCD", "EFGH", "IJ"])

    def test_max_lines_adds_ellipsis(self):
        lines = wrap("ONE TWO THREE FOUR FIVE", 9, max_lines=2)
        self.assertEqual(lines, ["ONE TWO", "THREE..."])

    def test_no_ellipsis_when_it_fits(self):
        self.assertEqual(wrap("ONE TWO", 9, max_lines=2), ["ONE TWO"])

    def test_empty(self):
        self.assertEqual(wrap("", 10), [])


class DomainTests(unittest.TestCase):
    def test_removes_www(self):
        self.assertEqual(domain("https://www.science.org/article"), "science.org")

    def test_keeps_subdomains(self):
        self.assertEqual(domain("https://news.ycombinator.com/item?id=1"),
                         "news.ycombinator.com")

    def test_scheme_less(self):
        self.assertEqual(domain("example.com/path"), "example.com")

    def test_empty(self):
        self.assertEqual(domain(""), "")
        self.assertEqual(domain(None), "")


class AgeTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(age(0), "NOW")
        self.assertEqual(age(59), "NOW")
        self.assertEqual(age(60), "1M")
        self.assertEqual(age(3599), "59M")
        self.assertEqual(age(3600), "1H")
        self.assertEqual(age(86400), "1D")
        self.assertEqual(age(7 * 86400), "1W")
        self.assertEqual(age(365 * 86400), "1Y")

    def test_invalid(self):
        self.assertEqual(age(None), "")


if __name__ == "__main__":
    unittest.main()
