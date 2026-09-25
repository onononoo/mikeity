import os
import tempfile
import unittest

from builder import extras

tsv = """# start\tend\tdate\tpart\tregion\ttext
-13799998050\t-13799998050\t13.8 billion years ago\t1\tthe universe\tthe big bang
-3000\t-3000\tc. 3000 bce\t4\teurope\tstonehenge is begun
-2600\t-2600\tc. 2600 bce\t4\tsouth asia\tthe indus cities
-2500\t-2000\t2500-2000 bce\t4\tafrica\ta long kingdom
-1900\t-1900\t1900 bce\t4\tthe middle east\tthing one
-1900\t-1900\t1900 bce\t4\tthe middle east\tthing two
1492\t1492\t1492\t7\tthe americas\tcolumbus
"""


class parse_tests(unittest.TestCase):
    """the text each tool prints, read back into records."""

    def test_charts(self):
        c = extras.parse_charts("a.svg\t740\t300\ta chart\n")
        self.assertEqual(c[0].src, "images/a.svg")
        self.assertEqual((c[0].width, c[0].height, c[0].alt), (740, 300, "a chart"))

    def test_gaps(self):
        g = extras.parse_gaps(
            "gap\t400\tc. 3000 bce\tstonehenge\tc. 2600 bce\tthe indus\n"
            "year\t1945\t3\t1945\ta / b / c\n"
            "year\t1914\t2\t1914\td / e\n")
        self.assertEqual(g.quiet[0].years, 400)
        self.assertEqual(g.quiet[0].after, "the indus")
        self.assertEqual([b.year for b in g.busy], [1945, 1914])
        self.assertEqual(g.busy[0].what, ["a", "b", "c"])

    def test_contemporaries(self):
        people = {"a": "person a", "b": "person b"}
        t = extras.parse_contemporaries("with\ta\tb\t12\ncount\ta\t1\nwith\ta\tnobody\t3\n", people)
        self.assertEqual(t["a"].count, 1)
        self.assertEqual([(o.person, o.years) for o in t["a"].alongside], [("person b", 12)])


@unittest.skipUnless(extras._find("awk", "gawk", "mawk"), "no awk")
class awk_tests(unittest.TestCase):
    """runs tools/gaps.awk on a tiny timeline."""

    def test_gaps_and_busy_years(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as out:
            os.makedirs(os.path.join(out, "data"))
            with open(os.path.join(out, "data", "events.tsv"), "w", encoding="utf-8", newline="\n") as f:
                f.write(tsv)
            g, skipped = extras.gaps(root, out)
        self.assertIsNone(skipped)
        # deep time is left out, and the long kingdom fills 2500 to 2000 bce
        self.assertEqual([q.years for q in g.quiet], [3392, 400, 100, 100])
        self.assertEqual([(b.year, b.events) for b in g.busy], [(-1900, 2)])


if __name__ == "__main__":
    unittest.main()
