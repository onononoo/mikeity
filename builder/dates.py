"""
date parsing and formatting for historical dates.

dates in the data files are written the way a person would write them:

    "13.8 billion years ago"      deep time, measured back from the present
    "66 mya", "300 kya"           short forms of the above
    "c. 3100 bce"                 approximate year before the common era
    "1492", "476 ce"              plain years in the common era
    "1914-1918", "c. 2600 to 2500 bce"   ranges (the era suffix is shared)
    "5th century bce"             centuries
    "1960s"                       decades
    "present", "today"            the current year

every date is turned into an hdate with a numeric start and end so it can be
sorted. years before the common era are negative. there is no year zero in
the historical calendar, but the tiny error that causes does not matter for
sorting, so it is ignored on purpose.
"""

import datetime
import re

# "years ago" dates count back from this year (the usual "before present" convention)
present = 1950

_approx_words = ("c.", "c", "ca.", "circa", "about", "around", "~")
_units = {
    "billion years ago": 1e9,
    "bya": 1e9,
    "million years ago": 1e6,
    "mya": 1e6,
    "thousand years ago": 1e3,
    "kya": 1e3,
    "years ago": 1,
}
_range_split = re.compile(r"\s*(?:–|—|\bto\b|\s-\s|(?<=[\da-z.])-(?=\d|present))\s*")
_number = r"(\d[\d,]*(?:\.\d+)?)"


class date_error(ValueError):
    pass


class hdate:
    """a parsed historical date or date range."""

    __slots__ = ("start", "end", "approx", "text", "deep")

    def __init__(self, start, end=None, approx=False, text="", deep=False):
        self.start = start
        self.end = start if end is None else end
        self.approx = approx
        self.text = text
        # deep dates are measured in years ago rather than calendar years
        self.deep = deep

    @property
    def key(self):
        return self.start

    @property
    def is_range(self):
        return self.end != self.start

    def contains(self, year):
        return self.start <= year <= self.end

    def overlaps(self, lo, hi):
        return self.start <= hi and self.end >= lo

    def __lt__(self, other):
        return (self.start, self.end) < (other.start, other.end)

    def __eq__(self, other):
        return isinstance(other, hdate) and (self.start, self.end) == (other.start, other.end)

    def __hash__(self):
        return hash((self.start, self.end))

    def __repr__(self):
        return f"hdate({self.start!r}, {self.end!r}, approx={self.approx}, text={self.text!r})"

    def __str__(self):
        return self.text or describe(self)


def _num(s):
    return float(s.replace(",", ""))


def _clean(s):
    return " ".join(s.lower().strip().split())


def _strip_approx(s):
    for w in _approx_words:
        if s.startswith(w + " ") or (w.endswith(".") and s.startswith(w)):
            return s[len(w):].strip(), True
    return s, False


def _era_of(s):
    """return (text without era suffix, era) where era is 'bce', 'ce' or none."""
    for suffix in ("bce", "bc", "b.c.e.", "b.c."):
        if s.endswith(" " + suffix) or s.endswith(suffix) and s[: -len(suffix)].rstrip()[-1:].isdigit():
            return s[: -len(suffix)].strip(), "bce"
    for suffix in ("ce", "ad", "c.e.", "a.d."):
        if s.endswith(" " + suffix):
            return s[: -len(suffix)].strip(), "ce"
    return s, None


def _ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _parse_single(s, shared_era=None):
    """parse one side of a range. returns (start, end, deep)."""
    if s in ("present", "the present", "today", "now"):
        y = datetime.date.today().year
        return y, y, False
    s, era = _era_of(s)
    era = era or shared_era

    # deep time: "66 million years ago", "4.5 bya"
    for unit, scale in _units.items():
        m = re.fullmatch(_number + r"\s*" + re.escape(unit), s)
        if m:
            y = present - _num(m.group(1)) * scale
            return y, y, True

    # centuries: "5th century", "15th century ce"
    m = re.fullmatch(r"(\d+)(?:st|nd|rd|th)\s+century", s)
    if m:
        n = int(m.group(1))
        if era == "bce":
            return -(n * 100), -((n - 1) * 100 + 1), False
        return (n - 1) * 100 + 1, n * 100, False

    # decades: "1960s"
    m = re.fullmatch(r"(\d+0)s", s)
    if m:
        y = int(m.group(1))
        if era == "bce":
            return -(y + 9), -y, False
        return y, y + 9, False

    # plain years: "1492", "10,000"
    m = re.fullmatch(_number, s)
    if m:
        y = _num(m.group(1))
        y = int(y) if y.is_integer() else y
        return (-y, -y, False) if era == "bce" else (y, y, False)

    raise date_error(f"cannot understand date part: {s!r}")


