import datetime
import unittest

from builder import dates
from builder.dates import date_error, parse


class parse_tests(unittest.TestCase):
    def check(self, text, start, end=None, label=None, approx=False):
        d = parse(text)
        self.assertEqual(d.start, start, text)
        self.assertEqual(d.end, start if end is None else end, text)
        self.assertEqual(d.approx, approx, text)
        if label is not None:
            self.assertEqual(str(d), label, text)

    def test_plain_years(self):
        self.check("1492", 1492, label="1492")
        self.check("476 ce", 476, label="476 ce")
        self.check("476", 476, label="476 ce")
        self.check("44 bce", -44, label="44 bce")
        self.check("3100 bc", -3100, label="3100 bce")

    def test_approximate(self):
        self.check("c. 3100 bce", -3100, label="c. 3100 bce", approx=True)
        self.check("c.1200", 1200, label="c. 1200", approx=True)
        self.check("circa 800", 800, approx=True)

    def test_commas(self):
        self.check("10,000 bce", -10000, label="10,000 bce")

    def test_ranges(self):
        self.check("1914-1918", 1914, 1918, label="1914–1918")
        self.check("1914–1918", 1914, 1918)
        self.check("264-146 bce", -264, -146, label="264–146 bce")
        self.check("c. 2600 to 2500 bce", -2600, -2500, label="c. 2600–2500 bce", approx=True)
        self.check("63 bce-14 ce", -63, 14, label="63 bce–14 ce")
        self.check("500 bce - 100 ce", -500, 100)

    def test_deep_time(self):
        d = parse("66 million years ago")
        self.assertEqual(d.start, dates.present - 66e6)
        self.assertTrue(d.deep)
        self.assertEqual(str(d), "66 million years ago")
        self.assertEqual(str(parse("4.54 billion years ago")), "4.54 billion years ago")
        self.assertEqual(str(parse("66 mya")), "66 million years ago")
        self.assertEqual(str(parse("300,000 years ago")), "300,000 years ago")
        self.assertEqual(str(parse("12,000 years ago")), "12,000 years ago")

    def test_centuries_and_decades(self):
        self.check("5th century bce", -500, -401, label="5th century bce")
        self.check("15th century", 1401, 1500, label="15th century")
        self.check("21st century", 2001, 2100)
        self.check("1960s", 1960, 1969, label="1960s")

    def test_present(self):
        now = datetime.date.today().year
        self.check("present", now, label="the present")
        self.check("1945 to present", 1945, now, label="1945–present")
        self.check("1955-present", 1955, now)

    def test_sorting(self):
        texts = ["1492", "13.8 billion years ago", "c. 3100 bce", "44 bce", "1914-1918", "66 mya"]
        ordered = [str(d) for d in sorted(parse(t) for t in texts)]
        self.assertEqual(ordered, ["13.8 billion years ago", "66 million years ago",
                                   "c. 3100 bce", "44 bce", "1492", "1914–1918"])

    def test_bad_dates(self):
        for bad in ("", "yesterday", "12 potatoes", "1918-1914", "1 to 2 to 3"):
            with self.assertRaises(date_error, msg=bad):
                parse(bad)

    def test_overlaps(self):
        ww1 = parse("1914-1918")
        self.assertTrue(ww1.overlaps(1900, 1914))
        self.assertTrue(ww1.overlaps(1918, 2000))
        self.assertFalse(ww1.overlaps(1919, 2000))
        self.assertTrue(ww1.contains(1916))


class format_tests(unittest.TestCase):
    def test_format_year(self):
        self.assertEqual(dates.format_year(-3100), "3100 bce")
        self.assertEqual(dates.format_year(-12000), "12,000 bce")
        self.assertEqual(dates.format_year(79), "79 ce")
        self.assertEqual(dates.format_year(2001), "2001")

    def test_span(self):
        self.assertEqual(dates.span_label(-13.8e9, -7e6), "about 13.8 billion years")
        self.assertEqual(dates.span_label(1914, 1945), "about 31 years")
        self.assertEqual(dates.span_label(-3500, -800), "about 2,700 years")

    def test_year_input(self):
        self.assertEqual(dates.year_input("-500"), -500)
        self.assertEqual(dates.year_input("500 bc"), -500)
        self.assertEqual(dates.year_input("1,066"), 1066)


if __name__ == "__main__":
    unittest.main()