def parse(text):
    """parse a date string into an hdate. raises date_error on nonsense."""
    if isinstance(text, hdate):
        return text
    if isinstance(text, (int, float)):
        return hdate(text, text, text=format_year(text))

    s = _clean(str(text))
    if not s:
        raise date_error("empty date")

    s, approx = _strip_approx(s)
    parts = [p for p in _range_split.split(s) if p]
    if len(parts) > 2:
        raise date_error(f"too many parts in date range: {text!r}")

    if len(parts) == 1:
        start, end, deep = _parse_single(parts[0])
    else:
        left, right = parts
        left, left_approx = _strip_approx(left)
        right, right_approx = _strip_approx(right)
        approx = approx or left_approx or right_approx
        # "2600-2500 bce": the era on the right side applies to both
        _, right_era = _era_of(right)
        _, left_era = _era_of(left)
        a0, a1, deep_a = _parse_single(left, None if left_era else right_era)
        b0, b1, deep_b = _parse_single(right)
        if a0 > b1:
            # "1918-1914" is almost always a typo, so refuse it
            raise date_error(f"date range runs backwards: {text!r}")
        start, end, deep = a0, max(a1, b1), deep_a or deep_b

    if start > end:
        raise date_error(f"date range runs backwards: {text!r}")

    d = hdate(start, end, approx=approx, deep=deep)
    d.text = describe(d, original=s)
    return d


def format_year(y):
    """turn a numeric year into text, e.g. -3100 -> '3100 bce', 476 -> '476 ce'."""
    if y < present - 100_000:
        return format_years_ago(present - y)
    y = int(round(y))
    if y < 0:
        return f"{-y:,} bce" if -y >= 10_000 else f"{-y} bce"
    if y < 1000:
        return f"{y} ce"
    return str(y)


def format_years_ago(n):
    for unit, scale in (("billion", 1e9), ("million", 1e6)):
        if n >= scale:
            v = n / scale
            v = f"{v:.2f}".rstrip("0").rstrip(".")
            return f"{v} {unit} years ago"
    step = -3 if n >= 10_000 else -2
    return f"{int(round(n, step)):,} years ago"


def describe(d, original=None):
    """a clean lowercase label for a date, used on the site."""
    prefix = "c. " if d.approx else ""
    if original:
        # keep centuries and decades in the words the author used
        s, _ = _strip_approx(original)
        if "century" in s or re.search(r"\d0s\b", s):
            return prefix + s
    now = re.search(r"\b(present|today|now)$", original or "")
    fmt = (lambda y: format_years_ago(present - y)) if d.deep else format_year
    if not d.is_range:
        return "the present" if now else prefix + fmt(d.start)
    a, b = fmt(d.start), ("present" if now else fmt(d.end))
    # "2600–2500 bce" reads better than "2600 bce–2500 bce"
    for suffix in (" bce", " ce", " years ago"):
        if a.endswith(suffix) and b.endswith(suffix) and suffix != " years ago":
            return f"{prefix}{a[: -len(suffix)]}–{b}"
    return f"{prefix}{a}–{b}"


def span_label(start, end):
    """describe how long a stretch of time lasted."""
    n = abs(end - start)
    for unit, scale in (("billion", 1e9), ("million", 1e6)):
        if n >= scale:
            v = f"{n / scale:.1f}".removesuffix(".0")
            return f"about {v} {unit} years"
    if n >= 1000:
        return f"about {int(round(n, -2)):,} years"
    return f"about {int(round(n))} years"


def year_input(text):
    """
    parse a loose year typed by a person, e.g. '500 bc', '-500', '66 mya'.
    used by the command line tools. returns a number or raises date_error.
    """
    s = _clean(text)
    if re.fullmatch(r"-?\d[\d,]*", s):
        return int(s.replace(",", ""))
    return parse(s).start
